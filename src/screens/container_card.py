"""Responsive installed-container card and its primary actions."""

from __future__ import annotations

import flet as ft

from components import card
from core import theme, tokens
from screens.container_actions import container_menu_items
from screens.formatting import format_size


def build_container_card(row: dict, page: ft.Page, methods, is_narrow: bool) -> ft.Control:
    cname = row.get("name", "?")

    def _reset(_e) -> None:
        def _yes(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.reset_container, cname)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Reset {cname}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "Container files are wiped back to the clean base image.",
                    size=tokens.FONT_SM,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.FilledButton(
                        "Reset",
                        on_click=_yes,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            bgcolor=theme.warn(),
                        ),
                    ),
                ],
            )
        )

    def _remove(_e) -> None:
        clean_cache_cb = ft.Checkbox(
            label="Also remove cached download layers",
            value=True,
        )

        def _yes(_e) -> None:
            page.pop_dialog()
            should_clean = bool(clean_cache_cb.value)

            async def _do_remove() -> None:
                await methods.remove_container(cname)
                if should_clean:
                    await methods.clear_orphan_layers()

            page.run_task(_do_remove)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Remove {cname}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Are you sure? This permanently deletes all files in this container.",
                            size=tokens.FONT_SM,
                        ),
                        clean_cache_cb,
                    ],
                    tight=True,
                    spacing=tokens.SPACE_SM,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.FilledButton(
                        "Remove",
                        on_click=_yes,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            bgcolor=theme.warn(),
                        ),
                    ),
                ],
            )
        )

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
    btn_reset = ft.Button("Reset", on_click=_reset, height=tokens.CONTROL_SM)
    btn_remove = ft.Button("Remove", on_click=_remove, height=tokens.CONTROL_SM)
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
                    controls=[btn_shell, btn_reset, btn_remove],
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
                btn_reset,
                btn_remove,
                menu_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
        )

    return card(card_content, padding=tokens.SPACE_SM)
