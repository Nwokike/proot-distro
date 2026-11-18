"""The display log dialog.

One dialog, two paths: copy the log, or copy it and open the GitHub issue
tracker. Reporting is the reason the log is kept durable in the first place
(device feedback 2026-11-17: "how do I report this?").
"""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.constants import GITHUB_ISSUES_URL
from core.shared_services import launch_url

from .display_common import _tail_file_lines

logger = logging.getLogger(__name__)


class DisplayLogsMixin:
    def _copy_text(self, text: str, note: str) -> None:
        async def _do() -> None:
            from components.snack import show_snack

            clipboard = getattr(self.page, "clipboard", None)
            if clipboard is None:
                return
            await clipboard.set(text)
            show_snack(self.page, note)

        self.page.run_task(_do)

    def _report(self, text: str) -> None:
        """Copy the log, then open the issue tracker to paste it."""

        async def _do() -> None:
            from components.snack import show_snack

            clipboard = getattr(self.page, "clipboard", None)
            if clipboard is not None:
                await clipboard.set(text)
            await launch_url(GITHUB_ISSUES_URL, self.page)
            show_snack(self.page, "Log copied. Paste it into the new GitHub issue")

        self.page.run_task(_do)

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
                    f"Display logs: {key}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
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
                actions=[
                    ft.TextButton(
                        "Copy log",
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        on_click=lambda _e: self._copy_text(tail, "display log copied"),
                    ),
                    ft.TextButton(
                        "Report on GitHub",
                        icon=ft.Icons.BUG_REPORT_ROUNDED,
                        on_click=lambda _e: self._report(tail),
                    ),
                    ft.TextButton("Close", on_click=lambda _e: self.page.pop_dialog()),
                ],
            )
        )
