"""Session listing, kills and the one-tap X display."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme
from core.state import state

from ._common import _reason

logger = logging.getLogger(__name__)


class SessionListingMixin:
    async def list_sessions(self) -> None:
        try:
            rows = await asyncio.to_thread(self.proot.active_sessions)
        except Exception as exc:
            self.show_snack(f"could not list sessions: {_reason(exc)}")
            return
        state.running_sessions = list(rows or [])
        if not rows:
            self.show_snack("no running sessions")
            return
        from components.ui import pill_dropdown
        from core import tokens

        signal = {"value": "TERM"}
        signal_pill = pill_dropdown(
            "Signal",
            ft.Icons.BOLT_ROUNDED,
            [
                "TERM",
                "INT",
                "HUP",
                "QUIT",
                "KILL",
                "USR1",
                "USR2",
                "STOP",
                "CONT",
                "ALRM",
            ],
            "TERM",
            lambda value: signal.update(value=value),
            tooltip="Signal sent by Stop and Stop all",
        )
        # Upstream accepts any signal name/number — a free-text field keeps the
        # full surface reachable (e.g. numeric 9 or a rare name).
        from components.ui import house_field

        signal_custom = house_field(
            label="Or a custom signal",
            hint="name or number, e.g. 9 or USR1",
            width=tokens.DIALOG_SIGNAL_WIDTH,
            text_size=tokens.FONT_XS,
            height=tokens.CONTROL_SM,
        )

        def _signal() -> str | None:
            custom = (signal_custom.value or "").strip()
            return custom or signal["value"] or None

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
                    leading=ft.Container(
                        content=ft.Icon(
                            ft.Icons.TERMINAL_ROUNDED,
                            size=tokens.ICON_SM,
                            color=theme.ok(),
                        ),
                        width=tokens.CONTROL_INPUT,
                        height=tokens.CONTROL_INPUT,
                        border_radius=tokens.RADIUS_PILL,
                        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.ok()),
                        alignment=ft.Alignment.CENTER,
                    ),
                    title=ft.Text(
                        f"{r.get('container')} · PID {r.get('pid')}",
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.W_600,
                    ),
                    subtitle=ft.Text(
                        f"{r.get('user')} · {r.get('command')}",
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                    ),
                    trailing=ft.IconButton(
                        icon=ft.Icons.STOP_CIRCLE_ROUNDED,
                        icon_color=theme.warn(),
                        tooltip="Stop this session",
                        on_click=lambda _e, p=pid_val: _kill(p),
                    ),
                )
            )

        self.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Running processes",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"{len(rows)} guest process(es), signal:",
                                    size=tokens.FONT_XS,
                                    color=theme.text_dim(),
                                ),
                                signal_pill,
                            ],
                            spacing=tokens.SPACE_XS,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        signal_custom,
                        ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
                        *items,
                    ],
                    spacing=tokens.SPACE_XS,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[
                    ft.TextButton("Stop all", on_click=_kill_all),
                    ft.TextButton("Close", on_click=_close_dlg),
                ],
            )
        )

    async def kill_all_sessions(self, signal: str | None = None) -> None:
        await self.ad_service.show_interstitial()
        outcome = await asyncio.to_thread(self.proot.kill_session, None, True, signal)
        state.running_sessions = None
        self.show_snack(
            "stopped all sessions" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def kill_session(self, pid: str, signal: str | None = None) -> None:
        await self.ad_service.show_interstitial()
        outcome = await asyncio.to_thread(self.proot.kill_session, str(pid), False, signal)
        state.running_sessions = None
        self.show_snack(
            f"stopped session {pid}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def start_x_display(self, key: str) -> None:
        """Start a bare X display for this shell's container and inject its
        environment INTO THE LIVE SHELL — GUI apps then just run here
        (`firefox` with no tab switch; device 2026-11-14: shells had no
        DISPLAY). The display also appears on the Display tab for the viewer."""

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
            # Source the file the manager already wrote (quoting-proof and
            # idempotent); Ctrl-U clears anything half-typed at the prompt so
            # the line is executed instead of being appended to user input.
            from core.constants import GUEST_X11_DIR

            try:
                entry.session.write(f"\x15. {GUEST_X11_DIR}/env\n".encode())
            except Exception as exc:
                logger.debug("could not inject the display env into the shell: %s", exc)
        self.show_snack(f"X display :{session.display} attached to this shell")
