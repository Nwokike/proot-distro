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


# ── consent-gating regressions (swarm: flet-ads F1/F2, ad_service F2) ───────


class _FailingConsentManager:
    def request_consent_info_update(self):
        raise RuntimeError("network down")


def test_consent_failure_disables_ads_and_is_flagged(monkeypatch):
    """A failed UMP flow means NO ads — never 'default to allow'."""
    import asyncio

    monkeypatch.setattr(ad_service.fta, "ConsentManager", _FailingConsentManager)
    service = ad_service.AdService(_page(mobile=True))
    asyncio.run(service.gather_consent())
    assert service.can_request_ads is False
    assert service.consent_failed is True


class _GrantingConsentManager:
    async def request_consent_info_update(self):
        return None

    async def load_and_show_consent_form_if_required(self):
        return None

    async def can_request_ads(self):
        return True

    async def get_privacy_options_requirement_status(self):
        return ad_service.fta.PrivacyOptionsRequirementStatus.NOT_REQUIRED


def test_consent_success_opens_the_gate(monkeypatch):
    import asyncio

    monkeypatch.setattr(ad_service.fta, "ConsentManager", _GrantingConsentManager)
    service = ad_service.AdService(_page(mobile=True))
    asyncio.run(service.gather_consent())
    assert service.can_request_ads is True
    assert service.consent_failed is False


def test_banner_is_refused_before_consent(monkeypatch):
    """The banner must never request an ad without a UMP verdict."""
    import sys

    sys.path.insert(0, "src")
    from components import banner_ad
    from core.state import state

    banner_ad.clear_banner_pool()
    state.can_request_ads = False
    out = banner_ad.build_banner_ad(_page(mobile=True))
    assert getattr(out, "width", None) == 0 and getattr(out, "height", None) == 0
    banner_ad.clear_banner_pool()


def test_banner_pool_key_includes_the_consent_verdict():
    from components import banner_ad
    from core.state import state

    banner_ad.clear_banner_pool()
    try:
        state.can_request_ads = False
        before = banner_ad.pooled_banner_ad("slot-x", _page(mobile=True))
        state.can_request_ads = True
        after = banner_ad.pooled_banner_ad("slot-x", _page(mobile=True))
        assert before is not after  # the verdict flip forces a rebuild
    finally:
        state.can_request_ads = False
        banner_ad.clear_banner_pool()
