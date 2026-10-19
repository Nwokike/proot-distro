"""Brand hero + the shared theme toggle (CollabShell pattern).

CollabShell puts its brand mark in the HOME body — a large centered icon under
a tagline — and keeps the shell free of a header bar; the theme switch is a
bare icon button beside the content it belongs to. The icon is the SVG the
owner supplied; it is tinted per theme (white on dark) so the artwork inverts
with the color mode.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core import theme
from core.state import state


def app_icon_svg() -> bytes:
    """The brand SVG as bytes (ffmpeg's load_asset_bytes pattern)."""
    from pathlib import Path

    src_root = Path(__file__).resolve().parents[1]
    for candidate in (
        src_root / "assets" / "icon.svg",
        Path.cwd() / "src" / "assets" / "icon.svg",
        Path.cwd() / "assets" / "icon.svg",
    ):
        if candidate.is_file():
            return candidate.read_bytes()
    return b""


def build_brand_hero(tagline: str | None = None) -> ft.Control:
    """The home hero: large centered brand icon (+ optional tagline)."""
    controls: list[ft.Control] = [
        ft.Image(
            src=app_icon_svg(),
            width=96,
            height=96,
            fit=ft.BoxFit.CONTAIN,
            # Color-invert with the theme: white on dark, artwork's own
            # colors on light (the owner's requested behavior).
            color=None if theme.is_light_theme() else ft.Colors.WHITE,
            error_content=ft.Icon(ft.Icons.TERMINAL, size=64),
        ),
    ]
    if tagline:
        controls.append(
            ft.Text(
                tagline,
                size=12,
                color=theme.text_dim(),
                text_align=ft.TextAlign.CENTER,
            )
        )
    return ft.Container(
        content=ft.Column(
            controls=controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=ft.Padding.only(top=16, bottom=8),
    )


def theme_toggle_button(on_click: Callable[[], None]) -> ft.Control:
    """The shared theme-cycle button (CollabShell's round icon set)."""
    icon = {
        "light": ft.Icons.LIGHT_MODE_ROUNDED,
        "dark": ft.Icons.DARK_MODE_ROUNDED,
    }.get(state.theme_mode, ft.Icons.BRIGHTNESS_AUTO_ROUNDED)
    tooltip = {
        "light": "Light Theme",
        "dark": "Dark Theme",
    }.get(state.theme_mode, "System Theme")
    return ft.IconButton(
        icon=icon,
        icon_size=20,
        tooltip=f"{tooltip} — tap to switch",
        on_click=lambda _e: on_click(),
    )
