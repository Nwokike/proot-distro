# src/components/banner_ad.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/components/banner_ad.py` (all 92 lines) · `src/services/ad_service.py` · `tests/test_ads.py` · `docs/decisions.md` D-017 (§6-§9) · `/home/maikel/.zcode/workspace/default/DDGS/src/core/styles.py:12-78` (`build_banner_ad`) · installed `flet==1.0.4` (`.venv/lib/python3.14/site-packages/flet/`) and `flet_ads` (`.venv/lib/python3.14/site-packages/flet_ads/`) · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/components/banner_ad.py` is the single canonical banner builder. It exposes three public functions:

1. `banner_unit_id()` (`:27-28`) — returns the Android test banner id (production id is identical today, deferred to M5 per D-017.15).
2. `pooled_banner_ad(slot, page)` (`:31-36`) — caches a `Control` per slot string in module-global `_BANNER_POOL` (`:24`) so rebuilds reuse one instance.
3. `build_banner_ad(page)` (`:43-92`) — mobile-gates (`page.platform.is_mobile()` + not `page.web`), constructs a `flet_ads.BannerAd` (320x50), and wraps it in a full-width glass/surface container (`expand=True`) centered inside an outer `ft.Row`.

Consumers: `src/screens/views.py:377,553` ("distros-1", "settings-1") and `src/screens/terminal_view.py:181` ("terminal-1", only when not fullscreen per D-017.7). `AdService.close()` calls `clear_banner_pool()` (`src/services/ad_service.py:236`).

---

## Findings

### F1 · P1 · Banner ad identity and `USE_TEST_IDS` flag are duplicated, independent of `AdService`
- **Where:** `src/components/banner_ad.py:20-22, 27-28` (`BANNER_ID_ANDROID_TEST/PROD`, `USE_TEST_IDS`, `banner_unit_id`) · `src/services/ad_service.py:27-30, 46-50` (`USE_TEST_IDS`, `INTERSTITIAL_ID_*`, `interstitial_id`) · `docs/decisions.md:112-115` (D-017 §6 "Ads follow Sherlock's AdService exactly")
- **What:** D-017 §6 requires ads to follow Sherlock's `AdService` exactly (UMP, preload/show, interval guard, service release, pooled banners). The interstitial path is centralized in `AdService`, but the banner path keeps its own `USE_TEST_IDS` flag and its own id constants. Flipping `AdService.USE_TEST_IDS` (or adding the M5 production id) does not affect banners, so the two surfaces can disagree on test-vs-production and on the production id value. `BANNER_ID_ANDROID_PROD` (`:21`) is also still the Google sample test id, identical to `BANNER_ID_ANDROID_TEST` (`:20`), while DDGS ships a distinct prod id (`ca-app-pub-5679949845754640/9885079510`, `DDGS/src/services/ad_service.py:38`).
- **Evidence:** `src/components/banner_ad.py:20-22` defines its own flag/ids; `src/services/ad_service.py:27-30` defines a separate flag/ids; no `banner_id` property exists on `AdService` (contrast DDGS `src/services/ad_service.py:53-56`).
- **Fix / opportunity:** Add a `banner_id` property to `AdService` (mirroring `interstitial_id`, `:46-50`) and `BANNER_ID_ANDROID_*` constants (`:29-30`), store `AdService` on `state` (or pass it in), and have `build_banner_ad`/`pooled_banner_ad` resolve `unit_id` from it; share a single `USE_TEST_IDS`. Remove the duplicated constants from `banner_ad.py`.
- **Risk if ignored:** Banner and interstitial can run on different id regimes after the M5 production flip; silent revenue/compliance drift.

### F2 · P2 · Banner ads are not consent-gated
- **Where:** `src/components/banner_ad.py:43-92` (`build_banner_ad` never reads consent) · `src/services/ad_service.py:39, 59-94` (`_can_request_ads`, `gather_consent`) · `src/app_controller.py:92` (consent at launch)
- **What:** `AdService` runs the UMP flow at launch and records `_can_request_ads` (`:75`), and interstitials honor it (`show_interstitial`, `:167`). Banners do not: `build_banner_ad` constructs and returns a live `fta.BannerAd` whenever the platform is mobile, regardless of consent outcome. In a regulated region where the user denies/withdraws consent, banners still request ads.
- **Evidence:** `src/services/ad_service.py:131-133` skips interstitial preload when `not self._can_request_ads`; no equivalent check exists in `src/components/banner_ad.py`.
- **Fix / opportunity:** Gate banner construction on consent: resolve the `AdService` (see F1) and return the zero-size placeholder when `not ad_service._can_request_ads` (or expose a public `can_request_ads` property). Because banners are pooled, re-check on consent change or clear the pool when consent flips.
- **Risk if ignored:** Ads requested without consent in EEA/UK — compliance exposure.

### F3 · P2 · Pooling caches the desktop/empty placeholder, so a slot can be permanently blank
- **Where:** `src/components/banner_ad.py:31-36` (`pooled_banner_ad`) · `:43-57` (mobile gate returns `ft.Container(width=0, height=0)`)
- **What:** `pooled_banner_ad` caches whatever `build_banner_ad` returns on the first call for a slot, including the zero-size placeholder produced on desktop, when `page` is `None`/contextless, or when `ft.context.page` resolution fails (`:44-48`). That cached empty container is then reused for every later call, including on a real mobile page, so the slot never shows an ad. The test in `tests/test_ads.py:68-78` only asserts identity, so this regression is not caught.
- **Evidence:** `:32-35` `_BANNER_POOL.get(slot)` → if present returns cached instance unconditionally; `:44-48` returns empty container on page-resolution failure; `:50-57` returns empty container on non-mobile.
- **Fix / opportunity:** Only pool successful (mobile) ad instances; return a fresh placeholder for non-mobile/contextless calls without caching, or key the pool by `(slot, page)` and skip caching of zero-size placeholders. Add a test asserting a desktop-first call does not poison a later mobile call.
- **Risk if ignored:** Banners silently never appear for a slot if it is first evaluated in a non-mobile/test context; intermittent blank ad slots.

### F4 · P2 · Overly broad exception handling hides real failures
- **Where:** `src/components/banner_ad.py:44-48, 53-57, 59-71`
- **What:** Three separate `except Exception` blocks swallow every error (including programming errors and `FletUnsupportedPlatformException`) and return a zero-size container. DDGS's reference catches only `ValueError, TypeError, OSError, RuntimeError, ConnectionError, ImportError` (`DDGS/src/core/styles.py:52-59`); D-017 §9 also rules out log-and-return-empty for service failures. The broad catch makes a malformed call or a missing attribute indistinguishable from a legitimate desktop/no-ads case.
- **Evidence:** `:47-48` `except Exception: return ft.Container(width=0, height=0)`; `:56-57` same; `:69-71` `except Exception as e: ... return ft.Container(width=0, height=0)`.
- **Fix / opportunity:** Narrow the catches to the specific exceptions DDGS uses (`:52-59`) for the construction block; for page/platform resolution, check explicitly (`if page is None`, `if page.platform is None`) instead of bare `except Exception`.
- **Risk if ignored:** Real bugs (e.g. wrong argument types) are masked as "no ad available"; debugging impossible.

### F5 · P2 · Module-global pool is not page-scoped and can bind a control to a stale page
- **Where:** `src/components/banner_ad.py:24` (`_BANNER_POOL: dict[str, Control]`) · `:31-36` · `src/services/ad_service.py:236` (`clear_banner_pool`)
- **What:** The pool is process-global and keyed only by slot. A cached `ft.Control` (and its `fta.BannerAd`) is bound to the page it was first built on. In a multi-page/multi-session process, or after a page reconnect, reusing the instance can attach a control to a stale/foreign page. `clear_banner_pool()` is only invoked on `AdService.close()` (`:236`), i.e. app shutdown, not per page.
- **Evidence:** `:24` global dict; `:34` `ad = build_banner_ad(page)` uses the page at first build only; `src/services/ad_service.py:236` calls `clear_banner_pool()` only in `close()`.
- **Fix / opportunity:** Scope the pool to the page (e.g. `dict[ft.Page, dict[str, Control]]` or store on `page`), and clear on page disconnect. At minimum document the single-page assumption.
- **Risk if ignored:** Stale control/page binding in multi-page or reconnect scenarios (UNVERIFIED on-device; label UNVERIFIED).

### F6 · P3 · Styling diverges from the DDGS/Sherlock glass pattern
- **Where:** `src/components/banner_ad.py:73-92` · `DDGS/src/core/styles.py:63-78` (`adaptive_glass_bg`, `adaptive_glass_border`, `tokens`)
- **What:** The app uses `theme.surface()` / `theme.surface_alt()` solid colors (`:85-86`) and `padding=8`/`border_radius=12`/`spacing=4`, while DDGS uses `adaptive_glass_bg(page)`/`adaptive_glass_border(page)` with token-based spacing/radius. Minor visual inconsistency with the reference; not a functional bug.
- **Evidence:** `src/components/banner_ad.py:83-86` vs `DDGS/src/core/styles.py:65-77`.
- **Fix / opportunity:** Align to `adaptive_glass_bg`/`adaptive_glass_border` if the house design requires glass; otherwise document the intentional divergence.
- **Risk if ignored:** Cosmetic drift only.

### F7 · P3 · `build_banner_ad` has no `unit_id` override (API parity with DDGS)
- **Where:** `src/components/banner_ad.py:43` signature `build_banner_ad(page=None)` · `DDGS/src/core/styles.py:12` signature `build_banner_ad(page, unit_id=None)`
- **What:** DDGS allows callers to pass a `unit_id`; the app hard-codes `banner_unit_id()`. Limits testability and reuse (DDGS tests pass `unit_id="ca-app-pub-test/banner"`, `DDGS/tests/test_banner_design.py:53,80,106,114`).
- **Evidence:** `src/components/banner_ad.py:43` vs `DDGS/src/core/styles.py:12`.
- **Fix / opportunity:** Add `unit_id: str | None = None` parameter, defaulting to `banner_unit_id()` / `AdService.banner_id`.
- **Risk if ignored:** Tests cannot inject a fake unit id; minor.

---

## Missed capabilities (dependency audits only)

Not applicable — this is a file audit. (DDGS's `build_banner_ad` already demonstrates the `unit_id` override and specific exception catches; the app does not use them — see F4, F7.)

---

## Verified-good list

1. **Mobile gating is correct and matches `flet_ads` contract:** `page.platform.is_mobile()` (`.venv/.../flet/controls/types.py:843-849`) and `page.web` (`.venv/.../flet/controls/page.py:516`) are checked before constructing `fta.BannerAd`; `fta.BannerAd.before_update` (`.venv/.../flet_ads/base_ad.py:70-75`) raises `FletUnsupportedPlatformException` on web/non-mobile, which the pre-check avoids.
2. **Sizing is correct:** `fta.BannerAd(width=320, height=50)` (`.venv/.../flet_ads/base_ad.py` inherits `LayoutControl.width/height`, `.venv/.../flet/controls/control.py:66-73`) plus the inner `ft.Container(content=ad, width=320, height=50)` (`:76`); 320x50 matches the AdMob banner standard and DDGS (`DDGS/src/core/styles.py:48-49`).
3. **Full-width wrapper / layout-width behavior:** outer `ft.Row(controls=[banner], alignment=ft.MainAxisAlignment.CENTER)` with `banner` `expand=True` matches the DDGS docstring rationale ("rows fill what their parent offers"; `DDGS/src/core/styles.py:15-23, 65-78`). `ft.Row`, `ft.MainAxisAlignment.CENTER`, `ft.CrossAxisAlignment.CENTER`, `ft.Border.all` all exist (spot-checked).
4. **Pooling per slot works as tested:** `tests/test_ads.py:68-78` passes (identity reuse + clear invalidates).
5. **`ft.context.page` usage is valid:** `.venv/.../flet/controls/context.py:46-69`; raises `RuntimeError` outside a page callback, caught by the generic handler.
6. **No imperative widget mutation:** builder returns controls only; complies with D-015.
7. **`fta.BannerAd` constructor params used (`unit_id`, `width`, `height`, `on_load`, `on_error`) all exist:** `flet_ads/banner_ad.py:8-41` (class) and `flet_ads/base_ad.py:21-65` (fields); `on_load`/`on_error` are `BaseAd` fields (`:31-43`).

---

## Unverified

1. **Multi-page/stale-control binding (F5):** whether Flet 1.0.4 permits reusing a `Control` instance across pages without `FletException` — not exercised in tests; label UNVERIFIED.
2. **Consent interaction with banners (F2):** whether the app's `AdService` is reachable from `banner_ad` without plumbing `state.ad_service` — architecture question; label UNVERIFIED.
3. **`page.platform` being `None` on some desktop builds:** handled via broad catch (F4); exact default verified as `Optional[PagePlatform] = None` (`.venv/.../flet/controls/page.py:595`), but the resulting `None.is_mobile()` path is only covered by the broad catch.
4. **Production id value for banners:** deferred to M5 (D-017.15); `BANNER_ID_ANDROID_PROD` currently equals the test id by design.