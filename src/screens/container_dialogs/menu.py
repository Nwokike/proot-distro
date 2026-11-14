"""The container overflow menu."""

from __future__ import annotations

import flet as ft

from core import theme, tokens

from .archive import ask_backup, ask_run
from .confirm import _confirm_restore, ask_remove, ask_rename, ask_reset, browse_files
from .path_ops import ask_copy, ask_sync
from .shell_options import ask_shell_options


def container_menu_items(page: ft.Page, methods, cname: str) -> list[ft.PopupMenuItem]:
    """Grouped container menu: info/actions first, then a separator, and the
    destructive pair last (warn-colored) so accidents don't sit next to
    everyday actions."""
    return [
        ft.PopupMenuItem(
            icon=ft.Icons.TERMINAL_ROUNDED,
            content=ft.Text("Shell with options…", size=tokens.FONT_SM),
            on_click=lambda _e: ask_shell_options(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.EDIT_ROUNDED,
            content=ft.Text("Rename", size=tokens.FONT_SM),
            on_click=lambda _e: ask_rename(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.ARCHIVE_ROUNDED,
            content=ft.Text("Backup snapshot", size=tokens.FONT_SM),
            on_click=lambda _e: ask_backup(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.UNARCHIVE_ROUNDED,
            content=ft.Text("Restore from backup…", size=tokens.FONT_SM),
            on_click=lambda _e: _confirm_restore(page, methods),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.FOLDER_COPY_ROUNDED,
            content=ft.Text("Copy a path", size=tokens.FONT_SM),
            on_click=lambda _e: ask_copy(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.SYNC_ROUNDED,
            content=ft.Text("Sync folder", size=tokens.FONT_SM),
            on_click=lambda _e: ask_sync(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            content=ft.Text("Browse files", size=tokens.FONT_SM),
            on_click=lambda _e: browse_files(page, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.INFO_OUTLINE_ROUNDED,
            content=ft.Text("Inspect container", size=tokens.FONT_SM),
            on_click=lambda _e: page.run_task(methods.inspect_container, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
            content=ft.Text("Run command", size=tokens.FONT_SM),
            on_click=lambda _e: ask_run(page, methods, cname),
        ),
        ft.PopupMenuItem(content=ft.Divider(height=1)),
        ft.PopupMenuItem(
            icon=ft.Icons.RESTART_ALT_ROUNDED,
            content=ft.Text("Reset", size=tokens.FONT_SM, color=theme.warn()),
            on_click=lambda _e: ask_reset(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.DELETE_FOREVER_ROUNDED,
            content=ft.Text("Remove", size=tokens.FONT_SM, color=theme.warn()),
            on_click=lambda _e: ask_remove(page, methods, cname),
        ),
    ]
