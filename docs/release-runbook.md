# Release Runbook — Proot Distro v1.0.0 → Play Store & GitHub Releases

How a release happens, in order. The git tag is YOUR action; everything before
and during the CI build is automated or documented below.

---

## 1. Version Bump Discipline (Enforced by CI Identity Check)

Every location must agree before tagging:

1. `pyproject.toml`:
   - `[project] version = "X.Y.Z"`
   - `[tool.flet] build_number = N`
2. `src/core/constants.py`:
   - `APP_VERSION = "X.Y.Z"`
   - `APP_BUILD_NUMBER = N`
3. `src/core/changelog.py`:
   - Add a key `"X.Y.Z": "..."` to `CHANGELOG` with user-facing bullet points (tested by `test_changelog_has_an_entry_for_the_current_version`).
4. `version.json` (local feed, gitignored):
   - `version` and `build_number` must match `pyproject.toml` or be held back.
   - **Never commit a `version.json` whose `build_number` exceeds the shipped build.**
5. Run `uv lock` to synchronize `uv.lock`.

---

## 2. In-App Update Policy (`version.json`)

- `mandatory: false` (default): Shows "What's New" with an optional "Later" button.
- `mandatory: true`: Hides the "Later" button and makes the dialog modal.
  Use **only** for critical fixes (broken-update recovery, security, or data corruption).

---

## 3. Pre-Tag Local Verification

Before pushing a release tag, verify all local gates:

```bash
uv run ruff check src tests scripts/build_flet_proot_wheel.py scripts/check_elf_alignment.py scripts/generate_third_party_sources.py
uv run ruff format --check src tests scripts/build_flet_proot_wheel.py scripts/check_elf_alignment.py scripts/generate_third_party_sources.py
uv run pytest -q -m "not live"
uv run python scripts/generate_third_party_sources.py
```

All commands must exit 0.

---

## 4. CI Workflow (`.github/workflows/app.yml`)

Triggered on push to `main` or via manual `workflow_dispatch`.

1. **`quality` job:**
   - Ruff linting and format checking.
   - Flet AST API guard (`tests/check_flet_api.py`) verifying all `ft.*` chains against installed Flet.
   - Release identity consistency check: verifies `pyproject.toml`, `core.constants`, `BUILD_VERSION`, `BUILD_NUMBER`, and `version.json` alignment.
   - Full test suite (`pytest -m "not live"`).

2. **`apk` job:**
   - Native wheel assembly (`flet-proot`) with sha256 checksums and 16 KiB PT_LOAD alignment verification.
   - Keystore decoding from repository secrets (`KEYSTORE_BASE64`).
   - `flet build apk --split-per-abi` with environment-based signing.
   - 16 KiB ELF alignment check on all output APKs (`scripts/check_elf_alignment.py`).
   - GitHub Releases pre-release asset publication (`app-<run#>`).

3. **`aab` job:**
   - Builds Google Play Android App Bundle (`flet build aab`).
   - Merged manifest inspection:
     - `targetSdkVersion >= 36` (mandatory Play requirement).
     - Permissions audit: strictly `INTERNET` and `ACCESS_NETWORK_STATE` only.
     - Verification of no `REQUEST_INSTALL_PACKAGES` or install intents.
   - Cleanliness check: verifies no test/development files exist in the bundle.
   - 16 KiB ELF alignment check on the `.aab` file.
   - Generates and bundles `THIRD-PARTY-SOURCES.md`.
   - Publishes AAB artifact to the release.

---

## 5. Post-Build Release Ritual

1. **Test on Device:** Sideload `proot-distro-flet-arm64-v8a.apk` onto physical hardware. Verify:
   - App launches cleanly without crashing.
   - Consent dialog and AdMob test banner render properly.
   - Distro installation succeeds (e.g. `debian:bookworm`).
   - Interactive shell connects with working PTY, input, and resize.
2. **Finalize GitHub Release:**
   - Navigate to the GitHub Releases page for `app-<run#>`.
   - Replace the automated pre-release placeholder description with finalized user release notes.
   - Switch release status from pre-release to latest (if applicable).
3. **Publish In-App Update Feed:**
   - Commit the updated `version.json` to the `main` branch to notify installed clients.
4. **Google Play Console:**
   - Upload the inspected `.aab` bundle to the target release track (Internal Testing / Closed Testing / Production).
