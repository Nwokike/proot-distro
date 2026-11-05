"""Desk service — the native display wrap: provision, guest script, session manager.

Wraps `termux-desk` (amirghm/termux-desk, pinned 0.2.0 @ 446fadf) one-to-one:
its TermuxDeskServer runs IN THE APP (bundled deps — aiohttp/Pillow/python-xlib
come transitively with the termux-desk dependency), captures the container's
X11 display over loopback TCP, and serves its own browser client — which the
app renders in a flet-webview WebView. The guest container only provides
Xvfb + the desktop. Pure service layer: controllers drive it, the UI renders
it. This package never imports proot_distro (sole-importer rule:
proot_service only).
"""

from .environments import BY_KEY, DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
from .manager import DeskManager, DeskSession, DeskStatus, session_key, shared_manager
from .provision import install, install_script, package_manager_for, unsupported_reason
from .script import TUNNEL_URL_RE, build_guest_script, is_valid_geometry

__all__ = [
    "BY_KEY",
    "DEFAULT_DESKTOP",
    "DESKTOP_ENVIRONMENTS",
    "TUNNEL_URL_RE",
    "DeskManager",
    "DeskSession",
    "DeskStatus",
    "build_guest_script",
    "install",
    "install_script",
    "is_valid_geometry",
    "package_manager_for",
    "session_key",
    "shared_manager",
    "unsupported_reason",
]
