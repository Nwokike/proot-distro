"""AppController — owns the services and every action."""

from __future__ import annotations

import asyncio
import functools
import inspect
import json
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
from controller_actions.app_misc import AppMiscMixin
from core import proot_probe, shared_services, theme
from core.constants import (
    NOTIFICATION_ICON,
    PREF_APP_PRESETS,
    PREF_DISPLAY_SETTINGS,
    PREF_DOCKER_TOKEN,
    PREF_ENV_DEFAULTS,
    PREF_TERMINAL_SETTINGS,
    PREF_THEME_MODE,
    STORAGE_ONBOARDING_DONE,
    UPDATE_CHECK_INTERVAL_SEC,
)
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


class AppController(
    AppMiscMixin, DistroActions, ContainerActions, SessionActions, BuildActions, DisplayActions
):
    def __init__(self, page: ft.Page):
        self.page = page
        self.proot = proot_service
        # Process-wide registry: the FGS keeps the process alive across
        # activity destroy/recreate, so reopening the app re-attaches to the
        # same live shells instead of losing them (Termux behavior).
        self.session_manager = session_manager.shared_manager()
        # Shared singleton (same pattern): the FGS keeps the process alive, so
        # a reopened app re-adopts running display sessions instead of losing them.
        self.desk_manager = desk_service.shared_manager()
        # Session transitions (start/stop/fail) → observable rev bump, so the
        # Display tab re-reads the manager's lists immediately.
        self.desk_manager.on_sessions_changed = self._bump_display_sessions
        self.desk_manager.on_log_line = self._bump_display_log
        self.ad_service = ad_service.AdService(page)
        # android_default_icon: our app-icon silhouette (bundled via
        # tool.flet.android.res_dir), not the plugin's default Flet logo.
        self.notifications = ft_notifications.Notifications(android_default_icon=NOTIFICATION_ICON)
        self.notifications.on_action = self._on_notification_action
        self.notifications.on_tap = self._on_notification_tap
        self.session_manager.notifications = self.notifications

    def _bump_display_sessions(self) -> None:
        """DeskManager fired a session transition: bump the observable rev so
        subscribed views re-read the session lists right away (the Stop button
        flips its row to "stopping…" without leaving the tab) AND reconcile the
        display state — a crashed session must not leave the app pointing at a
        dead display with the wakelock and FGS still held."""

        async def _apply_bump() -> None:
            state.display_sessions_rev = (state.display_sessions_rev or 0) + 1
            active = state.active_display
            if active:
                s = self.desk_manager.get(active)
                if s is None or s.status is not desk_service.DeskStatus.RUNNING:
                    state.active_display = None
                    if s is not None and s.status is desk_service.DeskStatus.ERROR:
                        # A crash is never silent: the error text drives the
                        # viewer's error branch and the tab's Failed rows.
                        state.display_status = "error"
                        state.display_error = s.error
                    else:
                        state.display_status = "idle"
                        state.display_status_text = ""
                    state.display_url = ""
                    self._wakelock(False)
                    self._lock_orientation(False)
            await self._update_fgs()

        self.page.run_task(_apply_bump)

    def _bump_display_log(self) -> None:
        """A guest log line arrived: bump the rev so the display view's output
        panel streams live (the reader thread can't touch the UI directly)."""

        async def _apply() -> None:
            state.display_log_rev = (state.display_log_rev or 0) + 1

        self.page.run_task(_apply)

    async def init(self) -> None:
        state.app_ready = False
        state.startup_stage = "Starting…"
        # Warm reopen (the FGS kept the process alive): never land in
        # chrome-less fullscreen — the toolbar is hidden there, so a stale
        # flag would leave no on-screen exit.
        state.display_fullscreen = False

        await self.check_probe()

        # Housekeeping, off the UI thread: temp/ is throwaway by contract
        # (.flet/README.md), and the durable display logs are bounded so a year
        # of runs cannot grow without limit.
        try:
            from core import storage_paths

            await asyncio.to_thread(storage_paths.sweep_temp)
            await asyncio.to_thread(storage_paths.prune_display_logs)
        except Exception as exc:
            logger.debug("startup housekeeping skipped: %s", exc)

        # New page session (app reopened while the process stayed alive via the
        # foreground service): drop stale terminal widgets so each live shell
        # re-creates its MobileTerminal on THIS page and re-wires; the retained
        # scrollback replays on mount.
        for _entry in self.session_manager.entries.values():
            _entry.mt = None
            _entry.wired = False
        # Display sessions keep their WebView too — it belongs to the old page.
        self.desk_manager.release_page_bindings()

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
            remove_container=self.remove_container,
            reset_container=self.reset_container,
            search_distro=self.search_distro,
            open_notification_settings=self.open_notification_settings,
            open_developer_tools=self.open_developer_tools,
            save_env_defaults=self.save_env_defaults,
            save_app_preset=self.save_app_preset,
            delete_app_preset=self.delete_app_preset,
            open_settings_section=self.open_settings_section,
            save_display_settings=self.save_display_settings,
            save_terminal_settings=self.save_terminal_settings,
            check_updates_now=self.check_updates_now,
            replay_onboarding=self.replay_onboarding,
            run_container=self.run_container,
            clear_cache=self.clear_cache,
            clear_app_cache=self.clear_app_cache,
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
            probe_apps=self.probe_apps,
            start_display=self.start_display,
            stop_display=self.stop_display,
            start_x_display=self.start_x_display,
            retry_display=self.retry_display,
            resume_display=self.resume_display,
            cancel_install_display=self.cancel_install_display,
            leave_display=self.leave_display,
            install_display_support=self.install_display_support,
            show_display_logs=self.show_display_logs,
            set_display_fullscreen=self.set_display_fullscreen,
            share_display=self.share_display,
            finish_onboarding=self.finish_onboarding,
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

        # Render immediately — AppShell shows the startup splash screen
        # (brand icon + spinner + startup_stage) on cold boot only. A warm
        # re-open (notification tap, FGS kept the process alive) already has
        # the container list in memory: flip app_ready NOW so the shell lands
        # straight on the terminal in ~1s, and refresh in the background.
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))

        warm_reopen = bool(state.containers)
        if warm_reopen:
            state.app_ready = True
            self.page.run_task(self.refresh_containers)
        else:
            state.startup_stage = "Loading containers…"
            await self.refresh_containers()
            # Startup complete: dismiss splash into fully-loaded UI.
            state.app_ready = True

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

        async def _probe_connectivity() -> None:
            from core.state import _is_online

            try:
                state.online = _is_online(await self.connectivity.get_connectivity())
            except Exception as exc:
                logger.debug("connectivity probe failed: %s", exc)

        self.page.run_task(_probe_connectivity)
        # Official Flet audio-recorder service — `has_permission()` is the
        # supported way to obtain the RECORD_AUDIO runtime grant (the display's
        # mic path asks through it before the PulseAudio daemon starts). A
        # Service registers with the page AT CONSTRUCTION, so it must be built
        # HERE (per page session) — a warm reopen (FGS kept the process alive)
        # re-runs init() but not __init__, and a recorder built for the dead
        # page session makes has_permission() fail silently (device audit
        # 2026-11-13). Audio only — never a startup failure.
        try:
            import flet_audio_recorder as far

            self.mic_recorder = far.AudioRecorder()
        except Exception as exc:
            logger.debug("audio recorder service unavailable: %s", exc)
            self.mic_recorder = None
        # Wakelock/Clipboard/Share for the display wrap are the ONE app-wide
        # instances already mounted by shared_services (page.wakelock,
        # page.clipboard, page.share) — never mount a second instance.
        # Termux-style persistent notification: keeps the app alive in the
        # background while Linux sessions are running.
        self.page.services.append(self.notifications)

    async def _restore_prefs(self) -> None:
        if self.prefs is None:
            return
        # One bridge round-trip instead of three sequential ones on the splash path.
        mode, token, saved_settings = await asyncio.gather(
            self.prefs.get(PREF_THEME_MODE),
            self.prefs.get(PREF_DOCKER_TOKEN),
            self.prefs.get(PREF_DISPLAY_SETTINGS),
        )
        if isinstance(mode, str) and mode in _THEME_MODES:
            state.theme_mode = mode
            theme.apply_theme_mode(self.page, mode)
        if isinstance(token, str):
            if token and ":" not in token:
                # A bare PAT saved by an older build would break even anonymous
                # pulls (upstream needs user:token) — never apply it.
                logger.warning("ignoring a malformed persisted Docker credential")
                state.docker_token = ""
            else:
                state.docker_token = token
                if token:
                    os.environ["PD_DOCKER_AUTH"] = token
        if not (isinstance(saved_settings, str) and saved_settings):
            await self._apply_battery_defaults()
        saved_terminal = await self.prefs.get(PREF_TERMINAL_SETTINGS)
        from core.state import DEFAULT_TERMINAL_SETTINGS

        state.terminal_settings = dict(DEFAULT_TERMINAL_SETTINGS)
        if isinstance(saved_terminal, str) and saved_terminal:
            try:
                loaded_terminal = json.loads(saved_terminal)
                if isinstance(loaded_terminal, dict):
                    state.terminal_settings.update(loaded_terminal)
            except TypeError, ValueError:
                logger.debug("saved terminal_settings unparseable, keeping defaults")

        # Guest defaults the user added in Settings -> Environment.
        saved_env = await self.prefs.get(PREF_ENV_DEFAULTS)
        state.env_defaults = {}
        if isinstance(saved_env, str) and saved_env:
            try:
                loaded_env = json.loads(saved_env)
                if isinstance(loaded_env, dict):
                    state.env_defaults = {
                        str(k): str(v) for k, v in loaded_env.items() if str(k).strip()
                    }
            except TypeError, ValueError:
                logger.debug("saved env_defaults unparseable, keeping empty")

        # User-made display presets (name + command + its login options).
        saved_presets = await self.prefs.get(PREF_APP_PRESETS)
        state.app_presets = []
        if isinstance(saved_presets, str) and saved_presets:
            try:
                loaded_presets = json.loads(saved_presets)
                if isinstance(loaded_presets, list):
                    state.app_presets = [
                        item
                        for item in loaded_presets
                        if isinstance(item, dict) and str(item.get("cmd", "")).strip()
                    ]
            except TypeError, ValueError:
                logger.debug("saved app_presets unparseable, keeping empty")

        if isinstance(saved_settings, str) and saved_settings:
            try:
                loaded = json.loads(saved_settings)
                if isinstance(loaded, dict) and loaded.get("resize") == "remote":
                    # "remote" was our old default and cropped the desktop on
                    # Android; treat it as the fit default unless re-chosen.
                    loaded["resize"] = "scale"
                if isinstance(loaded, dict):
                    from core.state import DEFAULT_DISPLAY_SETTINGS

                    state.display_settings = {**DEFAULT_DISPLAY_SETTINGS, **loaded}
            except ValueError, TypeError:
                logger.debug("saved display_settings unparseable, keeping defaults")
        state.theme_revision += 1

    async def refresh_containers(self) -> None:
        try:
            # Wall time = the slowest scan instead of the sum of three.
            containers, storage, cached = await asyncio.gather(
                asyncio.to_thread(self.proot.list_containers),
                asyncio.to_thread(self.proot.storage_split),
                asyncio.to_thread(self.proot.cached_images),
            )
            state.containers = containers
            state.storage_containers_bytes, state.storage_cache_bytes = storage
            state.storage_bytes = storage[0] + storage[1]
            state.cached_count = len(cached)
            state.cached_images = cached
            state.data_note = ""
            self._warm_probes(containers)
        except Exception as exc:
            # Surface, never swallow: the UI shows why the list is empty
            # (e.g. proot_distro missing because the app runs under the wrong
            # interpreter — system flet instead of the project venv).
            state.data_note = f"proot-distro unavailable: {exc}"
            logger.warning("refresh_containers failed: %s", exc)

    def _warm_probes(self, containers: list[dict]) -> None:
        """Probe containers that have no fresh cache entry, once per app start.

        With the TTL cache warm, the Display tab paints from disk; without this,
        a first launch after an install would still show "probing..."."""
        if getattr(self, "_probe_warmed", False):
            return
        self._probe_warmed = True
        from core import probe_cache

        for row in containers:
            name = str(row.get("name", ""))
            if not name:
                continue
            if probe_cache.load("caps", name) is None:
                self.page.run_task(self.probe_display, name)
            if probe_cache.load("apps", name) is None:
                self.page.run_task(self.probe_apps, name)

    async def check_probe(self, force: bool = False) -> None:
        probe = await asyncio.to_thread(proot_probe.bootstrap_env, None, force)
        state.probe_passed = probe.ok
        state.probe_summary = "; ".join(probe.problems) or (
            f"payload {probe.payload_provenance} · {probe.f2fs}"
        )

    # ── misc ──────────────────────────────────────────────────────────────────

    def _guard(self, fn):
        """Wrap a controller coroutine so exits and session teardown never kill the app."""

        @functools.wraps(fn)
        async def _wrapped(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except (SystemExit, KeyboardInterrupt) as exc:
                name = getattr(fn, "__name__", "action")
                logger.exception("handler %s raised %s, contained", name, type(exc).__name__)
                state.data_note = f"{name} tried to exit the app ({exc!r}), contained"
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

    async def finish_onboarding(self) -> None:
        state.onboarding_done = True
        if self.prefs is not None:
            await self.prefs.set(STORAGE_ONBOARDING_DONE, "true")

    _UPDATE_CHECK_INTERVAL = UPDATE_CHECK_INTERVAL_SEC  # seconds between background checks
