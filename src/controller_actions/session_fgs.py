"""The foreground service + notification lifecycle."""

from __future__ import annotations

import logging

from core.constants import APP_NAME

logger = logging.getLogger(__name__)


class SessionFgsMixin:
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
                options=self._session_notification_options(),
            )
            self._fgs_active = True
            self._fgs_label = label
            logger.info("FGS started (%s)", label)
        except Exception as exc:
            logger.warning("FGS start failed: %s", exc)

    @staticmethod
    def _session_notification_options():
        """The session-alive notification belongs to a LOW-importance channel:
        it must never make a sound when the label changes."""
        try:
            import flet_notifications as ftn

            return ftn.AndroidOptions(
                channel=ftn.NotificationChannel(
                    id="sessions",
                    name="Sessions",
                    importance=ftn.AndroidImportance.LOW,
                ),
                silent=True,
                only_alert_once=True,
            )
        except Exception:
            return None

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

    async def open_notification_settings(self) -> None:
        """Honest settings entry: opens the system screen when notifications are
        off, otherwise reports that they are enabled."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        try:
            if await notifications.are_notifications_enabled():
                self.show_snack("notifications are enabled")
            else:
                await notifications.open_settings()
        except Exception as exc:
            logger.debug("notification settings unavailable: %s", exc)
