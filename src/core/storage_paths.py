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
            "app-storage locations (run via `flet run` — the packaged app "
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


def env_contract() -> dict[str, str]:
    """The env proot-distro must see BEFORE its first import."""
    contract = {
        "TERMUX_APP__PACKAGE_NAME": PACKAGE_NAME,
        "TERMUX__PREFIX": "/data/data/" + PACKAGE_NAME + "/files/usr",
        "TERMUX__HOME": "/data/data/" + PACKAGE_NAME + "/files/home",
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
            "certifi unavailable — OCI layer pulls will not validate registry certificates: %r",
            exc,
        )
    return contract
