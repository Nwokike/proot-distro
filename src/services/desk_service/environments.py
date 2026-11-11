"""Desktop environment registry — names, descriptions, RAM notes.

Session starters come from the ONE registry in
`proot_service._capabilities.DESKTOP_STARTERS` (per-distro alternates) — this
module only carries display metadata. Probing (`guest_capabilities`) and the
guest script both read that table, so the two can never diverge again.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.proot_service import DESKTOP_STARTERS


@dataclass(frozen=True)
class DesktopEnv:
    key: str
    name: str
    description: str
    ram_note: str
    best: bool = False  # the recommended default (ServalDesk's BEST badge)

    @property
    def starter(self) -> str:
        """The primary session starter for this DE (first candidate)."""
        return DESKTOP_STARTERS[self.key][0].rsplit("/", 1)[-1]


# ServalDesk's DE cards: XFCE best all-rounder, LXQt fastest, MATE classic,
# IceWM/Openbox minimal.
DESKTOP_ENVIRONMENTS: tuple[DesktopEnv, ...] = (
    DesktopEnv(
        key="xfce",
        name="XFCE",
        description="Fast, customizable, low resource usage. The best all-rounder.",
        ram_note="~300 MB RAM",
        best=True,
    ),
    DesktopEnv(
        key="lxqt",
        name="LXQt",
        description="Ultra-lightweight Qt-based desktop. Fastest option.",
        ram_note="~200 MB RAM",
    ),
    DesktopEnv(
        key="mate",
        name="MATE",
        description="Classic GNOME 2 fork. Familiar and comfortable.",
        ram_note="~400 MB RAM",
    ),
    DesktopEnv(
        key="icewm",
        name="IceWM",
        description="Minimal window manager. Extremely light and snappy.",
        ram_note="~150 MB RAM",
    ),
    DesktopEnv(
        key="openbox",
        name="Openbox",
        description="Bare-bones WM with a root menu. For maximum headroom.",
        ram_note="~120 MB RAM",
    ),
)

DEFAULT_DESKTOP = "xfce"

BY_KEY = {de.key: de for de in DESKTOP_ENVIRONMENTS}
