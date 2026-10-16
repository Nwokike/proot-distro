# app-data-formulator.md — Data Formulator (cleanest facade)

Verified 2026-10-16 against `C:\Users\nwoki\.zcode\workspace\default\data-formulator`.

## Identity
`data-formulator-app` v1.0.0. Wraps PyPI `data-formulator>=0.7.0` (locked 0.7.0; upstream 0.8.0b1 only ever vendor-cloned for study, never vendored). Only **4 direct runtime deps**: `data-formulator`, `flet>=1.0.3`, `flet-ads>=1.0.3`, `flet-android-notifications>=0.11.2` — "minimal direct deps" posture in action (159 packages ride in transitively via the wrapped lib).

## Wrapping pattern — the model to copy verbatim
- `src/services/data_formulator_service.py` (~3k lines) declares itself **"the ONLY module that may import `data_formulator.*`"**; all upstream imports are lazy inside a thread-safe `_load_df_modules()` gate so `flet run` boots without touching upstream; every blocking call in `asyncio.to_thread`; returns only plain `dict/list/dataclass` — never Flask objects. The upstream Flask server is never started; all 95 routes re-implemented 1:1 as Flet.
- **Provider seam by constructor injection, not patching**: upstream's litellm client is replaced by passing `KiriClient` (same `ping`/`get_completion`/`get_completion_with_tools` surface) into agent constructors. Proof that even LLM clients can be swapped patch-free.
- Upstream steered via its public config surface: `DATA_FORMULATOR_HOME` env, `DF_AGENT_LOG=off`, `PYTHONDONTWRITEBYTECODE` (Windows crash workaround) — none of it a patch.
- Additive normalization before the upstream gate (`.tsv`→tab-csv, parquet direct-read, charset sniff, fuzzy dates) + honest feature-degradation (vl-convert feature-detected; PNG export disabled with a stated reason).
- **Zero monkeypatches** (repo-wide grep clean outside test fixtures). One boundary leak flagged: `app_controller.py:1089` imports `data_formulator.data_loader` directly, contradicting the sole-importer docstring — enforce with a CI grep guard in ours.

## CI quality gate ideas to copy
Frozen `uv sync`; `compileall`; **button-API grep guard**; **Python AST namespace guard** (banned APIs + every `ft.Icons.*` verified against installed flet); **Android compile proof**: `uv pip compile --python-version 3.12 --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/` — catches Android wheel gaps before the APK job; version-consistency check.

## Drifts to avoid (working tree currently ships them)
`version.json` 0.1.0 vs pyproject 1.0.0; `requires-python >=3.14` vs CI `UV_PYTHON 3.12`; `ci/android-excludes.txt` deleted while the workflow still passes `--excludes` to it → the Android proof step as written cannot pass. Lesson: the version-consistency gate only works if all sources move in one commit.

## Transferables for proot-distro-flet
One `proot_service.py` as the sole importer + lazy-load gate + `to_thread` + plain-data returns; declare every directly-imported transitive in pyproject (DDGS's test guards it); steer proot-distro via env contract (`TERMUX__*`, `PD_PROOT_BIN`, XDG) — **no patches needed**; add the Android compile proof to our CI quality job; keep `docs/dependency-studies`-style per-dep docs (this repo's convention, mirrored here).
