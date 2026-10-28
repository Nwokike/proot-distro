"""AppController — owns the services and every action."""

from __future__ import annotations

import asyncio
import logging
import os

import flet as ft

from app_shell import AppShell
from controller_actions import ContainerActions, DistroActions, SessionActions
from core import proot_probe, shared_services, theme
from core.constants import STORAGE_HINTS_DISMISSED, STORAGE_ONBOARDING_DONE
from core.state import state
from services import ad_service, proot_service, session_manager
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx

logger = logging.getLogger(__name__)


_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}
# The ONE theme cycle definition (house order: Light → Dark → System); the
# header button and the Settings row both call it so they cannot diverge.
_THEME_ORDER = ("light", "dark", "system")


class AppController(DistroActions, ContainerActions, SessionActions):
    def __init__(self, page: ft.Page):
        self.page = page
        self.proot = proot_service
        self.session_manager = session_manager.SessionManager()
        self.ad_service = ad_service.AdService(page)

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        # The env contract + grp shim must be set before proot_distro is importable.
        await self.check_probe()

        self._mount_services()

        light, dark = theme.build_theme()
        self.page.theme = light
        self.page.dark_theme = dark
        await self._restore_prefs()
        await self._restore_onboarding()

        methods = ControllerMethods(
            refresh_containers=self.refresh_containers,
            install_distro=self.install_distro,
            cancel_install=self._noop_cancel,
            remove_container=self.remove_container,
            reset_container=self.reset_container,
            search_distro=self.search_distro,
            clear_cache=self.clear_cache,
            clear_orphan_layers=self.clear_orphan_layers,
            remove_cached_image=self.remove_cached_image,
            set_docker_token=self.set_docker_token,
            set_theme_mode=self.set_theme_mode,
            cycle_theme_mode=self.cycle_theme_mode,
            check_probe=self.check_probe,
            show_snack=self.show_snack,
            show_privacy_options=self.show_privacy_options,
            rename_container=self.rename_container,
            backup_container=self.backup_container,
            restore_container=self.restore_container,
            copy_path=self.copy_path,
            sync_path=self.sync_path,
            inspect_container=self.inspect_container,
            list_sessions=self.list_sessions,
            kill_session=self.kill_session,
            kill_all_sessions=self.kill_all_sessions,
            open_session=self.open_session,
            leave_session=self.leave_session,
            close_session=self.close_session,
            finish_onboarding=self.finish_onboarding,
            dismiss_hints=self.dismiss_hints,
        )
        self.page._controller = self
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))

        # The update check runs in the background and only flips state.
        self.page.run_task(self._check_for_updates)

        # UMP consent then preload the first interstitial (Sherlock pattern).
        async def _consent_and_preload() -> None:
            await self.ad_service.gather_consent()
            # Publish the verdict: banners gate on state.can_request_ads, and
            # a failed consent run is surfaced instead of silently serving
            # (or silently not serving) ads.
            state.can_request_ads = self.ad_service.can_request_ads
            if not state.can_request_ads and self.ad_service.consent_failed:
                state.data_note = "Ad consent is unavailable — ads stay off this session."
            await self.ad_service.preload_interstitial()

        self.page.run_task(_consent_and_preload)
        await self.refresh_containers()

    def _mount_services(self) -> None:
        mounted = shared_services.mount_shared_services(self.page)
        self.prefs = mounted.get("prefs")
        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)
        self.connectivity = ft.Connectivity()
        self.connectivity.on_change = self._on_connectivity
        self.page.services.append(self.connectivity)

    async def _restore_prefs(self) -> None:
        if self.prefs is None:
            return
        mode = await self.prefs.get("theme_mode")
        if isinstance(mode, str) and mode in _THEME_MODES:
            state.theme_mode = mode
            theme.apply_theme_mode(self.page, mode)
        token = await self.prefs.get("docker_token")
        if isinstance(token, str):
            state.docker_token = token
            if token:
                os.environ["PD_DOCKER_AUTH"] = token
        state.theme_revision += 1

    def _noop_cancel(self) -> None:
        return None

    def _on_connectivity(self, _e) -> None:
        # Informational only: installs fail loudly without a network.
        return

    # ── actions (state-only mutations) ────────────────────────────────────────

    async def refresh_containers(self) -> None:
        state.containers = await asyncio.to_thread(self.proot.list_containers)
        state.storage_bytes = await asyncio.to_thread(self.proot.storage_bytes)
        cached = await asyncio.to_thread(self.proot.cached_images)
        state.cached_count = len(cached)
        state.cached_images = cached
        state.busy_locks = await asyncio.to_thread(self.proot.busy_locks)
        state.data_note = ""

    async def set_docker_token(self, token: str) -> None:
        token = token.strip()
        state.docker_token = token
        if token:
            os.environ["PD_DOCKER_AUTH"] = token
        else:
            os.environ.pop("PD_DOCKER_AUTH", None)
        if self.prefs is not None:
            await self.prefs.set("docker_token", token)
        self.show_snack("Docker Hub token saved" if token else "Docker Hub token cleared")

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

    async def check_probe(self) -> None:
        state.probe_running = True
        try:
            probe = await asyncio.to_thread(proot_probe.bootstrap_env)
            state.probe_passed = probe.ok
            state.probe_summary = "; ".join(probe.problems) or (
                f"payload {probe.payload_provenance} · {probe.f2fs}"
            )
        finally:
            state.probe_running = False

    # ── misc ──────────────────────────────────────────────────────────────────

    def show_snack(self, message: str) -> None:
        from components.snack import show_snack as _show

        _show(self.page, message)

    async def _restore_onboarding(self) -> None:
        """The deck shows until it is dismissed once."""
        if self.prefs is None:
            return
        done = await self.prefs.get(STORAGE_ONBOARDING_DONE)
        state.onboarding_done = done == "true"
        hints = await self.prefs.get(STORAGE_HINTS_DISMISSED)
        if hints == "true":
            state.hints_dismissed = True

    async def finish_onboarding(self) -> None:
        state.onboarding_done = True
        if self.prefs is not None:
            await self.prefs.set(STORAGE_ONBOARDING_DONE, "true")

    async def dismiss_hints(self) -> None:
        """The hints card stays gone across launches, not per-render."""
        state.hints_dismissed = True
        if self.prefs is not None:
            await self.prefs.set(STORAGE_HINTS_DISMISSED, "true")

    async def _check_for_updates(self) -> None:
        """Silent background check; a newer build flips the header chip."""
        from services.update_service import check_for_update

        try:
            data = await check_for_update()
        except Exception:
            logger.exception("Startup update check failed")
            raise
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
