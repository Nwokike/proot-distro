"""Opening, leaving and closing guest shells."""

from __future__ import annotations

import asyncio
import logging

from core.state import state

from ._common import _reason

logger = logging.getLogger(__name__)


class SessionOpenMixin:
    async def open_session(self, container: str) -> None:
        """Open a NEW shell on the container (multi-shell; no ad on open).
        In-flight guard: a double-tap must not open two shells."""
        opening = getattr(self, "_opening_sessions", None)
        if opening is None:
            opening = self._opening_sessions = set()
        if container in opening:
            self.show_snack(f"already opening a shell on {container}…")
            return
        opening.add(container)
        try:
            await self._open_session_impl(container)
        finally:
            opening.discard(container)

    def _display_env_for(self, container: str) -> dict[str, str]:
        """A running display's guest environment for a NEW shell — DISPLAY,
        XAUTHORITY and PULSE_SERVER — so GUI apps launched from any shell reach
        the display (device 2026-11-14: `firefox` → "no DISPLAY"). Empty when
        no display runs (plain shell), and never fatal on lookup errors."""
        manager = getattr(self, "desk_manager", None)
        if manager is None:
            return {}
        try:
            return manager.guest_display_env(container)
        except Exception as exc:
            logger.debug("display env lookup failed for %s: %s", container, exc)
            return {}

    async def _open_session_impl(self, container: str) -> None:
        state.session_error = ""
        # If an image ref was passed instead of a container name (e.g.
        # 'archlinux/archlinux'), resolve it to the actual installed container.
        if "/" in container:
            containers = await asyncio.to_thread(self.proot.list_containers)
            match = next(
                (c["name"] for c in containers if c.get("image") == container),
                container.rsplit("/", 1)[-1],
            )
            container = match
        try:
            entry = await self.session_manager.open(
                container,
                extra_env=self._display_env_for(container),
            )
        except Exception as exc:
            state.session_error = f"could not open {container}: {_reason(exc)}"
            self.show_snack(state.session_error)
            logger.exception("Could not open shell for %s", container)
            raise
        state.active_session = entry.key
        await self._update_fgs()
        # Interstitial at the natural break of opening a shell (allowed by
        # AdMob placement rules — terminal-adjacent breaks only, never mid-type).
        await self.ad_service.show_interstitial()

    async def open_session_with_options(self, container: str, opts: dict) -> None:
        """Open a NEW shell with the upstream login options (100% proot-distro
        wrap: user, work-dir, env, bind, shared tmp/home, fix-low-ports,
        isolated). Same flow as open_session otherwise."""
        state.session_error = ""
        try:
            entry = await self.session_manager.open(
                container, options=opts, extra_env=self._display_env_for(container)
            )
        except Exception as exc:
            state.session_error = f"could not open {container}: {_reason(exc)}"
            self.show_snack(state.session_error)
            logger.exception("Could not open shell (options) for %s", container)
            raise
        state.active_session = entry.key
        await self._update_fgs()
        await self.ad_service.show_interstitial()

    async def leave_session(self) -> None:
        state.active_session = None
        await self.ad_service.show_interstitial()

    async def close_session(self, session_key: str) -> None:
        await asyncio.to_thread(self.session_manager.close, session_key)
        if state.active_session == session_key:
            state.active_session = None
        await self._update_fgs()  # stops only when no shells AND no displays remain
        await self.ad_service.show_interstitial()

    async def exit_app(self) -> None:
        """Kill all sessions and displays, stop the foreground service, exit."""
        manager = getattr(self, "desk_manager", None)
        if manager is not None:
            await manager.stop_all()
        await asyncio.to_thread(self.session_manager.close_all)
        await self._stop_fgs()
        notifications = getattr(self, "notifications", None)
        if notifications is not None:
            try:
                await notifications.cancel_all()  # leave no stale shade entries
            except Exception as exc:
                logger.debug("notification cleanup failed: %s", exc)
        ads = getattr(self, "ad_service", None)
        if ads is not None:
            try:
                await ads.close()
            except Exception as exc:
                logger.debug("ad cleanup failed: %s", exc)
        # Android: finish the activity directly.
        try:
            from jnius import autoclass

            autoclass("android.os.Process").killProcess(autoclass("android.os.Process").myPid())
        except Exception:
            import os

            os._exit(0)
