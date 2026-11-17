"""The advanced display options (every control threads into Xvnc/PulseAudio).

Every enum uses the house pill (components/ui.pill_dropdown) so these match the
Home/Build controls; booleans are switches. All values are the real option keys
— labels are display-only, and a saved custom value is never hidden.
"""

from __future__ import annotations

import logging

import flet as ft

from components.ui import pill_dropdown
from core import theme, tokens
from core.state import state

from .common import _set_setting, _switch_row

logger = logging.getLogger(__name__)


def _pill(
    key: str,
    label: str,
    icon: ft.IconData,
    choices: tuple[tuple[str, str], ...],
    *,
    default: str,
    tooltip: str = "",
) -> ft.Control:
    current = str((state.display_settings or {}).get(key, default))
    values = [value for value, _text in choices]
    if current not in values:
        values.append(current)  # a saved custom value must stay selectable
    labels = dict(choices)
    return pill_dropdown(
        label,
        icon,
        values,
        current,
        lambda value, k=key: _set_setting(k, value),
        tooltip=tooltip,
        labels=labels,
    )


def _row(controls: list[ft.Control]) -> ft.Row:
    return ft.Row(controls=controls, spacing=tokens.SPACE_SM, wrap=True)


def _advanced_display_controls() -> ft.Control:
    """Real Xvnc/PulseAudio options — each thread 1:1 into the argv/module
    lines (depth → -depth, frame rate → -FrameRate, viewers →
    -AlwaysShared/-NeverShared, auto-close → -MaxDisconnectionTime, clipboard →
    -AcceptCutText/-SendCutText, audio → the PulseAudio module args)."""
    return ft.ExpansionTile(
        title=ft.Text("Advanced display options", size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(
            "Depth, frame rate, viewers, privacy and audio, applied when the display starts.",
            size=tokens.FONT_XXS,
            color=theme.text_dim(),
        ),
        expanded=False,
        controls=[
            _row(
                [
                    _pill(
                        "depth",
                        "Depth",
                        ft.Icons.LAYERS_ROUNDED,
                        (("16", "16-bit"), ("24", "24-bit"), ("32", "32-bit")),
                        default="24",
                        tooltip="Xvnc -depth",
                    ),
                    _pill(
                        "fps",
                        "Frame rate",
                        ft.Icons.SPEED_ROUNDED,
                        (("15", "15 /s"), ("30", "30 /s"), ("60", "60 /s")),
                        default="30",
                        tooltip="Xvnc -FrameRate (1-60)",
                    ),
                    _pill(
                        "shared_policy",
                        "Viewers",
                        ft.Icons.GROUPS_ROUNDED,
                        (("always", "Several"), ("never", "One at a time")),
                        default="always",
                        tooltip="Xvnc -AlwaysShared / -NeverShared",
                    ),
                ]
            ),
            _row(
                [
                    _pill(
                        "compare_fb",
                        "Pixel diff",
                        ft.Icons.DIFFERENCE_ROUNDED,
                        (("2", "Compare"), ("1", "Region"), ("0", "Always send")),
                        default="2",
                        tooltip="Xvnc -CompareFB",
                    ),
                    _pill(
                        "dpi",
                        "DPI",
                        ft.Icons.STRAIGHTEN_ROUNDED,
                        (("0", "Default"), ("96", "96"), ("120", "120"), ("144", "144")),
                        default="0",
                        tooltip="Xvnc -dpi (0 = default, up to 480)",
                    ),
                    _pill(
                        "disconnect_timeout",
                        "Auto-close",
                        ft.Icons.TIMER_OFF_ROUNDED,
                        (("0", "Never"), ("900", "15 min"), ("1800", "30 min"), ("3600", "1 hour")),
                        default="0",
                        tooltip="Xvnc -MaxDisconnectionTime",
                    ),
                ]
            ),
            _row(
                [
                    _pill(
                        "idle_timeout",
                        "Idle timeout",
                        ft.Icons.HOURGLASS_EMPTY_ROUNDED,
                        (("0", "Never"), ("300", "5 min"), ("900", "15 min")),
                        default="0",
                        tooltip="Xvnc -IdleTimeout (drops an idle viewer)",
                    ),
                    _pill(
                        "max_connection_time",
                        "Max session",
                        ft.Icons.TIMELAPSE_ROUNDED,
                        (("0", "Unlimited"), ("1800", "30 min"), ("7200", "2 hours")),
                        default="0",
                        tooltip="Xvnc -MaxConnectionTime",
                    ),
                    _pill(
                        "max_cut_text",
                        "Clipboard cap",
                        ft.Icons.CONTENT_PASTE_ROUNDED,
                        (
                            ("0", "Default"),
                            ("65536", "64 KiB"),
                            ("262144", "256 KiB"),
                            ("1048576", "1 MiB"),
                        ),
                        default="0",
                        tooltip="Xvnc -MaxCutText (bytes, up to 16 MiB)",
                    ),
                ]
            ),
            _row(
                [
                    _switch_row("Clipboard sync", "clipboard", True),
                    _switch_row("Microphone", "mic", False),
                    _switch_row("Restrict to this device", "restrict_local", False),
                    _switch_row("View only", "view_only", False),
                    _switch_row("Kick other viewers", "disconnect_clients", False),
                ]
            ),
            _row(
                [
                    _pill(
                        "audio_pm",
                        "Audio mode",
                        ft.Icons.GRAPHIC_EQ_ROUNDED,
                        (("2", "Low latency"), ("1", "Power saving"), ("0", "Balanced")),
                        default="2",
                        tooltip="AAudio performance mode (pm=)",
                    ),
                    _pill(
                        "audio_latency_ms",
                        "Audio latency",
                        ft.Icons.AV_TIMER_ROUNDED,
                        (("0", "Default"), ("40", "40 ms"), ("80", "80 ms"), ("125", "125 ms")),
                        default="0",
                        tooltip="AAudio latency= (0-2000 ms)",
                    ),
                    _pill(
                        "audio_rate",
                        "Speaker rate",
                        ft.Icons.SPEAKER_ROUNDED,
                        (("0", "Default"), ("44100", "44.1 kHz"), ("48000", "48 kHz")),
                        default="0",
                        tooltip="AAudio sink rate=",
                    ),
                ]
            ),
            _row(
                [
                    _pill(
                        "mic_rate",
                        "Mic rate",
                        ft.Icons.MIC_ROUNDED,
                        (
                            ("0", "Default"),
                            ("16000", "16 kHz"),
                            ("44100", "44.1 kHz"),
                            ("48000", "48 kHz"),
                        ),
                        default="0",
                        tooltip="sles-source rate=",
                    ),
                    _pill(
                        "mic_format",
                        "Mic format",
                        ft.Icons.GRAPHIC_EQ_ROUNDED,
                        (("", "Default"), ("s16le", "s16le"), ("float32le", "float32le")),
                        default="",
                        tooltip="sles-source format=",
                    ),
                    _pill(
                        "mic_channels",
                        "Mic channels",
                        ft.Icons.SURROUND_SOUND_ROUNDED,
                        (("0", "Default"), ("1", "Mono"), ("2", "Stereo")),
                        default="0",
                        tooltip="sles-source channels= (0-8)",
                    ),
                ]
            ),
            _row(
                [
                    _pill(
                        "resample_method",
                        "Resampler",
                        ft.Icons.TUNE_ROUNDED,
                        (
                            ("", "Default"),
                            ("speex-float-1", "Speex fast"),
                            ("speex-float-5", "Speex HQ"),
                            ("soxr-hq", "SoXR HQ"),
                        ),
                        default="",
                        tooltip="PulseAudio --resample-method",
                    ),
                    _pill(
                        "viewer_logging",
                        "Viewer log",
                        ft.Icons.BUG_REPORT_ROUNDED,
                        (
                            ("error", "Errors"),
                            ("warn", "Warnings"),
                            ("info", "Info"),
                            ("debug", "Debug"),
                        ),
                        default="warn",
                        tooltip="noVNC client log level",
                    ),
                    _switch_row("AAudio workaround", "audio_no_close_hack", False),
                    _switch_row("Viewer bell", "viewer_bell", True),
                    _switch_row("Cursor dot", "show_dot", False),
                    _switch_row(
                        "Forward guest notifications",
                        "forward_guest_notifications",
                        True,
                    ),
                ]
            ),
        ],
    )
