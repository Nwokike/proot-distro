"""AppHeader — the shared menu chrome (CollabShell's pattern).

Tab name left in bold; the action cluster right (theme cycle now, help/version
slots built in). No brand mark here — the hero lives in the home body.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core import theme
from core.state import state


def theme_button(on_cycle: Callable[[], None]) -> ft.Control:
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
        icon_size=18,
        tooltip=f"{tooltip} — tap to switch",
        on_click=lambda _e: on_cycle(),
    )


def AppHeader(title: str, on_cycle_theme: Callable[[], None]) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=theme.text()),
                ft.Container(expand=True),
                ft.Row(
                    controls=[theme_button(on_cycle_theme)],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
    )
