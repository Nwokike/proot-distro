"""In-app Xvnc + PulseAudio runtime — public facade.

The payload paths, staging, command builders and the spawn helper live in the
sibling modules; this module re-exports them so existing imports keep working.
"""

from __future__ import annotations

import subprocess  # noqa: F401 - tests patch the module object

from core import storage_paths  # noqa: F401

from . import xvnc_paths  # noqa: F401 - tests patch constants there
from .pulse import (
    probe_pulseaudio,
    pulseaudio_command,
    request_mic_permission,
    write_pulse_config,
)
from .xvnc_command import xvnc_command
from .xvnc_paths import (
    _FAMILY_INTERNET,
    _FAMILY_LOCAL,
    _FAMILY_WILD,
    _SYSTEM_SHELL,
    PULSE_TCP_PORT,
    RFB_PORT_BASE,
    app_root,
    ensure_lock_dir,
    ensure_prefix_bin,
    guest_cookie_path,
    module_path,
    native_dir,
    pulseaudio_binary,
    write_xauth_file,
    xauth_bytes,
    xvnc_binary,
)
from .xvnc_payload import (
    ensure_font_dir,
    ensure_pa_libs,
    ensure_ttf_dir,
    ensure_xkb_dir,
    guest_font_dirs,
)
from .xvnc_spawn import spawn

__all__ = [
    "PULSE_TCP_PORT",
    "RFB_PORT_BASE",
    "_FAMILY_INTERNET",
    "_FAMILY_LOCAL",
    "_FAMILY_WILD",
    "_SYSTEM_SHELL",
    "app_root",
    "ensure_font_dir",
    "ensure_lock_dir",
    "ensure_pa_libs",
    "ensure_prefix_bin",
    "ensure_ttf_dir",
    "ensure_xkb_dir",
    "guest_cookie_path",
    "guest_font_dirs",
    "module_path",
    "native_dir",
    "probe_pulseaudio",
    "pulseaudio_binary",
    "pulseaudio_command",
    "request_mic_permission",
    "spawn",
    "write_pulse_config",
    "write_xauth_file",
    "xauth_bytes",
    "xvnc_binary",
    "xvnc_command",
]
