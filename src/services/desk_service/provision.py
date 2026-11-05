"""Per-distro desktop provisioning — install Xvfb (+ xauth) + a desktop +
clipboard (+ ssh for the tunnel) into the guest. The display SERVER is not
installed here: it runs in the app, bundled with its deps.

APT reliability block copied from ServalDesk (Acquire::Retries, lock timeout,
dpkg --configure -a first) — it is what makes installs survive flaky mobile
networks and stale dpkg state.
"""

from __future__ import annotations

import asyncio
import logging
import shlex

from services import session_service

logger = logging.getLogger(__name__)

# distro_id (or distro_like) -> package manager binary. Probed from
# /etc/os-release by proot_service.guest_capabilities.
_PM_BY_ID = {
    "alpine": "apk",
    "debian": "apt-get",
    "ubuntu": "apt-get",
    "linuxmint": "apt-get",
    "pop": "apt-get",
    "fedora": "dnf",
    "rhel": "dnf",
    "centos": "dnf",
    "rocky": "dnf",
    "alma": "dnf",
    "arch": "pacman",
    "manjaro": "pacman",
    "endeavouros": "pacman",
    "opensuse": "zypper",
    "sles": "zypper",
}

# Base stack: X server (+ xauth for the app-global cookie), clipboard, dbus
# for the session, and openssh for the upstream localhost.run tunnel
# (`ssh -R … nokey@localhost.run`). NO guest python — the display server is
# bundled in the app.
_BASE_PACKAGES = {
    "apk": [
        "xvfb",
        "xauth",
        "xclip",
        "dbus",
        "dbus-x11",
        "openssh-client",
    ],
    "apt-get": [
        "xvfb",
        "xauth",
        "xclip",
        "dbus-x11",
        "openssh-client",
    ],
    "dnf": [
        "xorg-x11-server-Xvfb",
        "xauth",
        "xclip",
        "dbus-x11",
        "openssh-clients",
    ],
    "pacman": [
        "xorg-server-xvfb",
        "xorg-xauth",
        "xclip",
        "dbus",
        "openssh",
    ],
    "zypper": [
        "xorg-x11-server-Xvfb",
        "xauth",
        "xclip",
        "dbus-1-x11",
        "openssh",
    ],
}

# Per-desktop environment packages, per package manager.
_DESKTOP_PACKAGES = {
    "apk": {
        "xfce": ["xfce4", "xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop", "xfce4-settings"],
        "lxqt": ["lxqt-desktop"],
        "mate": ["mate-desktop-environment"],
        "icewm": ["icewm"],
        "openbox": ["openbox"],
    },
    "apt-get": {
        "xfce": ["xfce4", "xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop4", "xfce4-settings"],
        "lxqt": ["lxqt"],
        "mate": ["mate-desktop-environment"],
        "icewm": ["icewm"],
        "openbox": ["openbox"],
    },
    "dnf": {
        "xfce": ["xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop"],
        "lxqt": ["lxqt-desktop"],
        "mate": ["mate-session-manager"],
        "icewm": ["icewm"],
        "openbox": ["openbox"],
    },
    "pacman": {
        "xfce": ["xfce4"],
        "lxqt": ["lxqt"],
        "mate": ["mate"],
        "icewm": ["icewm"],
        "openbox": ["openbox"],
    },
    "zypper": {
        "xfce": ["xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop"],
        "lxqt": ["lxqt-desktop"],
        "mate": ["mate-desktop-environment"],
        "icewm": ["icewm"],
        "openbox": ["openbox"],
    },
}

_UPDATE_COMMANDS = {
    "apk": "apk update",
    "apt-get": "apt-get update",
    "dnf": "dnf makecache --refresh=never 2>/dev/null || true",
    "pacman": "pacman -Sy --noconfirm",
    "zypper": "zypper --non-interactive refresh",
}

_INSTALL_COMMANDS = {
    "apk": "apk add --no-cache {packages}",
    "apt-get": "DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends {packages}",
    "dnf": "dnf install -y {packages}",
    "pacman": "pacman -S --noconfirm --needed {packages}",
    "zypper": "zypper --non-interactive install {packages}",
}

# ServalDesk's apt reliability defaults: retries, lock timeout, repaired dpkg.
_APT_RELIABILITY = """
# Reliability defaults (ServalDesk): retries, lock timeout, repaired dpkg.
printf '%s\\n' 'APT::Sandbox::User "root";' 'Acquire::Retries "3";' \\
  'DPkg::Lock::Timeout "60";' > /etc/apt/apt.conf.d/99-proot-x11.conf
dpkg --configure -a >/dev/null 2>&1 || true
"""


def package_manager_for(caps: dict) -> str | None:
    """The container's package manager from its probed os-release, or None."""
    os_info = caps.get("os") or {}
    for key in (os_info.get("distro_id"), *(os_info.get("distro_like") or "").split()):
        pm = _PM_BY_ID.get((key or "").strip().lower())
        if pm:
            return pm
    return None


def unsupported_reason(caps: dict) -> str | None:
    """Why this container cannot grow a display, or None when it can."""
    if package_manager_for(caps) is None:
        return (
            "This container has no supported package manager, so Xvfb and the "
            "desktop cannot be installed inside it. Use a Debian, Ubuntu, "
            "Alpine, Fedora or Arch image instead."
        )
    return None


def install_script(caps: dict, desktop_env: str = "xfce") -> str:
    """The `/bin/sh -lc` payload that turns a bare container into a
    display-ready one (Xvfb + desktop + clipboard + guest python modules)."""
    pm = package_manager_for(caps)
    if pm is None:
        raise ValueError(unsupported_reason(caps))
    packages = [*_BASE_PACKAGES[pm], *_DESKTOP_PACKAGES[pm].get(desktop_env, [])]
    # Dedupe, keep order.
    seen: set[str] = set()
    packages = [p for p in packages if not (p in seen or seen.add(p))]
    quoted = shlex.join(packages)
    update = _UPDATE_COMMANDS[pm]
    install = _INSTALL_COMMANDS[pm].format(packages=quoted)
    reliability = _APT_RELIABILITY if pm == "apt-get" else ""
    return f"""set -e
{update}
{reliability}{install}
echo "desktop ready ({desktop_env})"
"""


async def install(container: str, caps: dict, desktop_env: str = "xfce", on_chunk=None) -> dict:
    """Run the provisioning script in the guest; unbounded by design (an
    install must not time out) — the UI owns progress and cancellation.
    Streams output through `on_chunk`. The capture is sync, so it runs on a
    worker thread to keep the event loop responsive. Nothing is vendored:
    the display server is bundled in the app."""
    script = install_script(caps, desktop_env)
    return await asyncio.to_thread(
        session_service.command_capture,
        container,
        ["/bin/sh", "-lc", script],
        timeout=None,
        on_chunk=on_chunk,
    )
