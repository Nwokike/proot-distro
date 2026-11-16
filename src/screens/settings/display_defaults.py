"""Settings — Display defaults, rendered INLINE on the Settings screen.

The owner's ruling (2026-11-15): the display defaults belong on the page next
to the terminal defaults, not behind their own subscreen. Related options share
a line, each line has a tiny label, and the advanced Xvnc/audio surface stays
the same scrollable ExpansionTile.
"""

from __future__ import annotations

import flet as ft

from components.ui import pill_dropdown
from core import theme, tokens
from core.state import state
from screens.display_sheets.advanced import _advanced_display_controls
from screens.display_sheets.common import _set_setting, _switch_row


def _pill(key: str, label: str, icon: ft.IconData, choices: tuple[tuple[str, str], ...], on_change):
    settings = state.display_settings or {}
    current = str(settings.get(key, choices[0][0]))
    values = [value for value, _text in choices]
    if current not in values:
        values.append(current)

    def _select(value: str, k: str = key) -> None:
        _set_setting(k, value)
        if on_change is not None:
            on_change()

    return pill_dropdown(
        label,
        icon,
        values,
        current,
        _select,
        tooltip=label,
        labels=dict(choices),
    )


def _line(controls: list[ft.Control]) -> ft.Control:
    return ft.Row(
        controls=controls,
        spacing=tokens.SPACE_MD,
        wrap=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _tiny(label: str) -> ft.Control:
    return ft.Text(label, size=tokens.FONT_XS, color=theme.text_dim())


def build_display_defaults(on_change=None) -> ft.Control:
    """The display-default surface, inline: image → viewer → advanced."""
    return ft.Column(
        controls=[
            _tiny("Image"),
            _line(
                [
                    _pill(
                        "depth",
                        "Depth",
                        ft.Icons.LAYERS_ROUNDED,
                        (("16", "16-bit"), ("24", "24-bit"), ("32", "32-bit")),
                        on_change,
                    ),
                    _pill(
                        "quality",
                        "Quality",
                        ft.Icons.HIGH_QUALITY_ROUNDED,
                        (("50", "50"), ("70", "70"), ("85", "85"), ("95", "95")),
                        on_change,
                    ),
                    _pill(
                        "compression",
                        "Compression",
                        ft.Icons.COMPRESS_ROUNDED,
                        (("2", "Fast"), ("6", "Balanced"), ("9", "Smallest")),
                        on_change,
                    ),
                    _pill(
                        "fps",
                        "Frame rate",
                        ft.Icons.SPEED_ROUNDED,
                        (("15", "15 /s"), ("30", "30 /s"), ("60", "60 /s")),
                        on_change,
                    ),
                ]
            ),
            _line(
                [
                    _pill(
                        "geometry",
                        "Resolution",
                        ft.Icons.ASPECT_RATIO_ROUNDED,
                        (
                            ("auto", "Match this phone"),
                            ("1280x720", "1280 x 720"),
                            ("1600x900", "1600 x 900"),
                            ("1920x1080", "1920 x 1080"),
                        ),
                        on_change,
                    ),
                    _pill(
                        "resize",
                        "Fit",
                        ft.Icons.FIT_SCREEN_ROUNDED,
                        (
                            ("scale", "Fit the whole desktop"),
                            ("remote", "Remote resize"),
                            ("off", "Actual size"),
                        ),
                        on_change,
                    ),
                    _pill(
                        "orientation",
                        "Full screen",
                        ft.Icons.SCREEN_LOCK_LANDSCAPE_ROUNDED,
                        (
                            ("landscape", "Landscape"),
                            ("portrait", "Portrait"),
                            ("auto", "System"),
                        ),
                        on_change,
                    ),
                ]
            ),
            _tiny("Viewer & input"),
            _line(
                [
                    _switch_row("Clipboard sync", "clipboard", True),
                    _switch_row("View only", "view_only", False),
                    _switch_row("Kick other viewers", "disconnect_clients", False),
                    _switch_row("LAN: Wi-Fi devices", "lan", False),
                    _switch_row("Public URL tunnel", "tunnel", False),
                ]
            ),
            _advanced_display_controls(),
        ],
        spacing=tokens.SPACE_XS,
        tight=True,
    )
