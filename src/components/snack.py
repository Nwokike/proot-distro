"""Snack bars that can never strand the screen or render unreadable.

Uses floating SnackBar overlay pattern matching CollabShell / KTV Player standard:
appended directly to page.overlay so it never competes with or corrupts the
page._dialogs modal stack.
"""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens

logger = logging.getLogger(__name__)


def show_snack(page: ft.Page | None, message: str) -> None:
    """Show a readable floating SnackBar on page.overlay."""
    if not message or page is None:
        return
    try:
        snack = ft.SnackBar(
            content=ft.Text(message, color=theme.WHITE, size=tokens.FONT_SM),
            bgcolor=theme.surface_alt(),
            behavior=ft.SnackBarBehavior.FLOATING,
            show_close_icon=True,
            dismiss_direction=ft.DismissDirection.HORIZONTAL,
            duration=3000,
            open=True,
        )
        page.overlay.append(snack)
        page.update()
    except Exception as ex:
        logger.warning("Failed to show floating snack: %s", ex)
