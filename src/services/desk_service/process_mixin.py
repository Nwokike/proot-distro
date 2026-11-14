"""Session failure, teardown and log-file cleanup."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
from collections import deque

from . import xvnc_runtime
from .models import DeskSession, DeskStatus

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


class ProcessMixin:
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
