"""The advanced display options (every control threads into Xvnc/PulseAudio)."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import state

from .common import _picker_with_custom, _set_setting, _switch_row

logger = logging.getLogger(__name__)


def _advanced_display_controls() -> ft.Control:
    """Real Xvnc/PulseAudio options for technical users — every control here
    threads 1:1 into the server argv/module lines (depth → -depth, frame rate →
    -FrameRate, viewers → -AlwaysShared/-NeverShared, auto-close →
    -MaxDisconnectionTime, clipboard → -AcceptCutText/-SendCutText, audio →
    the PulseAudio module args). Defaults keep the friendly path intact."""
    settings = state.display_settings or {}
    return ft.ExpansionTile(
        title=ft.Text("Advanced display options", size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(
            "Depth, frame rate, viewers, privacy, audio — applied when the display starts.",
            size=tokens.FONT_XXS,
            color=theme.text_dim(),
        ),
        expanded=False,
        controls=[
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Color depth",
                        value=str(settings.get("depth", "24")),
                        options=[
                            ft.dropdown.Option("16", "16-bit (fastest)"),
                            ft.dropdown.Option("24", "24-bit (default)"),
                            ft.dropdown.Option("32", "32-bit"),
                        ],
                        on_select=lambda e: _set_setting("depth", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "Frame rate",
                        (("60", "60 /s"), ("30", "30 /s"), ("15", "15 /s")),
                        "fps",
                        hint="updates per second (1-60)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Viewers",
                        value=str(settings.get("shared_policy", "always")),
                        options=[
                            # noVNC always asks for shared=1, so upstream's
                            # "auto" is observably identical to "always" —
                            # exposing both would be a fake choice.
                            ft.dropdown.Option("always", "Several viewers"),
                            ft.dropdown.Option("never", "One viewer at a time"),
                        ],
                        on_select=lambda e: _set_setting("shared_policy", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "Auto-close",
                        (
                            ("0", "Never"),
                            ("900", "15 minutes"),
                            ("1800", "30 minutes"),
                            ("3600", "1 hour"),
                        ),
                        "disconnect_timeout",
                        hint="seconds after the last viewer (0 = never)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _switch_row("Clipboard sync", "clipboard", True),
                    _switch_row("Microphone", "mic", True),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _switch_row("Restrict to this device", "restrict_local", False),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Audio latency",
                        (
                            ("0", "Device default"),
                            ("40", "40 ms"),
                            ("80", "80 ms"),
                            ("125", "125 ms"),
                        ),
                        "audio_latency_ms",
                        hint="milliseconds (0-2000)",
                    ),
                    ft.Dropdown(
                        label="Audio performance",
                        value=str(settings.get("audio_pm", "2")),
                        options=[
                            ft.dropdown.Option("2", "Low latency"),
                            ft.dropdown.Option("1", "Power saving"),
                            ft.dropdown.Option("0", "Balanced"),
                        ],
                        on_select=lambda e: _set_setting("audio_pm", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            # ── remaining REAL Xvnc 1.16.2 parameters ──────────────────────
            ft.Row(
                controls=[
                    _switch_row("View only (no remote input)", "view_only", False),
                    _switch_row("New viewer kicks the others", "disconnect_clients", False),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Pixel diff",
                        value=str(settings.get("compare_fb", 2)),
                        options=[
                            ft.dropdown.Option("2", "Compare (default)"),
                            ft.dropdown.Option("1", "Region compare"),
                            ft.dropdown.Option("0", "Always send"),
                        ],
                        on_select=lambda e: _set_setting("compare_fb", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "DPI",
                        (("0", "Xvnc default"), ("96", "96"), ("120", "120"), ("144", "144")),
                        "dpi",
                        hint="dots per inch (0-480)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Viewer idle timeout",
                        (("0", "Never"), ("300", "5 minutes"), ("900", "15 minutes")),
                        "idle_timeout",
                        hint="seconds (0 = never)",
                    ),
                    _picker_with_custom(
                        "Max connection time",
                        (("0", "Unlimited"), ("1800", "30 minutes"), ("7200", "2 hours")),
                        "max_connection_time",
                        hint="seconds (0 = unlimited)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Clipboard limit",
                        (
                            ("0", "Xvnc default"),
                            ("65536", "64 KiB"),
                            ("262144", "256 KiB"),
                            ("1048576", "1 MiB"),
                        ),
                        "max_cut_text",
                        hint="bytes (0-16777216)",
                    ),
                    ft.Dropdown(
                        label="Speaker rate",
                        value=str(settings.get("audio_rate", 0)),
                        options=[
                            ft.dropdown.Option("0", "Device default"),
                            ft.dropdown.Option("44100", "44.1 kHz"),
                            ft.dropdown.Option("48000", "48 kHz"),
                        ],
                        on_select=lambda e: _set_setting("audio_rate", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _switch_row("AAudio close workaround", "audio_no_close_hack", False),
                    _switch_row("Viewer bell", "viewer_bell", True),
                    _switch_row("Show cursor dot", "show_dot", False),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Mic rate",
                        value=str(settings.get("mic_rate", 0)),
                        options=[
                            ft.dropdown.Option("0", "Device default"),
                            ft.dropdown.Option("16000", "16 kHz"),
                            ft.dropdown.Option("44100", "44.1 kHz"),
                            ft.dropdown.Option("48000", "48 kHz"),
                        ],
                        on_select=lambda e: _set_setting("mic_rate", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    ft.Dropdown(
                        label="Mic format",
                        value=str(settings.get("mic_format", "")),
                        options=[
                            ft.dropdown.Option("", "Device default"),
                            ft.dropdown.Option("s16le", "s16le"),
                            ft.dropdown.Option("float32le", "float32le"),
                        ],
                        on_select=lambda e: _set_setting("mic_format", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "Mic channels",
                        (("0", "Device default"), ("1", "Mono"), ("2", "Stereo")),
                        "mic_channels",
                        hint="channels (0-8)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Resampler",
                        value=str(settings.get("resample_method", "")),
                        options=[
                            ft.dropdown.Option("", "PulseAudio default"),
                            ft.dropdown.Option("speex-float-1", "Speex (faster)"),
                            ft.dropdown.Option("speex-float-5", "Speex HQ"),
                            ft.dropdown.Option("soxr-hq", "SoXR HQ"),
                        ],
                        on_select=lambda e: _set_setting("resample_method", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    ft.Dropdown(
                        label="Viewer log",
                        value=str(settings.get("viewer_logging", "warn")),
                        options=[
                            ft.dropdown.Option("error", "Errors"),
                            ft.dropdown.Option("warn", "Warnings"),
                            ft.dropdown.Option("info", "Info"),
                            ft.dropdown.Option("debug", "Debug"),
                        ],
                        on_select=lambda e: _set_setting("viewer_logging", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
        ],
    )
