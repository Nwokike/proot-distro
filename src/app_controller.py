"""AppController — owns the services and every action."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

import flet as ft

from app_shell import AppShell
from core import proot_probe, shared_services, theme
from core.state import state
from services import ad_service, proot_service, session_manager
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx

logger = logging.getLogger(__name__)


def _reason(exc: BaseException) -> str:
    """One honest line for a failure — never a bare swallow."""
    text = str(exc).strip() or exc.__class__.__name__
    return text.splitlines()[0][:200]


_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}
# The ONE theme cycle definition (house order: Light → Dark → System); the
# header button and the Settings row both call it so they cannot diverge.
_THEME_ORDER = ("light", "dark", "system")


class AppController:
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

        methods = ControllerMethods(
            refresh_containers=self.refresh_containers,
            install_distro=self.install_distro,
            cancel_install=self._noop_cancel,
            remove_container=self.remove_container,
            reset_container=self.reset_container,
            search_distro=self.search_distro,
            clear_cache=self.clear_cache,
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
            list_sessions=self.list_sessions,
            kill_session=self.kill_session,
            open_session=self.open_session,
            leave_session=self.leave_session,
            close_session=self.close_session,
        )
        self.page._controller = self
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))

        # UMP consent then preload the first interstitial (Sherlock pattern).
        async def _consent_and_preload() -> None:
            await self.ad_service.gather_consent()
            await self.ad_service.preload_interstitial()

        self.page.run_task(_consent_and_preload)
        await self.refresh_containers()

    def _mount_services(self) -> None:
        mounted = shared_services.mount_shared_services(self.page)
        self.prefs = mounted.get("prefs")
        try:
            self.file_picker = ft.FilePicker()
            self.page.services.append(self.file_picker)
        except Exception as exc:
            logger.debug("file picker unavailable: %s", exc)
            self.file_picker = None
        try:
            self.connectivity = ft.Connectivity()
            self.connectivity.on_change = self._on_connectivity
            self.page.services.append(self.connectivity)
        except Exception as exc:
            logger.debug("connectivity unavailable: %s", exc)
            self.connectivity = None

    async def _restore_prefs(self) -> None:
        if self.prefs is None:
            return
        try:
            mode = await self.prefs.get("theme_mode")
            if isinstance(mode, str) and mode in _THEME_MODES:
                state.theme_mode = mode
                self.page.theme_mode = _THEME_MODES[mode]
            token = await self.prefs.get("docker_token")
            if isinstance(token, str):
                state.docker_token = token
                if token:
                    os.environ["PD_DOCKER_AUTH"] = token
        except Exception as exc:
            logger.debug("prefs restore failed: %r", exc)
        state.theme_revision += 1

    def _noop_cancel(self) -> None:
        return None

    def _on_connectivity(self, _e) -> None:
        # Informational only: installs fail loudly without a network.
        return

    # ── actions (state-only mutations) ────────────────────────────────────────

    async def refresh_containers(self) -> None:
        notes: list[str] = []
        try:
            state.containers = await asyncio.to_thread(self.proot.list_containers)
        except Exception as exc:
            state.containers = []
            notes.append(f"container list unavailable: {_reason(exc)}")
        try:
            state.storage_bytes = await asyncio.to_thread(self.proot.storage_bytes)
        except Exception as exc:
            state.storage_bytes = 0
            notes.append(f"storage size unavailable: {_reason(exc)}")
        try:
            cached = await asyncio.to_thread(self.proot.cached_images)
            state.cached_count = len(cached)
        except Exception as exc:
            state.cached_count = 0
            notes.append(f"cached-image list unavailable: {_reason(exc)}")
        state.data_note = " · ".join(notes)

    async def install_distro(self, image: str, name: str) -> None:
        if state.installing:
            return
        if await asyncio.to_thread(self.proot.busy_locks):
            state.busy_note = "another install is already running"
            return
        state.installing = name or image
        state.install_stage = "preparing"
        state.busy_note = ""

        loop = self.page.loop

        def _apply_line(line: str) -> None:
            state.install_stage = line.strip()

        def _on_line(line: str) -> None:
            loop.call_soon_threadsafe(_apply_line, line)

        def _run():
            return self.proot.install(image, name, on_line=_on_line)

        try:
            outcome = await asyncio.to_thread(_run)
            if outcome.ok:
                state.install_stage = f"installed {state.installing}"
            else:
                state.install_stage = (
                    self.proot.PULL_LIMIT_COPY
                    if self.proot.is_pull_limit(outcome)
                    else self.proot.friendly_job_error(outcome)
                )
                self.show_snack(state.install_stage)
        except Exception as exc:
            state.install_stage = f"install failed: {exc!r}"
            self.show_snack(state.install_stage)
        finally:
            installed_now = state.installing
            state.installing = None
            await self.refresh_containers()
            if installed_now and outcome is not None and outcome.ok:
                await self.ad_service.show_interstitial()

    async def remove_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.remove_container, name)
        self.show_snack(f"removed {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def reset_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.reset_container, name)
        self.show_snack(f"reset {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        await self.refresh_containers()

    async def search_distro(self, query: str) -> None:
        state.search_status = f"searching “{query}”…"
        try:
            results = await asyncio.to_thread(self.proot.search_images, query)
        except Exception as exc:
            state.search_results = []
            state.search_status = f"search failed: {_reason(exc)}"
            return
        state.search_results = results
        state.search_status = (
            f"{len(results)} result(s) — tap one to fill the fields"
            if results
            else "no results (or the search failed)"
        )

    async def clear_cache(self) -> None:
        if state.cache_busy:
            return
        state.cache_busy = True
        try:
            images = await asyncio.to_thread(self.proot.cached_images)
            for image in images:
                identifier = image.get("identifier")
                if identifier and identifier != "?":
                    await asyncio.to_thread(self.proot.remove_cached_image, identifier)
            self.show_snack("cached downloads cleared")
        except Exception as exc:
            self.show_snack(f"cache clear failed: {exc!r}")
        finally:
            state.cache_busy = False
            await self.refresh_containers()

    async def set_docker_token(self, token: str) -> None:
        token = token.strip()
        state.docker_token = token
        if token:
            os.environ["PD_DOCKER_AUTH"] = token
        else:
            os.environ.pop("PD_DOCKER_AUTH", None)
        if self.prefs is not None:
            with contextlib.suppress(Exception):
                await self.prefs.set("docker_token", token)
        self.show_snack("Docker Hub token saved" if token else "Docker Hub token cleared")

    async def set_theme_mode(self, mode: str) -> None:
        if mode not in _THEME_MODES:
            return
        state.theme_mode = mode
        state.theme_revision += 1
        self.page.theme_mode = _THEME_MODES[mode]
        if self.prefs is not None:
            with contextlib.suppress(Exception):
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
        with contextlib.suppress(Exception):
            self.page.show_dialog(ft.SnackBar(ft.Text(message)))

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

    async def rename_container(self, orig: str, new: str) -> None:
        new = new.strip()
        if not new:
            return
        outcome = await asyncio.to_thread(self.proot.rename_container, orig, new)
        self.show_snack(
            f"renamed to {new}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )
        await self.refresh_containers()

    async def backup_container(self, container: str) -> None:
        if self.file_picker is None:
            self.show_snack("file picker unavailable on this build")
            return
        target = await self.file_picker.save_file(
            dialog_title=f"Backup {container}", file_name=f"{container}.tar.gz"
        )
        if not target:
            return
        outcome = await asyncio.to_thread(self.proot.backup_container, container, target)
        self.show_snack(
            f"backup written to {target}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    async def restore_container(self) -> None:
        if self.file_picker is None:
            self.show_snack("file picker unavailable on this build")
            return
        picked = await self.file_picker.pick_files(
            dialog_title="Restore a container archive", allow_multiple=False
        )
        if not picked:
            return
        path = picked[0].path
        outcome = await asyncio.to_thread(self.proot.restore_container, path)
        self.show_snack(
            "container restored" if outcome.ok else self.proot.friendly_job_error(outcome)
        )
        await self.refresh_containers()

    async def copy_path(self, source: str, destination: str) -> None:
        source = source.strip()
        destination = destination.strip()
        if not source or not destination:
            self.show_snack("copy needs a source and a destination")
            return
        outcome = await asyncio.to_thread(self.proot.copy_path, source, destination)
        self.show_snack(
            f"copied {source} -> {destination}"
            if outcome.ok
            else self.proot.friendly_job_error(outcome)
        )

    async def list_sessions(self) -> None:
        rows = await asyncio.to_thread(self.proot.active_sessions)
        if not rows:
            self.show_snack("no running sessions")
            return
        lines = [
            f"pid {row.get('pid')} · {row.get('container')} · {row.get('kind')}" for row in rows
        ]
        self.show_snack(" · ".join(lines[:4]))

    async def kill_session(self, pid: str) -> None:
        outcome = await asyncio.to_thread(self.proot.kill_session, str(pid))
        self.show_snack(
            f"stopped session {pid}" if outcome.ok else self.proot.friendly_job_error(outcome)
        )

    # ── sessions ──────────────────────────────────────────────────────────────

    async def open_session(self, container: str) -> None:
        state.session_error = ""
        try:
            await asyncio.to_thread(self.session_manager.open, container)
        except Exception as exc:
            state.session_error = f"could not open {container}: {_reason(exc)}"
            return
        state.active_session = container

    async def leave_session(self) -> None:
        state.active_session = None

    async def close_session(self, container: str) -> None:
        await asyncio.to_thread(self.session_manager.close, container)
        if state.active_session == container:
            state.active_session = None
