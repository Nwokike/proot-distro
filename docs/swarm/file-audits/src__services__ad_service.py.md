# src/services/ad_service.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** src/services/ad_service.py · src/components/banner_ad.py · tests/test_ads.py · docs/decisions.md D-017 · Sherlock/src/services/ad_service.py · .venv/lib/python3.14/site-packages/flet_ads/* · .venv/lib/python3.14/site-packages/flet/* · Date: 2026-10-24

## What it does / how the app uses it

`AdService` manages AdMob interstitial ads and UMP (Google User Messaging Platform) consent, mirroring Sherlock's `AdService` exactly per D-017.6. It (1) runs the UMP consent flow at launch (`gather_consent`), (2) gate interstitials behind consent + a 30s minimum-interval guard (`show_interstitial`), (3) preloads an interstitial ahead of time (`preload_interstitial`) and restocks it after each show, (4) releases spent services from `page.services` on `close()`, (5) clears the module-level banner pool, and (6) exposes `show_privacy_options()` for a settings entry point. `USE_TEST_IDS = True` hardcodes Google's public sample unit IDs; production IDs + a CI guard are deferred to M5 (D-017.6). The AdMob `APPLICATION_ID` (needed or the Dart extension kills the process at launch, D-017.8) is declared at `pyproject.toml:74-75` as Google's sample test app id and asserted present by CI. Every `flet_ads` API used was verified against the installed source with `file:line` below.

## Findings

### F1 · P1 · Production interstitial unit ID equals Google's test ID (banners too)
- **Where:** `src/services/ad_service.py:29-30`; `src/components/banner_ad.py:20-21`
- **What:** `INTERSTITIAL_ID_ANDROID_PROD` (`src/services/ad_service.py:30`) is byte-identical to `INTERSTITIAL_ID_ANDROID_TEST` (`:29`, both `ca-app-pub-3940256099942544/1033173712`). Same for banners: `BANNER_ID_ANDROID_PROD` == `BANNER_ID_ANDROID_TEST` (`banner_ad.py:20-21`, both `…/9214589741`). `USE_TEST_IDS` is a hardcoded source constant, not a build flavor (confirmed by `docs/swarm/dependency-utilization/flet-ads.md:130-134`). If `USE_TEST_IDS` is ever flipped to False (D-017.6 plans production IDs at M5), the app would serve Google's sample publisher as "production" — invalid traffic / no fill / AdMob account-ban risk. CI only asserts `APPLICATION_ID` presence (`pyproject.toml:74-75`, `.github/workflows/app.yml:231-232,265-268`); it never inspects ad-unit values, and no production-ID guard exists yet (the FFmpeg-house precedent `docs/reference/app-ffmpeg.md:16` is not implemented here).
- **Evidence:** `src/services/ad_service.py:27-30`; `src/components/banner_ad.py:20-22`; `docs/swarm/dependency-utilization/flet-ads.md:130-134`; `docs/decisions.md D-017.6 (:112-115)`.
- **Fix / opportunity:** Source unit IDs from an env/build flag (not a source constant) so a release build cannot silently use `3940256099942544`; add the FFmpeg-style CI guard that greps sources/artifact for `3940256099942544` and fails the release job. Deferred per D-017.6 to M5 — make that hand-off safe now rather than shipping prod test IDs.
- **Risk if ignored:** AdMob policy violation, invalid traffic, no real revenue, possible account suspension when production IDs land at M5.

### F2 · P1 · UMP consent failure defaults to allowing ads — swallowed bug, violates D-017.9
- **Where:** `src/services/ad_service.py:92-94` (`gather_consent` except block)
- **What:** `except Exception` logs a warning then sets `self._can_request_ads = True`, so when UMP fails the app serves ads **without consent**. D-017.9 ruling (`docs/decisions.md:128-131`): "No swallowed bugs… it raises with the real reason and the controller surfaces it in the UI (`state.data_note`)." Sherlock's copy makes the same choice (`Sherlock/src/services/ad_service.py:127-131`), but D-017.9 binds this app. Privacy/GDPR compliance risk in EEA/UK — ads served before/without consent.
- **Evidence:** `src/services/ad_service.py:92-94`; `docs/decisions.md D-017.9 (:128-131)`; `Sherlock/src/services/ad_service.py:127-131` (same pattern, not a defense).
- **Fix / opportunity:** On UMP failure default `_can_request_ads = False` (no ads without consent) and surface/re-raise the reason via the controller's `state.data_note` per D-017.9, rather than silently permitting ads.
- **Risk if ignored:** GDPR/EEA non-compliance, serving ads without user consent, regulatory exposure in regulated regions.

### F3 · P2 · Interval guard consumes the 30s timer even when the show fails
- **Where:** `src/services/ad_service.py:179-192`
- **What:** `self._last_interstitial_at = time.monotonic()` (`:179`) is assigned **before** `await ad_to_show.show()` (`:185`). On show failure (`:188-192`) the timer is already consumed, forcing a full 30s wait despite no ad having been shown. Sherlock's copy is identical (`Sherlock/src/services/ad_service.py:242-260`) — a shared robustness defect, not unique to this file.
- **Evidence:** `src/services/ad_service.py:170-195`; `Sherlock/src/services/ad_service.py:230-263`.
- **Fix / opportunity:** Move the timer assignment to after a successful show, or reset it in the `except` path so a failed show does not penalize the user with a longer-than-necessary gap.
- **Risk if ignored:** UX defect — longer-than-necessary gaps between interstitials after a failed load; minor, no compliance impact.

## Missed capabilities
N/A — this is a file audit, not a dependency audit. (Skipped per BRIEF report contract.)

## Verified-good list
Everything below was checked against installed source with `file:line`; no change needed.
- `USE_TEST_IDS = True` (`src/services/ad_service.py:27`) is correct per D-017.6; test unit IDs are Google's public samples — interstitial `flet_ads/interstitial_ad.py:20-21`, banner `flet_ads/banner_ad.py:18-19`.
- AdMob `APPLICATION_ID` configured correctly at `pyproject.toml:74-75` (`ca-app-pub-3940256099942544~3347511713`, the D-017.8-settled value `:122-127`); CI asserts presence in merged manifest — D-017.8 crash (app-5) mitigated, **not** a bug in this build. UNVERIFIED only at device level (D-005 gate).
- Mobile gating: `_is_mobile()` (`ad_service.py:51-55`) uses `page.platform.is_mobile()` — `PagePlatform.is_mobile()` verified at `flet/controls/types.py:849` (True for IOS/ANDROID); `page.platform` is `Optional[PagePlatform] = None` (`flet/controls/page.py:595`), defensively caught by `ad_service.py:52-55`; `page.web` guard (`ad_service.py:53`, `banner_ad.py:54`) redundant but harmless since PagePlatform has no WEB value.
- Consent flow skipped on non-mobile (`ad_service.py:65-68`); `_can_request_ads=True` there is fine because `show_interstitial` re-gates on `_is_mobile()` (`:167`).
- All `flet_ads` APIs used exist with exact signatures: `ConsentManager` (`flet_ads/consent_manager.py:14`, `@ft.control`, `ft.Service`); `request_consent_info_update` (`:44-58`); `load_and_show_consent_form_if_required` (`:108-116`); `can_request_ads` (`:85-92`); `get_privacy_options_requirement_status` (`:94-106`); `show_privacy_options_form` (`:118-126`); `PrivacyOptionsRequirementStatus.REQUIRED` (`flet_ads/types.py:187`); `InterstitialAd` (`flet_ads/interstitial_ad.py:5-6`); `show` (`:30-37`); `BaseAd` handlers `unit_id`/on_load/on_error/on_close (`flet_ads/base_ad.py:21-57`); `BannerAd` (`flet_ads/banner_ad.py:8-9`, `@ft.control`, `ft.LayoutControl, BaseAd`).
- Flet `Page.services` property (`flet/controls/base_page.py:823-832`); `page.run_task` sets page context via `_context_page.set(self)` before running (`flet/controls/page.py:929-945`); Service auto-registers with current page at construction (`flet/controls/services/service.py:36-65`); `unregister_services` drops refcount <=3 on Python 3.14 (`flet/controls/page.py:232`) — app keeps strong Python refs in `self.interstitial`/`self._shown_interstitial` **and** appends to `page.services` (belt-and-suspenders, matches Sherlock).
- Service release on `close()` (`ad_service.py:229-236`); banner pool cleared via `clear_banner_pool()` (`banner_ad.py:39-40`).
- `tests/test_ads.py` assertions consistent: non-mobile skips consent (`:23-29`), desktop show skipped (`:32-36`), interval guard (`:39-46`), close releases services (`:48-59`), test IDs used (`:62-66`), banner pool reuse (`:68-78`).
- `ft.context.page` exists (`flet/controls/context.py`, re-exported `flet/context`) and is used defensively in `banner_ad.py:46`.

## Unverified
- Production unit IDs do not exist anywhere yet (no placeholder); whether M5 supplies real AdMob unit IDs and the CI production-ID guard is deferred (`docs/decisions.md D-017.6 :112-115`, deferred list :135-136). UNVERIFIED.
- Whether the controller surfaces `show_privacy_options()` / consent outcomes in the UI via `state.data_note` per D-017.9 — outside `ad_service.py` scope; UNVERIFIED.
- Device-level behavior of the `flet_ads` Dart extension + native AdMob SDK — only gated via CI device build (D-005); not runnable here; UNVERIFIED.

No application code, tests, or docs were modified; this is a read-only audit producing one report file.