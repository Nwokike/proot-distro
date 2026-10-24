# flet-ads utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/services/ad_service.py`, `src/components/banner_ad.py`, `src/screens/terminal_view.py`, `src/app_controller.py`, `src/core/shared_services.py`, `src/screens/views.py`, `src/app_shell.py`, `src/main.py`, `src/core/state.py`, `src/state/controller_ctx.py`, `pyproject.toml`, `.github/workflows/app.yml`, `PRIVACY.md`, `tests/test_ads.py`; installed `flet-ads 1.0.4` (`.venv/Lib/site-packages/flet_ads/{__init__,base_ad,banner_ad,interstitial_ad,consent_manager,native_ad,types}.py`, `.venv/Lib/site-packages/flutter/flet_ads/{pubspec.yaml,lib/flet_ads.dart,lib/src/*.dart,lib/utils/*.dart}`), installed `flet 1.0.4` (`controls/page.py`, `controls/base_page.py`, `controls/core/view.py`, `controls/services/service.py`, `controls/types.py`, `components/component.py`, `messaging/session.py`) · **Date:** 2026-10-20

Prior knowledge used, spot-checked against the installed source: `docs/dependency-studies/flet-ads.md`, `docs/reference/dep-flet-ads.md`. Every API claim below was re-verified against `.venv` with a `file:line`; the export surface and the four control classes were additionally verified by instantiating them in the installed interpreter.

## What it does / how the app uses it

`flet-ads` is the app's AdMob monetization layer and it is used in three places:

1. **UMP consent** — `AdService.gather_consent()` creates one `fta.ConsentManager()` (`src/services/ad_service.py:70`), mounts it on `page.services`, and runs the canonical flow `request_consent_info_update` → `load_and_show_consent_form_if_required` → `can_request_ads` (`src/services/ad_service.py:73-75`), then probes `get_privacy_options_requirement_status()` (`src/services/ad_service.py:77`). The controller kicks it off at launch (`src/app_controller.py:91-95`).
2. **Interstitial** — `AdService.preload_interstitial()` builds an `fta.InterstitialAd`, registers it, and `show_interstitial()` shows it behind a 30 s minimum-interval guard (`src/services/ad_service.py:32, 122-227`). It is triggered at the two natural breaks the app has: a completed install (`src/app_controller.py:201-202`) and a completed container removal (`src/app_controller.py:208-209`).
3. **Banner** — a pooled, slot-keyed `fta.BannerAd` builder (`src/components/banner_ad.py`) mounted on three screens: Distros (`src/screens/views.py:377`), Settings (`src/screens/views.py:553`) and the terminal screen (`src/screens/terminal_view.py:181`).

The consent gate (`self._can_request_ads`) is consulted **only** by the interstitial path (`src/services/ad_service.py:131, 167`). The banner path never consults it — that is the central defect of this audit (F1).

The whole surface is mobile-gated (`src/services/ad_service.py:51-55`, `src/components/banner_ad.py:53-57`) because the package raises `FletUnsupportedPlatformException` from `before_update` on desktop/web (`flet_ads/base_ad.py:69-75`, `flet_ads/consent_manager.py:36-42`).

### Verified API surface (no hallucination)

| Claim | Installed evidence |
|---|---|
| Exactly 12 exports; `NativeAd` is **not** exported | `flet_ads/__init__.py:1-29`; runtime: `flet_ads.__all__` = `['AdRequest','BannerAd','BaseAd','ConsentDebugSettings','ConsentManager','ConsentRequestParameters','ConsentStatus','DebugGeography','InterstitialAd','PaidAdEvent','PrecisionType','PrivacyOptionsRequirementStatus']`, `hasattr(flet_ads,'NativeAd')` → `False` |
| `BannerAd` is a `LayoutControl`; `InterstitialAd`/`ConsentManager` are `Service`s | `flet_ads/banner_ad.py:8-9`, `flet_ads/interstitial_ad.py:5-6`, `flet_ads/consent_manager.py:13-14`; runtime `isinstance(b, ft.LayoutControl)` → `True`, `isinstance(i, ft.Service)` → `True` |
| All three are keyword-only (`unit_id` mandatory) | `flet_ads/base_ad.py:8, 21`; runtime `fta.BannerAd()` → `TypeError: BannerAd.__init__() missing 1 required keyword-only argument: 'unit_id'` |
| `AdRequest()` is the default, all six fields `None` | `flet_ads/base_ad.py:26`, `flet_ads/types.py:61-105`; runtime `b.request` → `AdRequest(keywords=None, content_url=None, neighboring_content_urls=None, non_personalized_ads=None, http_timeout=None, extras=None)` |
| `ConsentManager` exposes the 8 UMP methods; `reset()` exists | `flet_ads/consent_manager.py:44, 60, 73, 85, 94, 108, 118, 128`; runtime dir() confirms all eight |
| `BannerAd.on_paid` / `on_will_dismiss` exist but are unused by the app | `flet_ads/banner_ad.py:28, 36`; runtime dir() confirms both |
| `InterstitialAd` has **no** `on_paid` | `flet_ads/interstitial_ad.py:30-37`; runtime dir() has no `on_paid` |
| Dart maps `BannerAd`→widget, `InterstitialAd`/`ConsentManager`→services, `NativeAd`→`null` | `flutter/flet_ads/lib/src/extension.dart:18-27, 29-41` |
| `google_mobile_ads: ^9.0.0` is the only Dart ad dependency; no patcher ships | `flutter/flet_ads/pubspec.yaml:15`; no `patcher*` file under `flet_ads*` in site-packages |

### How flet 1.0.4 actually mounts a service (needed to judge the app's lifetime code)

`page.services` is **not** the framework's client registry — it is a Python-side keep-alive list:

- `page.services` → `BasePage.services` → `self.__root_view().services` (`flet/controls/base_page.py:823-828`) → `View.services`, a plain list declared `metadata={"skip": True}` (`flet/controls/core/view.py:144`) and therefore excluded from serialization/patching (`flet/controls/object_patch.py:1205, 1271, 1397, 1660, 1714`). Nothing in the flet package reads it except the property itself.
- The client registry is `Page._services` → `ServiceRegistry._services` (`flet/controls/page.py:102, 714`). It is populated **only** by `Service.__post_init__` → `page._services.register_service(self)` (`flet/controls/services/service.py:47-54`; `flet/controls/page.py:120-139`), i.e. automatically at construction, using `ft.context.page`.
- It is pruned by **refcount**, not by the app: `ServiceRegistry.unregister_services()` drops services whose `sys.getrefcount` is `<= 3` (`flet/controls/page.py:228-245`), called after every event (`flet/messaging/session.py:570`).

Consequence: `page.services.append(x)` is the *keep-alive* idiom (it holds the extra reference that keeps the service above the prune threshold) and `page.services.remove(x)` is what releases it so the next event disposes it. This matches the house note verbatim (`docs/reference/app-sherlock.md:18`: "Flet drops services with refcount ≤3 after every event → `page.services.append(...)` + `mount_shared_services` once"). The app uses that idiom correctly — but it does **not** need the `append` for registration (that is automatic), and the release it performs is one event later than it looks (F7).

## Findings

### F1 · P1 · Banner ads are requested with no consent decision in hand
- **Where:** `src/components/banner_ad.py:53-68` (constructs `fta.BannerAd` with the default empty `AdRequest()` and no consent check), mounted at `src/screens/views.py:377`, `src/screens/views.py:553`, `src/screens/terminal_view.py:181`; the consent gate exists only on the interstitial path (`src/services/ad_service.py:131, 167`); the consent flow starts at `src/app_controller.py:91-95`, i.e. *after* the first render at `src/app_controller.py:85`; the gate itself defaults to **allow** (`src/services/ad_service.py:39`).
- **What:** `can_request_ads()` is the documented gate for every ad load (`flet_ads/consent_manager.py:85-92`; the package docstring at `flet_ads/consent_manager.py:22-30` spells out the launch order). The banner path never reads it, so a `BannerAd` is built and loaded during the first render of Distros/Settings/Terminal — while `request_consent_info_update()` (a network round-trip, `flutter/flet_ads/lib/src/consent_manager.dart:22-36`) is still in flight. On the Dart side the load is unconditional; there is no second consent check there either.
- **Evidence:**
  ```
  src/components/banner_ad.py:62:        ad = fta.BannerAd(
  src/components/banner_ad.py:63:            unit_id=banner_unit_id(),
  src/components/banner_ad.py:64:            width=320,
  src/components/banner_ad.py:65:            height=50,
  src/components/banner_ad.py:66:            on_load=lambda _e: logger.info("BannerAd loaded"),
  src/components/banner_ad.py:67:            on_error=lambda e: logger.warning("BannerAd load error: %s", getattr(e, "data", e)),
  ```
  ```
  flutter/flet_ads/lib/src/banner.dart:26:    BannerAd bannerAd = BannerAd(
  flutter/flet_ads/lib/src/banner.dart:27:      adUnitId: widget.control.getString("unit_id", testAdUnitId)!,
  flutter/flet_ads/lib/src/banner.dart:28:      request:
  flutter/flet_ads/lib/src/banner.dart:29:          parseAdRequest(widget.control.get("request"), const AdRequest())!,
  flutter/flet_ads/lib/src/banner.dart:30:      size: AdSize.banner,
  ...
  flutter/flet_ads/lib/src/banner.dart:77:    if (!_isLoaded) {
  flutter/flet_ads/lib/src/banner.dart:78:      bannerAd.load();
  flutter/flet_ads/lib/src/banner.dart:79:    }
  ```
  `grep -rn "_can_request_ads" src/` shows the flag read only at `src/services/ad_service.py:131` and `:167` — the banner builder (`src/components/banner_ad.py`) does not import `AdService` at all.
- **Fix / opportunity:** Make the banner obey the same gate. Cheapest correct shape: keep one `AppState` flag (or read `AdService._can_request_ads` through `ControllerMethodsCtx`) and render the zero-size placeholder until the consent promise resolves; build the `BannerAd` only once `can_request_ads()` has been answered. While there, give the request an explicit `AdRequest(non_personalized_ads=True)` fallback so a non-consenting region still gets an untargeted fill instead of nothing (`flet_ads/types.py:87`).
- **Risk if ignored:** Ad requests are issued before any consent decision in regulated regions. That is the exact pattern UMP/AdMob policy forbids, it is inconsistent with the app's own `PRIVACY.md:37` ("consent is requested and managed via Google's User Messaging Platform (UMP) at application launch"), and it puts the Play data-safety declaration at risk.

### F2 · P1 · A failed UMP flow is treated as "consent granted"
- **Where:** `src/services/ad_service.py:92-94`.
- **What:** Both UMP steps raise on failure — `requestConsentInfoUpdate` completes with an error (`flutter/flet_ads/lib/src/consent_manager.dart:29-34`, "Consent info update failed (code): msg") and `loadAndShowConsentFormIfRequired` completes with a form error (`flutter/flet_ads/lib/src/consent_manager.dart:54-62`, "Consent form error (code): msg"). The app catches both under one `except` and **sets `_can_request_ads = True`**, i.e. a failure to ask for consent is interpreted as permission to serve ads. The banner (F1) is then ungated and the interstitial is explicitly enabled.
- **Evidence:**
  ```
  src/services/ad_service.py:92:        except Exception as e:
  src/services/ad_service.py:93:            logger.warning("AdService: UMP consent flow failed, defaulting to allow ads: %s", e)
  src/services/ad_service.py:94:            self._can_request_ads = True
  ```
  The comment itself states the policy inversion.
- **Fix / opportunity:** Default to the safe side: `self._can_request_ads = False` on failure, keep serving only `non_personalized_ads=True` requests, and surface the reason in `state.data_note` (the app already has that channel — `src/app_controller.py:141-159`, and D-017.9 at `docs/decisions.md:128` requires it).
- **Risk if ignored:** On any transient network error or UMP form error in the EEA/UK, the app requests personalized ads without a collected decision — a direct UMP violation and a repeat-offender trigger for an AdMob account.

### F3 · P2 · `show()` is called before the interstitial has loaded
- **Where:** `src/services/ad_service.py:135-154` (preload), `:137` (`on_load` only logs), `:180-195` (`show()`), `:197-227` (the fresh-instance fallback).
- **What:** The package has **no** `load()` API — the load is coupled to service init (`flutter/flet_ads/lib/src/interstitial.dart:18-51`) and the only completion signal is the `on_load` event. The app treats "constructed and registered" as "loaded": `preload_interstitial` logs *"interstitial preloaded"* immediately, and `show_interstitial` calls `await ad_to_show.show()` with no loaded gate. Dart's `show` is a **null-safe no-op** when the native ad is not in the static slot (`flutter/flet_ads/lib/src/interstitial.dart:57-59`: `_interstitialAd?.show();`). The first interstitial of a session — the one preloaded at `src/app_controller.py:93` — is therefore very likely shown before its load completes, and the failure is silent: `show()` returns normally, the app logs *"InterstitialAd shown"*, and no ad appears.
- **Evidence:**
  ```
  src/services/ad_service.py:154:        logger.info("AdService: interstitial preloaded (unit=%s)", self.interstitial_id)
  ...
  src/services/ad_service.py:137:                on_load=lambda _e: logger.info("InterstitialAd loaded"),
  ...
  src/services/ad_service.py:185:                await ad_to_show.show()
  src/services/ad_service.py:186:                logger.info("InterstitialAd shown (preloaded instance)")
  ```
  ```
  flutter/flet_ads/lib/src/interstitial.dart:18:    InterstitialAd.load(
  ...
  flutter/flet_ads/lib/src/interstitial.dart:56:      case "show":
  flutter/flet_ads/lib/src/interstitial.dart:57:        _interstitialAd?.show();
  flutter/flet_ads/lib/src/interstitial.dart:58:        return null;
  ```
  `flet_ads/interstitial_ad.py:30-37` confirms `show()` is a bare `_invoke_method("show")` pass-through with no readiness check.
- **Fix / opportunity:** Track readiness: set `self._interstitial_ready = True` in the `on_load` handler and only `show()` when it is set; on `on_load` of a *fresh* instance (the `:197-227` path) the show is already correct — keep that behaviour and make the preloaded path symmetric. If the ad is not ready when a break arrives, skip it rather than burning the interval (see F11).
- **Risk if ignored:** Silently no-shows: the user sees no ad at a natural break and the app logs success. Revenue silently lost, and the "show" path looks healthy in logs.

### F4 · P2 · Two `InterstitialAd` instances are alive at once, over a shared static native slot
- **Where:** `src/services/ad_service.py:193-195` (the `finally` preloads the next instance *before* the shown ad is dismissed), `:146-153` (the new instance is registered immediately).
- **What:** The package keeps **one static** native ad handle for the whole app (`flutter/flet_ads/lib/src/interstitial.dart:10`: `static InterstitialAd? _interstitialAd;`), overwritten by whichever instance loads last (`:44`). The package's own rule is "use at most one live instance at a time" (`docs/dependency-studies/flet-ads.md` §3.3 rule 3; the same rule restated in `docs/reference/dep-flet-ads.md:10`). The app violates it on every show: after `await ad_to_show.show()` returns (Dart's `show()` returns immediately — the ad is still on screen), the `finally` creates and loads instance #2, which takes over the static slot while instance #1 is still displayed. `InterstitialAdService.dispose()` then disposes whatever is in the static slot (`flutter/flet_ads/lib/src/interstitial.dart:65-69`) — i.e. it can dispose the *preloaded* ad rather than the one it owns.
- **Evidence:**
  ```
  src/services/ad_service.py:193:            finally:
  src/services/ad_service.py:194:                if not self._is_shutting_down:
  src/services/ad_service.py:195:                    await self.preload_interstitial(on_close=self._on_close)
  ```
  ```
  flutter/flet_ads/lib/src/interstitial.dart:10:  static InterstitialAd? _interstitialAd;
  flutter/flet_ads/lib/src/interstitial.dart:44:            _interstitialAd = ad;
  flutter/flet_ads/lib/src/interstitial.dart:66:  void dispose() {
  flutter/flet_ads/lib/src/interstitial.dart:67:    _interstitialAd?.dispose();
  ```
- **Fix / opportunity:** Move the "pre-create the next" step out of the `finally` and into `_handle_close` (which already runs on the ad's `close` event, `src/services/ad_service.py:156-164`), i.e. discard-then-pre-create, exactly as the study prescribes: "Create → await `on_load` → hold → `show()` at the next break → discard → pre-create the next."
- **Risk if ignored:** `show()` may present an ad belonging to a different instance, or a disposed one (the client-side symptom needs a device to pin down — see Unverified). Revenue loss and possible AdMob "invalid impression" reports.

### F5 · P2 · The "production" ad-unit IDs are Google's public test IDs, and no CI guard stops them shipping
- **Where:** `src/services/ad_service.py:29-30`, `src/services/ad_service.py:27`, `src/components/banner_ad.py:20-22`, `pyproject.toml:69-75`, `.github/workflows/app.yml:231-232` and `:265-268`.
- **What:** `INTERSTITIAL_ID_ANDROID_PROD` and `BANNER_ID_ANDROID_PROD` are byte-identical to their `_TEST` twins — both are Google's public sample publisher `ca-app-pub-3940256099942544/…`. `USE_TEST_IDS` is a hardcoded source constant, not a build flavor. The CI asserts only that `com.google.android.gms.ads.APPLICATION_ID` is *present* in the merged manifest; it never inspects its *value*, and it never looks at the ad-unit IDs at all. The FFmpeg house precedent — "AdMob production-ID guard (fails tags if test IDs present)" (`docs/reference/app-ffmpeg.md:16`) — is **not** implemented here.
- **Evidence:**
  ```
  src/services/ad_service.py:29:    INTERSTITIAL_ID_ANDROID_TEST = "ca-app-pub-3940256099942544/1033173712"
  src/services/ad_service.py:30:    INTERSTITIAL_ID_ANDROID_PROD = "ca-app-pub-3940256099942544/1033173712"
  src/components/banner_ad.py:20: BANNER_ID_ANDROID_TEST = "ca-app-pub-3940256099942544/9214589741"
  src/components/banner_ad.py:21: BANNER_ID_ANDROID_PROD = "ca-app-pub-3940256099942544/9214589741"
  ```
  ```
  .github/workflows/app.yml:231:          admob=$(grep -o 'com.google.android.gms.ads.APPLICATION_ID' "$manifest" | head -1 || true)
  .github/workflows/app.yml:265:          if [ -z "$admob" ]; then
  .github/workflows/app.yml:266:            echo "::error::com.google.android.gms.ads.APPLICATION_ID missing — flet-ads needs it or the app dies at launch"
  ```
  `grep -rn "ca-app-pub" .github/` returns **nothing** — there is no production-ID guard in CI. The package's own docstrings mark these as test IDs (`flet_ads/interstitial_ad.py:15-25`: "Remember to replace them in production"; `flet_ads/banner_ad.py:11-21`, same).
- **Fix / opportunity:** D-017.6 (`docs/decisions.md:112`) defers the production IDs + the guard to M5; make that hand-off safe now: (a) select the unit ID from an env/build flag rather than a source constant, so a release build cannot silently use the sample publisher; (b) add the FFmpeg-style CI guard — grep the built artifact / sources for `3940256099942544` and fail the release job. The `APPLICATION_ID` in `pyproject.toml:75` is already Google's correct sample app id (`ca-app-pub-3940256099942544~3347511713`, the value D-017.8 at `docs/decisions.md:122` settled on).
- **Risk if ignored:** When the AdMob account arrives, flipping `USE_TEST_IDS = False` changes nothing: the app keeps serving public test ads, earns nothing, and publishes under Google's sample publisher id. Nothing in CI flags it.

### F6 · P2 · The consent path cannot be exercised — no UMP debug settings
- **Where:** `src/services/ad_service.py:73` — `await self._consent_manager.request_consent_info_update()` is called with **no** parameters.
- **What:** The package ships `ConsentRequestParameters`, `ConsentDebugSettings` and `DebugGeography` (`flet_ads/__init__.py:8, 10, 12`) precisely so a developer can force the EEA form on a registered test device without travelling (`flet_ads/types.py:218-243`, `:245-265`, `:196-216`). The app never uses them, so in this repo the GDPR branch of the UMP flow has never been seen, and `can_request_ads()` can never be observed returning `False` for a decline. The whole compliance path (F1, F2) is therefore unvalidated.
- **Evidence:**
  ```
  src/services/ad_service.py:73:            await self._consent_manager.request_consent_info_update()
  ```
  ```
  flet_ads/types.py:225:    debug_geography: Optional[DebugGeography] = None
  flet_ads/types.py:230:    test_identifiers: Optional[list[str]] = None
  flet_ads/types.py:251:    tag_for_under_age_of_consent: Optional[bool] = None
  ```
  `grep -rn "ConsentDebugSettings\|DebugGeography\|ConsentRequestParameters" src/` returns nothing.
- **Fix / opportunity:** In dev builds, pass `ConsentRequestParameters(consent_debug_settings=ConsentDebugSettings(debug_geography=DebugGeography.EEA, test_identifiers=[...]))`, with the hashed device id taken from `adb logcat` (emulators auto-register — `flet_ads/types.py:235-237`). Keep it out of release builds.
- **Risk if ignored:** The single most important flow in the app is never tested against the real form; every fix for F1/F2 lands blind.

### F7 · P2 · Ad failures are swallowed — a direct violation of D-017.9
- **Where:** `src/services/ad_service.py:86-87`, `:92-94`, `:103-104`, `:116-117`, `:143-145`, `:150-153`, `:215-217`, `:222-225`; `src/components/banner_ad.py:44-48`, `:50-51`, `:56-57`, `:69-71`.
- **What:** D-017.9 (`docs/decisions.md:128`) is an owner ruling: "The service no longer logs-and-returns-empty: it raises with the real reason and the controller surfaces it in the UI (`state.data_note`)". The ad service is the one place that still does exactly what was ruled out — every failure becomes a `logger.warning` and an empty/zero-size result. `state.data_note` is never touched by the ad code (`grep -rn "data_note" src/` → only `src/core/state.py:16`, `src/app_controller.py:159` and `src/screens/views.py:372`). The banner builder is worse: `except Exception: return ft.Container(width=0, height=0)` swallows even programming errors.
- **Evidence:**
  ```
  src/components/banner_ad.py:69:    except Exception as e:
  src/components/banner_ad.py:70:        logger.warning("Failed to load BannerAd: %s", e)
  src/components/banner_ad.py:71:        return ft.Container(width=0, height=0)
  ```
  ```
  src/services/ad_service.py:144:            logger.warning("AdService: failed to construct InterstitialAd: %s", exc)
  src/services/ad_service.py:145:            return
  ```
- **Fix / opportunity:** Route ad failures through the same channel the container service uses: set `state.data_note` (or a dedicated `state.ad_note`) from the controller and show it next to the screen, exactly like `src/app_controller.py:141-159` does for an empty container list. Keep the log line too — the log alone is invisible in a release APK.
- **Risk if ignored:** "Ads silently stopped working" is indistinguishable from "no fill" for both the user and the maintainer; the app's own no-swallowed-bugs standard is not met, and the M5 revenue work has no signal to debug from.

### F8 · P3 · The privacy-options requirement is computed and then thrown away; the tile is always shown
- **Where:** `src/services/ad_service.py:41` (`self._privacy_options_required: bool | None = None`), `:78-80` (assigned), `src/screens/views.py:529-533` (the tile), `src/app_controller.py:319-328` (the handler).
- **What:** The flag is written once and **never read** (`grep -n "_privacy_options_required" src/services/ad_service.py` → only `:41` and `:78`). The Settings tile therefore shows in every region, and a user outside the EEA taps it and gets the snackbar *"Privacy options are not required in your region"* (`src/app_controller.py:324`) — a dead-end control. The package's contract is that the entry point is required only when `get_privacy_options_requirement_status() == REQUIRED` (`flet_ads/consent_manager.py:94-106`, `flet_ads/types.py:171-193`).
- **Fix / opportunity:** Either drive the tile's visibility off the flag (hide it when not required) or delete the flag and keep the always-visible tile deliberately. Hiding it is what the study and `docs/reference/dep-flet-ads.md:17` describe.
- **Risk if ignored:** Cosmetic noise in Settings and a dead field that will mislead the next reader into thinking the requirement is handled.

### F9 · P3 · The consent state is never shown to the user
- **Where:** no call to `get_consent_status()` or `is_consent_form_available()` anywhere in `src/` (`grep -rn "get_consent_status\|is_consent_form_available" src/` → nothing).
- **What:** Two exported methods are unused (`flet_ads/consent_manager.py:60-71`, `:73-83`). The user can open the privacy-options form but cannot see what their current consent state is, and the app cannot tell "no consent needed here" from "consent never collected".
- **Fix / opportunity:** Read `get_consent_status()` after the launch flow and after `show_privacy_options_form()`, put it in `AppState`, and render it as a subtitle on the Settings privacy row.
- **Risk if ignored:** Low user impact; it is the cheapest missing signal for support ("why am I seeing ads?").

### F10 · P3 · `AdService.close()` is dead code, so the banner pool is never cleared and is not page-scoped
- **Where:** `src/main.py:24-31` (`page.on_close` closes **sessions only**), `src/services/ad_service.py:229-236` (`close()` → `clear_banner_pool()`), `src/components/banner_ad.py:24, 31-40`.
- **What:** `grep -rn "ad_service" src/` shows `close()` is called nowhere outside `tests/test_ads.py:56`. So `clear_banner_pool()` never runs in the app. The pool is a **module-level dict keyed by slot string only** (`src/components/banner_ad.py:24, 31-36`) — `pooled_banner_ad` ignores the `page` argument for a cached entry. On a page rebuild (or a second window in the same `flet-desktop` process) the pooled control from the dead page is re-mounted.
- **Evidence:**
  ```
  src/main.py:24:    def _on_close(_e=None) -> None:
  src/main.py:25:        controller.session_manager.close_all()
  ```
  ```
  src/components/banner_ad.py:31: def pooled_banner_ad(slot: str, page: ft.Page | None = None) -> Control:
  src/components/banner_ad.py:32:     ad = _BANNER_POOL.get(slot)
  src/components/banner_ad.py:33:     if ad is None:
  src/components/banner_ad.py:34:         ad = build_banner_ad(page)
  src/components/banner_ad.py:35:         _BANNER_POOL[slot] = ad
  src/components/banner_ad.py:36:     return ad
  ```
- **Fix / opportunity:** Call `await controller.ad_service.close()` from `main.py`'s `_on_close`, and key the pool by `(slot, id(page))` (or store the page on the pooled entry and rebuild when it changes).
- **Risk if ignored:** On desktop (`flet run`) a reopened window can mount a control owned by the previous page — a flet "control already has a parent"-class error. On device the process dies with the window, so it is latent.

### F11 · P3 · The 30-second interval is stamped before the ad is actually shown
- **Where:** `src/services/ad_service.py:170-179`.
- **What:** `self._last_interstitial_at = time.monotonic()` is written **before** the show attempt and before the outcome is known. Combined with F3 (a no-op show), a silent no-show still consumes the window, so the next natural break is blocked for 30 s for an ad that never appeared.
- **Fix / opportunity:** Stamp the timestamp when the ad is confirmed shown (on `on_open`/`on_load` of the shown instance) rather than at request time.
- **Risk if ignored:** A missed ad suppresses the next opportunity; revenue loss that looks like "the guard is too strict".

### F12 · P3 · The banner's revenue and lifecycle events are all unwired
- **Where:** `src/components/banner_ad.py:62-68` wires only `on_load` and `on_error`.
- **What:** `BannerAd` exposes `on_paid` (`flet_ads/banner_ad.py:36`), `on_will_dismiss` (iOS only, `:28`), and inherits `on_open`, `on_close`, `on_impression`, `on_click` (`flet_ads/base_ad.py:44-64`); Dart fires all of them (`flutter/flet_ads/lib/src/banner.dart:49-73`). None is used. `on_paid` is the only per-impression revenue signal in the package (`flet_ads/interstitial_ad.py` has no paid event).
- **Fix / opportunity:** Wire `on_paid` to a counter (remember: the payload is **micros** — Dart sends `valueMicros` under `"value"`, `flutter/flet_ads/lib/src/banner.dart:62-69`, while the Python field is documented as "the monetary value", `flet_ads/types.py:45-48` — divide by 1e6). `on_open`/`on_close` are the documented hook to pause/resume whatever the ad overlay covers (`flet_ads/base_ad.py:44-57`); in this app the install-progress thread (`src/app_controller.py:173-177`) is the thing that keeps mutating state behind the overlay.
- **Risk if ignored:** No revenue telemetry and no ability to pause work behind a click-through.

### F13 · P3 · One of the three natural-break interstitials is missing
- **Where:** `src/app_controller.py:412-413` (`leave_session` — returning from a terminal session to the distro list) shows no ad; `src/app_controller.py:201-202` and `:208-209` do.
- **What:** The design intent (recorded in the study §8.1 item 2 and mirrored in the house reference) is interstitials at three natural breaks: after an install completes, after a container removal, and on return to the distro list from a session. Two of the three are implemented.
- **Fix / opportunity:** Add `await self.ad_service.show_interstitial()` to `leave_session` — it is a genuine break (the user just finished a task) and is exactly where the interval guard and the "no ad mid-typing" rule are satisfied.
- **Risk if ignored:** Missed impressions at the highest-intent moment in the app.

### F14 · P3 · No iOS ad-unit IDs exist
- **Where:** `src/services/ad_service.py:29-30`, `src/components/banner_ad.py:20-21` — Android only; `interstitial_id` (`src/services/ad_service.py:45-49`) always returns the Android value.
- **What:** The package documents separate unit IDs per platform (`flet_ads/interstitial_ad.py:20-21`: Android `…/1033173712`, iOS `…/4411468910`; `flet_ads/banner_ad.py:18-19`: Android `…/9214589741`, iOS `…/2435281174`). The project ships Android only (`pyproject.toml:43-52` defines `[tool.flet.android]`; there is no `[tool.flet.ios]`), so this is **not** a live defect — it is preparation for an iOS port.
- **Fix / opportunity:** When iOS enters scope, add an `ios` axis to the ID selection *and* an `[tool.flet.ios.meta_data]` APPLICATION_ID entry, mirroring `pyproject.toml:74-75`.
- **Risk if ignored:** An iOS build would request an Android unit ID and never fill.

### F15 · P3 · `PRIVACY.md` §2.A contradicts §2.C.2 and the manifest's advertising-id permission
- **Where:** `PRIVACY.md:19` vs `PRIVACY.md:34-37`; `.github/workflows/app.yml:242-264` (the CI explicitly tolerates `android.permission.ACCESS_ADSERVICES_*`).
- **What:** §2.A states the app "**does not collect, store, or transmit any personal information**", while §2.C.2 discloses that AdMob may collect device identifiers and the build carries the advertising-id permission. The two statements cannot both be true, and the Play data-safety form must match the manifest, not §2.A.
- **Fix / opportunity:** Reword §2.A to exclude advertising identifiers ("except as described in 2.C.2"), and keep the AdMob paragraph.
- **Risk if ignored:** A policy/data-safety inconsistency on a Play submission, and an unnecessary support burden.

## Missed capabilities

| Capability | API location | Proposed integration point | Value vs cost |
|---|---|---|---|
| **Non-personalized ad fallback** — serve an untargeted fill instead of nothing when consent is absent | `flet_ads/types.py:87` (`AdRequest.non_personalized_ads`) | `AdService` builds the `AdRequest` once and passes it to both the interstitial (`src/services/ad_service.py:135`) and the banner (`src/components/banner_ad.py:62`) | High value / ~5 lines: it is the standard UMP answer to "consent not granted" and it removes the need for the all-or-nothing gate |
| **UMP debug geography / test identifiers** — see the real EEA form from a desk | `flet_ads/types.py:196-243` | `AdService.gather_consent()` (`src/services/ad_service.py:73`), dev builds only | High value / ~10 lines: the only way to validate F1/F2 without travelling |
| **Consent status + form availability** — show the user's current state | `flet_ads/consent_manager.py:60-83` | `AppState` field + the Settings privacy row (`src/screens/views.py:529-533`) | Medium value / ~10 lines: makes the privacy UI meaningful and supportable |
| **Privacy-options entry point gated on REQUIRED** | `flet_ads/consent_manager.py:94-106`, `flet_ads/types.py:171-193` | `AdService._privacy_options_required` (`src/services/ad_service.py:78`) → `AppState` → `src/screens/views.py:529-533` | Medium value / ~5 lines: the field already exists and is already computed |
| **`on_paid` revenue telemetry** (banner only) | `flet_ads/banner_ad.py:36`, payload `flutter/flet_ads/lib/src/banner.dart:62-69` (value is **micros**) | `src/components/banner_ad.py:66-67` | Medium value / ~5 lines: the only per-impression revenue number the package exposes |
| **`on_open` / `on_close` pause-resume hook** | `flet_ads/base_ad.py:44-57` | `src/components/banner_ad.py:66-67` (banner) and `src/services/ad_service.py:135-142` (interstitial) | Low-medium value / ~10 lines: pauses the install-progress state churn behind a click-through overlay |
| **Under-age consent tag** | `flet_ads/types.py:251` (`tag_for_under_age_of_consent`) | `ConsentRequestParameters` in `gather_consent()` | Low value (this is a developer tool with no under-age mode) but it is a one-line, explicit policy statement |
| **Targeting for a developer-tool audience** | `flet_ads/types.py:70-82` (`keywords`, `content_url`, `neighboring_content_urls`) | the `AdRequest` built in `AdService` | Low value / low cost: `keywords=["proot","termux","linux container"]` would improve fill quality, but note the privacy-policy cost of declaring the targeting in the Play data-safety form |
| **The third natural-break interstitial** (return to the distro list) | — (orchestration, not an API) | `AppController.leave_session` (`src/app_controller.py:412-413`) | Medium value / 1 line |
| **Adaptive / larger banner sizes** | **not available in 1.0.4** — `size: AdSize.banner` is hardcoded (`flutter/flet_ads/lib/src/banner.dart:30`) | — | N/A |
| **Rewarded ads, app-open ads, native ads** | **not available** — no such class in the wheel; `NativeAd` is unexported and its Dart case is commented out (`flutter/flet_ads/lib/src/extension.dart:34-37`) | — | N/A |

## Verified-good list

1. **Consent-before-ads ordering for the interstitial** — `src/app_controller.py:91-95` runs `gather_consent()` then `preload_interstitial()`, matching the package's prescribed launch order (`flet_ads/consent_manager.py:22-30`).
2. **`can_request_ads()` really does gate the interstitial** — checked at `src/services/ad_service.py:131` (preload) and `:167` (show), and re-read after the privacy-options form (`:110`). (The banner path is the gap — F1.)
3. **Platform gating matches the package guard exactly** — `src/services/ad_service.py:51-55` and `src/components/banner_ad.py:53-57` pre-check `page.platform.is_mobile()` / `page.web`, the same predicate the package uses before raising `FletUnsupportedPlatformException` (`flet_ads/base_ad.py:69-75`, `flet_ads/consent_manager.py:36-42`). `flet run` on desktop therefore renders a zero-size placeholder instead of crashing.
4. **Single-show discipline** — `show_interstitial` takes the instance out of `self.interstitial` before showing it (`src/services/ad_service.py:182`), so one instance is never shown twice, as the package requires (`flet_ads/interstitial_ad.py:10-13`).
5. **The 30-second minimum interval exists and is enforced** — `src/services/ad_service.py:32, 170-178`, matching D-017.6 (`docs/decisions.md:112`).
6. **Service lifetime is right** — the `ConsentManager` is created once (`src/services/ad_service.py:70`) and kept alive in `page.services` (`:72`) so `show_privacy_options_form()` can still be invoked later from Settings (`:109`). This is the correct flet 1.0.4 idiom: `Service.__post_init__` registers it with the client (`flet/controls/services/service.py:47-54`) and the `page.services` reference keeps it above flet's refcount prune threshold (`flet/controls/page.py:228-245`, `docs/reference/app-sherlock.md:18`).
7. **Release-on-close is sound** — `_handle_close` (`src/services/ad_service.py:156-164`) drops the keep-alive reference through `_release_service` (`:239-243`), which lets flet's refcount pruning remove the service and the Dart side run `InterstitialAdService.dispose()` (`flutter/flet_ads/lib/src/interstitial.dart:65-69`).
8. **Banner placement matches D-017.7** — on the terminal screen the ad sits above the app chrome with the header row between it and the terminal, the row is permanent (fixed 320×50 → no layout jump), and it disappears in full-screen mode (`src/screens/terminal_view.py:177-197`; sizing `src/components/banner_ad.py:64-65, 76` matching the hardcoded `AdSize.banner` at `flutter/flet_ads/lib/src/banner.dart:30`).
9. **Invalid-traffic exposure is bounded and recorded** — the terminal banner is not adjacent to any tap target (`src/screens/terminal_view.py:178-195`), and D-017.7 (`docs/decisions.md:116`) records the residual accidental-click risk as knowingly accepted.
10. **The Android APPLICATION_ID is present and correct** — `pyproject.toml:74-75` carries Google's official sample app id `ca-app-pub-3940256099942544~3347511713` (the value settled in D-017.8, `docs/decisions.md:122`), and the CI asserts the meta-data is present in the merged manifest (`.github/workflows/app.yml:231-232, 265-268`).
11. **Permissions are right** — `INTERNET` + `ACCESS_NETWORK_STATE` declared (`pyproject.toml:65-67`), and the CI's permission allowlist correctly tolerates the ads SDK's `ACCESS_ADSERVICES_*` / attribution permissions while still failing on any install permission (`.github/workflows/app.yml:242-268`).
12. **`reset()` is never called** — the package's testing-only consent reset (`flet_ads/consent_manager.py:128-136`) has no production call path, as the study requires.
13. **`NativeAd` is not used** — correct; it is unexported and its Dart case is commented out (`flet_ads/__init__.py:1-29`, `flutter/flet_ads/lib/src/extension.dart:34-37`).
14. **No API hallucination** — every `flet_ads` symbol the app touches is one of the 12 exported names, and the three control constructions were executed successfully against the installed wheel (see the table above).
15. **`shared_services.py` is correctly *not* the ads mount point** — `src/core/shared_services.py:21-50` owns the five core services only, keeping the "one upstream importer per service" rule (D-015/BRIEF rule 4) intact: `flet_ads` is imported in exactly two places, `src/services/ad_service.py:17` and `src/components/banner_ad.py:60`.
16. **The lock is in place** — `uv.lock` pins `flet-ads 1.0.4` (`uv.lock:208-215`) and `flet 1.0.4` (`uv.lock:193-195`), satisfying the package's hard `Requires-Dist: flet==1.0.4` (`.venv/.../flet_ads-1.0.4.dist-info/METADATA:14`), and CI installs with `uv sync --frozen` (`.github/workflows/app.yml:49, 149, 203`) so the family cannot drift.

## Unverified

- **On-device behaviour of every ad path** — no device or CI-build evidence exists in this repo for: the UMP form appearing, the banner filling, the interstitial filling, or the AdMob APPLICATION_ID being consumed. All device-level claims above are derived from the installed Dart source, not observed.
- **The exact end-to-end symptom of the static-slot collision (F4)** — the shared static handle (`flutter/flet_ads/lib/src/interstitial.dart:10, 44`) and the app's two-live-instance pattern are source-provable; whether the user sees the wrong ad, a disposed ad, or nothing requires a device run.
- **Whether flet's client actually calls `dispose()` when a service leaves the registry** (the Dart half of `FletService.dispose()` is not in site-packages), which the release-on-close chain depends on.
- **The exact runtime failure mode when `APPLICATION_ID` is missing** — `pyproject.toml:69-73` and D-017.8 assert the process dies; the precise mechanism was never reproduced here.
- **Whether the banner's Dart `_isLoaded` flag survives the control being removed from and re-added to the tree** (`flutter/flet_ads/lib/src/banner.dart:17, 35-37, 77-79`), i.e. whether the pooling actually suppresses the reload-per-build behaviour it is meant to.
- **Whether `AdSize.banner` (320×50 dp) overflows on narrow or split-screen devices** — the app hardcodes 320/50 (`src/components/banner_ad.py:64-65, 76`) with no width check.
- **The real `get_privacy_options_requirement_status()` per region** and whether Google's required-entry-point rules are satisfied by the current always-visible tile.
- **The resolved `google_mobile_ads` 9.x minor** — build-time resolved from `flutter/flet_ads/pubspec.yaml:15`, not pinned by the wheel.
- **The `DebugGeography` wire-name smell** in `flutter/flet_ads/lib/utils/consent.dart:4-6` (`"debugGeography$value"` vs the Dart enum name) — needs a device to confirm that the EEA simulation in F6 actually works.
