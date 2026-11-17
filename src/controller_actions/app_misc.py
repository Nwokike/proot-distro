"""App-level actions split out of AppController (theme, credentials, updates,
lifecycle, page-error routing, ads privacy)."""

from __future__ import annotations

import json
import logging
import os
import time

import flet as ft

from core import theme, tokens
from core.constants import (
    APP_NAME,
    BATTERY_SAVER_DISPLAY,
    LOW_BATTERY_PCT,
    NOTIFICATION_CHANNEL_GUEST,
    NOTIFICATION_CHANNEL_GUEST_NAME,
    NOTIFICATION_ID_GUEST_BASE,
    PREF_APP_PRESETS,
    PREF_DISPLAY_SETTINGS,
    PREF_DOCKER_TOKEN,
    PREF_ENV_DEFAULTS,
    PREF_TERMINAL_SETTINGS,
    PREF_THEME_MODE,
    PREF_UPDATE_CHECKED_AT,
    STORAGE_ONBOARDING_DONE,
)
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
            await prefs.set(PREF_DISPLAY_SETTINGS, json.dumps(self._display_settings()))
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
        self.show_snack(f"internal error: {detail[: tokens.SNACK_DETAIL_MAX_CHARS]}")

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

        for key, tuned in BATTERY_SAVER_DISPLAY.items():
            if state.display_settings.get(key) == DEFAULT_DISPLAY_SETTINGS[key]:
                state.display_settings[key] = tuned
        logger.info("battery saver detected, display defaults lowered")

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
        if isinstance(level, int) and level < LOW_BATTERY_PCT:
            self.show_snack(f"battery at {level}%, keep the app open during the install")

    async def set_docker_token(self, token: str) -> None:
        """Docker Hub credentials — upstream's PD_DOCKER_AUTH needs
        `username:password` (username:PAT), NOT a bare PAT: a malformed value
        breaks even anonymous pulls (device audit 2026-11-14)."""
        token = token.strip()
        if token and ":" not in token:
            self.show_snack(
                "Docker credentials need the form username:token. A bare token breaks pulls"
            )
            return
        state.docker_token = token
        if token:
            os.environ["PD_DOCKER_AUTH"] = token
        else:
            os.environ.pop("PD_DOCKER_AUTH", None)
        if self.prefs is not None:
            await self.prefs.set(PREF_DOCKER_TOKEN, token)
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
            await self.prefs.set(PREF_THEME_MODE, mode)

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
                last = await self.prefs.get(PREF_UPDATE_CHECKED_AT)
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
                await self.prefs.set(PREF_UPDATE_CHECKED_AT, str(time.time()))
            except Exception as exc:
                logger.debug("update throttle write failed: %s", exc)
        if not data:
            return
        state.update_available = True
        state.update_data = data

    async def open_developer_tools(self, open_: bool = True) -> None:
        """Settings shows the Build & push screen in place (a component can only
        be constructed during render, so it lives inside SettingsView)."""
        state.settings_section = "build" if open_ else ""

    async def open_settings_section(self, section: str = "") -> None:
        """Show the in-place Settings subscreen ("", "build").

        Display and environment no longer have subscreens: display defaults
        render inline and the environment is a dialog (owner ruling
        2026-11-15)."""
        state.settings_section = section if section in ("", "build") else ""

    async def save_env_defaults(self, env: dict | None = None) -> None:
        """Persist the guest-default environment the user edited.

        These keys are injected into every NEW shell (and therefore into apps
        launched from it); they are separate from the app's own runtime
        contract, which is read-only."""
        import re

        cleaned: dict[str, str] = {}
        for key, value in (env if env is not None else state.env_defaults or {}).items():
            name = str(key).strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
                cleaned[name] = str(value)
        state.env_defaults = cleaned
        prefs = getattr(self, "prefs", None)
        if prefs is None:
            return
        try:
            import json

            await prefs.set(PREF_ENV_DEFAULTS, json.dumps(cleaned))
        except Exception as exc:
            logger.debug("env defaults persist failed: %s", exc)

    async def save_app_preset(self, preset: dict | None = None) -> None:
        """Add or replace a launch preset (name, command, work dir, env).

        This is the user's own "desktop shortcut": what to run, what to call
        it, and the login options that belong to it. Detected .desktop apps
        stay separate; presets are what the user created."""
        data = dict(preset or {})
        name = str(data.get("name") or "").strip()
        cmd = str(data.get("cmd") or "").strip()
        if not cmd:
            self.show_snack("a preset needs a command")
            return
        if not name:
            name = cmd.split()[0].rsplit("/", 1)[-1]
        # Truncate BEFORE comparing: the replace-by-name filter must see the
        # same string that lands in the store, or long names duplicate.
        name = name[:40]
        work_dir = str(data.get("work_dir") or "").strip()
        env_lines = [str(item).strip() for item in data.get("env") or [] if str(item).strip()]
        container = str(data.get("container") or "").strip()
        entry = {"name": name, "cmd": cmd}
        if container:
            entry["container"] = container
        if work_dir:
            entry["work_dir"] = work_dir
        if env_lines:
            entry["env"] = env_lines
        current = [
            item
            for item in (state.app_presets or [])
            if str(item.get("name", "")).lower() != name.lower()
        ]
        current.append(entry)
        state.app_presets = current
        prefs = getattr(self, "prefs", None)
        if prefs is None:
            return
        try:
            import json

            await prefs.set(PREF_APP_PRESETS, json.dumps(current))
        except Exception as exc:
            logger.debug("app presets persist failed: %s", exc)
        self.show_snack(f"preset '{entry['name']}' saved")

    async def delete_app_preset(self, name: str) -> None:
        """Remove a launch preset by name."""
        current = [
            item
            for item in (state.app_presets or [])
            if str(item.get("name", "")).lower() != str(name).lower()
        ]
        state.app_presets = current
        prefs = getattr(self, "prefs", None)
        if prefs is None:
            return
        try:
            import json

            await prefs.set(PREF_APP_PRESETS, json.dumps(current))
        except Exception as exc:
            logger.debug("app presets persist failed: %s", exc)

    async def save_display_settings(self) -> None:
        """Settings -> Display saves immediately (a sheet edit used to be lost)."""
        prefs = getattr(self, "prefs", None)
        if prefs is None:
            return
        try:
            import json

            await prefs.set(PREF_DISPLAY_SETTINGS, json.dumps(self._display_settings()))
        except Exception as exc:
            logger.debug("display settings persist failed: %s", exc)

    async def save_terminal_settings(self) -> None:
        prefs = getattr(self, "prefs", None)
        if prefs is None:
            return
        try:
            import json

            from core.state import DEFAULT_TERMINAL_SETTINGS

            merged = {**DEFAULT_TERMINAL_SETTINGS, **(state.terminal_settings or {})}
            await prefs.set(PREF_TERMINAL_SETTINGS, json.dumps(merged))
        except Exception as exc:
            logger.debug("terminal settings persist failed: %s", exc)

    async def check_updates_now(self) -> None:
        """Manual check from Settings -> About (the startup check is throttled)."""
        from services.update_service import check_for_update

        self.show_snack("checking for updates…")
        try:
            data = await check_for_update()
        except Exception as exc:
            self.show_snack(f"update check failed: {exc}")
            return
        if data:
            from components.update_dialog import show_update_dialog

            show_update_dialog(self.page, data)
        else:
            self.show_snack("this build is up to date")

    async def replay_onboarding(self) -> None:
        prefs = getattr(self, "prefs", None)
        if prefs is not None:
            try:
                await prefs.set(STORAGE_ONBOARDING_DONE, "false")
            except Exception as exc:
                logger.debug("onboarding reset failed: %s", exc)
        state.onboarding_done = False

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
        """Tapping the persistent notification returns to the running work:
        the display if one is up (from ANY screen — the old early-return made
        the tap dead while inside a terminal, device 2026-11-17), else the
        last live shell."""
        manager = getattr(self, "desk_manager", None)
        running = manager.running() if manager is not None else []
        if running:
            state.active_display = running[-1].key
            return
        entries = list(self.session_manager.entries.values())
        if entries and not state.active_session:
            state.active_session = entries[-1].key

    # ── guest notifications → Android ─────────────────────────────────────────

    def _on_guest_notification(self, app: str, summary: str, body: str) -> None:
        """Called from the display watcher thread: hop to the page loop."""
        self.page.run_task(self._show_guest_notification, app, summary, body)

    async def _show_guest_notification(self, app: str, summary: str, body: str) -> None:
        """Forward one guest D-Bus notification as a native Android one.

        Best effort: a missing service or a denied POST_NOTIFICATIONS simply
        means nothing appears. Titles/bodies are bounded and de-duplicated."""
        notifications = getattr(self, "notifications", None)
        if notifications is None:
            return
        text = " · ".join(part for part in (summary, body) if part).strip()
        if not text:
            return
        key = (app, text)
        if key == getattr(self, "_last_guest_notification", None):
            return
        self._last_guest_notification = key
        sequence = (getattr(self, "_guest_notify_seq", 0) + 1) % 500
        self._guest_notify_seq = sequence
        try:
            import flet_notifications as ftn

            options = ftn.AndroidOptions(
                channel=ftn.NotificationChannel(
                    id=NOTIFICATION_CHANNEL_GUEST,
                    name=NOTIFICATION_CHANNEL_GUEST_NAME,
                ),
                auto_cancel=True,
            )
            await notifications.show(
                id=NOTIFICATION_ID_GUEST_BASE + sequence,
                title=(app or APP_NAME)[:80],
                body=text[:400],
                options=options,
            )
        except Exception as exc:
            logger.debug("guest notification show failed: %s", exc)

    # ── lifecycle ─────────────────────────────────────────────────────────────
