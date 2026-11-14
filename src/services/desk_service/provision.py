"""Per-distro desktop provisioning — install the session bus + the tunnel ssh
client, plus the desktop-only extras and a desktop environment into the guest.
The X server (Xvnc) and PulseAudio run IN THE APP (native payloads) — single-app
displays install NOTHING here; only a desktop session needs packages.

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

# Base stack — deliberately MINIMAL: the session bus (GTK/Qt apps want one)
# and openssh for the upstream localhost.run tunnel. The X server (Xvnc) and
# PulseAudio run IN THE APP — single-app displays install NOTHING here.
#
# The desktop-only extras (icon theme / pixbuf / mime / fonts / rsvg) live in
# the per-DESKTOP-ENVIRONMENT lists below: a minimal container ships none of
# them, and without them GTK cannot load a single image — xfdesktop renders no
# wallpaper and xfce4-panel ABORTS on a libwnck icon assertion ("Bail out!
# default_icon_at_size"), taking xfconfd and xfsettingsd down with it (the
# pitch-black root window, device-proven 2026-11-10). Apps don't need them.
_BASE_PACKAGES = {
    "apk": [
        "dbus",
        "dbus-x11",
        "openssh-client",
    ],
    "apt-get": [
        "dbus-x11",
        "openssh-client",
    ],
    "dnf": [
        # Fedora/RHEL have no dbus-x11; dbus-tools carries dbus-run-session.
        "dbus-daemon",
        "dbus-tools",
        "openssh-clients",
    ],
    "pacman": [
        "dbus",
        "openssh",
    ],
    "zypper": [
        # Tumbleweed carries the daemon + tools in dbus-1-daemon (there is no
        # dbus-1-x11 there; the name exists only in Leap).
        "dbus-1-daemon",
        "openssh",
    ],
}

# Desktop-only extras (per package manager): a full desktop session needs an icon theme, working
# pixbuf loaders, the mime database, fonts and rsvg (GTK cannot load a single
# image without them — xfdesktop draws no wallpaper and xfce4-panel aborts).
# Single-app displays don't, which is why they are NOT in the base stack.
_DESKTOP_EXTRAS = {
    "apk": [
        # core X bitmap fonts — xterm and Xvnc's font path need them
        "font-misc-misc",
        "adwaita-icon-theme",
        "gdk-pixbuf",
        "shared-mime-info",
        "desktop-file-utils",
        "librsvg",
        "font-dejavu",
    ],
    "apt-get": [
        "xfonts-base",
        "adwaita-icon-theme",
        "shared-mime-info",
        "desktop-file-utils",
        "fontconfig",
        "fonts-dejavu-core",
        "librsvg2-common",
    ],
    "dnf": [
        "xorg-x11-fonts-misc",
        "adwaita-icon-theme",
        "shared-mime-info",
        "desktop-file-utils",
        "dejavu-sans-fonts",
        "librsvg2",
    ],
    "pacman": [
        "xorg-fonts-misc",
        "adwaita-icon-theme",
        "shared-mime-info",
        "desktop-file-utils",
        "ttf-dejavu",
        "librsvg",
    ],
    "zypper": [
        "xorg-x11-fonts-core",
        "adwaita-icon-theme",
        "shared-mime-info",
        "desktop-file-utils",
        "dejavu-fonts",
        "librsvg-2-2",
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
        # xfce4-settings is REQUIRED: without it xfce4-session cannot launch
        # xfsettingsd ("No such file or directory" on device) and the session
        # degrades to a bare window manager on a black root.
        "xfce": ["xfce4-session", "xfwm4", "xfce4-panel", "xfdesktop", "xfce4-settings"],
        # Fedora has no lxqt-desktop package; the comps group is lxqt-desktop.
        "lxqt": ["@lxqt-desktop"],
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
        "lxqt": ["patterns-lxqt-lxqt"],
        "mate": ["patterns-mate-mate"],
        "icewm": ["icewm"],
        "openbox": ["openbox"],
    },
}

_UPDATE_COMMANDS = {
    "apk": "apk update",
    "apt-get": "apt-get update",
    "dnf": "dnf makecache --refresh=never 2>/dev/null || true",
    "pacman": "pacman -Sy --noconfirm",
    # Metadata can be pinned stale (zypper keeps a 0-byte cache on HTTP 304 —
    # device 2026-11-14 "repomd.xml Document is empty"); clean first.
    "zypper": "zypper clean -a && zypper --non-interactive refresh",
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
            "This container has no supported package manager, so the desktop "
            "packages cannot be installed inside it. The display server itself "
            "ships with the app; use a Debian, Ubuntu, Alpine, Fedora or Arch "
            "image for a full desktop."
        )
    return None


def install_script(caps: dict, desktop_env: str = "xfce") -> str:
    """The `/bin/sh -lc` payload that turns a bare container into a
    display-ready one (minimal X11 base + desktop extras + the chosen DE)."""
    pm = package_manager_for(caps)
    if pm is None:
        raise ValueError(unsupported_reason(caps))
    packages = [
        *_BASE_PACKAGES[pm],
        *_DESKTOP_EXTRAS[pm],
        *_DESKTOP_PACKAGES[pm].get(desktop_env, []),
    ]
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
