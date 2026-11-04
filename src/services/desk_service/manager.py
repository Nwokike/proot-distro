"""DeskManager — one X11 display session per container.

Lifecycle: IDLE → STARTING (spawn + /health readiness) → RUNNING → STOPPING →
IDLE, or ERROR with a bounded log tail and an explicit Retry (no automatic
restart loop). The whole guest tree is one process group (`start_new_session`
+ proot `--kill-on-exit`), so SIGTERM to the group tears down Xvfb, the
desktop, and the TermuxDesk server together.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum

from core import storage_paths
from services import session_service

from .environments import DEFAULT_DESKTOP
from .script import build_guest_script

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 300
MAX_LOG_BYTES = 2 * 1024 * 1024
READINESS_TIMEOUT = 90.0
AUTH_RETRIES = 20
TUNNEL_RETRIES = 60  # 60 x 1s — the tunnel needs a few seconds of ssh handshake
# GUEST paths inside the container rootfs (proot's own /tmp), not host /tmp.
AUTH_FILE = "/tmp/termux-desk/auth.json"  # noqa: S108 - guest path in the rootfs
TUNNEL_FILE = "/tmp/termux-desk/tunnel.json"  # noqa: S108 - guest path in the rootfs


class DeskStatus(StrEnum):
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class DeskSession:
    container: str
    mode: str = "desktop"  # v1: always "desktop"; app mode is a follow-up
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
    tunnel_url: str = ""  # filled from the guest tunnel.json once ssh reports it
    pid: int | None = None
    status: DeskStatus = DeskStatus.IDLE
    error: str = ""
    log_tail: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    started_at: float = 0.0
    wv: object | None = None  # the WebView control, created once by DesktopView
    _process: subprocess.Popen | None = None
    _log_file: object | None = None
    _reader: threading.Thread | None = None


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


def _write_guest_script(container: str, script: str) -> str:
    """Write the guest script into the container rootfs; return the
    guest-ABSOLUTE path (the guest cwd is /root, so a relative path would
    resolve into the wrong place — on-device lesson).

    Writing the exact bytes into the rootfs kills the whole class of
    argv-escaping bugs: the script passes through upstream's printed command
    line → our parse → harden → re-spawn, and only a file survives that
    round-trip byte-for-byte.
    """
    rootfs = storage_paths.containers_dir() / container / "rootfs"
    target = rootfs / "tmp" / "termux-desk" / "run-display.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8")
    return "/tmp/termux-desk/run-display.sh"  # noqa: S108 - guest path in the rootfs


def _read_auth(container: str) -> dict:
    """Read {code, port} from the rootfs file the guest server writes."""
    return _read_guest_json(container, AUTH_FILE)


def _read_tunnel(container: str) -> dict:
    """Read {url} (or {error}) from the rootfs file the tunnel thread writes."""
    return _read_guest_json(container, TUNNEL_FILE)


def _read_guest_json(container: str, guest_path: str) -> dict:
    rel = guest_path.lstrip("/")
    path = storage_paths.containers_dir() / container / "rootfs" / rel
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("guest file %s unreadable for %s: %r", guest_path, container, exc)
        return {}


def _http_ok(port: int, path: str = "/health") -> bool:
    """HTTP 200 from the TermuxDesk /health endpoint — the readiness signal."""
    import httpx

    try:
        response = httpx.get(f"http://127.0.0.1:{port}{path}", timeout=1.0)
        return response.status_code == 200
    except Exception:
        return False


class DeskManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, DeskSession] = {}

    # ── public async API ──────────────────────────────────────────────────────

    async def start(
        self,
        container: str,
        *,
        desktop_env: str = DEFAULT_DESKTOP,
        fps: float = 12.0,
        quality: int = 70,
        geometry: str = "1280x720",
        host: str = "127.0.0.1",
        tunnel: bool = False,
    ) -> DeskSession:
        with self._lock:
            existing = self._sessions.get(container)
            if existing and existing.status in (DeskStatus.RUNNING, DeskStatus.STARTING):
                if existing.status is DeskStatus.RUNNING:
                    return existing
                raise RuntimeError(
                    f"a display session for '{container}' is already {existing.status.value}"
                )
            session = DeskSession(
                container=container,
                desktop_env=desktop_env,
                fps=fps,
                quality=quality,
                geometry=geometry,
                host=host,
                tunnel=tunnel,
            )
            self._sessions[container] = session
        try:
            await asyncio.to_thread(self._spawn, session)
        except Exception as exc:
            with self._lock:
                session.status = DeskStatus.ERROR
                session.error = str(exc).strip().splitlines()[0][:200] or exc.__class__.__name__
            raise
        await asyncio.to_thread(self._wait_ready, session, READINESS_TIMEOUT)
        if session.status is DeskStatus.ERROR:
            raise RuntimeError(session.error)
        return session

    async def stop(self, container: str) -> None:
        with self._lock:
            session = self._sessions.get(container)
            if session is None or session.status is DeskStatus.IDLE:
                return
            session.status = DeskStatus.STOPPING
        await asyncio.to_thread(self._stop_sync, session)

    async def stop_all(self) -> None:
        with self._lock:
            containers = [c for c, s in self._sessions.items() if s.status is not DeskStatus.IDLE]
        for container in containers:
            await self.stop(container)

    def get(self, container: str) -> DeskSession | None:
        with self._lock:
            return self._sessions.get(container)

    def running(self) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.status is DeskStatus.RUNNING]

    # ── sync implementation (worker threads) ─────────────────────────────────

    def _spawn(self, session: DeskSession) -> None:
        session.port = _free_port()
        session.display = 0  # DISPLAY=:0 fixed everywhere (ServalDesk rule)
        script = build_guest_script(
            display=session.display,
            port=session.port,
            desktop_env=session.desktop_env,
            fps=session.fps,
            quality=session.quality,
            geometry=session.geometry,
            host=session.host,
            tunnel=session.tunnel,
        )
        guest_script = _write_guest_script(session.container, script)
        env, argv = session_service.command_argv(
            container=session.container, command=["/bin/sh", guest_script]
        )
        log_path = storage_paths.cache_root() / "display-logs" / f"{session.container}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "wb", buffering=0)  # noqa: SIM115 - closed in _stop_sync
        session._log_file = log_file
        session.status = DeskStatus.STARTING
        session.error = ""
        session.started_at = time.time()
        logger.info(
            "display: starting %s (xfce-session on :%d) on 127.0.0.1:%d",
            session.container,
            session.display,
            session.port,
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
        session._reader = threading.Thread(target=self._read_logs, args=(session,), daemon=True)
        session._reader.start()

    def _read_logs(self, session: DeskSession) -> None:
        process = session._process
        if process is None or process.stdout is None:
            return
        log_file = session._log_file
        while True:
            line = process.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").rstrip()
            session.log_tail.append(text)
            if log_file is not None:
                try:
                    if log_file.tell() < MAX_LOG_BYTES:
                        log_file.write(line)
                    else:
                        log_file.seek(0)
                        log_file.truncate()
                except OSError:
                    pass

    def _wait_ready(self, session: DeskSession, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            process = session._process
            if process is None or process.poll() is not None:
                self._fail(session, "the display server exited", session.log_tail)
                return
            if _http_ok(session.port):
                self._finish_ready(session)
                return
            time.sleep(0.5)
        self._fail(
            session,
            f"timed out waiting for the display server after {timeout:.0f}s",
            session.log_tail,
        )

    def _finish_ready(self, session: DeskSession) -> None:
        """/health answered — read the auth code the guest wrote. The viewer
        reads the code from its input box, so DesktopView injects it via
        run_javascript after page load (viewer.html has no URL-param support).
        When a tunnel was requested, the public *.lhr.life URL is read the
        same way; a tunnel that never comes up is surfaced in the share
        dialog, never a start failure."""
        auth: dict = {}
        for _ in range(AUTH_RETRIES):
            auth = _read_auth(session.container)
            if auth.get("code"):
                break
            time.sleep(0.25)
        code = auth.get("code") or ""
        if not code:
            self._fail(session, "the display server never wrote its access code", session.log_tail)
            return
        session.url = f"http://127.0.0.1:{session.port}/"
        session.code = code
        session.status = DeskStatus.RUNNING
        logger.info("display: %s ready on %s", session.container, session.port)
        if session.tunnel:
            for _ in range(TUNNEL_RETRIES):
                if session._process is None or session._process.poll() is not None:
                    return  # died while waiting — _wait_ready/_fail path owns it
                data = _read_tunnel(session.container)
                if data.get("url"):
                    session.tunnel_url = str(data["url"])
                    logger.info(
                        "display: tunnel for %s at %s", session.container, session.tunnel_url
                    )
                    return
                time.sleep(1.0)

    def _fail(self, session: DeskSession, message: str, log_tail: deque[str]) -> None:
        last = ""
        for line in reversed(log_tail):
            if line.strip():
                last = line.strip()
                break
        session.error = f"{message}: {last}" if last else message
        session.error = session.error.splitlines()[0][:200]
        session.status = DeskStatus.ERROR
        logger.warning("display: %s — %s", session.container, session.error)

    def _stop_sync(self, session: DeskSession) -> None:
        # termux-desk has no stop command — the process group IS the API.
        # SIGTERM reaches Xvfb, the desktop session, and the server together.
        process = session._process
        if process is not None and process.poll() is None:
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
                    logger.warning("display: %s process group refused to die", session.container)
        log_file, session._log_file = session._log_file, None
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass
        session._process = None
        session._reader = None
        session.pid = None
        session.status = DeskStatus.IDLE
        session.url = ""
        session.code = ""
        session.tunnel_url = ""
        logger.info("display: %s stopped", session.container)
