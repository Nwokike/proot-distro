"""Staging of the xkb/fonts/pa-libs payload trees."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from core import storage_paths

from .xvnc_paths import native_dir

logger = logging.getLogger(__name__)


def _xkb_version() -> str:
    try:
        import flet_xvnc  # type: ignore[import-not-found]

        return str(getattr(flet_xvnc, "XVNC_VERSION", ""))
    except Exception:  # desktop/dev runs — the payload wheel is Android-only
        return ""


def _copy_tree(node, target: Path) -> None:
    """Copy an importlib.resources Traversable tree onto disk (works whether the
    package lives in a directory OR inside the Android runtime's ZIP)."""
    for entry in node.iterdir():
        out = target / entry.name
        if entry.is_dir():
            out.mkdir(exist_ok=True)
            _copy_tree(entry, out)
        else:
            out.write_bytes(entry.read_bytes())


def ensure_xkb_dir() -> Path:
    """Copy the wheel's xkb tree to a writable dir (Xvnc may write compiled
    keymaps beside it) and return it for -xkbdir.

    The Android runtime imports pip packages from a stored ZIP (sitepackages.zip),
    so a `__file__`-relative path does NOT exist on disk — the tree is read
    through the importlib.resources Traversable API, which works inside zips.
    """
    runtime = storage_paths.support_root() / "runtime"
    dest = runtime / "xkb"
    version = _xkb_version()
    marker = dest / ".version"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == version:
        return dest
    try:
        from importlib import resources

        root = resources.files("flet_xvnc") / "data" / "xkb"
        if not root.is_dir():
            raise FileNotFoundError("flet_xvnc/data/xkb")
    except Exception as exc:
        raise RuntimeError(
            f"the flet-xvnc payload data is unreadable (the wheel's xkb tree is missing): {exc}"
        ) from exc
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    _copy_tree(root, dest)
    marker.write_text(version, encoding="utf-8")
    logger.info("xkb data staged at %s (%s)", dest, version or "unknown version")
    return dest


# The core X bitmap font directories a container may provide (with fonts.dir).
_GUEST_FONT_LAYOUTS = (
    "usr/share/fonts/misc",
    "usr/share/fonts/X11/misc",
    "usr/share/X11/fonts/misc",
    "usr/share/fonts/TTF",
    "usr/share/fonts/truetype",
    "usr/share/fonts/X11/TTF",
)


def ensure_font_dir() -> Path | None:
    """Stage the wheel's bundled core X fonts (PCF + fonts.dir) for -fp.

    Xvnc's compiled-in font path points at the Termux prefix (absent in the
    app), so every start logged six "Could not init font path element" lines
    and xterm could not load a font (device 2026-11-13). The wheel bundles
    xorg-fonts-misc plus a generated fonts.dir; stage it through the zip-safe
    Traversable API like the xkb tree."""
    runtime = storage_paths.support_root() / "runtime"
    dest = runtime / "fonts"
    version = _xkb_version()
    marker = dest / ".version"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == version:
        return dest
    try:
        from importlib import resources

        root = resources.files("flet_xvnc") / "data" / "fonts" / "misc"
        if not root.is_dir():
            raise FileNotFoundError("flet_xvnc/data/fonts/misc")
    except Exception as exc:
        logger.debug("bundled X fonts unavailable: %s", exc)
        return None
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    _copy_tree(root, dest)
    marker.write_text(version, encoding="utf-8")
    logger.info("X fonts staged at %s (%s)", dest, version or "unknown version")
    return dest


def guest_font_dirs(container: str) -> list[str]:
    """Font directories INSIDE the container that Xvnc can read from the host
    (the rootfs lives on the app's filesystem; read-only is fine)."""
    from core import storage_paths as sp

    rootfs = sp.containers_dir() / container / "rootfs"
    dirs: list[str] = []
    for rel in _GUEST_FONT_LAYOUTS:
        directory = rootfs / rel
        if (directory / "fonts.dir").is_file():
            dirs.append(str(directory))
    return dirs


# ── process commands ─────────────────────────────────────────────────────────


def ensure_pa_libs() -> Path:
    """Stage the PulseAudio closure into its OWN dir and use it as the linker path.

    The native dir also holds Xvnc's libcrypto.so (OpenSSL 3.x); with it on the
    daemon's LD_LIBRARY_PATH, vendor libraries that dlopen system libs expecting
    the old OpenSSL ABI fail (device 2026-11-13: module-sles-source →
    /system/lib64/libsqlite.so → missing OpenSSL_add_all_algorithms). A
    libcrypto-free dir keeps the daemon's namespace clean."""
    import flet_pulseaudio  # type: ignore[import-not-found]

    native = native_dir()
    runtime = storage_paths.support_root() / "runtime"
    dest = runtime / "pa-libs"
    version = str(getattr(flet_pulseaudio, "PA_VERSION", ""))
    marker = dest / ".version"
    if marker.is_file() and marker.read_text(encoding="utf-8").strip() == version:
        return dest
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    for name in getattr(flet_pulseaudio, "LIBS", []):
        src = native / name
        if src.is_file():
            (dest / name).write_bytes(src.read_bytes())
    marker.write_text(version, encoding="utf-8")
    logger.info("pulseaudio libs staged at %s (%s)", dest, version)
    return dest
