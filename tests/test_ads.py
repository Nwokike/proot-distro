"""Ads service — the Sherlock contract: consent gate, interval guard, cleanup.

Offline: the flet_ads surfaces are faked, the page is a stand-in.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from services import ad_service


def _page(mobile: bool = True) -> MagicMock:
    page = MagicMock()
    platform = MagicMock()
    platform.is_mobile.return_value = mobile
    page.platform = platform
    page.web = False
    page.services = []
    return page


def test_non_mobile_skips_the_consent_flow():
    service = ad_service.AdService(_page(mobile=False))
    import asyncio

    asyncio.run(service.gather_consent())
    assert service._can_request_ads is True
    assert service._consent_manager is None


def test_interstitial_is_skipped_on_desktop():
    service = ad_service.AdService(_page(mobile=False))
    import asyncio

    assert asyncio.run(service.show_interstitial()) is False


def test_interval_guard_blocks_a_back_to_back_show():
    import asyncio

    service = ad_service.AdService(_page(mobile=True))
    service._can_request_ads = True
    service._last_interstitial_at = __import__("time").monotonic()
    assert asyncio.run(service.show_interstitial()) is False


def test_close_releases_services():
    import asyncio

    page = _page(mobile=True)
    service = ad_service.AdService(page)
    ad = MagicMock()
    page.services.append(ad)
    service.interstitial = ad
    asyncio.run(service.close())
    assert ad not in page.services
    assert service.interstitial is None
    assert service._is_shutting_down is True


def test_test_ids_are_used_while_no_production_account_exists():
    service = ad_service.AdService(_page())
    assert service.USE_TEST_IDS is True
    assert "3940256099942544" in service.interstitial_id


def test_banner_pool_reuses_one_control_per_slot():
    from components import banner_ad

    banner_ad.clear_banner_pool()
    page = _page(mobile=False)
    first = banner_ad.pooled_banner_ad("slot-a", page)
    second = banner_ad.pooled_banner_ad("slot-a", page)
    assert first is second
    banner_ad.clear_banner_pool()
    third = banner_ad.pooled_banner_ad("slot-a", page)
    assert third is not first
