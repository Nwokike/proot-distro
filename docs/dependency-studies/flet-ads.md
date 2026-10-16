# flet-ads 1.0.4 — exhaustive API reference

**Package:** `flet-ads` · **Version:** 1.0.4 · **Date verified:** 2026-10-16
**Installed source:** `.venv/Lib/site-packages/flet_ads` (all `file:line` refs below are relative to that dir unless stated)
**Project context:** `docs/roadmap.md` (§0, §1, M3/M5), `docs/decisions.md` (D-003, D-004, D-010 — flet family stays on stable 1.0.4)
**Anti-hallucination rule:** every API claim carries a `file:line` ref verified against the installed source or a quoted Dart snippet from the bundled plugin. Anything not visible in the installed source is labeled **unverified**.

---

## 1. Identity

| Item | Value | Evidence |
|---|---|---|
| PyPI name / version | `flet-ads` 1.0.4 | `flet_ads-1.0.4.dist-info/METADATA` (`Name: flet-ads`, `Version: 1.0.4`) |
| License | **Apache-2.0** | METADATA `License-Expression: Apache-2.0`; full text in `flet_ads-1.0.4.dist-info/licenses/LICENSE` |
| Exact flet pin | **`flet==1.0.4`** (hard equality) | METADATA `Requires-Dist: flet==1.0.4`. Project consequence (D-004): flet + flet-ads bump as one atomic pair; the family must stay lock-stepped |
| Requires-Python | `>=3.10` | METADATA `Requires-Python: >=3.10` |
| Wheel tag | `py3-none-any`, pure lib (`Root-Is-Purelib: true`) | `flet_ads-1.0.4.dist-info/WHEEL` |
| Homepage / docs / repo | https://flet.dev · https://flet.dev/docs/controls/ads · https://github.com/flet-dev/flet/tree/main/sdk/python/packages/flet-ads | METADATA `Project-URL` entries |
| Upstream basis | `google_mobile_ads` Flutter package | METADATA long description ("It is based on the `google_mobile_ads` Flutter package") |
| Platform support (declared) | iOS ✅ · Android ✅ · Windows/macOS/Linux/Web ❌ | METADATA long description platform table |

### 1.1 Wheel contents (from `flet_ads-1.0.4.dist-info/RECORD`)

**Python side (7 files, 616 lines total):**

| File | Lines | Role |
|---|---|---|
| `flet_ads/__init__.py` | 29 | Sole export surface |
| `flet_ads/banner_ad.py` | 41 | `BannerAd` control |
| `flet_ads/base_ad.py` | 75 | `BaseAd` shared base |
| `flet_ads/consent_manager.py` | 136 | `ConsentManager` service + 8 UMP methods |
| `flet_ads/interstitial_ad.py` | 37 | `InterstitialAd` service + `show()` |
| `flet_ads/native_ad.py` | 33 | `NativeAd` — on disk but **not exported** (see §3) |
| `flet_ads/types.py` | 265 | All dataclasses/enums/value types |

**Bundled Flutter plugin (10 files, shipped under `site-packages/flutter/flet_ads/`):**

| File | Role |
|---|---|
| `flutter/flet_ads/pubspec.yaml` | Dart package manifest (see §1.2) |
| `flutter/flet_ads/lib/flet_ads.dart` (3 lines) | Barrel: `export "src/extension.dart" show Extension;` |
| `flutter/flet_ads/lib/src/extension.dart` (42 lines) | `Extension` — `ensureInitialized` + `createService`/`createWidget` mappings (quoted in §6) |
| `flutter/flet_ads/lib/src/banner.dart` | `BannerAdControl` widget |
| `flutter/flet_ads/lib/src/interstitial.dart` | `InterstitialAdService` |
| `flutter/flet_ads/lib/src/consent_manager.dart` | `ConsentManagerService` (8 method-name cases) |
| `flutter/flet_ads/lib/src/native.dart` | `NativeAdControl` — exists but **never wired** (case commented out in `extension.dart:34-37`) |
| `flutter/flet_ads/lib/utils/ads.dart` (14 lines) | `parseAdRequest` wire parser |
| `flutter/flet_ads/lib/utils/consent.dart` (25 lines) | `parseDebugGeography` / `parseConsentDebugSettings` / `parseConsentRequestParameters` |
| `flutter/flet_ads/lib/utils/native.dart` (51 lines) | Native template-style parsers (dead code path while NativeAd is unwired) |

**What is NOT in the wheel:** no `patcher.py` / build-time patcher of any kind (verified: no `patcher*` file under `flet_ads*` in site-packages), no Gradle/XML templates, no `project.scripts` entry points. Contrast with `flet-notifications`, which ships a manifest/gradle patcher — flet-ads supplies none, so the AdMob APPLICATION_ID must come from our own `[tool.flet.android.meta_data]` (see §7).

### 1.2 Dart dependency

`flutter/flet_ads/pubspec.yaml:1-18` (verbatim relevant block):

```yaml
name: flet_ads
description: Display Google Ads in Flet apps.
version: 0.1.0          # Dart-side package version; independent of the 1.0.4 Python version
publish_to: none
environment:
  sdk: '>=3.2.3 <4.0.0'
  flutter: ">=1.17.0"
dependencies:
  flutter:
    sdk: flutter
  collection: ^1.16.0
  google_mobile_ads: ^9.0.0     # <-- the AdMob SDK binding; resolved at `flet build` time
  flet:
    path: ../../../../../../../packages/flet   # local path ref; rewritten by the flet build template in CI
```

- `google_mobile_ads: ^9.0.0` (`pubspec.yaml:15`) is the only ad-SDK dependency; it pulls the native Mobile Ads SDKs (Android GMS ads + iOS Google-Mobile-Ads-SDK) transitively at Flutter build time. No Gradle lines are needed or possible from our side for the SDK itself.
- Resolved `google_mobile_ads` minor/patch at build time is **unverified** (depends on the CI build environment's pub cache; nothing in the wheel pins it beyond `^9.0.0`).

---

## 2. Complete public API — export surface

`__init__.py:1-29` exports **exactly 12 names** (`__all__` at `__init__.py:16-28`):

```python
# __init__.py:1-14 (imports = the entire public surface)
from flet_ads.banner_ad import BannerAd             # __init__.py:1
from flet_ads.base_ad import BaseAd                 # __init__.py:2
from flet_ads.consent_manager import ConsentManager # __init__.py:3
from flet_ads.interstitial_ad import InterstitialAd # __init__.py:4
from flet_ads.types import (                        # __init__.py:5-13
    AdRequest,
    ConsentDebugSettings,
    ConsentRequestParameters,
    ConsentStatus,
    DebugGeography,
    PaidAdEvent,
    PrecisionType,
    PrivacyOptionsRequirementStatus,
)
```

Notable **omissions** (present on disk, absent from `__init__.py` and `__all__`):

- `NativeAd` (`native_ad.py:9`) — importable only via the private path `flet_ads.native_ad.NativeAd`, and functionally dead anyway (§3).
- `NativeAdTemplateStyle`, `NativeAdTemplateTextStyle`, `NativeAdTemplateType`, `NativeTemplateFontStyle` — listed in `types.py:6-13` (`types.__all__`) but **not re-exported** by the package `__init__`; reachable only as `flet_ads.types.*`.

Four control files exist on disk (`banner_ad.py`, `base_ad.py`, `consent_manager.py`, `interstitial_ad.py`, plus `native_ad.py` = five files / four usable controls + one dead).

---

## 3. Control classes (all four on-disk controls)

### 3.1 `BaseAd` — `base_ad.py:8-75`

```python
# base_ad.py:8-9
@dataclass(kw_only=True)
class BaseAd(ft.BaseControl):
```

Shared base for every ad control/service. **Keyword-only construction** (`kw_only=True`, `base_ad.py:8`).

| Member | Kind | Type / default | Ref | Notes |
|---|---|---|---|---|
| `unit_id` | property | `str`, **required, no default** | `base_ad.py:21` | Ad unit ID. Always sent; Dart falls back to a test ID only if the key is missing on the wire (`banner.dart:27`, `interstitial.dart:19-23`), which cannot happen through the Python API since the field is mandatory |
| `request` | property | `AdRequest`, default `field(default_factory=lambda: AdRequest())` | `base_ad.py:26` | Targeting info; empty `AdRequest()` = no targeting |
| `on_load` | event | `Optional[ControlEventHandler["BaseAd"]] = None` | `base_ad.py:31` | Fired on successful load (`triggerEvent("load")` — `banner.dart:34`, `interstitial.dart:45`, `native.dart:39`) |
| `on_error` | event | `Optional[...] = None` | `base_ad.py:36` | `e.data: str` = `error.toString()` (`banner.dart:41`, `interstitial.dart:31,48`) |
| `on_open` | event | `Optional[...] = None` | `base_ad.py:44` | Full-screen overlay presented (click-through). Pause animations/timers here |
| `on_close` | event | `Optional[...] = None` | `base_ad.py:53` | Overlay closed; resume what `on_open` paused |
| `on_impression` | event | `Optional[...] = None` | `base_ad.py:59` | An impression was recorded |
| `on_click` | event | `Optional[...] = None` | `base_ad.py:64` | Ad clicked |
| `before_update()` | method | — | `base_ad.py:69-75` | **Platform guard** (see §5) |

### 3.2 `BannerAd` — `banner_ad.py:8-41`

```python
# banner_ad.py:8-9
@ft.control("BannerAd")
class BannerAd(ft.LayoutControl, BaseAd):
```

Inline banner widget (layout control — occupies space in the widget tree). Inherits all 8 `BaseAd` members (§3.1); adds **no new properties and no methods**, only 2 events:

| Member | Kind | Type / default | Ref | Notes |
|---|---|---|---|---|
| `on_will_dismiss` | event | `Optional[ControlEventHandler["BannerAd"]] = None` | `banner_ad.py:28` | **iOS only** (docstring `banner_ad.py:28-33`). Wired to `onAdWillDismissScreen` (`banner.dart:59-61`) |
| `on_paid` | event | `Optional[ControlEventHandler[PaidAdEvent["BannerAd"]]] = None` | `banner_ad.py:36` | Paid-event payload dict `{value, precision, currency_code}` (`banner.dart:62-69`); allowlisted accounts only (docstring `banner_ad.py:36-41`) |

Test ad unit IDs (docstring `banner_ad.py:11-21`):

- Android banner: `ca-app-pub-3940256099942544/9214589741`
- iOS banner: `ca-app-pub-3940256099942544/2435281174`

**Source-visible Dart caveat:** the Dart fallback test ID in `banner.dart:23-25` uses the *interstitial* test IDs (`…/1033173712` Android, `…/4411468910` iOS), not the banner IDs above. Harmless in practice (`unit_id` is required Python-side so the fallback is unreachable), but do not copy those IDs as banner test IDs.

**Source-visible Dart behavior:** `banner.dart:30` hardcodes `size: AdSize.banner` (standard 320×50). No adaptive/anchored-adaptive/MREC/large-banner size is exposed — fixed banner size is all 1.0.4 offers. `banner.dart:72-74` calls `bannerAd.load()` on every build while `_isLoaded` is false, i.e. widget rebuilds re-trigger loads until the first success.

### 3.3 `InterstitialAd` — `interstitial_ad.py:5-37`

```python
# interstitial_ad.py:5-6
@ft.control("InterstitialAd")
class InterstitialAd(ft.Service, BaseAd):
```

Full-screen interstitial. It is an `ft.Service` (no visual tree node — add to `page.services`/`page.overlay`, *not* to a layout), inheriting all 8 `BaseAd` events. Adds one method, no new properties/events:

| Member | Kind | Signature | Ref | Notes |
|---|---|---|---|---|
| `show()` | `async` method | `async def show(self)` → `await self._invoke_method("show")` | `interstitial_ad.py:30-37` | Presents the loaded ad. Dart: `_interstitialAd?.show()` (`interstitial.dart:57-59`) — **null-safe no-op if the ad hasn't loaded**; await `on_load` (or gate on a loaded flag) before calling |

Test ad unit IDs (docstring `interstitial_ad.py:15-25`):

- Android interstitial: `ca-app-pub-3940256099942544/1033173712`
- iOS interstitial: `ca-app-pub-3940256099942544/4411468910`

Lifecycle rules (all source-visible):

1. **Single-show instances.** Docstring `interstitial.dart`-side behavior + `interstitial_ad.py:8-13`: "Each instance is allowed to be shown (using `show`) only once. To show another ad, create a new instance." Dart disposes the native ad on dismiss (`interstitial.dart:34-39`).
2. **Load starts at service init.** `interstitial.dart:18-51` — `InterstitialAd.load(...)` fires in `init()`, i.e. as soon as the service attaches. There is no explicit `load()` API; attaching the service *is* the load request.
3. **One shared native slot.** `_interstitialAd` is `static` (`interstitial.dart:10`): concurrent `InterstitialAd` instances overwrite each other's native handle; the last-loaded wins and earlier instances' `show()` would present the wrong ad or nothing. **Use at most one live instance at a time** (create → await load → show → discard → create next).
4. No `on_paid` / `on_will_dismiss` on this class (those live on `BannerAd` only); `FullScreenContentCallback` wires `open` (showed), `impression`, `error` (failed-to-show), `close` (dismissed), `click` (`interstitial.dart:27-41`).

### 3.4 `ConsentManager` — `consent_manager.py:13-136`

```python
# consent_manager.py:13-14
@ft.control("ConsentManager")
class ConsentManager(ft.Service):
```

UMP consent service (`ft.Service`; `before_update` guard at `consent_manager.py:36-42`, same mobile-only rule as §5). No properties, no events — 8 async methods, each a thin `_invoke_method` pass-through to the Dart string cases in `consent_manager.dart:19-80`:

| # | Method | Signature | Python ref | Dart case | Semantics |
|---|---|---|---|---|---|
| 1 | `request_consent_info_update` | `(params: Optional[ConsentRequestParameters] = None) -> None` | `consent_manager.py:44-58` | `consent_manager.dart:22-36` | **Call (and await) at every app launch**, before anything else. `None` → default params (`utils/consent.dart:18-25`). Failure surfaces as `Exception("Consent info update failed (<code>): <msg>")` (`consent_manager.dart:30-33`) |
| 2 | `is_consent_form_available` | `() -> bool` | `consent_manager.py:60-71` | `consent_manager.dart:38-39` | Whether a form exists to show. Await method 1 first |
| 3 | `get_consent_status` | `() -> ConsentStatus` | `consent_manager.py:73-83` | `consent_manager.dart:41-42` | Cached between sessions; readable before update. Wire `.name` string → enum |
| 4 | `can_request_ads` | `() -> bool` | `consent_manager.py:85-92` | `consent_manager.dart:44-45` | **The gate for all ad loading** — `True` means consent state permits ad requests |
| 5 | `get_privacy_options_requirement_status` | `() -> PrivacyOptionsRequirementStatus` | `consent_manager.py:94-106` | `consent_manager.dart:47-50` | Whether a persistent privacy-options entry point (e.g. settings button) is required |
| 6 | `load_and_show_consent_form_if_required` | `() -> None` | `consent_manager.py:108-116` | `consent_manager.dart:52-64` | No-op when consent isn't required. Errors → `Exception("Consent form error (<code>): <msg>")` |
| 7 | `show_privacy_options_form` | `() -> None` | `consent_manager.py:118-126` | `consent_manager.dart:66-78` | Present only when method 5 returns `REQUIRED`. Errors → `Exception("Privacy options form error ...")` |
| 8 | `reset` | `() -> None` | `consent_manager.py:128-136` | `consent_manager.dart:79-80` | Clears UMP state (first-time-user simulation). **Testing only — never ship a call path to it in production** (docstring `consent_manager.py:128-135`) |

Canonical launch flow (docstring `consent_manager.py:22-30`): `request_consent_info_update` → `load_and_show_consent_form_if_required` → `can_request_ads` → load ads only if `True`.

### 3.5 `NativeAd` — `native_ad.py:8-33` — UNEXPORTED / BROKEN in 1.0.4

```python
# native_ad.py:8-9
@ft.control("NativeAd")
class NativeAd(BannerAd):
```

| Member | Type / default | Ref | Notes |
|---|---|---|---|
| `factory_id` | `str = None` | `native_ad.py:14` | Platform-view factory id; **unverified** end-to-end (no factory registration path exists in the wheel) |
| `template_style` | `NativeAdTemplateStyle = None` | `native_ad.py:22` | Template styling; parsed by `utils/native.dart:34-51` *if* it were ever reached |
| `init()` | raises `ValueError("factory_id or template_style must be set")` when both are `None` | `native_ad.py:30-33` | The only validation; runs Python-side |

Why it is dead in 1.0.4 (three independent breaks, all source-visible):

1. **Not exported**: no `NativeAd` import in `__init__.py:1-14`, absent from `__all__` (`__init__.py:16-28`). `import flet_ads; flet_ads.NativeAd` raises `AttributeError`.
2. **Not wired in Dart**: `extension.dart:34-37` comments the `"NativeAd"` widget case out with `TODO: Finalize NativeAdControl`. Even a direct `flet_ads.native_ad.NativeAd` import produces a control type the extension returns `null` for.
3. Supporting types (`NativeAdTemplateStyle` et al., `types.py:108-136`) are themselves excluded from the package `__init__` (only in `types.__all__`).

Do not use `NativeAd` in this project until a future flet-ads release un-comments the Dart case *and* exports the class. Test IDs exist in the dead Dart file (`native.dart:24-26`: Android `…/2247696110`, iOS `…/3986624511`) for future reference only.

---

## 4. Value types — every dataclass / enum (`types.py`)

### 4.1 `AdRequest` — `types.py:61-105` (`@ft.value`)

All six fields `Optional`, all default `None` (= untargeted request):

| Property | Type / default | Ref | Wire key (`utils/ads.dart:6-13`) | Notes |
|---|---|---|---|---|
| `keywords` | `Optional[list[str]] = None` | `types.py:70` | `keywords` | Words/phrases describing current user activity |
| `content_url` | `Optional[str] = None` | `types.py:75` | `content_url` | Webpage URL matching app content (targeting/brand-safety) |
| `neighboring_content_urls` | `Optional[list[str]] = None` | `types.py:82` | `neighboring_content_urls` | URLs of web content near the ad |
| `non_personalized_ads` | `Optional[bool] = None` | `types.py:87` | `non_personalized_ads` | NPA flag (EEA/consent-fallback path). AdMob docs: https://support.google.com/admob/answer/7676680?hl=en |
| `http_timeout` | `Optional[int] = None` | `types.py:94` | `http_timeout` → `httpTimeoutMillis` (`utils/ads.dart:11`) | Custom HTTPS timeout **in milliseconds**. **Android only, ignored on iOS** (docstring `types.py:94-101`) |
| `extras` | `Optional[dict[str, str]] = None` | `types.py:102` | `extras` | Extra string pairs for the AdMob adapter/mediation |

### 4.2 `PaidAdEvent` — `types.py:39-58` + `PrecisionType` — `types.py:22-37`

```python
# types.py:39-40
@dataclass
class PaidAdEvent(ft.Event[ft.EventControlType]):
```

| Field | Type | Ref |
|---|---|---|
| `value` | `float` (required — no default) | `types.py:45` |
| `precision` | `PrecisionType` (required) | `types.py:50` |
| `currency_code` | `str` (required) | `types.py:55` |

`PrecisionType` (`types.py:23-37`) wire values: `UNKNOWN="unknown"`, `ESTIMATED="estimated"`, `PUBLISHER_PROVIDED="publisherProvided"`, `PRECISE="precise"`.

**Payload caveat (source-visible):** Dart sends the raw micros number under `"value"` (`banner.dart:62-69`: `"value": valueMicros`) — the Python field is named `value` with docstring "The monetary value of the ad" (`types.py:45-48`), so consumers must treat the received number as **micros** (divide by 1e6) despite the docstring. Only `BannerAd.on_paid` (and dead `NativeAd`) expose this; `InterstitialAd` has no paid event.

### 4.3 Consent enums — `types.py:139-217`

`ConsentStatus` (`types.py:139-168`): `NOT_REQUIRED="notRequired"` · `OBTAINED="obtained"` (a decision was *collected* — consent **or** decline/custom, per docstring `types.py:156-163`) · `REQUIRED="required"` · `UNKNOWN="unknown"`. Never means granted-vs-denied; the actual choice lives in the IAB TCF string read automatically by the SDK.

`PrivacyOptionsRequirementStatus` (`types.py:171-193`): `NOT_REQUIRED` · `REQUIRED` · `UNKNOWN` (e.g. before `request_consent_info_update` completes).

`DebugGeography` (`types.py:196-216`): `DISABLED="disabled"` · `EEA="eea"` · `REGULATED_US_STATE="regulatedUsState"` · `OTHER="other"`. Effective only on registered test devices (see below). **Wire-name caveat:** `utils/consent.dart:4-6` builds the enum lookup as `"debugGeography$value"`, i.e. it matches against `"debugGeographyeea"`-style strings rather than the Dart enum's `eea` name — exercise `ConsentDebugSettings` on a real device before trusting geography simulation (source-visible smell, device verification required).

### 4.4 Consent debug/parameter values — `types.py:218-265` (both `@ft.value`)

`ConsentDebugSettings` (`types.py:219-243`): `debug_geography: Optional[DebugGeography] = None` (`types.py:225`); `test_identifiers: Optional[list[str]] = None` (`types.py:230`) — physical-device hashed IDs from `adb logcat` on first consent request; emulators auto-registered.

`ConsentRequestParameters` (`types.py:246-265`): `tag_for_under_age_of_consent: Optional[bool] = None` (`types.py:251`) — `True` **suppresses the consent form entirely** (under-age users can't be asked); `consent_debug_settings: Optional[ConsentDebugSettings] = None` (`types.py:262`).

### 4.5 Native template types — `types.py:108-136` (dead in 1.0.4, see §3.5)

`NativeAdTemplateType` (`types.py:108-110`): `SMALL="small"`, `MEDIUM="medium"`. `NativeTemplateFontStyle` (`types.py:113-118`): `NORMAL/BOLD/ITALIC/MONOSPACE`. `NativeAdTemplateTextStyle` (`types.py:120-125`, `@ft.value`): `size: Optional[Number]`, `text_color: Optional[ColorValue]`, `bgcolor: Optional[ColorValue]`, `style: Optional[NativeTemplateFontStyle]` — all `None`. `NativeAdTemplateStyle` (`types.py:128-136`, `@ft.value`): `template_type: NativeAdTemplateType = MEDIUM` (the **only non-None default** in the file) plus `main_bgcolor`, `corner_radius`, `call_to_action_text_style`, `primary_text_style`, `secondary_text_style`, `tertiary_text_style`, all `None`.

**Wire-name caveat (source-visible):** `utils/native.dart:26-31` reads `value["color"]` for `textColor`, but the Python `@ft.value` serializes the field as `text_color`. Unless the flet value-codec aliases it, a `text_color` set Python-side may not arrive Dart-side — verify on device if native templates ever ship. (`bgcolor` matches on both sides.)

---

## 5. Platform guards — what raises where

`BaseAd.before_update` (`base_ad.py:69-75`, verbatim):

```python
def before_update(self):
    super().before_update()
    if self.page.web or not self.page.platform.is_mobile():
        raise ft.FletUnsupportedPlatformException(
            f"{self.__class__.__name__} is only supported on "
            f"Mobile (Android and iOS)"
        )
```

`ConsentManager.before_update` (`consent_manager.py:36-42`) is identical apart from the class name.

| Surface | Desktop (`flet run`, prebuilt client) | Web | Android / iOS (built APK/IPA) |
|---|---|---|---|
| `BannerAd` (incl. `BaseAd` guard) | raises `FletUnsupportedPlatformException` | raises | works |
| `InterstitialAd` | raises (inherits `BaseAd.before_update`) | raises | works |
| `ConsentManager` | raises (own guard) | raises | works |
| `NativeAd` | raises (inherits via `BannerAd`) — moot, unwired | raises | unwired (`extension.dart` returns `null`) |

Project consequence (roadmap §1b): `flet run` uses the prebuilt desktop client with no extension Dart, so **every ad/consent surface must sit behind a platform-availability placeholder** in dev, and `uv run flet run` covers only non-extension UI. Device truth comes from CI `build-<sha>` artifacts only.

---

## 6. Dart extension surface (quoted from the bundled plugin)

`flutter/flet_ads/lib/src/extension.dart:9-42`, verbatim (imports trimmed):

```dart
class Extension extends FletExtension {
  @override
  void ensureInitialized() {
    if (isMobilePlatform()) {
      MobileAds.instance.initialize();   // extension.dart:11-15
    }
  }

  @override
  FletService? createService(Control control) {
    switch (control.type) {
      case "InterstitialAd":
        return InterstitialAdService(control: control);   // extension.dart:20-21
      case "ConsentManager":
        return ConsentManagerService(control: control);   // extension.dart:22-23
      default:
        return null;
    }
  }

  @override
  Widget? createWidget(Key? key, Control control) {
    switch (control.type) {
      case "BannerAd":
        return BannerAdControl(control: control);         // extension.dart:32-33
      /* TODO: Finalize NativeAdControl -> https://developers.google.com/admob/flutter/native/platforms
      case "NativeAd":
        return NativeAdControl(control: control);         // extension.dart:34-37 (commented out)
      */
      default:
        return null;
    }
  }
}
```

Mapping summary: `"BannerAd"` → widget; `"InterstitialAd"` / `"ConsentManager"` → services; `"NativeAd"` → `null` (commented out); everything else → `null`. SDK init is mobile-gated inside `ensureInitialized`. Consent method-name strings handled Dart-side (`consent_manager.dart:22,38,41,44,47,52,66,79`): `request_consent_info_update`, `is_consent_form_available`, `get_consent_status`, `can_request_ads`, `get_privacy_options_requirement_status`, `load_and_show_consent_form_if_required`, `show_privacy_options_form`, `reset`; unknown names throw (`consent_manager.dart:82`). Interstitial handles only `show` (`interstitial.dart:56-60`).

---

## 7. Android notes

- **APPLICATION_ID manifest entry is OUR job — no patcher in the package.** Verified: no `patcher.py`/manifest-template/gradle-template anywhere under `flet_ads*` in site-packages (contrast `flet-notifications`, whose patcher injects manifest bits). Roadmap M5 (`[tool.flet.android.meta_data]` AdMob entry) is the mechanism: the `com.google.android.gms.ads.APPLICATION_ID` `<meta-data>` must be declared in our own `[tool.flet]` config; without it the Mobile Ads SDK fails at runtime (no ad loads, typically an `IllegalStateException`-class init error from the GMS SDK — **unverified** exact exception text, never observed in this repo).
- **Gradle deps arrive transitively via the plugin.** `google_mobile_ads: ^9.0.0` (`pubspec.yaml:15`) is resolved at `flet build apk` time inside the Flutter template; we add no ` dependencies`, no `pubspec overrides`, no Gradle edits (per roadmap M5: "No pubspec overrides unless a CI build proves one necessary").
- **`MobileAds.instance.initialize()` runs at extension init, mobile-gated** (`extension.dart:11-15`). Initialization order relative to the UMP `request_consent_info_update` call is SDK-internal; our required order is only the Python-side flow in §3.4.
- **Permissions:** AdMob needs `INTERNET` + `ACCESS_NETWORK_STATE` — exactly the two permissions roadmap M5 already scopes the app to. No extra permission is introduced by flet-ads (source-visible: nothing in the wheel declares permissions).
- **targetSdk 35/36 behavior: unverified.** Nothing in the installed Python or Dart source references `targetSdkVersion`, edge-to-edge, or foreground-service types; any Play-console warnings about the ads SDK vs targetSdk 35/36 can only be established from a CI-built APK/AAB (M5) and the resolved `google_mobile_ads` 9.x minor in that build's pub cache. The `collection: ^1.16.0` Dart dep (`pubspec.yaml:14`) is likewise build-time-resolved and **unverified** as to its settled version.

---

## 8. How this project uses / will use it (roadmap M3/M5)

Per roadmap §1 (locked architecture: "`flet-ads` … consent + interstitial (mobile-gated; banner only where space is reserved)") and §4 parking lot ("consent + interstitial only; banner placement reserved row"):

- **M3 scaffold**: `ConsentManager` service mounted at app launch behind the platform-availability placeholder (desktop = placeholder pane; device = real UMP flow from §3.4). Settings screen gets the privacy-options entry point, shown iff `get_privacy_options_requirement_status() == REQUIRED`. `can_request_ads()` gates every ad attach. Ads respect the terminal screens' reserved layout rows only.
- **M5 packaging/CI**: AdMob APPLICATION_ID via `[tool.flet.android.meta_data]`; INTERNET + ACCESS_NETWORK_STATE permissions; no pubspec overrides; `uv pip compile --python-platform aarch64-linux-android` proof step covers the `flet==1.0.4` pair.
- Test-device discipline: physical-device hashed IDs from `adb logcat` into `ConsentDebugSettings.test_identifiers` + `DebugGeography.EEA` during development (real GDPR-form sighting without traveling); `reset()` confined to dev builds, never in shipped code paths.

### 8.1 Fullest-utilization proposals (every 1.0.4 capability exercised)

1. **Consent at launch, always**: `request_consent_info_update` on every cold start (§3.4 method 1) → `load_and_show_consent_form_if_required` → `can_request_ads` cached in `AppState`; re-check `get_consent_status` on resume-from-background. Settings screen hosts `show_privacy_options_form` behind the method-5 `REQUIRED` check — this is the GDPR ongoing-entry-point obligation, implemented with one button.
2. **Interstitial cadence**: single live `InterstitialAd` instance at a time (§3.3 rule 3); natural-break placement only — after a distro install completes, after a container removal, on return-to-distro-list from a session — never mid-typing in the terminal and never on first launch. Create → await `on_load` → hold → `show()` at the next break → discard → pre-create the next. `on_error` with backoff (no retry storms on no-fill).
3. **Banner placement rules for a terminal app**: terminal/session screens have no spare vertical space (roadmap §4), so the banner gets a **reserved fixed row only on non-terminal screens** (distro list, install progress, settings), `AdSize.banner` is 320×50 dp fixed (§3.2) so the row height is constant and layout never jumps when `on_load` fires. Never overlay the terminal view (keyboard + toolbar + banner = unusable). `on_paid` logged (micros → currency) for revenue telemetry where the AdMob account is allowlisted.
4. **Targeting hygiene**: default empty `AdRequest()` everywhere except `non_personalized_ads=True` fallback when `can_request_ads()` is `False` (serve NPA rather than nothing, where policy allows); `extras` reserved for future mediation adapters; `http_timeout` left `None` (Android-only knob with no demonstrated need).
5. **`on_open`/`on_close` discipline**: pause terminal render-flush/progress timers on `on_open`, resume on `on_close` (both events exist on all three usable surfaces via `BaseAd`).

### 8.2 What CANNOT be done in 1.0.4 (source-verified absences)

- **Rewarded ads**: no `RewardedAd` class/file/string anywhere in the wheel (Python or Dart). Not available.
- **Native ads**: `NativeAd` dead on three counts (§3.5). Not available.
- **App-open ads**: no such surface in Python or Dart. Not available.
- **Adaptive/anchored-adaptive/large banner sizes**: `AdSize.banner` hardcoded (`banner.dart:30`). Not available.
- **Explicit interstitial `load()`/dispose control**: load is init-coupled, dispose is dismiss-coupled (§3.3 rules 2–3). Preloading N ads or manual disposal is not expressible.
- **Interstitial paid events**: no `onPaidEvent` wiring in `interstitial.dart` (only `banner.dart:62-69` and dead `native.dart:54-60` have it). Revenue-per-impression telemetry is banner-only.
- **Desktop/web ads**: guards raise (§5). No fallback renderer exists.

---

## 9. How flet-ads makes our app significantly better than Termux's proot-distro

Termux ships `proot-distro` as an unpaid utility inside a donation/goodwill economy: no monetization primitive, no consent framework, and every sustainability question is answered with volunteer labor. Our app wraps the same capability as a **sustainable free product**, and flet-ads is the mechanism — three concrete advantages, each grounded in the verified API above:

1. **Sustainable free-app economics via consent-first AdMob.** Termux cannot fund maintenance, hosting of rootfs mirrors, or support load from its distribution itself. We can: the §3.4 UMP flow (`request_consent_info_update` → `load_and_show_consent_form_if_required` → `can_request_ads`) makes EEA/GDPR-compliant monetization a launch-time primitive, and the interstitial single-show lifecycle (§3.3) maps exactly onto our rare natural breaks (install/remove completions), so revenue never taxes the terminal interaction that is the product. The `on_paid` micros pipeline (§4.2) gives per-impression revenue telemetry Termux has no equivalent of.
2. **Official-extension lockstep, not a fork.** `Requires-Dist: flet==1.0.4` (§1) means flet-ads moves atomically with the flet family — our D-004 "bump as one atomic set" update path covers ads with zero extra policy. Termux's distribution story is community plugins of varying provenance; ours is one versioned, signed, PyPI-resolved dependency whose Dart (`google_mobile_ads ^9.0.0`) is maintained by Google/Flet upstream, not by us.
3. **Zero-patch integration.** No patcher, no manifest templates, no Gradle edits, no entry points (§1.1, §7) — ads hook in through `import flet_ads` + control/service attach exactly like the R1 finding for flet extensions generally. Against the owner "no patching of upstream" constraint (roadmap §0), flet-ads is the model citizen: our only integration surface is our *own* `[tool.flet.android.meta_data]` APPLICATION_ID entry plus platform-gated UI code we own. Nothing to rebase, nothing that breaks when flet 1.1.0 stable lands beyond the paired bump.

---

## 10. Verification ledger

Every claim above traces to installed source. Key refs:

- Identity/pin/license: `flet_ads-1.0.4.dist-info/METADATA` (Name, Version, License-Expression, Requires-Dist `flet==1.0.4`, Requires-Python `>=3.10`); `…/WHEEL`; `…/RECORD` (7 py + 10 flutter files); `flutter/flet_ads/pubspec.yaml:1-18`.
- Exports: `flet_ads/__init__.py:1-29`; `types.py:6-13` (`types.__all__` incl. the 4 non-reexported native names).
- `BaseAd`: `base_ad.py:8` (kw_only), `:21` (unit_id), `:26` (request default), `:31/:36/:44/:53/:59/:64` (events), `:69-75` (guard).
- `BannerAd`: `banner_ad.py:8-9` (decorator/bases), `:11-21` (test IDs), `:28` (will_dismiss iOS), `:36` (paid).
- `InterstitialAd`: `interstitial_ad.py:5-6`, `:8-13` (single-show), `:15-25` (test IDs), `:30-37` (`show`).
- `ConsentManager`: `consent_manager.py:13-14`, `:36-42` (guard), `:44/:60/:73/:85/:94/:108/:118/:128` (8 methods), `:22-30` (flow).
- `NativeAd`: `native_ad.py:8-9`, `:14`, `:22`, `:30-33` (ValueError); unwired `extension.dart:34-37`.
- Types: `types.py:22-37` (PrecisionType), `:39-58` (PaidAdEvent), `:61-105` (AdRequest), `:108-136` (native templates), `:139-168` (ConsentStatus), `:171-193` (PrivacyOptions), `:196-216` (DebugGeography), `:218-243`/`:246-265` (debug settings/params).
- Dart: `extension.dart:9-42` (quoted §6); `banner.dart:23-31` (fallback IDs + fixed size), `:34/:41/:49-61/:62-69` (events); `interstitial.dart:10` (static slot), `:18-51` (init-load), `:27-45` (callbacks), `:56-60` (show); `consent_manager.dart:19-82` (8 cases + error strings); `native.dart:24-32` (dead test IDs + factory check); `utils/ads.dart:3-14`, `utils/consent.dart:4-25`, `utils/native.dart:21-51` (parsers); `lib/flet_ads.dart:1-3` (barrel).

**Unverified** (labeled inline; need device/CI evidence): resolved `google_mobile_ads` 9.x minor at build time; exact runtime failure text for missing APPLICATION_ID; `targetSdk` 35/36 Play behavior; `debug_geography` simulation fidelity (`utils/consent.dart:4-6` smell); `NativeAdTemplateTextStyle.text_color` wire delivery (`utils/native.dart:28` vs `text_color`); `factory_id` platform-view registration path (no code path in wheel).
