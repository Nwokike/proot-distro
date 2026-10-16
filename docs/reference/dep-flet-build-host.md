# dep-flet-build-host.md — flet-desktop / flet-platform-assets / pillow

Verified 2026-10-16 against `.venv/Lib/site-packages` (D2 study). All build/dev-host only — **none ship into the APK**.

## flet-desktop 1.0.4 (Apache-2.0)
- The prebuilt desktop viewer client used by `flet run` (downloaded to `~/.flet/client/`, version-locked to flet).
- `flet build apk` does **NOT** need it (grep: only `run.py` + `pack.py` touch it); `run.py` ensures it via `ensure_flet_desktop_package_installed()` — skipped for `--web/--android/--ios`.
- Lockstep family member (auto-reinstall on mismatch per `flet/utils/pip.py`).

## flet-platform-assets 1.0.4 (Apache-2.0, requires pillow)
- Generates app icons + splash for every platform **at build time on the host**; its OUTPUT (Android mipmaps 48–192 px normal, 108–432 px adaptive; `.ico` sets; iOS catalogs) ships, the package doesn't.
- `adaptive_icon_background` is a template colour RESOURCE (no pixels); icon.png → mipmaps always needs Pillow.

## pillow 12.3.0 (MIT-CMU)
- The image engine behind icon/splash rendering (`load_source` → exif transpose → RGBA → LANCZOS). Range dep `>=11.3.0`, independent of flet's version.
- Our app: `[tool.flet] icon` (+ optional `icon_background`/`adaptive_icon_background`) goes through this pipeline in CI; nothing to configure locally.
