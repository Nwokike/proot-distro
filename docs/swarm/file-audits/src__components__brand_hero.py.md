# src/components/brand_hero.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/components/brand_hero.py` (62 lines) · `CollabShell/src/components/brand_header.py` (42 lines) · `src/assets/icon.svg` (16 lines) · `src/core/theme.py`, `src/core/tokens.py`, `src/main.py` · `tests/test_ui_reactive.py:58-76` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/components/brand_hero.py` exposes two public helpers: `app_icon_svg()` (lines 17-29), which resolves `src/assets/icon.svg` from a small list of filesystem locations and returns its bytes (or `b""`), and `build_brand_hero(tagline=None)` (lines 32-62), which builds a centered `Container` holding a 96x96 `ft.Image` of that SVG plus an optional 12px tagline. It is used by `screens/views.py:311` (Distros home hero) and `screens/onboarding_view.py:77` (onboarding slide icon, duplicating the `ft.Image` construction). The theme toggle is not in this file despite the module docstring; tinting is driven by `theme.is_light_theme()`.

---

## Findings

### F1 · P2 · Tint is set without a blend mode, so the color may not actually be applied
- **Where:** `src/components/brand_hero.py:40-42` (`color=None if theme.is_light_theme() else ft.Colors.WHITE`) · `.venv/lib/python3.14/site-packages/flet/controls/core/image.py:66-74` (`color: Optional[ColorValue]` "blended with each image pixel using :attr:`color_blend_mode`"; `color_blend_mode: Optional[BlendMode] = None`) · house standard `docs/reference/house-ui-design.md` §3 ("Brand SVGs ... tinted `color` + `BlendMode.SRC_IN`").
- **What:** The code sets `color=ft.Colors.WHITE` on dark but never sets `color_blend_mode`. Per the Flet 1.0.4 `Image` docstring, `color` is only blended through `color_blend_mode`; with that left at its default `None` the tint is not guaranteed to take effect (and the intended "white silhouette on dark" treatment is not explicitly requested). The house standard calls for `BlendMode.SRC_IN`.
- **Evidence:** `.venv/.../flet/controls/core/image.py:66-74`; `docs/reference/house-ui-design.md` §3.
- **Fix / opportunity:** Add `color_blend_mode=ft.BlendMode.SRC_IN` whenever `color` is set (and leave it `None` when `color is None`). `ft.BlendMode.SRC_IN` exists at `.venv/.../flet/controls/types.py:611`.
- **Risk if ignored:** On dark mode the icon may keep its two-tone artwork (or render untinted) instead of inverting to the requested white mark; UX drift from the house treatment.

### F2 · P2 · Asset lookup fallbacks depend on `cwd`, which is unreliable on Android
- **Where:** `src/components/brand_hero.py:19-29` (`src_root = Path(__file__).resolve().parents[1]`; candidates `src_root/assets/icon.svg`, `Path.cwd()/src/assets/icon.svg`, `Path.cwd()/assets/icon.svg`) · `src/main.py:37-40` (`assets = Path(__file__).resolve().parent / "assets"; ft.run(main, assets_dir=...)`) · `.venv/.../flet/app.py:677-700` (`__get_assets_dir_path` resolves relative `assets_dir` against the script dir or cwd).
- **What:** The first candidate is correct for a normal source checkout, but on Android the app is packaged and the working directory is not the project root, so the two `Path.cwd()` fallbacks are very likely wrong and the function can fall through to `return b""`. There is no use of the configured `assets_dir` or package resources, and no check for PyInstaller-style `_MEI` roots.
- **Evidence:** `src/main.py:39-40`; `.venv/.../flet/app.py:690-698` (cwd vs `get_current_script_dir()`); `brand_hero.py:27-29`.
- **Fix / opportunity:** Prefer the asset through the same path resolution as `main.py` (resolve `assets` next to the script / via `FLET_ASSETS_DIR`), and only then fall back. Alternatively ship the SVG as a package resource via `importlib.resources` so it does not depend on cwd at all. Labelled UNVERIFIED on actual Android filesystem layout (see Unverified).
- **Risk if ignored:** Brand icon silently degrades to `error_content` (terminal glyph) or empty bytes on device builds.

### F3 · P2 · `app_icon_svg()` does uncached disk reads on every render
- **Where:** `src/components/brand_hero.py:17-29` (no cache; `candidate.read_bytes()` each call) · callers `screens/views.py:311` and `screens/onboarding_view.py:77`.
- **What:** Each component render re-reads the SVG from disk. `build_brand_hero` is called while rendering home/onboarding, so the file is re-read on every reactive re-render with no memoization.
- **Evidence:** `src/components/brand_hero.py:27-28`; `screens/views.py:311`; `screens/onboarding_view.py:77`.
- **Fix / opportunity:** Cache the bytes once (e.g. `functools.lru_cache(maxsize=1)` on `app_icon_svg`, or a module-level `_ICON_SVG: bytes | None`). Keep returning `b""` on miss so the existing test (`tests/test_ui_reactive.py:63`) still passes.
- **Risk if ignored:** Avoidable main-thread disk IO during reactive renders; minor jank on theme toggles.

### F4 · P3 · Hardcoded sizes instead of house tokens
- **Where:** `src/components/brand_hero.py:37-38` (`width=96, height=96`) and `:43` (`size=64`) · `src/core/tokens.py:55` (`HERO_ICON_SIZE = 96`) and `:40` (`ICON_HERO = 64`).
- **What:** The hero image and fallback icon use magic numbers that happen to equal the house tokens but are not referenced from `tokens`, so they drift independently of the design scale (CollabShell's `brand_header.py:14-15` uses `tokens.ICON_XXXL`).
- **Evidence:** `src/core/tokens.py:40,55`; `CollabShell/src/components/brand_header.py:14-15`.
- **Fix / opportunity:** Import `core.tokens` and use `tokens.HERO_ICON_SIZE` / `tokens.ICON_HERO`, matching `onboarding_view.py:77-78` which already does.
- **Risk if ignored:** Cosmetic inconsistency if the token scale changes.

### F5 · P3 · Tagline typography is hardcoded rather than tokenized
- **Where:** `src/components/brand_hero.py:50` (`size=12`) · `src/core/tokens.py:28` (`FONT_MD = 12`).
- **What:** The tagline size is a literal `12` instead of `tokens.FONT_MD`/`FONT_SM`; CollabShell uses `tokens.FONT_SM` for its tagline (`brand_header.py:25`).
- **Evidence:** `src/core/tokens.py:27-28`; `CollabShell/src/components/brand_header.py:25`.
- **Fix / opportunity:** Use `tokens.FONT_MD` (or `FONT_SM` to match CollabShell) and `tokens.SPACE_*` for padding.
- **Risk if ignored:** Minor visual drift.

### F6 · P3 · `error_content` fallback glyph is an unrelated terminal icon
- **Where:** `src/components/brand_hero.py:43` (`error_content=ft.Icon(ft.Icons.TERMINAL, size=64)`).
- **What:** When the SVG fails to load, the user sees a terminal glyph rather than a brand/empty-state affordance. `ft.Icons.TERMINAL` does exist (verified), and `ft.Icon` is a valid `error_content: Optional[Control]` (`image.py:48`), so this is a UX choice, not a crash.
- **Evidence:** `.venv/.../flet/controls/core/image.py:48` (`error_content: Optional[Control] = None`); `.venv/.../flet` import check `ft.Icons.TERMINAL == 73289`.
- **Fix / opportunity:** Consider an empty-state icon (`ft.Icons.IMAGE_NOT_SUPPORTED_ROUNDED` or a backdrop-wrapped icon per house §5) and/or a short `semantics_label`. Keep size tokenized.
- **Risk if ignored:** Low; fallback only appears on asset failure.

### F7 · P3 · `src=bytes` is valid in Flet 1.0.4, but empty bytes behaviour is not verified
- **Where:** `src/components/brand_hero.py:36` (`src=app_icon_svg()`) · `.venv/.../flet/controls/core/image.py:36` (`src: Union[str, bytes]`) · `.venv/.../flet/messaging/protocol.py` (msgpack transport; bytes are a native msgpack type).
- **What:** Passing raw bytes as `src` is supported by the installed Flet API and transport. However, when `app_icon_svg()` returns `b""`, the resulting `ft.Image(src=b"")` behaviour (whether it triggers `error_content` or renders nothing) is not established by the Python source and is not covered by tests.
- **Evidence:** `image.py:36`; `protocol.py` encode/decode (bytes pass through msgpack).
- **Fix / opportunity:** Keep `src=bytes` (no change needed), but add a test or guard so a missing asset deterministically shows `error_content`. Labelled UNVERIFIED.
- **Risk if ignored:** On a missing asset the UI may show a blank 96x96 box instead of the fallback icon.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-component audit, not a dependency audit. No new packages proposed (D-003).

---

## Verified-good list

1. **`src=bytes` is a supported `ft.Image` source type** — `.venv/.../flet/controls/core/image.py:36` (`src: Union[str, bytes]`) and the msgpack-based protocol (`protocol.py`) carry bytes natively.
2. **`error_content` is a real, correctly typed property** — `image.py:48` (`Optional[Control]`), and `ft.Icon(ft.Icons.TERMINAL, size=64)` constructs a valid `Control` (verified `ft.Icons.TERMINAL` importable).
3. **`ft.BoxFit.CONTAIN`, `ft.Padding.only`, `ft.Column`, `ft.Container`, `ft.Text`, `ft.TextAlign.CENTER`, `ft.CrossAxisAlignment.CENTER`, `ft.Colors.WHITE`** all exist in Flet 1.0.4 (verified by import/usage and the test suite).
4. **`theme.is_light_theme()` and `theme.text_dim()`** are defined in `src/core/theme.py:31-52` and `:75-78`; the light/dark tint branch matches the test contract (`tests/test_ui_reactive.py:67-75`: dark → `color == WHITE`, light → `color is None`).
5. **`app_icon_svg()` first candidate is correct** — `Path(__file__).resolve().parents[1]` resolves to `src/`, so `src/assets/icon.svg` is the right on-disk location in a source checkout (`src/main.py:37` confirms assets live in `src/assets`).
6. **Inner column is centered** — `horizontal_alignment=ft.CrossAxisAlignment.CENTER` (`brand_hero.py:58`) centers the icon and tagline within the container; `spacing=8` and padding `top=16, bottom=8` are explicit.
7. **No imperative widget mutation** (D-015): the file only builds and returns controls; no `.value =`, `page.update()`, or `.controls.append/clear`.
8. **SVG asset is the owner's self-adapting mark** — `src/assets/icon.svg:8-13` carries a `prefers-color-scheme` block with slate/mark fills, matching the house "one self-adapting SVG" ruling (`house-ui-design.md` §3).

---

## Unverified

- Actual Android filesystem layout / whether `Path(__file__).resolve().parents[1]/assets/icon.svg` exists on device (labelled UNVERIFIED; only `src/main.py`'s `assets_dir` resolution and flet's `__get_assets_dir_path` were inspected).
- Whether `ft.Image(src=b"")` triggers `error_content` or renders blank (no test or runtime evidence).
- Whether omitting `color_blend_mode` leaves the tint unapplied in the Flutter client (the Python source documents the contract but the default client behaviour is not in `.venv`; hence F1 is framed as "not guaranteed" rather than "broken").
- Whether `functools.lru_cache` on `app_icon_svg` is safe across flet's component re-render lifecycle (expected yes, but not exercised by tests).
