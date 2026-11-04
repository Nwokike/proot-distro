"""Desk service — the native display wrap: provision, guest script, session manager.

Wraps `termux-desk` (amirghm/termux-desk, pinned 0.2.0 @ 446fadf) one-to-one:
its TermuxDeskServer runs INSIDE the guest container, captures the guest's
X11 display, and serves its own browser client — which the app renders in a
flet-webview WebView. Pure service layer: controllers drive it, the UI
renders it. This package never imports proot_distro (sole-importer rule:
proot_service only).
"""

from .environments import BY_KEY, DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
from .manager import DeskManager, DeskSession, DeskStatus
from .provision import (
    install,
    install_script,
    package_manager_for,
    unsupported_reason,
    vendor_termux_desk,
)
from .script import build_guest_script

__all__ = [
    "BY_KEY",
    "DEFAULT_DESKTOP",
    "DESKTOP_ENVIRONMENTS",
    "DeskManager",
    "DeskSession",
    "DeskStatus",
    "build_guest_script",
    "install",
    "install_script",
    "package_manager_for",
    "unsupported_reason",
    "vendor_termux_desk",
]
