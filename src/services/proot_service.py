"""The only module allowed to import proot_distro."""

from __future__ import annotations

import contextlib
import importlib
import io
import logging
import os
import threading
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
    """Env contract + shims before the first proot_distro import (idempotent).

    Also resolves the payload env (PD_PROOT_BIN / PROOT_LOADER /
    LD_LIBRARY_PATH / PROOT_TMP_DIR) so every upstream call — including
    `login --get-proot-cmd`, which needs the proot binary — finds the binary
    even if the startup probe's native-dir lookup missed it.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    from core import posixdb

    posixdb.ensure()
    os.environ.update(storage_paths.env_contract())
    from core import proot_probe

    proot_probe.ensure_proot_env()
    _BOOTSTRAPPED = True


def available() -> bool:
    bootstrap()
    try:
        importlib.import_module("proot_distro")
    except Exception:
        return False
    return True


class _LineTee(io.TextIOBase):
    """A stderr stand-in that forwards each line to `on_line` as it is
    written AND keeps the text for the final Outcome.

    stdlib capture only — this is exactly `redirect_stderr` with a live hook,
    not a patch of anything upstream."""

    def __init__(self, on_line):
        self._on_line = on_line
        self._buf = io.StringIO()

    def write(self, data: str) -> int:
        self._buf.write(data)
        if data.strip():
            for line in data.splitlines():
                if line.strip():
                    self._on_line(line)
        return len(data)

    def flush(self) -> None:  # pragma: no cover - trivial
        return None

    def getvalue(self) -> str:
        return self._buf.getvalue()


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
    tee: _LineTee | None = None
    try:
        if on_line is not None:
            tee = _LineTee(on_line)
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(tee):
                fn(namespace)
        else:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                fn(namespace)
        captured = buf.getvalue() + (tee.getvalue() if tee is not None else "")
        return Outcome(True, "completed", captured)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        captured = buf.getvalue() + (tee.getvalue() if tee is not None else "")
        if code == 0:
            return Outcome(True, "no-op", captured)
        return Outcome(False, f"proot-distro exited {code}", captured)
    except Exception as exc:
        captured = buf.getvalue() + (tee.getvalue() if tee is not None else "")
        return Outcome(False, f"{exc}", captured)


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


def _ns_rename(orig: str, new: str) -> SimpleNamespace:
    return SimpleNamespace(orig_name=orig, new_name=new)


def _ns_backup(container: str, output: str, compression: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        container_name=container,
        output=output,
        compression=compression,
        verbose=False,
        quiet=False,
    )


def _ns_restore(archive: str) -> SimpleNamespace:
    return SimpleNamespace(archive=archive, verbose=False)


def _ns_copy(
    source: str, destination: str, move: bool = False, recursive: bool = True
) -> SimpleNamespace:
    return SimpleNamespace(
        source=source,
        destination=destination,
        verbose=False,
        quiet=False,
        move=move,
        recursive=recursive,
    )


def _ns_kill(target: str, all_sessions: bool = False, signal: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(target=target, all=all_sessions, signal=signal)


def _ns_clear_cache(orphan: bool = False, build_cache: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        orphan=orphan,
        build_cache=build_cache,
        verbose=False,
        quiet=False,
    )


def _ns_sync(
    source: str, destination: str, checksum: bool = True, delete: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        source=source,
        destination=destination,
        checksum=checksum,
        delete=delete,
        verbose=False,
        quiet=False,
    )


def _ns_run(container: str, run_args: list[str], work_dir: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        container_name=container,
        run_args=run_args,
        work_dir=work_dir,
        user="root",
        redirect_ports=False,
        shared_home=False,
        shared_tmp=False,
        shared_x11=False,
        bind=[],
        emulator=None,
        kernel=None,
        hostname=None,
        env=[],
        detach=False,
        get_proot_cmd=False,
    )


# ── public API (plain data) ──────────────────────────────────────────────────


def _tree_bytes(path: Path) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += (Path(dirpath) / f).stat().st_size
            except OSError:
                pass
    return total


def _container_rows() -> list[dict]:
    """Installed containers via upstream's paths + a host-side size walk."""
    bootstrap()
    from proot_distro import paths

    containers_dir = storage_paths.containers_dir()
    rows: list[dict] = []
    for name in sorted(paths.installed_container_names()):
        image, arch = "", ""
        try:
            image, arch = paths.container_image_origin(name)
        except Exception:
            pass
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
        try:
            path = image.get("full_path") or image.get("path")
            if path and Path(path).is_dir():
                size = _tree_bytes(Path(path))
        except Exception:
            pass
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


def _ns_login_get_proot_cmd(container: str) -> SimpleNamespace:
    # Verified against parser.py:116-160 (_add_login_or_run_common) + :262
    # (_login): every field _login_with_rootfs reads from the namespace.
    return SimpleNamespace(
        container_name=container,
        user="root",
        redirect_ports=False,
        fix_low_ports=False,
        isolated=False,
        minimal=False,
        shared_home=False,
        termux_home=False,
        shared_tmp=False,
        shared_x11=False,
        bind=[],
        no_link2symlink=False,
        no_sysvipc=False,
        no_kill_on_exit=False,
        emulator="",
        kernel="",
        hostname="",
        work_dir="",
        env=[],
        detach=False,
        get_proot_cmd=True,
        login_cmd=[],
    )


class _CapturedStdout:
    """sys.stdout stand-in carrying the `.buffer` upstream's printer writes to.

    login/__init__.py prints `--get-proot-cmd` output via
    `sys.stdout.buffer.write(...)`; io.StringIO has no `.buffer`, which made
    the previous capture raise AttributeError on every session open.
    """

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, data: str) -> int:  # upstream writes through .buffer
        return self.buffer.write(data.encode("utf-8", errors="replace"))

    def flush(self) -> None:  # pragma: no cover - trivial
        return None

    @property
    def value(self) -> str:
        return self.buffer.getvalue().decode("utf-8", errors="replace")


_GET_PROOT_CMD_LOCK = threading.Lock()


def get_proot_cmd(container: str, _retry: bool = True) -> str:
    """Upstream's own session command line: `pd login <c> --get-proot-cmd`.

    Calls `command_login` directly: `cli.main()` installs a SIGQUIT handler
    (main-thread-only) so it cannot run on a worker thread, and a subprocess
    is impossible on Android (`sys.executable` is the Flutter host). With
    `--get-proot-cmd` upstream prints the `env -i …` line and returns before
    any exec; parsing lives in session_service.
    """
    bootstrap()
    import sys

    from proot_distro.commands.login import command_login

    with _GET_PROOT_CMD_LOCK:
        stdout_backup = sys.stdout
        stderr_backup = sys.stderr
        captured = _CapturedStdout()
        errors = io.StringIO()
        sys.stdout = captured
        sys.stderr = errors
        try:
            command_login(_ns_login_get_proot_cmd(container))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            if code != 0:
                reason = errors.getvalue().strip().splitlines()
                detail = reason[-1][:200] if reason else "no output"
                # The payload env can resolve late on device (the probe's
                # native-dir glob is not the only path). Re-resolve and retry
                # once before surfacing the failure.
                if _retry and "proot utility does not exist" in errors.getvalue().lower():
                    from core import proot_probe

                    if proot_probe.ensure_proot_env(force=True):
                        logger.info("proot payload resolved on retry — reopening %s", container)
                        sys.stdout = stdout_backup
                        sys.stderr = stderr_backup
                        return get_proot_cmd(container, _retry=False)
                raise RuntimeError(f"login --get-proot-cmd exited {code} — {detail}") from exc
        finally:
            sys.stdout = stdout_backup
            sys.stderr = stderr_backup
    return captured.value


def rename_container(orig: str, new: str) -> Outcome:
    """Rename a container (upstream also rewrites its l2s symlinks)."""
    return _run_command(
        "proot_distro.commands.rename",
        "command_rename",
        _ns_rename(orig, new),
    )


def backup_container(container: str, output: str, compression: str | None = None) -> Outcome:
    """Write a container's tree to a tar archive (compression from the suffix)."""
    return _run_command(
        "proot_distro.commands.backup",
        "command_backup",
        _ns_backup(container, output, compression),
    )


def restore_container(archive: str) -> Outcome:
    """Restore a container tree from a tar archive (destroys the target)."""
    return _run_command(
        "proot_distro.commands.restore",
        "command_restore",
        _ns_restore(archive),
    )


def copy_path(source: str, destination: str, move: bool = False) -> Outcome:
    """Copy (or move) a path between containers / host ('name:/path')."""
    return _run_command(
        "proot_distro.commands.copy",
        "command_copy",
        _ns_copy(source, destination, move=move),
    )


def sync_path(
    source: str, destination: str, checksum: bool = True, delete: bool = False
) -> Outcome:
    """Synchronize directories between containers / host with checksum and pruning."""
    return _run_command(
        "proot_distro.commands.sync",
        "command_sync",
        _ns_sync(source, destination, checksum=checksum, delete=delete),
    )


def clear_cache(orphan: bool = False, build_cache: bool = False) -> Outcome:
    """Clear download cache or sweep orphan layer blobs."""
    return _run_command(
        "proot_distro.commands.clear_cache",
        "command_clear_cache",
        _ns_clear_cache(orphan=orphan, build_cache=build_cache),
    )


def run_command(container: str, run_args: list[str], work_dir: str | None = None) -> Outcome:
    """Run a non-interactive command inside container via Entrypoint/Cmd."""
    return _run_command(
        "proot_distro.commands.run",
        "command_run",
        _ns_run(container, run_args, work_dir),
    )


def inspect_container(name: str) -> dict:
    """Inspect installed container: image origin, OCI config, guest /etc/os-release."""
    bootstrap()
    from proot_distro import guestfile, paths

    rootfs = paths.container_rootfs(name)
    origin_image, origin_arch = "", ""
    try:
        origin_image, origin_arch = paths.container_image_origin(name)
    except Exception:
        pass

    config = {}
    try:
        config = paths.container_image_config(name) or {}
    except Exception:
        pass

    os_release = {}
    try:
        raw = guestfile.read_guest_file(rootfs, "etc/os-release") or guestfile.read_guest_file(
            rootfs, "usr/lib/os-release"
        )
        if raw:
            for line in raw.splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os_release[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass

    return {
        "name": name,
        "image": origin_image,
        "arch": origin_arch,
        "os_release": os_release,
        "config": config,
    }


def kill_session(target: str, all_sessions: bool = False) -> Outcome:
    """Stop a running session (SIGTERM, then SIGKILL escalation upstream)."""
    return _run_command(
        "proot_distro.commands.kill",
        "command_kill",
        _ns_kill(target, all_sessions),
    )


def active_sessions() -> list[dict]:
    """Live sessions as upstream sees them (read-only; we never register)."""
    bootstrap()
    try:
        from proot_distro import session

        return [
            {
                "pid": record.get("pid"),
                "container": record.get("container"),
                "kind": record.get("kind"),
                "user": record.get("user"),
                "command": record.get("command"),
                "start_time": record.get("start_time"),
            }
            for record in session.active_sessions()
        ]
    except Exception as exc:
        logger.warning("active_sessions failed: %r", exc)
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


PULL_LIMIT_COPY = (
    "Docker Hub pull limit reached. This is a Docker Hub rate limit, not an app "
    "error — wait a few hours and retry, or add an optional Docker Hub token in "
    "Settings to raise your limit."
)

_LIMIT_MARKERS = (
    "toomanyrequests",
    "rate limit",
    "too many requests",
    "429",
    "pull rate",
)


def is_pull_limit(outcome: Outcome) -> bool:
    """True when upstream's failure is Docker Hub's pull limit."""
    haystack = (outcome.detail + "\n" + outcome.output).lower()
    return any(marker in haystack for marker in _LIMIT_MARKERS)
