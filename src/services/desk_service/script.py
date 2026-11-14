"""Guest script builder — what runs inside the container for one display session.

The DISPLAY SERVER RUNS IN THE APP (Xvnc + PulseAudio from the APK's
native-library dir) — the guest only runs the session and connects to it over
the shared loopback, needing NOTHING installed for single apps:

- `DISPLAY=127.0.0.1:N` — Xvnc's X port (proot shares the host network
  namespace, so guest loopback IS host loopback). No unix socket: Xvnc runs
  with -nolisten unix (there is no /tmp/.X11-unix on Android).
- `XAUTHORITY=/tmp/x11/xauth-N` — the auth file the app wrote into the rootfs
  (Python-written, no xauth binary needed in the guest).
- `PULSE_SERVER=127.0.0.1:4713` — the app-side PulseAudio daemon (guest apps
  that link libpulse play through the phone; no guest audio packages).

With the tunnel enabled, the EXACT upstream `LocalhostRunTunnel` command line
(`ssh -R 80:localhost:PORT nokey@localhost.run`, tunnel.py) runs in the guest —
Android hosts have no ssh binary — and its output lands in
`/tmp/x11/tunnel-{N}.log`, where the manager applies upstream's same URL regex.

No python, no pip, no vendoring in the guest. Every UI-supplied value is
validated or shlex-quoted — the script runs as guest root inside proot, still
treat it as untrusted input.
"""

from __future__ import annotations

import re
import shlex

from .display_env import guest_display_env
from .environments import BY_KEY

# Strict geometry allow-list format: the value is validated everywhere the
# display size is chosen (Xvnc's -geometry app-side). The script itself no
# longer starts any X server — it validates to keep one source of truth.
_GEOMETRY_RE = re.compile(r"^\d{2,5}x\d{2,5}$")
# Upstream tunnel.py's own URL pattern (verbatim) — the manager applies it to
# the guest tunnel log.
TUNNEL_URL_RE = re.compile(r"(https://[^\s]+\.lhr\.life[^\s]*)")


def is_valid_geometry(geometry: str) -> bool:
    """True when `geometry` is a safe WxH display value."""
    return bool(_GEOMETRY_RE.match(geometry))


def guest_tunnel_log(display: int) -> str:

    return f"/tmp/x11/tunnel-{display}.log"  # noqa: S108 - guest rootfs path


def guest_script_name(display: int) -> str:
    return f"run-display-{display}.sh"


def build_guest_script(
    *,
    display: int = 0,
    port: int,
    desktop_env: str = "xfce",
    geometry: str = "1280x720",
    xauth_cookie: str = "",
    tunnel: bool = False,
    app_command: str | None = None,
) -> str:
    """The `/bin/sh` payload for one display session on DISPLAY=:{display}.

    The whole guest tree is one proot process group (kill-on-exit), so SIGTERM
    tears down the session and any ssh tunnel together; the X server and the
    stream server are app-side and torn down by the manager. `app_command`
    switches to single-app mode: the DE launch is replaced by `sh -c
    <app_command>`. `port` is only used by the tunnel forward (the host server
    binds it itself). `geometry`/`xauth_cookie` are validated for the surface
    that consumes them app-side.
    """
    if not isinstance(display, int) or not 0 <= display <= 99:
        raise ValueError(f"display must be an int 0-99, got {display!r}")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if not _GEOMETRY_RE.match(geometry):
        raise ValueError(f"geometry must be WxH digits, got {geometry!r}")
    if xauth_cookie and not re.match(r"^[0-9a-f]{32}$", xauth_cookie):
        raise ValueError("xauth_cookie must be 32 hex chars")
    app_mode = app_command is not None and app_command.strip() != ""
    if app_mode:
        session_cmd = f"sh -c {shlex.quote(app_command.strip())}"
    else:
        de = BY_KEY.get(desktop_env)
        if de is None:
            raise ValueError(f"unknown desktop environment: {desktop_env!r}")
        session_cmd = f"dbus-run-session -- {shlex.quote(de.starter)}"

    tunnel_block = ""
    if tunnel:
        # Upstream LocalhostRunTunnel's exact command line (tunnel.py), run in
        # the guest; output goes to the log the manager parses with
        # TUNNEL_URL_RE — the same pattern as upstream's parser.
        tunnel_block = (
            f"( ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30"
            f" -R 80:localhost:{int(port)} nokey@localhost.run"
            f" > {guest_tunnel_log(display)} 2>&1 ) &\n"
        )

    guest_env = guest_display_env(display)
    return f"""set -u
export DISPLAY={guest_env["DISPLAY"]}
export XAUTHORITY="{guest_env["XAUTHORITY"]}"
export PULSE_SERVER={guest_env["PULSE_SERVER"]}
export XDG_SESSION_TYPE=x11
export XDG_RUNTIME_DIR=/tmp/runtime-root
export NO_AT_BRIDGE=1
export GTK_A11Y=none
export LC_ALL=C.UTF-8
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

[ -f "$XAUTHORITY" ] || echo "warning: the display auth file is missing"

{session_cmd} &
SESSION_PID=$!

{tunnel_block}# The session owns this script: when the app or the desktop exits, the
# guest tree exits and the manager marks the display ERROR.
wait "$SESSION_PID" 2>/dev/null
exit $?
"""
