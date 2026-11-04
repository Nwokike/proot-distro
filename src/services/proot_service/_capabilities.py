"""Per-container desktop capability probe — rootfs filesystem reads only.

Instant by design: no proot spawn, no PTY, works offline. Presence-only —
runtime facts (the desktop session's health) are gathered at start time, not
here.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ._core import _imp

logger = logging.getLogger(__name__)

# Desktop environments: key -> the session starter inside the guest.
_DESKTOP_STARTERS = {
    "xfce": "usr/bin/startxfce4",
    "lxqt": "usr/bin/startlxqt",
    "mate": "usr/bin/mate-session",
    "icewm": "usr/bin/icewm-session",
    "openbox": "usr/bin/openbox-session",
}

# Stack binaries a desktop session needs around the desktop itself.
_STACK_BINARIES = {
    "dbus": "usr/bin/dbus-run-session",
}


def guest_capabilities(name: str) -> dict:
    """What this container can do for the display feature, probed from the
    rootfs on the host filesystem.

    Returns {"os": {...}, "desk_ready": bool, "dbus": bool, "x_server": bool,
    "python3": bool, "desktops": {name: bool}}. Raises with the real reason
    when the container/rootfs is unavailable — the UI surfaces it, never a
    silently empty probe. `desk_ready` means: python3 + the three guest
    modules TermuxDesk imports (aiohttp, PIL, Xlib) are importable, i.e. the
    vendored termux_desk package can run.
    """
    paths = _imp("proot_distro.paths")
    guestfile = _imp("proot_distro.guestfile")
    rootfs = Path(paths.container_rootfs(name))
    if not rootfs.is_dir():
        raise RuntimeError(f"container '{name}' has no rootfs at {rootfs}")

    os_release: dict[str, str] = {}
    try:
        raw = guestfile.read_guest_file(rootfs, "etc/os-release") or guestfile.read_guest_file(
            rootfs, "usr/lib/os-release"
        )
        if raw:
            for line in raw.splitlines():
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    os_release[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as exc:
        logger.debug("os-release unreadable for %s: %r", name, exc)

    def has(rel: str) -> bool:
        try:
            return (rootfs / rel).exists()
        except OSError as exc:
            logger.debug("capability check skipped %s/%s: %r", name, rel, exc)
            return False

    def guest_python_version() -> str:
        """The guest python3 X.Y version (for the dist-packages path), or ''."""
        for bindir in ("usr/bin", "usr/local/bin"):
            try:
                candidates = sorted((rootfs / bindir).glob("python3.*"))
            except OSError:
                continue
            for candidate in candidates:
                stem = candidate.name
                if stem.count(".") == 1 and stem[7:].isdigit():
                    return stem[7:]
        return ""

    py_ver = guest_python_version()
    dist_packages = rootfs / f"usr/lib/python{py_ver}" if py_ver else rootfs / "usr/lib/python3"

    def guest_module(name: str) -> bool:
        try:
            return (dist_packages / name).is_dir() or (dist_packages / f"{name}.py").is_file()
        except OSError:
            return False

    desk_ready = (
        has("usr/bin/python3")
        and guest_module("aiohttp")
        and guest_module("PIL")
        and guest_module("Xlib")
    )

    return {
        "os": {
            "distro_id": os_release.get("ID", ""),
            "distro_like": os_release.get("ID_LIKE", ""),
            "version_id": os_release.get("VERSION_ID", ""),
            "pretty_name": os_release.get("PRETTY_NAME", ""),
        },
        "python3": has("usr/bin/python3"),
        "python_ver": py_ver,
        "guest_deps": {
            "aiohttp": guest_module("aiohttp"),
            "PIL": guest_module("PIL"),
            "Xlib": guest_module("Xlib"),
        },
        "desk_ready": desk_ready,
        "dbus": has(_STACK_BINARIES["dbus"]),
        "x_server": has("usr/bin/Xvfb") or has("usr/bin/Xorg"),
        "desktops": {key: has(starter) for key, starter in _DESKTOP_STARTERS.items()},
    }
