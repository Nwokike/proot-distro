"""The display log dialog."""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens

from .display_common import _tail_file_lines

logger = logging.getLogger(__name__)


class DisplayLogsMixin:
    async def show_display_logs(self, key: str) -> None:
        session = self.desk_manager.get(key)
        if session is not None:
            lines = list(session.log_tail)
        else:
            # The session object is gone (cold reopen): the durable log file
            # is the only surviving evidence (data root — clear-cache can't
            # touch it).
            from core import storage_paths

            path = storage_paths.data_root() / "display-logs" / f"{key}.log"
            lines = _tail_file_lines(path, tokens.DISPLAY_LOG_TAIL_BYTES)
        tail = "\n".join(lines[-tokens.DISPLAY_LOG_TAIL_LINES :]) or "(no logs yet)"
        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Display logs — {key}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=ft.Container(
                    content=ft.Text(
                        tail,
                        font_family=tokens.MONO_FONT,
                        size=tokens.FONT_XXS,
                        color=theme.text_dim(),
                        selectable=True,
                    ),
                    width=tokens.DIALOG_WIDTH_LG,
                    height=320,
                ),
                actions=[ft.TextButton("Close", on_click=lambda _e: self.page.pop_dialog())],
            )
        )
