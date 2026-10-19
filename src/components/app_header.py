"""AppHeader — the single shared header for every screen (house pattern).

Brand SVG left (tinted white on dark), optional title/subtitle column, and
the action cluster right: the 3-way theme cycle plus per-screen extras.
Mirrors Sherlock's `AppHeader` and ffmpeg's `BrandHeader`: both views build
it during render, so a theme flip re-paints it. `ft.Image` renders SVG
natively (flet 1.0.4); the icon loads as bytes so it can be tinted.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import flet as ft

from core import theme
from core.state import state


def app_icon_svg() -> bytes:
    """The brand SVG as bytes (ffmpeg's load_asset_bytes pattern)."""
    src_root = Path(__file__).resolve().parents[1]
    for candidate in (
        src_root / "assets" / "icon.svg",
        Path.cwd() / "src" / "assets" / "icon.svg",
        Path.cwd() / "assets" / "icon.svg",
    ):
        if candidate.is_file():
            return candidate.read_bytes()
    return b""


def theme_icon() -> str:
    """The theme-cycle icon for the current mode (read at render time)."""
    return {
        "light": ft.Icons.LIGHT_MODE,
        "dark": ft.Icons.DARK_MODE,
    }.get(state.theme_mode, ft.Icons.BRIGHTNESS_AUTO)


def AppHeader(
    *,
    title: str | None = None,
    subtitle: str | None = None,
    on_cycle_theme: Callable[[], None] | None = None,
    extra_actions: list[ft.Control] | None = None,
) -> ft.Control:
    is_light = theme.is_light_theme()

    left: list[ft.Control] = [
        ft.Image(
            src=app_icon_svg(),
            width=30,
            height=30,
            fit=ft.BoxFit.CONTAIN,
            # Sherlock convention: tint the mark white on dark, keep the
            # artwork's own colors on light.
            color=None if is_light else ft.Colors.WHITE,
            error_content=ft.Icon(ft.Icons.TERMINAL, size=24),
        ),
    ]
    if title:
        title_controls: list[ft.Control] = [
            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=theme.text()),
        ]
        if subtitle:
            title_controls.append(
                ft.Text(subtitle, size=10, color=theme.text_dim()),
            )
        left.append(ft.Column(controls=title_controls, spacing=0, tight=True))

    right: list[ft.Control] = list(extra_actions or [])
    right.append(
        ft.IconButton(
            icon=theme_icon(),
            icon_size=18,
            on_click=lambda _e: on_cycle_theme() if on_cycle_theme else None,
            tooltip="Theme: Light / Dark / System",
        ),
    )

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    left,
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(expand=True),
                ft.Row(
                    right,
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
