# flet-platform-assets 1.0.4 — exhaustive API reference

> Companion to `docs/reference/dep-flet-build-host.md` (summary) and `docs/roadmap.md` (M5 branding context).
> Every claim cites the installed source (`.venv/Lib/site-packages/flet_platform_assets/...`)
> or its caller in `flet_cli/commands/build_base.py` (`BB:`); anything not established there
> is labeled **unverified**. flet stays 1.0.4 per D-010. Verified 2026-10-16.

## 0. How to read this file

* `INIT:` = `__init__.py`; `MOD:` = `_models.py`; `SRC:` = `_source.py`; `IMG:` = `_imaging.py`;
  `ICO:` = `_icons.py`; `SPL:` = `_splash.py`; `WRI:` = `_write.py`; `BB:` = `flet_cli/commands/build_base.py`.
* Design mantra (from `METADATA` + `INIT:1-19` docstring): **rendering is separate from writing**.
  `render_*()` is pure (images in → images out, no FS, no prints); `write()` is the only step touching disk;
  diagnostics are data in `RenderResult.warnings`, never log output — the caller decides how to surface them.
* What it will not do (`METADATA`): never re-frame finished artwork — only transforms the platform actually
  requires (flattening where alpha is rejected, macOS grid, multi-size `.ico`, opaque maskables). Sole exception:
  the Android 12 splash icon, whose outer third the platform always crops, so artwork is fitted to the visible circle.

---

## 1. Identity

| Item | Value | Source |
|---|---|---|
| Package / version | `flet-platform-assets 1.0.4` | `flet_platform_assets-1.0.4.dist-info/METADATA:2-3` |
| Summary | `Generate app icons and splash screens for every platform Flet builds for` | `METADATA:4` |
| License | `Apache-2.0` | `METADATA:6` |
| Requires-Python | `>=3.10` | `METADATA:10` |
| Sole runtime dep | `pillow>=11.3.0` | `METADATA:12` |
| Coupling | Nothing imports `flet` or `flet-cli` — importable standalone | `METADATA` ("nothing here imports `flet` or `flet-cli`"); `INIT:` imports only `._*` + Pillow via `MOD:92` |
| Public surface | 27 names in `__all__` | `INIT:52-80`; live: `len(fpa.__all__) == 27` |
| Role | Build-host icon/splash renderer; its OUTPUT (mipmaps, `.ico`, catalogs) ships, the package doesn't | roadmap §3/D2; `BB:2088-2470` pipeline |
| APK relevance | Build-host only — none of the package ships into the APK | roadmap §3/D2 |

---

## 2. Models (`MOD:`) — every dataclass with signatures + defaults

### 2.1 `Target` — `MOD:106-126` (frozen)

```python
@dataclass(frozen=True)
class Target:
    relative_path: str
    size: int
    opaque: bool = False
    frame: str | None = None
```

One file to produce. `relative_path` = destination relative to the Flutter project root; `size` = side length px;
`opaque` = flatten onto the options' background, emit RGB (where a platform rejects alpha);
`frame` = name of a rule in `FRAMING` applied to this file alone (web needs all three at once: unmasked favicon,
circle-cropped maskable, iOS-style apple-touch — `MOD:115-119`).

### 2.2 `AssetSpec` — `MOD:128-144` (frozen)

```python
@dataclass(frozen=True)
class AssetSpec:
    targets: Sequence[Target] = ()
    ico_sizes: Sequence[int] = ()
```

Which files a platform wants, at what sizes. Defaults describe a stock Flutter project (sensible preview output
with no project on disk); `flet build` overrides with what the rendered project actually declares so it never writes
an unreferenced file (`MOD:132-136`).

### 2.3 `IconOptions` — `MOD:147-168` (frozen)

```python
@dataclass(frozen=True)
class IconOptions:
    background: tuple[int, int, int] = WHITE            # (255,255,255), IMG:46
    macos_style: str = "auto"                           # "auto" | "grid" | "raw"
    application_id: str = "com.example.app"
```

`background` fills three places: the mandatory iOS flatten (App Store rejects alpha), the macOS tile, and the opaque
web icons (2 maskables + apple-touch). A transparent source is expected, so this is the colour the user actually sees
on Apple platforms (`MOD:151-157`). `macos_style`: `"auto"` composes the inset squircle + shadow unless the source
already looks shaped; `"grid"` always composes; `"raw"` places full-bleed (`MOD:158-161`).

### 2.4 `SplashOptions` — `MOD:171-193` (frozen)

```python
@dataclass(frozen=True)
class SplashOptions:
    color: str = "#ffffff"
    dark_color: str = "#222222"
    icon_background: str | None = None
    icon_dark_background: str | None = None
    icon_fit: str = "contain"                           # "contain" | "none"
```

`color`/`dark_color` = light/dark backgrounds as `#rrggbb`. `icon_background`: background behind the Android 12 splash
icon — setting it changes that icon's canvas from 1152px-equivalent (288dp) to 960-equivalent (240dp), per platform
spec (`MOD:178-180`). `icon_fit`: `"contain"` fits artwork inside the guaranteed-visible circle; `"none"` passes
through untouched (what flutter_native_splash did) (`MOD:182-186`).

### 2.5 `RenderedAsset` — `MOD:195-210` (frozen)

```python
@dataclass(frozen=True)
class RenderedAsset:
    relative_path: str
    image: Image.Image
    @property
    def path(self) -> Path: ...   # MOD:207-210, Relative_path as Path
```

One produced image, not yet written anywhere.

### 2.6 `RenderResult` — `MOD:213-246` (mutable)

```python
@dataclass
class RenderResult:
    assets: list[RenderedAsset] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ico: dict[str, dict[int, Image.Image]] = field(default_factory=dict)
    stale: list[str] = field(default_factory=list)
    def add(self, relative_path: str, image: Image.Image) -> None: ...   # MOD:239-241
    def warn(self, message: str) -> None: ...                            # MOD:243-246
```

`ico` kept apart from `assets` because one `.ico` is many images in one file (`MOD:224-226`); `stale` = files a
previous generator left behind that this render replaces (cookiecutter overwrites but never deletes — a dark splash
after dark mode off, a `.webp` after source change, would otherwise keep being served — `MOD:227-231`).

---

## 3. `load_source` / `square` (`SRC:`)

### 3.1 `MAX_SOURCE_SIZE = 2048` — `SRC:11-17,259-265`

Sources larger than this are reduced once (to 2048 on the long side) rather than per output: every target resamples
from the source, so an 8000px original would be downscaled a dozen times; one reduction to comfortably above the
largest target (1024) costs nothing visible and bounds the work.

### 3.2 `load_source(path)` — `SRC:24-90,272-325`

```python
class SourceError(Exception): ...                                    # SRC:20-22,268-270
def load_source(path: str | Path) -> tuple[Image.Image, bool]:
```

Reads + normalises user input into safe-to-composite RGBA: EXIF-rotated phone photos, palette/CMYK PNGs, animated
GIFs, non-square banners, pre-made `.ico`/`.icns` (`SRC:249-258` docstring). Steps (`SRC:291-325`):

1. `Image.open(path)` + `img.load()`; `FileNotFoundError` → `SourceError("icon source not found: ...")`;
   `(UnidentifiedImageError, OSError, ValueError)` → `SourceError("could not read image ...")` (`SRC:293-298`).
2. `pre_rendered = suffix in (".ico", ".icns")`; when true, `_largest_frame()` picks the highest-res frame
   (`img.ico.getimage(max(sizes()))`, fall back to as-opened on any error — `SRC:353-362`).
3. `ImageOps.exif_transpose(img) or img` (`SRC:305`).
4. Animated (`n_frames > 1`): `seek(0)` — first frame is the icon (`SRC:308-309`).
5. Non-RGBA → `convert("RGBA")` (`SRC:311-312`).
6. Long side > 2048: single `RGBa`-premultiplied `LANCZOS` reduction, back to RGBA (`SRC:314-323`).
7. Returns `(img, pre_rendered)` (`SRC:325`).

### 3.3 `square(img)` — `SRC:80-103,328-350`

```python
def square(img: Image.Image) -> tuple[Image.Image, str | None]:
```

Pads the short axis with transparency, centred — never stretch (distorts) or crop (discards). Returns
`(squared, warning_or_None)`; warning text advises supplying a square image (`SRC:347-350`). Note `customize_icons`
deliberately does NOT square first — centring happens per-icon anyway, and pre-padding would make opaque artwork look
like a glyph and get it reframed on top of letterboxing (`BB:2140-2147`).

---

## 4. Icon matrix (`ICO:`) — every platform's size lists, quoted verbatim

### 4.1 Constants

```python
ADAPTIVE_SAFE_FRACTION = 72 / 108                       # ICO:51 — visible fraction of adaptive foreground
ANDROID_MIPMAP_SIZES = {                                # ICO:53-59
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
ANDROID_ADAPTIVE_SIZES = {                              # ICO:61-67
    "drawable-mdpi": 108,
    "drawable-hdpi": 162,
    "drawable-xhdpi": 216,
    "drawable-xxhdpi": 324,
    "drawable-xxxhdpi": 432,
}
WINDOWS_ICO_SIZES = (16, 32, 48, 256)                   # ICO:71 — Explorer/taskbar/alt-tab each pick differently;
                                                        # single-256 downscaled everywhere looks mushy (ICO:69-70)
LINUX_HICOLOR_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)  # ICO:76 — exactly what the hicolor index declares;
                                                        # undeclared dir = never found; wrong pixels = wrong scale (ICO:73-75)
_IOS_ICONS = {                                          # ICO:78-94
    "Icon-App-20x20@1x.png": 20,   "Icon-App-20x20@2x.png": 40,   "Icon-App-20x20@3x.png": 60,
    "Icon-App-29x29@1x.png": 29,   "Icon-App-29x29@2x.png": 58,   "Icon-App-29x29@3x.png": 87,
    "Icon-App-40x40@1x.png": 40,   "Icon-App-40x40@2x.png": 80,   "Icon-App-40x40@3x.png": 120,
    "Icon-App-60x60@2x.png": 120, "Icon-App-60x60@3x.png": 180,
    "Icon-App-76x76@1x.png": 76,   "Icon-App-76x76@2x.png": 152,
    "Icon-App-83.5x83.5@2x.png": 167,
    "Icon-App-1024x1024@1x.png": 1024,
}
_MACOS_ICONS = {f"app_icon_{s}.png": s for s in (16, 32, 64, 128, 256, 512, 1024)}  # ICO:96
_IOS_DIR = "ios/Runner/Assets.xcassets/AppIcon.appiconset"      # ICO:98
_MACOS_DIR = "macos/Runner/Assets.xcassets/AppIcon.appiconset"  # ICO:99
_ANDROID_RES = "android/app/src/main/res"                       # ICO:100
```

### 4.2 Default specs (`_default_specs()` / `DEFAULT_SPECS` — `ICO:103-166`)

| Platform | Files |
|---|---|
| `ios` | 15 `_IOS_ICONS` entries under `_IOS_DIR`, ALL `opaque=True` (App Store rejects alpha; review tooling checks) |
| `macos` | 7 `_MACOS_ICONS` under `_MACOS_DIR` |
| `android` | 5 `ic_launcher.png` mipmaps + 5 `ic_launcher_foreground.png` adaptive layers under `_ANDROID_RES` |
| `windows` | `AssetSpec(ico_sizes=WINDOWS_ICO_SIZES)` — pixels live in `result.ico`, not `assets` |
| `web` | `web/favicon.png` 32; `web/icons/Icon-192.png` 192; `web/icons/Icon-512.png` 512; `web/icons/Icon-maskable-{192,512}.png` opaque + `frame="maskable"`; `web/icons/apple-touch-icon-192.png` opaque + `frame="apple-touch"` (template's index.html links it though flutter_launcher_icons never generated it) |
| `linux` | `AssetSpec()` (empty — names depend on the desktop-entry id; filled by `linux_targets()`) |

### 4.3 Framing (`FRAMING`, `FRAMING_TOLERANCE`, `_frame`)

```python
FRAMING = {                                             # ICO:177-197
    "ios": (0.60, alpha_extent),
    "macos": (0.68, alpha_extent),
    "android": (0.567, radial_extent),   # radial: mask is circular; 0.567 lands furthest point at 85% of mask radius
    "maskable": (0.80, radial_extent),   # spec safe zone = circle 80% of width
    "apple-touch": (0.60, alpha_extent), # = native iOS rule
    "splash": (0.60, alpha_extent),      # icon-derived splash only; icons fill canvas by design
}
FRAMING_TOLERANCE = 1.02                                # ICO:199 — idempotence slack; skips lossy no-op resamples
```

`_frame(source, rule)` (`ICO:303-330`): unknown rule → return as-is; measure extent; opaque (`None`) → untouched
(a finished icon, not a glyph); already within `target * 1.02` → untouched; else `scale_to_fit` to
`side * target / current` measured/re-centred on the LONGEST side, `place()`d back on the original side. Shrink-only
⇒ idempotent and safe on anything. `render_icons(..., derived=True)` frames a generic `icon.png` for the platform's
mask; an `icon_<platform>.png` (`derived=False`) is the author's finished composition and is never reframed
(`ICO:202-271` docstring + `BB:2100-2110` resolution).

### 4.4 `render_icons()` — `ICO:202-271`

```python
def render_icons(
    source: Image.Image,
    options: IconOptions | None = None,
    spec: AssetSpec | None = None,
    *,
    platform: str,            # "ios" | "macos" | "android" | "windows" | "web" | "linux"
    pre_rendered: bool = False,
    derived: bool = False,
) -> RenderResult:
```

Unknown platform → `ValueError` (`ICO:256-257`); `spec=None` → `DEFAULT_SPECS[platform]`; macOS → `_render_macos`,
Linux → `_render_linux`, else per-target `_plain` with (rule,size,opaque)-memoised renders (`ICO:258-278`); Android
adds adaptive-safe-zone warning; web adds maskable warning; any `spec.ico_sizes` renders
`windows/runner/resources/app_icon.ico` entries (`ICO:280-287`); always `_warn_low_resolution`.

macOS (`_render_macos`, `ICO:350-394`): unknown `macos_style` → `ValueError`; `raw` or auto-detected pre-shaped
(`pre_rendered or looks_pre_shaped(source)`) → place as-is + warning naming `macos.icon_style = "grid"` override;
else compose `apple_grid` ONCE at the largest size, LANCZOS-downscale for the rest (the one place chained downscaling
is correct — tile+art+shadow shrink together).

Linux (`_render_linux`, `ICO:396-415`): `spec.targets or linux_targets(application_id).targets`; `flet build` always
passes the per-app spec (`BB:2260-2263`).

### 4.5 `linux_targets()` / `web_targets_from_manifest()` — `ICO:436-460,497-540`

```python
def linux_targets(application_id: str) -> AssetSpec: ...
def web_targets_from_manifest(manifest: dict, favicon_size: int = 32) -> AssetSpec: ...
```

`linux_targets`: `linux/icons/hicolor/{s}x{s}/apps/{application_id}.png` for all 8 hicolor sizes + `linux/app_icon.png`
256 (the GTK runner's direct window icon). `web_targets_from_manifest`: favicon + every `manifest.icons[]` entry with
parseable `NNNxMMM` sizes (`maskable` purpose ⇒ opaque + maskable frame; skips entries without `x` in sizes or
unparseable ints) + apple-touch. `flet build` uses both to follow the rendered project's own declaration (`BB:2240-2258`).

### 4.6 Diagnostics

* `_warn_low_resolution` (`ICO:273-301`): source long side < largest produced ⇒ warn with both numbers; iOS/macOS 1024
  is the App Store listing image — softness lands where it is looked at most.
* `_warn_adaptive_safe_zone` (`ICO:417-434`): transparent artwork past 72/108 of canvas ⇒ warn (opaque squares exempt).
* `_warn_maskable_safe_zone` (`ICO:462-495`): only for explicit `icon_web.png` (generic already fitted; explicit is
  the author's composition — warn, don't touch); opaque exempt (bleed is the point).

---

## 5. Splash (`SPL:`) — full matrix

```python
ANDROID_DENSITIES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}  # SPL:34
IOS_SCALES = {"": 1, "@2x": 2, "@3x": 3}                                            # SPL:35
WEB_SCALES = {"1x": 1, "2x": 2, "3x": 3, "4x": 4}                                    # SPL:36
ANDROID_12_VISIBLE_FRACTION = 2 / 3                                                 # SPL:42
ANDROID_12_CANVAS_DP = 288; ANDROID_12_CANVAS_DP_WITH_BACKGROUND = 240              # SPL:40-41 (288dp/192dp circle,
                                                                                    # 240dp/160dp with background — same 2/3)
```

Sizes follow `width * density / 4` (Dart-truncated, via `density_size` — `SPL:125-129`, `IMG:88-103`) replicating
flutter_native_splash, so a 1024px source renders at 256 dp/pt/CSS px (`SPL:1-13`). Only pixels are produced; the
XML/storyboard/HTML referencing them are static template files (`SPL:11-13`).

```python
def render_splash(
    light: Image.Image,
    dark: Image.Image | None = None,
    options: SplashOptions | None = None,
    *,
    platform: str,        # "android" | "ios" | "web"
    derived: bool = False,
) -> RenderResult:
```

No `spec` (splash file list is conventional, nothing to override — `SPL:81-83`); unknown `icon_fit` or platform →
`ValueError` (`SPL:100-101,121`); `derived` frames icon-sourced art with the `"splash"` rule first (`SPL:103-106`).

| Platform | Outputs |
|---|---|
| android (`_render_android`, `SPL:131-175`) | Per density: `drawable-{d}/splash.png` + `drawable-{d}/android12splash.png` (fitted canvas, `SPL:177-210`); `-night-` variants when dark art or dark icon background present, else listed `stale`; legacy FNS `background.png`/`launch_background.xml` under `drawable{,-v21,-night,-night-v21}` listed stale (`SPL:52-65` — Android now uses `@color/flet_splash_background` instead) |
| ios (`_render_ios`, `SPL:228-258`) | `LaunchImage{suffix}.png` + `LaunchImageDark{suffix}.png` at 1x/2x/3x — all six always written (catalog declares them unconditionally); dark missing ⇒ light reused. Plus 1x1 `background.png` + `darkbackground.png` swatches (storyboard-stretched; chosen over `.colorset` whose `namedColor` needs a newer `toolsVersion` — `SPL:253-258`) |
| web (`_render_web`, `SPL:266-287`) | `web/splash/img/light-{1x..4x}.png` + dark twins (light reused when no dark); always `.png` whatever the source ext (FNS named after source, emitting srcsets pointing at never-written files); stale `.webp` twins listed |

`_android_12` (`SPL:177-210`): opaque art (`radial_extent None`) or art already inside the circle ⇒ placed whole and
left to crop (a finished composition, not a glyph); else scaled so furthest point lands on the circle. `icon_fit="none"`
+ art past the circle ⇒ crop warning (`SPL:212-226`).

---

## 6. Imaging helpers (`IMG:`) + `write()` (`WRI:`)

Compositing rules (`IMG:366-379`): resample ONCE from full-res source (chained downscaling = mushy small icons);
premultiplied-alpha (`RGBa`) LANCZOS so soft edges don't halo.

| Helper | Signature | Notes |
|---|---|---|
| `parse_hex_color` | `(value: str) -> tuple[int,int,int]` (`IMG:64,429-450`) | `#rrggbb`/`rrggbb`/3-digit; `ValueError("not a hex colour: ...")` |
| `density_size` | `(width, height, density: float) -> (w,h)` (`IMG:88,453-473`) | Dart `w*density~/4` truncation (differs from `//` at hdpi 1.5); min 1x1 |
| `scale_to_height` / `scale_to_fit` | `(art, height/box: int)` (`IMG:111-119,476-490`) | Aspect-preserving; single `_resample`; identity resize skipped (premultiply round-trip is lossy near-zero alpha — `IMG:493-513`) |
| `superellipse_mask` | `(size, n, supersample=4)` (`IMG:151,516-575`) | `|u|^n+|v|^n<=1`, row-solved + boundary-corrected, LANCZOS-downsampled |
| `place` | `(art, canvas, *, bg=None, tile=None, tile_n=WEB_TILE_N, tile_color=WHITE, offset=(0,0))` (`IMG:213-260,578-623`) | Centre scaled art; `bg` ⇒ flatten to RGB; `tile` ⇒ superellipse plate |
| `apple_grid` | `(art, canvas=1024, *, tile_ratio=MACOS_TILE_RATIO, n=5.0, blur=11, dy=8, shadow_alpha=64, tile_color=WHITE)` (`IMG:261,626-677`) | 824/1024 tile + shadow measured from Apple icons/template default |
| `alpha_extent` / `radial_extent` | `(img) -> float | None` (`IMG:315,471,680-706,836-885`) | Axis vs circular reach; `None` = fully opaque (finished composition) |
| `looks_pre_shaped` | `(img, *, min_fill=0.70, aspect_tolerance=0.08)` (`IMG:344-345,709-754`) | Filled near-square tile with cut corners vs plain logo (Flet mark 0.77/0.56 vs shaped 1.00/0.84) |
| `has_transparent_corners` | `(img, *, probe=0.06, threshold=8)` (`IMG:392,757-784`) | Corner-box mean-alpha test |
| `save_png` / `save_ico` | `(img, path)` / `(path, {size: img})` (`IMG:431-442,796-833`) | `optimize=True`, no metadata (deterministic per Pillow version); ICO base = largest (Pillow drops oversize), every size supplied (Pillow resamples from leaked loop var otherwise); empty ⇒ `ValueError` |
| constants | `WHITE=(255,255,255)` (`IMG:46,411-412`); `MACOS_TILE_RATIO=824/1024`, `SQUIRCLE_N=5.0`, `SHADOW_BLUR=11`, `SHADOW_DY=8`, `SHADOW_ALPHA=64` (`IMG:53-57,414-422`); `WEB_TILE_INSET=0.953`, `WEB_TILE_N=4.0` (`IMG:60-61,424-426`) | |

```python
def write(result: RenderResult, project_dir: str | Path, *, declared_only: bool = True) -> list[Path]:  # WRI:13-57
```

Deletes `result.stale` files that exist; writes each asset via `save_png` unless `declared_only` and the file doesn't
already exist; writes each `.ico` via `save_ico` under the same guard; returns written paths in production order
(stale removals excluded). `flet build` passes `declared_only = platform not in {"android","linux"}`
(`BB:2171`, `ICONS_CREATED_FRESH BB:109`) and `False` for splashes (`BB:2444`).

---

## 7. Adaptive-icon / background handling

The single most misunderstood knob in M5 — exact mechanics:

1. `adaptive_icon_background` is a **colour resource, not pixels**. `build_base` resolves
   `options.android_adaptive_icon_background or tool.flet.android.adaptive_icon_background or icon_background_value("android") or "#ffffff"`
   (`BB:1645-1653`) and hands it to the cookiecutter template (`BB:1644`), which authors it like the splash colours.
   The foreground PIXELS come from `ANDROID_ADAPTIVE_SIZES` layers (`drawable-*/ic_launcher_foreground.png`).
2. `icon_background` (global or per-platform) is PIXELS-side: parsed by `_resolve_icon_background()`
   (platform-over-global, invalid ⇒ white + warning — `BB:2198-2237`) into `IconOptions.background`, flattening iOS,
   the macOS tile, and opaque web icons. It ALSO falls through to Android's resource (`BB:1649-1652`), so one colour
   can cover every platform.
3. The Android 12 splash icon background (`SplashOptions.icon_background`) additionally SHRINKS the canvas
   (288dp → 240dp, `SPL:40-41`) per platform spec — the only size-changing background in the system.
4. CLI aliases: `dest="android_adaptive_icon_background"` (`BB:437`); splash keys renamed in 1.0.0 with old names
   still read (`SPLASH_KEY_ALIASES BB:114-118`; mapping `icon_background→icon_bgcolor`, `icon_dark_background→icon_dark_bgcolor`,
   `icon_fit→android_12_fit`, `BB:115-117`); template data key stays `adaptive_icon_background` (`BB:1645`).

---

## 8. How flet-cli consumes it (`BB:`)

* Import: `IconOptions, SplashOptions, load_source, render_icons, render_splash, ...` (`BB:14-25`); targets:
  `ICON_PLATFORMS` maps build targets → asset platform names (`BB:93-102`); splash targets `SPLASH_PLATFORMS`
  (`BB:120-126`, macOS/Windows/Linux absent ⇒ no splash); generator versions `ICONS_GENERATOR_VERSION=1`,
  `SPLASH_GENERATOR_VERSION=3` feed the hash stamps (`BB:88-89`).
* Icons (`customize_icons`, `BB:2088-2174`): hash-stamped (`build/.hash/icons` + template digest); source =
  `assets/icon_{platform}.*` else `assets/icon.*` (`derived` = fell through to generic; `BB:2100-2110`);
  none ⇒ restore template originals from `build/.icons-orig` and return (`BB:2116-2122`, backup/restore
  `BB:2293-2351`); unchanged + nothing missing ⇒ skip (`BB:2129-2131`, `_icons_missing BB:2271-2291`);
  `macos.icon_style` pyproject → `IconOptions.macos_style` (`BB:2113`); spec from rendered project
  (`_icon_spec`: web manifest, Linux per-app, Windows existing `.ico` sizes — `BB:2239-2269`) else defaults;
  `write(result, flutter_dir, declared_only=...)` (`BB:2171`).
* Splash (`customize_splash_images`, `BB:2353-2470`): gated by `template_data["splash"][platform]`
  (`BB:2366-2369`, from `_resolve_splash` `BB:1723-1761`: per-platform toggles default ON,
  `color` default `#ffffff`, `dark_color` default `#222222`); artwork fallback chain
  `splash_{platform} → splash → icon(derived)` + `splash_dark_{platform} → splash_dark`
  (`BB:2372-2388`) terminating at the template's `images/icon.png` (`BB:2398-2402`);
  `SplashOptions(color, dark_color, icon_background, icon_dark_background, icon_fit or "contain")`
  (`BB:2389-2393`, via `splash_setting()` platform-over-global `BB:1695-1721`);
  splash squared with warning (`BB:2431-2435`, icons are NOT — `BB:2140-2147`);
  `write(..., declared_only=False)` + iOS storyboard size-hint patch (`BB:2444-2446`).
* Asset lookup `find_platform_image()` matches by stem with image extensions (`BB:2088-2110` context);
  `get_ico_sizes()` reads existing `.ico` so rebuilds keep the project's entry list (`BB:2264-2268`).

---

## 9. How flet-platform-assets makes our app significantly better than Termux's proot-distro

Termux's proot-distro has no brand surface at all — it lives inside someone else's launcher icon. This package is what
turns our wrapper into a shippable product:

1. **One `assets/icon.png` → every store listing.** iOS 1024 marketing icon, macOS grid tile, Android mipmaps +
   adaptive layers, Windows multi-entry `.ico`, Linux hicolor tree, PWA icons — all from a single source at CI time.
   No per-store manual export, no designer retainer.
2. **Correct-by-construction platform compliance.** iOS flatten (rejection-avoiding), adaptive safe-zone + maskable
   warnings (catch clipping before review screenshots), `.ico` multi-size (no mushy taskbar), hicolor-exact sizes
   (no wrong-scale icon cache) — the kind of polish gap that separates a side-loaded tool from a Play-listed app.
3. **Branded first-run.** The splash pipeline (light/dark, Android 12 fitted icon, iOS storyboard, web PWA splash)
   gives a branded launch from cold start — Termux shows a black terminal. For an app whose core UX IS a terminal,
   the splash is the only brand moment before the prompt.
4. **Zero-cost iteration.** Pure render/impure write split + hash-stamp skipping means re-running `flet build`
   without touching `assets/` costs nothing; changing one PNG regenerates everything deterministically
   (`optimize=True`, no metadata). Brand experiments are one-commit diffs.
5. **Dark-mode + adaptive backgrounds as config, not art.** `icon_background` / `adaptive_icon_background` /
   splash colours are strings in `pyproject.toml` — a dark-brand app avoids the white-square trap with zero new
   image assets.

---

## 10. Verification

* `__init__.py:1-80` design docstring + 27-name `__all__`.
* `_models.py:106-246` all six dataclasses + defaults; `WHITE` default origin `_imaging.py:46,411-412`.
* `_source.py:11-17` 2048 cap; `:20-22` SourceError; `:24-90,272-325` load pipeline (EXIF `ImageOps.exif_transpose`,
  `LANCZOS` single reduction, `_largest_frame`); `:80-103,328-350` square + warning text.
* `_imaging.py:46-61` all constants; `:64,429-450` hex parser; `:88,453-473` density truncation;
  `:111-148,476-513` scale/resample (premultiplied `RGBa`, identity skip); `:151,516-575` superellipse;
  `:213-309,578-623,626-677` place/apple_grid; `:315-422,680-784` extent/shape/corner probes;
  `:431-470,796-833` save helpers; `:471,836-885` radial extent (`BILINEAR` measure resize).
* `_icons.py:51-100` every size constant + iOS/macOS tables + dirs; `:103-166` default specs;
  `:177-199` FRAMING + 1.02; `:202-271` render entry; `:273-301` low-res; `:303-348` frame/plain;
  `:350-415` macOS/Linux; `:417-460` adaptive warn + linux_targets; `:462-540` maskable warn + manifest targets.
* `_splash.py:34-65` densities/scales/2-3 fraction/stale list; `:67-129` entry + validation;
  `:131-226` Android + canvas + warnings; `:228-287` iOS + web.
* `_write.py:13-57` declared_only/write/stale/return contract.
* `flet_platform_assets-1.0.4.dist-info/METADATA:2-12` identity + `pillow>=11.3.0`.
* `flet_cli/commands/build_base.py:14-25,88-126,1645-1653,1695-1761,2088-2174,2198-2269,2271-2351,2353-2470`
  full CLI consumption; `ICONS_CREATED_FRESH :109`; key aliases `:114-118`.
* Live: `len(fpa.__all__)==27` (2026-10-16).
