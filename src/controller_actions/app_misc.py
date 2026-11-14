"""App-level actions split out of AppController (theme, credentials, updates,
lifecycle, page-error routing, ads privacy)."""

from __future__ import annotations

import json
import logging
import os
import time

import flet as ft

from core import theme
from core.state import state

logger = logging.getLogger(__name__)


_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}
# The ONE theme cycle definition (house order: Light → Dark → System); the
# header button and the Settings row both call it so they cannot diverge.
_THEME_ORDER = ("light", "dark", "system")


class AppMiscMixin:
    async def on_lifecycle(self, e) -> None:
        """Pause → drop the wakelock + persist settings; resume → wakelock back
        iff work is visible. The FGS keeps the processes alive either way."""
        name = getattr(getattr(e, "state", None), "value", "")
        if name in ("hide", "pause", "detach"):
            self._wakelock(False)
            await self._persist_display_settings()
            return
        if name in ("resume", "show"):
            has_work = bool(state.active_display) or bool(self.session_manager.entries)
            if has_work:
                self._wakelock(True)
            await self._update_fgs()

    async def _persist_display_settings(self) -> None:
        prefs = getattr(self, "prefs", None)
        if prefs is None:
            return
        try:
            await prefs.set("display_settings", json.dumps(self._display_settings()))
        except Exception as exc:
            logger.debug("display settings persist failed: %s", exc)

    async def on_media_change(self, _e=None) -> None:
        """Track orientation + the keyboard inset (PageMediaData). The terminal
        and launcher read these instead of inferring from resize events."""
        media = getattr(self.page, "media", None)
        if media is None:
            return
        orientation = getattr(media, "orientation", None)
        state.device_orientation = str(getattr(orientation, "value", orientation) or "portrait")
        insets = getattr(media, "view_insets", None)
        state.keyboard_inset = float(getattr(insets, "bottom", 0) or 0)

    async def on_keyboard_event(self, e) -> None:
        """Hardware-keyboard shortcuts (tablets/Chromebooks): Ctrl+Alt+T opens a
        shell, Ctrl+Alt+C copies the selection. Soft keyboards never send them."""
        key = (getattr(e, "key", "") or "").lower()
        if not (getattr(e, "ctrl", False) and getattr(e, "alt", False)):
            return
        if key == "t":
            entry = self.session_manager.entries.get(state.active_session or "")
            if entry is not None:
                await self.open_session(entry.container)
        elif key == "c":
            entry = self.session_manager.entries.get(state.active_session or "")
            if entry is not None and entry.mt is not None:
                from screens.terminal.wiring import copy_selection

                await copy_selection(self.page, entry.mt)

    async def on_page_error(self, e) -> None:
        """Unhandled page errors are logged and shown, never silent."""
        detail = str(getattr(e, "data", "") or e)
        logger.error("page error: %s", detail)
        self.show_snack(f"internal error: {detail[:120]}")

    def _on_connectivity(self, e) -> None:
        from core.state import _is_online

        state.online = _is_online(getattr(e, "connectivity", None))

    # ── actions (state-only mutations) ────────────────────────────────────────

    async def _apply_battery_defaults(self) -> None:
        """First launch on a battery-saver device: lighter display defaults.
        Saved settings always win — this only tunes values still at factory."""
        battery = getattr(self.page, "battery", None)
        if battery is None:
            return
        try:
            if not await battery.is_in_battery_save_mode():
                return
        except Exception as exc:
            logger.debug("battery save-mode probe failed: %s", exc)
            return
        from core.state import DEFAULT_DISPLAY_SETTINGS

        for key, tuned in (("fps", 15), ("quality", 60), ("compression", 4)):
            if state.display_settings.get(key) == DEFAULT_DISPLAY_SETTINGS[key]:
                state.display_settings[key] = tuned
        logger.info("battery saver detected — display defaults lowered")

    async def _warn_low_battery(self) -> None:
        """A big install on a nearly-flat battery is a support ticket waiting
        to happen — warn, never block."""
        battery = getattr(self.page, "battery", None)
        if battery is None:
            return
        try:
            level = await battery.get_battery_level()
        except Exception as exc:
            logger.debug("battery level probe failed: %s", exc)
            return
        if isinstance(level, int) and level < 20:
            self.show_snack(f"battery at {level}% — keep the app open during the install")

    async def set_docker_token(self, token: str) -> None:
        """Docker Hub credentials — upstream's PD_DOCKER_AUTH needs
        `username:password` (username:PAT), NOT a bare PAT: a malformed value
        breaks even anonymous pulls (device audit 2026-11-14)."""
        token = token.strip()
        if token and ":" not in token:
            self.show_snack(
                "Docker credentials need the form username:token — a bare token breaks pulls"
            )
            return
        state.docker_token = token
        if token:
            os.environ["PD_DOCKER_AUTH"] = token
        else:
            os.environ.pop("PD_DOCKER_AUTH", None)
        if self.prefs is not None:
            await self.prefs.set("docker_token", token)
        self.show_snack(
            "Docker Hub credentials saved" if token else "Docker Hub credentials cleared"
        )

    async def set_theme_mode(self, mode: str) -> None:
        if mode not in _THEME_MODES:
            return
        state.theme_mode = mode
        state.theme_revision += 1
        theme.apply_theme_mode(self.page, mode)
        if self.prefs is not None:
            await self.prefs.set("theme_mode", mode)

    async def cycle_theme_mode(self) -> None:
        current = state.theme_mode if state.theme_mode in _THEME_ORDER else "system"
        await self.set_theme_mode(
            _THEME_ORDER[(_THEME_ORDER.index(current) + 1) % len(_THEME_ORDER)]
        )

    async def _check_for_updates(self) -> None:
        """Silent background check; a newer build flips the header chip.

        Throttled across runs: one small TLS request per 6 h, not per reopen."""
        from services.update_service import check_for_update

        if self.prefs is not None:
            try:
                last = await self.prefs.get("update_checked_at")
                if last is not None and time.time() - float(last) < self._UPDATE_CHECK_INTERVAL:
                    return
            except TypeError, ValueError:
                pass
        try:
            data = await check_for_update()
        except Exception:
            logger.exception("Startup update check failed")
            raise
        if self.prefs is not None:
            try:
                await self.prefs.set("update_checked_at", str(time.time()))
            except Exception as exc:
                logger.debug("update throttle write failed: %s", exc)
        if not data:
            return
        state.update_available = True
        state.update_data = data

    async def show_privacy_options(self) -> None:
        outcome = await self.ad_service.show_privacy_options()
        if outcome == "form_shown":
            self.show_snack("Privacy options updated")
        elif outcome == "not_required":
            self.show_snack("Privacy options are not required in your region")
        elif outcome == "no_manager":
            self.show_snack("Privacy options are unavailable in this build")
        else:
            self.show_snack(f"Privacy options failed: {outcome}")

    # ── container actions ─────────────────────────────────────────────────────

    # ── sessions ──────────────────────────────────────────────────────────────

    async def _on_notification_action(self, e) -> None:
        """Notification action buttons — the FGS notification's Exit tears down."""
        if getattr(e, "action_id", "") == "exit":
            self.page.run_task(self.exit_app)

    def _on_notification_tap(self, e) -> None:
        """Tapping the persistent notification returns to the running work —
        the open display if there is one, else the running shell."""
        if state.active_display:
            return
        entries = list(self.session_manager.entries.values())
        if entries and not state.active_session:
            state.active_session = entries[-1].key

    # ── lifecycle ─────────────────────────────────────────────────────────────
