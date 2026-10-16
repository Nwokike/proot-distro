# dep-flet-ads.md — flet-ads 1.0.4 (official flet-dev AdMob extension)

Verified 2026-10-16 against `.venv/Lib/site-packages/flet_ads` (R4 study). Not third-party: it's part of the flet monorepo (`sdk/python/packages/flet-ads`).

## Identity & lockstep
- `Requires-Dist: flet==1.0.4` — **exact pin**. Bump `flet` and `flet-ads` as an atomic pair (same as flet-audio/camera/video family). A lone flet bump = resolver conflict or broken protocol.
- Bundles `flutter/flet_ads/` (pubspec depends on `google_mobile_ads: ^9.0.0`); the flet build pipeline auto-injects it as a path dep — the app never edits its pubspec.

## Surface
- `BannerAd` (LayoutControl + `AdWidget`; occupies layout space — cannot float over a terminal; reserve a permanent row or omit), `InterstitialAd` (Service; **single-use: each instance can `show()` once**; one live ad at a time — create per break), `ConsentManager` (Service; UMP flow: `request_consent_info_update()` → `load_and_show_consent_form_if_required()` → gate on `can_request_ads()`), `NativeAd` exists on disk but is **unexported from `__init__` and its Dart case is commented out — unusable in 1.0.4**. **No rewarded ads exist in this version.**
- Events: `on_load/on_error/on_open/on_close/on_impression/on_click` (+ `on_paid` on banner).
- **Mobile-only: `before_update` raises `FletUnsupportedPlatformException` on web/desktop** → ads MUST be platform-gated in our app (also required so `flet run` preview doesn't crash).
- **`APPLICATION_ID` must come from `[tool.flet.android.meta_data]`** (`com.google.android.gms.ads.APPLICATION_ID`) — the package supplies no manifest bits, no patcher, no default app ID (that's why FFmpeg Lite carries the meta_data + a CI guard against test IDs).
- Test IDs (docstrings): banner Android `…/9214589741`, interstitial Android `…/1033173712`; Dart fallbacks exist but banner's fallback mistakenly uses the interstitial IDs (only matters if `unit_id` omitted — always pass explicit IDs).

## Verdict for our app
Ads design: interstitial at natural breaks + UMP consent at launch, both Service-based and mobile-gated; banner only if a screen has a spare row (terminal screens don't → likely no banner). Add the production-ID guard to CI (FFmpeg Lite precedent).
