# tests/test_imports_vs_deps.py — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `tests/test_imports_vs_deps.py` · `pyproject.toml` (declared deps + `[tool.flet.<platform>].dependencies`) · installed env `.venv/lib/python3.14/site-packages/` (Python 3.14.9) · all `src/**/*.py` · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/test_imports_vs_deps.py` is the app's "honest-import" guard (mirroring the DDGS discipline in `docs/reference/app-ddgs.md:8-12`). It parses every `src/**/*.py` file with `ast`, collects top-level third-party imports, skips local packages and stdlib (`sys.stdlib_module_names`), and asserts each import resolves to a declared dependency. Rationale from the docstring (`tests/test_imports_vs_deps.py:1-6`): `flet build` resolves ONLY `[project].dependencies` plus the `[tool.flet.<platform>].dependencies` tables, so an undeclared desktop-only import crashes the packaged app on Android.

Declared dependencies (normalized names, `pyproject.toml:9-15` + android table `pyproject.toml:52`):
- `flet>=1.0.4`, `flet-ads>=1.0.4`, `httpx>=0.28.1`, `flet-terminal>=0.4.0`, `proot-distro>=5.10.0` (`[project].dependencies`)
- `flet-proot==5.1.107.98` (`[tool.flet.android.dependencies]`)

The test passes (1 passed in 0.71s) — every import in `src/` currently resolves to a declared dependency, so there is no active missing-import bug in the tree.

## Findings

### F1 · P2 · Hand-rolled PEP 508 re-implementation instead of `packaging` (already installed)
- **Where:** `tests/test_imports_vs_deps.py:18-32` (`_declared`) — dependency name extraction via chained `str.split(";")`/`split("[")`/`split(">")`/`split("<")`/`split("=")`/`split("!")`/`split("~")`/`split()` and `.lower().replace("-","_")`.
- **What:** The test re-implements PEP 508 dependency parsing by hand rather than using `packaging.requirements.Requirement` / `packaging.utils.canonicalize_name`. `packaging==26.3` is already installed in the venv (`.venv/lib/python3.14/site-packages/packaging-26.3.dist-info/`) and is importable (verified: `from packaging.requirements import Requirement; from packaging.utils import canonicalize_name` works). The hand-rolled parser diverges from PEP 503 canonicalization: `my.package` → `my.package` (dot never replaced) vs canonical `my-package`; `My_Package` → `my_package` vs canonical `my-package`. For the current codebase all module names are simple (`flet`, `httpx`, `proot_distro`, …) so no live mismatch — but it is a latent correctness/robustness defect that will misfire if a dependency with dotted or mixed-case naming is ever added (D-003 freezes the set, but the parser itself is still fragile).
- **Evidence:** `tests/test_imports_vs_deps.py:26-31`; divergence demonstrated against installed `packaging` (`canonicalize_name("my.package")` → `my-package` vs hand-rolled `my.package`). `pyproject.toml:9-15` shows all current deps are simple names, so the gap is latent.
- **Fix / opportunity:** Replace `_declared()`'s manual splitting with `Requirement(dep).name` normalized via `canonicalize_name(...).replace("-","_")` (to keep the underscore convention the test already uses for module names), and drop the manual marker/extras stripping (`Requirement` handles markers/extras natively). No new dependency (`packaging` already ships in the venv); host-side test only, not built into the APK.
- **Risk if ignored:** A future dependency whose dist name differs from its top-level module in a non-underscore way (dots, mixed case) would be mis-normalized → false "missing import" or false pass.

### F2 · P2 · Provider mapping (`packages_distributions()`) is unreliable for the flet family; test leans on name-only fallback
- **Where:** `tests/test_imports_vs_deps.py:46-57` (resolution logic) and `tests/test_imports_vs_deps.py:62-68` (`_dist_map`).
- **What:** `_dist_map()` calls `importlib.metadata.packages_distributions()`. For `flet_proot` it returns `None` (not installed in the dev venv — `flet-proot` is a build-time Android payload resolved from CI `PIP_FIND_LINKS` per `pyproject.toml:50-52`; confirmed absent: `flet-proot NOT installed in venv`). For `flet_terminal` → `['flet-terminal']` and `flet_ads` → `['flet-ads']` it works. Because `flet_proot`'s provider map is empty, its imports (`src/core/proot_probe.py:9`, `src/screens/views.py:34`) pass ONLY via the name-only fallback `mod.lower() in declared` (`flet_proot` IS declared at `pyproject.toml:52`), not via provider mapping. So the provider-mapping leg (`providers & declared`) is dead code for the flet-proot import; the test's correctness for flet_proot rests entirely on name matching.
- **Evidence:** `packages_distributions()` → `flet_proot: None`, `flet_terminal: ['flet-terminal']`, `flet_ads: ['flet-ads']`, `proot_distro: ['proot_distro']` (verified against installed venv). `_declared()` normalized set includes `flet_proot` (`pyproject.toml:52`). Test passes; `flet_proot` resolution OK solely via `mod.lower() in declared`.
- **Fix / opportunity:** Keep name-only matching as the primary mechanism (it's correct here) but document that `packages_distributions()` is unreliable for the flet family / platform-only deps, so maintainers don't "fix" it by removing the name fallback. Alternatively, treat platform-table deps as declared-by-name explicitly.
- **Risk if ignored:** A maintainer removing the `mod.lower() in declared` fallback (trusting providers) would falsely flag `flet_proot` imports as missing — or worse, trust an empty provider map and miss a real undeclared flet-family import.

### F3 · P2 · Name-only checking is correct here by coincidence, not by design
- **Where:** `tests/test_imports_vs_deps.py:56-57` (`mod.lower() not in declared`) and provider check at `:56`.
- **What:** The test resolves imports purely by comparing the top-level import name (lowercased, hyphens→underscores) against declared dependency names. This works for the current set because every module name happens to match its dist name modulo case/hyphen (`flet`↔`flet`, `httpx`↔`httpx`, `proot_distro`↔`proot-distro`, `flet_proot`↔`flet-proot`, `flet_terminal`↔`flet-terminal`, `flet_ads`↔`flet-ads`). It is not robust to a package whose top-level module differs substantially from its dist name (classic examples: `import yaml` from `PyYAML`, `import PIL` from `pillow`, `import bs4` from `beautifulsoup4`). None are imported in `src/` today, so no live bug — but the check is "name-only" with no provider cross-check as a backstop for those cases.
- **Evidence:** All imports resolve OK via name match (resolution table in analysis; test passes 1/1). `packages_distributions()` is present but only used as an OR-clause (`providers & declared`), never as the sole authority.
- **Fix / opportunity:** Combine name matching with `packages_distributions()` provider lookup (canonicalized both sides) so a dist-to-module mismatch is caught in either direction. Requires `packaging` canonicalization (see F1).
- **Risk if ignored:** A future dependency with a non-obvious module/dist name split could be imported undeclared and pass the guard → crash on Android (the exact M0 the guard exists to prevent).

### F4 · P3 · `markupsafe` "false negative in dev-only guard" claim — UNVERIFIED, not supported by evidence
- **Where:** `tests/test_proot_surfaces.py:133-148` (`test_dev_only_packages_are_not_imported_from_src`, dev-only set) vs `.venv` (markupsafe installed).
- **What:** The prompt suggests `markupsafe` may be a false negative — missing from the dev-only guard while being importable/dev-only. Evidence: `markupsafe==3.0.4` IS installed (`.venv/lib/python3.14/site-packages/markupsafe-3.0.4.dist-info/`) but `markupsafe` is NOT imported anywhere in `src/` (grep over `src/` → no matches) and NOT in `pyproject.toml`. Since it is not imported, it is not a false negative of either guard; it is simply an unimported transitive dep (of `jinja2`, which IS in the dev-only set at `test_proot_surfaces.py:143`). The claim that markupsafe is "missing from the dev-only guard" is UNVERIFIED — no evidence it is imported or should be guarded.
- **Evidence:** `tests/test_proot_surfaces.py:135-145` (dev_only set lacks markupsafe, but jinja2 is present); `grep -rn "markupsafe\|jinja2" src/` → no matches in src; `markupsafe` not in `pyproject.toml`.
- **Fix / opportunity:** None required. If markupsafe were ever imported in `src/`, both `test_imports_vs_deps.py` (it's not a declared runtime dep) and `test_dev_only_packages_are_not_imported_from_src` (it's not in dev_only) would need updating — but that's speculative.
- **Risk if ignored:** None today. Label UNVERIFIED per house rule.

## Verified-good list
- All 22 third-party imports across `src/` resolve to a declared dependency (flet×15, flet_ads×2, flet_terminal×1, flet_proot×2, proot_distro×1, httpx×1) — test passes 1/1 (`.venv/bin/python3 -m pytest tests/test_imports_vs_deps.py` → 1 passed in 0.71s).
- `pyproject.toml` declared set: `flet`, `flet_ads`, `flet_proot`, `flet_terminal`, `httpx`, `proot_distro` (normalized) — covers every third-party import in `src/`.
- `_imports()` correctly handles `import X` and `from X import Y` (`ast.Import` / `ast.ImportFrom`, level 0), skips stdlib (`tomllib`, `ast`, `pathlib`, `sys`) and local packages (`src/` dirs/stems).
- `flet-terminal` and `flet-ads` provider mapping works via `packages_distributions()` (`flet-terminal`, `flet-ads`).
- `packaging==26.3` installed and importable (candidate for F1/F3 fix, already present, host-side only).

## Unverified
- Whether `flet-proot==5.1.107.98` should be installed in the dev venv or is correctly build-time-only (per `pyproject.toml:50-52` CI `PIP_FIND_LINKS` comment) — not installed; declared as android platform dep; imports pass via name fallback. UNVERIFIED.
- That `packaging`-based canonicalization would produce zero false positives/negatives against the full installed dist set — not exhaustively run; only spot-checked divergence examples. UNVERIFIED.
- Whether any `src/` file uses lowercase `ft.border.all` (docstring precision concern raised in the flet API guard audit) — out of scope for this file; UNVERIFIED.

## Missed capabilities
N/A — this is a test/guard audit, not a dependency-study; no capability-in-dependency analysis applies.
