"""Storage — the three Flet app-storage locations, and nothing else.

`flet run` (and a packaged app on a device) expose exactly three writable
roots, `FLET_APP_STORAGE_DATA` / `FLET_APP_STORAGE_CACHE` /
`FLET_APP_STORAGE_TEMP` — see `.flet/README.md`. This module maps
proot-distro onto them. Because upstream computes its paths at import time,
the mapping is exported as the env contract
(`services.proot_service.bootstrap`) *before* proot_distro is imported:

- `XDG_DATA_HOME` = the `data` root. Upstream builds
  `<data>/proot-distro/` (containers/, locks/, sessions/) inside it —
  durable data, per the README.
- `XDG_CACHE_HOME` = the `cache` root. Upstream builds
  `<cache>/proot-distro/` (oci_layers/, oci_manifests/) inside it —
  regenerable, per the README.
- `PROOT_TMP_DIR` and exports staging go to the `temp` root — throwaway
  scratch, per the README.

When a storage env var is unset the app is not running under Flet (a bare
`python src/main.py`, a stray script). Such a run fails loudly rather than
inventing a location: anything stored outside the app-storage contract is
invisible to the packaged app and would be lost.
"""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

PACKAGE_NAME = "ng.kiri.prootdistro"


def _env_path(var: str, what: str) -> Path:
    env = os.environ.get(var)
    if not env:
        raise RuntimeError(
            f"{var} is not set; proot-distro {what} must live in the Flet "
            "app-storage locations (run via `flet run`; the packaged app "
            "sets them automatically)."
        )
    p = Path(env)
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_root() -> Path:
    """Durable application data (`FLET_APP_STORAGE_DATA`)."""
    return _env_path("FLET_APP_STORAGE_DATA", "containers and state")


def cache_root() -> Path:
    """Regenerable OCI/install cache (`FLET_APP_STORAGE_CACHE`)."""
    return _env_path("FLET_APP_STORAGE_CACHE", "the OCI cache")


def temp_root() -> Path:
    """Throwaway scratch space (`FLET_APP_STORAGE_TEMP`)."""
    return _env_path("FLET_APP_STORAGE_TEMP", "temporary files")


def support_root() -> Path:
    """Alias of data_root() — staged runtime libs live in durable data."""
    return data_root()


def xdg_data_home() -> Path:
    """proot-distro's RUNTIME_DIR root — the data root itself."""
    return data_root()


def xdg_cache_home() -> Path:
    """proot-distro's BASE_CACHE_DIR root — the cache root itself."""
    return cache_root()


def containers_dir() -> Path:
    """`containers/<name>/` as upstream composes it under our XDG data root."""
    p = xdg_data_home() / "proot-distro" / "containers"
    p.mkdir(parents=True, exist_ok=True)
    return p


def proot_tmp_dir() -> Path:
    """Temporary directory the proot process itself works in — temp."""
    return temp_root()


def exports_root() -> Path:
    """Staging for archives (backup/restore) before hand-off — temp."""
    p = temp_root() / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def prune_display_logs(keep_per_container: int = 3, keep_days: int = 7) -> int:
    """Bound the durable display logs; returns the count removed.

    Logs live in the data root on purpose (clear-cache must not destroy crash
    evidence), so they need their own reaper: keep the newest generations per
    container and drop anything older than `keep_days`."""
    import time

    folder = data_root() / "display-logs"
    if not folder.is_dir():
        return 0
    cutoff = time.time() - keep_days * 86400
    by_container: dict[str, list] = {}
    removed = 0
    for path in folder.glob("*.log*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
                continue
        except OSError:
            continue
        name = path.name.split(".log", 1)[0]
        by_container.setdefault(name, []).append(path)
    for paths in by_container.values():
        for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[
            keep_per_container:
        ]:
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                continue
    if removed:
        logger.info("display-log prune removed %d old file(s)", removed)
    return removed


def sweep_temp(max_age_hours: int = 24) -> int:
    """Delete stale files under the temp root; returns the count removed.

    The README calls temp throwaway: a failed export or an aborted archive must
    not sit there forever. Called once at startup, never at runtime."""
    import time

    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    root = temp_root()
    for path in root.rglob("*"):
        try:
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        except OSError as exc:
            logger.debug("temp sweep skipped %s: %s", path, exc)
    if removed:
        logger.info("temp sweep removed %d stale file(s)", removed)
    return removed


def app_root() -> Path:
    """The app's private root, RESOLVED.

    Android names the same directory `/data/data/<pkg>` and
    `/data/user/0/<pkg>`; proot canonicalizes the rootfs while link2symlink
    chains may store the other spelling — a hard link dpkg just made then
    becomes unresolvable ("error setting ownership of '…dpkg-new': No such
    file or directory", device 2026-11-14 / oonid/pr#35). Every path we hand
    to proot must use ONE spelling: the resolved one."""
    return data_root().parents[1].resolve()


def env_contract() -> dict[str, str]:
    """The env proot-distro must see BEFORE its first import.

    TERMUX__PREFIX/HOME are derived from the REAL app root (resolved), never
    from a hardcoded `/data/data/<pkg>` — the two Android spellings of the same
    directory must not leak into proot + link2symlink paths."""
    root = app_root()
    contract = {
        "TERMUX_APP__PACKAGE_NAME": PACKAGE_NAME,
        "TERMUX__PREFIX": str(root / "files" / "usr"),
        "TERMUX__HOME": str(root / "files" / "home"),
        "XDG_DATA_HOME": str(xdg_data_home()),
        "XDG_CACHE_HOME": str(xdg_cache_home()),
        "PROOT_TMP_DIR": str(proot_tmp_dir()),
        "PD_FORCE_NO_COLORS": "1",
    }
    try:
        certifi = importlib.import_module("certifi")
        contract["SSL_CERT_FILE"] = certifi.where()
    except Exception as exc:
        logger.warning(
            "certifi unavailable; OCI layer pulls will not validate registry certificates: %r",
            exc,
        )
    # Upstream's --shared-home binds TERMUX__HOME; it must EXIST or the bind
    # silently points nowhere. We create it (the home dir only — deliberately
    # NOT files/usr, whose existence would flip upstream's IS_TERMUX detection
    # and move its runtime paths off the XDG contract).
    try:
        Path(contract["TERMUX__HOME"]).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.debug("could not create the shared home dir: %r", exc)
    return contract
