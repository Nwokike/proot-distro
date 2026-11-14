"""The guest-side environment of a running display — ONE source of truth.

The display session script exports exactly these values for the desktop
process, and every NEW shell opened while a display runs inherits them — so a
GUI app launched from any shell reaches the display (device 2026-11-14:
`firefox` → "no DISPLAY environment variable specified"). Keeping the strings
in one place means the script and the shell overlay cannot drift.
"""

from __future__ import annotations

from .xvnc_runtime import PULSE_TCP_PORT


def guest_display_env(display: int, *, pulse: bool = True) -> dict[str, str]:
    """DISPLAY / XAUTHORITY (+ PULSE_SERVER) for guest processes on `display`.

    Xvnc runs `-nolisten unix`, so the display address is loopback TCP (proot
    shares the host network namespace); the xauth file is written by the app
    into the rootfs at `/tmp/x11/xauth-<display>` (guest-absolute path).
    `pulse` reflects whether the app-wide PulseAudio daemon is actually alive —
    pointing apps at a dead socket would fail more confusingly than unset."""
    env = {
        "DISPLAY": f"127.0.0.1:{display}",
        "XAUTHORITY": f"/tmp/x11/xauth-{display}",  # noqa: S108 - guest rootfs path
    }
    if pulse:
        env["PULSE_SERVER"] = f"127.0.0.1:{PULSE_TCP_PORT}"
    return env
