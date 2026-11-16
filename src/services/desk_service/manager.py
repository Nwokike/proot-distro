"""One X11 display session per container: spawn, readiness, teardown.

The class is assembled from mixins (spawn, audio, process) so each file stays
small; models.py holds DeskSession/DeskStatus and the helpers.
"""

from __future__ import annotations

import asyncio
import os  # noqa: F401 - historical module surface (tests patch these names)
import subprocess
import threading
import time
from collections.abc import Callable

from core import storage_paths  # noqa: F401
from services import session_service  # noqa: F401

from . import stream_server, xvnc_runtime
from .audio_mixin import AudioMixin
from .environments import DEFAULT_DESKTOP
from .models import (  # noqa: F401 - re-exported for tests and callers
    MAX_DISPLAY_NUMBER,
    MAX_LOG_BYTES,
    XVNC_READY_TIMEOUT,
    XVNC_RFB_BASE,
    DeskSession,
    DeskStatus,
    _free_port,
    _generate_code,
    _local_ip,
    _quality_level,
    _read_tunnel_url,
    _tcp_open,
    _write_guest_script,
    logger,
    session_key,
    xauth_cookie,
    xvnc_rfb_port,
)
from .process_mixin import ProcessMixin
from .script import build_guest_script  # noqa: F401
from .spawn_mixin import SpawnMixin


class DeskManager(SpawnMixin, AudioMixin, ProcessMixin):
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
        bare: bool = False,  # X server only — no guest session (terminal use)
        frame_rate: int = 30,  # Xvnc -FrameRate (updates/second to the viewer)
        quality: int = 70,
        compression: int = 2,
        geometry: str = "1280x720",
        depth: str = "24",
        shared_policy: str = "always",
        resize_mode: str = "remote",
        clipboard: bool = True,
        localhost_only: bool = False,
        compare_fb: int = 2,
        dpi: int = 0,
        idle_timeout: int = 0,
        max_connection_time: int = 0,
        view_only: bool = False,
        max_cut_text: int = 0,
        disconnect_clients: bool = False,
        audio_rate: int = 0,
        audio_no_close_hack: bool = False,
        mic_rate: int = 0,
        mic_format: str = "",
        mic_channels: int = 0,
        resample_method: str = "",
        viewer_bell: bool = True,
        show_dot: bool = False,
        viewer_logging: str = "warn",
        disconnect_timeout: int = 0,
        desktop_name: str = "",
        mic: bool = True,
        audio_latency_ms: int = 0,
        audio_pm: int = 2,
        host: str = "127.0.0.1",
        tunnel: bool = False,
        options: dict | None = None,
    ) -> DeskSession:
        with self._lock:
            if display is None:
                # Display numbers are GLOBAL: Xvnc binds TCP 6000+N on the host
                # network namespace that proot shares, so two containers must
                # never claim the same :N — the second Xvnc would fail to bind
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
                mode=(
                    "display"
                    if bare
                    else "app"
                    if app_command and app_command.strip()
                    else "desktop"
                ),
                app_command=(app_command or "").strip(),
                desktop_env=desktop_env,
                display=display,
                port=_free_port(),
                fps=float(frame_rate),
                quality=quality,
                geometry=geometry,
                depth=depth,
                frame_rate=frame_rate,
                shared_policy=shared_policy,
                resize_mode=resize_mode,
                clipboard=clipboard,
                disconnect_timeout=disconnect_timeout,
                desktop_name=desktop_name,
                mic=mic,
                audio_latency_ms=audio_latency_ms,
                audio_pm=audio_pm,
                host=host,
                tunnel=tunnel,
            )
            # Reserve the number as STARTING before publishing the session, so a
            # concurrent start (any container) can't claim the same :N while the
            # spawn window is open.
            session.status = DeskStatus.STARTING
            session.login_options = dict(options or {})
            # Opt-in raw-port gates (defaults unchanged: no password, all
            # interfaces). The stream server's access code stays the viewer gate.
            session.localhost_only = bool(localhost_only)
            session.compare_fb = max(0, min(2, int(compare_fb)))
            session.dpi = max(0, int(dpi))
            session.idle_timeout = max(0, int(idle_timeout))
            session.max_connection_time = max(0, int(max_connection_time))
            session.view_only = bool(view_only)
            session.max_cut_text = max(0, int(max_cut_text))
            session.disconnect_clients = bool(disconnect_clients)
            session.audio_rate = max(0, int(audio_rate))
            session.audio_no_close_hack = bool(audio_no_close_hack)
            session.mic_rate = max(0, int(mic_rate))
            session.mic_format = str(mic_format or "")
            session.mic_channels = max(0, int(mic_channels))
            session.resample_method = str(resample_method or "")
            session.viewer_bell = bool(viewer_bell)
            session.show_dot = bool(show_dot)
            session.viewer_logging = str(viewer_logging or "warn")
            self._sessions[key] = session
        self._notify_changed()
        session._loop = asyncio.get_running_loop()
        try:
            await asyncio.to_thread(self._spawn, session)
            await asyncio.to_thread(self._wait_xvnc, session, XVNC_READY_TIMEOUT)
        except Exception as exc:
            with self._lock:
                session.status = DeskStatus.ERROR
                session.error = str(exc).strip().splitlines()[0][:200] or exc.__class__.__name__
            self._notify_changed()
            raise
        if session.status is DeskStatus.STOPPING:
            return session
        if session.status is DeskStatus.ERROR:
            # _wait_xvnc does not raise on failure — it marks the session ERROR
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
                xvnc_rfb_port(session.display),
                _generate_code(),
                quality=_quality_level(quality),
                compression=compression,
                resize_mode=session.resize_mode,
                bell=session.viewer_bell,
                show_dot=session.show_dot,
                logging_level=session.viewer_logging,
                view_only=session.view_only,
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

    def pulse_server_alive(self) -> bool:
        """True while the app-wide PulseAudio daemon runs. Public accessor —
        the actions layer must never read the private process handle."""
        process = self._pulse_process
        return process is not None and process.poll() is None

    def guest_display_env(self, container: str) -> dict[str, str]:
        """DISPLAY/XAUTHORITY/PULSE_SERVER for a NEW shell on `container` while
        one of its displays runs — so GUI apps launched from any shell reach
        the display (device 2026-11-14: `firefox` → "no DISPLAY"). Deterministic
        pick: desktop-mode first, then the lowest display; only RUNNING sessions
        count (STARTING/STOPPING/ERROR point nowhere). Empty when no display
        runs — the shell keeps today's plain environment."""
        from .display_env import guest_display_env as _env

        with self._lock:
            candidates = [
                s
                for s in self._sessions.values()
                if s.container == container and s.status is DeskStatus.RUNNING
            ]
        # A display whose auth file is gone cannot be used (XAUTHORITY would
        # fail) — skip it rather than poisoning the whole shell env.
        candidates = [
            s for s in candidates if xvnc_runtime.guest_cookie_path(container, s.display).is_file()
        ]
        if not candidates:
            return {}
        chosen = min(candidates, key=lambda s: (s.mode != "desktop", s.display))
        # A bare "display" session never starts the per-display bus, so it must
        # not advertise a socket that does not exist.
        return _env(
            chosen.display,
            pulse=self.pulse_server_alive(),
            bus=chosen.mode != "display",
        )

    # ── sync implementation (worker threads) ─────────────────────────────────

    def _wait_xvnc(self, session: DeskSession, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        port = XVNC_RFB_BASE + session.display
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
