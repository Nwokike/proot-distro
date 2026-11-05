"""Distro management actions: install, remove, reset, search, cache."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import theme
from core.state import state

from ._common import _reason

logger = logging.getLogger(__name__)


class DistroActions:
    @staticmethod
    def _derive_container_name(image_ref: str) -> str:
        """Derive a valid container name from an image ref — mirrors upstream
        proot_distro.helpers.docker.refs.derive_alias: take the last path
        component after '/', strip the tag. 'archlinux/archlinux' -> 'archlinux'."""
        repo = image_ref.strip().split("@")[0].split(":")[0]
        return repo.rsplit("/", 1)[-1]

    async def install_distro(
        self, image: str, name: str, arch: str = "", insecure: bool = False
    ) -> None:
        if state.installing:
            return
        if await asyncio.to_thread(self.proot.busy_locks):
            state.busy_note = "another install is already running"
            return
        # Sanitize: a container name must never contain '/' (upstream
        # require_valid_name rejects it). Derive from the image ref if the
        # user left the name blank or typed an invalid one.
        if not name.strip() or "/" in name:
            name = self._derive_container_name(image)
        state.installing = name or image
        state.install_stage = "preparing"
        state.install_logs = []
        state.install_completed = False
        state.install_dialog_minimized = False
        state.busy_note = ""

        loop = self.page.loop

        def _apply_line(line: str) -> None:
            clean = line.strip()
            # Assign new list objects for every line: the rows previously
            # mutated `state.install_logs` in place, which does not notify
            # `@ft.observable` and therefore did not reliably repaint the
            # progress dialog/banner.
            state.install_stage = clean
            if clean:
                state.install_logs = [*state.install_logs[-499:], clean]
            # Live-update the modal controls if the dialog is still open.
            stage_ctrl = getattr(self.page, "_install_stage_text", None)
            logs_ctrl = getattr(self.page, "_install_logs_column", None)
            if stage_ctrl is not None:
                stage_ctrl.value = clean or state.install_stage
                stage_ctrl.update()
            from core import tokens as _t

            if logs_ctrl is not None:
                logs_ctrl.controls = [
                    ft.Text(
                        ln,
                        font_family=_t.MONO_FONT,
                        size=_t.FONT_XXS,
                        color=theme.text_dim(),
                    )
                    for ln in state.install_logs[-60:]
                ]
                logs_ctrl.update()
            dialog = getattr(self.page, "_install_dialog", None)
            if dialog is not None and getattr(dialog, "open", False):
                try:
                    dialog.update()
                except RuntimeError:
                    pass

        def _on_line(line: str) -> None:
            loop.call_soon_threadsafe(_apply_line, line)

        def _run():
            return self.proot.install(
                image,
                name,
                on_line=_on_line,
                override_arch=arch or None,
                allow_insecure=insecure,
            )

        outcome = None
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
            logger.exception("Could not install %s", image)
            raise
        finally:
            installed_now = state.installing
            state.installing = None
            await self.refresh_containers()
            # Close the install progress modal automatically when done, unless
            # the user already minimized it into the background banner.
            if not state.install_dialog_minimized:
                self.page.pop_dialog()
            dialog = getattr(self.page, "_install_dialog", None)
            if dialog is not None and not dialog.open:
                self.page._install_dialog = None
                self.page._install_stage_text = None
                self.page._install_logs_column = None
            if installed_now and outcome is not None and outcome.ok:
                state.install_completed = True
                state.last_installed = installed_now
                await self.ad_service.show_interstitial()

    async def remove_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.remove_container, name)
        self.show_snack(f"removed {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        if outcome.ok:
            from controller_actions.display_actions import invalidate_display_support

            invalidate_display_support(name)
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def reset_container(self, name: str) -> None:
        outcome = await asyncio.to_thread(self.proot.reset_container, name)
        self.show_snack(f"reset {name}" if outcome.ok else self.proot.friendly_job_error(outcome))
        if outcome.ok:
            # The rootfs changed on disk — drop the cached caps and re-probe.
            from controller_actions.display_actions import invalidate_display_support

            invalidate_display_support(name)
            await self.probe_display(name)
        await self.refresh_containers()
        if outcome.ok:
            await self.ad_service.show_interstitial()

    async def search_distro(self, query: str, limit: int = 20) -> None:
        state.search_status = f"searching “{query}”…"
        try:
            results = await asyncio.to_thread(self.proot.search_images, query, limit)
        except Exception as exc:
            state.search_results = []
            state.search_status = f"search failed: {_reason(exc)}"
            logger.exception("Distro search failed for %r", query)
            raise
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
            outcome = await asyncio.to_thread(self.proot.clear_cache)
            self.show_snack(
                "cached downloads cleared" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
        except Exception as exc:
            self.show_snack(f"cache clear failed: {exc!r}")
            logger.exception("Could not clear the image cache")
            raise
        finally:
            state.cache_busy = False
            await self.refresh_containers()

    async def clear_orphan_layers(self) -> None:
        if state.cache_busy:
            return
        state.cache_busy = True
        try:
            outcome = await asyncio.to_thread(self.proot.clear_cache, orphan=True)
            self.show_snack(
                "orphan layers cleared" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
        except Exception as exc:
            self.show_snack(f"orphan sweep failed: {exc!r}")
            logger.exception("Could not sweep orphan image layers")
            raise
        finally:
            state.cache_busy = False
            await self.refresh_containers()

    async def remove_cached_image(self, identifier: str) -> None:
        if state.cache_busy:
            return
        state.cache_busy = True
        try:
            outcome = await asyncio.to_thread(self.proot.remove_cached_image, identifier)
            self.show_snack(
                f"removed {identifier}" if outcome.ok else self.proot.friendly_job_error(outcome)
            )
        except Exception as exc:
            self.show_snack(f"image remove failed: {exc!r}")
            logger.exception("Could not remove cached image %s", identifier)
            raise
        finally:
            state.cache_busy = False
            await self.refresh_containers()
