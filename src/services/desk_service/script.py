"""Guest script builder — what runs inside the container for one display session.

The script writes the server's auth code to a rootfs file (`/tmp/termux-desk/
auth.json`) so the app can auto-authenticate the WebView without parsing
logs, and — when the tunnel is enabled — starts upstream's LocalhostRunTunnel
in a daemon thread that publishes the `*.lhr.life` URL to
`/tmp/termux-desk/tunnel.json` the same way. Every UI-supplied value is
validated (geometry/host) or shlex-quoted — the script runs as guest root
inside proot, still treat it as untrusted input.
"""

from __future__ import annotations

import re
import shlex

from .environments import BY_KEY

# Strict geometry allow-list format: the value is interpolated into the
# Xvfb command line, so anything but digits-x-digits is rejected outright.
_GEOMETRY_RE = re.compile(r"^\d{2,5}x\d{2,5}$")
_ALLOWED_HOSTS = {"127.0.0.1", "0.0.0.0"}  # noqa: S104 - LAN binding is the feature


def is_valid_geometry(geometry: str) -> bool:
    """True when `geometry` is a safe WxH Xvfb screen value."""
    return bool(_GEOMETRY_RE.match(geometry))


def build_guest_script(
    *,
    display: int = 0,
    port: int,
    desktop_env: str = "xfce",
    fps: float = 12.0,
    quality: int = 70,
    geometry: str = "1280x720",
    host: str = "127.0.0.1",
    tunnel: bool = False,
) -> str:
    """The `/bin/sh` payload for one display session.

    DISPLAY=:0 is fixed everywhere (ServalDesk rule — the guest never
    configures X). Order matters: Xvfb first, then the desktop session on
    that display, then the server (which blocks; the proot process group —
    kill-on-exit — owns its whole tree, so SIGTERM to the group tears down
    Xvfb, the desktop, the server, and any ssh tunnel together). `host` is
    upstream's listen address: 127.0.0.1 for the app's own WebView,
    0.0.0.0 for LAN sharing (other devices connect to the phone's IP with
    the same access code).
    """
    de = BY_KEY.get(desktop_env)
    if de is None:
        raise ValueError(f"unknown desktop environment: {desktop_env!r}")
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    if host not in _ALLOWED_HOSTS:
        raise ValueError(f"host must be one of {sorted(_ALLOWED_HOSTS)}")
    if not _GEOMETRY_RE.match(geometry):
        raise ValueError(f"geometry must be WxH digits, got {geometry!r}")
    starter = shlex.quote(de.starter)

    return f"""set -u
export DISPLAY=:{display}
export XDG_SESSION_TYPE=x11
export XDG_RUNTIME_DIR=/tmp/runtime-root
export NO_AT_BRIDGE=1
export GTK_A11Y=none
export LC_ALL=C.UTF-8
mkdir -p "$XDG_RUNTIME_DIR" /tmp/termux-desk
chmod 700 "$XDG_RUNTIME_DIR"

Xvfb :{display} -screen 0 {geometry}x24 -nolisten tcp &
XVFB_PID=$!
sleep 1

dbus-run-session -- {starter} &
DE_PID=$!

# The server writes its access code where the app can read it (rootfs file);
# with the tunnel enabled a daemon thread publishes the public URL the same
# way. Then the server blocks until the process group is torn down.
python3 - <<'PYEOF'
import json
import threading

from termux_desk import TermuxDeskServer
from termux_desk.tunnel import LocalhostRunTunnel

server = TermuxDeskServer(
    host={host!r},
    port={int(port)},
    display=":{display}",
    fps={float(fps)},
    quality={int(quality)},
)
with open("/tmp/termux-desk/auth.json", "w", encoding="utf-8") as handle:
    json.dump({{"code": server._auth_code, "port": server.port}}, handle)


def _tunnel() -> None:
    # Upstream LocalhostRunTunnel: ssh -R 80 to nokey@localhost.run.
    try:
        url = LocalhostRunTunnel(server.port).start()
    except Exception as exc:  # noqa: BLE001 - the app reads whatever we got
        with open("/tmp/termux-desk/tunnel.json", "w", encoding="utf-8") as handle:
            json.dump({{"error": str(exc)}}, handle)
        return
    with open("/tmp/termux-desk/tunnel.json", "w", encoding="utf-8") as handle:
        json.dump({{"url": url}}, handle)


if {bool(tunnel)}:
    threading.Thread(target=_tunnel, daemon=True).start()

server.run()
PYEOF
SERVER_STATUS=$?
kill "$DE_PID" "$XVFB_PID" 2>/dev/null
exit "$SERVER_STATUS"
"""
