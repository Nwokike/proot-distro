"""Terminal session actions: list, kill, open/leave/close, one-shot run."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme
from core.constants import APP_NAME
from core.state import state

from ._common import _reason

logger = logging.getLogger(__name__)


class SessionActions:
    async def _ensure_notification_permission(self) -> bool:
        """Request POST_NOTIFICATIONS (Android 13+) before starting the FGS.
        Returns True when notifications are available."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return False
        try:
            granted = await notifications.request_permissions()
            if not granted:
                logger.warning("Notification permission denied by user")
            return granted
        except Exception as exc:
            logger.debug("Notification permission request failed: %s", exc)
            return False

    async def _start_fgs(self, label: str) -> None:
        """Start the Termux-style foreground service notification (keeps the
        app alive in the background while Linux sessions run). `label` is the
        notification body line, e.g. "Desktop running: debian"."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        try:
            from flet_notifications import (
                AndroidForegroundServiceType,
                AndroidServiceStartType,
                NotificationAction,
            )

            await self._ensure_notification_permission()
            await notifications.start_foreground_service(
                id=1,
                title=APP_NAME,
                body=label,
                start_type=AndroidServiceStartType.STICKY,
                service_types=[AndroidForegroundServiceType.SPECIAL_USE],
                # Termux-style: the persistent notification carries an Exit
                # action that tears down sessions + FGS and closes the app.
                actions=[NotificationAction(id="exit", title="Exit")],
            )
            logger.info("FGS started (%s)", label)
        except Exception as exc:
            logger.warning("FGS start failed: %s", exc)

    async def _update_fgs(self) -> None:
        """Ref-count the foreground service: it runs while ANY shell or display
        session is alive and stops only when both are gone. Closing one shell
        must not kill the background service while a display (or another shell)
        runs."""
        shells = list(getattr(self.session_manager, "entries", {}) or {})
        desktops = []
        manager = getattr(self, "desk_manager", None)
        if manager is not None:
            desktops = manager.running()
        if desktops:
            await self._start_fgs(f"Display running: {desktops[0].container}")
        elif shells:
            await self._start_fgs(f"Linux session running: {sorted(shells)[0]}")
        else:
            await self._stop_fgs()

    async def _stop_fgs(self) -> None:
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        try:
            await notifications.stop_foreground_service()
            logger.info("FGS stopped")
        except Exception as exc:
            logger.debug("FGS stop failed: %s", exc)

    async def list_sessions(self) -> None:
        rows = await asyncio.to_thread(self.proot.active_sessions)
        if not rows:
            self.show_snack("no running sessions")
            return
        from core import tokens

        signal_dropdown = ft.Dropdown(
            label="Signal",
            value="TERM",
            options=[
                ft.dropdown.Option("TERM"),
                ft.dropdown.Option("INT"),
                ft.dropdown.Option("HUP"),
                ft.dropdown.Option("QUIT"),
                ft.dropdown.Option("KILL"),
            ],
            width=tokens.DIALOG_SIGNAL_WIDTH,
        )

        def _close_dlg(_e=None):
            self.page.pop_dialog()

        def _kill(pid):
            _close_dlg()
            self.page.run_task(self.kill_session, str(pid), signal_dropdown.value or None)

        def _kill_all(_e):
            _close_dlg()
            self.page.run_task(self.kill_all_sessions, signal_dropdown.value or None)

        items = []
        for r in rows:
            pid_val = str(r.get("pid", ""))
            items.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.primary()),
                    title=ft.Text(
                        f"{r.get('container')} (PID {r.get('pid')})",
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.W_600,
                    ),
                    subtitle=ft.Text(
                        f"user: {r.get('user')} · cmd: {r.get('command')}",
                        size=tokens.FONT_XS,
                    ),
                    trailing=ft.IconButton(
                        icon=ft.Icons.STOP_CIRCLE_ROUNDED,
                        icon_color=theme.warn(),
                        tooltip="Stop session",
                        on_click=lambda _e, p=pid_val: _kill(p),
                    ),
                )
            )

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Active Sessions",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=[signal_dropdown, *items],
                    spacing=tokens.SPACE_XS,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[
                    ft.TextButton("Stop All", on_click=_kill_all),
                    ft.TextButton("Close", on_click=_close_dlg),
                ],
            )
        )

    async def kill_all_sessions(self, signal: str | None = None) -> None:
        outcome = await asyncio.to_thread(self.proot.kill_session, "", True, signal)
        self.show_snack(
            "stopped all sessions" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def kill_session(self, pid: str, signal: str | None = None) -> None:
        outcome = await asyncio.to_thread(self.proot.kill_session, str(pid), False, signal)
        self.show_snack(
            f"stopped session {pid}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def open_session(self, container: str) -> None:
        """Open a NEW shell on the container (multi-shell; no ad on open)."""
        state.session_error = ""
        # If an image ref was passed instead of a container name (e.g.
        # 'archlinux/archlinux'), resolve it to the actual installed container.
        if "/" in container:
            containers = await asyncio.to_thread(self.proot.list_containers)
            match = next(
                (c["name"] for c in containers if c.get("image") == container),
                container.rsplit("/", 1)[-1],
            )
            container = match
        try:
            entry = await self.session_manager.open(container)
        except Exception as exc:
            state.session_error = f"could not open {container}: {_reason(exc)}"
            self.show_snack(state.session_error)
            logger.exception("Could not open shell for %s", container)
            raise
        state.active_session = entry.key
        await self._update_fgs()
        # Interstitial at the natural break of opening a shell (allowed by
        # AdMob placement rules — terminal-adjacent breaks only, never mid-type).
        await self.ad_service.show_interstitial()

    async def open_session_with_options(self, container: str, opts: dict) -> None:
        """Open a NEW shell with the upstream login options (100% proot-distro
        wrap: user, work-dir, env, bind, shared tmp/home, fix-low-ports,
        isolated). Same flow as open_session otherwise."""
        state.session_error = ""
        try:
            entry = await self.session_manager.open(container, options=opts)
        except Exception as exc:
            state.session_error = f"could not open {container}: {_reason(exc)}"
            self.show_snack(state.session_error)
            logger.exception("Could not open shell (options) for %s", container)
            raise
        state.active_session = entry.key
        await self._update_fgs()
        await self.ad_service.show_interstitial()

    async def leave_session(self) -> None:
        state.active_session = None
        await self.ad_service.show_interstitial()

    async def close_session(self, session_key: str) -> None:
        await asyncio.to_thread(self.session_manager.close, session_key)
        if state.active_session == session_key:
            state.active_session = None
        await self._update_fgs()  # stops only when no shells AND no displays remain
        await self.ad_service.show_interstitial()

    async def exit_app(self) -> None:
        """Kill all sessions and displays, stop the foreground service, exit."""
        manager = getattr(self, "desk_manager", None)
        if manager is not None:
            await manager.stop_all()
        await asyncio.to_thread(self.session_manager.close_all)
        await self._stop_fgs()
        # Android: finish the activity directly.
        try:
            from jnius import autoclass

            autoclass("android.os.Process").killProcess(autoclass("android.os.Process").myPid())
        except Exception:
            import os

            os._exit(0)

    async def run_container(self, container: str, args_text: str) -> None:
        """`proot-distro run` — Entrypoint/Cmd plus the args, on a PTY, captured live."""
        from core import tokens as _t
        from services import session_service

        run_args = [a for a in args_text.split() if a]
        state.run_busy = container
        state.run_status = "starting…"
        state.run_output = ""
        state.run_returncode = None
        loop = self.page.loop

        def _apply(chunk: str) -> None:
            if chunk:
                state.run_output += chunk
            col = getattr(self.page, "_run_output_column", None)
            if col is not None:
                col.controls = [
                    ft.Text(
                        state.run_output[-4000:],
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
                session_service.run_capture, container, run_args, None, on_chunk=_on_chunk
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
        state.run_returncode = result.get("returncode")
        _apply("")
        state.run_busy = None
