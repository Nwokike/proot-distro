"""Where proot-distro keeps its state inside this app."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

PACKAGE_NAME = "ng.kiri.prootdistro"


def data_root() -> Path:
    env = os.environ.get("FLET_APP_STORAGE_DATA")
    p = Path(env) if env else (Path.cwd() / ".proot-local" / "data")
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_root() -> Path:
    env = os.environ.get("FLET_APP_STORAGE_CACHE")
    p = Path(env) if env else (data_root() / "cache")
    p.mkdir(parents=True, exist_ok=True)
    return p


def temp_root() -> Path:
    env = os.environ.get("FLET_APP_STORAGE_TEMP")
    p = Path(env) if env else (data_root() / "tmp")
    p.mkdir(parents=True, exist_ok=True)
    return p


def proot_tmp_dir() -> Path:
    p = temp_root() / "proot_tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def support_root() -> Path:
    return data_root()


def xdg_data_home() -> Path:
    """proot-distro's RUNTIME_DIR root (containers/, locks/, sessions/)."""
    p = data_root() / ".local" / "share"
    p.mkdir(parents=True, exist_ok=True)
    return p


def xdg_cache_home() -> Path:
    """proot-distro's BASE_CACHE_DIR root (oci_layers/, oci_manifests/)."""
    p = cache_root() / "proot-distro"
    p.mkdir(parents=True, exist_ok=True)
    return p


def containers_dir() -> Path:
    """Where upstream stores `containers/<name>/` for our XDG root."""
    p = xdg_data_home() / "proot-distro" / "containers"
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
    except Exception:
        pass
    return contract
