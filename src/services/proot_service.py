"""The only module allowed to import proot_distro."""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from core import storage_paths

logger = logging.getLogger(__name__)

_BOOTSTRAPPED = False


class ProotUnavailable(RuntimeError):
    """proot-distro cannot run on this interpreter (desktop Windows, no grp shim)."""


@dataclass
class Outcome:
    ok: bool
    detail: str
    output: str = ""


def bootstrap() -> None:
    """Env contract + shims before the first proot_distro import (idempotent)."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    from core import posixdb

    posixdb.ensure()
    os.environ.update(storage_paths.env_contract())
    _BOOTSTRAPPED = True


def available() -> bool:
    bootstrap()
    try:
        importlib.import_module("proot_distro")
    except Exception:
        return False
    return True


class _LineTee(io.TextIOBase):
    """A stderr stand-in that forwards each line to `on_line` as it is written.

    stdlib capture only — this is exactly `redirect_stderr` with a live hook,
    not a patch of anything upstream."""

    def __init__(self, on_line):
        self._on_line = on_line

    def write(self, data: str) -> int:
        if data.strip():
            for line in data.splitlines():
                if line.strip():
                    self._on_line(line)
        return len(data)

    def flush(self) -> None:  # pragma: no cover - trivial
        return None


def _run_command(
    module_name: str, fn_name: str, namespace: SimpleNamespace, on_line=None
) -> Outcome:
    """Run one upstream command_* handler with captured output.

    When `on_line` is given, upstream's stderr stage lines are forwarded live
    (the UI's progress source) as well as captured for the final report.
    """
    bootstrap()
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ProotUnavailable(f"proot_distro unavailable: {exc!r}") from exc
    fn = getattr(module, fn_name)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
            if on_line is not None:
                with contextlib.redirect_stderr(_LineTee(on_line)):
                    fn(namespace)
            else:
                fn(namespace)
        return Outcome(True, "completed", buf.getvalue())
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code == 0:
            return Outcome(True, "no-op", buf.getvalue())
        return Outcome(False, f"proot-distro exited {code}", buf.getvalue())
    except Exception as exc:
        return Outcome(False, f"{exc}", buf.getvalue())


# ── argparse namespaces (the only fragile part; verified against parser.py) ──


def _ns_install(image: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        image_ref=image,
        custom_container_name=name,
        override_arch=None,
        allow_insecure=False,
    )


def _ns_remove(name: str) -> SimpleNamespace:
    # Verified: _remove defines target/--image/--architecture/-v/-q.
    return SimpleNamespace(
        target=name,
        image=False,
        override_arch=None,
        verbose=False,
        quiet=False,
    )


def _ns_reset(name: str) -> SimpleNamespace:
    # Verified: _reset defines container_name/-q.
    return SimpleNamespace(
        container_name=name,
        verbose=False,
        quiet=False,
    )


# ── public API (plain data) ──────────────────────────────────────────────────


def _tree_bytes(path: Path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            with contextlib.suppress(OSError):
                total += (Path(dirpath) / f).stat().st_size
    return total


def _container_rows() -> list[dict]:
    """Installed containers via upstream's paths + a host-side size walk."""
    bootstrap()
    from proot_distro import paths

    containers_dir = storage_paths.containers_dir()
    rows: list[dict] = []
    for name in sorted(paths.installed_container_names()):
        image, arch = "", ""
        with contextlib.suppress(Exception):
            image, arch = paths.container_image_origin(name)
        rows.append(
            {
                "name": name,
                "image": image,
                "arch": arch,
                "size_bytes": _tree_bytes(containers_dir / name),
            }
        )
    return rows


def list_containers() -> list[dict]:
    """Installed containers. Raises with the real reason — the controller
    surfaces it in the UI instead of showing a silently empty list."""
    return _container_rows()


def install(image: str, name: str, on_line=None) -> Outcome:
    """Install `image` as `name`, forwarding upstream stage lines live.

    `image` is any reference upstream accepts (debian:bookworm,
    alpine@sha256:…, ./path.tar.gz, https://…). Empty name → upstream derives.
    """
    return _run_command(
        "proot_distro.commands.install",
        "command_install",
        _ns_install(image, name or None),
        on_line=on_line,
    )


def remove_container(name: str) -> Outcome:
    return _run_command(
        "proot_distro.commands.remove",
        "command_remove",
        _ns_remove(name),
    )


def reset_container(name: str) -> Outcome:
    return _run_command(
        "proot_distro.commands.reset",
        "command_reset",
        _ns_reset(name),
    )


def _ns_remove_image(identifier: str) -> SimpleNamespace:
    # Verified: remove.py defines target/--image/--architecture/-v/-q; --image
    # targets a cached image rather than a container.
    return SimpleNamespace(
        target=identifier,
        image=True,
        override_arch=None,
        verbose=False,
        quiet=False,
    )


def remove_cached_image(identifier: str) -> Outcome:
    """Delete one cached image's layers (storage reclaim; containers stay)."""
    return _run_command(
        "proot_distro.commands.remove",
        "command_remove",
        _ns_remove_image(identifier),
    )


def search_images(query: str, limit: int = 20) -> list[dict]:
    """Docker Hub search — upstream's own normalized hits (plain dicts)."""
    bootstrap()
    from proot_distro.helpers.docker import search as docker_search

    results, _total = docker_search.search_images(query, limit)
    return [r for r in results if isinstance(r, dict)]


def cached_images() -> list[dict]:
    """Cached OCI images (host-side sizes) for the storage screen."""
    bootstrap()
    from proot_distro.helpers.docker import cache

    rows = []
    for image in cache.iter_cached_images():
        size = 0
        with contextlib.suppress(Exception):
            path = image.get("full_path") or image.get("path")
            if path and Path(path).is_dir():
                size = _tree_bytes(Path(path))
        rows.append(
            {
                "identifier": image.get("image_ref") or image.get("id") or "?",
                "arch": image.get("arch", ""),
                "size_bytes": size,
            }
        )
    return rows


def storage_bytes() -> int:
    try:
        return _tree_bytes(storage_paths.xdg_data_home() / "proot-distro")
    except OSError as exc:
        raise ProotUnavailable(f"storage size unavailable: {exc}") from exc


def busy_locks() -> list[str]:
    """Locks held by other processes — 'install in progress' states."""
    bootstrap()
    try:
        from proot_distro import locking

        return [hint for _path, hint in locking.busy_locks()]
    except Exception:
        return []


def friendly_job_error(outcome: Outcome) -> str:
    """Translate an Outcome into one honest, actionable line."""
    detail = (outcome.detail or "").strip()
    if not detail:
        detail = (
            outcome.output.strip().splitlines()[-1] if outcome.output.strip() else "unknown error"
        )
    tail = outcome.output.strip().splitlines()[-3:]
    return f"{detail}" + (f" — {tail[-1]}" if tail and tail[-1] != detail else "")
