"""Desktop-support provisioning and its notification."""

from __future__ import annotations

import asyncio
import logging

from core.constants import (
    NOTIFICATION_CHANNEL_INSTALLS,
    NOTIFICATION_CHANNEL_INSTALLS_NAME,
    NOTIFICATION_ID_INSTALL,
)
from core.state import state
from services import desk_service, proot_service

from ._common import _reason

logger = logging.getLogger(__name__)


class DisplayInstallMixin:
    async def _notify_install(self, title: str, body: str, *, ongoing: bool = False) -> None:
        """Local notification for desktop-install start/finish/fail. The start
        shows an indeterminate progress bar and never re-alerts; the finish
        replaces it (same id) without progress."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        try:
            import flet_notifications as ftn

            options = ftn.AndroidOptions(
                channel=self._install_channel(),
                progress=ftn.AndroidProgress(indeterminate=True) if ongoing else None,
                only_alert_once=ongoing,
                auto_cancel=not ongoing,
            )
            await self._ensure_notification_permission()
            await notifications.show(
                id=NOTIFICATION_ID_INSTALL, title=title, body=body, options=options
            )
        except Exception as exc:
            logger.debug("install notification failed: %s", exc)

    async def install_display_support(
        self, container: str, desktop_env: str = "xfce", script_text: str | None = None
    ) -> None:
        """Install desktop support, streaming live into TWO surfaces — the
        notebook-style command cell on the launcher sheet
        (`page._display_install_cell`) and the reactive progress card on the
        Display tab (`state.display_progress`, the CollabShell NotebookCell
        mechanism: a small observable model passed as the component argument).

        `script_text` (the possibly-EDITED cell source) runs verbatim via
        `login -- /bin/sh -lc <script>` with NO timeout; without it the canned
        per-distro script runs."""
        from core.state import display_progress

        await self.ad_service.show_interstitial()
        state.display_error = ""
        display_progress.clear(container)
        display_progress.set_running(True)
        self.show_snack(f"installing desktop in {container}…")
        await self._notify_install(
            "Installing desktop",
            f"{container}: installing desktop support…",
            ongoing=True,
        )
        cell = getattr(self.page, "_display_install_cell", None)
        if cell is not None:
            cell.set_running(True)
            cell.clear_output()
        await self.probe_display(container)
        caps = self._display_caps(container)

        def _on_chunk(data: bytes) -> None:
            text = data.decode("utf-8", "replace")
            if not text:
                return

            async def _apply(t: str = text) -> None:
                # Runs inside page.run_task: run_task sets ft.context's page
                # var in the calling thread and the loop task inherits that
                # context, so the observable notify schedules the card update.
                display_progress.append(t)
                if cell is not None:
                    cell.append_output(t)

            self.page.run_task(_apply)

        try:
            if script_text:
                from services import session_service

                result = await asyncio.to_thread(
                    session_service.command_capture,
                    container,
                    ["/bin/sh", "-lc", script_text],
                    None,
                    None,  # timeout=None — an install must never be killed
                    on_chunk=_on_chunk,
                    # The Stop button kills this PTY session (edit honoree runs verbatim).
                    on_start=lambda s: setattr(self, "_install_session", s),
                )
            else:
                result = await desk_service.install(
                    container, caps, desktop_env, on_chunk=_on_chunk
                )
        except Exception as exc:
            self._install_session = None
            state.display_error = _reason(exc)
            display_progress.set_running(False)
            display_progress.append(f"install failed: {_reason(exc)}")
            await self._notify_install("Install failed", f"{container}: {_reason(exc)}")
            if cell is not None:
                cell.set_running(False)
                cell.append_output(f"install failed: {_reason(exc)}")
            logger.exception("display install failed for %s", container)
            return
        self._install_session = None
        display_progress.finish(bool(result.get("ok")))
        if cell is not None:
            cell.set_running(False)
        if result.get("ok"):
            self.show_snack(f"desktop installed in {container}")
            await self._notify_install(
                "Desktop installed", f"{container}: open it from the Display tab"
            )
            # Re-probe without the cache guard: the container changed on disk.
            try:
                caps = await asyncio.to_thread(proot_service.guest_capabilities, container)
                # REASSIGN the whole dict: nested item assignment on the
                # observable does not notify, so card labels would keep saying
                # "Install display support" after it is installed.
                state.display_support = {**(state.display_support or {}), container: caps}
            except Exception as exc:
                logger.warning("display re-probe failed for %s: %s", container, exc)
            # Repaint the launcher sheet (if still open) into its ready state.
            try:
                from screens.display_launcher import rebuild_display_sheet

                rebuild_display_sheet(self.page, container)
            except Exception:
                pass
        else:
            state.display_error = f"install exited {result.get('returncode')}, see the log tail"
            self.show_snack(f"display install failed in {container}")
            if cell is not None:
                cell.append_output(state.display_error)

    # ── diagnostics ───────────────────────────────────────────────────────────

    @staticmethod
    def _install_channel():
        """Its own channel: users can silence installs without touching the
        session-alive notification (Android groups them independently)."""
        try:
            import flet_notifications as ftn

            return ftn.NotificationChannel(
                id=NOTIFICATION_CHANNEL_INSTALLS,
                name=NOTIFICATION_CHANNEL_INSTALLS_NAME,
            )
        except Exception:
            return None
