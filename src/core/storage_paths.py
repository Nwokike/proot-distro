"""Where proot-distro keeps its state inside this app."""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_NAME = "ng.kiri.prootdistro"


def support_root() -> Path:
    """The support dir (sync). FLET_APP_STORAGE_* are set by the client at boot."""
    env = os.environ.get("FLET_APP_STORAGE_DATA") or os.environ.get("FLET_APP_STORAGE_TEMP")
    if env:
        return Path(env)
    # Desktop dev runs set neither var before the client boots; fall back to a
    # workspace-local dir so the service is still testable on a laptop.
    return Path.cwd() / ".proot-local" / "data"


def xdg_data_home() -> Path:
    """proot-distro's RUNTIME_DIR root (containers/, locks/, sessions/)."""
    return support_root() / ".local" / "share"


def xdg_cache_home() -> Path:
    """proot-distro's BASE_CACHE_DIR root (oci_layers/, oci_manifests/)."""
    return support_root() / ".local" / "cache"


def containers_dir() -> Path:
    """Where upstream stores `containers/<name>/` for our XDG root."""
    return xdg_data_home() / "proot-distro" / "containers"


def env_contract() -> dict[str, str]:
    """The env proot-distro must see BEFORE its first import.

    Mirrors upstream `constants.py:47-99` (import-time reads) exactly:
    TERMUX_APP__PACKAGE_NAME decouples us from the com.termux defaults,
    XDG_* relocate the state away from Termux prefixes, PD_PROOT_BIN/
    PROOT_LOADER point at the payload the M2 wheel staged. Callers extend
    this with the payload paths from `core.proot_probe`.
    """
    return {
        "TERMUX_APP__PACKAGE_NAME": PACKAGE_NAME,
        "TERMUX__PREFIX": "/data/data/" + PACKAGE_NAME + "/files/usr",
        "TERMUX__HOME": "/data/data/" + PACKAGE_NAME + "/files/home",
        "XDG_DATA_HOME": str(xdg_data_home()),
        "XDG_CACHE_HOME": str(xdg_cache_home()),
        "PROOT_TMP_DIR": str(support_root() / "tmp"),
        "PD_FORCE_NO_COLORS": "1",
    }
