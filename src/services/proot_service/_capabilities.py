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

# Desktop environments: key -> candidate session starters inside the guest
# (per-distro alternates — e.g. lxqt ships startlxqt on some distros and
# lxqt-session on others; the probe accepts any, the script uses the first).
# THE single registry: desk_service.environments consumes it.
DESKTOP_STARTERS: dict[str, tuple[str, ...]] = {
    "xfce": ("usr/bin/startxfce4",),
    "lxqt": ("usr/bin/startlxqt", "usr/bin/lxqt-session"),
    "mate": ("usr/bin/mate-session",),
    "icewm": ("usr/bin/icewm-session", "usr/bin/icewm"),
    "openbox": ("usr/bin/openbox-session", "usr/bin/openbox"),
}

# Stack binaries a desktop session needs around the desktop itself.
_STACK_BINARIES = {
    "dbus": "usr/bin/dbus-run-session",
}


def guest_capabilities(name: str) -> dict:
    """What this container can do for the display feature, probed from the
    rootfs on the host filesystem.

    Returns {"os": {...}, "desk_ready": bool, "dbus": bool, "x_server": bool,
    "desktops": {name: bool}}. Raises with the real reason when the
    container/rootfs is unavailable — the UI surfaces it, never a silently
    empty probe. `desk_ready` is ALWAYS true: Xvnc + PulseAudio run in the app
    (native payloads), so a single-app display needs nothing in the guest —
    only a full desktop session depends on the probed facts below.
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
            logger.debug("capability check skipped %s/%s: %r", name, exc)
            return False

    x_server = has("usr/bin/Xvfb") or has("usr/bin/Xorg")
    dbus = has(_STACK_BINARIES["dbus"])

    return {
        "os": {
            "distro_id": os_release.get("ID", ""),
            "distro_like": os_release.get("ID_LIKE", ""),
            "version_id": os_release.get("VERSION_ID", ""),
            "pretty_name": os_release.get("PRETTY_NAME", ""),
        },
        "desk_ready": True,
        "dbus": dbus,
        "x_server": x_server,
        "desktops": {
            key: any(has(starter) for starter in starters)
            for key, starters in DESKTOP_STARTERS.items()
        },
    }
