"""BannerAd — single canonical banner ad builder (mobile only).

Matches the Sherlock pattern:
- Pre-checks `page.platform.is_mobile()` and returns `ft.Container(width=0, height=0)` on desktop/web.
- Caches created banner instances in `_BANNER_POOL` by slot string so rebuilds don't recreate them.
- Full-width wrapper with glass/surface styling and centered 320x50 native ad.
"""

from __future__ import annotations

import logging

import flet as ft
from flet import Control

from core import theme

logger = logging.getLogger(__name__)

BANNER_ID_ANDROID_TEST = "ca-app-pub-3940256099942544/9214589741"
BANNER_ID_ANDROID_PROD = "ca-app-pub-3940256099942544/9214589741"
USE_TEST_IDS = True

_BANNER_POOL: dict[str, Control] = {}


def banner_unit_id() -> str:
    return BANNER_ID_ANDROID_TEST if USE_TEST_IDS else BANNER_ID_ANDROID_PROD


def pooled_banner_ad(slot: str, page: ft.Page | None = None) -> Control:
    # The consent verdict is part of the cache key: a slot pooled as a
    # pre-consent placeholder must be rebuilt once consent lands (and vice
    # versa), or the pool would serve the stale shape forever.
    from core.state import state

    key = f"{slot}:{int(state.can_request_ads)}"
    ad = _BANNER_POOL.get(key)
    if ad is None:
        ad = build_banner_ad(page)
        _BANNER_POOL[key] = ad
    return ad


def clear_banner_pool() -> None:
    _BANNER_POOL.clear()


def build_banner_ad(page: ft.Page | None = None) -> Control:
    if page is None:
        try:
            page = ft.context.page
        except Exception:
            return ft.Container(width=0, height=0)

    if not page or not hasattr(page, "platform"):
        return ft.Container(width=0, height=0)

    try:
        if not page.platform.is_mobile() or page.web:
            return ft.Container(width=0, height=0)
    except Exception:
        return ft.Container(width=0, height=0)

    # Consent gate: the banner must never request an ad before (or without)
    # a UMP verdict — this is the same gate the interstitial path uses.
    from core.state import state

    if not state.can_request_ads:
        return ft.Container(width=0, height=0)

    try:
        import flet_ads as fta

        ad = fta.BannerAd(
            unit_id=banner_unit_id(),
            width=320,
            height=50,
            on_load=lambda _e: logger.info("BannerAd loaded"),
            on_error=lambda e: logger.warning("BannerAd load error: %s", getattr(e, "data", e)),
        )
    except Exception as e:
        logger.warning("Failed to load BannerAd: %s", e)
        return ft.Container(width=0, height=0)

    banner = ft.Container(
        content=ft.Column(
            [
                ft.Container(content=ad, width=320, height=50),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
            tight=True,
        ),
        expand=True,
        padding=8,
        border_radius=12,
        bgcolor=theme.surface(),
        border=ft.Border.all(1, theme.surface_alt()),
    )

    return ft.Row(
        controls=[banner],
        alignment=ft.MainAxisAlignment.CENTER,
    )
