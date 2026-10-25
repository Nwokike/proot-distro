"""Modal popup dialog wrapper for the container file manager matching CollabShell."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from screens.files import FilesView


def show_manage_files_modal(page: ft.Page, container: str, initial_path: str = "/root") -> None:
    """Show the container file manager inside a modal dialog."""
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=theme.primary()),
                ft.Text(f"Files — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            ],
            spacing=tokens.SPACE_SM,
        ),
        content=ft.Container(
            content=FilesView(default_container=container, default_path=initial_path),
            width=tokens.DIALOG_WIDTH_LG + 120,
            height=480,
        ),
        actions=[
            ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
        ],
    )
    page.show_dialog(dialog)
