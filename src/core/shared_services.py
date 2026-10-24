"""Long-lived services, mounted exactly once."""

from __future__ import annotations

import logging
from typing import Any

import flet as ft

logger = logging.getLogger(__name__)

_ATTR_NAMES = {
    "haptics": "haptics",
    "clipboard": "clipboard",
    "share": "share",
    "url_launcher": "url_launcher",
    "prefs": "shared_preferences",
    "wakelock": "wakelock",
}


def mount_shared_services(page: ft.Page) -> dict[str, Any]:
    """Idempotently mount the app-wide services. Returns the mounted map."""
    specs = (
        ("haptics", ft.HapticFeedback),
        ("clipboard", ft.Clipboard),
        ("share", ft.Share),
        ("url_launcher", ft.UrlLauncher),
        ("prefs", ft.SharedPreferences),
        ("wakelock", ft.Wakelock),
    )
    mounted: dict[str, Any] = {}
    for key, factory in specs:
        attr = _ATTR_NAMES[key]
        existing = getattr(page, attr, None)
        if existing is not None:
            mounted[key] = existing
            continue
        try:
            instance = factory()
        except Exception as exc:
            logger.debug("shared service %s unavailable: %s", key, exc)
            continue
        try:
            if instance not in page.services:
                page.services.append(instance)
        except Exception as exc:
            logger.debug("shared service %s mount skipped: %s", key, exc)
            continue
        setattr(page, attr, instance)
        mounted[key] = instance
    return mounted


def shared_url_launcher(page: ft.Page | None = None) -> ft.UrlLauncher | None:
    p = page or _current_page()
    return getattr(p, "url_launcher", None) if p else None


async def launch_url(url: str, page: ft.Page | None = None) -> bool:
    launcher = shared_url_launcher(page)
    if launcher is not None:
        try:
            await launcher.launch_url(url)
            return True
        except Exception as exc:
            logger.debug("launch_url failed for %s: %s", url, exc)
    return False


def _current_page() -> ft.Page | None:
    try:
        from flet import context

        return context.page
    except Exception:
        return None
