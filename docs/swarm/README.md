# Swarm audit — 2026-10-20

Scope: the M4 codebase, after the state-driven rework (D-015) and terminal/ads work (D-017).

- `dependency-tree/` — `uv tree`, inverted tree, installed-version inventory.
- `dependency-utilization/` — one report per installed package: how the app uses it today, what it misses, and whether existing usage is correct. Package source studies were already complete (`docs/dependency-studies/`, 47/47), so these agents audit **current app utilization**, not the package from scratch.
- `file-audits/` — one report per app file: bugs, Flet 1.0.4 API correctness, architecture violations, and improvements.
- `SYNTHESIS.md` — consolidated verdict and prioritized fix list (written after all batches).

Rules for auditors: `BRIEF.md`.
