"""Run one file in place: editable command and a live OUTPUT panel.

Split out of operations.py (file-size rule). This is the CollabShell cell the
display sheet uses, wired to `command_capture` instead of a window: the file's
own folder is the working directory, output streams as it arrives, and Stop
kills the PTY session. Nothing is opened in the terminal, so the folder and the
file stay the context of the run (device feedback 2026-11-17: "run in terminal"
ran `./file` from /root and missed the file).
"""

from __future__ import annotations

import asyncio

import flet as ft

from components.command_cell import build_command_cell
from core import theme, tokens
from services import session_service


def open_file_run_dialog(page: ft.Page, container: str, folder: str, command: str) -> None:
    holder: dict = {"session": None}
    cells: dict = {}

    def _append(text: str) -> None:
        ctrl = cells.get("ctrl")
        if ctrl is not None and text.strip():
            ctrl.append_output(text)

    def _run(ctrl) -> None:
        cmd = (ctrl.source() or "").strip()
        if not cmd:
            return
        ctrl.set_running(True)
        ctrl.clear_output()

        async def _job() -> None:
            def _on_chunk(data: bytes) -> None:
                # Worker thread: the widget write goes through the page loop.
                page.run_task(_append, data.decode("utf-8", "replace"))

            def _on_start(session) -> None:
                holder["session"] = session

            try:
                result = await asyncio.to_thread(
                    session_service.command_capture,
                    container,
                    ["/bin/sh", "-lc", cmd],
                    folder,
                    None,  # an interactive program must not time out
                    _on_chunk,
                    _on_start,
                )
            except Exception as exc:
                _append(f"run failed: {exc}")
                result = None
            holder["session"] = None
            ctrl.set_running(False)
            if result is not None:
                ctrl.append_output(f"[exit {result.get('returncode')}]")

        page.run_task(_job)

    def _stop() -> None:
        session = holder.get("session")
        if session is not None:
            session.stop()

    cell, ctrl = build_command_cell(
        page,
        source=command,
        hint="command to run in this folder",
        on_run=_run,
        on_stop=_stop,
        label="Run file",
        run_on_top=True,  # the keyboard must never hide the Run control
    )
    cells["ctrl"] = ctrl
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Run in {container}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Working dir: {folder}",
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                    ),
                    cell,
                ],
                spacing=tokens.SPACE_XS,
                tight=True,
                width=tokens.DIALOG_WIDTH_LG,
            ),
            actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
        )
    )
