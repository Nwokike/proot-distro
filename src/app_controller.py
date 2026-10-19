"""AppController — builds the shell and owns every service call.

One-to-one wrapping: each action is a single upstream call on a worker thread
(`asyncio.to_thread`), its result lands in the observable state, and the views
re-render from that state. Views never mutate controls; this module never
touches a control either — only `state.*` fields and page-level services.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

import flet as ft

from app_shell import AppShell
from core import proot_probe, shared_services, theme
from core.state import state
from services import proot_service
from state.controller_ctx import ControllerMethods, ControllerMethodsCtx

logger = logging.getLogger(__name__)

_THEME_MODES = {
    "system": ft.ThemeMode.SYSTEM,
    "light": ft.ThemeMode.LIGHT,
    "dark": ft.ThemeMode.DARK,
}


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.proot = proot_service

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def init(self) -> None:
        # 1. Environment + payload probe BEFORE the UI shows anything. The env
        #    contract and the grp shim are what make upstream importable on
        #    Android at all (device-proven, M0); nothing else is patched.
        await self.check_probe()

        # 2. Shared services (mounted once; refcount discipline is theirs).
        self._mount_services()

        # 3. Themes + persisted preferences, then the shell.
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
            check_probe=self.check_probe,
            show_snack=self.show_snack,
        )
        self.page._controller = self
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))

        # 4. First data load.
        await self.refresh_containers()

    def _mount_services(self) -> None:
        mounted = shared_services.mount_shared_services(self.page)
        self.prefs = mounted.get("prefs")
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

    def _noop_cancel(self) -> None:  # upstream install isn't interruptible; the
        return None  # view shows live stages and leaves cleanup to remove

    def _on_connectivity(self, _e) -> None:
        # Informational only: installs fail loudly without a network.
        return

    # ── actions (state-only mutations) ────────────────────────────────────────

    async def refresh_containers(self) -> None:
        state.containers = await asyncio.to_thread(self.proot.list_containers)
        state.storage_bytes = await asyncio.to_thread(self.proot.storage_bytes)
        state.cached_count = len(await asyncio.to_thread(self.proot.cached_images))

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
                state.install_stage = self.proot.friendly_job_error(outcome)
                self.show_snack(state.install_stage)
        except Exception as exc:
            state.install_stage = f"install failed: {exc!r}"
            self.show_snack(state.install_stage)
        finally:
            state.installing = None
            await self.refresh_containers()

    async def remove_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.remove_container, name)
        self.show_snack(f"removed {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        await self.refresh_containers()

    async def reset_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.reset_container, name)
        self.show_snack(f"reset {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        await self.refresh_containers()

    async def search_distro(self, query: str) -> None:
        state.search_status = f"searching “{query}”…"
        results = await asyncio.to_thread(self.proot.search_images, query)
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
