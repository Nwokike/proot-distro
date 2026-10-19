"""Shared long-lived services, mounted exactly once.

Flet's service registry prunes by refcount after every event, and each
`Service()` construction auto-registers — so services are mounted once here and
screens reach them via the accessors (or page.* attributes), never by
constructing a fresh instance per render. Mirrors the Sherlock pattern.
"""

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
}


def mount_shared_services(page: ft.Page) -> dict[str, Any]:
    """Idempotently mount the app-wide services. Returns the mounted map."""
    specs = (
        ("haptics", ft.HapticFeedback),
        ("clipboard", ft.Clipboard),
        ("share", ft.Share),
        ("url_launcher", ft.UrlLauncher),
        ("prefs", ft.SharedPreferences),
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


def shared_haptics() -> ft.HapticFeedback | None:
    page = _current_page()
    return getattr(page, "haptics", None) if page else None


def _current_page() -> ft.Page | None:
    try:
        from flet import context

        return context.page
    except Exception:
        return None
