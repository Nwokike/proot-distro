"""Session spawn, log tailing, readiness and the tunnel poll."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import threading
import time

from core import storage_paths
from services import session_service

from . import xvnc_runtime
from .models import (
    DeskSession,
    DeskStatus,
    _read_tunnel_url,
    _write_guest_script,
    xauth_cookie,
)
from .script import build_guest_script

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


class SpawnMixin:
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
            # Core X fonts: the bundled set first (bare containers have none),
            # then whatever font dirs the container itself provides.
            staged_fonts = xvnc_runtime.ensure_font_dir()
            font_paths = (
                [str(staged_fonts)] if staged_fonts is not None else []
            ) + xvnc_runtime.guest_font_dirs(session.container)
            xvnc_argv, xvnc_env = xvnc_runtime.xvnc_command(
                session.display,
                session.geometry,
                cookie_path,
                xkb_dir,
                depth=session.depth,
                frame_rate=session.frame_rate,
                shared_policy=session.shared_policy,
                clipboard=session.clipboard,
                disconnect_timeout=session.disconnect_timeout,
                desktop_name=session.desktop_name or session.key,
                font_paths=font_paths,
                localhost_only=session.localhost_only,
                compare_fb=session.compare_fb,
                dpi=session.dpi,
                idle_timeout=session.idle_timeout,
                max_connection_time=session.max_connection_time,
                view_only=session.view_only,
                max_cut_text=session.max_cut_text,
                disconnect_clients=session.disconnect_clients,
            )
            session._xvnc_process = xvnc_runtime.spawn(xvnc_argv, xvnc_env)
            threading.Thread(
                target=self._read_logs,
                args=(session, session._xvnc_process, "xvnc"),
                daemon=True,
            ).start()
            self._ensure_pulseaudio(
                mic=session.mic,
                latency_ms=session.audio_latency_ms,
                pm=session.audio_pm,
                rate=session.audio_rate,
                no_close_hack=session.audio_no_close_hack,
                mic_rate=session.mic_rate,
                mic_format=session.mic_format,
                mic_channels=session.mic_channels,
                resample_method=session.resample_method,
            )
            # A file guests/scripts can `source` — the same values every new
            # shell inherits (display_env is the ONE source of truth).
            self._write_display_env_file(session)

            if session.mode == "display":
                # Bare X display (started from a terminal): no session to run —
                # the caller's existing shell gets DISPLAY injected directly.
                session.pid = None
                return

            script = build_guest_script(
                display=session.display,
                port=session.port,
                desktop_env=session.desktop_env,
                geometry=session.geometry,
                xauth_cookie=xauth_cookie(),
                tunnel=session.tunnel,
                pulse=self.pulse_server_alive(),
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

    def _write_display_env_file(self, session: DeskSession) -> None:
        """Write `<rootfs>/tmp/x11/env` — the display's guest environment in
        sourceable form (`source /tmp/x11/env`). Same values as the shell
        overlay, from the same helper."""
        from .display_env import guest_display_env

        try:
            rootfs = storage_paths.containers_dir() / session.container / "rootfs"
            target = rootfs / "tmp" / "x11" / "env"
            target.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                f"export {key}={value}"
                for key, value in guest_display_env(
                    session.display,
                    pulse=self.pulse_server_alive(),
                    bus=session.mode != "display",
                ).items()
            ]
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.debug("display env file not written: %r", exc)

    def _read_logs(self, session: DeskSession, process: subprocess.Popen, kind: str) -> None:
        if process.stdout is None:
            return
        while True:
            # Two reader threads share one handle and either may rotate it, so
            # re-read it each iteration instead of capturing a stale (closed)
            # object at thread start.
            log_file = session._log_file
            line = process.stdout.readline()
            if not line:
                break  # EOF: the process closed its stdout (usually dead)
            text = line.decode("utf-8", "replace").rstrip()
            session.log_tail.append(f"[{kind}] {text}" if kind != "guest" else text)
            # Surface every line in the app's diagnostic terminal — this is the
            # ONLY place Xvnc/session errors appear, and a black screen is
            # unreadable without them.
            logger.info("display[%s][%s] %s", session.key, kind, text)
            # 10 Hz: every line used to bump the observable and re-render the
            # whole desktop view; log_tail is read on render anyway.
            now = time.monotonic()
            if now - session._log_notify_at >= 0.1:
                session._log_notify_at = now
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
                        # Rotate instead of rewinding in place: the old write
                        # path truncated and lost the newest context exactly
                        # when a crash was being explained.
                        from pathlib import Path

                        current = Path(log_file.name)
                        log_file.close()
                        rotated = current.with_suffix(current.suffix + ".1")
                        try:
                            rotated.unlink(missing_ok=True)
                            current.replace(rotated)
                        except OSError:
                            pass
                        log_file = open(current, "wb", buffering=0)  # noqa: SIM115
                        session._log_file = log_file
                        log_file.write(line)
                except OSError, ValueError:
                    # ValueError: the other reader rotated and closed this
                    # handle between our re-read and the write.
                    pass
        cb = self.on_log_line  # trailing notify so the last lines are painted
        if cb is not None:
            try:
                cb()
            except Exception:
                pass
        # Crash watcher: EOF while RUNNING means that side died — the guest
        # session ended (single app closed) or the X server died. Both end the
        # session; shut the stream server down on the session loop.
        if session.status is DeskStatus.RUNNING and process.poll() is not None:
            # A configured auto-close (MaxDisconnectionTime) makes Xvnc exit
            # with code 0 once the last viewer has been gone for N seconds —
            # that is the feature WORKING, not a crash: close the session
            # cleanly instead of surfacing a false ERROR.
            clean_auto_close = (
                kind == "xvnc" and process.returncode == 0 and session.disconnect_timeout > 0
            )
            if clean_auto_close:
                logger.info(
                    "display: %s auto-closed after %ss without viewers",
                    session.key,
                    session.disconnect_timeout,
                )
                # Full teardown bookkeeping (kills the guest tree, closes the
                # log handle, frees the session) — not just a status flip.
                with self._lock:
                    session.status = DeskStatus.STOPPING
                self._stop_sync(session)
                self._notify_changed()
            else:
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
