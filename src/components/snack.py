"""Snack bars that can never strand the screen or render unreadable.

Two traps from the house audits (CollabShell notifications.py + DDGS
core/snack.py): a SnackBar without an explicit bgcolor falls back to the
theme's inverseSurface while its text stays ON_SURFACE — black-on-black in
light mode; and a bar whose client dismissal timer never fires sits in the
dialog stack swallowing every tap. This helper fixes both: explicit
surface colors, FLOATING behavior (the app has a NavigationBar), and a
local backstop that closes the bar whatever the client does.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme, tokens

logger = logging.getLogger(__name__)

# A little longer than flet's own 4 s default so the client normally wins.
_BACKSTOP_S = 5.0


def show_snack(page: ft.Page, message: str) -> None:
    """Show a readable, self-dismissing SnackBar."""
    if message == "" or page is None:
        return
    snack = ft.SnackBar(
        content=ft.Text(message, color=theme.text(), size=tokens.FONT_SM),
        bgcolor=theme.surface_alt(),
        behavior=ft.SnackBarBehavior.FLOATING,
        show_close_icon=True,
    )
    try:
        page.show_dialog(snack)
    except RuntimeError:
        return  # already open (double tap): nothing to do

    async def _backstop() -> None:
        try:
            await asyncio.sleep(_BACKSTOP_S)
        except asyncio.CancelledError:
            return
        try:
            if not snack.open:
                return  # the client dismissed it on time — normal path
            snack.open = False
            snack.update()
        except Exception:
            logger.debug("snack backstop could not close the bar", exc_info=True)

    try:
        page.run_task(_backstop)
    except Exception:
        # No task runner: the client-side duration is all we have.
        logger.debug("no task runner for the snack backstop", exc_info=True)
