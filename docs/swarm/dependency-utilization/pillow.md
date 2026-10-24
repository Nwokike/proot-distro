# pillow 12.3.0 — build-host image-engine utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/pillow.md`; `docs/reference/dep-flet-build-host.md`; `docs/swarm/dependency-utilization/flet-platform-assets.md` (cross-ref only); `docs/decisions.md:39,59`; `pyproject.toml`; `uv.lock`; `src/assets/icon.png`; `src/assets/icon.svg`; `src/components/brand_hero.py`; `src/core/theme.py:10,17`; `.venv/Lib/site-packages/PIL/{Image.py,ImageOps.py,ImageFilter.py,_deprecate.py,IcoImagePlugin.py,PngImagePlugin.py,__init__.py}`; `.venv/Lib/site-packages/flet_platform_assets/{_source.py,_imaging.py,_icons.py,_splash.py}`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/flet/controls/core/raw_image.py`; `.venv/Lib/site-packages/{flet_platform_assets-1.0.4,pillow-12.3.0,flet-1.0.4,flet_cli-1.0.4}.dist-info/METADATA`; pinned Flet build template (`/home/maikel/AppData/Local/Temp/flet-tpl/build/{{cookiecutter.out_dir}}`) · **Date:** 2026-10-20

## What it does / how the app uses it

Pillow is **never imported by the app**. `grep -rn "PIL\|pillow" src/ --include=*.py` → the only hits are `ft.Image` (`src/components/brand_hero.py:35`, `src/screens/onboarding_view.py:76`) and `RADIUS_PILL` (`src/core/tokens.py:23`) — no `PIL` import anywhere in `src/`. Its entire role is **transitive and build-host-only**: `pyproject.toml:78-84` (dev group) → `flet-cli` → `flet-platform-assets 1.0.4` → `pillow 12.3.0`.

The chain, verified end to end:

- `uv.lock:220` `flet-cli` → `uv.lock:228` `{ name = "flet-platform-assets" }` → `uv.lock:253` `flet-platform-assets` → `uv.lock:257` `{ name = "pillow" }` → `uv.lock:515-518` `pillow 12.3.0`.
- `flet_cli-1.0.4.dist-info/METADATA:13` `Requires-Dist: flet-platform-assets==1.0.4`; `flet_platform_assets-1.0.4.dist-info/METADATA:12` `Requires-Dist: pillow>=11.3.0`.
- `flet` 1.0.4 itself does **not** pull pillow except in its `test` extra (`flet-1.0.4.dist-info/METADATA:33` `pillow>=10.3.0; extra == "test"`), which this project does not install.
- **It cannot reach the APK.** `flet build apk` builds the bundled site-packages from `[project].dependencies` plus `tool.flet.<platform>.dependencies` only (`flet_cli/commands/build_base.py:2566-2576`); `pyproject.toml:9-15` lists `flet, flet-ads, httpx, flet-terminal, proot-distro` and `pyproject.toml:52` adds `flet-proot==5.1.107.98`. No pillow → no compiled `_imaging` extension on the device. CI installs the dev group and builds (`app.yml:49,149,159,203,213`).

So Pillow's utilisation is **100 % indirect**: it is the engine behind `flet_platform_assets`, which turns `src/assets/icon.png` into every platform's icon set and splash bitmap at build time. The images it produces ship; the library does not.

I re-verified the study's API claims against the installed tree (30 of 32 line refs exact; 2 off by ≤3 lines, corrected below), re-rendered all six icon platforms and the Android splash in isolation, and ran the whole pipeline under Pillow 13.0.0 in a throwaway venv to bound the version risk.

## Findings

### F1 · P1 · The Android launch screen composites a slate wordmark over `#121218` — 1.5:1 contrast, verified through the pinned template

- **Where:** `pyproject.toml:39-41` (`[tool.flet.splash] color = "#121218"`, `dark_color = "#121218"`); `src/assets/` (only `icon.png` / `icon.svg` — no `splash*.png`); `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2379-2384` (splash chain `splash_<platform> → splash → icon`, `derived = True`), `:2387-2393` (`SplashOptions(color=splash["color"], …)`), `:2427-2445` (`load_source` → `square` → `render_splash` → `write`); `.venv/Lib/site-packages/flet_platform_assets/_splash.py:108-111` (`_frame(light, "splash")`), `:125-128` (`_scaled`), `:145-152` (`drawable-{d}/splash.png` + `android12splash.png`), `:177-209` (`_android_12`, fit-to-circle).
  Template (pinned cookiecutter, `…/flet-tpl/build/{{cookiecutter.out_dir}}/android/app/src/main/res/`): `drawable/launch_background.xml:5` `<item android:drawable="@color/flet_splash_background" />` + `<bitmap android:gravity="center" android:src="@drawable/splash" />`; `values/colors.xml:6` and `values-night/colors.xml:3` both bind `flet_splash_background` to `splash.color` / `splash.dark_color`; `values-v31/styles.xml:14-15` and `values-night-v31/styles.xml:10-11` → `android:windowSplashScreenBackground` = `@color/flet_splash_background`, `android:windowSplashScreenAnimatedIcon` = `@drawable/android12splash`.
- **What:** with no splash artwork of its own, the pipeline falls back to the launcher icon, whose opaque pixels are slate `#2E353B` — and the launch screen behind them is `#121218`. Both the pre-Android-12 `launch_background` layer-list and the Android 12 `windowSplashScreen*` attributes are proven to use that colour, in **both** light and night mode (`color == dark_color`). The launch screen is a black rectangle with a barely-visible wordmark.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "... contrast of the measured artwork colour vs the splash colour ..."
  slate #2e353b vs bg #121218 : 1.5
  light #f4f4f8 vs bg #121218 : 17.01
  white      vs bg #121218 : 18.66
  ```
  Pillow render of the shipped `icon.png` composited on `#121218` (temp dir, `alpha` preserved): the wordmark is invisible; only the penguin's white outline registers. `render_splash(...)` on the same source returns **0 warnings** — the package is not complaining, the *input* is wrong.
- **Fix / opportunity:** give the splash its own artwork. The pipeline picks it up by convention with **zero code**: `build_base.py:2379-2384` resolves `splash_<platform>` then `splash`, and a real `splash.png` is used with `derived = False`, so it is not reframed. The light-on-transparent raster can be produced by Pillow alone from the existing PNG (see **F5**) — no external rasteriser, no new dependency.
- **Risk if ignored:** the app's only brand moment before the terminal prompt is a black rectangle on every cold start, on every device, in both system modes.

### F2 · P1 · The launcher icon is a 1.75:1 wordmark; Pillow's framing measurement shrinks it further and the text is 9 px tall at mdpi

- **Where:** `src/assets/icon.png`; `.venv/Lib/site-packages/flet_platform_assets/_imaging.py:315-341` (`alpha_extent`), `:471-520` (`radial_extent`), `:119-125` (`scale_to_fit`), `:213-258` (`place`); `_icons.py:51` (`ADAPTIVE_SAFE_FRACTION = 72/108`), `:177-193` (`FRAMING`), `:241-242` (`derived` → `_frame`), `:303-329` (`_frame`), `:332-347` (`_plain`), `:53-67` (mipmap / adaptive sizes).
- **What:** the source is a wide lockup inside a 1024² canvas — the artwork's alpha bbox is `(53, 256, 969, 779)`, i.e. 89.6 % of the width but only 51 % of the height. Because Android's framing is measured **radially** (`FRAMING["android"] = (0.567, radial_extent)`), and `radial_extent` measures a letterbox's off-axis corner pixels, the wordmark reads **1.0278** (> 1.0) and is shrunk by `1024 × 0.567 / 1.0278 = 565 px` — the artwork ends up at ~49 % of the canvas width, not 57 %. Every square target is then a small wide wordmark floating in a large empty square.
- **Evidence:**
  ```
  loaded: (1024, 1024) RGBA pre_rendered: False
  alpha_extent: 0.896484375
  radial_extent: 1.0277951825786085
  looks_pre_shaped: False
  alpha bbox: (53, 256, 969, 779) extrema: (0, 254)
  ```
  Coverage of the rendered Android set (Pillow-measured alpha bbox per file):
  ```
  mipmap-mdpi/ic_launcher.png        (48, 48)   artbbox=(10, 15, 38, 33)   art_px=302   (13.1 % of canvas)
      -> 'PRoot Distro' text band bbox=(10, 0, 38, 9)   text height = 9 px
  mipmap-xxxhdpi/ic_launcher.png    (192, 192) artbbox=(46, 67, 146, 126)  art_px=2697  (7.3 % of canvas)
  drawable-mdpi/ic_launcher_foreground.png (108,108) artbbox=(25,37,83,72)  art_px=1113  (9.5 % of canvas)
  drawable-xxxhdpi/ic_launcher_foreground.png (432,432) artbbox=(107,154,324,280) art_px=9972 (5.3 % of canvas)
  ```
  At `mipmap-mdpi` the "PRoot Distro" band is **9 px tall** and ~28 px wide for 11 characters. The 432 px adaptive layer carries the artwork in a 217×126 px box.
- **Fix / opportunity:** use the per-platform source convention that is already implemented and currently unused: `build_base.py:2103-2105` resolves `icon_<platform>.*` **before** the generic `icon.*`, and a per-platform source is a finished composition that is never reframed (`_icons.py:222-226`, `:252`). Add `src/assets/icon_android.png` — a 1024² square mark — and the launcher gets a legible icon with no code, no new dependency and no effect on iOS/macOS/web.
- **Risk if ignored:** the app is unidentifiable on the home screen; the Play listing thumbnail and the taskbar icon are mush. (Sibling report `flet-platform-assets.md` F2 owns the config framing; this finding supplies the Pillow measurement and the per-size numbers.)

### F3 · P2 · The adaptive icon's background is a white colour resource carrying a dark wordmark

- **Where:** `pyproject.toml:43-52` (`[tool.flet.android]` — no `adaptive_icon_background`); `.venv/Lib/site-packages/flet_cli/commands/build_base.py:1645-1653` (`self.options.android_adaptive_icon_background or get_pyproject("tool.flet.android.adaptive_icon_background") or self.icon_background_value("android") or "#ffffff"`), `:2194-2196` (`icon_background_value`); `.venv/Lib/site-packages/flet_platform_assets/_icons.py:61-67` (the foreground layers only). Template: `values/ic_launcher_background.xml:6` `<color name="ic_launcher_background">{{ cookiecutter.adaptive_icon_background }}</color>`; `mipmap-anydpi-v26/ic_launcher.xml:7-8` `<background android:drawable="@color/ic_launcher_background" />` + `<foreground android:drawable="@drawable/ic_launcher_foreground" />`.
- **What:** the adaptive icon's background is a **colour resource, not pixels** — Pillow only produces the five `drawable-*/ic_launcher_foreground.png` layers. With nothing configured, the resolution chain falls through to the literal `"#ffffff"`, so the launcher draws a **white** rounded square carrying the slate wordmark, while the launch screen behind it is `#121218` and the app itself is dark-themed (`src/core/theme.py:17`).
- **Evidence:** template XML quoted above; `build_base.py:1645-1653` resolution walk with the current `pyproject.toml` (CLI flag `None` → `tool.flet.android.adaptive_icon_background` absent → `tool.flet.android.icon_background` absent → `tool.flet.icon_background` absent → `"#ffffff"`). Pillow composite of the generated 432 px foreground over white inside a circular mask: a white disc with a small dark wordmark. The template's own comment (`mipmap-anydpi-v26/ic_launcher.xml:2-5`) notes that without the adaptive icon the launcher "falls back to the legacy square mipmap and wraps it in its own white circle" — so white is the platform default either way.
- **Fix / opportunity:** `[tool.flet.android] adaptive_icon_background = "#121218"` — one line (`build_base.py:1647`). **It must land together with the artwork change in F2/F5**: the current slate wordmark would be dark-on-dark in the adaptive icon too.
- **Risk if ignored:** a glaring white tile in an otherwise black product; on Pixel-style launchers it reads as a third-party app.

### F4 · P2 · Pillow is build-host-only by *app choice*, not by dependency structure — `flet` 1.0.4 has an optional runtime Pillow dependency the repo's import guard cannot see

- **Where:** `.venv/Lib/site-packages/flet/controls/core/raw_image.py:424` (section comment: “Pillow helpers (Pillow is an optional dependency; import lazily)”), `:434-435` (`from PIL import Image as PILImage` / `from PIL import ImageChops` inside `_premultiply_pil`), `:449-457` (`_pil_from_rgba` → `RuntimeError("Pillow is required to premultiply raw RGBA pixels; install it or pass premultiplied pixels")`), `:460-465` (`_try_pil_from_rgba` → returns `None`, graceful), `:301-311` (`render_raw` calls `_pil_from_rgba` when `premultiplied=False`); `.venv/Lib/site-packages/flet/__init__.py:186,1088,1630` (`RawImage` export); `src/` (no `RawImage` usage — `grep -rn "RawImage\|raw_image" src/ --include=*.py` → no hits); `tests/test_imports_vs_deps.py:35-44` (the guard keys on **top-level module names** only).
- **What:** `flet` itself imports Pillow lazily, at runtime, for `ft.RawImage`. On an APK built without pillow, `RawImage.render_raw(..., premultiplied=False)` raises `RuntimeError` at the moment the frame is sent. The repo's import guard would **not** catch a future `ft.RawImage` usage: the import is `flet`, which is declared — the missing piece is a *transitive optional* dependency that only bites on the device.
- **Evidence:** the quoted source lines; `build_base.py:2566-2576` (only `[project].dependencies` + `tool.flet.<platform>.dependencies` are packaged) and `pyproject.toml:9-15,52` (neither lists pillow).
- **Fix / opportunity:** no change now. If `ft.RawImage` is ever needed, either pass `premultiplied=True` (the Pillow-free path, `raw_image.py:312-322`) or add `pillow` to `tool.flet.android.dependencies` — which then needs an **Android wheel** that does not exist for pillow 12.3.0 (`uv.lock:515-546` lists win/mac/ios/manylinux/musllinux only). Cheapest durable guard: extend `tests/test_imports_vs_deps.py` to fail on `ft.RawImage` usage, since the existing import-level check cannot see it.
- **Risk if ignored:** a runtime crash on device (not a build error) that no CI job can see, appearing the day someone adds a raw-frame widget.

### F5 · P2 · Pillow *can* be used at build time — but only for the splash, and only because Pillow cannot rasterise the SVG

- **Where:** Pillow has **no SVG support**: no `SvgImagePlugin` in `.venv/Lib/site-packages/PIL/` and `Image.open("src/assets/icon.svg")` → `UnidentifiedImageError: cannot identify image file 'src/assets/icon.svg'` (`PIL/Image.py:3585` is the only entry point). The zero-code conventions that already exist: `build_base.py:2103-2105` (`icon_<platform>`), `:2379-2385` (`splash_<platform>` / `splash` / `splash_dark`); the hash stamp at `build_base.py:2088-2132`.
- **What:** answering the audit question directly —
  - **Icon variants: over-engineering.** The pipeline already supports per-platform icon sources and dedicated splash art *by filename convention*. A Pillow script that renders the same outputs would duplicate `flet_platform_assets` and fight the change-detection stamp (`build_base.py:2088-2132` hashes the source mtime, the options and the generator version). Pillow *can* crop a square mark out of the existing PNG — I did it: the white "mark" family's bbox is `(393, 259, 664, 610)`, 272×352 — but that encodes a **design decision as hard-coded crop coordinates** in a script, and it bypasses the SVG master. Do not ship that.
  - **Splash: worth it, and it is the one thing only Pillow can do here.** The SVG's own dark variant is unusable on `#121218` (it paints the penguin in `#121218`), and Pillow cannot rasterise the SVG to get the light variant. But Pillow **can** re-tint the existing raster into a light-on-transparent mark in three operations, using APIs verified in this tree: `Image.open` (`Image.py:3585`) → `load()` (`:968`) → `convert("RGBA")` (`:1017`) → `getchannel("A")` (`:2796`) → `Image.new("RGBA", size, (244,244,248,0))` (`:3193`) → `putalpha(alpha)` (`:2048`) → `save(path, format="PNG", optimize=True)` (`:2592`).
- **Evidence:** I produced that tinted raster, wrote it as `splash.png` and ran it through the real `render_splash(..., derived=False)`:
  ```
  drawable-mdpi      splash.png           (256, 256)   artbbox=(12, 62, 245, 197)
  drawable-xxxhdpi   splash.png           (1024, 1024) artbbox=(53, 256, 969, 779)  glyph_rgb_sample=[(244, 244, 248), ...]
  drawable-xxxhdpi   android12splash.png  (1152, 1152) artbbox=(241, 388, 911, 772)
  warnings: []
  ```
  Composited on `#121218` the splash is fully legible at 17.01:1 (rendered and visually checked), and the Android 12 icon is scaled by `_android_12` (`_splash.py:203-207`) to exactly the 2/3 circle the platform guarantees. This is the same operation the app performs at runtime with `ft.Image(color=ft.Colors.WHITE)` (`src/components/brand_hero.py:42`; `flet/controls/core/image.py:67-72` “this color is blended with each image pixel”).
- **Fix / opportunity:** add a host-side step (a small script run on the build machine — Pillow is already installed there via the dev group) that emits `src/assets/splash.png` from `src/assets/icon.png` with the alpha preserved and the RGB replaced by `#f4f4f8`. Keep the output **committed** (a build-time script that regenerates on every build would churn the hash stamp); do **not** import Pillow from `src/` — it is not in the APK.
- **Risk if ignored:** F1 stays open; the only in-repo route to a legible launch screen needs an external SVG rasteriser the project does not have.

### F6 · P3 · The shipped brand raster is a quantised palette PNG whose alpha never reaches 255 — the SVG's flat fill is not reproduced

- **Where:** `src/assets/icon.png`; PNG chunk list `IHDR, PLTE(768 B), tRNS(256 B), IDAT×15, IEND` — a 256-entry palette with a per-index alpha table and no `gAMA`/`sRGB`/`tEXt`; `.venv/Lib/site-packages/PIL/Image.py:3585` (`open` → mode `P`), `:1017` (`convert("RGBA")` materialises the tRNS table); `.venv/Lib/site-packages/flet_platform_assets/_source.py:63-64` (the `P` → `RGBA` conversion the toolchain performs).
- **What:** the artwork's alpha **maxes at 254, never 255** — the interior of a solid fill is 254, so the entire brand composites at 99.61 % opacity over whatever is behind it. And the *eroded* interior (88,087 pixels whose 3×3 neighbourhood is fully opaque) carries **117 distinct RGB values** for a fill the SVG defines as flat `#2e343a` with **no gradient** (`grep -c "linearGradient\|radialGradient\|filter=" src/assets/icon.svg` → `0`).
- **Evidence:**
  ```
  sha256 1ea1e923dea2100a6be5c305d32e145bf3576cfd11ebf16a9f193a1cac2afe43
  bytes 99177
  format PNG mode P size (1024, 1024)
  alpha extrema (0, 254)
  eroded interior pixels: 88087  distinct RGB: 117
  top 10: [((46,53,59),5246), ((45,52,58),4355), ((47,54,60),3076), ((44,51,57),2944), ...]
  ```
  93,517 of the 134,131 non-transparent pixels sit at exactly alpha 254. The pipeline handles the palette source correctly (no black corners, alpha preserved) — the defect is in the **source asset**, not the consumer.
- **Fix / opportunity:** re-export `src/assets/icon.png` as 8-bit RGBA from the SVG master (alpha 255, two flat colours). This is an asset change, not a code change, and it also removes the tonal noise. Note: Pillow cannot do the SVG→PNG step itself (F5) — the export must come from the design tool that produced `icon.svg`.
- **Risk if ignored:** small. 0.4 % transparency over the whole glyph and ±3/255 quantisation noise on a flat fill; visible only as a faint darkening of the mark against a coloured plate. P3 polish, and the reason the sibling report's F7 "faithful raster" claim is only half right — the **geometry** matches (PNG alpha bbox `(53,256,969,779)` vs SVG path extents `x[56.5,970.5] y[258.9,777.1]`), the **colour** does not.

### F7 · P3 · `pillow>=11.3.0` is an open range and Pillow 13.0.0 is already published — the lock is the only thing pinning the icon pipeline to 12.3.0

- **Where:** `.venv/Lib/site-packages/flet_platform_assets-1.0.4.dist-info/METADATA:12` (`Requires-Dist: pillow>=11.3.0`); `uv.lock:515-518` (pinned `12.3.0`); `.github/workflows/app.yml:49,149,203` (`uv sync --frozen --group dev`); `.venv/Lib/site-packages/PIL/_deprecate.py:50-54` (`Pillow 13 (2026-10-15)`, `Pillow 14 (2027-10-15)`); `PIL/Image.py:1540` (`deprecate("Image.Image.getdata", 14, "get_flattened_data")`).
- **What:** the range is open, so a `uv lock --upgrade` would move the icon engine forward. I measured the impact instead of guessing: I installed `pillow==13.0.0` + `flet-platform-assets==1.0.4` into a throwaway venv and re-rendered every platform with the same source.
- **Evidence:**
  ```
  total outputs compared: 58
  differing between pillow 12.3.0 and 13.0.0: 0
  ```
  All 58 rendered assets (6 icon platforms + the Android splash set) are **byte-identical** (SHA-256 of the `optimize=True` PNG bytes), with zero `RenderResult.warnings` and no `DeprecationWarning` under `-W error::DeprecationWarning` on both versions. The five APIs Pillow 12.3.0 schedules for removal in 13 (`PIL/Image.py:1671,3438,3953`; `PIL/ImageCms.py:260`; `PIL/PngImagePlugin.py:1391`) are all outside the toolchain's call set.
- **Fix / opportunity:** none required. If the team wants belt-and-braces, pin `pillow==12.3.0` in the dev group (`pyproject.toml:78-84`) or add a host-side render check to CI (see Missed capabilities). The residual risk is Pillow 14 (2027-10-15), which removes `Image.Image.getdata` — **not** used by `flet_platform_assets` (grep: the toolchain uses `point`, `crop`, `histogram`, `getbbox`, `getextrema`, `getchannel`, `putalpha`, `paste`, `alpha_composite`, `filter`, `convert`, `resize`, `new`, `frombytes`, `save`, `open`, `load`, `seek`, `exif_transpose`, `ico.getimage`).
- **Risk if ignored:** low today. A lock refresh silently changes every shipped icon byte; a future Pillow major that changes behaviour would break `flet build apk` at the icon step, late in the pipeline.

## Missed capabilities (dependency audits only)

| Capability | API location | Proposed integration point | Value vs cost |
|---|---|---|---|
| **Alpha-preserving re-tint** — replace the artwork's RGB while keeping its alpha, producing a light-on-transparent raster from the existing PNG | `PIL/Image.py:2796` `getchannel("A")`, `:3193` `new`, `:2048` `putalpha`, `:2592` `save` | a host-side script (dev group already has Pillow) that emits `src/assets/splash.png` from `src/assets/icon.png` | Closes F1 (P1) with 3 Pillow calls, no new dependency, no device impact · cost: ~10 lines + one committed PNG. **Do not** import Pillow from `src/` — it is not in the APK |
| **Per-platform icon source** — `icon_<platform>.png` is used as-is and never reframed | `flet_cli/commands/build_base.py:2103-2105`; `flet_platform_assets/_icons.py:222-226`, `:252` | add `src/assets/icon_android.png` (a square mark) | Fixes F2/F3 without touching iOS/macOS/web · cost: 1 PNG, 0 code. The convention is already implemented and unused |
| **Two-artwork splash** — `splash.png` (light) + `splash_dark.png` (dark) | `flet_cli/commands/build_base.py:2379-2385` (the dark pass has **no** icon fallback) | `src/assets/splash.png`, `src/assets/splash_dark.png` | Lets the launch screen follow the system theme like the app does (`src/core/state.py:30` `theme_mode = "system"`) · cost: 2 PNGs, both producible by the re-tint above |
| **Render-result warnings as data** — `RenderResult.warnings` is structured, not log text | `flet_platform_assets/_models.py:152` (the field), `:160-162` (`warn()`); `_icons.py:273-300`, `:417-433`; `_splash.py:212-225`; surfaced at `flet_cli/commands/build_base.py:2166-2167` | a CI step that runs `render_icons`/`render_splash` on `src/assets/icon.png` and **fails on any warning** | Turns the package's own diagnostics into a build gate; today the pipeline emits 0 warnings, so a future bad asset (too small, wrong aspect, unsafe zone) is caught before release · cost: ~20 lines, no new dependency, no Android SDK needed. This is also the cheapest guard against a Pillow major changing behaviour (F7) |
| **`flet_platform_assets` standalone use** — it imports no `flet`/`flet-cli` code and can be driven directly | `flet_platform_assets/__init__.py:1-18` (module docstring: “Rendering is separate from writing… `render_icons` is pure”), `:20-56` (every import is one of its own modules); `METADATA` (“nothing here imports flet or flet-cli”) | a host-side script that renders every platform into a temp tree and asserts the sizes/modes (48/72/96/144/192 mipmaps, 108/162/216/324/432 adaptive, 16/32/48/256 ico, 15 iOS files, 8 hicolor sizes) | Asserts the shipped icon set without a full `flet build` · cost: ~30 lines |
| **`ft.RawImage` is Pillow-backed at runtime** — Flet ships an *optional* runtime Pillow dependency | `flet/controls/core/raw_image.py:424`, `:434-435`, `:449-457`; `flet/__init__.py:1088` | `tests/test_imports_vs_deps.py` (extend the guard) | Makes the one place where "Pillow is build-host only" could silently stop being true visible to CI · cost: 3 lines. Listed so the synthesis does not re-open it as a new dependency suggestion |

## Verified-good list

- **Pillow is genuinely build-host-only for this app.** It is not in `[project].dependencies` (`pyproject.toml:9-15`), not in `tool.flet.android.dependencies` (`pyproject.toml:52`), and the APK's site-packages is built from exactly those two lists (`flet_cli/commands/build_base.py:2566-2576`). The `uv.lock` chain is `flet-cli` (`:220`) → `flet-platform-assets` (`:228`) → `flet-platform-assets` (`:253`) → `pillow` (`:257`) → `pillow 12.3.0` (`:515-518`). The wheel is compiled (`WHEEL`: `Root-Is-Purelib: false`, `cp314-cp314-win_amd64`), and `uv.lock:520-546` lists no Android wheel — so it could not be shipped to the APK even by accident.
- **The app never imports Pillow.** `grep -rn "PIL\|pillow" src/ --include=*.py` → only `ft.Image` (`src/components/brand_hero.py:35`, `src/screens/onboarding_view.py:76`) and `RADIUS_PILL` (`src/core/tokens.py:23`).
- **The whole pipeline is deprecation-free on the installed Pillow.** Running every icon platform and the Android splash under `-W error::DeprecationWarning -W error::PendingDeprecationWarning` completes with exit 0 and no warnings; `Image.open("src/assets/icon.png")` under the same flags is clean. The toolchain uses no API scheduled for removal in Pillow 13 or 14.
- **Pillow 13.0.0 produces byte-identical output** — 58/58 assets identical, 0 warnings (F7). The forward-compat risk is empirically cleared for the next major.
- **The palette-mode source is handled correctly.** `icon.png` is mode `P` with a tRNS table; `load_source` converts it to RGBA (`_source.py:63-64`) and the alpha survives intact — alpha extrema `(0, 254)`, all four corners at alpha 0, and 10,151 near-white penguin pixels (alpha ≥ 128, luminance > 200) preserved. No black-corner artefact, no alpha loss.
- **The generated asset sizes are exactly right.** Android mipmaps 48/72/96/144/192 (`_icons.py:53-59`), adaptive foregrounds 108/162/216/324/432 (`:61-67`), iOS 15 files 20…1024 (`:78-94`), macOS 7 files 16…1024 (`:96`), Windows `.ico` 16/32/48/256 (`:71`), Linux 8 hicolor sizes + `linux/app_icon.png` (`:76`, `:436-459`), Android splash 256/384/512/768/1024 and `android12splash` 288/432/576/864/1152 (`_splash.py:34`, `:41`, `:196`). No size is wrong.
- **The `icon.png` resolution is adequate.** The source is 1024² and the largest target per platform is 1024 (iOS/macOS), 512 (web), 432 (Android adaptive), 256 (Windows) — `_warn_low_resolution` (`_icons.py:273-300`) never fires, and the 2048 source cap (`_source.py:11-17`, `:66-75`) is not engaged.
- **The framing is idempotent and does not double-shrink.** `FRAMING_TOLERANCE = 1.02` (`_icons.py:199`) and the per-target `frame` rules are only applied to `derived` sources that have not already been platform-framed (`_icons.py:241-242`, `:252-254`).
- **iOS icons come out alpha-free** (all 15 `RGB`, `_icons.py:109-114` — the App Store's no-alpha rule) and the two web maskables + the apple-touch icon come out opaque `RGB` (`_icons.py:140-159`), avoiding the black-corner failure mode.
- **All 28 Pillow API line refs in the study spot-check clean** — `PIL/Image.py` 147/968/1017/1369/1442/1479/1565/1779/1840/1932/1988/2048/2329/2592/2731/2796/3097/3193/3242/3585/3722, `PIL/ImageOps.py` 73/272/334/518/690, `PIL/ImageFilter.py` 186, plus `PIL/_deprecate.py:50-54`. **Two corrections to the study**: `DecompressionBombWarning` is at `PIL/Image.py:75` (the study says `IMG:79`, which is `DecompressionBombError`), and `ImageOps.cover` is at `PIL/ImageOps.py:303` (the study says `OPS:300`).
- **`Pillow` is the only dependency of `flet_platform_assets`** (`METADATA:12`) and the package imports nothing from `flet` or `flet-cli` — so it can be driven standalone from a test or a CI step without the Flutter/Android toolchain.
- **`pillow` ships no runtime requirements** (`pillow-12.3.0.dist-info/METADATA:27-33` — docs extras only), so adding it to a build group costs nothing transitively.

## Unverified

- **That a real `flet build apk` reproduces my isolated render byte-for-byte.** The renderer is pure (images in → images out) and the pipeline is hash-stamped, so the images must match, but no `build/` directory exists in the repo and the Flutter/Android SDKs are not provisioned on this host. Every asset quoted here was produced by calling the installed `flet_platform_assets` directly with the options `build_base.py` resolves for `config_platform = "android"`.
- **That the pinned cookiecutter template in `%TEMP%\flet-tpl` is byte-identical to the one `flet build` would download.** It is the template `flet-cli` cached on this host (cookiecutter.json defaults: `splash.color "#ffffff"`, `splash.dark_color "#222222"`, `adaptive_icon_background "#ffffff"`), and the app overrides the first two via `pyproject.toml:40-41` — but the download itself was not re-performed.
- **The exact launch-screen composition at runtime** (layer order, gravity, the `values-night` selection) is inferred from the template XML quoted in F1; it was not observed on a device.
- **The Flutter-side boot screen.** `pyproject.toml:33-37` selects the built-in `"flet"` boot screen with a `startup_message`; its `bgcolor_light`/`bgcolor_dark` live in the Dart client inside the same template and are not audited here.
- **Whether `uv lock --upgrade` would actually select Pillow 13.0.0.** PyPI reports `pillow 13.0.0` as the latest release (it raises `Requires-Python` to `>=3.11`, which this project satisfies), but I did not regenerate the lock.
- **Whether the always-dark splash and the white adaptive-icon background are deliberate brand decisions.** `docs/decisions.md` has no entry for either; `O-1` (`:39`) is still open.
- **The exact rasterisation of `icon.svg` to `icon.png`.** No SVG rasteriser is available on this host, so the PNG's provenance is inferred from geometry; Pillow cannot do it (F5).
- **Contrast ratios are WCAG-style relative-luminance ratios** computed from measured sRGB pixels — a proxy for perceived legibility, not a platform guideline.
