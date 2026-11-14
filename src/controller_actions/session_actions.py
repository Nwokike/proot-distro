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
        notification body line, e.g. "Desktop running: debian". Re-issued only
        when the label actually changes — every manager transition used to
        re-post the notification (device audit 2026-11-13: start/stop churn
        on every shell open/close)."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        active = getattr(self, "_fgs_active", None)
        if active is True and getattr(self, "_fgs_label", "") == label:
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
            self._fgs_active = True
            self._fgs_label = label
            logger.info("FGS started (%s)", label)
        except Exception as exc:
            logger.warning("FGS start failed: %s", exc)

    async def _update_fgs(self) -> None:
        """Ref-count the foreground service: it runs while ANY shell or
        display session is alive and stops only when both are gone. Closing
        one shell must not kill the background service while a display (or
        another shell) runs. STARTING and STOPPING sessions count too — a
        display takes up to 60s to come up, and backgrounding during that
        window used to kill the process and the start with it (device audit
        2026-11-13)."""
        shells = list(getattr(self.session_manager, "entries", {}) or {})
        displays = []
        manager = getattr(self, "desk_manager", None)
        if manager is not None:
            displays = manager.starting() + manager.visible()
        if displays:
            names = ", ".join(sorted(s.key for s in displays))
            label = (
                f"Display running: {names}"
                if len(displays) == 1
                else f"{len(displays)} displays running: {names}"
            )
            await self._start_fgs(label)
        elif shells:
            names = ", ".join(sorted(shells))
            label = (
                f"Linux session running: {names}"
                if len(shells) == 1
                else f"{len(shells)} Linux sessions running: {names}"
            )
            await self._start_fgs(label)
        else:
            await self._stop_fgs()

    async def _stop_fgs(self) -> None:
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        # None = unknown (a fresh controller after a warm reopen — the
        # OS-level service can outlive the old page session): still attempt.
        if getattr(self, "_fgs_active", None) is False:
            return
        try:
            await notifications.stop_foreground_service()
            self._fgs_active = False
            self._fgs_label = ""
            logger.info("FGS stopped")
        except Exception as exc:
            logger.debug("FGS stop failed: %s", exc)

    async def list_sessions(self) -> None:
        try:
            rows = await asyncio.to_thread(self.proot.active_sessions)
        except Exception as exc:
            self.show_snack(f"could not list sessions: {_reason(exc)}")
            return
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
                ft.dropdown.Option("USR1"),
                ft.dropdown.Option("USR2"),
                ft.dropdown.Option("STOP"),
                ft.dropdown.Option("CONT"),
                ft.dropdown.Option("ALRM"),
            ],
            width=tokens.DIALOG_SIGNAL_WIDTH,
        )
        # Upstream accepts any signal name/number — a free-text field keeps the
        # full surface reachable (e.g. numeric 9 or a rare name).
        signal_custom = ft.TextField(
            label="Or a custom signal",
            hint_text="name or number, e.g. 9 or USR1",
            width=tokens.DIALOG_SIGNAL_WIDTH,
            text_size=tokens.FONT_XS,
            border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        )

        def _signal() -> str | None:
            custom = (signal_custom.value or "").strip()
            return custom or signal_dropdown.value or None

        def _close_dlg(_e=None):
            self.page.pop_dialog()

        def _kill(pid):
            sig = _signal()
            _close_dlg()
            self.page.run_task(self.kill_session, str(pid), sig)

        def _kill_all(_e):
            sig = _signal()
            _close_dlg()
            self.page.run_task(self.kill_all_sessions, sig)

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
        outcome = await asyncio.to_thread(self.proot.kill_session, None, True, signal)
        self.show_snack(
            "stopped all sessions" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def kill_session(self, pid: str, signal: str | None = None) -> None:
        outcome = await asyncio.to_thread(self.proot.kill_session, str(pid), False, signal)
        self.show_snack(
            f"stopped session {pid}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def start_x_display(self, key: str) -> None:
        """Start a bare X display for this shell's container and inject its
        environment INTO THE LIVE SHELL — GUI apps then just run here
        (`firefox` with no tab switch; device 2026-11-14: shells had no
        DISPLAY). The display also appears on the Display tab for the viewer."""
        import shlex as _shlex

        entries = getattr(self.session_manager, "entries", {}) or {}
        entry = entries.get(key)
        if entry is None or getattr(entry, "session", None) is None:
            self.show_snack("open a shell first")
            return
        manager = getattr(self, "desk_manager", None)
        if manager is None:
            return
        container = entry.container
        settings = self._display_settings()
        try:
            session = await manager.start(
                container,
                bare=True,
                frame_rate=int(settings.get("fps", 30) or 30),
                quality=int(settings.get("quality", 70)),
                compression=int(settings.get("compression", 2)),
                geometry=self._resolve_geometry(settings),
            )
        except Exception as exc:
            self.show_snack(f"X display failed: {_reason(exc)}")
            return
        env = manager.guest_display_env(container)
        if env:
            payload = "; ".join(f"export {k}={_shlex.quote(v)}" for k, v in env.items())
            try:
                entry.session.write((payload + "\n").encode())
            except Exception as exc:
                logger.debug("could not inject the display env into the shell: %s", exc)
        self.show_snack(f"X display :{session.display} attached to this shell")

    async def open_session(self, container: str) -> None:
        """Open a NEW shell on the container (multi-shell; no ad on open).
        In-flight guard: a double-tap must not open two shells."""
        opening = getattr(self, "_opening_sessions", None)
        if opening is None:
            opening = self._opening_sessions = set()
        if container in opening:
            self.show_snack(f"already opening a shell on {container}…")
            return
        opening.add(container)
        try:
            await self._open_session_impl(container)
        finally:
            opening.discard(container)

    def _display_env_for(self, container: str) -> dict[str, str]:
        """A running display's guest environment for a NEW shell — DISPLAY,
        XAUTHORITY and PULSE_SERVER — so GUI apps launched from any shell reach
        the display (device 2026-11-14: `firefox` → "no DISPLAY"). Empty when
        no display runs (plain shell), and never fatal on lookup errors."""
        manager = getattr(self, "desk_manager", None)
        if manager is None:
            return {}
        try:
            return manager.guest_display_env(container)
        except Exception as exc:
            logger.debug("display env lookup failed for %s: %s", container, exc)
            return {}

    def _shell_preflight(self, container: str) -> tuple[dict | None, str | None]:
        """Which shell the container can actually run, and whether it can run
        one at all.

        Distroless/scratch images ship no shell — login has nothing to exec, so
        the user got a generic "could not open". Images with /bin/sh but no
        bash failed the same way even though they are perfectly usable. Returns
        (login options override, honest error) — both None when bash is there.
        """
        from core import storage_paths

        rootfs = storage_paths.containers_dir() / container / "rootfs"
        if not rootfs.is_dir():
            return None, f"{container} has no rootfs on disk — reinstall it."
        if (rootfs / "bin" / "bash").exists() or (rootfs / "usr" / "bin" / "bash").exists():
            return None, None
        if (rootfs / "bin" / "sh").exists() or (rootfs / "usr" / "bin" / "sh").exists():
            return {"login_cmd": ["/bin/sh"]}, None
        return (
            None,
            f"{container} has no /bin/sh or /bin/bash — this image is distroless "
            "and cannot host a terminal. Use a distro image instead.",
        )

    async def _open_session_impl(self, container: str) -> None:
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
        shell_opts, shell_error = self._shell_preflight(container)
        if shell_error:
            state.session_error = shell_error
            self.show_snack(shell_error)
            return
        try:
            entry = await self.session_manager.open(
                container,
                options=shell_opts,
                extra_env=self._display_env_for(container),
            )
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
        shell_opts, shell_error = self._shell_preflight(container)
        if shell_error:
            state.session_error = shell_error
            self.show_snack(shell_error)
            return
        merged = {**(shell_opts or {}), **opts}  # user's own login_cmd wins
        try:
            entry = await self.session_manager.open(
                container, options=merged, extra_env=self._display_env_for(container)
            )
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
        import shlex

        from core import tokens as _t
        from services import session_service

        try:
            run_args = shlex.split(args_text)
        except ValueError as exc:
            state.run_status = f"could not parse args: {exc}"
            state.run_output = ""
            state.run_returncode = None
            state.run_busy = None
            self.show_snack(f"bad args syntax: {exc}")
            return
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
