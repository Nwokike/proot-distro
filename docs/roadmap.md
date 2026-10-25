# Roadmap to 100% + publication — proot-distro (Flet)

**Date:** 2026-10-24 · **Supersedes:** the 2026-10-19 roadmap (M1–M4 done: flet-terminal 0.4.0, flet-proot wheel, app scaffold, terminal integration — see `docs/decisions.md` D-012/D-013/D-015/D-016/D-017).
**Inputs:** the complete document corpus re-read 2026-10-24 (47 dependency studies, 16 reference studies, 3 compliance docs, decisions D-001–D-017, testing-findings, release-runbook, roadmap-synthesis, all 96 swarm audit reports in `docs/swarm/` — 47 dependency-utilization, 43 file audits, 4 design-parity, dependency tree, brief), plus the owner's rulings: design must match CollabShell; no MVP scoping — everything to completion; dependencies utilized to the fullest.

**How to read this:** R1–R9 are execution milestones in order. Each cites its evidence (`file:line` or report). Nothing is descoped; items the owner must decide are marked **[O]** and carried in the milestone that needs them. The swarm reports are the finding-level detail; this file is the work index.

---

## R1 — Restore & Unbreak (P0/P1 correctness)

Everything in this milestone is a verified broken thing. No new features.

**1.1 Restore the deleted tree (blocks tests, CI, and the wheel builder today):**
- `LICENSES/` + `src/LICENSES/` (7 texts each) — `tests/test_ui_reactive.py:182,206` fail; the licenses screen renders "(text missing)"; GPL §3.3 unmet. Evidence: `views.py:627-628`, git status `D`.
- `scripts/check_elf_alignment.py`, `scripts/generate_third_party_sources.py` — still invoked by `app.yml:52-53,175,291,294` and the runbook; restore or re-point. Evidence: `docs/swarm/file-audits/pyproject.toml.md` F4, `app.yml.md` F1.
- `docs/compliance/*`, `docs/roadmap.md` (this file replaces it), `docs/testing-findings.md`, `docs/release-runbook.md`, `THIRD-PARTY-SOURCES.md` — restore from HEAD; this new roadmap supersedes the old one.

**1.2 P0 functional breaks (verified by multiple agents):**
- **AppShell lost its observable subscription** — commit `4ad4593` removed `st, _ = ft.use_state(state)`; `AppShell` reads `state.onboarding_done`/`state.active_session` with no subscription → first-run dead-ends at onboarding; "Open shell" dead. Evidence: `docs/swarm/file-audits/src__app_shell.py.md` F1 (P0), `dependency-utilization/flet.md` F1.
- **Every shell open fails twice over:** (a) `get_proot_cmd` runs `cli.main()` on a worker thread but upstream installs a SIGQUIT handler at `cli.py:258` → `ValueError: signal only works in main thread`; (b) it swaps `sys.stdout` for `io.StringIO` but upstream prints via `sys.stdout.buffer` (`login/__init__.py:624`) → `AttributeError`. Only `SystemExit` is caught. Evidence: `file-audits/src__services__proot_service.py.md` F1, `tests__test_sessions.py.md` F1, `tests__test_proot_surfaces.py.md` F1. Fix: run `--get-proot-cmd` on the main-thread dispatcher or capture with a real `TextIOWrapper` over a pipe; add a non-mocked golden test.
- **Live PTY output never reaches the screen:** `SessionManager._on_bytes` only appends to the scrollback deque; the only `mt.send_bytes` is the mount replay. The terminal renders nothing after mount. Evidence: `file-audits/src__services__session_manager.py.md` F1 (P0), `src__screens__terminal_view.py.md` F1, `dependency-utilization/flet-terminal.md` F1, `anyio.md` F1.
- **"Check for Updates" button is dead:** `update_dialog.py:102` sync lambda returns the coroutine; Flet discards it (`base_control.py:548-552`). Evidence: `file-audits/src__components__update_dialog.py.md` F1 (P0).
- **Update-feed URL allow-list bypass:** `urlsplit("https://evil.com\\@github.com/")` → host `github.com` (allowed) while Chrome resolves `evil.com`. Evidence: `dependency-utilization/idna.md`/`mdurl.md` F1 (P1 security), `update_service.py:26-37`. Fix: `urlsplit(url.replace("\\", "/"))` + tests.

**1.3 P1 compliance/monetization breaks:**
- Banner ads are not consent-gated (banner builder never reads `_can_request_ads`; first banner renders before UMP finishes) and a failed UMP flow defaults to *allow*. Evidence: `dependency-utilization/flet-ads.md` F1/F2. Gate everything on `can_request_ads()`; surface UMP failure in `state.data_note` (D-017.9).
- `backup_container` uses `FilePicker.save_file` without `src_bytes` → `ValueError` on Android (mobile requires bytes). Evidence: `file-audits/src__app_controller.py.md` F2, `dependency-utilization/proot-distro.md` F1-P1.
- CI release-identity `vt()` comparator blocks releases on cosmetic version reformats (`1.0` vs `1.0.0`) and raises on pre-releases. Evidence: `dependency-utilization/packaging.md` F2 (P1), `app.yml:85-105`. Replace with `packaging.version.Version` (already installed).
- `hints_dismissed` never persisted → card returns every launch (`file-audits/src__components__ui.py.md` F1).
- `changelog.notes_for` returns the oldest entry, docstring says newest (`file-audits/src__core__changelog.py.md` F1).
- Licenses screen: full texts, no `[:6000]` truncation, `errors="replace"` decode (`file-audits/src__screens__views.py.md` F1-P0, `charset-normalizer.md` F1, `jinja2.md` F1).
- Theme never follows a runtime system-brightness change (no `on_platform_brightness_change`) — `dependency-utilization/flet.md` F5.

**1.4 P2 correctness batch (same milestone, after the P1s):** `posixdb` grp shim semantics (`file-audits/src__core__posixdb.py.md` F1-F3), `_f2fs_probe` OSError escape (`proot_probe.py.md` F1), env-contract split latch (`storage_paths.py.md` F2), observable mutations marshaled to the UI loop (`core__state.py.md` F1, `anyio.md` F2-F4), `_LineTee` not capturing install output (`proot_service.py.md` F4), `show()` without `on_load` + single interstitial slot (`flet-ads.md` F3/F4), settings `playstore_url` fallback (`constants.py.md` F1), interstitial timer consumed on failed show (`ad_service.py.md` F3), `show_snack` noop arity (`controller_ctx.py.md` F1), `S110` silent except in `views.py:595`, PEP-758 `except` parens normalization decision (valid on 3.14 — keep, but document; `pygments.md`/`urllib3.md` notes).

**Exit criteria:** `uv run pytest` fully green including the two license tests; an unmocked `session_argv` integration test proves shells open; device run from a CI APK: onboarding completes, install `debian:bookworm`, open shell, see output, type, exit.

---

## R2 — CollabShell design parity (the owner's explicit standard)

Primary target: **CollabShell** (`docs/swarm/design-parity/01-header-home.md`, `02-terminal.md`, `03-design-system.md`, `04-ddgs-and-collabshell-personal.md`). DDGS contributes the polish layer only (type floor, 8-pt grid, Outfit, centered search-first composition, SafeArea/nav styling, snack backstop, motion) — never the header logo (owner explicitly rejects DDGS's logo-in-header).

- **Shell chrome:** fixed header bar at shell level (title = active tab from `_TABS`; back button when a session is open), `ft.SafeArea` root, `NavigationBar` hidden while a session is open or fullscreen (parity 02-F1/F2), `indicator_color` + `ALWAYS_SHOW` labels, header padding tokens `(SPACE_LG, SPACE_SM, SPACE_MD, SPACE_SM)`, no horizontal scroll on the header row, help slot.
- **Home order restored:** header outside the scroll; centered brand hero as the first body item (80 px icon per `tokens.ICON_XXXL`, tagline `FONT_SM`, token spacers); body order hero → hints → Install → Containers → ad → `NAV_BAR_CLEARANCE` spacer (all tokenized; no literals).
- **Tokens:** raise the type floor to 11 pt minimum (`FONT_XXS/XS→11, SM→12, MD→14, LG→16, XL→20, XXL→24, HERO→32`); 8-pt spacing grid (`4/8/12/16/24/32`); tokenized paddings everywhere (`file-audits/src__core__tokens.py.md` F1, design-parity 03).
- **Theme/surfaces:** distinct elevation — dark glass `#26263A`-class vs surface; light bg/glass separation; theme-aware `ok()/warn()/accent()` resolvers (contrast ≥3:1 both modes — `file-audits/src__core__styles.py.md` F1, design-system F1/F2/F5); SnackBar always explicit `bgcolor` + `behavior=FLOATING` + dismissal backstop (one `show_snack` helper, 18 call sites — design-system F14).
- **Typography:** ship `Outfit` (4 weights) under `src/assets/fonts/`, set `font_family` on both `ft.Theme`s and all text (design-system F7).
- **Composition:** centered search-first install row (SearchBar-style field, pill `FilledButton` primary action, ≥44 px targets), status chips, centered sections; empty/loading states with tinted circular backdrop + ProgressRing; 150 ms animations on chips/expandables; onboarding polish (circular icon backdrop 120 px, animated dots, swipe `expand=True` fix — `file-audits/src__screens__onboarding_view.py.md` F2).
- **Terminal chrome parity** (from 02): flat full-width session header (`ARROW_BACK_ROUNDED`/`ICON_MD`/`FONT_LG`/`status_dot`+ProgressRing), quick commands send `\n` (or escape codes), `show_search=False` + toggle action, glass session-selector cards with full-card tap (`ink=True`, `RADIUS_MD`), remove dead `bottom_inset` code.
- **Brand tint:** `color_blend_mode=SRC_IN` with the dark-mode white tint (`file-audits/src__components__brand_hero.py.md` F1); onboarding gets `error_content`.

**Exit criteria:** side-by-side screenshot comparison against CollabShell (light+dark) with the parity matrices from 01/02/03 re-checked item by item; owner sign-off on the home screen.

---

## R3 — Terminal excellence (beat Termux's terminal)

- **Live pipeline:** feed → `send_bytes` forwarding (from R1), observable scrollback or event-driven flush (~2 Hz coalescing, Sherlock render-flusher pattern), blocking `os.write` moved off the DataChannel thread (`flet-terminal.md` F7).
- **Multi-shell UI:** in-screen tab switcher over `SessionManager.entries` (4 shells) with per-tab close and a `+` (design-parity 02-F5); session lifetime hardening — fd leaks on failed `Popen` (`session_service.py.md` F2), `stop()` SIGTERM→SIGKILL escalation + reader-thread join (F3), partial-write handling (F4), `close()` stale `ready` state and dead-session replacement (manager F3/F4), entries-dict thread safety via loop marshaling (F2).
- **Session features:** FAB/action menu (copy selection, paste, zoom in/out/reset, cursor blink, clear, theme presets — 02-F8/F10), `on_title_change` (OSC 0/2) → live `user@host:cwd` in the header, `on_bell` → subtle feedback, sticky CTRL/ALT parity, custom extra-keys layouts per distro, hardware-shortcut bus (`on_shortcut`) for tab switching, scrollback search wired to the toggle, wakelock while a session is open, fullscreen that actually fullscreens (nav hidden), reconnect-on-remount hardening (DataChannel `_channel` reset — `flet-terminal.md` F2).
- **argv fidelity:** golden contract stays, plus the D-016 flag set verified on device (`--change-id`, `/dev/shm`, stdio binds, `--link2symlink`, `-L`, `--sysvipc`, `--kill-on-exit`, `--kernel-release`, `PROOT_L2S_DIR`); decide **[O-8]** TERMUX-masquerade env to unlock upstream's own Termux flag path.
- **apt note:** the D-016 `--no-upgrade` caveat surfaced below the header (no layout jump — 02-F11).

**Exit criteria:** device run — two shells in two containers, tab switching with replay, resize on keyboard, extra keys, search, zoom, copy/paste, fullscreen, force-stop; no fd/thread leaks over a 10-minute session.

---

## R4 — Full proot-distro surface (utilization to the fullest; beat Termux at its own game)

Everything upstream exposes gets UI or a recorded deliberate no, per `dependency-utilization/proot-distro.md` and `proot-distro-api.md` §4.2:

- **Container actions, complete:** rename, backup (SAF-correct save with `src_bytes`), restore, copy-path, sync (checksum + prune), reset, remove, remove-image, clear-cache (orphans + build cache), ps (live session list), kill (SIGTERM→SIGKILL escalation UI).
- **Storage manager:** `iter_cached_images` table (IMAGE/ARCH/ID/SIZE/CREATED with upstream `_fmt_age` parity — `arrow.md` F3/F4), per-image reclaim, "free X MB" flows, busy-lock states ("install already in progress" via `busy_locks()`).
- **Distro detail screens:** `guestfile`/`passwd` introspection (os-release, default shell, image Env/Entrypoint/Cmd from `manifest.json`), resolved digest display.
- **Certified catalog, hardened:** digest-pinned entries (tag for display, digest on the wire), per-distro `registry` field (distro-images §4), custom-ref path shows resolved digest; search pagination + official badge.
- **Structured command mode (O-4):** `command_run` one-shot exec → CollabShell notebook-style output cells (roadmap §1c mapping); dual-mode UX (interactive console + structured command→outputs).
- **On-device image bakery:** `command_build` (Dockerfile engine, RUN via subprocess — facade-safe `run_step.py:228`) → "Remix this container"; `command_push` to GHCR/Hub with `PD_DOCKER_AUTH`. **[O]** decide shipping order vs R5.
- **Background services:** `login --detach` daemons surviving screen switches (registered sessions, force-stop from ps).
- **Install pipeline on anyio:** `CancelScope` + shielded cleanup, `CapacityLimiter(1-2)`, memory-object-stream progress (replaces stderr scraping), cancel button that actually cancels; `SSL_CERT_FILE=certifi.where()` set in the env contract so OCI pulls use the pinned bundle (`certifi.md` F1).
- **Pull-limit UX:** ratelimit-header logging, `is_pull_limit` copy pointing at Docker's limits + the existing token setting (distro-images §2); never a tight retry loop.

**Exit criteria:** every §4.2 row in `proot-distro-api.md` maps to shipped UI or an owners-signed no; device run exercises backup→restore, sync, build→install-as, ps/kill, storage reclaim.

---

## R5 — Updates, ads production, telemetry

- **Owner ruling (2026-10-24): ads must be EXACTLY Sherlock's AdService** — port `/home/maikel/.zcode/workspace/default/Sherlock/src/services/ad_service.py` verbatim in behavior (UMP flow at launch, preload→show with the 30 s interval guard, service release on close, privacy-options probe, pooled banners per slot); our `AdService`/`banner_ad.py` are audited against that file line-by-line and every divergence is either removed or justified in a decision entry. This subsumes the consent-gate items below.

- **Update service rebuild:** `packaging.version.Version` comparisons (local + feed), app-owned retry with backoff over `httpx.TimeoutException`/5xx only, per-phase timeouts, one long-lived client, error ≠ no-update (distinct states), `MockTransport` tests, `playstore_url` fallback, overall deadline, no redirect downgrade (`httpx.md`, `update_service.py.md`).
- **Production AdMob:** owner creates the account; production unit IDs replace the test aliases (today PROD == Google test IDs byte-for-byte — `ad_service.py.md` F1); CI production-ID guard (FFmpeg precedent); `DebugGeography.EEA` device sighting; interstitial at natural breaks only; `on_paid` micros logging; UMP privacy-options entry always reachable; consent failure = no ads + surfaced reason.
- **In-app feed ops:** `version.json` publishing ritual (runbook §5), mandatory-update path honored.

**Exit criteria:** EEA consent flow sighted on device with debug geography; test-vs-prod ID guard green; update check verified against the real feed with a staged newer version.

---

## R6 — Release engineering, CI, tests

- **CI (`app.yml`):** Android compile proof (`uv pip compile --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/` — the msgpack-rule executable); prune verification that recurses into `app/app.zip` (+ fix `oauthlib/**` → `oauthlib*` so dist-info goes too — `oauthlib.md` F2); alignment gate that inspects *all* artifacts (fix the `all()` short-circuit — `click.md` F2) and handles empty-build paths; release-notes **finalize** step (never leaves placeholder bodies); `timeout-minutes` on the quality job; quoted step names (D-015.7); template-zip sha256 pre-seed/verify; `paths:`/D-015 §7(b) drift fixed; AAB minSdk/targetSdk/ABI recorded into `play-policy.md` §2 (A-4).
- **Quality gates:** real render gate — `Renderer.render_component` executes component bodies (today the D-015 guard is void — `tests__test_ui_reactive.py.md` F1); mutation-hardened guards (imperative-mutation scan covers all screen files — F3; bare `from flet import X` names visible to the AST guard — `check_flet_api.py.md` F1); `timeout_method = "thread"` pin (`pytest-timeout.md` F1); shim cleanup promoted to `conftest.py` (order-independence — `test_core.py.md` F1); dead `conftest.py` fixtures removed or used; coverage for `app_controller`/`update_service` (currently 0 %); terminal-wiring tests drive real byte flow (not MagicMock vacuity — `test_terminal_wiring.py.md` F1-F4); version-identity chain includes `flet-proot` pin + changelog head (`test_version_sync.py.md` F1/F4) and the missing D-013/D-014 decision entries get written.
- **Tooling:** builder fail-fast license check before download (`scripts/build_flet_proot_wheel.py.md` F1), retry/backoff on deb fetch (F3), wheel METADATA multi-license (F4), recipe pin re-sync 5.1.107.96→98 (`cookiecutter.md` F3, `THIRD-PARTY-SOURCES.md` table), ruff `required-version` + format scope vs deleted files, `filterwarnings` regex fix (dead `tests`/`hooks` branches, missing `app_controller` — `iniconfig.md` F2).

**Exit criteria:** one tagged prerelease runs the full gate set end-to-end with recorded AAB inspection outputs; mutation checks catch the seven currently-invisible regressions.

---

## R7 — Brand, assets, store presence

- **[O-1] Brand name decision** (repo/product; must not be "proot-distro"/Termux/distro names — licensing A7) — single rename commit across pyproject/bundle/readme.
- **Icon system:** redesign `icon.png` for 48 px legibility (current wordmark alpha-bbox is 1.75:1 in a 1024 canvas), fix the `#121218`-on-`#121218` dark-mode penguin, adaptive-icon background + `icon_background`, light-tone `splash.png` (17:1 target — `flet-platform-assets.md` F1-F3, `pillow.md` F1/F6, `icon.svg.md` F1).
- **Store assets:** feature graphic, phone screenshots (7" & 10"), 512×512 icon, listing copy per distro-images §5 (brand-only title, factual distro references, non-affiliation disclaimers), README badges + screenshots.
- **Privacy:** stable policy URL (kiri.ng or repo page) + in-app link consistency check (play-policy A-9).

---

## R8 — Licensing & compliance ship (M6 of the old plan, fully kept)

- LICENSES texts ship inside the APK (restored in R1; verified by the two tests); in-app screen carries full texts + §3.3 wording + Debian/Ubuntu attribution block (licensing §3.3, distro-images §1.3).
- `THIRD-PARTY-SOURCES.md` regenerated per release (A3) with the 5.1.107.98 pin table; written offer ≥3 years; source links next to every release (GPL §6(d)+§6(b)).
- **[O/A8] Counsel decision** on the GPL derivative question recorded in `decisions.md` (proceed-as-Option-A posture meanwhile).
- Play console: data-safety form transcribed from the Mobile Ads SDK Index entry (A-8), export-compliance declaration (A-10), IARC questionnaire, ads declaration, FGS stance memo (default NO; revisit only from background-kill evidence — A-11), App Signing enrollment choice (A-15), precedent re-check UserLAnd/Termux/Andronix (A-16), zstd probe (O-7) if bundled imagery ever lands.

## R9 — Publication

- Version `1.0.0` tag → full CI → device QA per the testing protocol (pass/fail + taps + logcat per action) → release ritual (verification swarm, finalized notes, feed publish) → Play internal → closed → production; AAB carries the `CHANNEL` stamp; F-Droid/GitHub fallback decision (A-10); post-launch: update-feed ops, crash watch, AdMob policy monitoring, dependency-bump discipline (D-004/D-010 re-verify lists).

---

## Standing rules (every milestone)

- Plan mode before each milestone; decisions appended to `decisions.md`.
- No patches/vendoring/forks; env/config/CLI steering only (D-001). Dependencies frozen (D-003); msgpack never pinned ≥1.2.0; flet family bumps atomically (D-004).
- Offline tests + `flet run` smoke before any APK handoff; device truth only from CI artifacts (D-005/D-006); evidence protocol from `testing-findings.md` on every device run.
- Every device-facing change re-checks the swarm findings that touch it (`docs/swarm/` is the regression index).
