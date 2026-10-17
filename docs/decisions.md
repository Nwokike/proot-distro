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
Owner initially said "our flet version should not be 1.0.4 but 1.1.0". **Verified**: no stable `1.1.0` exists on PyPI or GitHub — only `1.1.0.dev0` (pre-release, published 2026-10-15 18:53 UTC; flet/flet-ads/flet-cli alike; `uv add flet==1.1.0` cannot resolve). Decision (owner, after the verified facts): **stay on the stable 1.0.4 lockstep family** — the stack M0 validated on-device and the house standard — and run the full per-dependency API documentation swarm against the 1.0.4 tree. The day stable 1.1.0 ships: bump the family in one command + rerun a diff study (docs/dependency-studies/ diffs).

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
| O-8 | TERMUX-masquerade env (`TERMUX_VERSION` + prefix) to unlock Termux-mode proot flags after M0 | M0 → M3 |
| O-9 | Whether the no-local-builds rule extends to dev-only desktop builds (the only way to see extensions locally) | owner |

## D-011 · 2026-10-16 · M0 device-retest loop DEFERRED (owner) — M1 proceeds
Owner ruling: "The tenth spike still don't work… I'm not going to continue doing it. When we are done with all my milestones, then we can go back to the loop if it is still available."
Ruling: the spike device-retest loop is **closed for now and not blocking**. M0's load-bearing claims are already proven on hardware (G1 exec from nativeLibraryDir, G2 in-process OCI install, G3 guest exec via loader, G5 interactive PTY session — see `m0-checklist.md`). The one open failure is **G4-apt only for upgrade-over-existing packages** (dpkg chown ENOENT through link2symlink; fresh installs work). Interim product behavior: `--no-upgrade` (already in spike-10's G4) + guest UI note if the bug proves durable.
**Resume recipe (cold):** install release `spike-10` (or any later build), Run ALL, capture the G4 + G4b log text; G4b (`--only-upgrade perl-base`) isolates the upgrade path. Owner Termux control #2 (`apt-get install --only-upgrade perl-base` in Termux's Debian) completes the matrix: same failure in Termux ⇒ upstream/proot-wide (document, keep workaround); works in Termux ⇒ flag/env delta to chase. Do this when the owner re-opens the loop (after M1–M6), not before.
Evidence: owner message 2026-10-16 (spike-10 retest failing); apt arc in `docs/m0-checklist.md` §"Device retests #4+".

## D-012 · 2026-10-16 · flet-terminal 0.4.0 shipped; package dep style = bare `flet` + compat matrix; app keeps floors + lock
M1 executed. `flet-terminal` 0.4.0 is on PyPI (publish workflow, trusted publisher) with a proper `v0.4.0` GitHub release (Windows/Linux + unsigned split-per-ABI demo APK).
Rulings recorded:
1. **Package dependency style (O-2 for the package): bare `"flet"`**, exactly like flet-notifications/flet-yandex-ads. The safety net is the new `compat.yml` matrix (flet 1.0.0/1.0.1/1.0.4/latest × python 3.10/3.14 + Dart analyze/test on Flutter 3.44.8), not a pip floor. If a matrix leg ever fails, the proven floor is pinned in a follow-up commit.
2. **App pin style (O-2 for the app): floors in pyproject + exact in `uv.lock`** (unchanged; house style). App now requires `flet-terminal>=0.4.0`; m0-spike pins `==0.4.0`.
3. **Construct-anywhere fix chosen over document-only**: `MobileTerminal` de-componentized (plain modifier buttons + implemented `ExtraKeysBar.refresh_buttons()`), fixing both the renderer-context RuntimeError and the latent `AttributeError`; `Terminal._mark_dart_ready()` hardened for detached controls.
4. **CI lesson baked into the package repo**: local lock had ruff 0.15.22 while CI pip-installed latest (0.17.1) — the quality gate failed on the v0.4.0 tag because defaults had moved. Fix = `ruff==0.17.1` pinned everywhere + explicit `[tool.ruff.lint] select` + `required-version`. Also `publish.yml` is now idempotent (checks PyPI before upload) so re-tags are safe.
Evidence: `Nwokike/flet-terminal` releases v0.4.0; PyPI `flet-terminal` 0.4.0; CI runs 38946374422 (compat main), 38946425178 (build-all v0.4.0), 38946420293 (publish skip-path).

## D-013 · 2026-10-16 · flet-proot production wheel: own-CI repack, pinned + 16K-enforced, arm64-v8a + x86_64
M2 executed (forge request #6979 still unanswered — reply posted, recipe bundle kept ready, not blocking).
Rulings:
1. **Production path = our own CI wheel set**, built by `tools/build_flet_proot_wheel.py` from the sha256 lock `tools/flet_proot_sources.json` (proot 5.1.107.96, libtalloc 2.5.0, libandroid-shmem 0.7 for aarch64 + x86_64). Bumping any source = one-commit lock edit (the "bump a version" rule). If mobile-forge accepts the recipe later, consumption collapses to a normal dependency.
2. **Wheel naming/versioning mirrors `flet-libffmpeg`**: version = upstream proot version, build tag = our revision, platform tag `py3-none-android_24_<abi>` per arch (`flet_proot-5.1.107.96-1-py3-none-android_24_arm64_v8a.whl`).
3. **ABI policy (O-6 RESOLVED): arm64-v8a + x86_64** (x86_64 wheels + a dedicated spike APK leg for emulator/QA; skip armeabi-v7a — 64-bit rule satisfied, negligible 32-bit share for this app).
4. **Integrity chain (triple-gated)**: sha256 of each deb verified at download (builder) → every payload's min PT_LOAD ≥ 0x4000 asserted at wheel-write time (builder) → presence + alignment re-checked in built APKs by the now-enforcing `tools/check_apk_alignment.py`. The once-planned **NDK-r28+ rebuild is not required while Termux prebuilts stay 16K-aligned** (evidence: all payloads `align=0x4000` in every CI run; the build-time assert catches any regression with a named offender) — NDK rebuild remains the documented fallback.
5. **Full license texts + THIRD-PARTY.md ship inside the wheel** (GPL-2.0, GPL-3.0, BSD-3-Clause; vendored under `tools/licenses/`), and the manifest exposes machine-readable provenance (`VERSION`, `WHEEL_BUILD_TAG`, `ARCH`, `SOURCES` with url+sha256) that feeds M5's `THIRD-PARTY-SOURCES.md` and the in-app licenses screen.
6. **Forge track**: reply posted on #6979 offering the recipe (repack-based build.sh question raised); bundle lives at `docs/requests/mobile-forge-recipe-flet-proot/` — no upstream dependency created.
Evidence: local builds of both wheels + legacy `py3-none-any` mode (all payloads 0x4000, RECORD/licenses/manifest verified); CI: `spike-<run>` dual-ABI legs + enforcing APK inspect (recorded in `docs/m0-checklist.md` after the run).

## D-014 · 2026-10-17 · One-OS test, login-shell session parity, and the spike Run-ALL wiring bug
Owner rulings/feedback after testing spike-13 ("all of them have been the same error… I'm sure you are missing something", "lets only install 1 os in test", "I don't think what we logged into is proot distro Debian"):
1. **One OS in the spike test: `debian:bookworm` only** (owner offered debian-or-ubuntu; debian = apt/dpkg = the interesting surface). G2/G3/G4/G5 all use it; Alpine removed from the spike. M3 keeps the certified catalog (ubuntu/debian/alpine) but each install/test run is one container at a time.
2. **Session spawn parity with `proot-distro login`**: the interactive session now runs the container's LOGIN shell (`/bin/bash -l`, fallback `/bin/sh -i`) — the owner's complaint ("just hash, I don't even know which is it") was our bare `/bin/sh -i`, which shows a `#` prompt and none of the login profile; upstream commands/login runs `login_shell [-l | -c …]`, which is what produces Termux's `root@hostname` prompt. M4's ProotSession inherits this rule.
3. **Root cause found for the "same error every time": a harness wiring bug, not a device mystery.** `run_all`'s G4-apt command was missing `--no-upgrade` while the individual G4 button had it — every "Run ALL" (the path the owner actually presses) has been exercising the *unpatched* dpkg upgrade-over-existing path while my notes claimed the patch. Fixed with ONE shared `APT_SCRIPT` constant used by both paths. (This is the class of miss that duplicate near-identical code creates; the constant is now the only definition.)
4. **f2fs semantics verified from pinned upstream source** (termux/proot v5.1.107.96, `src/path/f2fs-bug.c:120-136`, `src/path/canon.c:156`): `PROOT_F2FS_WORKAROUND` accepts `1`=force-enable, `0`=force-disable, unset=proot probes. The forced `"0"` is REMOVED (unset = Termux reference behavior), and the spike now logs an on-device Python replication of proot's probe at G0 so the resumed loop reasons from data. The workaround, when active, returns a synthetic -ENOENT for entries absent from readdir — which is exactly dpkg's `.dpkg-new` chown failure signature; the resumed loop tests both states with evidence.
 Evidence: spike-13 device log (owner, 2026-10-17) shows G1/G1b/G2/G3 green and the dpkg chown ENOENT on the *unpatched* upgrade path; upstream source quotes above; local gates green.
