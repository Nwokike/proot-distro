"""The app-wide PulseAudio daemon lifecycle."""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time

from . import xvnc_runtime

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


class AudioMixin:
    def _ensure_pulseaudio(
        self,
        *,
        mic: bool = True,
        latency_ms: int = 0,
        pm: int = 2,
        rate: int = 0,
        no_close_hack: bool = False,
        mic_rate: int = 0,
        mic_format: str = "",
        mic_channels: int = 0,
        resample_method: str = "",
    ) -> None:
        """One app-wide daemon; audio degrades gracefully if it cannot start.

        The first display configures it; a LATER display that asks for a
        different audio shape (mic on/off, AAudio latency/performance) makes
        the daemon restart with the new configuration — otherwise those
        controls would be silently inert until every display stopped (device
        audit 2026-11-14: first-display-wins)."""
        config = (
            bool(mic),
            int(latency_ms),
            int(pm),
            int(rate),
            bool(no_close_hack),
            int(mic_rate),
            str(mic_format),
            int(mic_channels),
            str(resample_method),
        )
        alive = self._pulse_process is not None and self._pulse_process.poll() is None
        if alive:
            if getattr(self, "_pulse_config", None) == config:
                return
            logger.info("display: pulseaudio reconfiguring for %s", config)
            self._stop_pulseaudio()
        try:
            pa_argv, pa_env = xvnc_runtime.pulseaudio_command(
                mic=mic,
                latency_ms=latency_ms,
                pm=pm,
                rate=rate,
                no_close_hack=no_close_hack,
                mic_rate=mic_rate,
                mic_format=mic_format,
                mic_channels=mic_channels,
                resample_method=resample_method,
            )
            self._pulse_process = xvnc_runtime.spawn(pa_argv, pa_env)
            self._pulse_config = config
        except Exception as exc:
            logger.warning("display: pulseaudio could not start (audio disabled): %s", exc)
            self._pulse_process = None
            self._pulse_config = None
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
            try:
                process.wait(timeout=2.0)  # port must be free before a restart
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=1.0)
                except OSError:
                    pass
                except subprocess.TimeoutExpired:
                    logger.warning("pulseaudio refused to die")
        self._pulse_process = None
        self._pulse_config = None
