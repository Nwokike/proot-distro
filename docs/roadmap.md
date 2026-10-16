# Roadmap — proot-distro

**Date:** 2026-10-16 · **Status:** milestone breakdown, pre-plan-mode (M1 planning next)
**Naming:** repo = `Nwokike/proot-distro` (renamed from `proot-distro-flet`, 2026-10-16). Local dir + uv project name stay `proot-distro-flet` because the uv project cannot be named the same as its `proot-distro` dependency. Product brand TBD.

---

## 0. What this is

A Flet Android app that wraps upstream **`proot-distro` 5.10.0** (pure-Python, zero runtime deps — verified on PyPI) to run **Debian, Ubuntu, Alpine and any Docker/OCI image** on-device — no root, **no Termux layer**. Interactive shells render in **`flet-terminal`** (owner's control). Monetization via **`flet-ads`** (official AdMob extension). Background research: workspace `proot-distro-flet-feasibility.md` (canonical) + `proot-distro-flet-research.md` (verification).

**Owner constraints (non-negotiable):**
- Dependencies = `flet`, `flet-ads`, the wrapped package (`proot-distro`), plus `flet-terminal`. Dev-only: `flet-cli`, `flet-desktop`, `pytest`, `pytest-timeout`, `ruff`.
- **No patching of upstream.** Steer via public config surface only (env vars, constructor args, `--get-proot-cmd`). Any monkeypatch = red flag in review.
- No build complications. Update path = **bump a version** (upstream ships → we bump floor → lockfile moves → tests + CI prove it).
- No local `flet build`; all builds through GitHub Actions.
- Plan mode per milestone; this doc is the milestone index, not a plan.

## 1. Locked architecture (from research + house studies)

```
Flet app (src/)
 ├─ services/proot_service.py ... sole importer of proot_distro.* (lazy import gate, asyncio.to_thread,
 │                               plain-data returns — the Data Formulator facade pattern)
 ├─ services/terminal_bridge.py . spawns proot login via flet-terminal (no pty needed on Python side)
 ├─ core/proot_probe.py ........ probe-gating (proot present, arch, image availability) — FFmpeg Lite pattern
 ├─ flet-terminal .............. session UI
 ├─ flet-ads ................... consent + interstitial (mobile-gated; banner only where space is reserved)
 └─ proot-distro (PyPI) ........ install/list/remove/build in-process; login argv via --get-proot-cmd

Native: flet-proot wheel (requested → flet-dev/flet#discussions/6979)
 ├─ opt/lib/libproot.so + libproot-loader.so + libtalloc.so + libandroid-shmem.so → jniLibs (copyOpt)
 ├─ [tool.flet.android].legacy_packaging = true  → extracts to nativeLibraryDir (exec allowed by SELinux)
 └─ env at runtime: ANDROID_NATIVE_LIBRARY_DIR-based PD_PROOT_BIN + PROOT_LOADER
```

Distro catalog: certified map (Phase 1: `ubuntu:24.04`, `debian:bookworm`, `alpine:3.21`) + arbitrary OCI refs / local tarballs via upstream. Every certified distro must be fully usable ("every provider a complete app").

## 1b. Testing & dev loop (verified 2026-10-16)

- `flet run` (desktop) uses the PREBUILT flet-desktop client; `flet run --android/--web/--ios` serve a dev URL + QR to the official Flet preview app. Neither contains third-party extension Dart — **flet-terminal / flet-ads never render under `flet run`** (owner's notifications README confirms: "desktop preview — prebuilt client").
- Fast local loop = `uv run pytest` (pure logic incl. fake-transport ProotSession tests, CollabShell template) + `uv run flet run` for all non-extension UI. Wrap extension panes in platform-availability placeholders — ads already MUST be gated (they raise on desktop).
- Device truth = CI artifacts: every push builds `build-<sha>` prereleases (house workflow) → install on the phone. This is the established ritual under the no-local-builds rule.
- M0 spike APK is the first dedicated device harness; M1 uses flet-terminal's own example workflows + CollabShell as regression consumer.
- CollabShell precedent check: its Android terminal is a REMOTE Colab PTY over WS (`POST /api/terminals` + `wss://…/terminals/websocket/{name}`) — it proves the flet-terminal VIEW works on Android with real typing, NOT that local process spawn works (CollabShell spawns nothing locally; zero subprocess/proot code in `src/`).
- Optional lever (owner decision, not a default): a local desktop `flet build windows/linux` compiles extension Dart and would show the terminal locally — currently against the standing no-local-builds rule.

## 1c. Structured mode (CollabShell notebook I/O template)

CollabShell's cell pipeline gives us a second, highly testable UX mode: input = code string (+ stdin modal dialog via `threading.Event` returning the typed answer), output = normalized `{"type": stream|execute_result|display_data|error, …}` dicts (`_to_cell_output`), append-only output list with text/image budgets and incremental rendering (`outputs_rev` cache). Tests are pure offline fixtures (fake kernel messages, MagicMock MobileTerminal, source guards). Our `ProotSession` bridge should be shaped like `ColabTerminalClient` (`send_input` / `set_size` / `on_stdout` / `alive` / `close`) so the panel wiring, scrollback-replay, and offline tests port directly — replacing only the transport (local proot spawn instead of remote WS).

## 2. Milestones

### M0 — Phase-0 device spike (GO/NO-GO) → *enters plan mode first*
Goal: prove the load-bearing mechanics on a real phone before any UI work. CI-built minimal APK only.
Gates (each pass/fail on-device):
1. `nativeLibraryDir/libproot.so --version` executes from the app (Python `subprocess`; fallback: Dart-side spawn).
2. Install alpine (bundled tarball and/or Docker Hub OCI) into app-private dir; run `uname -a` through proot with `PROOT_LOADER` set.
3. `apt update && apt install cowsay` inside a Debian/Ubuntu guest (proves loader mmap-exec of guest binaries).
4. Spawn path decided: flet-terminal 0.3.9 spawns nothing (verified — view-only control). First try Python-side `subprocess`/`create_subprocess_exec` running the `--get-proot-cmd` argv; if Python subprocess is unreliable under serious_python on Android (a known upstream hang report), test Dart-side `Process` spawn (would become a flet-terminal package feature, keeping app code pure Python). Session visible in flet-terminal either way. Test BOTH shapes: a one-shot exec (`proot … sh -c 'cmd'`, the structured mode's dependency) and a long-lived interactive session (stdin pump + resize, the console mode's dependency).
5. Repeat 1–4 on a second/older device (seccomp/OEM variance).
Exit: if green → M1–M5 proceed; if exec blocked → fallback plan (linker64 trick) goes to M1 planning.
Implementation: `m0-spike/` (pyproject, `src/main.py` gates G0–G6, `tools/build_proot_wheel.py`, `tools/check_apk_alignment.py`) built by `.github/workflows/m0-spike.yml` (CI-only); device results recorded in [m0-checklist.md](m0-checklist.md).

### M1 — `flet-terminal` refactor (0.3.x → 0.4.0)
Goal: the "perfect for this project" terminal package, matching the new one-to-one extension style. Full blueprint from the trio study; headline: **add contract tests + compat matrix FIRST, then drop the pin** (otherwise a visible floor is traded for invisible drift risk).
- Dependency deltas: `flet>=1.0.1` → bare `"flet"` (matches yandex-ads/notifications verbatim); `requires-python ">=3.14"` → `">=3.10"` (matches new packages; revisit vs the 1.0-only `@ft.component` APIs in a compat decision); add `license = "MIT"` + `license-files = ["LICENSE"]` (currently NO license metadata in the wheel); URL order → Homepage/Repository/Issues.
- Packaging deltas: narrow Flutter package-data glob `"**/*"` → `["pubspec.yaml", "lib/**"]` (stops shipping Dart README/CHANGELOG/tests in the wheel); regenerate both `uv.lock` files; example pyproject `flet>=0.86.3` → bare `flet`, drop `[tool.flet.dev_packages]`, keep `[tool.uv.sources]`.
- Add: `tests/` contract suite (wire-value + event-resolution tests in the yandex-ads style), `compat.yml` matrix (`flet 0.85.0 / 1.0.0 / latest` — proves the bare-dep claim; scope the matrix to versions the 1.0-era APIs actually support), quality gate in build-all.yml, `sync_versions.py` (Python↔Dart version drift), `.fvmrc`, README rewritten to the house extension standard.
- Spawn capability decision rides on M0 gate 4. If Dart-side is chosen, add it as a first-class package API (spawn/write/resize/exit) so consuming apps stay pure Python; if Python-side works, package stays view-only and our app owns a `ProotSession`.
  - **RESOLVED 2026-10-16 (device): Python-side PTY, owner's example pattern.** M1 keeps the package view-only and hardens it for that role.
- **Owner requirements added 2026-10-16 (from the M0 device runs):** (1) `MobileTerminal` must construct OUTSIDE component trees (renderer-context bug hit on-device) — it is the owner's package and the fix belongs there, not in workarounds; (2) full mobile-terminal parity — everything exposed (extra keys bar, search, themes, zoom) exactly as used in ColabShell, easily portable into other apps via the example; (3) one-to-one house-extension standard like flet-notifications/flet-yandex-ads (tests, compat matrix, metadata, packaging, README).
- Deliberately NOT copied from flet-notifications: the `patcher.py` build patcher (not needed — terminal is pure Dart rendering, no manifest/gradle requirements) and its `[project.scripts]`.
- Darwin-free note: no flet version floor means any consumer resolves — the contract tests + matrix are the safety net instead.
- **R1 study note (decision input for M1 planning):** flet-terminal's hook-in has NO registration/manifest — drift risk is the `_c` name string + property/event wire shape (unversioned internal contracts; worst case silent protocol mismatch). Options: (a) bare `"flet"` exactly like yandex-ads/notifications + contract tests + compat matrix (owner's stated goal); (b) keep a modest floor (`flet>=1.0.4`). Decide in M1 plan mode.
- Consumers must not break: CollabShell pins 0.3.9 and uses `MobileTerminal` + `BUILTIN_THEMES` — ship a compatible surface or coordinate the bump.
Exit: published to PyPI; our app resolves it; CollabShell build green (or explicitly deferred with owner sign-off).

### M2 — Native wheel: `flet-proot`
Goal: `proot` binary reachable as a build-time dependency, zero app-side build hacks.
- Track the forum request ([discussions/6979](https://github.com/flet-dev/flet/discussions/6979)); if accepted → recipe lands on pypi.flet.dev → we consume (`uv add` + `extract_packages` if needed per FFmpeg study's `__file__`-loader rule).
- Index fact (verified): pypi.flet.dev hosts only wheels that need Android-native builds — pure-Python packages resolve from PyPI. Our mix: `flet-terminal`/`proot-distro`/`flet-ads` come from PyPI; only the native `flet-proot` payload needs the Forge index.
- Fallback: our own CI publishes `py3-none-any` android payload wheel (data-only, chmod+exec at runtime is NOT enough — needs jniLibs path; verify mechanism in M2 planning).
- SDK/ABI decisions: NDK r28+ 16 KB alignment; `target_arch` = exactly the ABIs the wheel ships (do not copy sibling ABI notes — FFmpeg study lesson); x86_64 for emulator QA.
- Version-tracking policy: termux/proot version + termux-packages build flags (`PROOT_WITH_LIBANDROID_SHMEM=true`, `PROOT_UNBUNDLE_LOADER`) pinned in our build recipe; bump = one commit.
Exit: CI APK contains `lib/arm64-v8a/libproot.so` + friends; M0 gate 1 re-verified from the wheel (not a hand-copied file).

### M3 — App scaffold + distro manager
Goal: house-standard app skeleton and the container lifecycle UI.
- Scaffold per Sherlock/DDGS/CollabShell: `src/{main.py, app_shell.py, core/, state/, services/, components/, screens/, hooks/}`, `@ft.observable AppState`, `ControllerMethodsCtx` bridge, controller owns services, thin screens; `tests/{conftest.py(FakePage), flet_tree.py}` + `test_imports_vs_deps.py` + `test_version_sync.py` ported.
- `services/proot_service.py`: sole importer; lazy-load gate; `asyncio.to_thread` for install/download/extract; friendly error translation (`friendly_job_error` pattern).
- **proot-distro integration contract (verified on the installed wheel):**
  - Env must be set BEFORE first import (module constants are computed at import time): `TERMUX__PREFIX`, `TERMUX__HOME`, `TERMUX_APP__PACKAGE_NAME`, `XDG_DATA_HOME`/`XDG_CACHE_HOME`, `PD_PROOT_BIN`.
  - Update-safe surfaces to build on: `parse_reference`, `derive_alias`, `iter_cached_images`, `paths.installed_container_names/container_is_installed/container_rootfs`, `progress.fmt_size`, `arch.*`, the env contract, and the on-disk layout (`containers/<name>/{rootfs,manifest.json,shm}`, `oci_layers/`, `oci_manifests/`). Fragile internal surfaces to isolate behind ONE wrapper: `command_*` handlers (argparse namespaces + `sys.exit`), `build_proot_args` (13 kwargs), `_run_install`/`_login_with_rootfs`, `ContainerLock`, the `dirfd` descriptor convention (`pull_image` takes `rootfs_fd`, not a path).
  - Install path: decide in M3 plan mode between in-process `_run_install` (raises `RuntimeError`; wrap `SystemExit` too) vs spawning the public CLI (`pd install …`) — documented CLI contract may beat internal APIs for update-safety; both need the off-main-thread rule (sync urllib, 120 s timeout, 5×5 s retries).
  - Progress: there are NO callbacks and byte bars are auto-suppressed when stderr is not a TTY. Capture stage lines with `contextlib.redirect_stderr` around the in-process call (standard capture — NOT a patch of the library) or parse subprocess stderr; UI shows stage-level + indeterminate progress. Do not monkeypatch `draw_bytes_bar`.
  - Login argv: `--get-proot-cmd` stdout deliberately differs from the real exec (path pinning) — use it as the recipe source or re-implement the preamble + `build_proot_args`; never call `login` in-process (`os.execvpe`).
- `core/proot_probe.py`: binary/loader presence, arch support, rootfs writability — screens refuse before start (probe-gating).
- Screens: distro list (certified + custom ref), install flow (progress, cancel, size reporting), container actions (open/stop/reset/remove), settings (storage, ads).
- Storage: app-private dirs via `FLET_APP_STORAGE_*` conventions; env plumbing `PD_PROOT_BIN`/`PROOT_LOADER`/`TERMUX__*` dance settled here (parking lot item from research §8).
Exit: install/uninstall/list of all three certified distros from UI; offline first-boot with one bundled rootfs.

### M4 — Terminal integration
Goal: full interactive sessions in `flet-terminal`.
- Login argv via upstream `--get-proot-cmd` (never call `login` in-process — `os.execvpe` replaces the app process).
- Session screen: reserved layout for ads; stdin-hook dialog pattern (CollabShell `stdin_hook.py`) for first-login prompts; keep-alive services (refcount rule); render flusher if progress streaming needs it.
- Dual-mode decision (M4 planning): interactive console + structured "command → outputs" mode using the CollabShell notebook I/O mapping (§1c) as template; both modes share the same local-spawn dependency from M0.
- Sessions survive screen switches; foreground-service notification decision (adds `flet-notifications` + its patcher complication — default NO, revisit only if Play review demands it).
Exit: `apt install` inside a session from UI; keyboard/toolbar usable on phone; no ANRs.

### M5 — Packaging, CI, release ritual
Goal: house-standard multi-target CI.
- `build-all.yml` per Sherlock/FFmpeg: quality job (version consistency across pyproject/constants/version.json/workflow, ruff, `pytest -m "not live"`, import-vs-deps guard, Android compile proof `uv pip compile --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/`) → placeholder release → parallel jobs: `flet build apk --split-per-abi`, AAB, Windows (Inno), Linux (fpm deb/rpm). Keystore only via `FLET_ANDROID_SIGNING_*` secrets.
- Fix house drifts IN OUR APP (flagged by studies): version.json must be tracked or CI must tolerate absence (FFmpeg contradiction); add the real release-notes-finalize step (FFmpeg/sherlock leave placeholder bodies); AAB minSdk/libproot floor inspection step for real.
- `[tool.flet]` config: org `ng.kiri`, product, build_number, boot_screen message, splash, android bundle_id/permissions (INTERNET + ACCESS_NETWORK_STATE only)/AdMob meta_data, gradle jvmargs cap, `[tool.flet.cleanup]` audit.
- Cleanup globs (initial candidate): `oauthlib/**` (no login flow — breaks only `Page.login()`); audit the rest against the actual tree (do NOT copy sibling globs blindly).
- CI toolchain specifics (from D1 study): `--yes` for non-interactive builds; pin `FLET_CACHE_DIR` + `PYTHON_BUILD_RELEASE_DATE`; signing passwords only via env (`FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD` / `_KEY_PASSWORD`), `key_store`/`key_alias` may live in pyproject; pytest `timeout_method = "thread"` for Windows/Linux parity.
- Build-template trust boundary (D3 study): template zip cache has no checksum and template hooks execute — template ref follows the flet version pin; never use an untrusted `--template`/`--template-dir`.
- No pubspec overrides unless a CI build proves one necessary (then: comment with the exact error, per FFmpeg discipline).
Exit: tagged pre-release produces all artifacts green.

### M6 — Policy, licensing, distribution
- GPL obligations (proot GPL-2.0, libtalloc GPL-3.0, proot-distro GPL-3.0-only): in-app licenses screen + source links.
- Play policy positioning (downloaded rootfs = user data; exec chain never downloaded; bundle default rootfs; F-Droid/GitHub fallback build if needed).
- Ubuntu/Debian trademark care (attribute, don't brand as them).
- Release ritual per house memory: 3-agent verification swarm → retag → watch ALL CI → real release notes.
Exit: store-ready.

## 3. Dependency map (48 locked packages → 11 study agents)

| Agent | Packages | Headline findings |
|---|---|---|
| R1 flet | flet | ✓ Pure-Python (no native code in the package; rendering lives in flet-desktop/web or the Flutter client baked at build time). Extensions hook in with just `import flet` + `@ft.control("Name")` subclass — **no registration, no manifest, no entry points**. Only 4 hard runtime deps (oauthlib, httpx, repath, msgpack). **Danger: flet silently `pip`-reinstalls flet-cli/web/desktop on ANY version skew at startup** (`flet/utils/pip.py`) → keep the flet family perfectly lock-stepped. Android = embedded dart_bridge transport (`FLET_PLATFORM=android`, `FLET_DART_BRIDGE_PORT`); `StoragePaths` etc. are client-implemented stubs — storage behavior is validated on the built APK, not in Python |
| R2 httpx cluster | httpx, httpcore, h11, anyio, idna, certifi, typing-extensions | ✓ All pure-Python, ship unmodified; httpx/httpcore/h11/anyio/idna/certifi dormant unless OAuth is used (flet imports httpx only in `auth/`); typing-extensions load-bearing on every launch; certifi pins a build-time CA bundle (240 KB) instead of the Android trust store; none on pypi.flet.dev (none needed) |
| R3 flet utils | msgpack, oauthlib, repath, six | ✓ msgpack = the Python↔Dart wire protocol (load-bearing every session); pypi.flet.dev ships Android arm64 wheels only for msgpack **1.1.x** (incl. cp314) — never pin 1.2.3 for Android, keep it floating so the mobile resolver settles on 1.1.2; oauthlib = dead without `Page.login()` → prune; repath/six pure-Python, needed only if routing |
| R4 flet-ads | flet-ads | ✓ `flet==1.0.4` exact pin (bump as pair with flet); mobile-only controls raise on desktop → platform-gate ads; no rewarded/native ads in 1.0.4; UMP consent flow required; AdMob APPLICATION_ID must come from `[tool.flet.android.meta_data]` (the package supplies none) |
| R5 flet-terminal (wheel) | flet-terminal | ✓ View-only control — NO spawn/pty API (write/`send_bytes`/`set_on_bytes`/`on_resize` only; channel label "pty" is transport naming). `Requires-Python >=3.14`, no license metadata in wheel. App owns a `ProotSession` for the child process; recommend Python-side bridge first |
| R6 proot-distro (wheel) | proot-distro | ✓ Zero deps; GPL-3.0-only; env contract before import; pure helpers = safe surfaces; `command_*`/`sys.exit` + `build_proot_args` = fragile behind one wrapper; no progress callbacks (stderr capture); wheel is 93 files incl. full build engine + completions |
| D1 flet-cli | flet-cli, qrcode, colorama | ✓ Flags VERIFIED in 1.0.4: `--android-legacy-packaging` (+ `tool.flet.android.legacy_packaging`) exists; `--android-extract-packages` (+ `extract_packages`) exists; arch flag is `--arch` (no `--target-arch`); **`target_sdk_version`/`min_sdk_version` do NOT exist as keys** — SDK levels come from the build template; `.so→jniLibs` machinery is NOT in flet-cli (lives in serious_python Gradle fetched at build time). CI: `--yes`, `FLET_CACHE_DIR` + `PYTHON_BUILD_RELEASE_DATE` pins, signing via `FLET_ANDROID_SIGNING_*` env (passwords env/CLI only). qrcode/colorama = `flet run` device-connect extras, zero build relevance |
| D2 desktop/assets | flet-desktop, flet-platform-assets, pillow | ✓ All build/dev-host only, none ship into the APK. `flet build apk` needs NO flet-desktop; icons/mipmaps are rendered on the host by flet-platform-assets + Pillow from `assets/icon.png`; `adaptive_icon_background` is a template colour resource (no pixels) |
| D3 cookiecutter tree | cookiecutter + 18 deps | ✓ Build-host only (none ships to APK); pure-Python throughout (chardet LGPL — do not vendor). Mechanics that matter: top-level unknown `template_data` keys are silently ignored (typo vanishes without error — every key must exist in the template's cookiecutter.json); `extra_context` must stay JSON-serializable; StrictUndefined fails closed; `[tool.flet.flutter.pubspec.*]` overrides are applied post-render to pubspec.yaml via YAML (not cookiecutter). Trust boundary: the flet-build-template.zip is cached WITHOUT checksum and its hooks execute at build time — keep the template ref = flet version, never point `--template` at untrusted URLs. Bump in groups (jinja2+markupsafe, requests+urllib3+charset-normalizer, markdown-it-py+mdurl, arrow+dateutil+tzdata) |
| D4 test stack | pytest, pytest-timeout, pluggy, iniconfig, packaging | ✓ All pure-Python; every house pytest key (`pythonpath`, `strict_config/markers`, `filterwarnings`, `timeout`) valid at 9.1.1/2.4.0. Config notes: add `[tool.pytest.ini_options]` — NOT `[tool.pytest]` (both together = UsageError); pin `timeout_method = "thread"` for Windows/Linux CI parity |
| D5 lint/build tools | ruff, watchdog | ✓ ruff = single Rust binary, dev-only (MIT, no Python deps; unknown config keys hard-error — house keys all valid at 0.17.1); watchdog = `flet run` hot-reload only, inert in CI/`flet build`; neither ships to Android |

Repo studies completed: Sherlock ✓ (production standard: service-per-lib, controller bridge, KeepAlive services, CI matrix, richest ruff), DDGS ✓ (floor pins + honest-import comments + `test_imports_vs_deps.py`, version discipline gates), CollabShell ✓ (already embeds flet-terminal `MobileTerminal` + stdin-hook dialog; patches galore = what we must NOT need), FFmpeg ✓ (two-artifact Forge shape `av`+`flet-libffmpeg`, probe-gating, `extract_packages` rule, `jni` override likely stale at 1.0.4), Data Formulator ✓ (sole-importer facade + constructor injection, zero monkeypatches, Android compile proof step).

## 4. Parking lot (decide in the owning milestone's plan mode)

- Brand/product name (+ dir/pyproject rename).
- flet pin style: `==1.0.4` exact (FFmpeg style) vs `>=` floor (Sherlock/DDGS style) for the flet family — flet-ads forces the exact pair anyway; flet also AUTO-REINSTALLS flet-cli/web/desktop at startup on any version mismatch (R1), so the family must stay lock-stepped in `uv.lock` regardless; decide policy in M1.
- Whether ads: consent + interstitial only; banner placement reserved row (terminal screens have no spare space).
- Terminal spawn port: Dart-side `Process` vs pty — decided by M1 trio study + M0 gate 4 result.
- x86_64 ABI inclusion (emulator QA) vs wheel coverage from M2.
- zstd OCI layers: verify `compression.zstd` in Flet's bundled Python 3.14 build (fallback: gzip-layered images).
- msgpack: RESOLVED — never pin above 1.1.x for Android (Forge index tops at 1.1.2; 1.2.3 is desktop-only). Keep it floating in the lock.
- `flet-notifications` inclusion: default NO (patcher complication); revisit only if required.
- First-run offline rootfs choice + size budget (~30 MB compressed) vs `split_per_abi` already in place.

## 5. Open items (verify on device / upstream)

1. Discussion 6979 outcome → M2 path decision (forge wheel vs own CI wheel).
2. exec mechanism end-to-end inside Flet APK (M0) — the single go/no-go.
3. Play review behavior for OCI pulls (UserLAnd precedent live; mitigation prepared).
4. flet-cli flag names RESOLVED by D1 study (dep table): legacy-packaging / extract-packages / `--arch` confirmed; `target_sdk_version`/`min_sdk_version` do not exist as keys.
5. `jni` override: NEVER copy blind; add only if a CI build fails with the exact documented error.
