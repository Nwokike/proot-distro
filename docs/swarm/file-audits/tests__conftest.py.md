# tests/conftest.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `tests/conftest.py` · all `tests/*.py` · `pyproject.toml` `[tool.pytest.ini_options]` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/conftest.py` (59 lines) declares a `FakePage` class plus two pytest fixtures (`fake_page`, `platform_windows`) intended as "a minimal page stand-in for controller-branch tests" (`tests/conftest.py:1`). No test in the tree requests either fixture or instantiates `FakePage`, and no source imports it. The module loads as a pytest plugin for the `tests/` directory but contributes nothing to any running test. The suite itself passes its collected tests (the only 2 failures are pre-existing `src/LICENSES` absences in `tests/test_ui_reactive.py:182,206`, unrelated to conftest).

## Findings

### F1 · P2 · conftest.py is entirely dead code — `FakePage`, `fake_page`, `platform_windows` are referenced nowhere
- **Where:** `tests/conftest.py:10-48` (`class FakePage`), `:51-53` (`fake_page` fixture), `:56-59` (`platform_windows` fixture)
- **What:** The whole module is a leftover harness (ported from the sherlock app per `docs/reference/app-sherlock.md:34`). `grep -rn "fake_page\|platform_windows\|FakePage" tests/ src/` returns only the definitions themselves (`tests/conftest.py:10,52,57`) — nothing consumes them. The docstring's promise of "controller-branch tests" is false: `src/app_controller.py` (327 executable lines, 0 covered) has no tests, and `AppController.__init__` needs only `page.services`, `page.render`, `page.run_task`, `page.loop` — all present on the stand-in but never exercised (`docs/swarm/dependency-utilization/pytest.md:96-97,113`).
- **Evidence:** `grep -rn "fake_page\|platform_windows\|FakePage" /home/maikel/.zcode/workspace/default/proot-distro-flet/tests/ /home/maikel/.zcode/workspace/default/proot-distro-flet/src/` → only `tests/conftest.py:10,52,57`. Sibling audits concur: `docs/swarm/dependency-utilization/iniconfig.md:144-150`, `docs/swarm/dependency-utilization/pytest.md:96-97,165-168`, `docs/swarm/dependency-utilization/pluggy.md:23`.
- **Fix / opportunity:** Either delete `tests/conftest.py` (or empty it) and remove the misleading docstring, or start using it — e.g. wire `AppController(FakePage())` + `asyncio.run` to drive install/remove/theme/probe actions as `docs/swarm/dependency-utilization/pytest.md:113,203` suggests. Do not keep a 59-line scaffold nothing uses.
- **Risk if ignored:** A new contributor reads `tests/conftest.py`, concludes "the house harness is `FakePage`", and writes tests against a page double that no other test uses and that does not model `ft.Page` (no `add`, no `session`, `show_dialog`/`pop_dialog` invented for this repo) → false coverage signal.

### F2 · P2 · `FakePage.run_task` diverges from real `ft.Page.run_task` — latent bug if ever used
- **Where:** `tests/conftest.py:36-39` vs `.venv/lib/python3.14/site-packages/flet/controls/page.py:929-964`
- **What:** Real `Page.run_task` requires a coroutine function (raises `TypeError` otherwise at `page.py:940-941`), schedules via `asyncio.run_coroutine_threadsafe(..., self.session.connection.loop)` at `page.py:943-945`, and returns a `Future`. `FakePage.run_task` calls `handler(*args, **kwargs)` synchronously (`conftest.py:39`) and returns the result. For an `async` handler it returns a never-awaited coroutine → `RuntimeWarning: coroutine ... was never awaited` at garbage collection. The pyproject `filterwarnings` rule is `error::Warning` scoped to app modules (`pyproject.toml:95-97`), but that warning is raised at GC time where the originating module is unpredictable → it may slip through the filter. UNVERIFIED whether the filter actually catches it; moot today because nothing uses `fake_page`.
- **Evidence:** `conftest.py:36-39` (sync call, returns result); `page.py:929-964` (coroutine requirement, `run_coroutine_threadsafe`, Future return); `page.py:940-941` (`TypeError` guard).
- **Fix / opportunity:** Document `FakePage.run_task` as sync-only stand-in, or make it return an awaitable so future controller tests don't hit unawaited-coroutine warnings. Only worthwhile if F1 is resolved by actually using the fixture.
- **Risk if ignored:** A future test doing `fake_page.run_task(async_handler)` leaks a coroutine and possibly a warning that escapes the warnings filter.

### F3 · P2 · `FakePage.loop` diverges from real `ft.Page.loop`
- **Where:** `tests/conftest.py:23-31` vs `.venv/lib/python3.14/site-packages/flet/controls/page.py:1334-1338`
- **What:** Real `Page.loop` returns `self.session.connection.loop` (`page.py:1337-1338`) — requires an active session/connection. `FakePage.loop` lazily does `asyncio.get_running_loop()` or `asyncio.new_event_loop()` (`conftest.py:24-30`). Semantically different: a test asserting page-loop behavior would get a freshly created loop, not the page's connection loop. `AppController.__init__` reads `page.loop` (`src/app_controller.py:39-43` per `docs/swarm/dependency-utilization/pytest.md:113`), so this divergence matters if the fixture is ever wired.
- **Evidence:** `conftest.py:23-31`; `page.py:1334-1338`.
- **Fix / opportunity:** Note the divergence in the class docstring, or align `FakePage.loop` to expose a controllable loop attribute tests can set.
- **Risk if ignored:** Wrong loop semantics in any future controller-branch test.

### F4 · P3 · `FakePage.services` is a plain list attribute, not a property backed by root-view services
- **Where:** `tests/conftest.py:14` vs `.venv/lib/python3.14/site-packages/flet/controls/base_page.py:822-832`
- **What:** Real `Page.services` is a property returning `self.__root_view().services` (`list[Service]`) with a setter (`base_page.py:822-832`). `FakePage` sets `self.services = []` as a plain instance attribute in `__init__` (`conftest.py:14`). Superficially compatible (both are lists) but `FakePage` admits arbitrary `Any` items while real `Page` expects `Service` instances; and `FakePage` has no root-view lifecycle. Minor cosmetic divergence.
- **Evidence:** `conftest.py:14`; `base_page.py:822-832`.
- **Fix / opportunity:** If the fixture is adopted, type `services` as `list[Service]` or keep it a plain list but document it as a stand-in. Low priority.
- **Risk if ignored:** None real today; type-noise only if a future test puts non-Service objects in `services`.

### F5 · P2 · posixdb shim cleanup is module-local in `test_core.py`, not shared in `conftest.py` — order-dependency risk on Windows
- **Where:** `tests/test_core.py:12-21` (`_restore_db_modules` autouse fixture) vs `tests/conftest.py` (no posixdb reference at all)
- **What:** The `sys.modules["pwd"]`/`["grp"]` save/restore fixture lives only in `test_core.py:12-21`. `grep` confirms posixdb/pwd/grp shimming occurs only in `test_core.py` (lines 28,30,41-44,55,57,66,68) — `test_proot_surfaces.py:128-130` poisons `proot_distro`, not posixdb. The sibling pytest audit (F10) flags the suite as order-dependent and recommends moving `_restore_db_modules` verbatim into `tests/conftest.py` as a session-wide autouse fixture (`docs/swarm/dependency-utilization/pytest.md:118,210`). On Windows the local loop can go red for an unrelated reason; `--ff`/xdist change the answer. Moving it is a zero-behavior-change file move and removes a cross-test leak vector.
- **Evidence:** `test_core.py:12-21`; `grep` for posixdb/pwd/grp across `tests/` → only `test_core.py`; `docs/swarm/dependency-utilization/pytest.md:118,210`.
- **Fix / opportunity:** Move `_restore_db_modules` (`tests/test_core.py:12-21`) into `tests/conftest.py` as an `autouse` fixture (session or module scope). No behavior change today since `test_core.py` is the sole consumer; future posixdb users get the restore for free.
- **Risk if ignored:** `pwd`/`grp` shims installed by one test leak into the next, causing order-dependent failures (especially on Windows where neither module exists natively, `test_core.py:32-34`).

### F6 · P3 · `filterwarnings` interplay — conftest.py is in scope but emits no warnings; the `Warning` catch-all may or may not catch `FakePage.run_task` RuntimeWarning
- **Where:** `pyproject.toml:95-97` vs `tests/conftest.py` and `page.py:929-964`
- **What:** `filterwarnings = ["error::Warning:^(services|screens|components|core|state|hooks|tests)(\\.|$)"]` turns `Warning` subclasses into errors for the app packages plus `tests`. `tests/conftest.py` is under `tests/` so it matches, but the module emits no warnings itself. The interplay only bites if F2's fixture is ever used: an unawaited-coroutine `RuntimeWarning` raised at GC time may originate outside the matched modules and escape the `error::Warning` filter. The regex itself compiles cleanly (verified by running it). No test currently triggers a warnings-as-errors failure traceable to conftest.
- **Evidence:** `pyproject.toml:95-97`; `conftest.py` contains no `warnings.warn`/`assert_warns`; regex compile test OK.
- **Fix / opportunity:** If `FakePage.run_task` is adopted, either align it to return an awaitable (fixes root cause) or add `"error::RuntimeWarning"` to the filter. Defer until F1 is resolved.
- **Risk if ignored:** Latent warning-escape; no current impact.

## Missed capabilities (dependency audits only)
N/A — this is a file audit, not a dependency audit.

## Verified-good list
- `tests/conftest.py` imports cleanly and loads as a pytest plugin without collection errors (suite runs; 2 pre-existing failures unrelated to conftest).
- `FakePage.show_dialog`/`pop_dialog` roughly mirror real `BasePage.show_dialog`/`pop_dialog` (`.venv/.../flet/controls/base_page.py:402-445`).
- `FakePage.update(*_controls) -> None` signature matches real `Page.update` / `BasePage.update` (`page.py:819-832`, `base_page.py:320-332`), both return None.
- `FakePage.render(component, *args, **kwargs)` matches real `Page.render` signature (`page.py:750-755`).
- `on_disconnect`/`on_close` attributes exist on real `Page` (`page.py:670,676`) — the `FakePage.on_disconnect`/`on_close` slots (`conftest.py:19-20`) are legitimate extension points for a future `main.main()` disconnect/close regression test.
- `filterwarnings` regex compiles; no conftest-originated warnings-as-errors failures in the run.

## Unverified
- Whether `error::Warning` in `pyproject.toml:95-97` actually catches a `RuntimeWarning` from an unawaited coroutine returned by `FakePage.run_task` (raised at GC time, originating module unpredictable) — moot because nothing uses `fake_page` (F2).
- `docs/reference/app-sherlock.md:34` claims the sherlock layout has `tests/flet_tree.py` and `src/hooks/`; neither exists here — the copied harness was never needed. Not re-verified beyond the grep showing `FakePage`/`flet_tree` references are doc-only.
- Sibling audit `docs/swarm/dependency-utilization/pytest.md:113` claims `AppController.__init__` (`src/app_controller.py:39-43`) needs only `page.services`/`render`/`run_task`/`loop` — I did not re-read `app_controller.py` to confirm; taken from the sibling audit.
