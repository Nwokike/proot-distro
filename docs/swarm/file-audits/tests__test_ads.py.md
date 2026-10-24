# tests/test_ads.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_ads.py · src/services/ad_service.py · src/components/banner_ad.py · .venv/lib/python3.14/site-packages/flet_ads/* · Date: 2026-10-24

## What it does / how the app uses it

`tests/test_ads.py` is the ad-layer unit test file: 6 tests, all built on a `_page()` MagicMock stand-in (tests/test_ads.py:13-20) with `page.platform.is_mobile()` toggled per test. Each test drives async AdService methods with `asyncio.run()` (tests/test_ads.py:27, 36, 45, 56) and asserts state on the service/page objects. Coverage targets: non-mobile consent skip (tests/test_ads.py:23-29), desktop interstitial skip (:32-36), interval guard (:39-45), `close()` releasing page services (:48-59), test IDs (:62-66), and banner-pool reuse (:68-78). The file imports `from services import ad_service` (:10) and `from components import banner_ad` (:69), resolving under the pytest rootdir in pyproject.toml. No `pytest` fixtures from tests/conftest.py are used; the file is self-contained.

## Findings

### F1 · P1 · Consent gating — the core Sherlock contract — is asserted nowhere; every test dodges flet_ads
- **Where:** `tests/test_ads.py:23-29` (only consent test); `src/services/ad_service.py:59-94` (`gather_consent` mobile branch); `.venv/lib/python3.14/site-packages/flet_ads/consent_manager.py:44-126` (real ConsentManager API)
- **What:** `test_non_mobile_skips_the_consent_flow` covers only the early return at `ad_service.py:65-68` (`_can_request_ads = True` on non-mobile). No test mocks `fta.ConsentManager` or any of its methods (`request_consent_info_update` at `consent_manager.py:44-58`, `load_and_show_consent_form_if_required` at `:108-116`, `can_request_ads` at `:85-92`, `get_privacy_options_requirement_status` at `:94-106`), so the mobile branch where `_can_request_ads` is decided by UMP (`ad_service.py:73-75`, `88-91`, `78-80`) is unexecuted. Evidence: `pytest tests/test_ads.py` → `6 passed in 0.87s` with zero flet_ads-native invocations — every consent test uses `mobile=False`, and the interval test returns at `ad_service.py:170-178` before touching flet_ads. Proving the tests must mock: driving the real `fta.ConsentManager` without mocks raises `RuntimeError: ConsentManager(3) Control must be added to the page first` (reproduced by constructing `fta.ConsentManager()` and awaiting `request_consent_info_update()` / `can_request_ads()` against a MagicMock page). The mobile consent path therefore cannot run unmocked — and the file contains zero `mock.patch`/`monkeypatch` of flet_ads.
- **Fix / opportunity:** Add tests that `unittest.mock.patch("services.ad_service.fta.ConsentManager")` (or its async methods), simulate `can_request_ads()` True/False and `PrivacyOptionsRequirementStatus.REQUIRED`/`NOT_REQUIRED` (`.venv/lib/python3.14/site-packages/flet_ads/types.py:183-187`), and assert `_can_request_ads`, `page.services` registration (`ad_service.py:71-72`), and the privacy-options flag (`ad_service.py:78-80`). Also cover the `except` fallback at `ad_service.py:92-94` by making `request_consent_info_update` raise.
- **Risk if ignored:** EEA/UK GDPR — ads could be served without consent and no test would catch it (P1 compliance defect per sibling source audit F2 at `src/services/ad_service.py:92-94`).

### F2 · P2 · Interval guard test state-bashes the clock; no end-to-end guard-after-show
- **Where:** `tests/test_ads.py:39-45`; `src/services/ad_service.py:166-180`
- **What:** `test_interval_guard_blocks_a_back_to_back_show` sets `service._last_interstitial_at = time.monotonic()` directly (`tests/test_ads.py:44`), so `elapsed ≈ 0 < 30s` and `show_interstitial()` returns `False` at `ad_service.py:170-178`. It never tests that a completed show writes the timer (`ad_service.py:179-180`) and blocks the next show, nor that a show is allowed once 30s have elapsed. Relies on real `time.monotonic()` — passes only because elapsed is ~0, i.e. fragile by construction.
- **Fix / opportunity:** Mock `fta.InterstitialAd.show`; call `show_interstitial()` twice and assert the second returns `False`; then set `_last_interstitial_at` to `now - 31` and assert `True` is allowed. Prefer monkeypatching `time.monotonic` over direct private-state bashing.
- **Risk if ignored:** Guard defects (e.g. timer consumed on failed show, source audit F3 `ad_service.py:179-192`) ship untested — user-visible UX defect.

### F3 · P2 · ID-handling test is blind to prod==test aliasing; no USE_TEST_IDS=False coverage
- **Where:** `tests/test_ads.py:62-66`; `src/services/ad_service.py:27-30, 46-49`; `src/components/banner_ad.py:20-22`
- **What:** `test_test_ids_are_used_while_no_production_account_exists` asserts `USE_TEST_IDS is True` and `"3940256099942544" in service.interstitial_id`. This passes identically even if the production ID were wrong, because `INTERSTITIAL_ID_ANDROID_PROD` == `INTERSTITIAL_ID_ANDROID_TEST` (both `ca-app-pub-3940256099942544/1033173712`, `ad_service.py:29-30`). Same alias exists for banners (`BANNER_ID_ANDROID_PROD` == `BANNER_ID_ANDROID_TEST`, both `…/9214589741`, `banner_ad.py:20-21`). No test flips `USE_TEST_IDS` to `False`; no inequality assertion pins prod ≠ test.
- **Fix / opportunity:** Add a test with `USE_TEST_IDS = False` expecting a different ID; add a source-level assertion `INTERSTITIAL_ID_ANDROID_PROD != INTERSTITIAL_ID_ANDROID_TEST` (and banner equivalents) so a regressed copy-paste fails the suite. Source remediation (real prod IDs, env/build flag, CI guard) is deferred to M5 per D-017.6 — the test can still pin the inequality now.
- **Risk if ignored:** Production build serving Google sample IDs → invalid traffic, no fill, AdMob account-ban risk (P1 per source audit F1; coverage gap here).

### F4 · P3 · Half of AdService never exercised: show_privacy_options, preload_interstitial, _handle_close, fresh-instance show
- **Where:** `tests/test_ads.py` (zero tests for these paths); `src/services/ad_service.py:96-118` (`show_privacy_options`), `:122-154` (`preload_interstitial`), `:156-164` (`_handle_close`), `:197-227` (fresh interstitial branch); flet API `flet_ads/interstitial_ad.py:5-37`
- **What:** No coverage of the `PrivacyOptionsRequirementStatus` branching (`ad_service.py:105-107`), preload consent-gate + `InterstitialAd` construction + `page.services` registration (`:128-153`), `_handle_close` release + `on_close` callback (`:156-164`), or the fresh-instance branch with its `on_load`/`on_error` closures (`:197-227`).
- **Fix / opportunity:** Add tests with mocked `fta.InterstitialAd.show` and ConsentManager; assert the constructor receives `unit_id == service.interstitial_id`; assert `on_close` fires and `_shown_interstitial` is released.
- **Risk if ignored:** Regressions in preload/show/close lifecycle go undetected (P2 correctness).

### F5 · P3 · close() test covers only the self.interstitial branch
- **Where:** `tests/test_ads.py:48-59`; `src/services/ad_service.py:229-243`
- **What:** `test_close_releases_services` sets only `service.interstitial = ad`; `_shown_interstitial` stays `None`, so the release loop at `ad_service.py:231-235` never exercises releasing a shown interstitial. The `_release_service` ValueError path (`ad_service.py:239-243`, item absent from list) is also untested.
- **Fix / opportunity:** Set both `interstitial` and `_shown_interstitial`, assert both are removed from `page.services`; add a case releasing an already-absent item.
- **Risk if ignored:** Service-ref leaks on shutdown undetected (minor P3).

### F6 · P3 · Banner-pool test never asserts the control it produces (desktop returns a 0×0 ft.Container)
- **Where:** `tests/test_ads.py:68-78`; `src/components/banner_ad.py:31-57`
- **What:** With `mobile=False`, `pooled_banner_ad` → `build_banner_ad` returns `ft.Container(width=0, height=0)` (`banner_ad.py:54-55`); the test asserts only identity reuse (`first is second`, `:75`) and re-creation after `clear_banner_pool` (`:78`), never the control type/size or per-slot isolation. The mobile path that builds a real `fta.BannerAd` (`banner_ad.py:60-68`, `flet_ads/banner_ad.py:8-9`) is untested.
- **Fix / opportunity:** Assert `isinstance(first, ft.Container)` with `width == height == 0` on the desktop page; add a mobile test patching `fta.BannerAd`.
- **Risk if ignored:** Shape regressions in the no-ad fallback undetected (polish P3).

## Missed capabilities

N/A — this is a file audit, not a dependency audit. (Skipped per BRIEF report contract.)

## Verified-good list

- `pytest tests/test_ads.py` → `6 passed in 0.87s` (pytest 9.1.1, Python 3.14.9, rootdir pyproject.toml) — imports `services.ad_service` / `components.banner_ad` resolve, `asyncio.run` per test is loop-safe, no cross-test leakage.
- Assertions match the branches they target: `:23-29` ↔ `ad_service.py:65-68`; `:32-36` ↔ `ad_service.py:167`; `:39-45` ↔ `ad_service.py:170-178`; `:48-59` ↔ `ad_service.py:229-236`; `:62-66` ↔ `ad_service.py:27-30, 46-49`; `:68-78` ↔ `banner_ad.py:31-40`.
- `flet_ads` API used by the app was verified exact against installed source: `ConsentManager` (`flet_ads/consent_manager.py:14`, methods `:44-126`), `InterstitialAd` (`flet_ads/interstitial_ad.py:5-6`, `show :30-37`), `BannerAd` (`flet_ads/banner_ad.py:8-9`), `BaseAd` handlers (`flet_ads/base_ad.py:21-57`), `PrivacyOptionsRequirementStatus` (`flet_ads/types.py:171-193`). Note: the **tests** exercise none of these on mobile — see F1/F4.
- `test_interval_guard_blocks_a_back_to_back_show` correctly reproduces the guard's branch condition (`elapsed < INTERSTITIAL_MIN_INTERVAL_SEC` at `ad_service.py:172`) given state-bashed `:44`.

## Unverified

- Real `fta.ConsentManager`/`InterstitialAd` attached to a genuine `ft.Page` on a device — requires a device build (D-005 gate); not runnable here. The `RuntimeError: Control must be added to the page first` above was reproduced against a MagicMock page, not a real page — UNVERIFIED on real flet Page.
- Whether appending real flet_ads controls to `page.services` (`ad_service.py:71-72`, `148-149`, `220-221`) satisfies flet's "added to the page" requirement on a real page — UNVERIFIED.
- Whether the CI/test environment outside this `.venv` has `flet_ads` installed (`_HAS_ADS` is True here, verified by directory listing and successful import) — UNVERIFIED elsewhere.
- Device-level behavior of the flet_ads Dart extension + native AdMob SDK — UNVERIFIED (D-005).

No application code, tests, pyproject, or docs were modified; this is a read-only audit producing one report file.
