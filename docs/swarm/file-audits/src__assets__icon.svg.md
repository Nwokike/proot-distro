# src/assets/icon.svg — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/assets/icon.svg` (17 lines) · `src/components/brand_hero.py` · `src/screens/onboarding_view.py` · `pyproject.toml:28,40-41` · `docs/decisions.md:59` (D-015.8) · `.venv/lib/python3.14/site-packages/flet/controls/core/image.py:67-78` · **Date:** 2026-10-24

## What it does / how the app uses it

`src/assets/icon.svg` is the app's one brand mark: a 1024×1024 self-adapting SVG with two paths — `.slate` (#2e343a) and `.mark` (#ffffff) — each carrying presentation-attribute fill/stroke as the fallback for renderers that ignore SVG CSS, plus an internal `<style>` block whose `@media (prefers-color-scheme: dark)` swaps slate→#f4f4f8 and mark→#121218. The app consumes it as raw bytes via `app_icon_svg()` (`src/components/brand_hero.py:17-29`) rendered with `ft.Image(src=…, color=None if theme.is_light_theme() else ft.Colors.WHITE, …)` in `build_brand_hero()` (`brand_hero.py:32-62`, used by `screens/views.py`) and duplicated in `OnboardingView` (`src/screens/onboarding_view.py:76-82`). `pyproject.toml:28` declares `icon = "src/assets/icon.png"` for the platform-assets pipeline, and `[tool.flet.splash]` is #121218 (`pyproject.toml:40-41`). D-015.8 (`docs/decisions.md:59`) records the owner's ruling: one self-adapting SVG, tinted at render time by the app, with the internal prefers-color-scheme block so the README swaps on GitHub without a second white variant.

## Findings

### F1 · P2 · Dark-mode mark painted #121218 — invisible on the #121218 splash (known finding)

- **Where:** `src/assets/icon.svg:12` (`path.mark { fill: #121218; stroke: #121218; }` inside the `@media (prefers-color-scheme: dark)` block opened at :10) · `pyproject.toml:40-41` (splash `color = "#121218"`, `dark_color = "#121218"`) · `docs/decisions.md:59` (D-015.8: "the same file carries an internal prefers-color-scheme style block so the README swaps on GitHub")
- **What:** The file's own comment claims browsers that apply SVG CSS (this file in a README) swap the palette (:4-5). Where that swap applies, the mark becomes #121218 — byte-identical to the splash background — so the penguin vanishes on any #121218 background. The app render path is intended to be safe: the comment at :6-7 says renderers that ignore SVG CSS (the app's image pipeline) fall back to the presentation attributes, i.e. mark stays #ffffff (:16) with the runtime white tint (`brand_hero.py:42`, `onboarding_view.py:81`). Note the app splash itself never paints icon.svg (`pyproject.toml:34-37` boot_screen is the default "flet"; splash is color only), so the collision is real only in renderers honoring the dark media query (README, site, etc.). Known finding, accepted as-is per the task.
- **Evidence:** `icon.svg:10-13`; `pyproject.toml:40-41`; `decisions.md:59`.
- **Fix / opportunity:** Change line 12 mark fill/stroke from #121218 to #f4f4f8 (the same light value already used for slate in dark, :11) or #ffffff, so the penguin survives every context where the media query applies; keep light-mode mark #ffffff (:9, :16).
- **Risk if ignored:** brand mark invisible on dark README (if GitHub applies the CSS — see F2) and on any #121218 background, exactly the dark-mode context the swap was meant to serve.

### F2 · P2 · GitHub README dark-mode swap is UNVERIFIED

- **Where:** `src/assets/icon.svg:3-14` (`<style>` block :3-4, light palette :8-9, `@media (prefers-color-scheme: dark)` :10-13) · `docs/decisions.md:59`
- **What:** Whether GitHub actually applies an SVG's internal `<style>` + `@media prefers-color-scheme` to an image embedded in a README cannot be proven from this repo (offline; GitHub's rendering/sanitization pipeline for README images is external and not installed here). If GitHub strips/ignores the internal stylesheet, the README always renders the light palette: slate #2e343a + mark #ffffff (presentation attributes :8-9, :15-16). D-015.8's claim ("so the README swaps on GitHub without a second white variant") rests on this unverified behavior.
- **Evidence:** `icon.svg:3-14`; `decisions.md:59`.
- **Fix / opportunity:** Verify on a live GitHub README in dark mode; if the swap does not occur, either embed the SVG inline in the README or accept a single palette. No app code change required; out of scope for this audit.
- **Risk if ignored:** documented dark-mode README behavior may not hold; no user-visible impact in the app itself.

### F3 · P2 · Presentation attributes exist (fill to tint: yes) but `color_blend_mode` is unset — tint not guaranteed

- **Where:** `src/assets/icon.svg:15` (slate `fill="#2e343a" stroke="#2e343a"`) · `:16` (mark `fill="#ffffff" stroke="#ffffff"`) · `src/components/brand_hero.py:42` (`color=None if theme.is_light_theme() else ft.Colors.WHITE`) · `src/screens/onboarding_view.py:81` (identical) · `.venv/lib/python3.14/site-packages/flet/controls/core/image.py:67-74` (`color` docstring: "this color is blended with each image pixel using color_blend_mode"; `color_blend_mode: Optional[BlendMode] = None` at :73)
- **What:** Both paths carry presentation-attribute fills, so `ft.Image(color=ft.Colors.WHITE …)` on dark has fill to tint — the slate gray and the white mark are both paintable. However neither call site sets `color_blend_mode`, which defaults to `None` (`image.py:73`); per the Flet docstring the tint is applied through `color_blend_mode`, so whether the white tint actually takes effect is UNVERIFIED from the installed source (flagged UNVERIFIED in the brand_hero audit F1). House standard calls for `color` + `BlendMode.SRC_IN`. Additionally, a `srcIn` white tint paints every non-transparent pixel white, collapsing the two-tone artwork (slate + mark) into a solid white silhouette — confirm that matches the "white on dark" intent stated at `brand_hero.py:40-41`.
- **Evidence:** `icon.svg:15-16`; `brand_hero.py:42`; `onboarding_view.py:81`; `image.py:67-74`.
- **Fix / opportunity:** Add `color_blend_mode=ft.BlendMode.SRC_IN` at both call sites (`brand_hero.py:42`, `onboarding_view.py:81`) whenever `color` is set; leave `None` when `color is None`. `ft.BlendMode.SRC_IN` exists in flet 1.0.4 (import-verified).
- **Risk if ignored:** dark-mode icon may render untinted (two-tone on the dark splash) instead of the requested white silhouette — UX drift from the house treatment and the D-015.8 ruling.

### F4 · P3 · viewBox/dimensions vs icon.png — MATCH (verified-good)

- **Where:** `src/assets/icon.svg:2` (`viewBox="0 0 1024 1024" width="1024" height="1024"`) · `src/assets/icon.png` 1024×1024, mode P (PIL-verified) · `pyproject.toml:28` (`icon = "src/assets/icon.png"`)
- **What:** Identical square dimensions; the platform-assets pipeline derives every OS icon set from a 1024×1024 source with no aspect-ratio mismatch or letterboxing risk.
- **Fix:** none.

### F5 · P3 · XML validity — VALID (verified-good)

- **Where:** `src/assets/icon.svg:1-17` (`<?xml version="1.0" encoding="UTF-8"?>` :1; `<svg …>` root :2; `<style>` block :3-14 closed at :14; two self-closing `<path …/>` elements :15-16; `</svg>` :17)
- **What:** Parses as well-formed XML via `xml.dom.minidom.parse` (command output: `XML: WELL-FORMED`); no unclosed tags, bare entities, or namespace mismatches.
- **Fix:** none.

### F6 · P2 · onboarding_view duplicates the ft.Image without `error_content`

- **Where:** `src/screens/onboarding_view.py:76-82` vs `src/components/brand_hero.py:43` (`error_content=ft.Icon(ft.Icons.TERMINAL, size=64)`) · `brand_hero.py:27-29` (`return b""` when all three asset candidates miss)
- **What:** `build_brand_hero()` guards the SVG load with `error_content`; `OnboardingView`'s identical `ft.Image` construction (:76-82) has none. If `app_icon_svg()` misses every candidate and returns `b""` (device asset layout UNVERIFIED — see brand_hero audit F2), onboarding renders a blank 96×96 box (`tokens.HERO_ICON_SIZE`, :78-79).
- **Evidence:** `onboarding_view.py:76-82`; `brand_hero.py:43,27-29`; `.venv/…/flet/controls/core/image.py:46` (`error_content: Optional[Control] = None`).
- **Fix / opportunity:** Add `error_content=ft.Icon(ft.Icons.TERMINAL, size=64)` to the `ft.Image` at `onboarding_view.py:76`, matching `brand_hero.py:43`. Single-line change.
- **Risk if ignored:** blank hero zone on the first-run screen after an asset-misconfiguration build.

## Missed capabilities (dependency audits only)

N/A — this is a file audit, not a dependency audit; no new packages proposed (D-003 frozen set).

## Verified-good list

1. **XML well-formed** — `xml.dom.minidom.parse('src/assets/icon.svg')` succeeds (lines 1-17).
2. **Dimensions match icon.png** — SVG `viewBox`/`width`/`height` = 1024×1024 (line 2); `icon.png` = 1024×1024 (PIL).
3. **`ft.Colors.WHITE` and `ft.BlendMode.SRC_IN` exist** in flet 1.0.4 (import-verified via the venv).
4. **`ft.Image.src` accepts `Union[str, bytes]`** (`image.py:36`) — passing raw SVG bytes is a supported source type.
5. **Fill to tint exists** — both paths carry presentation-attribute fills (lines 15-16).
6. **`error_content` correctly typed and used in brand_hero** — `image.py:46` `Optional[Control]`; `brand_hero.py:43`.
7. **Light/dark tint branch matches intent** — `color=None if light else WHITE` (`brand_hero.py:42`, `onboarding_view.py:81`) matches the "white on dark" intent of `brand_hero.py:40-41` and D-015.8.

## Unverified

1. Whether GitHub actually applies the SVG's internal `@media prefers-color-scheme` block to a README image (F2).
2. Whether the app's render pipeline (Flutter SVG via Flet) honors or ignores the internal CSS — in-file claim only at `icon.svg:6-7`; the Dart side is not in `.venv`.
3. Whether `color` without `color_blend_mode` actually tints on the Flutter client (inherited UNVERIFIED; brand_hero audit F1).
4. Whether `ft.Image(src=b"")` triggers `error_content` or renders blank (Dart-side handling not in `.venv`).
5. Whether `app_icon_svg()`'s path candidates resolve on device (`brand_hero.py:22-27`; cwd fallbacks unreliable on Android).