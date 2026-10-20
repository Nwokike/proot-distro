"""AppHeader — the shared menu chrome (CollabShell's pattern).

Tab name left in bold; the action cluster right (theme cycle now, help/version
slots built in). No brand mark here — the hero lives in the home body.
"""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from core import theme, tokens
from core.constants import APP_VERSION
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


def version_chip(page: ft.Page | None) -> ft.Control:
    """v{version} — or an Update pill when the feed is ahead (house pattern)."""
    from core.state import state as core_state

    if core_state.update_available:
        data = core_state.update_data or {}
        label = data.get("version", "Update") if data.get("type") != "announcement" else "News"
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        f"Update: {label} Available!"
                        if data.get("type") != "announcement"
                        else "News",
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.BOLD,
                        color=theme.primary(),
                        no_wrap=True,
                    ),
                    ft.Container(
                        width=6,
                        height=6,
                        border_radius=3,
                        bgcolor=theme.primary(),
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(10, 4, 10, 4),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.15, theme.primary()),
            border=ft.Border.all(1.5, theme.primary()),
            ink=True,
            tooltip="New update available — tap to view",
            on_click=lambda _e: _open_update_dialog(page),
        )
    return ft.Container(
        content=ft.Text(
            f"v{APP_VERSION}",
            size=tokens.FONT_SM,
            weight=ft.FontWeight.BOLD,
            color=theme.text_dim(),
            no_wrap=True,
        ),
        padding=ft.Padding(10, 4, 10, 4),
        border_radius=10,
        bgcolor=ft.Colors.with_opacity(0.08, theme.text_dim()),
        ink=True,
        tooltip="What's New — version & changelog",
        on_click=lambda _e: _open_update_dialog(page),
    )


def _open_update_dialog(page: ft.Page | None) -> None:
    if page is None:
        return
    from components.update_dialog import show_update_dialog
    from core.state import state as core_state

    show_update_dialog(page, core_state.update_data if core_state.update_available else None)


def AppHeader(
    title: str, on_cycle_theme: Callable[[], None], page: ft.Page | None = None
) -> ft.Control:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Text(
                    title,
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                    color=theme.text(),
                ),
                ft.Container(expand=True),
                ft.Row(
                    controls=[
                        version_chip(page),
                        theme_button(on_cycle_theme),
                    ],
                    spacing=tokens.SPACE_XS,
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
