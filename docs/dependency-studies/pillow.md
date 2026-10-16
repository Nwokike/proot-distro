# Pillow 12.3.0 — exhaustive API reference (toolchain view)

> Companion to `docs/reference/dep-flet-build-host.md` (summary) and `docs/roadmap.md` (M5 + app context).
> Pillow here is covered **as the image engine this toolchain relies on** — not the whole library.
> Every claim cites the installed source (`.venv/Lib/site-packages/PIL/...`) or live introspection;
> anything not established there is labeled **unverified**. flet stays 1.0.4 per D-010. Verified 2026-10-16.

## 0. How to read this file

* `IMG:` = `PIL/Image.py`; `OPS:` = `PIL/ImageOps.py`; `FLT:` = `PIL/ImageFilter.py`; `INI:` = `PIL/__init__.py`;
  `VER:` = `PIL/_version.py`; `FPA-*:` = `flet_platform_assets` call sites (the toolchain contract).
* Only Pillow APIs exercised by `flet-platform-assets` get full signatures; the "broader surface" (§5) is the
  shortlist relevant to our app's future needs (image loading/conversion if ever), each with its installed-source ref.
* Anti-hallucination: no method is listed without a `grep`-confirmed `def` in the installed tree.

---

## 1. Identity

| Item | Value | Source |
|---|---|---|
| Package / version | `pillow 12.3.0` | `VER:` (`__version__ = "12.3.0"`); `pillow-12.3.0.dist-info/METADATA:2-3` |
| Summary | `Python Imaging Library (fork)` | `METADATA:4` |
| License | `MIT-CMU` | `METADATA:6` (`License-Expression: MIT-CMU`) |
| Requires-Python | `>=3.10` (incl. 3.10–3.14 classifiers, CPython + PyPy) | `METADATA:24,30-35` |
| Runtime deps | **None** (docs extras only: furo/olefile/sphinx…) | `METADATA:27-33` |
| Wheel tag (this host) | `cp314-cp314-win_amd64`, `Root-Is-Purelib: false` (compiled `_imaging` present) | `pillow-12.3.0.dist-info/WHEEL`; `_imaging.cp314-win_amd64.pyd` on disk |
| Range dep | `pillow>=11.3.0` from `flet-platform-assets` — independent of flet's version | `flet_platform_assets-1.0.4.dist-info/METADATA:12` |
| Role | Image engine behind icon/splash rendering (`load_source` → EXIF transpose → RGBA → LANCZOS) | roadmap §3/D2 |
| APK relevance | Build-host only; nothing ships to the APK. Android packaging notes in §6 | roadmap §3/D2 |

Live introspection (2026-10-16):

```text
Pillow 12.3.0 | LANCZOS = 1 | Resampling: NEAREST BOX BILINEAR HAMMING BICUBIC LANCZOS
webp True | jpg True | zlib True   (PIL.features.check on this host)
Image.new('RGBA',(4,4)) -> mode RGBA size (4,4)
```

---

## 2. The exact calls flet-platform-assets makes (toolchain contract)

Quoted verbatim from installed `flet_platform_assets`; each row is a Pillow API we implicitly depend on.

| # | Call (as written) | Pillow API + installed ref | What it does for the toolchain |
|---|---|---|---|
| 1 | `Image.open(path)` (`_source.py:45`) | `IMG:3585` `def open(fp, mode="r", formats=None)` — lazy identify; data unread until `load`/processing (`IMG:3585-3600` docstring) | Entry point for every icon/splash source |
| 2 | `img.load()` (`_source.py:46`) | `IMG:968` `Image.load() -> PixelAccess \| None` | Forces decode before further handling |
| 3 | `ImageOps.exif_transpose(img) or img` (`_source.py:57`) | `OPS:690` `def exif_transpose(image, *, in_place=False)` — orientation 2–8 mapped to Transpose ops, tag stripped (`OPS:700-730`) | Phone-photo sources composited upright |
| 4 | `img.seek(0)` (`_source.py:60`, animated guard `n_frames > 1`) | `IMG:2731` `def seek(self, frame)` | First frame of GIF/WebP/etc. is the icon |
| 5 | `img.convert("RGBA")` / `convert("RGBa")` (`_source.py:62,69; _imaging.py:148,510-513`) | `IMG:1017` `def convert(self, mode=None, matrix=None, dither=None, palette=WEB, colors=256)` | Normalise palette/CMYK/grey → RGBA; `RGBa` = premultiplied workspace for halo-free resampling |
| 6 | `img.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")` (`_imaging.py:148`) | `IMG:2329` `def resize(self, size, resample=None, box=None, reducing_gap=None)`; default filter BICUBIC, LANCZOS passed explicitly (`IMG:2329-2360` docstring). `Image.LANCZOS == 1` and `== Resampling.LANCZOS` (live) | The one-step halo-free resample; identity resize skipped (lossy near-zero alpha — `_imaging.py:128-148` docstring) |
| 7 | `Image.new("RGBA", (side,side), (0,0,0,0))` et al. (`_source.py:97`; `_imaging.py:174,209,241-309`) | `IMG:3193` `def new(mode, size, color=0)` — tuple color per band; `None` = uninitialised (`IMG:3193-3220` docstring) | Canvases, tiles, shadows, 1x1 swatches |
| 8 | `Image.frombytes("L", (t,t), bytes(data))` (`_imaging.py:209`) | `IMG:3242` `def frombytes(mode, size, data, ...)` | Superellipse mask construction |
| 9 | `mask.resize((size,size), Image.LANCZOS)` (`_imaging.py:210`); `composed.resize(...)` (`_icons.py:391`); `alpha.resize(..., Image.BILINEAR)` (`_imaging.py:505`) | Same `IMG:2329`; **note** `_imaging` deliberately avoids `thumbnail` (its default `reducing_gap=2.0` two-step softens small sizes — `_imaging.py:128-148` docstring) | Mask downsample; macOS chained composition; radial-extent measure |
| 10 | `canvas.alpha_composite(img, xy)` / `out.alpha_composite(art, ...)` (`_source.py:98`; `_imaging.py:248-310`) | `IMG:1932` `Image.alpha_composite(self, im, dest, source)` (in-place) | Squaring, tile plates, shadow layering |
| 11 | `out.paste(art, (x,y), art)` (`_imaging.py:245`) | `IMG:1840` `def paste(self, im, box=None, mask=None)` | Flatten path (bg given): art pasted with its own alpha as mask onto RGB |
| 12 | `tile.putalpha(mask)` / `silhouette.putalpha(...)` (`_imaging.py:248,304`) | `IMG:2048` `def putalpha(self, alpha: Image \| int)` | Tile shape, shadow silhouette |
| 13 | `img.getchannel("A")` (`_imaging.py:331,375,494`) | `IMG:2796` `def getchannel(self, channel)` | Alpha measurements (extent, corners, bbox, histogram) |
| 14 | `alpha.getextrema()` / `getbbox()` / `histogram()` / `crop()` / `point()` (`_imaging.py:332-511`) | `IMG:1565` getextrema; `IMG:1479` getbbox; `IMG:1779` histogram; `IMG:1369` crop; `IMG:1988` point | Opaque detection, bbox fill math, corner probes, thresholding |
| 15 | `shadow.filter(ImageFilter.GaussianBlur(blur))` (`_imaging.py:307`) | `IMG:1442` `def filter(self, filter)`; `FLT:186` `class GaussianBlur(MultibandFilter)` (`__init__(radius=2)`, `FLT:199-207`; no-op at 0) | macOS drop shadow; `MACOS_SHADOW_BLUR=11` |
| 16 | `Image.BILINEAR` (`_imaging.py:505`) | `IMG:147-164` `class Resampling` (`NEAREST BOX BILINEAR HAMMING BICUBIC LANCZOS` — live list) | Measure-only downscale in `radial_extent` |
| 17 | `img.save(path, format="PNG", optimize=True)` (`_imaging.py:433-438` via `save_png`); `.ico` multi-size save (`_imaging.py:442-470` via `save_ico`) | `IMG:2592` `def save(self, fp, format=None, **params)` — format from extension when omitted; unknown writer options silently ignored (`IMG:2592-2615` docstring) | Deterministic PNG output; ICO with explicit per-size images (works around Pillow dropping oversize + leaked-loop-var resample — `_imaging.py:442-470` docstring) |
| 18 | `Image.Transpose.*` (via `exif_transpose` orientation map, `OPS:700-730`) | `IMG:127` `class Transpose`; `IMG:3097` `def transpose(self, method)` | EXIF 2–8 handling |

Exception + plugin surface the toolchain touches: `UnidentifiedImageError` (caught → `SourceError`, `_source.py:47-49`);
ICO multi-frame via `img.ico.getimage(max(sizes()))` (`_source.py:353-362`, guarded `noqa BLE001` fallback);
`ExifTags.Base.Orientation` read inside `exif_transpose` (`OPS:700-730`).

---

## 3. `Image` essentials relied on (signatures)

```python
Image.open(fp, mode="r", formats=None) -> ImageFile.ImageFile          # IMG:3585
Image.new(mode, size, color=0) -> Image                                 # IMG:3193
Image.frombytes(mode, size, data, ...) -> Image                         # IMG:3242
Image.alpha_composite(im1, im2) -> Image  (module fn; NOT the one used) # IMG:3722
Image.load(self) / .convert(...) / .resize(size, resample, box, reducing_gap)
  / .crop(box) / .filter(f) / .paste(im, box, mask) / .alpha_composite(im, dest, source)
  / .putalpha(alpha) / .getchannel(ch) / .getbbox(alpha_only=True) / .getextrema()
  / .histogram() / .point(...) / .transpose(method) / .seek(frame) / .save(fp, format, **params)
                                                              # IMG:968,1017,2329,1369,1442,1840,
                                                              #   1932,2048,2796,1479,1565,1779,
                                                              #   1988,3097,2731,2592
Image.Resampling: NEAREST BOX BILINEAR HAMMING BICUBIC LANCZOS         # IMG:147-164
Image.Transpose / Transform / Dither / Palette / Quantize enums        # IMG:127-179
```

Key semantics: `open` is lazy (`IMG:3585-3600`); `resize` default is BICUBIC (LANCZOS always explicit in toolchain);
`save` infers format from extension; `getbbox(alpha_only=True)` default (`IMG:1479`); `convert` P-mode goes through
palette (`IMG:1017-1093`).

---

## 4. `ImageOps` / `ImageFilter` relied on (signatures)

```python
ImageOps.exif_transpose(image, *, in_place=False) -> Image | None      # OPS:681-730 (+Literal overloads 681-687)
ImageFilter.GaussianBlur(radius=2)                                     # FLT:186-207
```

`exif_transpose(in_place=True)` mutates and returns `None`; default returns transposed copy (or copy when no-op) and
strips the orientation tag incl. `info["exif"]` rewrite (`OPS:700-730` tail). Only other `ImageFilter` classes present
(unused by toolchain, listed for completeness): `Kernel/RankFilter/MedianFilter/MinFilter/MaxFilter/ModeFilter/
BoxBlur/UnsharpMask/BLUR/CONTOUR/DETAIL/EDGE_ENHANCE(+MORE)/EMBOSS/FIND_EDGES/SHARPEN/SMOOTH(+MORE)/Color3DLUT`
(`FLT:55-383` class index).

Other `ImageOps` present but NOT used by the toolchain (future-use candidates, §5): `autocontrast(image, cutoff=0,
ignore=None, mask=None, preserve_tone=False)` (`OPS:73`), `contain/cover/pad/fit(image, size, method=BICUBIC, ...)`
(`OPS:272,300,334,518`).

---

## 5. Broader Pillow API relevant to our app's future needs

Scope note: our app is a terminal + package-manager UI; Pillow is a BUILD-host dep today. The rows below are the
shortlist IF the app ever handles images itself (avatar/distro logos in-app, screenshot attach, share sheets).
Nothing here ships today — each is a verified-available API, not a recommendation to add a dependency.

| Need | API (installed ref) | Notes for us |
|---|---|---|
| Open any user/distro image | `Image.open` (`IMG:3585`) + `load()` (`IMG:968`) | Lazy — must `load()` inside try; catch `(UnidentifiedImageError, OSError)` exactly like `_source.py:47-49` |
| Normalise orientation | `ImageOps.exif_transpose` (`OPS:690`) | Phone-supplied PNGs/JPEGs; in-place variant exists |
| Convert for display/upload | `convert("RGB"/"RGBA")` (`IMG:1017`); `save(..., format="PNG"/"JPEG")` (`IMG:2592`) | JPEG has no alpha — flatten first or lose transparency silently |
| Thumbnail lists (distro catalog) | `contain/cover/fit/pad` (`OPS:272-560`) or manual `resize` (`IMG:2329`) | Toolchain rule still applies: premultiplied `RGBa` LANCZOS for soft logos; never chain-downscale |
| Blur/scrim behind sheets | `GaussianBlur` (`FLT:186`), `BoxBlur` (`FLT:209`) | Radius 0 = copy (cheap guard) |
| Read EXIF safely | `getexif()` + `ExifTags` (used inside `OPS:700-730`) | Strip orientation/location before sharing — privacy, not just correctness |
| Format support on host | PNG/JPEG/WebP/zlib present (live `features.check` True) | AVIF: `_avif` pyd + `AvifImagePlugin` ship in 12.3.0 tree — **unverified** at runtime decode level here |
| Decompression bombs | `DecompressionBombWarning/Error`, `_decompression_bomb_check` (`IMG:79,3564`) | Keep defaults if we ever open untrusted OCI-layer images |

Deliberately OUT of scope: `ImageDraw/ImageFont` (no in-app badge rendering planned), `ImageQt/Tk/Win/Grab/Show`
(desktop-only viewers), `ImageCms` (colour management overkill for logos), `ImageSequence` (no animated catalog art).

---

## 6. Android notes (pure-wheel? manylinux; not shipped to APK)

* Pillow is a **compiled** wheel on this host (`Root-Is-Purelib: false`, `cp314-win_amd64`, `_imaging*.pyd` present) —
  NOT pure-Python. It runs on the BUILD host (Windows/Linux CI) where pip provides matching wheels.
* It is **never resolved for Android**: no `flet build` path imports it on-device; it is not in the app's
  `[project].dependencies` (only `flet`, `flet-ads`, `flet-terminal`, `proot-distro` — project `pyproject.toml`);
  it arrives via the dev group (`flet-desktop` → `flet-platform-assets` → `pillow`) and the Forge/Android resolver
  never sees it. Roadmap §3/D2 + R3 msgpack note cover the Android-wheel discipline; Pillow needs no Forge entry
  because it never crosses the device boundary.
* manylinux: Pillow publishes `manylinux` wheels for Linux CI hosts — **unverified** for the exact
  `manylinux_x_y` tags of 12.3.0 in this tree (tag list lives on PyPI, not in installed source); the mechanism that
  matters is already proven — CI renders icons/splash on the host, only PNGs cross into the APK.
* If the app ever needed pixels on-device (distro-logo downscale in `ProotSession` output, share-sheet recode),
  prefer: (a) server/CI-side pre-rendered assets, or (b) Dart-side `flutter_image` decoding — adding Pillow to the
  Android closure would drag compiled native code into the APK for zero terminal benefit. Current stance: do NOT add.

---

## 7. How Pillow makes our app significantly better than Termux's proot-distro

Termux's proot-distro ships no images at all — its "brand" is whatever the terminal emulator draws. Pillow is two
layers under our entire visual identity:

1. **It IS the brand pipeline's engine.** Every number in `flet-platform-assets.md` (mipmaps 48–192, adaptive
   108–432, ICO 16/32/48/256, hicolor 8 sizes, iOS 15-file catalog, Android-12 2/3-circle fit) executes as Pillow
   ops: premultiplied-LANCZOS resamples, superellipse masks, EXIF transposes, deterministic `optimize=True` PNGs.
   Without it there is no one-PNG-to-every-store story — back to hand-exporting per density.
2. **Correctness users feel but never see.** Halo-free soft edges (premultiplied alpha), upright phone-photo sources
   (EXIF), non-mushy taskbar icons (multi-entry ICO), exact hicolor sizes (no wrong-scale cache) — each is one Pillow
   call in `_imaging.py`, each is a one-star review avoided.
3. **Deterministic CI.** `optimize=True` + no metadata ⇒ same Pillow version gives byte-identical icons; hash-stamp
   skipping in `build_base` means brand iteration is a clean one-PNG diff. Termux-side theming (PS1 colours, MOTD
   ASCII) can't be versioned, reviewed, or rolled back like this.
4. **Future image needs are already vetted.** If M3/M4 ever show distro logos, screenshot previews, or share-sheet
   recodes, the exact calls (`open/load/exif_transpose/convert/resize/save`, `contain/cover/fit`) are documented
   above with line refs — no new imaging dependency to evaluate.

---

## 8. Verification (file:line)

* Identity: `PIL/_version.py` (`__version__ = "12.3.0"`); `pillow-12.3.0.dist-info/METADATA:2-33`
  (name/version/license/py-requires/no runtime deps); `WHEEL` (`cp314-win_amd64`, `Root-Is-Purelib: false`).
* Toolchain calls: `flet_platform_assets/_source.py:45-49,57-72,97-98,105` + `_imaging.py:148,174,209-248,303-307,
  331-511` + `_icons.py:391` + `_splash.py` measure/resize paths — each mapped in §2 table.
* Signatures: `PIL/Image.py:127-179` enums; `:968` load; `:1017` convert; `:1369` crop; `:1442` filter;
  `:1479` getbbox; `:1565` getextrema; `:1779` histogram; `:1840` paste; `:1932` alpha_composite;
  `:1988` point; `:2048` putalpha; `:2329` resize; `:2592` save; `:2731` seek; `:2796` getchannel;
  `:3097` transpose; `:3193` new; `:3242` frombytes; `:3585` open; `:3722` module alpha_composite.
* Ops/filters: `PIL/ImageOps.py:73` autocontrast; `:272` contain; `:300` cover; `:334` pad; `:518` fit;
  `:681-730` exif_transpose; `PIL/ImageFilter.py:34-383` class index; `:186-207` GaussianBlur.
* CLI dep edge: `flet_platform_assets-1.0.4.dist-info/METADATA:12` (`pillow>=11.3.0`); project
  `pyproject.toml` (`[project].dependencies` has no pillow; dev group has `flet-desktop`).
* Live (2026-10-16): `Pillow 12.3.0`, `Image.LANCZOS == 1`, six Resampling members,
  `features.check(webp/jpg/zlib) == True`, `Image.new('RGBA',(4,4))` OK.
