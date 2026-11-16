"""Container probing, guest ssh and the mic grant."""

from __future__ import annotations

import asyncio
import logging

from core import probe_cache
from core.state import state
from services import proot_service

from .display_common import _probing

logger = logging.getLogger(__name__)


class DisplayProbeMixin:
    async def probe_display(self, container: str) -> None:
        """Cache the container's rootfs capability probe in state.display_support.

        Two layers: the in-memory observable for this page session, and a
        short-TTL copy under the regenerable cache root so a cold start paints
        the cards instantly instead of walking the rootfs again. Failures are
        NOT cached — the next mount re-probes. In-flight probes dedup via a set
        so a render loop never spawns parallel proot commands."""
        if state.display_support is None:
            state.display_support = {}
        cached = state.display_support.get(container)
        if cached is not None and "error" not in cached:
            return
        if container in _probing:
            return
        disk = probe_cache.load("caps", container)
        if isinstance(disk, dict) and "error" not in disk:
            state.display_support = {**(state.display_support or {}), container: disk}
            return
        _probing.add(container)
        try:
            caps = await asyncio.to_thread(proot_service.guest_capabilities, container)
        except Exception as exc:
            logger.warning("display probe failed for %s: %s", container, exc)
            return  # not cached — retried next mount
        finally:
            _probing.discard(container)
        probe_cache.store("caps", container, caps)
        # REASSIGN: nested dict-item mutation does not notify the observable,
        # so card labels ("Open display"/"Install display support") never flipped.
        state.display_support = {**(state.display_support or {}), container: caps}

    async def _guest_has_ssh(self, container: str) -> bool:
        """True when the container has an ssh client (the tunnel's only user).
        Single-app displays install nothing, so the switch must not promise a
        URL that can never appear."""
        from services import session_service

        try:
            result = await asyncio.to_thread(
                session_service.command_capture,
                container,
                ["/bin/sh", "-lc", "command -v ssh"],
                timeout=15.0,
            )
            return bool(result.get("ok"))
        except Exception:
            return False

    async def _ensure_mic_permission(self) -> bool:
        """Obtain the RECORD_AUDIO runtime grant through Flet's official
        AudioRecorder service (`has_permission()` requests it when needed)
        BEFORE the display's PulseAudio daemon starts — the mic module cannot
        open the recorder without it (device: 'Failed to initialize OpenSL ES:
        error 9'). A denied/absent service degrades audio only."""
        recorder = getattr(self, "mic_recorder", None)
        if recorder is None:
            return False
        try:
            return bool(await recorder.has_permission())
        except Exception as exc:
            logger.debug("mic permission check failed: %s", exc)
            return False

    # ── routing ───────────────────────────────────────────────────────────────

    def _display_caps(self, container: str) -> dict:
        return (state.display_support or {}).get(container) or {}
