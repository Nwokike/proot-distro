"""Copy and sync dialogs."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def ask_copy(page: ft.Page, methods, container: str) -> None:
    source = ft.TextField(
        hint_text="source (container:/path)",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )
    destination = ft.TextField(
        hint_text="destination (container:/path)",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )

    use_move = ft.Checkbox(label="Move (delete source after copy)", value=False)
    use_recursive = ft.Checkbox(label="Recursive", value=True)

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(
            methods.copy_path,
            source.value or "",
            destination.value or "",
            bool(use_move.value),
            bool(use_recursive.value),
        )

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Copy a path", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[source, destination, use_move, use_recursive],
                spacing=tokens.SPACE_XS,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Copy",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )


def ask_sync(page: ft.Page, methods, container: str) -> None:
    source = ft.TextField(
        hint_text="source folder (host or container:/path)",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )
    dest = ft.TextField(
        hint_text="destination folder",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )
    use_checksum = ft.Checkbox(label="Verify with checksums", value=False)
    prune_dest = ft.Checkbox(label="Prune files deleted in source", value=False)

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(
            methods.sync_path,
            source.value or "",
            dest.value or "",
            bool(use_checksum.value),
            bool(prune_dest.value),
        )

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Sync Directory", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[source, dest, use_checksum, prune_dest],
                spacing=tokens.SPACE_XS,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Sync",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )
