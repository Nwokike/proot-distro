"""AppController — owns the services and every action."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import os

import flet as ft
import flet_notifications as ft_notifications

from app_shell import AppShell
from controller_actions import (
    BuildActions,
    ContainerActions,
    DisplayActions,
    DistroActions,
    SessionActions,
)
from core import proot_probe, shared_services, theme
from core.constants import STORAGE_HINTS_DISMISSED, STORAGE_ONBOARDING_DONE
from core.state import state
from services import ad_service, desk_service, proot_service, session_manager
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


class AppController(DistroActions, ContainerActions, SessionActions, BuildActions, DisplayActions):
    def __init__(self, page: ft.Page):
        self.page = page
        self.proot = proot_service
        # Process-wide registry: the FGS keeps the process alive across
        # activity destroy/recreate, so reopening the app re-attaches to the
        # same live shells instead of losing them (Termux behavior).
        self.session_manager = session_manager.shared_manager()
        self.desk_manager = desk_service.DeskManager()
        self.ad_service = ad_service.AdService(page)
        # android_default_icon: our app-icon silhouette (bundled via
        # tool.flet.android.res_dir), not the plugin's default Flet logo.
        self.notifications = ft_notifications.Notifications(
            android_default_icon="ic_stat_prootdistro"
        )
        self.notifications.on_action = self._on_notification_action
        self.notifications.on_tap = self._on_notification_tap
        self.session_manager.notifications = self.notifications

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

    async def init(self) -> None:
        # The env contract + grp shim must be set before proot_distro is importable.
        await self.check_probe()

        # New page session (app reopened while the process stayed alive via the
        # foreground service): drop stale terminal widgets so each live shell
        # re-creates its MobileTerminal on THIS page and re-wires; the retained
        # scrollback replays on mount.
        for _entry in self.session_manager.entries.values():
            _entry.mt = None
            _entry.wired = False

        # Stale pooled-banner controls carry the PREVIOUS session's control
        # ids; patching them into the fresh Dart tree makes the client drop
        # patches ("unknown control … client is out of sync"). Rebuild the pool
        # for this session.
        from components.banner_ad import clear_banner_pool

        clear_banner_pool()

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
            run_container=self.run_container,
            clear_cache=self.clear_cache,
            clear_orphan_layers=self.clear_orphan_layers,
            clear_build_cache=self.clear_build_cache,
            remove_cached_image=self.remove_cached_image,
            storage_detail=self.storage_detail,
            refresh_storage_detail=self.refresh_storage_detail,
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
            open_session_with_options=self.open_session_with_options,
            leave_session=self.leave_session,
            close_session=self.close_session,
            open_display=self.open_display,
            probe_display=self.probe_display,
            start_display=self.start_display,
            stop_display=self.stop_display,
            leave_display=self.leave_display,
            install_display_support=self.install_display_support,
            show_display_logs=self.show_display_logs,
            set_display_fullscreen=self.set_display_fullscreen,
            share_display=self.share_display,
            finish_onboarding=self.finish_onboarding,
            dismiss_hints=self.dismiss_hints,
            exit_app=self.exit_app,
            run_build=self.run_build,
            push_image=self.push_image,
        )
        # Contain SystemExit/KeyboardInterrupt from any handler: in a packaged
        # app sys.exit is the build template's patched flet_exit (posts the
        # code to the Dart exit bridge instead of raising), and asyncio
        # re-raises SystemExit out of the event loop — either way the whole
        # process dies with that code. Surface it as a note instead.
        for _name, _fn in list(vars(methods).items()):
            if inspect.iscoroutinefunction(_fn):
                setattr(methods, _name, self._guard(_fn))
        self.methods = methods  # sheets opened imperatively (display launcher) need it
        self.page._controller = self
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))

        # The update check runs in the background and only flips state.
        self.page.run_task(self._check_for_updates)

        # UMP consent then preload the first interstitial (Sherlock pattern:
        # gather_consent defaults to allow on UMP failure; banners gate on
        # state.can_request_ads).
        async def _consent_and_preload() -> None:
            await self.ad_service.gather_consent()
            state.can_request_ads = self.ad_service.can_request_ads
            await self.ad_service.preload_interstitial()

        self.page.run_task(_consent_and_preload)

        # Request notification permission at startup (Android 13+ requires a
        # runtime prompt for POST_NOTIFICATIONS). If the user denies, we
        # re-request each time a foreground service is about to start.
        async def _request_notification_permission() -> None:
            try:
                await self.notifications.request_permissions()
            except Exception as exc:
                logger.debug("Notification permission request failed: %s", exc)

        self.page.run_task(_request_notification_permission)

        await self.refresh_containers()

    def _mount_services(self) -> None:
        mounted = shared_services.mount_shared_services(self.page)
        self.prefs = mounted.get("prefs")
        self.file_picker = ft.FilePicker()
        self.page.services.append(self.file_picker)
        # CollabShell reads page.file_picker — mount the attribute too, or the
        # file manager reports "file picker unavailable on this build".
        self.page.file_picker = self.file_picker
        self.connectivity = ft.Connectivity()
        self.connectivity.on_change = self._on_connectivity
        self.page.services.append(self.connectivity)
        # flet dev4 services the display wrap uses: screen-awake while a
        # desktop is open, the system share sheet and clipboard for URLs/code.
        self.wakelock = ft.Wakelock()
        self.clipboard = ft.Clipboard()
        self.share = ft.Share()
        for _service in (self.wakelock, self.clipboard, self.share):
            self.page.services.append(_service)
        # Termux-style persistent notification: keeps the app alive in the
        # background while Linux sessions are running.
        self.page.services.append(self.notifications)

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
        try:
            state.containers = await asyncio.to_thread(self.proot.list_containers)
            state.storage_bytes = await asyncio.to_thread(self.proot.storage_bytes)
            cached = await asyncio.to_thread(self.proot.cached_images)
            state.cached_count = len(cached)
            state.cached_images = cached
            state.busy_locks = await asyncio.to_thread(self.proot.busy_locks)
            state.data_note = ""
        except Exception as exc:
            # Surface, never swallow: the UI shows why the list is empty
            # (e.g. proot_distro missing because the app runs under the wrong
            # interpreter — system flet instead of the project venv).
            state.data_note = f"proot-distro unavailable: {exc}"
            logger.warning("refresh_containers failed: %s", exc)

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

    def _guard(self, fn):
        """Wrap a controller coroutine so exits and session teardown never kill the app."""

        @functools.wraps(fn)
        async def _wrapped(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except (SystemExit, KeyboardInterrupt) as exc:
                name = getattr(fn, "__name__", "action")
                logger.exception("handler %s raised %s — contained", name, type(exc).__name__)
                state.data_note = f"{name} tried to exit the app ({exc!r}) — contained"
                return None
            except RuntimeError as exc:
                # A task can finish after the page session is destroyed (app
                # closed mid-refresh): the observable values were already set —
                # only the notify needs a live session. Contain like exits
                # instead of surfacing "An attempt to fetch destroyed session".
                if "destroyed session" in str(exc) or "not associated" in str(exc):
                    logger.debug(
                        "handler %s raced session teardown: %s", getattr(fn, "__name__", "?"), exc
                    )
                    return None
                raise

        return _wrapped

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
