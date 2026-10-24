"""AdMob service — banner and interstitial ads with UMP consent (Sherlock pattern)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

import flet as ft

from components.banner_ad import clear_banner_pool

logger = logging.getLogger(__name__)

try:
    import flet_ads as fta

    _HAS_ADS = True
except ImportError:
    _HAS_ADS = False


class AdService:
    """Manages AdMob interstitial ads and UMP consent."""

    USE_TEST_IDS = True

    INTERSTITIAL_ID_ANDROID_TEST = "ca-app-pub-3940256099942544/1033173712"
    INTERSTITIAL_ID_ANDROID_PROD = "ca-app-pub-3940256099942544/1033173712"

    INTERSTITIAL_MIN_INTERVAL_SEC = 30.0

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial = None
        self._shown_interstitial = None
        self._on_close: Callable | None = None
        self._can_request_ads: bool = True
        self._consent_manager = None
        self._privacy_options_required: bool | None = None
        self._is_shutting_down: bool = False
        self._last_interstitial_at: float | None = None
        # True when the UMP flow itself failed (vs. a real "no" from the
        # user) — the controller surfaces it in state.data_note.
        self.consent_failed: bool = False

    @property
    def can_request_ads(self) -> bool:
        return self._can_request_ads

    @property
    def interstitial_id(self) -> str:
        if self.USE_TEST_IDS:
            return self.INTERSTITIAL_ID_ANDROID_TEST
        return self.INTERSTITIAL_ID_ANDROID_PROD

    def _is_mobile(self) -> bool:
        try:
            return self.page.platform.is_mobile() and not getattr(self.page, "web", False)
        except Exception:
            return False

    # ── Consent Management (UMP) ──────────────────────────────────────────

    async def gather_consent(self):
        """Run UMP consent flow. Only shows UI in regulated regions (EEA/UK)."""
        self.consent_failed = False
        if not _HAS_ADS:
            logger.info("AdService: flet_ads not available — ads disabled this build")
            self._can_request_ads = False
            return
        if not self._is_mobile():
            logger.info("AdService: non-mobile platform — consent flow skipped")
            self._can_request_ads = True
            return
        try:
            self._consent_manager = fta.ConsentManager()
            if self._consent_manager not in self.page.services:
                self.page.services.append(self._consent_manager)
            await self._consent_manager.request_consent_info_update()
            await self._consent_manager.load_and_show_consent_form_if_required()
            self._can_request_ads = await self._consent_manager.can_request_ads()
            try:
                status = await self._consent_manager.get_privacy_options_requirement_status()
                self._privacy_options_required = (
                    status == fta.PrivacyOptionsRequirementStatus.REQUIRED
                )
                logger.info(
                    "AdService: consent status=%s can_request_ads=%s",
                    status,
                    self._can_request_ads,
                )
            except Exception as exc:
                logger.warning("AdService: privacy-requirement probe failed: %s", exc)
            if not self._can_request_ads:
                logger.warning(
                    "AdService: UMP says ads cannot be requested — interstitials disabled this session"
                )
        except Exception as e:
            # Consent failure means NO ads this session — defaulting to allow
            # would serve ads without a verdict (D-017.9: no swallowed bugs;
            # the UI states why ads are off via state.data_note).
            logger.warning("AdService: UMP consent flow failed — ads disabled this session: %s", e)
            self._can_request_ads = False
            self.consent_failed = True

    async def show_privacy_options(self) -> str:
        if not self._consent_manager:
            logger.warning("AdService: privacy options requested but consent manager is missing")
            return "no_manager"
        try:
            status = await self._consent_manager.get_privacy_options_requirement_status()
        except Exception as e:
            logger.warning("AdService: privacy options status check failed: %s", e)
            return f"error:{e}"
        if status != fta.PrivacyOptionsRequirementStatus.REQUIRED:
            logger.info("AdService: privacy options form not required (status=%s)", status)
            return "not_required"
        try:
            await self._consent_manager.show_privacy_options_form()
            self._can_request_ads = await self._consent_manager.can_request_ads()
            logger.info(
                "AdService: privacy options form shown, can_request_ads=%s",
                self._can_request_ads,
            )
            return "form_shown"
        except Exception as e:
            logger.warning("AdService: privacy options form failed to open: %s", e)
            return f"error:{e}"

    # ── Interstitial Ads ──────────────────────────────────────────────────

    async def preload_interstitial(self, on_close: Callable | None = None):
        """Pre-load an interstitial ad for later display."""
        self._on_close = on_close
        if self._is_shutting_down:
            logger.info("AdService: preload skipped — shutting down")
            return
        if not _HAS_ADS or not self._is_mobile():
            logger.info("AdService: preload skipped — flet_ads missing or non-mobile")
            return
        if not self._can_request_ads:
            logger.info("AdService: preload skipped — consent gate closed")
            return
        try:
            ad = fta.InterstitialAd(
                unit_id=self.interstitial_id,
                on_load=lambda _e: logger.info("InterstitialAd loaded"),
                on_error=lambda e: logger.warning(
                    "InterstitialAd load error: %s", getattr(e, "data", e)
                ),
                on_close=self._handle_close,
            )
        except Exception as exc:
            logger.warning("AdService: failed to construct InterstitialAd: %s", exc)
            return
        self.interstitial = ad
        try:
            if ad not in self.page.services:
                self.page.services.append(ad)
        except Exception as exc:
            logger.warning("AdService: could not register preloaded interstitial: %s", exc)
            self.interstitial = None
            return
        logger.info("AdService: interstitial preloaded (unit=%s)", self.interstitial_id)

    async def _handle_close(self, _e):
        if self._shown_interstitial is not None:
            _release_service(self.page.services, self._shown_interstitial)
            self._shown_interstitial = None
        if self._on_close:
            if asyncio.iscoroutinefunction(self._on_close):
                await self._on_close()
            else:
                self._on_close()

    async def show_interstitial(self) -> bool:
        if not _HAS_ADS or not self._is_mobile() or not self._can_request_ads:
            logger.info("AdService: interstitial skipped — ads unavailable or consent gate closed")
            return False
        if self._last_interstitial_at is not None:
            elapsed = time.monotonic() - self._last_interstitial_at
            if elapsed < self.INTERSTITIAL_MIN_INTERVAL_SEC:
                logger.info(
                    "AdService: interstitial skipped — %.0fs since the last one (min interval %.0fs)",
                    elapsed,
                    self.INTERSTITIAL_MIN_INTERVAL_SEC,
                )
                return False
        if self.interstitial is not None:
            ad_to_show = self.interstitial
            self.interstitial = None
            self._shown_interstitial = ad_to_show
            try:
                await ad_to_show.show()
                # Consume the interval only on a successful show — a failed
                # one should not penalize the user with a 30 s dead window.
                self._last_interstitial_at = time.monotonic()
                logger.info("InterstitialAd shown (preloaded instance)")
                return True
            except Exception as e:
                logger.warning("AdService: preloaded interstitial show failed: %s", e)
                self._shown_interstitial = None
                _release_service(self.page.services, ad_to_show)
                return False
            finally:
                if not self._is_shutting_down:
                    await self.preload_interstitial(on_close=self._on_close)

        try:

            async def _show(e):
                await e.control.show()
                logger.info("InterstitialAd shown (fresh instance)")

            def _on_error(e):
                logger.warning("InterstitialAd load error: %s", getattr(e, "data", e))
                if self._shown_interstitial is not None:
                    _release_service(self.page.services, self._shown_interstitial)
                    self._shown_interstitial = None

            ad = fta.InterstitialAd(
                unit_id=self.interstitial_id,
                on_load=lambda e: self.page.run_task(_show, e),
                on_error=_on_error,
                on_close=self._handle_close,
            )
        except Exception as e:
            logger.warning("AdService: fresh interstitial construction failed: %s", e)
            return False
        self._shown_interstitial = ad
        try:
            if ad not in self.page.services:
                self.page.services.append(ad)
        except Exception as exc:
            logger.warning("AdService: could not register fresh interstitial: %s", exc)
            self._shown_interstitial = None
            return False
        logger.info("AdService: fresh interstitial queued — it will show on load")
        return True

    async def close(self):
        self._is_shutting_down = True
        for ad in (self.interstitial, self._shown_interstitial):
            if ad is not None:
                _release_service(self.page.services, ad)
        self.interstitial = None
        self._shown_interstitial = None
        clear_banner_pool()


def _release_service(services: list, item) -> None:
    try:
        services.remove(item)
    except ValueError:
        pass
