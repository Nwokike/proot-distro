# tests/test_flet_api_guard.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_flet_api_guard.py · tests/check_flet_api.py · docs/swarm/BRIEF.md · .venv/lib/python3.14/site-packages/flet/ (flet 1.0.4) · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/test_flet_api_guard.py` is the run-it-first gate: it loads `tests/check_flet_api.py` (the guard module) via `importlib.util` (tests/test_flet_api_guard.py:18-23), then runs `guard.main()` in-process against every `src/**/*.py` file (tests/test_flet_api_guard.py:34-45), failing the suite if any file references a `ft.*` chain missing from the installed flet 1.0.4. The guard itself (tests/check_flet_api.py) AST-parses each target, walks every attribute chain rooted at the name `ft` (tests/check_flet_api.py:24-50), then verifies each chain member-by-member against the live `flet` module using `hasattr`/`getattr` (tests/check_flet_api.py:66-79). Chains whose prefix hits `RuntimeError` (e.g. `ft.context.page` outside a running app) are accepted as "runtime-context" (tests/check_flet_api.py:74-79). Motivation from docstring: caught real M0 bugs `ft.ElevatedButton` (removed in Flet 1.0) and `ft.border.all()` (removed; use `ft.Border`/`ft.BorderSide`) (tests/check_flet_api.py:6-7).

## Findings

### F1 · P1 · Bare `from flet import X` names are invisible to the guard — known gap, partially present in app
- **Where:** tests/check_flet_api.py:39-46 (`_flatten` only accepts chains rooted at `ast.Name` with `id == "ft"`); tests/test_flet_api_guard.py:30-45 (drives guard over src); banner_ad.py:14 (`from flet import Control`); shared_services.py:71 (`from flet import context`)
- **What:** The guard only audits dotted `ft.*` attribute chains. A bare `from flet import X` binds `X` directly; usage `X(...)` produces no `ft`-rooted Attribute chain, so a removed/renamed symbol (e.g. `from flet import ElevatedButton`) would never be flagged. This is the acknowledged blind spot named in the task and in BRIEF.md rule 3.
- **Evidence:** grep confirms no bare `from flet import <removed-symbol>` exists app-wide; the only bare imports are `from flet import Control` (banner_ad.py:14) and `from flet import context` (shared_services.py:71), both of which are valid in flet 1.0.4 (`Control` and `context` exist). `_flatten` at tests/check_flet_api.py:39-47 returns `None` for any chain whose root is not `ast.Name(id="ft")`, so `Control(...)` / `context.page` are invisible.
- **Fix / opportunity:** Extend `_flatten`/chain collection to also resolve names imported via `from flet import X` (track import aliases in a symbol table), OR add a lint rule rejecting bare `from flet import` in favor of `import flet as ft`. Minimal and architecture-respecting: keep `import flet as ft` as the single import style.
- **Risk if ignored:** A future contributor adds `from flet import SomeRemovedControl` and uses it; the guard passes silently and the APK crashes on device (the exact M0 failure mode the guard exists to prevent).

### F2 · P2 · `hasattr()` propagates `RuntimeError` in Python 3.14.9 — guard survives by accident, not by design
- **Where:** tests/check_flet_api.py:66-79 (the `try/except RuntimeError` wraps both `hasattr` and `getattr`); flet/controls/context.py:64 (property raises `RuntimeError` outside app)
- **What:** In CPython 3.14.9, `hasattr(obj, prop)` re-raises any exception other than `AttributeError` raised by a property getter (verified: a `ValueError`-raising property propagates through `hasattr`). `ft.context.page` is such a property — `hasattr(flet.context, 'page')` raises `RuntimeError` (confirmed by direct run). The guard catches it via its broad `except RuntimeError` (tests/check_flet_api.py:74) and marks the chain `runtime_bound`, so it is accepted. This is correct behavior for `ft.context.page`, but the guard would equally swallow a genuine `RuntimeError` raised by any other property getter (false negative).
- **Evidence:** Direct run against installed flet 1.0.4: `hasattr(flet.context, 'page')` → `RuntimeError: The context is not associated with any page.`; the test suite passes (2 passed). The app uses `ft.context.page` in 9 locations: banner_ad.py:46, app_shell.py:43, shared_services.py:73, theme.py:38, terminal_view.py:61/236, views.py:77/389, onboarding_view.py:39.
- **Fix / opportunity:** Distinguish `AttributeError` (truly missing) from other exceptions (genuine runtime error) — catch `AttributeError` only for "missing", and treat other exceptions as hard failures or require an explicit runtime-context allowlist. Current broad `except RuntimeError` is too permissive.
- **Risk if ignored:** A bogus chain like `ft.nonexistent.runtime_thing` whose first attribute happens to raise `RuntimeError` would be silently accepted as runtime-context.

### F3 · P3 · No subprocess — guard runs in-process; interpreter handling implicit
- **Where:** tests/check_flet_api.py:59 (`import flet` inside `main()`); tests/test_flet_api_guard.py:36-44 (manipulates `sys.argv` and calls `guard.main()` in-process)
- **What:** There is no subprocess; the guard imports the installed flet directly into the test interpreter (Python 3.14.9, flet 1.0.4). `sys.argv` is overwritten per target and restored in a `finally` (tests/test_flet_api_guard.py:36,44). No isolation between targets: a `sys.exit` or module-level side effect in `guard.main()` would kill the whole test process — `main()` never calls `sys.exit` (only `return`), verified by reading tests/check_flet_api.py:53-100. UNVERIFIED: behavior if flet is not importable in the test interpreter (would raise `ModuleNotFoundError` inside `main()`, uncaught → pytest error, not a clean guard failure).
- **Evidence:** tests/check_flet_api.py:54-61 parses target and imports flet with no try/except around the import.
- **Fix / opportunity:** Wrap `import flet` in `main()` so a missing flet yields a clean exit code 2 rather than a traceback.
- **Risk if ignored:** CI environment without flet installed produces an error trace instead of a clear "guard cannot run" signal.

### F4 · P3 · Assertion quality is thin on coverage semantics
- **Where:** tests/test_flet_api_guard.py:30-31 (`test_guard_covers_every_source_file` only asserts src files exist); tests/test_flet_api_guard.py:34-45 (asserts all targets pass guard)
- **What:** `test_guard_covers_every_source_file` does not assert the guard actually audits anything meaningful — it only checks `_src_files()` is non-empty. If `SRC` were empty or mispointed, the second test would vacuously pass (`failures` empty → `assert not failures` passes). There is no test injecting a known-bad `ft.*` chain to confirm the guard returns non-zero (no mutation/negative test). UNVERIFIED: guard's ability to catch a real regression introduced into src.
- **Evidence:** tests/test_flet_api_guard.py:30-31 reads exactly: `assert _src_files(), "no src files found — the guard would silently cover nothing"`.
- **Fix / opportunity:** Add a negative test: create a temp src file referencing `ft.ElevatedButton` (confirmed absent: `hasattr(flet, 'ElevatedButton') is False`) and assert `guard.main() != 0`.
- **Risk if ignored:** Silent coverage collapse goes undetected.

## Missed capabilities (dependency audits only)
N/A — this is a test/guard audit, not a dependency audit.

## Verified-good list
- `tests/test_flet_api_guard.py` and `tests/check_flet_api.py` both exist and are internally consistent (guard path derived from test file location: tests/test_flet_api_guard.py:14).
- Both tests pass under `pytest` (2 passed, flet 1.0.4, Python 3.14.9).
- Every `ft.*` chain actually used in `src/` resolves in installed flet 1.0.4 (verified member-by-member: ThemeMode, Page, FilePicker, SnackBar, Text, Container, Column, Row, CrossAxisAlignment, MainAxisAlignment, NavigationBar, NavigationBarDestination, IconButton, Icon, TextAlign, FontWeight, Padding, BoxFit, Colors, Border, BorderSide, BorderSideStrokeAlign, HapticFeedback, Clipboard, Share, UrlLauncher, SharedPreferences, Connectivity, run, use_state, observable, component — all `True`).
- `ft.Border.all` exists and works (`True`); `ft.border.all` does NOT (`False`) — matching the docstring's M0 example (tests/check_flet_api.py:6-7).
- `ft.ElevatedButton` does NOT exist (`False`) — consistent with the docstring's claim it was removed.
- `ft.context.page` raises `RuntimeError` outside an app; the guard's `except RuntimeError` correctly accepts those chains as runtime-context.
- All app imports use `import flet as ft`; the only bare `from flet import` are `Control` (banner_ad.py:14) and `context` (shared_services.py:71), both valid.

## Unverified
- Whether the guard catches a real regression injected into `src/` (no negative/mutation test exists) — label UNVERIFIED.
- Behavior when flet is not importable in the test interpreter (uncaught `ModuleNotFoundError` inside `main()`) — label UNVERIFIED.
- Whether a broad `except RuntimeError` could swallow a genuine `RuntimeError` from a non-context property getter and falsely accept it — plausible but not demonstrated in app code; label UNVERIFIED.
- The claim that `from flet import X` bare usage would crash on device — inferred from the known M0 precedent, not reproduced; label UNVERIFIED.
