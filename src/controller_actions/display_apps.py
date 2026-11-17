"""App detection for the display surfaces (Display tab + sheet presets).

Split out of display_session.py (file-size rule). The scan is host-side (the
container's own .desktop entries) with a `command -v` fallback for minimal
images, and it is refreshed in place: the Display tab and the sheet show a
spinner and a refresh button, and a list older than APPS_STALE_AFTER_SEC is
re-scanned in the background so an app installed inside a running container
appears without restarting the app (owner ruling 2026-11-17).
"""

from __future__ import annotations

import logging

from core.state import state

logger = logging.getLogger(__name__)

# In-flight app scans per container (renders fire probe_apps freely; one scan
# runs at a time so a repaint loop cannot spawn parallel proot commands).
_PROBING_APPS: set[str] = set()


class DisplayAppsMixin:
    # A container's app list is re-scanned in the background once it is this
    # old, so an app installed inside a running container appears by itself.
    APPS_STALE_AFTER_SEC = 60.0

    async def probe_apps(self, container: str, force: bool = False) -> None:
        """Detect the preset GUI apps this container actually has.

        Primary source: the container's own .desktop files, read host-side (no
        proot spawn, real application names). Fallback for minimal images that
        register nothing: a `command -v` probe of the bundled preset list.

        `force=True` (the refresh button) bypasses BOTH caches. Otherwise the
        in-memory list is reused while younger than APPS_STALE_AFTER_SEC, and
        the disk TTL cache covers cold starts. Concurrent calls for the same
        container collapse into one scan."""
        import asyncio
        import time

        from core import probe_cache
        from core.constants import APP_PRESETS
        from services import proot_service, session_service

        now = time.monotonic()
        detected = dict(state.detected_apps or {})
        stamps = dict(state.detected_apps_at or {})
        if force:
            probe_cache.drop("apps", container)
            detected.pop(container, None)
        elif container in detected and now - stamps.get(container, 0) < self.APPS_STALE_AFTER_SEC:
            return
        if container in _PROBING_APPS:
            return
        if not force and container not in detected:
            disk = probe_cache.load("apps", container)
            if isinstance(disk, list):
                detected[container] = disk
                stamps[container] = now
                state.detected_apps = detected
                state.detected_apps_at = stamps
                return

        _PROBING_APPS.add(container)
        scan_failed = False
        try:
            found = await asyncio.to_thread(proot_service.guest_desktop_apps, container)
        except Exception as exc:
            logger.debug("desktop-app scan failed for %s: %s", container, exc)
            found = []
            scan_failed = True
        finally:
            _PROBING_APPS.discard(container)

        if not found:
            errors = {"count": 0}

            async def _one(label: str, cmd: str) -> dict | None:
                try:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(
                            session_service.command_capture,
                            container,
                            ["/bin/sh", "-c", f"command -v {cmd}"],
                            timeout=10.0,
                        ),
                        timeout=12.0,
                    )
                except Exception as exc:
                    logger.debug("app probe for %s/%s failed: %s", container, cmd, exc)
                    errors["count"] += 1
                    return None
                if result.get("ok") and result.get("output", "").strip():
                    return {"label": label, "cmd": cmd}
                return None

            found = [
                item
                for item in await asyncio.gather(*(_one(label, cmd) for label, cmd in APP_PRESETS))
                if item is not None
            ]
            # Every probe ERRORED (as opposed to a clean "not installed"): the
            # answer is unknown, so do not pin "no apps" in the cache.
            if errors["count"] == len(APP_PRESETS) or (scan_failed and errors["count"]):
                detected[container] = found
                stamps[container] = now
                state.detected_apps = detected
                state.detected_apps_at = stamps
                return
        probe_cache.store("apps", container, found)
        detected[container] = found
        stamps[container] = now
        state.detected_apps = detected
        state.detected_apps_at = stamps
