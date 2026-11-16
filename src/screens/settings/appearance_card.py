"""Settings -> Appearance & Theme card (split out to keep the view under 500 lines)."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from screens.settings_components import _settings_card

_THEME_CHOICES = (
    ("light", "Light", ft.Icons.LIGHT_MODE_ROUNDED),
    ("dark", "Dark", ft.Icons.DARK_MODE_ROUNDED),
    ("system", "System", ft.Icons.BRIGHTNESS_AUTO_ROUNDED),
)


def _theme_card(mode: str, label: str, icon: ft.IconData, current: str, on_select) -> ft.Container:
    """Compact icon+label selector — CollabShell's preferences pattern: one row,
    centered, PRIMARY tint + border when selected, 150ms animate."""
    selected = current == mode
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    icon,
                    size=tokens.ICON_MD,
                    color=theme.primary() if selected else theme.text_dim(),
                ),
                ft.Text(
                    label,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400,
                    color=theme.primary() if selected else theme.text(),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
            tight=True,
        ),
        expand=True,
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
        border_radius=tokens.RADIUS_MD,
        border=ft.Border.all(
            tokens.BORDER_WIDTH_EMPHASIS if selected else tokens.HAIRLINE,
            theme.primary() if selected else theme.glass_border(),
        ),
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TINT, theme.primary())
        if selected
        else ft.Colors.with_opacity(tokens.OPACITY_SUBTLE, theme.text()),
        animate=ft.Animation(tokens.ANIM_FAST_MS, ft.AnimationCurve.EASE_OUT),
        on_click=lambda _e, m=mode: on_select(m),
        ink=True,
    )


def build_appearance_card(current_mode: str, on_select) -> ft.Control:
    """The Light / Dark / System selector."""
    return _settings_card(
        [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Theme", size=tokens.FONT_MD, weight=ft.FontWeight.W_500),
                        ft.Row(
                            controls=[
                                _theme_card(mode, label, icon, current_mode, on_select)
                                for mode, label, icon in _THEME_CHOICES
                            ],
                            spacing=tokens.SPACE_SM,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
                padding=tokens.SPACE_LG,
            ),
        ]
    )
