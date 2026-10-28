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
        icon_size=tokens.ICON_SM,
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
                        width=tokens.STATUS_DOT_SM,
                        height=tokens.STATUS_DOT_SM,
                        border_radius=tokens.DOT_RADIUS,
                        bgcolor=theme.primary(),
                    ),
                ],
                spacing=tokens.HEADER_DOT_SPACING,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(
                tokens.CHIP_PADDING_H,
                tokens.CHIP_PADDING_V,
                tokens.CHIP_PADDING_H,
                tokens.CHIP_PADDING_V,
            ),
            border_radius=tokens.HEADER_RADIUS,
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_CHIP, theme.primary()),
            border=ft.Border.all(tokens.BORDER_WIDTH_EMPHASIS, theme.primary()),
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
        padding=ft.Padding(
            tokens.CHIP_PADDING_H,
            tokens.CHIP_PADDING_V,
            tokens.CHIP_PADDING_H,
            tokens.CHIP_PADDING_V,
        ),
        border_radius=tokens.HEADER_RADIUS,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.text_dim()),
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


def _open_help_dialog(page: ft.Page | None) -> None:
    """The header Help slot: the capability hints in a dialog."""
    if page is None:
        return
    from components.ui import hints_card

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("How this works", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=hints_card(False, lambda _e: page.pop_dialog()),
                width=tokens.DIALOG_MIN_WIDTH,
            ),
            actions=[ft.TextButton("Got it", on_click=lambda _e: page.pop_dialog())],
        )
    )


def AppHeader(
    title: str, on_cycle_theme: Callable[[], None], page: ft.Page | None = None
) -> ft.Control:
    # CollabShell's bar: one flat Row — title left, expand spacer, action
    # cluster right. No scroll (a header never scrolls horizontally), no
    # SPACE_BETWEEN (the spacer owns the alignment), token padding.
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
                version_chip(page),
                ft.IconButton(
                    icon=ft.Icons.HELP_OUTLINE_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="How this works",
                    on_click=lambda _e: _open_help_dialog(page),
                ),
                theme_button(on_cycle_theme),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
    )
