# src/core/constants.py — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `src/core/constants.py` (23 lines) · consumers `src/components/app_header.py`, `src/components/update_dialog.py`, `src/screens/views.py`, `src/app_controller.py`, `src/services/update_service.py` · `tests/test_version_sync.py` · `pyproject.toml` · `version.json` · `.github/workflows/app.yml` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/constants.py` is the single identity/distribution module: app name/version/build (`APP_NAME`, `APP_VERSION`, `APP_BUILD_NUMBER`), repo coordinates and derived URLs (`REPO_OWNER`, `REPO_NAME`, `GITHUB_RELEASES_URL`, `UPDATE_CONFIG_URL`), store/legal URLs (`PLAY_STORE_URL`, `PRIVACY_POLICY_URL`, `TERMS_OF_SERVICE_URL`), and a SharedPreferences key (`STORAGE_ONBOARDING_DONE`). Consumers: `app_header.py:14,74` shows `v{APP_VERSION}`; `update_dialog.py:16,89,127,161` uses name/version/github URL; `views.py:15,527` launches the privacy URL; `app_controller.py:14,298,307` reads/writes the onboarding flag; `update_service.py:14-18,61,66,70,91,97` compares versions/builds and fetches the feed. Version drift is guarded by `tests/test_version_sync.py:23-46` against `pyproject.toml` (`version=1.0.0`, `build_number=1`), `version.json` (`build_number=1`, `version=1.0.0`), the changelog, and workflow defaults.

---

## Findings

### F1 · P2 · `playstore_url` has no fallback to the shipped `PLAY_STORE_URL` constant
- **Where:** `src/services/update_service.py:97-98` (`"playstore_url": _safe_url(data.get("playstore_url"))` with no default) · `src/core/constants.py:18` (`PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=ng.kiri.prootdistro"`) · `src/components/update_dialog.py:119-135` (`play_url = data.get("playstore_url")` and the Play button is only appended `if is_android and play_url`)
- **What:** `github_url` falls back to `GITHUB_RELEASES_URL` (update_service.py:97, `..._safe_url(data.get("github_url"), GITHUB_RELEASES_URL)`), but `playstore_url` does not fall back to `PLAY_STORE_URL`. The constant exists and is even allow-listed (`_ALLOWED_HOSTS` includes `play.google.com`), yet it is never imported by `update_service.py` (grep `PLAY_STORE_URL` across `src/` returned only `constants.py:18`). If the feed omits `playstore_url`, the Android "Google Play" button silently disappears even though a valid store URL is shipped.
- **Evidence:** `grep -rn "PLAY_STORE_URL" src/ tests/` → only `src/core/constants.py:18`; `src/services/update_service.py:14-18` import list omits it.
- **Fix / opportunity:** import `PLAY_STORE_URL` in `update_service.py` and change line 98 to `_safe_url(data.get("playstore_url"), PLAY_STORE_URL)`, mirroring the `github_url` line. Then the Android button always has a target.
- **Risk if ignored:** on-device users on a feed that omits the field lose the Play Store update path and only see "Release page".

### F2 · P3 · `TERMS_OF_SERVICE_URL` points at the privacy document and is unused
- **Where:** `src/core/constants.py:20` (`TERMS_OF_SERVICE_URL = "https://github.com/Nwokike/proot-distro/blob/main/PRIVACY.md"`) · repo tree has only `PRIVACY.md` (no `TERMS.md`/`TERMS*`: `git ls-files | grep -i "privacy\|terms"` → `PRIVACY.md`)
- **What:** The constant is named "terms of service" but its path is `PRIVACY.md`, and `grep -rn "TERMS_OF_SERVICE_URL" src/ tests/` returns no matches (only the definition). It is dead today, but if wired into a settings/about screen it would open the wrong legal document.
- **Evidence:** grep above returned only `src/core/constants.py:20`; `git ls-files` has no terms file.
- **Fix / opportunity:** either delete the constant until a terms document exists, or add a real `TERMS.md` and point the constant at `/blob/main/TERMS.md`. Do not ship a mislabeled legal link.
- **Risk if ignored:** future wiring opens a privacy policy under a "Terms of Service" label (compliance/UX defect).

### F3 · P3 · `PRIVACY_POLICY_URL` and `TERMS_OF_SERVICE_URL` are hardcoded instead of derived from `REPO_OWNER`/`REPO_NAME`
- **Where:** `src/core/constants.py:14-15` (`REPO_OWNER`, `REPO_NAME`) · `src/core/constants.py:16-17` (f-strings for releases/config) · `src/core/constants.py:19-20` (full literal URLs)
- **What:** `GITHUB_RELEASES_URL` and `UPDATE_CONFIG_URL` are built from `REPO_OWNER`/`REPO_NAME`, but the privacy/terms URLs are full literals. Renaming the owner/repo would silently leave stale links; this is the same drift class the f-strings were introduced to prevent.
- **Evidence:** lines 16-17 vs 19-20.
- **Fix / opportunity:** make them `f"https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/main/PRIVACY.md"` (and terms when it exists), keeping the existing `is_allowed_launch_url` host check (`services/update_service.py:12-24`) valid.
- **Risk if ignored:** owner/repo rename ships broken legal links with no test failure.

### F4 · P3 · `APP_NAME` and the bundle/package id are hardcoded in multiple places with no sync guard
- **Where:** `src/core/constants.py:10` (`APP_NAME = "Proot Distro"`) · `pyproject.toml:4` (`name = "proot-distro-flet"`), `:24` (`product = "Proot Distro"`), `:44` (`bundle_id = "ng.kiri.prootdistro"`) · `src/core/storage_paths.py:8` (`PACKAGE_NAME = "ng.kiri.prootdistro"`) · `src/core/constants.py:18` (bundle id embedded in `PLAY_STORE_URL`)
- **What:** `APP_VERSION`/`APP_BUILD_NUMBER` are guarded by `tests/test_version_sync.py:23-26`, but `APP_NAME`, the product name, and the bundle/package id have no equivalent guard and are duplicated across `constants.py`, `pyproject.toml`, and `storage_paths.py`. The owner's no-hardcoded-data rule (D-015 §5) is honored for the licenses screen via `importlib.metadata` (`src/screens/views.py:5,565-572`), but identity strings here are still literals.
- **Evidence:** `grep -n "ng.kiri.prootdistro\|Proot Distro" src/core/storage_paths.py pyproject.toml src/core/constants.py`.
- **Fix / opportunity:** (a) centralize the bundle id in `constants.py` (e.g. `BUNDLE_ID`) and import it in `storage_paths.py`/`PLAY_STORE_URL`; (b) add a test asserting `APP_NAME == tomllib` product and bundle id consistency, extending `tests/test_version_sync.py`. Keep the constants module as the runtime source of truth (pyproject does not ship in the APK, per the module docstring).
- **Risk if ignored:** a rename touches 3+ files silently; drift surfaces only on device (wrong storage path / store link).

### F5 · P3 · `STORAGE_ONBOARDING_DONE` key is a bare literal with no versioning/ownership prefix beyond "proot_"
- **Where:** `src/core/constants.py:22` (`STORAGE_ONBOARDING_DONE = "proot_onboarding_done"`) · `src/app_controller.py:298,307` (read/write via `self.prefs`)
- **What:** The key is already centralized (good), but it carries no build/version or app namespace beyond `proot_`. Other screens may add their own keys without a shared prefix convention; a stale "done" flag from an older schema would be trusted. This is a robustness/policy observation rather than a current bug.
- **Evidence:** `grep -rn 'prefs.get\|prefs.set' src/` shows only this key today.
- **Fix / opportunity:** document a `proot_<feature>_<name>` naming convention in the module docstring and (optionally) version the key if the onboarding flow changes. No code change required now.
- **Risk if ignored:** future migrations silently reuse a stale flag.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-file audit, not a dependency audit. No new packages proposed (D-003). Note: `importlib.metadata` (already used in `src/screens/views.py:5` for license versions) is not applicable to `APP_VERSION` because the app itself is not an installed distribution in the APK (`.venv` has `proot-distro 5.10.0`, the upstream package, not `proot-distro-flet`); the module docstring correctly keeps the constant as runtime truth. UNVERIFIED whether a future Flet build exposes the app's own version via page metadata.

---

## Verified-good list

1. `APP_VERSION == "1.0.0"` matches `pyproject.toml:5` and `version.json:3` and `CHANGELOG` key (`src/core/changelog.py:6`); `APP_BUILD_NUMBER == 1` matches `pyproject.toml:26` and `version.json:2`; `tests/test_version_sync.py:23-26` passes (run: 4 passed).
2. `version.json` feed respects the guard: `build_number=1 <= APP_BUILD_NUMBER=1` and `release_notes` length > 80 (`tests/test_version_sync.py:34-41`).
3. Workflow defaults match: `.github/workflows/app.yml:20` `default: "1.0.0"` and `:24` `default: "1"` (`tests/test_version_sync.py:43-46`).
4. All URLs are `https://` and their hosts (`github.com`, `raw.githubusercontent.com`, `play.google.com`) are covered by `is_allowed_launch_url` (`src/services/update_service.py:12-24`); no scheme/host mismatch.
5. `REPO_OWNER`/`REPO_NAME` are used to build both release and config URLs (`constants.py:16-17`), so those two cannot drift independently.
6. `STORAGE_ONBOARDING_DONE` is the single source for the onboarding flag; both read and write in `app_controller.py:298,307` use it (no stray literal).
7. No imperative widget mutation or `page.update()` in `constants.py` (D-015 respected); the module is pure data.

---

## Unverified

1. Whether a `TERMS.md` (or terms URL) is intended to exist in the upstream repo — only `PRIVACY.md` is tracked locally; remote state UNVERIFIED.
2. Whether `APP_NAME` should be sourced from Flet app metadata at runtime instead of a literal — no such API verified in installed flet 1.0.4; labeled UNVERIFIED.
3. Whether centralizing env-var names (`FLET_APP_STORAGE_DATA`, `TERMUX_APP__PACKAGE_NAME`, etc.) into `constants.py` is desired — they currently live in `src/core/storage_paths.py:13` and `src/core/proot_probe.py:28,104-107`; no decision found in docs. UNVERIFIED.
4. Whether a feed without `playstore_url` actually occurs in practice — feed shape is UNVERIFIED (version.json in repo includes it).