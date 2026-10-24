# pyproject.toml — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `pyproject.toml` · `.github/workflows/app.yml` · `docs/decisions.md` (D-003/D-004/D-010) · `docs/dependency-studies/flet-cli.md` · `.venv/lib/python3.14/site-packages/flet_cli` (1.0.4) · `uv.lock` · `src/core/constants.py` · **Date:** 2026-10-24

## What it does / how the app uses it

`pyproject.toml` is the single configuration surface for the Flet Android build (`flet build apk|aab`) plus pytest/ruff/tooling. It declares the app identity (`name`, `version = "1.0.0"`), the frozen runtime dependency set (flet/flet-ads/flet-terminal/httpx/proot-distro) and dev group (flet-cli/flet-desktop/pytest/pytest-timeout/ruff), the `[tool.flet]` Android build config (org/product/company/build_number/icon/app/boot_screen/splash/android/cleanup), pytest ini_options, and ruff lint config. CI (`app.yml`) enforces release-identity consistency (pyproject version/build_number ↔ `src/core/constants.py` ↔ env ↔ optional `version.json`) and builds split-per-ABI APKs + AAB.

## Findings

### F1 · P0 · `tool.flet.icon` has no verified consumption path in flet-cli 1.0.4
- **Where:** `pyproject.toml:28` (`icon = "src/assets/icon.png"`); flet-cli config-read inventory `.venv/lib/python3.14/site-packages/flet_cli/commands/build_base.py` + `commands/build.py`
- **What:** `[tool.flet].icon` is listed under `[tool.flet]` but `icon` does NOT appear in flet-cli's full `get_pyproject("tool.flet...")` key inventory (build_base.py:1641/1761+ resolve `boot_screen`, `splash`, `target_arch`, etc.; `icon.png` is resolved purely by on-disk lookup `find_platform_image(self.assets_path, "icon", hash)` at build_base.py:2103-2107, not by a pyproject key). No `tool.flet.icon` read exists anywhere in installed `flet_cli/`.
- **Evidence:** grep of all `get_pyproject("tool.flet` call sites in `flet_cli/` returns 34 distinct keys, none `tool.flet.icon`; `build_base.py:2107` reads `icon` from `self.assets_path` (i.e. `build/python-app/assets/icon.png`) with no pyproject fallback.
- **Fix / opportunity:** Remove `icon = "src/assets/icon.png"` from `[tool.flet]` (it is dead config), or document that icon sourcing is disk-driven and the `src/assets/icon.png` → `build/python-app/assets/icon.png` copy step is implicit elsewhere. `icon.svg` exists at `src/assets/icon.svg` (4.3 KB) but `icon.png` (99 KB) is what `find_platform_image` prefers.
- **Risk if ignored:** Operator assumes `tool.flet.icon` drives icon generation; it does not. Silent misconfiguration of the brand icon.

### F2 · P1 · `cleanup.package_files = ["oauthlib/**"]` does not prune `oauthlib-4.0.0.dist-info/`
- **Where:** `pyproject.toml:63` (`package_files = ["oauthlib/**"]`); flet-cli cleanup semantics `.venv/lib/python3.14/site-packages/flet_cli/commands/build_base.py:2755-2794`
- **What:** The cleanup glob `oauthlib/**` matches the `oauthlib/` package directory but NOT `oauthlib-4.0.0.dist-info/` (different directory name; glob prefix `oauthlib/` cannot match `oauthlib-4.0.0.dist-info/`). Both exist in the venv (`.venv/.../site-packages/oauthlib` and `.venv/.../site-packages/oauthlib-4.0.0.dist-info`). flet's `oauthlib` (4.0.0) is only needed for `Page.login()` (`flet/auth/authorization_service.py:93,120,208`), which the app does not ship (licensing A4), so the intent — drop ~1 MB — is sound, but the glob leaves the dist-info metadata behind.
- **Evidence:** `uv.lock:497-499` pins `oauthlib` version `4.0.0`; site-packages contains both `oauthlib` and `oauthlib-4.0.0.dist-info`. Cleanup globs are applied as `serious_python package --cleanup-package-files` per path (build_base.py:2706-2708).
- **Fix / opportunity:** Widen to also drop dist-info metadata, e.g. `package_files = ["oauthlib/**", "oauthlib-4.0.0.dist-info/**"]`, or accept residual metadata (small, non-user-visible).
- **Risk if ignored:** Residual `oauthlib-4.0.0.dist-info/` ships in the APK; minor size leakage, no functional break.

### F3 · P2 · `timeout_method` missing from pytest config; relying on pytest-timeout default
- **Where:** `pyproject.toml:89` (`timeout = 60`); `.venv/lib/python3.14/site-packages/pytest_timeout.py:72-100` (`--timeout_method`/`--timeout-method` choices `["signal","thread"]`, ini `timeout_method` at line 100)
- **What:** pytest-timeout 2.4.0 supports a `timeout_method` ini setting (default unresolved from source; `settings.method` flows through `get_env_settings` at pytest_timeout.py:150-175). pyproject sets `timeout = 60` but declares no `timeout_method`, so the runner uses the plugin default (UNVERIFIED which — signal vs thread). On Linux CPython 3.14 the default is typically `signal`; thread-based is safer where `signal` is unavailable/limited.
- **Evidence:** `pytest_timeout.py:100` `parser.addini("timeout_method", METHOD_DESC)`; `pytest_timeout.py:306` `timeout_method = settings.method`; pyproject has no `timeout_method` key. `pytest --co` collects cleanly (exit 0) so config is syntactically valid.
- **Fix / opportunity:** Add `timeout_method = "thread"` (or `"signal"` after confirming the default) next to `timeout = 60` for deterministic timeout behavior on device/desktop CI.
- **Risk if ignored:** Timeout enforcement method implicit; if default is `signal` and a test blocks in a non-main thread on Android-desktop parity runs, timeout may not fire → hung CI.

### F4 · P2 · ruff per-file-ignores reference deleted / missing files
- **Where:** `pyproject.toml:107-117` (`[tool.ruff.lint.per-file-ignores]`); `.venv/lib/python3.14/site-packages/flet_cli` ruff 0.17.1
- **What:** The per-file-ignores table lists `tests/check_flet_api.py`, `tests/test_flet_api_guard.py`, `build_flet_proot_wheel.py`, `check_elf_alignment.py`, `generate_third_party_sources.py`. On disk, `check_elf_alignment.py` and `generate_third_party_sources.py` are MISSING from the workspace root (referenced by `app.yml:175`/`app.yml:291` and `app.yml:115`/`app.yml:294` steps that would fail if run). `tests/check_flet_api.py` and `tests/test_flet_api_guard.py` exist. Ruff itself does not error on ignores for absent files, so this is dead config, not a build break — but it masks the fact that two CI-referenced scripts are absent.
- **Evidence:** `ls`: `check_elf_alignment.py` MISSING, `generate_third_party_sources.py` MISSING (others exist). `app.yml:8-9` includes both in `push.paths` and `app.yml:175,215,291,294` invoke them.
- **Fix / opportunity:** Either restore the two missing scripts (they are part of the Android build pipeline per app.yml) or remove their per-file-ignores and the app.yml steps that call them. Do not leave CI referencing nonexistent files.
- **Risk if ignored:** CI `apk`/`aab` jobs calling `check_elf_alignment.py`/`generate_third_party_sources.py` fail at runtime (script not found) → release blocked.

### F5 · P3 · `[tool.flet].product` is a placeholder and ruff `required-version` is UNVERIFIED
- **Where:** `pyproject.toml:24` (`product = "Proot Distro"`); `pyproject.toml:100-101` (`[tool.ruff] line-length`, `target-version`); `docs/decisions.md:39` (O-1 brand decision pending)
- **What:** `product = "Proot Distro"` is explicitly a placeholder awaiting brand decision (O-1). ruff config lacks `required-version`; ruff 0.17.1 is installed and `target-version = "py314"` is accepted (`ruff check --target-version py314` passes). UNVERIFIED whether ruff supports a `required-version` key in `[tool.ruff]` — not confirmed in installed ruff.
- **Evidence:** `pyproject.toml:22-24` comment "Product name is the placeholder (O-1: brand decision pending)". `ruff 0.17.1`; `ruff check --target-version py314 src/core/constants.py` → "All checks passed!".
- **Fix / opportunity:** Resolve O-1 and set `product` to the final brand; verify/add `required-version = "0.17.1"` only if ruff supports it (otherwise leave absent).
- **Risk if ignored:** Launchers/dialogs ship with placeholder product name; ruff version drift unguarded if `required-version` were supported.

### F6 · P0 (identity guard) · version identity is consistent — verified-good
- **Where:** `pyproject.toml:5` (`version = "1.0.0"`), `pyproject.toml:26` (`build_number = 1`); `src/core/constants.py:11-12` (`APP_VERSION = "1.0.0"`, `APP_BUILD_NUMBER = 1`); `.github/workflows/app.yml:59-106` (Release identity consistency job)
- **What:** pyproject `version`/`build_number` match `core.constants.APP_VERSION`/`APP_BUILD_NUMBER` exactly. CI job "Release identity consistency" (app.yml:59-106) cross-checks `BUILD_VERSION`/`BUILD_NUMBER` env, pyproject, `core.constants`, and optional `version.json`. No drift detected.
- **Evidence:** `pyproject.toml:5,26`; `src/core/constants.py:11-12`; `app.yml:63-83`. `uv.lock:587-618` metadata mirrors the same floors/specifiers.
- **Fix / opportunity:** None — keep the guard.
- **Risk if ignored:** N/A (verified good).

## Missed capabilities (dependency audits only)
N/A — this is a file audit of `pyproject.toml`, not a dependency capability study. (See `docs/dependency-studies/flet-cli.md` for flet-cli levers such as `--source-packages`, `extract_packages`, `dev_packages`, `flutter.build_args`, `cleanup.*_files`.)

## Verified-good list
- `[tool.flet] org`, `product`, `company`, `build_number` — all read by flet-cli 1.0.4 (`tool.flet.org` BB:1596-1597; `tool.flet.product`; `tool.flet.company`; `tool.flet.build_number` build.py:198).
- `[tool.flet.app.path] = "src"` — read (`tool.flet.app.path` BB:1002-1005).
- `[tool.flet.boot_screen]` + `[tool.flet.boot_screen.flet] startup_message` — read (`tool.flet.boot_screen` BB:1761-1795).
- `[tool.flet.splash] color`/`dark_color` — read (`tool.flet.splash.*` BB:1695-1760).
- `[tool.flet.android] bundle_id`, `split_per_abi = true`, `legacy_packaging = true`, `target_arch = ["arm64-v8a","x86_64"]` — all valid; `target_arch` validated against `ANDROID_ARCH_TO_FLUTTER_TARGET_PLATFORM` (`.venv/.../flet_cli/utils/android.py:3-9`; x86_64 → `android-x64` supported).
- `[tool.flet.android.dependencies] = ["flet-proot==5.1.107.98"]` — read via `tool.flet.<platform>.dependencies` (BB:2571-2574).
- `[tool.flet.android.permission]` INTERNET + ACCESS_NETWORK_STATE — read (BB:1222); matches app.yml allow-list (app.yml:248-264).
- `[tool.flet.android.meta_data] com.google.android.gms.ads.APPLICATION_ID` = Google test id `ca-app-pub-3940256099942544~3347511713` — read (BB:1291); matches D-017 ruling (test id mandatory for flet-ads or app dies at launch).
- All dependency floors in pyproject equal uv.lock pinned versions (flet/flet-ads 1.0.4; flet-terminal 0.4.0; httpx 0.28.1; proot-distro 5.10.0; dev flet-cli/flet-desktop 1.0.4; pytest 9.1.1; pytest-timeout 2.4.0; ruff 0.17.1) — D-003/D-004 honored.
- pytest `filterwarnings = ["error::Warning:^(services|screens)(\.|$)"]` is a VALID 4-field spec (`action:message:category:module:line`, `_pytest/config/__init__.py:2146-2164`) and empirically verified: a `services` package UserWarning is raised as an error under it (test run EXIT 0 with error). The 4th field IS the module regex as intended.
- ruff `target-version = "py314"` accepted; `ruff check` passes on sample source.
- `project.name = "proot-distro-flet"` differs from wrapped `proot-distro` dep (avoids uv self-dependency; D-009).

## Unverified
- `tool.flet.icon` consumption path — no flet-cli read found (F1, UNVERIFIED as config key).
- pytest-timeout `timeout_method` default (signal vs thread) — not asserted from source (F3).
- ruff `required-version` key support in `[tool.ruff]` 1.0.4 — not confirmed (F5).
- Whether `oauthlib-4.0.0.dist-info/` residual metadata actually gets staged into the APK (cleanup applies to `serious_python package` staging; end-to-end APK contents not inspected here) (F2).
- `target_sdk_version`/`min_sdk_version` keys are NOT read by flet-cli 1.0.4 ("Do not use: zero reads in 1.0.4", flet-cli study §3.2) — pyproject correctly omits them; app.yml enforces targetSdkVersion ≥ 36 post-build (app.yml:233-240).

## Bottom line for the orchestrator
pyproject.toml is internally consistent and aligns with installed flet-cli 1.0.4 and uv.lock, but carries real defects: dead `tool.flet.icon` key (F1), a cleanup glob that misses `oauthlib-4.0.0.dist-info/` (F2), a missing pytest `timeout_method` (F3), and ruff per-file-ignores plus app.yml steps for two scripts that do not exist on disk (F4). Version identity is locked and correct (F6). Verdict: MIXED. Highest-impact item: F4 (missing `check_elf_alignment.py`/`generate_third_party_sources.py` referenced by CI) can break the APK/AAB release jobs.
