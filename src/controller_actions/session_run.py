"""`proot-distro run` with captured output."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme, tokens
from core.state import state

from ._common import _reason

logger = logging.getLogger(__name__)


class SessionRunMixin:
    async def run_container(
        self, container: str, args_text: str, options: dict | None = None
    ) -> None:
        """`proot-distro run` — Entrypoint/Cmd plus the args, on a PTY, captured live."""
        import shlex

        from core import tokens as _t
        from services import session_service

        try:
            run_args = shlex.split(args_text)
        except ValueError as exc:
            state.run_status = f"could not parse args: {exc}"
            state.run_output = ""
            state.run_busy = None
            self.show_snack(f"bad args syntax: {exc}")
            return
        # Visible "starting" state BEFORE the ad, so the action never looks
        # dead while the interstitial loads.
        state.run_busy = container
        state.run_status = "starting…"
        state.run_output = ""
        await self.ad_service.show_interstitial()
        loop = self.page.loop

        def _apply(chunk: str) -> None:
            if chunk:
                state.run_output += chunk
            col = getattr(self.page, "_run_output_column", None)
            if col is not None:
                col.controls = [
                    ft.Text(
                        state.run_output[-tokens.RUN_OUTPUT_TAIL_CHARS :],
                        font_family=_t.MONO_FONT,
                        size=_t.FONT_XXS,
                        color=theme.text_dim(),
                        selectable=True,
                    )
                ]
                col.update()
            stage_ctrl = getattr(self.page, "_run_stage_text", None)
            if stage_ctrl is not None:
                stage_ctrl.value = state.run_status
                stage_ctrl.update()
            dialog = getattr(self.page, "_run_dialog", None)
            if dialog is not None and dialog.open:
                dialog.update()

        def _on_chunk(data: bytes) -> None:
            loop.call_soon_threadsafe(_apply, data.decode("utf-8", "replace"))

        try:
            result = await asyncio.to_thread(
                session_service.run_capture,
                container,
                run_args,
                None,
                on_chunk=_on_chunk,
                options=options,
            )
        except Exception as exc:
            state.run_status = f"run failed: {_reason(exc)}"
            state.run_output = ""
            logger.exception("run failed in %s", container)
            _apply("")
            state.run_busy = None
            raise
        state.run_status = f"exit {result['returncode']}" + (
            " (timeout)" if result.get("timed_out") else ""
        )
        state.run_output = result.get("output", "")
        _apply("")
        state.run_busy = None
