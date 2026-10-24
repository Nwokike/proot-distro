# src/state/controller_ctx.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/state/controller_ctx.py` · `src/app_controller.py` · `src/core/state.py` · `src/screens/views.py` · `src/screens/terminal_view.py` · `src/screens/onboarding_view.py` · `docs/decisions.md` · `.venv/lib/python3.14/site-packages/flet/components/hooks/use_context.py` · `.venv/lib/python3.14/site-packages/flet/controls/page.py` · `.venv/lib/python3.14/site-packages/flet/components/component.py` · `.venv/lib/python3.14/site-packages/flet/controls/material/snack_bar.py` · `.venv/lib/python3.14/site-packages/flet/controls/base_page.py`
**Date:** 2026-10-24

## What it does / how the app uses it

`controller_ctx.py` defines two things and nothing else:

1. `ControllerMethods` — a `@dataclass` of typed callable fields, one per controller action, with no-op defaults so any component can call a method safely during the first render before `AppController.init()` has run.
2. `ControllerMethodsCtx` — a `ContextProvider[ControllerMethods]` created by `ft.create_context(ControllerMethods())`.

`AppController.init()` (`src/app_controller.py:59-85`) constructs a fully-populated `ControllerMethods` instance and injects it by calling `self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))`. Every `@ft.component` view then reads the methods via `ft.use_context(ControllerMethodsCtx)`.

---

## Findings

### F1 · P2 · `show_snack` no-op default cannot satisfy its own type annotation

- **Where:** `src/state/controller_ctx.py:42` (default), `src/state/controller_ctx.py:15-16` (`_noop` body)
- **What:** The field is declared `show_snack: Callable[[str], None] = field(default=_noop)`. `_noop` is defined as `def _noop() -> None` — zero positional parameters. Any caller that invokes the default with the required `str` argument (which is what the `Callable[[str], None]` contract mandates) receives `TypeError: _noop() takes 0 positional arguments but 1 was given`.

  The contrast is `_noop_async`, which correctly accepts variadic args (`*_args, **_kwargs`, `src/state/controller_ctx.py:19`) and is used for every other field.

- **Evidence:**
  ```
  $ python3 -c "
  def _noop(): return None
  _noop('test')
  "
  TypeError: _noop() takes 0 positional arguments but 1 was given
  ```
  `_noop_async` definition at `src/state/controller_ctx.py:19`: `async def _noop_async(*_args, **_kwargs) -> None`.

- **Current blast radius:** Zero. `show_snack` is never called via `methods.show_snack(str)` in any view (`grep -rn "methods\.show_snack"` returns no results in `src/`). The only callers are `AppController` methods calling `self.show_snack(...)` directly. The broken default is reached only if a component calls `methods.show_snack(msg)` while the bare `ControllerMethods()` default context is active (i.e. outside the provider — normally impossible in the running app).

- **Fix / opportunity:** Either change the default to `_noop_async` (signature matches `Callable[[str], Awaitable[None]]` — but the declared type is sync `None`, so `_noop_async` would also be a type mismatch), **or** introduce a `_noop_str(*_args, **_kwargs) -> None` helper (or simply inline `lambda *_: None`). The cleanest minimal fix consistent with the existing pattern is:
  ```python
  show_snack: Callable[[str], None] = field(default=lambda *_: None)
  ```
  This satisfies the declared type and survives any call arity.

- **Risk if ignored:** Silent latent crash if any future view invokes `methods.show_snack(msg)` (e.g. an inline snack from a dialog action). The type annotation gives false confidence that the default is safe to call.

---

### F2 · P3 · `refresh_containers` is the only field without `field(default=…)` wrapper

- **Where:** `src/state/controller_ctx.py:26`
- **What:** All 22 other callable fields use `field(default=<callable>)`; `refresh_containers` uses the bare assignment `= _noop_async`. This is valid Python — functions are immutable so the dataclass machinery does not raise — but it is an inconsistency that could confuse future editors (bare defaults must precede `field()` defaults by dataclass ordering rules; this one happens to be first so no ordering bug exists today, but the rule is easy to violate when adding fields above it).
- **Evidence:** `src/state/controller_ctx.py:26` vs all of lines 27-58 using `field(default=…)`. Verified correct by:
  ```
  python3 -c "
  from dataclasses import dataclass, field
  from collections.abc import Callable
  async def f(*a, **k): pass
  @dataclass
  class T:
      a: Callable = f           # bare
      b: Callable = field(default=f)  # wrapped
  T()  # no error
  "
  ```
- **Fix / opportunity:** Wrap `refresh_containers` in `field(default=_noop_async)` for consistency. One-character change, zero runtime impact.
- **Risk if ignored:** If a field is ever inserted above `refresh_containers` using `field()`, the ordering constraint still holds (a bare default may not follow a `field()` default that has no `default_factory`). The current position as first field means no ordering problem today.

---

## Verified-good list

- **`ft.create_context` API:** `create_context(default_value: T) -> ContextProvider[T]` exists and is exported at `.venv/.../flet/__init__.py:20` and `.venv/.../flet/components/hooks/use_context.py:50`. The call at `src/state/controller_ctx.py:61` — `ft.create_context(ControllerMethods())` — is correct.

- **`ContextProvider.__call__` usage:** `ContextProvider.__call__(value: T, callback: Callable[[], ProviderResultT])` at `.venv/.../use_context.py:45-47`. The injection call in `app_controller.py:85` — `self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))` — resolves correctly: `page.render` calls the outer lambda (no args); the lambda calls `ControllerMethodsCtx(methods, lambda: AppShell())`, matching the `(value, callback)` signature exactly. Confirmed at `.venv/.../flet/controls/page.py:750-773` and `.venv/.../flet/components/component.py:459-474`.

- **`ft.use_context` API:** `use_context(context: ContextProvider[T]) -> T` at `.venv/.../use_context.py:84`. Used correctly in `views.py:76`, `views.py:388`, `terminal_view.py:62`, `onboarding_view.py:38`.

- **`_noop_async` variadic signature:** `async def _noop_async(*_args, **_kwargs) -> None` at `src/state/controller_ctx.py:19` correctly absorbs any call arity for all async fields.

- **`cancel_install: Callable[[], None] = field(default=_noop)`:** `_noop()` takes zero args and the declared type is `Callable[[], None]` — the arity matches. The real implementation `AppController._noop_cancel()` is also zero-arg sync (`app_controller.py:132-133`). Correct.

- **All 23 method signatures match `AppController`:** Every field's `Callable[…]` annotation matches the real method's positional parameter count and async/sync character. Verified field-by-field against `app_controller.py:141-418`.

- **`ControllerMethods` dataclass construction in `AppController.init()`:** All 23 fields are explicitly supplied (`app_controller.py:59-83`); no field relies on a default at runtime.

- **`ft.observable` and `ft.component` decorators:** `observable` at `.venv/.../flet/components/observable.py:18`, exported at `flet/__init__.py:36`. `component` at `.venv/.../flet/components/component_decorator.py`, exported at `flet/__init__.py:16`. Both used correctly in `src/core/state.py:8` and `src/screens/*.py`.

- **`page.show_dialog(ft.SnackBar(ft.Text(msg)))` in `AppController.show_snack`:** `show_dialog` at `.venv/.../flet/controls/base_page.py:402` accepts `DialogControl`; `SnackBar` extends `DialogControl` at `.venv/.../flet/controls/material/snack_bar.py:155`. `pop_dialog` at `.venv/.../base_page.py:427`. All correct.

- **Architectural compliance (D-015):** The module contains no imperative widget mutations and no page references. It is a pure data bridge — a dataclass of callables plus a context token. Consistent with D-015's "pure function of state" ruling.

- **Single upstream importer rule (D-001/D-003):** `controller_ctx.py` is imported only by `app_controller.py` (to write) and `src/screens/*.py` (to read). No circular import path.

---

## Unverified

- Whether `ControllerMethods()` default context (from `ft.create_context(ControllerMethods())`) is ever reachable at runtime. In the shipped app `AppController.init()` calls `page.render(…ControllerMethodsCtx(methods, …))` before any view renders, so the default should never be the active context value. Verifying this with a running session was not attempted (read-only audit).
