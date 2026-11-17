"""Desk service — the Option-D display wrap: runtime, stream server, guest
script, session manager.

Xvnc (X server + VNC in ONE process) and PulseAudio run IN THE APP from the
APK's native-library dir (the flet-xvnc / flet-pulseaudio payload wheels —
Termux repackages, no compilation). The guest only runs the session and
connects over shared loopback; nothing X-related is installed for single apps.
The stream server (`stream_server.py`) serves the vendored noVNC viewer and
proxies its WebSocket straight to Xvnc's RFB port, so the framebuffer never
touches Python. Pure service layer: controllers drive it, the UI renders it.
This package never imports proot_distro (sole-importer rule: proot_service
only).
"""

from .manager import DeskManager, DeskSession, DeskStatus, session_key, shared_manager
from .script import TUNNEL_URL_RE, build_guest_script, is_valid_geometry

__all__ = [
    "TUNNEL_URL_RE",
    "DeskManager",
    "DeskSession",
    "DeskStatus",
    "build_guest_script",
    "is_valid_geometry",
    "session_key",
    "shared_manager",
]
