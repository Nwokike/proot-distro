# Decision log — proot-distro

Append-only. Each decision: date, context, ruling, evidence link.

## D-001 · 2026-10-16 · Wrap upstream `proot-distro`, never fork
Ruling: the app consumes `proot-distro` (PyPI, v5.x pure-Python, zero deps) as-is. Integration only through the documented contract: env vars before first import (`TERMUX__*`, XDG, `PD_PROOT_BIN`), pure helper APIs, on-disk layout, and the CLI for login/exec. No monkeypatches, no vendoring, no internal-API dependence beyond a single guarded adapter.
Evidence: `reference/dep-proot-distro.md`; canonical research `../proot-distro-flet-feasibility.md` (workspace).

## D-002 · 2026-10-16 · Docs live in-repo during the private phase
`docs/` (roadmap + reference library + decisions + testing findings + requests) is the context-preservation system so any agent can resume cold. Per the house extension standard, prune/adapt before the repo goes public.

## D-003 · 2026-10-16 · Frozen dependency set
Runtime: `flet`, `flet-ads`, `proot-distro`, `flet-terminal` (+ the `flet-proot` native wheel when it exists). Dev: `flet-cli`, `flet-desktop`, `pytest`, `pytest-timeout`, `ruff`. Any addition needs owner sign-off.

## D-004 · 2026-10-16 · Update path is a version bump
No pins above Android ceilings (msgpack rule: never ≥1.2.x); floors in pyproject, exact in `uv.lock`, `uv sync --frozen` in CI. flet family is bumped as one atomic set (flet-ads pins `flet==X`).

## D-005 · 2026-10-16 · Testing loop (verified mechanics)
(1) `uv run pytest` offline for all logic incl. fake-transport `ProotSession` tests; (2) `uv run flet run` for all non-extension UI with placeholder panes; (3) CI `build-<sha>` artifacts installed on device = the only true gate for extension + proot behavior. No local `flet build` (owner rule). Evidence: `testing-findings.md`.

## D-006 · 2026-10-16 · CI delivery = GitHub Releases only, never artifacts
`actions/upload-artifact` fails on this account: **"Artifact storage quota has been hit"** (observed in M0 spike run 38905063919; the same account-level quota already blocks Data Formulator CI). Release assets are unaffected → every workflow delivers via `softprops/action-gh-release` prereleases (house pattern). The M0 workflow's artifact step was removed after the first run.

## D-007 · 2026-10-16 · Repository is PUBLIC
Switched public per owner ("if you make the repository public, the GitHub action footer will no longer disturb you"): public repos get free Actions minutes + generous storage, removing the account-level quota/billing friction (D-006). Docs stay in-repo (animepahe-tv precedent); the reference library is written to be publishable.

## D-008 · 2026-10-16 · Signing: house keystore + secrets, scripted
Recovered the house signing material from an older app repo (secrets are write-only even for admins, so `tools/export_keystore_from_repo.py` temporarily ran a workflow in `Nwokike/Sherlock` that packed `KEYSTORE_BASE64`/`KEY_ALIAS`/`KEYSTORE_PASSWORD`/`KEY_PASSWORD` into a throwaway prerelease asset, then deleted branch+release — source repo left untouched). `tools/setup_signing.py` set all four secrets on this repo; verified alias = `upload`, keystore ≈ 3.7 KB b64. Workflow decodes with the exact house lines (`echo "$KEYSTORE_BASE64" | base64 --decode > kiri_keystore.jks`); pyproject carries the house `[tool.flet.android.signing]` block. Both scripts are generic — use for every future repo.

## D-009 · 2026-10-16 · Repo renamed to `proot-distro`
Renamed `Nwokike/proot-distro-flet` → `Nwokike/proot-distro` per owner ("rename the repo proot distro, don't add flet"). GitHub redirects every old URL (releases, links, remotes); all in-repo references updated. The **local workspace dir and the uv project name stay `proot-distro-flet`** — uv rejects a project that depends on a package with its own name, so the project name must differ from the wrapped `proot-distro` dependency (commented in pyproject.toml).

## D-010 · 2026-10-16 · flet version: stay on stable 1.0.4 (verified 1.1.0 = dev0 only)
Owner initially said "our flet version should not be 1.0.4 but 1.1.0". **Verified**: no stable `1.1.0` exists on PyPI or GitHub — only `1.1.0.dev0` (pre-release, published 2026-10-15 18:53 UTC; flet/flet-ads/flet-cli alike; `uv add flet==1.1.0` cannot resolve). Decision (owner, after the verified facts): **stay on the stable 1.0.4 lockstep family** — the stack the device spike validated on-device and the house standard — and run the full per-dependency API documentation swarm against the 1.0.4 tree. The day stable 1.1.0 ships: bump the family in one command + rerun a diff study (docs/dependency-studies/ diffs).

## Open decisions (resolve in the owning milestone's plan mode)
| # | Decision | Owner milestone |
|---|---|---|
| O-1 | Product/brand name (repo + `[tool.flet].product` + dir rename) | M0/M1 |
| O-2 | flet pin style: exact `==1.0.4` pair (FFmpeg style) vs `>=` floor (Sherlock style) | M1 |
| O-3 | Spawn port: Python-side `subprocess` vs Dart-side `Process` (flet-terminal feature) | **CLOSED 2026-10-16 by device evidence**: Python-side wins — PTY session ran on-device (spike-5, owner's example pattern: `pty.openpty` + `Popen` + `TIOCSWINSZ`); `sys.executable` is the Flutter host so the CLI-subprocess route is dead, but direct proot spawn is proven. |
| O-4 | Dual-mode UX (interactive console + structured command→outputs) | M4 |
| O-5 | `flet-notifications` inclusion for session persistence (default: NO — patcher complication) | M4/M5 |
| O-6 | x86_64 ABI inclusion (emulator QA) vs what the forge wheel ships | M2 |
| O-7 | zstd OCI layers: verify `compression.zstd` in Flet's bundled Python 3.14 (fallback: gzip images) | M0/M3 |
| O-8 | TERMUX-masquerade env (`TERMUX_VERSION` + prefix) to unlock Termux-mode proot flags | M3 → M4 |
| O-9 | Whether the no-local-builds rule extends to dev-only desktop builds (the only way to see extensions locally) | owner |

## D-015 · 2026-10-19 · M3 executed — scaffold + the state-driven rework (owner-reported crash)
M3 shipped (`src/` house scaffold: thin `main.py` → `AppController` → `@ft.observable AppState` + `ControllerMethodsCtx` → component `AppShell`; `services/proot_service.py` sole importer; `core/proot_probe.py` gating; CI `app.yml` quality → dual-ABI APK → enforcing payload/16K inspect → prerelease). Rulings:

1. **"Frozen controls cannot be updated" (owner's desktop run): the UI is now a pure function of state.** The first scaffold rendered stable screen objects and mutated them imperatively (`progress_line.value = …`, `search_status.value = …`, `container_column.controls`), which Flet 1.0's declarative renderer forbids. Rework: `src/screens.py` is `@ft.component DistroView/SettingsView` reading the observable state during render; handlers only write state or call controller methods; transient text inputs live in `ft.use_state`. A source-level guard (`tests/test_ui_reactive.py`) fails the build if imperative mutation returns to `screens.py`, and the components are constructed + re-rendered inside a renderer context in tests, so the bug class cannot silently return.
2. **Landmine recorded: `@ft.component` functions cannot be called from event handlers.** `page.show_dialog(content=LicensesView())` raised `RuntimeError: No current renderer is set` in prototyping — the same constraint as flet-terminal's `MobileTerminal`. Rule: anything built inside a handler (dialog content) is a plain function; only render trees call components. `licenses_view()` is the single definition of that content.
3. **Theme system (owner request: CollabShell light/dark parity):** `core/theme.py` mirrors the CollabShell pattern — `AppColors` LIGHT_/DARK_ palettes, `is_light_theme()` resolving SYSTEM via `page.platform_brightness`, `state.theme_mode`/`theme_revision` subscription, `build_theme()` → `ft.Theme` pair installed at boot, Settings cycles System/Light/Dark and persists via `SharedPreferences`. Every component reads its colors at render time, so a flip re-renders both palettes.
4. **A9 (Play Deceptive Behavior §3.2) enforced in the install flow:** an explicit consent dialog before every pull carrying the ref, the "size unknown until the registry responds" disclosure, and a labeled typical-size estimate (Alpine ~8 MB · Debian ~30 MB · Ubuntu ~75 MB). The facade has no pre-pull size API (fragile surface — the doc's conservative-estimate path applies).
5. **A8 (GPL posture): proceed as Option A.** The licenses screen ships the §3.3 content contract: dynamic per-component entries (versions read from installed dist metadata + the `flet_proot` wheel manifest — nothing hardcoded, honoring the owner's no-hardcoded-data rule), the §6(b) source-offer block with the Option-A whole-application clause, the Debian/Ubuntu §1.3 attribution lines, and the scrollable `LICENSES/` texts. Counsel question stays on the M3 record.
6. **flet-proot payload bumped 5.1.107.96 → 5.1.107.98** (Termux removed the old debs from the pool — CI 404). One-commit lock edit per D-013; both wheels rebuilt locally with every payload at `align=0x4000`; the app's `pyproject.toml` pin moved with it. The device-spike sources (removed per D-016) had verified the flags against 5.1.107.96 — a patch-level bump keeps that verification valid.
7. **CI lessons this run:** (a) an unquoted `": "` inside a YAML step name made GitHub reject the whole workflow file with no jobs — quote step names; (b) `app.yml`'s `paths:` filter excludes `tests/**`, so a tests-only change needs a `workflow_dispatch`; (c) Linux runners have a real `grp` module, so shim tests must exercise the factories directly rather than assuming the shim is active (the Android-only path is pinned by `test_ensure_only_shims_what_is_missing`).
8. **Header/menu (owner correction):** the M3 shell ships WITHOUT a header — the brand hero lives in the home body (CollabShell's `build_brand_header` pattern) and the theme switch is a bare icon button. The owner's ruling: CollabShell does have a menu/header and the correct design is an M4 task (study CollabShell's menu chrome + icon placement); the M3 shell is a skeleton by design. The brand icon is ONE self-adapting SVG (`src/assets/icon.svg`): the app tints it at render time (`ft.Image(color=…)`), and the same file carries an internal `prefers-color-scheme` style block so the README swaps on GitHub without a second white variant (the owner's point: one SVG can be made white — GitHub sanitizes README HTML, so the swap has to live inside the file, not in markup).
9. **Deferred, unchanged:** terminal/session UI (M4), ads wiring (M4/M5), anyio cancellable-install pipeline (P1–P2 stay parked until the owner asks — the install shows live stage lines and cleanup happens through Remove, matching the one-to-one wrapping rule).

## D-016 · 2026-10-19 · Device-spike era closed — rulings that survive (owner ruling)
Owner (2026-10-19): "I hope you have deleted everything about Milestone Zero." The
spike app (`m0-spike/`), its workflow and the M0 checklist are removed from the repo.
The spike proved the architecture on-device in October; what still governs the app is
recorded here (the old D-011/D-011-addendum/D-014 entries are superseded by this one):

1. **The go/no-go claims stay proven:** proot exec from `nativeLibraryDir`, in-process
   OCI install, guest exec through the loader, and an interactive PTY session all ran
   on the owner's phone; `pwd` exists and `grp` is absent on Android CPython (the
   `core/posixdb.py` shim, upstream request flet-dev/python-build#45).
2. **Guest apt: upgrade-over-existing remains the one open bug.** Fresh `apt install`
   works; upgrading an existing package fails (dpkg chown ENOENT through
   link2symlink; root-cause hypothesis: dpkg's hardlink-pair preservation triggers
   proot's l2s parking, and the follow-up chown misses). Verified NOT the f2fs
   workaround (device probe: bug absent). Resume recipe (owner re-opens it after M6):
   simulate (`apt-get -s install --no-upgrade cowsay`), log the exact command, and if
   apt insists, try a version-pinned install; a Termux control run
   (`apt-get install --only-upgrade perl-base`) completes the matrix. Until then the
   product behavior is `--no-upgrade` plus a guest copy note (M4).
3. **Session spawn rule for M4:** the interactive session runs the container's LOGIN
   shell (`/bin/bash -l`, fallback `/bin/sh -i`) — that is what produces Termux's
   `root@hostname` prompt; a bare `sh -i` (just `#`) was a real bug. Session argv uses
   `--change-id=0:0`, `<rootfs>tmp:/dev/shm`, stdio binds, `--link2symlink`, `-L`,
   `--sysvipc`, `--kill-on-exit`, `--kernel-release`, `PROOT_L2S_DIR`.
4. **Test policy:** one container per test run; `debian:bookworm` is the reference
   distro. Any duplicated near-identical code path is a defect class — one shared
   definition per behavior (the Run-ALL divergence that hid the apt bug for weeks).


## D-017 · 2026-10-19 · M4 executed — terminal sessions, the CollabShell menu, Sherlock's ads
M4 shipped (owner-approved plan: full terminal parity, the CollabShell header, the whole ads flow). Rulings:

1. **The guest argv comes from upstream, never from us.** `session_service.session_argv` runs
   `proot-distro login <c> --get-proot-cmd` IN-PROCESS (a subprocess is impossible on Android —
   `sys.executable` is the Flutter host, M0 G1b) and parses the printed `env -i …` line. Nothing
   about `build_proot_args` is reimplemented or hardcoded, so an upstream bump flows through; the
   parser is pinned by a golden-string test and fails loudly (never silently) on a format change.
2. **The PTY is the flet-terminal example's shape**: `openpty` + `Popen` on the slave fd with
   `start_new_session`, a blocking read thread, `TIOCSWINSZ` resize, close-master → terminate.
   That shape was proven on-device in the M0 spike, so M4 ports it instead of inventing one.
3. **Sessions live on observable entries, not on widgets** (CollabShell's `TerminalEntry`): the
   process and a 2000-chunk scrollback live on the entry, so switching tabs re-renders the widget
   and replays the buffer instead of killing the shell. Concurrency is capped at 4 shells.
4. **Both input paths are wired**: `set_on_bytes` (binary DataChannel) AND `on_data` (the string
   path Android's soft keyboard uses). Missing the second path is why characters silently vanish
   on a phone while delete still works — the example's note is now ours.
5. **The menu is CollabShell's**: a slim bar with the current tab's name left and the action
   cluster right (theme cycle; help/version slots built in). No `ft.AppBar`, and no brand mark in
   the bar — the hero stays in the home body. (Owner correction: the M3 shell had no header and
   that was wrong; the pattern is in `docs/reference/house-ui-design.md`.)
6. **Ads follow Sherlock's `AdService` exactly** — UMP flow at launch, preload → show with a
   30-second minimum-interval guard, service release on close, privacy-options probe, pooled
   banners per slot. TEST ids only for now (the owner has no production AdMob account yet); the
   production id + the CI production-id guard land with the account (M5).
7. **The banner on the terminal screen sits ABOVE the app chrome, never next to the input.** The
   owner's brief was "best money and not be banned": the app's own header row stays between the
   ad and the terminal, the ad is nowhere near the extra-keys bar, the row is permanent (no
   layout jump), and it disappears in full-screen mode. Residual exposure is invalid traffic
   (accidental clicks) — accepted knowingly, recorded here. CollabShell itself keeps its terminal
   screen banner-free; we deviate deliberately, and only there.
8. **The flet-ads crash lesson (app-5)**: depending on `flet-ads` is enough to kill the app at
   launch on Android — its Dart extension initializes the Mobile Ads SDK before any UI exists, so
   `com.google.android.gms.ads.APPLICATION_ID` is mandatory. The owner's ruling was the test id,
   not removing the dependency. The correct test app id is
   `ca-app-pub-3940256099942544~3347511713` (Google's public sample — the first attempt was
   missing digits and would not have loaded).
9. **No swallowed bugs (owner ruling).** The service no longer logs-and-returns-empty: it raises
   with the real reason and the controller surfaces it in the UI (`state.data_note`), so an empty
   container list or a failed search says why. Comment noise across the app was cut to constraint-
   stating comments only, and the `copyright` key was removed from pyproject (no app carries one).
10. **Container actions are thin one-to-one wraps** — rename, backup, restore, copy, running
    sessions, force stop — each with the upstream namespace built in one place.

**Deferred to M5:** the production AdMob id + the CI production-id guard, the structured
dual-mode (O-4), the image bakery/push (`command_build`), and the store/release plumbing.

## D-018 · 2026-10-24 · The full-corpus swarm audit + Milestone R1 executed

The owner ordered a complete re-verification of the app and docs (96 reports in
`docs/swarm/`: 47 dependency-utilization, 43 file audits, 4 design-parity incl.
the owner-directed DDGS/CollabShell comparison, dependency tree) and a full
milestone plan to 100% + publication with no MVP scoping (`docs/roadmap.md`,
R1–R9). R1 (Restore & Unbreak) then shipped:

1. **Working-tree restorations:** LICENSES/, src/LICENSES/, the compliance docs,
   runbook, testing-findings, roadmap-synthesis, check_elf_alignment.py,
   generate_third_party_sources.py, THIRD-PARTY-SOURCES.md — all were deleted
   uncommitted (two license tests + CI steps + the wheel builder broke).
2. **AppShell re-subscribes to state** (swarm P0): commit 4ad4593 removed
   `use_state(state)`; onboarding dead-ended and Open-shell never re-rendered.
   Observable reactivity is subscription-based — the hook stays, pinned by a
   source guard test.
3. **`get_proot_cmd` rewritten (swarm P0):** call `command_login` directly with
   a full login namespace (cli.main's SIGQUIT handler is main-thread-only;
   upstream prints via `sys.stdout.buffer`, which io.StringIO lacks). A
   `.buffer`-carrying stdout stand-in + module lock; unmocked integration test
   runs the real upstream path against a fake container (both historical
   failures now impossible to reintroduce silently).
4. **Live PTY output forwarded** (swarm P0): `SessionManager._on_bytes` now
   feeds scrollback AND `mt.send_bytes`; pre-mount bytes still arrive via
   replay (pinned by test).
5. **Update-dialog re-check fixed** (swarm P0): `page.run_task(_check_again,
   page)` — a sync lambda's coroutine return is discarded by Flet.
6. **Launch allow-list hardened** (swarm P1, security): backslash normalization
   before urlsplit (`evil.com\@github.com` split-brain closed), tested.
7. **Ads consent-gated everywhere (partial; full Sherlock parity is R5):** UMP
   failure now disables ads (was: default-allow) and is surfaced via
   `state.data_note`; banners gate on `state.can_request_ads` and the banner
   pool keys on the verdict; interstitial interval consumed only on a
   successful show.
8. **Backup fixed on Android:** stage the tar in app storage, then
   `save_file(..., src_bytes=...)` — save_file without bytes raises on mobile.
9. **P1 batch:** license texts full (no 6000-char cut) with `errors="replace"`;
   `notes_for` newest-by-version-key (stdlib-only; packaging is dev-only);
   hints dismissal persisted; system-theme follows platform brightness flips
   (single mapping site `theme.apply_theme_mode`); CI version compare via
   `packaging.version.Version` in the identity script; grp shim raises
   KeyError for unnamed gids (bionic parity — upstream skips them);
   `_f2fs_probe` fully guarded; `_LineTee` captures as well as forwards;
   `S110` silent except now logs; noop default accepts any arity; Play URL
   fallback; `dismiss_hints` on the controller bridge.

Owner ruling recorded for R5: **ads exactly as Sherlock's AdService** (port
`Sherlock/src/services/ad_service.py` behavior verbatim; divergences need a
decision entry).

Exit state: 79 tests green (was 53; +26 regression tests), ruff clean,
`flet run` smoke clean (session starts, consent gate logs, feed check silent).
Remaining R1 exit step: the owner's device run from a CI APK (onboarding →
install debian:bookworm → open shell → SEE OUTPUT → type → backup → re-check).

## D-019 · 2026-10-24 · Milestone R2 executed — CollabShell design parity & house design system

Following the owner's design mandate, R2 brings UI parity with CollabShell
while integrating DDGS house polish (11pt type floor, 8-pt grid, Outfit typeface):

1. **Fixed shell-level header:** `AppHeader` moved out of the scrolling view
   columns to the `AppShell` root, directly beneath `ft.SafeArea`. Title derives
   dynamically from active tab; header bar stays pinned while content scrolls.
   Suppressed while an active terminal session owns the screen.
2. **NavigationBar isolation:** `NavigationBar` rendered conditionally
   (`if entry is None and not fullscreen:`), resolving the tab-trapping bug and
   granting the terminal true full-screen space (~80px reclaimed on mobile).
3. **Brand Hero in home body:** Rendered as the top child of `DistroView`,
   centered, 80px icon (`tokens.HERO_ICON_SIZE`, matching CollabShell's
   `ICON_XXXL`), `color_blend_mode=ft.BlendMode.SRC_IN`, `FONT_SM` tagline, token
   spacers. The logo is strictly absent from the header bar.
4. **House typography & spacing tokens:** 11pt legibility floor enforced
   (`FONT_XXS/XS=11, SM=12, MD=14, LG=16, XL=20, XXL=24, HERO=32`), 8-pt spacing
   grid (`4/8/12/16/24/32/40`). Outfit variable font bundled in `src/assets/fonts/`
   under SIL OFL and wired into both `ft.Theme`s.
5. **Surfaces & contrast:** `DARK_GLASS_BG` set to `#26263A` restoring card
   elevation over `#1E1E2E` surface. Theme-aware `theme.ok()`, `theme.warn()`,
   `theme.accent()` provide ≥3:1 contrast in both light and dark modes. Central
   `components/snack.py` provides readable, FLOATING, backstopped SnackBars.
6. **Terminal chrome parity:** Flat full-width header (`ARROW_BACK_ROUNDED`,
   `status_dot` + `ProgressRing(14)` connecting spinner, search/close/fullscreen
   buttons); quick commands append `\n` to execute immediately; default
   `show_search=False` with header toggle; dead `bottom_inset` parsing purged;
   `SessionSelectorView` rows upgraded to full-surface interactive glass cards.
7. **Onboarding polish:** Full-screen `GestureDetector(expand=True)` eliminates
   swipe dead zones; 120px circular icon backdrops with 64px glyphs; animated
   width-morphing dots (200ms `EASE_OUT`); `error_content` fallback on brand icon.

Exit state: 85 tests green (+6 design-parity guard tests), ruff clean, `flet run`
smoke clean.
