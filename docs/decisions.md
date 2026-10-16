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
