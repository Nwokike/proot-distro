"""DeskManager — N X11 display sessions per container (keyed `container:display`).

ARCHITECTURE (the native wrap): the TermuxDeskServer runs IN THE APP PROCESS
with its bundled deps (aiohttp/Pillow/python-xlib came in transitively with
the termux-desk dependency). The guest container only provides the X
framebuffer (`Xvfb :N` on TCP) and the desktop/app session. The server
connects to `127.0.0.1:N` — proot shares the host network namespace, so guest
loopback IS host loopback.

Lifecycle: IDLE → STARTING (spawn guest tree + wait for the Xvfb TCP port +
start the in-process server) → RUNNING → STOPPING → IDLE, or ERROR with a
bounded log tail and an explicit Retry. The guest tree is one proot process
group (`start_new_session` + `--kill-on-exit`), so SIGTERM tears down Xvfb,
the session, and any ssh tunnel together; `server.stop()` closes the aiohttp
site and the X connection.

The manager is a process-wide singleton (like SessionManager): the FGS keeps
the process alive across activity destroy/recreate, so a reopened app
re-adopts the still-running display sessions instead of losing them.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import shlex
import signal
import socket
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from core import storage_paths
from services import session_service

from .environments import DEFAULT_DESKTOP
from .script import TUNNEL_URL_RE, build_guest_script, guest_script_name, guest_tunnel_log

logger = logging.getLogger(__name__)

MAX_LOG_LINES = 300
MAX_LOG_BYTES = 2 * 1024 * 1024
XVFB_READY_TIMEOUT = 60.0  # Xvfb itself is quick; the DE loads in parallel
TUNNEL_RETRIES = 60  # polled on a daemon thread AFTER ready — never blocks start()
MAX_DISPLAY_NUMBER = 99
XVFB_TCP_BASE = 6000


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
    log_tail: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    started_at: float = 0.0
    server: object | None = None  # the in-process TermuxDeskServer
    wv: object | None = None  # the WebView control, created once by DesktopView
    _loop: asyncio.AbstractEventLoop | None = None
    _process: subprocess.Popen | None = None
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


def _cookie_host_path(container: str, display: int) -> Path:
    """The HOST-side path of the guest's xauth file (inside the rootfs)."""
    return (
        storage_paths.containers_dir()
        / container
        / "rootfs"
        / "tmp"
        / "termux-desk"
        / f"xauth-{display}"
    )


def _write_guest_script(container: str, script: str, display: int) -> str:
    """Write the guest script into the container rootfs; return the
    guest-ABSOLUTE path (the guest cwd is /root, so a relative path would
    resolve into the wrong place — on-device lesson)."""
    rootfs = storage_paths.containers_dir() / container / "rootfs"
    name = guest_script_name(display)
    target = rootfs / "tmp" / "termux-desk" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(script, encoding="utf-8")
    return f"/tmp/termux-desk/{name}"  # noqa: S108 - guest path in the rootfs


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


# ── clipboard shim ───────────────────────────────────────────────────────────
# Upstream TermuxDeskServer shells out to `xclip` with DISPLAY set. On Android
# there is no host xclip, so ONE dispatcher shim on our PATH routes the call
# into the container that owns $DISPLAY (each session registered its own
# proot-exec script). Upstream code stays untouched.


def _shim_dir() -> Path:
    return storage_paths.cache_root() / "xclip-shim"


def _ensure_clipboard_shim(container: str, display: int) -> None:
    """(Re)generate the dispatcher + the per-container exec script and the
    DISPLAY→container registry, then prepend the dir to PATH once."""
    shim_dir = _shim_dir()
    shim_dir.mkdir(parents=True, exist_ok=True)
    env, argv = session_service.command_argv(container, ["/usr/bin/xclip"])
    exec_env = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    exec_script = shim_dir / f"exec-{container}.sh"
    # DISPLAY/XAUTHORITY arrive per-call from the dispatcher (upstream sets
    # DISPLAY=127.0.0.1:N on the xclip subprocess); forward them explicitly so
    # the guest xclip sees the GUEST paths — appended after exec_env so they
    # win even if the hardened env ever carries stale values.
    exec_script.write_text(
        f"#!/system/bin/sh\n"
        f'exec {exec_env} DISPLAY="$PDX_GUEST_DISPLAY" XAUTHORITY="$PDX_GUEST_XAUTH"'
        f' {shlex.join(argv)} "$@"\n',
        encoding="utf-8",
    )
    dispatcher = shim_dir / "xclip"
    dispatcher.write_text(
        "#!/system/bin/sh\n"
        "D=${DISPLAY#*:}\n"
        "D=${D%%.*}\n"
        'C=$(awk -v n="$D" \'$1==n{print $2}\' "$PDX_XCLIP_REGISTRY" 2>/dev/null)\n'
        '[ -n "$C" ] || exit 3\n'
        # Guest-side values: TCP form matches the xauth "127.0.0.1:N" entry
        # (proot shares host loopback, so the guest reaches Xvfb's TCP port);
        # the xauth file is the guest path the session script wrote.
        'export PDX_GUEST_DISPLAY="127.0.0.1:$D"\n'
        'export PDX_GUEST_XAUTH="/tmp/termux-desk/xauth-$D"\n'
        'exec "$PDX_XCLIP_DIR/exec-$C.sh" "$@"\n',
        encoding="utf-8",
    )
    registry = shim_dir / "registry"
    lines: dict[str, str] = {}
    if registry.exists():
        for line in registry.read_text(encoding="utf-8").splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                lines[parts[0]] = parts[1]
    lines[str(display)] = container
    registry.write_text(
        "\n".join(f"{n} {c}" for n, c in sorted(lines.items(), key=lambda kv: int(kv[0]))) + "\n",
        encoding="utf-8",
    )
    for path in (dispatcher, exec_script):
        path.chmod(0o755)
    path_str = os.environ.get("PATH", "")
    if str(shim_dir) not in path_str.split(os.pathsep):
        os.environ["PATH"] = f"{shim_dir}{os.pathsep}{path_str}"
    os.environ.setdefault("PDX_XCLIP_REGISTRY", str(registry))
    os.environ["PDX_XCLIP_REGISTRY"] = str(registry)
    os.environ["PDX_XCLIP_DIR"] = str(shim_dir)


class DeskManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, DeskSession] = {}  # keyed by session key

    # ── public async API ──────────────────────────────────────────────────────

    async def start(
        self,
        container: str,
        *,
        display: int | None = None,
        desktop_env: str = DEFAULT_DESKTOP,
        app_command: str | None = None,
        fps: float = 12.0,
        quality: int = 70,
        geometry: str = "1280x720",
        host: str = "127.0.0.1",
        tunnel: bool = False,
    ) -> DeskSession:
        from termux_desk import TermuxDeskServer

        with self._lock:
            if display is None:
                used = {
                    s.display
                    for s in self._sessions.values()
                    if s.container == container and s.status is not DeskStatus.IDLE
                }
                display = next(n for n in range(MAX_DISPLAY_NUMBER + 1) if n not in used)
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
            self._sessions[key] = session
        session._loop = asyncio.get_running_loop()
        try:
            await asyncio.to_thread(self._spawn, session)
            await asyncio.to_thread(self._wait_xvfb, session, XVFB_READY_TIMEOUT)
        except Exception as exc:
            with self._lock:
                session.status = DeskStatus.ERROR
                session.error = str(exc).strip().splitlines()[0][:200] or exc.__class__.__name__
            raise
        if session.status is DeskStatus.STOPPING:
            return session
        # The server runs IN THIS PROCESS — upstream's async start() sets up
        # the aiohttp site and returns; run() is never called.
        try:
            if xauth_cookie():
                os.environ["XAUTHORITY"] = str(_cookie_host_path(container, display))
            server = TermuxDeskServer(
                host,
                session.port,
                display=f"127.0.0.1:{display}",
                fps=float(fps),
                quality=int(quality),
            )
            await server.start()
        except Exception as exc:
            self._fail(session, f"the display server could not start: {exc}", session.log_tail)
            await asyncio.to_thread(self._kill_guest, session)
            raise RuntimeError(session.error) from exc
        session.server = server
        session.code = server._auth_code
        session.url = server.local_url
        session.status = DeskStatus.RUNNING
        session.error = ""
        logger.info("display: %s ready on %s (server in-app)", session.key, session.url)
        try:
            await asyncio.to_thread(_ensure_clipboard_shim, container, display)
        except Exception as exc:
            logger.warning("clipboard shim setup failed for %s: %s", session.key, exc)
        if session.tunnel:
            threading.Thread(target=self._poll_tunnel, args=(session,), daemon=True).start()
        return session

    async def stop(self, key: str) -> None:
        with self._lock:
            session = self._sessions.get(key)
            if session is None or session.status is DeskStatus.IDLE:
                return
            session.status = DeskStatus.STOPPING
        server = session.server
        if server is not None:
            try:
                await server.stop()
            except Exception as exc:
                logger.debug("server stop failed for %s: %s", key, exc)
        session.server = None
        await asyncio.to_thread(self._stop_sync, session)

    async def stop_all(self) -> None:
        with self._lock:
            keys = [k for k, s in self._sessions.items() if s.status is not DeskStatus.IDLE]
        for key in keys:
            await self.stop(key)

    def get(self, key: str) -> DeskSession | None:
        with self._lock:
            return self._sessions.get(key)

    def running(self) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.status is DeskStatus.RUNNING]

    def starting(self) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.status is DeskStatus.STARTING]

    def for_container(self, container: str) -> list[DeskSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.container == container]

    # ── sync implementation (worker threads) ─────────────────────────────────

    def _spawn(self, session: DeskSession) -> None:
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
        env, argv = session_service.command_argv(
            container=session.container, command=["/bin/sh", guest_script]
        )
        log_path = storage_paths.cache_root() / "display-logs" / f"{session.key}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "wb", buffering=0)  # noqa: SIM115 - closed in _stop_sync / on failure
        session._log_file = log_file
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
        try:
            session._process = subprocess.Popen(  # noqa: S603 - our hardened login argv
                argv,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True,
                start_new_session=True,
            )
        except Exception:
            # spawn failed — don't leak the log file handle
            session._log_file = None
            try:
                log_file.close()
            except OSError:
                pass
            raise
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
                break  # EOF: the process closed its stdout (usually dead)
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
        # Crash watcher: EOF while RUNNING means the guest tree (Xvfb) died
        # after a successful start — mark ERROR so the UI stops offering
        # Resume, and shut the in-process server down on the session loop.
        if session.status is DeskStatus.RUNNING and process.poll() is not None:
            self._fail(
                session,
                f"the display session exited (code {process.returncode})",
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

    def _wait_xvfb(self, session: DeskSession, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        port = XVFB_TCP_BASE + session.display
        while time.monotonic() < deadline:
            if session.status is DeskStatus.STOPPING:
                return  # user pressed Cancel — not an error
            process = session._process
            if process is None or process.poll() is not None:
                if session.status is not DeskStatus.STOPPING:
                    self._fail(session, "the display session exited", session.log_tail)
                return
            if _tcp_open(port):
                return
            time.sleep(0.4)
        if session.status is not DeskStatus.STOPPING:
            self._fail(
                session,
                f"timed out waiting for Xvfb on :{session.display} after {timeout:.0f}s",
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
        logger.warning("display: %s — %s", session.key, session.error)

    def _kill_guest(self, session: DeskSession) -> None:
        """Kill the guest process group only (used when the server fails to
        start — no full stop() bookkeeping needed yet)."""
        process = session._process
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                pass

    def _stop_sync(self, session: DeskSession) -> None:
        # SIGTERM to the group tears down Xvfb, the session, and the tunnel;
        # the in-process server was already stopped by stop().
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
                    logger.warning("display: %s process group refused to die", session.key)
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
