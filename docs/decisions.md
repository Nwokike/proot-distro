# Decision log — proot-distro-flet

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

## Open decisions (resolve in the owning milestone's plan mode)
| # | Decision | Owner milestone |
|---|---|---|
| O-1 | Product/brand name (repo + `[tool.flet].product` + dir rename) | M0/M1 |
| O-2 | flet pin style: exact `==1.0.4` pair (FFmpeg style) vs `>=` floor (Sherlock style) | M1 |
| O-3 | Spawn port: Python-side `subprocess` vs Dart-side `Process` (flet-terminal feature) | M0 gate 4 → M1 |
| O-4 | Dual-mode UX (interactive console + structured command→outputs) | M4 |
| O-5 | `flet-notifications` inclusion for session persistence (default: NO — patcher complication) | M4/M5 |
| O-6 | x86_64 ABI inclusion (emulator QA) vs what the forge wheel ships | M2 |
| O-7 | zstd OCI layers: verify `compression.zstd` in Flet's bundled Python 3.14 (fallback: gzip images) | M0/M3 |
| O-8 | TERMUX-masquerade env (`TERMUX_VERSION` + prefix) to unlock Termux-mode proot flags after M0 | M0 → M3 |
| O-9 | Whether the no-local-builds rule extends to dev-only desktop builds (the only way to see extensions locally) | owner |
