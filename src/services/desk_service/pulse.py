"""PulseAudio config + daemon argv + the mic permission."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import ClassVar

from core import storage_paths

from .xvnc_paths import (
    PULSE_TCP_PORT,
    _payload_env,
    module_path,
    pulseaudio_binary,
)
from .xvnc_payload import ensure_pa_libs

logger = logging.getLogger(__name__)


def write_pulse_config(
    runtime: Path,
    *,
    mic: bool = True,
    latency_ms: int = 0,
    pm: int = 2,
    rate: int = 0,
    no_close_hack: bool = False,
    mic_rate: int = 0,
    mic_format: str = "",
    mic_channels: int = 0,
) -> Path:
    """The daemon script: load OUR modules by absolute path (the compiled module
    dir is the Termux prefix, which does not exist in the app) and serve guests
    on the shared loopback only.

    Options map to real module args: `latency=` (ms; 0 = AAudio's own
    buffer-derived value) and `pm=` (AAudio performance-mode offset — 2 is
    LOW_LATENCY) for the sink; the mic source is loaded only when enabled."""
    pa_dir = runtime / "pulse"
    pa_dir.mkdir(parents=True, exist_ok=True)
    sink_args = " sink_name=output"
    if int(latency_ms) > 0:
        sink_args += f" latency={int(latency_ms)}"
    sink_args += f" pm={int(pm)}"
    if int(rate) > 0:
        sink_args += f" rate={int(rate)}"
    if no_close_hack:
        sink_args += " no_close_hack=1"
    lines = [
        # speakers (AAudio — the OpenSL ES sink broke on Android 16)
        f"load-module {module_path('module-aaudio-sink.so')}{sink_args}",
        # fallback when the device audio stack refuses the sink above
        f"load-module {module_path('module-null-sink.so')} sink_name=fallback",
    ]
    if mic:
        # microphone (guest apps record through PULSE_SERVER)
        mic_args = " source_name=mic"
        for key, value in (
            ("rate", int(mic_rate)),
            ("channels", int(mic_channels)),
        ):
            if value > 0:
                mic_args += f" {key}={value}"
        if mic_format:
            mic_args += f" format={mic_format}"
        lines.append(f"load-module {module_path('module-sles-source.so')}{mic_args}")
    lines.append(
        # serve guest apps over loopback TCP
        f"load-module {module_path('module-native-protocol-tcp.so')}"
        f" port={PULSE_TCP_PORT} listen=127.0.0.1"
        " auth-ip-acl=127.0.0.1 auth-anonymous=1"
    )
    path = pa_dir / "default.pa"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def request_mic_permission() -> None:
    """Grant RECORD_AUDIO at RUNTIME before the mic module loads.

    Android's dangerous permissions need a runtime grant — declaring
    RECORD_AUDIO in the manifest is not enough, and PulseAudio's sles-source
    fails with "Failed to initialize OpenSL ES: error 9" until the user allows
    it (device 2026-11-13). The Activity comes from serious_python's own
    embedding class; requestPermissions runs on the UI thread."""
    try:
        from jnius import PythonJavaClass, autoclass, java_method

        activity = autoclass("com.flet.serious_python_android.PythonActivity").mActivity
        if activity is None:
            return
        PackageManager = autoclass("android.content.pm.PackageManager")
        if (
            activity.checkSelfPermission("android.permission.RECORD_AUDIO")
            == PackageManager.PERMISSION_GRANTED
        ):
            return

        def _ask() -> None:
            activity.requestPermissions(["android.permission.RECORD_AUDIO"], 4713)

        class _UiRunnable(PythonJavaClass):  # pyjnius Java-interface shape
            __javainterfaces__: ClassVar[list] = ["java/lang/Runnable"]
            __javacontext__: ClassVar[str] = "app"

            @java_method("()V")
            def run(self) -> None:
                _ask()

        activity.runOnUiThread(_UiRunnable())
        logger.info("display: requested the microphone permission")
    except Exception as exc:  # desktop/no pyjnius — audio degradation only
        logger.debug("mic permission request skipped: %s", exc)


def pulseaudio_command(
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
) -> tuple[list[str], dict[str, str]]:
    """The PulseAudio daemon argv + env (one app-wide daemon; the manager starts
    it with the first display and stops it with the last). -n skips the missing
    system default.pa; -F runs ours, which loads every module by absolute path.
    `mic`/`latency_ms`/`pm` configure the module lines (see write_pulse_config);
    the RECORD_AUDIO grant is requested only when the mic is enabled."""
    if mic:
        request_mic_permission()
    binary = pulseaudio_binary()
    runtime = storage_paths.support_root() / "runtime"
    script = write_pulse_config(
        runtime,
        mic=mic,
        latency_ms=latency_ms,
        pm=pm,
        rate=rate,
        no_close_hack=no_close_hack,
        mic_rate=mic_rate,
        mic_format=mic_format,
        mic_channels=mic_channels,
    )
    env = _payload_env(binary.parent)
    pa_libs = ensure_pa_libs()
    # libcrypto-free linker path (see ensure_pa_libs)
    env["LD_LIBRARY_PATH"] = str(pa_libs)
    argv = [
        str(binary),
        *([f"--resample-method={resample_method}"] if resample_method else []),
        "--daemonize=no",
        "--exit-idle-time=-1",
        "--disallow-exit=1",
        "--use-pid-file=false",
        "--fail=0",
        "-n",
        f"--file={script}",
    ]
    return argv, env


def probe_pulseaudio() -> bool:
    """True when the daemon answers on the loopback TCP port."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", PULSE_TCP_PORT), timeout=0.5):
            return True
    except OSError:
        return False
