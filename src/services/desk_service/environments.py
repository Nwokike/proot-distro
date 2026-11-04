"""Desktop environment registry — names, descriptions, RAM notes, starters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesktopEnv:
    key: str
    name: str
    description: str
    ram_note: str
    starter: str  # session starter inside the guest
    best: bool = False  # the recommended default (ServalDesk's BEST badge)


# ServalDesk's DE cards: XFCE best all-rounder, LXQt fastest, MATE classic,
# IceWM/Openbox minimal. The starter names follow ServalDesk's session mapping.
DESKTOP_ENVIRONMENTS: tuple[DesktopEnv, ...] = (
    DesktopEnv(
        key="xfce",
        name="XFCE",
        description="Fast, customizable, low resource usage. The best all-rounder.",
        ram_note="~300 MB RAM",
        starter="startxfce4",
        best=True,
    ),
    DesktopEnv(
        key="lxqt",
        name="LXQt",
        description="Ultra-lightweight Qt-based desktop. Fastest option.",
        ram_note="~200 MB RAM",
        starter="lxqt-session",
    ),
    DesktopEnv(
        key="mate",
        name="MATE",
        description="Classic GNOME 2 fork. Familiar and comfortable.",
        ram_note="~400 MB RAM",
        starter="mate-session",
    ),
    DesktopEnv(
        key="icewm",
        name="IceWM",
        description="Minimal window manager. Extremely light and snappy.",
        ram_note="~150 MB RAM",
        starter="icewm-session",
    ),
    DesktopEnv(
        key="openbox",
        name="Openbox",
        description="Bare-bones WM with a root menu. For maximum headroom.",
        ram_note="~120 MB RAM",
        starter="openbox-session",
    ),
)

DEFAULT_DESKTOP = "xfce"

BY_KEY = {de.key: de for de in DESKTOP_ENVIRONMENTS}
