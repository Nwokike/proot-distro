# dep-flet-cli.md — flet-cli 1.0.4 (build tool)

Verified 2026-10-16 against `.venv/Lib/site-packages/flet_cli` (D1 study). Host-only; never ships to Android.

## Pipeline (orchestration only)
`initialize_command` (paths, python version resolve, `.python-version` switch wipes `build/`) → toolchain bootstrap (`flutter_version` 3.44.8; auto-installs Flutter + Android SDK/JDK into `~/flutter/<ver>`) → `setup_template_data` (merge precedence CLI > `[tool.flet.<platform>]` > `[tool.flet]` > defaults) → `create_flutter_project` (hash-stamped cookiecutter render of the cached `flet-build-template.zip`) → `package_python_app` (shells `dart run serious_python:main package …` — **the pip/index/platform-tag logic lives in serious_python, NOT here**) → `register_flutter_extensions` (collects `site-packages/flutter/*` into pubspec path deps) → `flutter build apk` with `SERIOUS_PYTHON_*` + `FLET_ANDROID_SIGNING_*` env → artifacts copied to `build/apk|aab`.

## Verified flags/config (1.0.4 — docs may lie)
- `--android-legacy-packaging` exists; config `tool.flet.android.legacy_packaging` (default False). Context-only — the extract-vs-mmap behavior is in the template/Gradle side.
- `--android-extract-packages` exists; config `extract_packages`; forwarded as `SERIOUS_PYTHON_ANDROID_EXTRACT_PACKAGES` to `flutter build`.
- Arch flag is **`--arch`** (`--target-arch` does NOT exist); config `target_arch`.
- **`target_sdk_version` / `min_sdk_version` do NOT exist as keys in 1.0.4** (zero hits) — SDK levels come from the build template; do not add these keys.
- `.so → jniLibs` machinery (`copyOpt`, `.soref`, opt/ split) is **NOT in flet-cli** — it's in the serious_python/serious_python_android Gradle plugin fetched at build time. flet-cli offers no knob to inject a prebuilt `lib*.so`; the native binary must enter via a wheel/template path.
- `[tool.flet.flutter.pubspec.*]`: `dependencies`/`dependency_overrides`/`dev_dependencies` are **replaced per-section** (update semantics, not deep-merge); the rest deep-merged; applied post-render to pubspec.yaml via YAML (not cookiecutter).
- Cleanup keys: `cleanup.app/packages/app_files/package_files`; specifying files forces the bool true.
- Signing: key_store + key_alias may live in pyproject; **passwords only via CLI/env** (`FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD`, `_KEY_PASSWORD`).

## CI specifics
`--yes` mandatory (Flutter/SDK install prompts block); pin `FLET_CACHE_DIR` (template zip + python-build manifest) and `PYTHON_BUILD_RELEASE_DATE`; `-v`/`-vv` streaming, `--no-rich-output` for plain logs; artifacts land in `<app>/build/{apk,aab}` then renamed. `qrcode` (device-connect QR in `flet run`) and `colorama` have zero build relevance.
