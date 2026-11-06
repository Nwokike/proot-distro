"""Responsive installed-container card — exactly three inline items: Open
shell, Open display (or Install desktop), and the ⋯ menu (rename/backup/copy/
sync/inspect/run + reset/remove live there now, grouped with the destructive
pair last)."""

from __future__ import annotations

import flet as ft

from components import card
from core import theme, tokens
from core.state import state
from screens.container_actions import container_menu_items
from screens.formatting import format_size


def build_container_card(row: dict, page: ft.Page, methods, is_narrow: bool) -> ft.Control:
    cname = row.get("name", "?")
    caps = (state.display_support or {}).get(cname) or {}
    ready = bool(caps.get("desk_ready") and caps.get("x_server"))
    # No probe yet (first paint) — label it unknown; the card must never lie
    # about install state before the probe lands.
    display_label = "Checking…" if not caps else ("Open display" if ready else "Install desktop")

    details_col = ft.Column(
        controls=[
            ft.Text(
                cname,
                size=tokens.FONT_MD,
                weight=ft.FontWeight.BOLD,
                color=theme.text(),
            ),
            ft.Text(
                f"{row.get('image', '')} · {format_size(row.get('size_bytes', 0))} · {row.get('arch', '')}",
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            ),
        ],
        spacing=tokens.SPACE_NONE,
        expand=not is_narrow,
    )

    btn_shell = ft.FilledButton(
        "Open shell",
        on_click=lambda _e: page.run_task(methods.open_session, cname),
        height=tokens.CONTROL_SM,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
        ),
    )
    btn_display = ft.FilledTonalButton(
        display_label,
        icon=ft.Icons.DESKTOP_WINDOWS,
        on_click=lambda _e: page.run_task(methods.open_display, cname),
        height=tokens.CONTROL_SM,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
        ),
    )
    menu_btn = ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        icon_size=tokens.ICON_MD,
        tooltip="More actions",
        items=container_menu_items(page, methods, cname),
    )

    if is_narrow:
        card_content = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.APPS_ROUNDED, size=tokens.ICON_MD, color=theme.primary()),
                        details_col,
                        menu_btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_SM,
                ),
                ft.Row(
                    controls=[btn_shell, btn_display],
                    spacing=tokens.SPACE_SM,
                    wrap=True,
                ),
            ],
            spacing=tokens.SPACE_SM,
        )
    else:
        card_content = ft.Row(
            controls=[
                ft.Icon(ft.Icons.APPS_ROUNDED, size=tokens.ICON_MD, color=theme.primary()),
                details_col,
                btn_shell,
                btn_display,
                menu_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
        )

    return card(card_content, padding=tokens.SPACE_SM)
