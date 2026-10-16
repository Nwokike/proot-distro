# Roadmap — proot-distro

**Date:** 2026-10-16 (post-corpus synthesis; supersedes the pre-study milestone list) · **Status:** milestone breakdown, pre-plan-mode (M1 planning next)
**Naming:** repo = `Nwokike/proot-distro` (renamed 2026-10-16, D-009). Local dir + uv project name stay `proot-distro-flet` (uv self-dependency rule). Product brand TBD (O-1).
**Corpus this plan rests on:** `docs/dependency-studies/` (47 per-package exhaustive API files + INDEX — every claim source-verified against the 1.0.4 lockstep tree, anti-hallucination cited), `docs/compliance/` (licensing / distro-images / play-policy), `docs/reference/` (16 integration studies), `docs/decisions.md` (D-001…D-010), `docs/m0-checklist.md` (device evidence + apt investigation arc), `docs/testing-findings.md`, and the progressive harvest log `docs/roadmap-synthesis.md`. **Every milestone below cites the doc that carries the detail; nothing here is invented.**

---

## 0. What this is

A Flet Android app that wraps upstream **`proot-distro` 5.10.0** (pure-Python, zero runtime deps — verified) to run **Debian, Ubuntu, Alpine and any Docker/OCI image** on-device — no root, **no Termux layer**. Interactive shells render in **`flet-terminal`** (owner's control). Monetization via **`flet-ads`** (official AdMob extension).

**Owner constraints (non-negotiable):** dependencies = `flet`, `flet-ads`, `proot-distro`, `flet-terminal` (dev-only: `flet-cli`, `flet-desktop`, `pytest`, `pytest-timeout`, `ruff`); **no patching of upstream** (steer via env/config/CLI only — the corpus confirmed this suffices); no build complications (update path = bump a version); **no local `flet build`**; plan mode per milestone (this doc is the milestone index).

## 1. Locked architecture (validated on hardware in M0 except where marked)

```
Flet app (src/)
 ├─ services/proot_service.py ... sole importer of proot_distro.*  (Data Formulator facade: lazy
 │                               import gate, to_thread/CapacityLimiter, plain-data returns;
 │                               CI AST guard enforces the sole-importer rule)
 ├─ services/session_manager.py  one anyio task group per terminal tab; ProotSession = PTY spawn
 │                               (pty.openpty + Popen + setsid/TIOCSCTTY + TIOCSWINSZ — PROVEN on-device)
 ├─ core/proot_probe.py ........ probe-gating (proot binary, arch, rootfs writability) — FFmpeg pattern
 ├─ core/codec.py .............. msgpack records (never pin ≥1.2.0 — Android wheel rule)
 ├─ flet-terminal .............. session UI (MobileTerminal — must be constructed inside @ft.component
 │                               trees; proven working there per owner's example + CollabShell)
 ├─ flet-ads ................... UMP consent + interstitial at natural breaks (mobile-gated; banner
 │                               never on terminal screens — AdMob placement policy)
 └─ proot-distro (PyPI) ........ install/list/remove/build in-process; session argv = WE build it,
                                 one-to-one with the Termux capture (spike-10; --change-id=0:0,
                                 <rootfs>/tmp:/dev/shm, stdio binds, --link2symlink, -L, --sysvipc,
                                 --kill-on-exit, --kernel-release, PROOT_L2S_DIR)

Native: flet-proot wheel (forum request → flet-dev/flet#discussions/6979)
 ├─ opt/lib/libproot.so + libproot-loader.so + libtalloc.so + libandroid-shmem.so → jniLibs (copyOpt)
 ├─ [tool.flet.android].legacy_packaging = true  → extracts to nativeLibraryDir (exec allowed by SELinux;
 │                                                  PROVEN: proot 5.1.107.96 runs from nativeLibraryDir)
 └─ env at runtime: ANDROID_NATIVE_LIBRARY_DIR-based PD_PROOT_BIN + PROOT_LOADER
```

Distro catalog: certified map (Phase 1: `ubuntu:24.04`, `debian:bookworm`, `alpine:3.21`) + arbitrary OCI refs / local tarballs via upstream. Every certified distro must be fully usable ("every provider a complete app"). Catalog entries carry tag (display) + digest (wire) + per-distro registry field (`docs/compliance/distro-images.md` §4).

## 1b. Testing & dev loop (verified mechanics — `docs/testing-findings.md`)

- `flet run` uses the PREBUILT desktop client; third-party extension Dart (flet-terminal, flet-ads) **never renders under `flet run`** (D-005). Fast local loop = `uv run pytest` (pure logic + fake-transport ProotSession tests) + `uv run flet run` for non-extension UI with platform-availability placeholders.
- Device truth = CI release artifacts (D-006: `build-<sha>` / milestone prereleases; artifacts upload is blocked account-wide — releases only).
- **Run-it-first rule**: `tools/check_flet_api.py` (AST guard vs the INSTALLED flet) + local `flet run` smoke BEFORE any APK handoff. CI runs the guard too.
- The M0 device record is `docs/m0-checklist.md` (runs #1–#6 + CI alignment evidence). Extension + proot behavior can only be validated there.

## 1c. Structured mode (CollabShell notebook I/O template)

Second highly-testable UX mode: input = command string (+ optional stdin modal via `threading.Event`), output = normalized `{"type": stream|execute_result|display_data|error, …}` dicts, append-only outputs with budgets and incremental rendering (`outputs_rev` cache). Our `ProotSession` bridge is shaped like `ColabTerminalClient` (`send_input` / `set_size` / `on_stdout` / `alive` / `close`) so panel wiring, scrollback-replay, and offline tests port directly — transport = local proot spawn instead of remote WS.

---

## 2. Milestones

### M0 — Phase-0 device spike (GO/NO-GO) → *architecture proven; device-retest loop DEFERRED (D-011)*
Goal: prove the load-bearing mechanics on a real phone before any UI work. CI-built APK only.
**Status 2026-10-16:** **G1 ✓✓** (exec from nativeLibraryDir), **G2 ✓** (in-process OCI install), **G3 ✓** (guest exec through loader), **G5 ✓** (interactive PTY shell on-device — O-3 closed: Python-side PTY), **G6 ✓** (export). **G4 = one open bug, upgrade-over-existing only**: fresh `apt install` paths work; dpkg chown ENOENT through link2symlink when upgrading existing packages (arc: `docs/m0-checklist.md` §"Device retests #4+", spikes 8/9/10). spike-10 (CI green) shipped the Termux device-truth argv + `--no-upgrade` workaround + G4b isolation probe; **owner retest: still failing, and the retest loop is closed by owner ruling (D-011) until after M1–M6**. Interim product behavior: `--no-upgrade` + guest copy note. **M0 is NON-BLOCKING for M1–M6** (the go/no-go claims are green; this is a package-manager edge bug, not an architecture risk).
**Resume recipe (post-milestones, D-011):** install `spike-10` (or later) → Run ALL → capture G4 + G4b log text; owner Termux control #2 (`apt-get install --only-upgrade perl-base`) completes the matrix (same failure in Termux ⇒ upstream-wide, document; works ⇒ flag/env delta).
**Still owed beyond the current device (gate 5):** one run on a second/older device (seccomp/OEM variance) — same spike APK; schedule when a second device is available (noted in `play-policy.md` §2.3).

### M1 — `flet-terminal` refactor (0.3.x → 0.4.0)
Goal: the "perfect for this project" terminal package, house-extension standard. Full blueprint: `docs/reference/dep-flet-terminal.md` (the trio comparison + "do NOT copy" list included).
- **Must-fix bugs (verified):** (1) `MobileTerminal()` raises `RuntimeError: No current renderer is set` when constructed OUTSIDE a `@ft.component` tree — owner requirement: give it a context-independent construction path (or at minimum a clear documented error + contract test; it works fine inside component trees — our M3 AppShell + owner's example + CollabShell all construct it there); (2) `ctrl_active`/`alt_active` setters call nonexistent `ExtraKeysBar.refresh_buttons` → latent `AttributeError`, fix.
- **Owner parity requirement:** full mobile terminal (extra keys bar CTRL/ALT/arrows/ESC/TAB, search, themes, zoom) exactly as used in CollabShell, easily portable via the example.
- **Metadata/packaging:** `flet>=1.0.1` → bare `"flet"` **after** tests + matrix exist (O-2; the drift risk is the unversioned `_c` wire name, not pip metadata — contract tests are the net); `requires-python ">=3.14"` → `">=3.10"`; add `license = "MIT"` + `license-files` (compliance A6 — the wheel currently ships NO license metadata); URLs → Homepage/Repository/Issues; package-data glob `"**/*"` → `["pubspec.yaml", "lib/**"]`.
- **Quality:** `tests/` contract suite (yandex-ads pattern: exports, defaults, wire values, typed-event resolution), `compat.yml` matrix (flet 0.85/1.0/latest — scoped to what the 1.0-era APIs support), `sync_versions.py` (Python↔Dart drift), `.fvmrc`, quality gate in build-all.yml, README to house standard. Example cleanup (bare `flet`, drop `[tool.flet.dev_packages]`, keep `[tool.uv.sources]`).
- **Not copied from flet-notifications:** `patcher.py` / `[project.scripts]` (no native registration needed). Spawn capability NOT added (O-3 resolved: package stays view-only).
- Consumers: CollabShell pins 0.3.9 (`MobileTerminal` + `BUILTIN_THEMES`) — ship compatible surface, coordinate the bump.
- Plan-mode decisions: O-2 (bare `"flet"` vs modest floor — recommendation: bare, after tests), font_family Android fallback (JetBrains Mono is not bundled — verify or ship the font).
Exit: published to PyPI; our app resolves it; CollabShell build green (or explicitly deferred with owner sign-off).

### M2 — Native wheel: `flet-proot`
Goal: `proot` binary reachable as a build-time dependency, zero app-side build hacks.
- Track the forum request ([discussions/6979](https://github.com/flet-dev/flet/discussions/6979)); if accepted → Forge recipe → we consume. Mirror FFmpeg's two-artifact shape (`docs/reference/app-ffmpeg.md`): Python side stays PyPI; only the native payload needs the Forge index — **Android native wheels resolve at `flet build` time; flet-cli/serious_python inject the index**.
- Fallback (already proven end-to-end in the spike): our CI builds the `py3-none-any` payload wheel; additive `[tool.flet.android]` mechanism per `docs/dependency-studies/flet-cli.md` (`.so→jniLibs` machinery is serious_python Gradle-side; `legacy_packaging` + names must be `lib*.so`).
- SDK/ABI: NDK r28+ 16 KB alignment (Play hard requirement — `play-policy.md` §2.2; current CI already *inspects* alignment, M2 makes the wheel *build* aligned); `target_arch` = exactly what the index ships (do not copy sibling ABI notes — FFmpeg lesson); x86_64 for emulator QA = O-6.
- Version-tracking policy: termux/proot v5.1.107.96 + termux-packages build flags (`PROOT_WITH_LIBANDROID_SHMEM=true`, `PROOT_UNBUNDLE_LOADER`) pinned in the recipe; bump = one commit.
Exit: CI APK contains `lib/arm64-v8a/libproot.so` + friends from the wheel (not hand-staged); M0 G1 re-verified from the wheel.

### M3 — App scaffold + distro manager
Goal: house-standard skeleton + container lifecycle UI. Architecture sources: `app-sherlock.md` (layout, controller bridge, keep-alive, render flusher), `app-data-formulator.md` (sole-importer facade), `app-ddgs.md` (guard tests), `app-collabshell.md` (test shapes), plus the per-dependency utilization sections of all 47 studies.
- **Scaffold:** `src/{main.py, app_shell.py, core/, state/, services/, components/, screens/, hooks/}`, `@ft.observable AppState`, `ControllerMethodsCtx` bridge, controller owns services, thin screens; `tests/{conftest.py(FakePage), flet_tree.py}` + `test_imports_vs_deps.py` (DDGS) + `test_version_sync.py` + sole-importer AST guard (Data Formulator idea).
- **`services/proot_service.py`:** sole importer; env set BEFORE first import (`TERMUX__*`, XDG, `PD_PROOT_BIN`, `PROOT_L2S_DIR`); install path decision in plan mode (in-process `_run_install` + `redirect_stderr` stage capture vs CLI-subprocess — both wrapped for `SystemExit`+`RuntimeError`; progress = stage-level + indeterminate, bars are auto-suppressed on non-TTY, never patch `draw_bytes_bar`); friendly error translation (`friendly_job_error`); all blocking work off the main thread (upstream urllib, 120 s timeout, 5×5 s retries).
- **anyio pipeline (P1–P4, `docs/dependency-studies/anyio.md`):** memory-object-stream progress pipeline; cancelable installs (`CancelScope` + shielded cleanup of partial rootfs + lock release; `move_on_after` default); `CapacityLimiter` caps (download/install); structured session manager lands M4.
- **Install flow UX (compliance-mandated):** explicit size disclosure + consent before every OCI pull (Play Deceptive Behavior §3.2 — `licensing.md` A9 / `play-policy.md` A-1); pull-limit error copy + optional Docker Hub token settings field (`PD_DOCKER_AUTH`, `distro-images.md` §2.4/§5); per-container delete/reset; connection gating via flet `Connectivity`; wake-lock during downloads (refcount discipline — services are pruned at `sys.getrefcount <= 3` per event; keep-alive = `page.services.append(...)`).
- **Certified catalog:** YAML manifests (pyyaml; `safe_load` + stable dumps) with tag+digest+registry (`distro-images.md` §4); names via `slugify`; timestamps via arrow/dateutil/tzdata; optional Jinja2 profile templates with `StrictUndefined`.
- **Probe-gating:** `core/proot_probe.py` (binary/loader presence, arch, rootfs writability) — screens refuse before start.
- **Bundled offline rootfs (D-2):** plan-mode decision — default runtime-pull; if bundled, byte-unmodified upstream image only (+ re-pack question flagged UNVERIFIED in `distro-images.md` §7).
- **Licenses infrastructure:** `LICENSES/` notices file + the licenses-screen *content contract* (§3.3 wording of `licensing.md`; screen UI wires in M4/M6) — GPL source-offer mechanics are mandatory in every option world.
- **GPL derivative question (A8) — M3 plan-mode agenda:** proceed as Option A (repo stays public, sources shippable) until counsel decides A vs B; the in-process `proot_distro` import is the strongest combination signal (`licensing.md` §2).
- **Tests:** fake-transport `ProotSession`, fake rootfs trees (`tmp_path`), hermetic env-import tests (`monkeypatch.setenv` + fresh import), CollabShell-shaped wiring tests; CI gains the **Android compile proof** (`uv pip compile --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/`).
Exit: install/uninstall/list of all three certified distros from UI; offline first-boot if bundled-rootfs chosen; all guard tests green.

### M4 — Terminal integration
Goal: full interactive sessions in `flet-terminal`.
- Sessions via our proven PTY spawn (spike-10 argv baseline); NEVER call upstream `login` in-process (`os.execvpe`). `MobileTerminal` inside the AppShell component tree (owner's example + CollabShell pattern: handlers wired before the tree; `show_extra_keys`, themes, search).
- Session screen: reserved layout rows; stdin-hook dialog (CollabShell `stdin_hook.py` pattern) for first-login prompts; keep-alive + render flusher (~2 Hz + coalescing — Flet has zero batching); resize wiring (`on_resize` → TIOCSWINSZ); scrollback replay on mount.
- **Dual-mode (O-4):** interactive console + structured command→outputs using the §1c mapping — plan-mode decision with the CollabShell mapping as the template.
- **Ads:** interstitial at natural breaks only (install complete / removal / return-to-list; single live instance); **no banner on terminal screens** (AdMob placement policy — `play-policy.md` §4.2); consent flow already wired (M3).
- **Workaround UI note:** guests keep the upgrade-over-existing caveat until G4b resolves; surface "update packages inside the container may fail — reinstalls are safe" style copy only if the bug proves durable.
- **Foreground service (O-5/A-11):** default NO (`flet-notifications` patcher complication); revisit only from on-device background-kill evidence.
- **Optional Track-Bs (plan-mode, each with an APK-size measurement):** pygments syntax-highlighted guest-file preview; markdown-it-py offline README viewer (`docs/dependency-studies/pygments.md` §9, `markdown-it-py.md` §8). Termux-mode env masquerade (O-8) also decided here (whether to unlock upstream's own Termux flag path vs our manual argv).
Exit: `apt install` inside a session from UI; keyboard/toolbar usable on phone; no ANRs.

### M5 — Packaging, CI, release ritual
Goal: house-standard multi-target CI (`app-ffmpeg.md` skeleton, fixes for its drifts).
- `build-all.yml`: quality job → placeholder prerelease → parallel apk-split / AAB / Windows / Linux. Quality contents: `uv sync --frozen`; ruff check+format (Sherlock select + ffmpeg's `PTH`+`ASYNC`, `line-length=100`, `target-version="py313"`, `required-version="==0.17.1"`); `pytest -m "not live"` (timeout=60/thread, strict config/markers); version-identity script (pyproject/constants/version.json/workflow — **version.json tracked** or CI tolerates absence — FFmpeg drift #2); imports-vs-deps; flet-API AST guard; Android compile proof; **AdMob production-ID guard** (FFmpeg precedent); **AAB inspection step for real** (FFmpeg drift #5): targetSdk ≥ 36 (`play-policy.md` §2.1 — mandatory for new submissions post-2026-08-31), minSdk + ABI set recorded, permissions exactly INTERNET + ACCESS_NETWORK_STATE, no REQUEST_INSTALL_PACKAGES, 16 KB ELF alignment gate (`check_apk_alignment.py` — currently inspection, make it blocking).
- `[tool.flet]` config: org `ng.kiri`, product/brand (O-1), build_number, boot_screen, splash, icon assets (flet-platform-assets pipeline), android bundle_id/permissions/AdMob meta_data/signing block, gradle jvmargs cap; `[tool.flet.cleanup]`: `oauthlib/**` (verified-safe prune, ~1 MB) + audit the rest against the real tree (never copy sibling globs blind).
- flet family: lockstepped (flet-ads pins `flet==1.0.4`); app pyproject uses floors + exact in `uv.lock` (O-2 recommendation); NEVER pin msgpack ≥1.2.0 (Android wheel rule — `dep-flet-runtime-utils.md`).
- CI toolchain: `--yes`; `--no-rich-output`; pin `FLET_CACHE_DIR` + `PYTHON_BUILD_RELEASE_DATE`; signing only via `FLET_ANDROID_SIGNING_*` secrets (D-008 keystore; alias `upload`); template trust boundary — template_ref = flet version, never untrusted `--template` (`dep-cookiecutter-stack.md`); no pubspec overrides unless a CI build proves one (then comment the exact error).
- **Fix house drifts in OUR app:** real release-notes finalize step (FFmpeg drift #4); `THIRD-PARTY-SOURCES.md` per release (compliance A3); release-only delivery (D-006 — house pattern).
Exit: tagged pre-release produces all artifacts green; AAB inspection outputs recorded in play-policy.md.

### M6 — Policy, licensing, distribution
- In-app LICENSES screen shipped (content contract from M3; wording `licensing.md` §3.3): GPL-2.0/3.0 texts + per-component entries + written-offer + source links (≥3 years per release). Trademark attribution block (`distro-images.md` §1.3): SPI/Debian, Canonical/Ubuntu, no logos, no "Official".
- Play: data-safety form from the AdMob SDK Index entry (A-8); privacy policy at stable URL + in-app link (A-9); export-compliance declaration (A-10); content rating truthfully (unrestricted network terminal); ads declared; App-content questionnaires (A-9).
- Listing copy rules (`distro-images.md` §5): brand-only title, factual distro references, size/consent messaging, non-affiliation disclaimers. Precedent re-check (UserLAnd/Termux/Andronix live) before submission (A-16).
- Release ritual per house memory: 3-agent verification swarm → retag → watch ALL CI → real release notes. F-Droid/GitHub fallback track decision (A-10).
Exit: store-ready.

## 3. Dependency map (47 studies + integrations)

Full per-package API references live in `docs/dependency-studies/` (INDEX.md is the entry point; each file is exhaustive, source-verified against the installed tree, anti-hallucination cited). Headline operational rules distilled there:

- **msgpack**: the Python↔Dart wire protocol; Android wheels exist only ≤1.1.x → never pin ≥1.2.0 anywhere.
- **oauthlib**: prune via `cleanup.package_files = ["oauthlib/**"]` (breaks only `Page.login()` — no login flow exists).
- **repath + six**: keep both (8+34 KB; M3 Router navigation depends on them).
- **httpx cluster + certifi + idna + typing-extensions**: dormant (no OAuth); certifi = pinned Mozilla bundle, not the Android store; typing-extensions' `dataclass_transform` is the only every-launch member (resolves to stdlib on 3.14).
- **flet family**: lockstep; auto-reinstall-on-mismatch danger (`flet/utils/pip.py`); extensions = `@ft.control` + bundled Dart, no registration (which is also why they never render under `flet run`).
- **flet-cli/cookiecutter tree/desktop/assets/pillow**: build-host only, none ship; template trust boundary; `--no-rich-output` for CI logs.
- **dev stack** (pytest 9.1.1 / pytest-timeout 2.4.0 / ruff 0.17.1 / packaging / pluggy / iniconfig / colorama / watchdog / qrcode / click / rich / pyyaml / slugify / arrow-chain / jinja2 / chardet / binaryornot): dev-only; config recipes captured per file.
- **proot-distro 5.10.0**: sole integration contract in `docs/reference/dep-proot-distro.md` (safe vs fragile surfaces, env-before-import, no callbacks, failure modes).

## 4. Parking lot (decide in the owning milestone's plan mode)

- Brand/product name (O-1 — repo + `[tool.flet].product`); must not be "proot-distro"/Termux/Ubuntu/Debian (`licensing.md` §4.5/A7).
- App flet pin style (O-2): floors + exact lock (recommended) vs exact pair.
- Dual-mode UX (O-4) — CollabShell mapping as template.
- FGS/flet-notifications (O-5/A-11): default NO.
- x86_64 ABI (O-6): what the wheel ships; CollabShell precedent (x86_64 dropped over 16 KB alignment).
- zstd OCI layers (O-7): verify `compression.zstd` in the Flet-bundled 3.14 during M3 image work (fallback: gzip images) — **still unverified**.
- Termux-masquerade env (O-8): our manual argv already carries the Termux flags; decide in M4 whether to also set `TERMUX_VERSION`/prefix env for upstream's own paths.
- Local desktop `flet build` (O-9, owner): the only way to see extension panes locally; standing rule remains NO.
- Bundled offline rootfs + size budget (~30 MB) vs runtime-pull default (D-2/A9).
- Optional Track-Bs (M4): pygments guest-file preview; markdown-it-py README viewer — each needs an APK-size measurement.
- Optional authenticated Docker Hub pulls (settings field) — never a baked-in shared token.

## 5. Open items (verify on device / upstream)

1. Discussion 6979 outcome → M2 path decision (forge wheel vs own CI wheel).
2. **M0 G4 retest (spike-10) + G4b probe result** — last M0 item (see `m0-checklist.md`).
3. Owner Termux control #2 (upgrade path in Termux Debian) — completes the apt matrix.
4. Play review behavior for OCI pulls (UserLAnd precedent live; mitigation prepared — `play-policy.md` §1.2).
5. GPL derivative-work decision + counsel engagement (M3 plan-mode agenda — `licensing.md` A8).
6. zstd probe in the bundled Python (O-7) — fold into M3 image work.
7. `jni` pubspec override: NEVER copy blind; add only if a CI build fails with the exact documented error (verify FFmpeg's "until 1.0.4" note is stale first).

## 6. Doc-integrity notes (2026-10-16, this synthesis pass)

- `docs/compliance/distro-images.md` had a **write-tool truncation baked into the committed file** (literal `...[truncated 6154 chars]` at line 369; the tail after §3.2 item 2 was never generated — unrecoverable from any transcript). §3.2(2)–§7 were **reconstructed and re-grounded** in the surviving sources + `dep-proot-distro.md`; a repair note marks the seam in the file.
- `docs/m0-checklist.md` was missing the apt-bug investigation (device retests #4–#6, spikes 8/9/10, Termux ground truth) — now recorded.
- All other 46 dependency docs + 15 reference docs + both remaining compliance docs verified complete (no truncation markers).
