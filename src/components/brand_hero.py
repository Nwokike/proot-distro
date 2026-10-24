"""Brand hero + the shared theme toggle (CollabShell pattern).

CollabShell puts its brand mark in the HOME body — a large centered icon under
a tagline — and keeps the shell free of a header bar; the theme switch is a
bare icon button beside the content it belongs to. The icon is the SVG the
owner supplied; it is tinted per theme (white on dark) so the artwork inverts
with the color mode.
"""

from __future__ import annotations

import flet as ft

from core import theme


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
    """The home hero: large centered brand icon (+ optional tagline).

    CollabShell's geometry: token spacers around an ICON_XXXL (80) icon,
    tagline at FONT_SM. The tint needs SRC_IN to actually recolor the
    artwork (color alone is not a guaranteed recolor in flet 1.0.4).
    """
    from core import tokens

    controls: list[ft.Control] = [
        ft.Container(height=tokens.SPACE_LG),
        ft.Image(
            src=app_icon_svg(),
            width=tokens.HERO_ICON_SIZE,
            height=tokens.HERO_ICON_SIZE,
            fit=ft.BoxFit.CONTAIN,
            # Color-invert with the theme: white on dark, artwork's own
            # colors on light (the owner's requested behavior).
            color=None if theme.is_light_theme() else ft.Colors.WHITE,
            color_blend_mode=ft.BlendMode.SRC_IN,
            error_content=ft.Icon(ft.Icons.TERMINAL, size=tokens.ICON_HERO),
        ),
    ]
    if tagline:
        controls.extend(
            [
                ft.Container(height=tokens.SPACE_SM),
                ft.Text(
                    tagline,
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                    text_align=ft.TextAlign.CENTER,
                ),
            ]
        )
    controls.append(ft.Container(height=tokens.SPACE_XL))
    return ft.Container(
        content=ft.Column(
            controls=controls,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
        ),
    )
