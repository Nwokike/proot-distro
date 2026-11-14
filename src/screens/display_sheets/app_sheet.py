"""The launcher, new-display and app sheets."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme, tokens
from core.constants import APP_PRESETS
from core.state import state
from services import session_service

from .common import (
    _dialog_height,
    _sheet_width,
)

logger = logging.getLogger(__name__)


_CUSTOM = "__custom__"


def _show_launcher(page: ft.Page, methods, container: str, caps: dict) -> None:
    from .launcher_sheet import show_display_sheet  # deferred: avoids a cycle

    show_display_sheet(page, methods, container, caps)


def _show_app_sheet(page: ft.Page, methods, container: str) -> None:
    """Second-level sheet: probed guest apps + a custom command — each starts a
    SINGLE-APP display (bare Xvnc, no desktop) on the next free display number."""
    results = ft.Column(
        controls=[ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD)],
        spacing=tokens.SPACE_XS,
    )
    custom = ft.TextField(
        hint_text="custom command (e.g. python3 app.py)",
        height=tokens.CONTROL_SM,
        text_size=tokens.FONT_XS,
        expand=True,
    )

    def _start_app(cmd: str) -> None:
        if not cmd.strip():
            return
        page.pop_dialog()
        page.run_task(methods.start_display, container, None, cmd.strip(), None)

    async def _probe_one(label: str, cmd: str) -> tuple[str, str] | None:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    session_service.command_capture,
                    container,
                    ["/bin/sh", "-c", f"command -v {cmd}"],
                    # timeout=, NOT a positional: the 3rd arg is work_dir
                    timeout=10.0,
                ),
                timeout=12.0,
            )
        except Exception as exc:
            logger.debug("app probe for %s failed: %s", cmd, exc)
            return None
        if result.get("ok") and result.get("output", "").strip():
            return (label, cmd)
        return None

    async def _probe() -> None:
        # Probes run in PARALLEL — one slow probe must not serialize the sheet.
        probed = await asyncio.gather(*(_probe_one(label, cmd) for label, cmd in APP_PRESETS))
        found = [item for item in probed if item is not None]
        # Named variable, never a literal list assignment.
        rows = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                title=ft.Text(label, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                subtitle=ft.Text(
                    f"{cmd} — on its own display", size=tokens.FONT_XS, color=theme.text_dim()
                ),
                on_click=lambda _e, c=cmd: _start_app(c),
            )
            for label, cmd in found
        ]
        results.controls = rows or [
            ft.Text(
                "no preset apps found in this container — use the custom command",
                size=tokens.FONT_SM,
            )
        ]
        try:
            dlg.update()
        except Exception:
            pass

    dlg = ft.AlertDialog(
        title=ft.Text(f"Open an app — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[
                ft.Text(
                    "Each app gets its own X display (:N) and streams like a desktop:",
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                ),
                results,
                ft.Row(
                    controls=[
                        custom,
                        ft.FilledButton(
                            "Start", on_click=lambda _e: _start_app(custom.value or "")
                        ),
                    ]
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            width=_sheet_width(page),
            height=_dialog_height(page),
        ),
        actions=[
            ft.TextButton(
                "Back",
                on_click=lambda _e: (
                    page.pop_dialog(),
                    _show_launcher(
                        page, methods, container, (state.display_support or {}).get(container) or {}
                    ),
                ),
            ),
        ],
    )
    page.show_dialog(dlg)
    page.run_task(_probe)
