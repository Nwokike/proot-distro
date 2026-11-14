"""Session listing, kills and the one-tap X display."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme

from ._common import _reason

logger = logging.getLogger(__name__)


class SessionListingMixin:
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
        await self.ad_service.show_interstitial()
        outcome = await asyncio.to_thread(self.proot.kill_session, None, True, signal)
        self.show_snack(
            "stopped all sessions" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def kill_session(self, pid: str, signal: str | None = None) -> None:
        await self.ad_service.show_interstitial()
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
        await self.ad_service.show_interstitial()
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
