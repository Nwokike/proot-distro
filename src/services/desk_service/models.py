"""DeskManager — N X11 display sessions per container (keyed `container:display`).

ARCHITECTURE (the native wrap, Option D): Xvnc (X server + VNC server in ONE
process) and PulseAudio run INSIDE THE APP from the APK's native-library dir —
the same execution pattern as proot. The guest container only runs the session
(desktop or single app) and connects to the display over loopback TCP; nothing
X-related is installed in the guest. The framebuffer never touches Python:
Xvnc pushes RFB on damage and `stream_server` proxies its WebSocket to the
noVNC viewer. Input and clipboard ride the VNC connection itself.

Lifecycle: IDLE → STARTING (spawn Xvnc + the guest tree, wait for the X TCP
port, start the stream server) → RUNNING → STOPPING → IDLE, or ERROR with a
bounded log tail and an explicit Retry. Each side is its own process group
(`start_new_session`), so SIGTERM tears down the session, the X server and any
ssh tunnel together; either side dying marks the session ERROR.

The manager is a process-wide singleton (like SessionManager): the FGS keeps
the process alive across activity destroy/recreate, so a reopened app
re-adopts the still-running display sessions instead of losing them.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import socket
import subprocess
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from core import storage_paths

from . import xvnc_runtime
from .environments import DEFAULT_DESKTOP
from .script import TUNNEL_URL_RE, guest_script_name, guest_tunnel_log

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 300
MAX_LOG_BYTES = 2 * 1024 * 1024
XVNC_READY_TIMEOUT = 60.0  # Xvnc itself is quick; the DE loads in parallel
TUNNEL_RETRIES = 60  # polled on a daemon thread AFTER ready — never blocks start()
MAX_DISPLAY_NUMBER = 99
XVNC_RFB_BASE = xvnc_runtime.RFB_PORT_BASE  # Xvnc: RFB on 5900+N, X on 6000+N
# noVNC knobs (0-9) — the session surface maps the launcher's quality preset
# onto qualityLevel and exposes compression directly.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous glyphs


class DeskStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DeskSession:
    container: str
    key: str = ""  # "{container}:{display}" — the manager's dict key
    mode: str = "desktop"  # desktop | app | display (bare X server)
    app_command: str = ""  # set in app mode
    desktop_env: str = DEFAULT_DESKTOP
    display: int = 0
    port: int = 0
    url: str = ""
    code: str = ""
    fps: float = 12.0
    quality: int = 70
    geometry: str = "1280x720"
    # Real Xvnc options (all threaded to the argv — see xvnc_command).
    depth: str = "24"
    frame_rate: int = 30
    shared_policy: str = "always"  # always | never ("auto" == always for our viewer)
    resize_mode: str = "remote"  # remote | scale | off (noVNC's own `resize` setting)
    clipboard: bool = True
    localhost_only: bool = False  # opt-in: bind the raw RFB port to loopback
    # Remaining real Xvnc 1.16.2 parameters (all threaded to the argv).
    compare_fb: int = 2  # 2 compare framebuffer, 1 region, 0 always send
    dpi: int = 0  # 0 = Xvnc default
    idle_timeout: int = 0  # seconds; drops an idle viewer, keeps the session
    max_connection_time: int = 0  # seconds; hard cap per viewer connection
    view_only: bool = False  # refuse key/pointer events server-side
    max_cut_text: int = 0  # bytes; 0 = Xvnc default (256 KiB)
    disconnect_clients: bool = False  # new viewer kicks the others
    disconnect_timeout: int = 0  # seconds after the last viewer; 0 = never
    desktop_name: str = ""  # "" → "<container>:<display>"
    # PulseAudio module options (one app-wide daemon; a later display with a
    # different audio shape restarts it).
    mic: bool = True
    audio_latency_ms: int = 0  # 0 = AAudio's own buffer-derived latency
    audio_pm: int = 2  # AAudio performance-mode offset (2 = LOW_LATENCY)
    audio_rate: int = 0  # AAudio sink sample rate (0 = device default)
    audio_no_close_hack: bool = False  # AAudio close-path workaround
    mic_rate: int = 0  # sles-source sample rate
    mic_format: str = ""  # sles-source sample format (e.g. s16le)
    mic_channels: int = 0  # sles-source channel count
    resample_method: str = ""  # PulseAudio --resample-method
    # noVNC viewer knobs (client-side, real settings).
    viewer_bell: bool = True
    show_dot: bool = False
    viewer_logging: str = "warn"
    host: str = "127.0.0.1"  # 0.0.0.0 = LAN sharing is on
    tunnel: bool = False  # guest localhost.run forward requested
    tunnel_url: str = ""  # filled asynchronously from the guest tunnel log
    pid: int | None = None
    status: DeskStatus = DeskStatus.IDLE
    error: str = ""
    login_options: dict = field(default_factory=dict)  # advanced proot-distro login opts
    log_tail: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    server: object | None = None  # the in-process stream server (aiohttp + RFB proxy)
    wv: object | None = None  # the WebView control, created once by DesktopView
    _loop: asyncio.AbstractEventLoop | None = None
    _process: subprocess.Popen | None = None  # the guest tree (proot session)
    _xvnc_process: subprocess.Popen | None = None  # the X server (own group)
    _log_file: object | None = None
    _reader: threading.Thread | None = None
    _log_notify_at: float = 0.0  # 10 Hz coalescing of on_log_line


def session_key(container: str, display: int) -> str:
    return f"{container}:{display}"


def _free_port() -> int:
    """Ephemeral loopback port: bind, read the number, close, hand to the server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _local_ip() -> str:
    """The phone's Wi-Fi IP for LAN URLs. A UDP connect() routes no packets —
    it only picks the interface the kernel would route through."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return ""
    finally:
        probe.close()


_COOKIE_LOCK = threading.Lock()
_XAUTH_COOKIE = ""


def xauth_cookie() -> str:
    """The app-global X cookie (32 hex chars): every guest xauth file carries
    the SAME value, so any session's file works as XAUTHORITY for all."""
    global _XAUTH_COOKIE
    with _COOKIE_LOCK:
        if not _XAUTH_COOKIE:
            _XAUTH_COOKIE = secrets.token_hex(16)
        return _XAUTH_COOKIE


def xvnc_rfb_port(display: int) -> int:
    """Xvnc serves the X protocol AND RFB from related ports: X on 6000+N
    (what the guest apps use), RFB on 5900+N (what the stream proxy connects
    to). Both are loopback-only from the guest's point of view."""
    return xvnc_runtime.RFB_PORT_BASE + display


def _quality_level(quality: int) -> int:
    """Map the launcher's 1-95 quality preset onto noVNC's 0-9 qualityLevel."""
    return max(0, min(9, round(int(quality) * 9 / 95)))


def _write_guest_script(container: str, script: str, display: int) -> str:
    """Write the guest script into the container rootfs; return the
    guest-ABSOLUTE path (the guest cwd is /root, so a relative path would
    resolve into the wrong place — on-device lesson)."""
    rootfs = storage_paths.containers_dir() / container / "rootfs"
    name = guest_script_name(display)
    target = rootfs / "tmp" / "x11" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8")
    return f"/tmp/x11/{name}"  # noqa: S108 - guest path in the rootfs


def _read_tunnel_url(container: str, display: int) -> str:
    """The public URL from the guest ssh forward's log."""
    rel = guest_tunnel_log(display).lstrip("/")
    path = storage_paths.containers_dir() / container / "rootfs" / rel
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    match = TUNNEL_URL_RE.search(text)
    return match.group(1) if match else ""


def _tcp_open(port: int) -> bool:
    """True when something accepts TCP connections on 127.0.0.1:port — the
    Xvnc readiness signal (the stream server's HTTP check follows this)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


# ── access code ──────────────────────────────────────────────────────────────
# The 6-char code gates the stream server's WebSocket (and the page's pre-check).
# Generated per session here — the old server generated its own; the alphabet
# drops the ambiguous glyphs (0/O, 1/I/L).


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
