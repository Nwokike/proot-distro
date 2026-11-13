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
import os
import secrets
import signal
import socket
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from core import storage_paths
from services import session_service

from . import stream_server, xvnc_runtime
from .environments import DEFAULT_DESKTOP
from .script import TUNNEL_URL_RE, build_guest_script, guest_script_name, guest_tunnel_log

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 300
MAX_LOG_BYTES = 2 * 1024 * 1024
XVFB_READY_TIMEOUT = 60.0  # Xvnc itself is quick; the DE loads in parallel
TUNNEL_RETRIES = 60  # polled on a daemon thread AFTER ready — never blocks start()
MAX_DISPLAY_NUMBER = 99
XVFB_TCP_BASE = xvnc_runtime.RFB_PORT_BASE  # the X port IS the RFB port base +N
# noVNC knobs (0-9) — the session surface maps the launcher's quality preset
# onto qualityLevel and exposes compression directly.
DEFAULT_COMPRESSION_LEVEL = 2
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
    mode: str = "desktop"  # "desktop" | "app" (single app on a bare Xvfb)
    app_command: str = ""  # set in app mode
    desktop_env: str = DEFAULT_DESKTOP
    display: int = 0
    port: int = 0
    url: str = ""
    code: str = ""
    fps: float = 12.0
    quality: int = 70
    geometry: str = "1280x720"
    host: str = "127.0.0.1"  # 0.0.0.0 = LAN sharing is on
    tunnel: bool = False  # upstream localhost.run tunnel requested
    tunnel_url: str = ""  # filled asynchronously from the guest tunnel log
    pid: int | None = None
    status: DeskStatus = DeskStatus.IDLE
    error: str = ""
    login_options: dict = field(default_factory=dict)  # advanced proot-distro login opts
    log_tail: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    started_at: float = 0.0
    server: object | None = None  # the in-process stream server (aiohttp + RFB proxy)
    wv: object | None = None  # the WebView control, created once by DesktopView
    _loop: asyncio.AbstractEventLoop | None = None
    _process: subprocess.Popen | None = None  # the guest tree (proot session)
    _xvnc_process: subprocess.Popen | None = None  # the X server (own group)
    _log_file: object | None = None
    _reader: threading.Thread | None = None


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


def xvfb_rfb_port(display: int) -> int:
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
    """Apply upstream tunnel.py's URL regex to the guest ssh log."""
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
    Xvfb readiness signal (the server's /health lives in-process now)."""
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


class DeskManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, DeskSession] = {}  # keyed by session key
        # One PulseAudio daemon for the whole app (guest apps reach it over
        # loopback); started with the first display, stopped with the last.
        self._pulse_process: subprocess.Popen | None = None
        # Fired on every session-set/status transition (start, running, stop,
        # error) so the UI can re-read running()/visible() reactively — the
        # controller wires this to an observable rev bump.
        self.on_sessions_changed: Callable[[], None] | None = None
        # Fired on every guest log line so the UI can stream the output panel.
        self.on_log_line: Callable[[], None] | None = None

    def _notify_changed(self) -> None:
        cb = self.on_sessions_changed
        if cb is not None:
            try:
                cb()
            except Exception:
                logger.debug("on_sessions_changed callback failed", exc_info=True)

    # ── public async API ──────────────────────────────────────────────────────

    async def start(
        self,
        container: str,
        *,
        display: int | None = None,
        desktop_env: str = DEFAULT_DESKTOP,
        app_command: str | None = None,
        fps: float = 12.0,  # kept for the settings surface — RFB has no fps knob
        quality: int = 70,
        compression: int = 2,
        geometry: str = "1280x720",
        host: str = "127.0.0.1",
        tunnel: bool = False,
        options: dict | None = None,
    ) -> DeskSession:
        with self._lock:
            if display is None:
                # Display numbers are GLOBAL: Xvfb binds TCP 6000+N on the host
                # network namespace that proot shares, so two containers must
                # never claim the same :N — the second Xvfb would fail to bind
                # while the readiness probe sees the first one's open port.
                display = self.next_free_display()
                if display < 0:
                    raise RuntimeError(f"no free X display number (0-{MAX_DISPLAY_NUMBER})")
            key = session_key(container, display)
            existing = self._sessions.get(key)
            if existing and existing.status in (DeskStatus.RUNNING, DeskStatus.STARTING):
                if existing.status is DeskStatus.RUNNING:
                    return existing
                raise RuntimeError(f"a display session '{key}' is already {existing.status.value}")
            session = DeskSession(
                container=container,
                key=key,
                mode="app" if app_command and app_command.strip() else "desktop",
                app_command=(app_command or "").strip(),
                desktop_env=desktop_env,
                display=display,
                port=_free_port(),
                fps=fps,
                quality=quality,
                geometry=geometry,
                host=host,
                tunnel=tunnel,
            )
            # Reserve the number as STARTING before publishing the session, so a
            # concurrent start (any container) can't claim the same :N while the
            # spawn window is open.
            session.status = DeskStatus.STARTING
            session.login_options = dict(options or {})
            self._sessions[key] = session
        self._notify_changed()
        session._loop = asyncio.get_running_loop()
        try:
            await asyncio.to_thread(self._spawn, session)
            await asyncio.to_thread(self._wait_xvfb, session, XVFB_READY_TIMEOUT)
        except Exception as exc:
            with self._lock:
                session.status = DeskStatus.ERROR
                session.error = str(exc).strip().splitlines()[0][:200] or exc.__class__.__name__
            self._notify_changed()
            raise
        if session.status is DeskStatus.STOPPING:
            return session
        if session.status is DeskStatus.ERROR:
            # _wait_xvfb does not raise on failure — it marks the session ERROR
            # ("the X server exited" / readiness timeout). A failed start must
            # never reach RUNNING: tear the process tree down and surface it
            # (device 2026-11-13: the user got a "running" dead surface with
            # the error wiped).
            self._kill_session(session)
            raise RuntimeError(session.error or "the display failed to start")
        # The stream server runs IN THIS PROCESS — its start() sets up the
        # aiohttp site and returns; the RFB bytes flow through the proxy task.
        try:
            server = stream_server.DisplayStreamServer(
                host,
                session.port,
                xvfb_rfb_port(session.display),
                _generate_code(),
                quality=_quality_level(quality),
                compression=compression,
            )
            await server.start()
        except Exception as exc:
            self._fail(session, f"the display server could not start: {exc}", session.log_tail)
            await asyncio.to_thread(self._kill_session, session)
            raise RuntimeError(session.error) from exc
        session.server = server
        session.code = server.code
        session.url = server.local_url()
        session.status = DeskStatus.RUNNING
        session.error = ""
        self._notify_changed()
        logger.info("display: %s ready on %s (Xvnc + noVNC in-app)", session.key, session.url)
        if session.tunnel:
            threading.Thread(target=self._poll_tunnel, args=(session,), daemon=True).start()
        return session

    async def stop(self, key: str) -> None:
        with self._lock:
            session = self._sessions.get(key)
            if session is None or session.status is DeskStatus.IDLE:
                return
            session.status = DeskStatus.STOPPING
        self._notify_changed()  # the row flips to "stopping…" immediately
        server = session.server
        if server is not None:
            try:
                await server.stop()
            except Exception as exc:
                logger.debug("server stop failed for %s: %s", key, exc)
        session.server = None
        await asyncio.to_thread(self._stop_sync, session)
        with self._lock:
            live = any(s.status is not DeskStatus.IDLE for s in self._sessions.values())
        if not live:
            await asyncio.to_thread(self._stop_pulseaudio)
        self._notify_changed()  # the row disappears once fully stopped

    async def stop_all(self) -> None:
        with self._lock:
            keys = [k for k, s in self._sessions.items() if s.status is not DeskStatus.IDLE]
        for key in keys:
            await self.stop(key)

    def get(self, key: str) -> DeskSession | None:
        with self._lock:
            return self._sessions.get(key)

    def next_free_display(self) -> int:
        """The lowest display number not claimed by a live session, or -1."""
        with self._lock:
            used = {s.display for s in self._sessions.values() if s.status is not DeskStatus.IDLE}
            for n in range(MAX_DISPLAY_NUMBER + 1):
                if n not in used:
                    return n
        return -1

    def running(self) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.status is DeskStatus.RUNNING]

    def release_page_bindings(self) -> None:
        """Drop WebView references so a reopened page rebuilds them (the FGS
        keeps the process alive across activity destroy/recreate)."""
        with self._lock:
            for s in self._sessions.values():
                s.wv = None

    def visible(self) -> list[DeskSession]:
        """Sessions the Display tab lists as running — RUNNING plus STOPPING
        (so pressing Stop shows immediate "stopping…" feedback in place)."""
        with self._lock:
            return [
                s
                for s in self._sessions.values()
                if s.status in (DeskStatus.RUNNING, DeskStatus.STOPPING)
            ]

    def failed(self) -> list[DeskSession]:
        """Sessions that died on their own (start failure or mid-run crash).
        ERROR is a visible state: the tab lists each one with its log tail,
        a Retry and a Dismiss — a crash must never be silent (device
        2026-11-13: rows vanished and nothing explained why)."""
        with self._lock:
            return [s for s in self._sessions.values() if s.status is DeskStatus.ERROR]

    def starting(self) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.status is DeskStatus.STARTING]

    def for_container(self, container: str) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.container == container]

    # ── sync implementation (worker threads) ─────────────────────────────────

    def _spawn(self, session: DeskSession) -> None:
        # The cookie file must exist before anything connects to the display:
        # Xvnc reads it via -auth, the guest session exports it as XAUTHORITY.
        cookie_path = xvnc_runtime.write_xauth_file(
            xauth_cookie(),
            session.display,
            xvnc_runtime.guest_cookie_path(session.container, session.display),
        )
        xkb_dir = xvnc_runtime.ensure_xkb_dir()
        session.status = DeskStatus.STARTING
        session.error = ""
        session.started_at = time.time()
        logger.info(
            "display: starting %s (%s on :%d), server will bind %s:%d",
            session.key,
            session.mode,
            session.display,
            session.host,
            session.port,
        )
        # Durable by design: upstream `clear-cache` empties the CACHE root,
        # which would destroy the only crash evidence if these lived there
        # (device audit 2026-11-13). The data root survives clear-cache.
        log_path = storage_paths.data_root() / "display-logs" / f"{session.key}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "wb", buffering=0)  # noqa: SIM115 - closed in _stop_sync / on failure
        session._log_file = log_file
        try:
            # Xvnc FIRST — the guest session connects to its X port the moment
            # it starts. Own process group, own log reader.
            xvnc_argv, xvnc_env = xvnc_runtime.xvnc_command(
                session.display, session.geometry, cookie_path, xkb_dir
            )
            session._xvnc_process = xvnc_runtime.spawn(xvnc_argv, xvnc_env)
            threading.Thread(
                target=self._read_logs,
                args=(session, session._xvnc_process, "xvnc"),
                daemon=True,
            ).start()
            self._ensure_pulseaudio()

            script = build_guest_script(
                display=session.display,
                port=session.port,
                desktop_env=session.desktop_env,
                geometry=session.geometry,
                xauth_cookie=xauth_cookie(),
                tunnel=session.tunnel,
                app_command=session.app_command or None,
            )
            guest_script = _write_guest_script(session.container, script, session.display)
            login_opts = getattr(session, "login_options", None)
            if login_opts:
                # Advanced login options: user/work_dir/env/bind/shared_*/
                # isolated/fix_low_ports — everything proot-distro supports.
                env, argv = session_service.session_argv_with_options(
                    session.container, {"login_cmd": ["/bin/sh", guest_script], **login_opts}
                )
            else:
                env, argv = session_service.command_argv(
                    container=session.container, command=["/bin/sh", guest_script]
                )
            session._process = subprocess.Popen(  # noqa: S603 - our hardened login argv
                argv,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True,
                start_new_session=True,
            )
            session.pid = session._process.pid
            session._reader = threading.Thread(
                target=self._read_logs, args=(session, session._process, "guest"), daemon=True
            )
            session._reader.start()
        except Exception:
            # spawn failed — kill whatever side already started, don't leak
            self._kill_session(session)
            session._log_file = None
            try:
                log_file.close()
            except OSError:
                pass
            raise

    def _read_logs(self, session: DeskSession, process: subprocess.Popen, kind: str) -> None:
        if process.stdout is None:
            return
        log_file = session._log_file
        while True:
            line = process.stdout.readline()
            if not line:
                break  # EOF: the process closed its stdout (usually dead)
            text = line.decode("utf-8", "replace").rstrip()
            session.log_tail.append(f"[{kind}] {text}" if kind != "guest" else text)
            # Surface every line in the app's diagnostic terminal — this is the
            # ONLY place Xvnc/session errors appear, and a black screen is
            # unreadable without them.
            logger.info("display[%s][%s] %s", session.key, kind, text)
            cb = self.on_log_line
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass
            if log_file is not None:
                try:
                    if log_file.tell() < MAX_LOG_BYTES:
                        log_file.write(line)
                    else:
                        log_file.seek(0)
                        log_file.truncate()
                except OSError:
                    pass
        # Crash watcher: EOF while RUNNING means that side died — the guest
        # session ended (single app closed) or the X server died. Both end the
        # session; shut the stream server down on the session loop.
        if session.status is DeskStatus.RUNNING and process.poll() is not None:
            what = "the X server" if kind == "xvnc" else "the display session"
            self._fail(
                session,
                f"{what} exited (code {process.returncode})",
                session.log_tail,
            )
            loop = session._loop
            server = session.server
            if loop is not None and server is not None:

                async def _stop_server() -> None:
                    try:
                        await server.stop()
                    except Exception:
                        pass

                try:
                    loop.call_soon_threadsafe(asyncio.create_task, _stop_server())
                except RuntimeError:
                    pass  # loop gone (app closed) — the process is dying anyway

    def _ensure_pulseaudio(self) -> None:
        """One app-wide daemon; audio degrades gracefully if it cannot start."""
        if self._pulse_process is not None and self._pulse_process.poll() is None:
            return
        try:
            pa_argv, pa_env = xvnc_runtime.pulseaudio_command()
            self._pulse_process = xvnc_runtime.spawn(pa_argv, pa_env)
        except Exception as exc:
            logger.warning("display: pulseaudio could not start (audio disabled): %s", exc)
            self._pulse_process = None
            return
        threading.Thread(
            target=self._read_pulse_logs, args=(self._pulse_process,), daemon=True
        ).start()
        for _ in range(10):
            if xvnc_runtime.probe_pulseaudio():
                logger.info("display: pulseaudio up on 127.0.0.1:%d", xvnc_runtime.PULSE_TCP_PORT)
                return
            time.sleep(0.3)
        logger.warning("display: pulseaudio did not answer its tcp port (audio unavailable)")

    def _read_pulse_logs(self, process: subprocess.Popen) -> None:
        if process.stdout is None:
            return
        while True:
            line = process.stdout.readline()
            if not line:
                break
            logger.info("pulseaudio: %s", line.decode("utf-8", "replace").rstrip())
        if self._pulse_process is process:
            self._pulse_process = None
        logger.info("pulseaudio: exited (code %s)", process.returncode)

    def _stop_pulseaudio(self) -> None:
        process = self._pulse_process
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                pass
        self._pulse_process = None

    def _wait_xvfb(self, session: DeskSession, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        port = XVFB_TCP_BASE + session.display
        while time.monotonic() < deadline:
            if session.status is DeskStatus.STOPPING:
                return  # user pressed Cancel — not an error
            xvnc = session._xvnc_process
            if xvnc is None or xvnc.poll() is not None:
                if session.status is not DeskStatus.STOPPING:
                    self._fail(session, "the X server exited", session.log_tail)
                return
            if _tcp_open(port):
                return
            time.sleep(0.4)
        if session.status is not DeskStatus.STOPPING:
            self._fail(
                session,
                f"timed out waiting for the X display :{session.display} after {timeout:.0f}s",
                session.log_tail,
            )

    def _poll_tunnel(self, session: DeskSession) -> None:
        """Daemon: fill session.tunnel_url from the guest ssh log once
        localhost.run answers. Never blocks start(); absence is surfaced in
        the share dialog, never a start failure."""
        for _ in range(TUNNEL_RETRIES):
            process = session._process
            if process is None or process.poll() is not None:
                return  # session died — the crash watcher owns the error
            url = _read_tunnel_url(session.container, session.display)
            if url:
                session.tunnel_url = url
                logger.info("display: tunnel for %s at %s", session.key, url)
                return
            time.sleep(1.0)

    def _fail(self, session: DeskSession, message: str, log_tail: deque[str]) -> None:
        if session.status is DeskStatus.STOPPING:
            return
        last = ""
        for line in reversed(log_tail):
            if line.strip():
                last = line.strip()
                break
        session.error = f"{message}: {last}" if last else message
        session.error = session.error.splitlines()[0][:200]
        session.status = DeskStatus.ERROR
        self._notify_changed()
        logger.warning("display: %s — %s", session.key, session.error)
        # The log handle must not leak into the ERROR state: the reader
        # threads are done with it (EOF path) or their writes no-op through
        # the OSError guard, and a leaked fd keeps the file pinned until the
        # user happens to press Stop.
        log_file, session._log_file = session._log_file, None
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass

    def _kill_session(self, session: DeskSession) -> None:
        """SIGTERM both process groups (used when the stream server fails to
        start — no full stop() bookkeeping needed yet)."""
        for attr in ("_process", "_xvnc_process"):
            process = getattr(session, attr)
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except OSError:
                    pass

    def _stop_sync(self, session: DeskSession) -> None:
        # SIGTERM to both groups tears down the session, Xvnc and the tunnel;
        # the in-process server was already stopped by stop().
        for attr in ("_process", "_xvnc_process"):
            process = getattr(session, attr)
            if process is None or process.poll() is not None:
                continue
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                pass
            try:
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    logger.warning("display: %s process group refused to die", session.key)
        log_file, session._log_file = session._log_file, None
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass
        session._process = None
        session._xvnc_process = None
        session._reader = None
        session.pid = None
        session.status = DeskStatus.IDLE
        session.url = ""
        session.code = ""
        session.tunnel_url = ""
        session.wv = None  # release the last WebView with the session
        logger.info("display: %s stopped", session.key)


_SHARED: DeskManager | None = None


def shared_manager() -> DeskManager:
    """Process-wide display registry. The foreground service keeps the PROCESS
    alive when the activity is destroyed, so a module-level singleton is what
    makes running displays survive an app reopen (same pattern as
    SessionManager.shared_manager)."""
    global _SHARED
    if _SHARED is None:
        _SHARED = DeskManager()
    return _SHARED
