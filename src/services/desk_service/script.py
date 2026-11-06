"""Guest script builder — what runs inside the container for one display session.

The DISPLAY SERVER RUNS IN THE APP (host-side, bundled deps) — the guest only
provides the X framebuffer and the session:

- `Xvfb :N` listens on TCP 6000+N so the host-side server connects over
  `127.0.0.1:N` (proot shares the host network namespace — guest loopback IS
  host loopback). An app-global xauth cookie gates the connection; if the
  guest lacks `xauth` the script falls back to no-auth (device-gated).
- The desktop session (or a single app via `sh -c`) runs on that display.
- With the tunnel enabled, the EXACT upstream `LocalhostRunTunnel` command
  line (`ssh -R 80:localhost:PORT nokey@localhost.run`, tunnel.py) runs in
  the guest — Android hosts have no ssh binary — and its output lands in
  `/tmp/termux-desk/tunnel-{N}.log`, where the manager applies upstream's
  same URL regex.

No python, no pip, no vendoring in the guest. Every UI-supplied value is
validated or shlex-quoted — the script runs as guest root inside proot, still
treat it as untrusted input.
"""

from __future__ import annotations

import re
import shlex

from .environments import BY_KEY

# Strict geometry allow-list format: the value is interpolated into the
# Xvfb command line, so anything but digits-x-digits is rejected outright.
_GEOMETRY_RE = re.compile(r"^\d{2,5}x\d{2,5}$")
# Upstream tunnel.py's own URL pattern (verbatim) — the manager applies it to
# the guest tunnel log.
TUNNEL_URL_RE = re.compile(r"(https://[^\s]+\.lhr\.life[^\s]*)")


def is_valid_geometry(geometry: str) -> bool:
    """True when `geometry` is a safe WxH Xvfb screen value."""
    return bool(_GEOMETRY_RE.match(geometry))


def guest_tunnel_log(display: int) -> str:

    return f"/tmp/termux-desk/tunnel-{display}.log"  # noqa: S108 - guest rootfs path


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

    Order matters: xauth + Xvfb (TCP) first, then the session (desktop or
    single app) on that display. The whole tree is one proot process group
    (kill-on-exit), so SIGTERM tears down Xvfb, the session, and any ssh
    tunnel together. `app_command` switches to single-app mode: the DE launch
    is replaced by `sh -c <app_command>` on the same Xvfb. `port` is only
    used by the tunnel forward (the host server binds it itself).
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

    xauth_setup = ""
    if xauth_cookie:
        # GUEST path inside the container rootfs, not host /tmp (S108 is a false positive).
        xauth_file = f"/tmp/termux-desk/xauth-{display}"  # noqa: S108
        # XVFB_AUTH is ALWAYS defined (device lesson: with `set -u`, an unset
        # var in the Xvfb line killed the whole script when the guest lacked
        # xauth — the empty default IS the graceful no-auth fallback).
        xauth_setup = (
            'XVFB_AUTH=""\n'
            "if command -v xauth >/dev/null 2>&1; then\n"
            f'  xauth -f {xauth_file} add "127.0.0.1:{display}" . {xauth_cookie} 2>/dev/null || true\n'
            f'  xauth -f {xauth_file} add "localhost:{display}" . {xauth_cookie} 2>/dev/null || true\n'
            f'  XVFB_AUTH="-auth {xauth_file}"\n'
            "fi"
        )

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

    return f"""set -u
export DISPLAY=:{display}
export XDG_SESSION_TYPE=x11
export XDG_RUNTIME_DIR=/tmp/runtime-root
export NO_AT_BRIDGE=1
export GTK_A11Y=none
export LC_ALL=C.UTF-8
mkdir -p "$XDG_RUNTIME_DIR" /tmp/termux-desk
chmod 700 "$XDG_RUNTIME_DIR"
{xauth_setup}

Xvfb :{display} $XVFB_AUTH -screen 0 {geometry}x24 &
XVFB_PID=$!
sleep 1
kill -0 "$XVFB_PID" 2>/dev/null || {{
  echo "Xvfb failed to start on :{display}"
  exit 1
}}

{session_cmd} &
SESSION_PID=$!

{tunnel_block}# The Xvfb framebuffer owns the session: wait on IT only. If the desktop
# crashes, the display (and the server's connection to it) stays up.
wait "$XVFB_PID" 2>/dev/null
exit $?
"""
