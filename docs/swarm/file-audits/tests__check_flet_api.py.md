# tests/check_flet_api.py — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `tests/check_flet_api.py` (guard) · `tests/test_flet_api_guard.py` (suite driver) · `pyproject.toml` (deps/pytest config) · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · all `src/**/*.py` · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/check_flet_api.py` is a static AST namespace guard. It parses a target Python file, walks every `ast.Attribute`, flattens chains whose root is the bare name `ft` (e.g. `ft.Border.all` → `("Border","all")`), and verifies each member-by-member against the INSTALLED `flet` package via `hasattr`/`getattr` starting from `import flet`. A missing link is reported `MISSING` and the guard exits 1. A `RuntimeError` mid-chain (e.g. `ft.context.page` outside a running app) is accepted as `runtime_bound` and the prefix is verified. `tests/test_flet_api_guard.py` runs the guard in-process over every `src/*.py` file (re-loading the guard module per target via `importlib`), failing the suite if any file reports missing chains. The app imports flet exclusively as `import flet as ft` in 20 modules; the guard's entire surface is `ft.*` attribute chains. There are 265 distinct `ft.*` chains across `src/` (verified by running the guard's own `chains()` over every source file). All pass against flet 1.0.4; the suite passes (2 passed in 2.88s).

## Findings

### F1 · P2 · Coverage gap: bare `from flet import X` names are invisible to the guard — false negatives
- **Where:** `tests/check_flet_api.py:39-47` (`_flatten` requires root `ast.Name` with `id == "ft"`) · `src/components/banner_ad.py:14` (`from flet import Control`) · `src/core/shared_services.py:71` (`from flet import context`)
- **What:** `_flatten` only records chains rooted at `ast.Name(id="ft")`. Bare-name imports produce `ast.Name(id="Control")` / `ast.Name(id="context")`, never `ast.Attribute` rooted at `ft`, so they are never collected and never verified. `banner_ad.py:24` uses `Control` as a type annotation (`_BANNER_POOL: dict[str, Control]`) and `shared_services.py:73` calls `context.page`; if `Control` were renamed/removed in flet, or `context` relocated, the guard would say OK and the app would crash at import/runtime. This is a false negative.
- **Evidence:** `banner_ad.py:14` `from flet import Control`; `shared_services.py:71` `from flet import context` (inside `_current_page`); `_flatten` at `check_flet_api.py:39-47` has no branch for `ast.Name` roots other than `"ft"`. Confirmed by running the guard over `banner_ad.py` and `shared_services.py` — both exit 0 with no `Control`/`context` chain reported (`tests/check_flet_api.py` output never lists them).
- **Fix / opportunity:** Extend `chains()` to also harvest bare names imported from `flet` (scan `ast.ImportFrom` with `module == "flet"` and `ast.Import` with `import flet as ft`), then verify each against `getattr(flet, name)`. Minimal, architecture-respecting, no new dependency.
- **Risk if ignored:** A renamed/removed bare-imported flet symbol slips past the guard and crashes on device — exactly the M0 class the guard was built to prevent (ElevatedButton / border.all precedent, `check_flet_api.py:5-9`).

### F2 · P2 · Docstring conflates `ft.border` (module) with `ft.Border` (class) — imprecise, not a live bug
- **Where:** `tests/check_flet_api.py:6-9` (docstring) vs `.venv/lib/python3.14/site-packages/flet/controls/border.py:173,203-204` and `flet/__init__.py:1783,1328`
- **What:** The docstring claims "`ft.border.all()` (helper removed; use `ft.Border()`/`ft.BorderSide()`)". That is only half-true: `ft.border` is the `border` *module* (flet/__init__.py:1783 maps `"border"` → `flet.controls`), and `ft.border.all` does NOT exist (module has no `all` attribute — confirmed MISSING at runtime). But `ft.Border.all` *does* exist as a classmethod (`border.py:203-204`, `Border` mapped at `__init__.py:1328`) and every app call site uses capital-`B`: `app_header.py:67`, `banner_ad.py:86`, `ui.py:75`, `styles.py` — all `ft.Border.all(...)`, all verified EXISTS. So the app is correct; the docstring's wording is imprecise and could mislead a maintainer into "fixing" working call sites to `ft.Border(...)`. UNVERIFIED whether any call site actually uses lowercase `ft.border.all` (grep shows none).
- **Evidence:** `check_flet_api.py:6-9`; runtime check `ft.border.all` → AttributeError `module 'flet.controls.border' has no attribute 'all'`; `ft.Border.all` → bound method (border.py:204); app call sites `app_header.py:67`, `banner_ad.py:86`, `ui.py:75` all use `ft.Border.all`.
- **Fix / opportunity:** Reword the docstring to say "the `ft.border` module has no `all` helper; use `ft.Border.all()`/`ft.BorderSide()` (capital B)". No code change required.
- **Risk if ignored:** Maintainer confusion; possible spurious "fixes" of correct `ft.Border.all` call sites. No user impact today.

### F3 · P1 (latent) · `ft.ElevatedButton` is genuinely missing in flet 1.0.4 — guard correctly detects it, but it is unused in src; historical M0 already fixed
- **Where:** `tests/check_flet_api.py:6-7` (docstring cites it as a caught M0 bug) vs `flet/__init__.py` (no `ElevatedButton` in `_LAZY` or `__all__`) and the full `src/` chain enumeration
- **What:** `ft.ElevatedButton` does not exist in flet 1.0.4 (confirmed MISSING via `getattr(flet, 'ElevatedButton')` → AttributeError). The guard correctly flags it. However `grep` over `src/` shows zero usages of `ft.ElevatedButton` — it was already removed from the app (the historical M0 crash referenced in the docstring is fixed). This is not a live defect; it is evidence the guard works as designed.
- **Evidence:** `check_flet_api.py:6-7`; runtime `ft.ElevatedButton` → MISSING; `grep -rn "ElevatedButton" src/` → no matches.
- **Fix / opportunity:** None needed. Keep the docstring's historical note but it should not be read as an active bug in the tree.
- **Risk if ignored:** None — guard already protects against reintroduction.

### F4 · P2 · The `RuntimeError` mid-chain branch is fragile / partially dead code — `hasattr` swallows `RuntimeError`
- **Where:** `tests/check_flet_api.py:66-79` (main loop) · `flet/controls/context.py` (source of `ft.context.page` RuntimeError)
- **What:** The loop does `if not hasattr(obj, part): ... missing ... break` then `obj = getattr(obj, part)` inside `try/except RuntimeError`. `hasattr()` swallows *all* exceptions (including `RuntimeError`) and returns `False`, so the only way the `except RuntimeError` branch fires is if `hasattr` returned `True` but the immediate `getattr` raises `RuntimeError` — a descriptor/property race that is unusual. Empirically `ft.context.page` IS accepted as `runtime_bound` (running the walk shows `getattr(context,'page')` raises `RuntimeError` after `hasattr(context,'page')` returned `True` — UNVERIFIED why `hasattr` doesn't swallow it here; possibly `Context` defines `page` such that `hasattr` probes differently). Because `hasattr` normally swallows `RuntimeError`, a future flet change that makes `getattr(context,'page')` raise `RuntimeError` *during* the `hasattr` probe would flip this chain from `ok*` to `MISSING` (false positive) — or conversely a typo like `ft.context.pge` raises `AttributeError` (not RuntimeError) and is correctly MISSING. The branch is under-tested: no test exercises `ft.context.page` through the guard's runtime-bound path.
- **Evidence:** `check_flet_api.py:66-79`; `tests/test_flet_api_guard.py` asserts only exit code 0, never the `ok*`/`runtime_bound` branch. Runtime demonstration: `ft.context.page` → `ok*` (accepted); the guard output marks it `ok*  (runtime-context)` at `check_flet_api.py:87`.
- **Fix / opportunity:** Add an explicit test (or at least a `# noqa`-free assertion in `test_flet_api_guard.py` or a scratch file) that `ft.context.page` is reported `runtime_bound`/accepted, and document that `hasattr` swallowing `RuntimeError` makes the `except RuntimeError` branch reachable only in the narrow descriptor case. Consider replacing `hasattr` with a try/except around `getattr` for clarity and correctness.
- **Risk if ignored:** The runtime-bound acceptance of `ft.context.page` is untested; a flet internals change could silently turn it into a hard FAIL (false positive) or, worse, a typo could be accepted. Low probability, moderate impact.

### F5 · P2 · Event-handler signatures, enum *string* values, and kwargs are not validated — false negatives
- **Where:** `tests/check_flet_api.py:24-50` (only attribute chains; ignores call arguments) · app call sites e.g. `ui.py:64` `ft.TextButton("Got it", on_click=on_dismiss)`, `app_header.py:122` `scroll=ft.ScrollMode.AUTO`
- **What:** The guard verifies `ft.*` *names exist* but never checks: (a) event-handler callable signatures (`on_click`, `on_change`, etc. — plain Python callables, not `ft.*`, so invisible); (b) whether a string passed where an flet enum is expected is a valid enum member (e.g. `scroll="auto"` vs `ft.ScrollMode.AUTO` — the string is a literal, not an `ft.*` chain, so unchecked); (c) constructor kwargs whose *values* are non-`ft` literals that must match flet's accepted domain (e.g. `ft.TextButton` `style`, `ButtonStyle` fields). These are false negatives: a wrong `on_click` signature or an invalid enum string crashes at runtime but the guard passes.
- **Evidence:** `check_flet_api.py:24-50` has no handling of `ast.Call`/kwargs; `ui.py:64` passes `on_click=on_dismiss` (a local function, unchecked); `app_header.py:122` uses `ft.ScrollMode.AUTO` (verified EXISTS, but a string `"auto"` would be unchecked). Flet 1.0.4 `ControlEvent`/`Button` signatures at `flet/controls/control_event.py` and `flet/controls/buttons.py` are not consulted by the guard.
- **Fix / opportunity:** Out of scope for a pure namespace guard (would require signature/type checking). Document as a known limitation; the guard's purpose (catch renamed/removed controls) is served. Do not expand scope without a house decision.
- **Risk if ignored:** Runtime crashes from bad event signatures / invalid enum strings that the guard cannot catch by design. Accepted trade-off.

### F6 · P3 · Execution cost is modest but the test re-loads the guard module per file
- **Where:** `tests/test_flet_api_guard.py:30-45` (`importlib.util.spec_from_file_location` + `exec_module` per target) · `tests/check_flet_api.py:59` (`import flet` inside `main()`)
- **What:** Running the guard directly over all 32 src files takes ~1.8s (cold, includes `import flet` once per process but re-exec'd per call). Under pytest, `test_every_source_file_passes_the_api_guard` re-loads the guard module for *each* of the 32 files via `exec_module`; `import flet` is served from `sys.modules` cache so the cost is AST-parse + chain-walk per file. Measured suite run: 2 tests passed in 2.88s. Cost is acceptable today; scales linearly with src file count. UNVERIFIED under cold-cache CI with a much larger src tree, but 32 files × ~2ms is trivial.
- **Evidence:** Direct timing run over 32 files: 1815.2 ms total (~57 ms/file including interpreter/import overhead). `pytest tests/test_flet_api_guard.py` → 2 passed in 2.88s. `test_flet_api_guard.py:39-42` loops `_src_files()` re-loading guard per target.
- **Fix / opportunity:** None required. If src grows beyond ~100 files, consider loading the guard module once and calling `main()` per target (currently `sys.argv` is mutated per target, which is already a workaround for `main()` reading `sys.argv`).
- **Risk if ignored:** None today.

## Verified-good list
- All 265 distinct `ft.*` chains across `src/` exist in flet 1.0.4 (enumerated by running `check_flet_api.chains()` over every `src/*.py`; each verified via `getattr` against installed flet). No active missing-chain bug in the tree.
- `ft.Border.all` EXISTS (`border.py:203-204`); all four app call sites use capital-`B` correctly (`app_header.py:67`, `banner_ad.py:86`, `ui.py:75`, `styles.py`).
- `ft.Colors.with_opacity` EXISTS (`colors.py:110` staticmethod); `ft.Padding.symmetric`, `ft.Padding.only`, `ft.Alignment.CENTER`, `ft.FontWeight.BOLD/W_400/W_600`, `ft.ScrollMode.AUTO`, `ft.MainAxisAlignment.*`, `ft.CrossAxisAlignment.*`, `ft.TextAlign.CENTER`, `ft.BoxFit.CONTAIN`, `ft.Brightness.LIGHT`, `ft.MarkdownExtensionSet.GITHUB_WEB`, all `ft.Icons.*` members used in app — all verified EXISTS against installed flet.
- `ft.context.page` accepted as `runtime_bound` (RuntimeError path works empirically).
- `tests/test_flet_api_guard.py` passes (2 passed in 2.88s); guard exits 0 on every src file.
- `pyproject.toml` deps: `flet>=1.0.4` installed as exactly 1.0.4 (`flet/version.py:23` `flet_version = "1.0.4"`); dev deps `pytest>=9.1.1`, `pytest-timeout>=2.4.0` installed.

## Unverified
- Why `hasattr(context, 'page')` returns `True` while the immediate `getattr(context, 'page')` raises `RuntimeError` (F4) — descriptor-level behavior of `flet.controls.context.Context.page` not traced; accepted empirically but not proven.
- Whether `ft.border.all` (lowercase) is used anywhere in `src/` — grep found none, but not proven beyond `grep -rn "ft.border" src`.
- Cold-cache CI execution cost at scale (F6) — measured only on this 32-file tree.
- That `error::Warning` in `pyproject.toml:95-97` would or would not catch a runtime warning from an invalid enum/event — out of scope; labeled UNVERIFIED per house rule.
