# src/core/state.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/core/state.py` (55 lines) · consumers `src/app_controller.py`, `src/screens/views.py`, `src/screens/terminal_view.py`, `src/state/controller_ctx.py` · `docs/decisions.md` (D-015) · `.venv/lib/python3.14/site-packages/flet/components/observable.py` (Flet 1.0.4) · anyio utilization `docs/swarm/dependency-utilization/anyio.md` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/state.py` defines the single observable state object for the app: `@ft.observable class AppState` with 30+ typed fields (probe/environment, distro screen, settings, hints, onboarding, update feed, terminal sessions) and a module-level singleton `state = AppState()` (`state.py:54`). Fields are plain public attributes; `__init__` (`state.py:49-52`) only seeds `containers` and `search_results` to `[]`. Views subscribe via `ft.use_state(state)` (`src/screens/views.py:75,387`; `src/screens/terminal_view.py:63,234`), so every field assignment or in-place collection mutation triggers `_notify` and a re-render. Controllers mutate fields directly from async methods and worker threads (`src/app_controller.py:144-418`). The only Flet API used in the file is `ft.observable` (`state.py:5,8`).

---

## Findings

### F1 · P1 · Observable mutations are not thread-safe, but the app mutates `state` from worker threads

- **Where:** `src/core/state.py:8-54` (every public field is observable and notifies synchronously) · `.venv/lib/python3.14/site-packages/flet/components/observable.py:204-213` (`__setattr__` → `_notify` at `:165-175`, which calls every listener synchronously) · `.venv/.../flet/components/component.py:214-220` (`_schedule_update`) · `src/app_controller.py:144,149,154,164,184,205,212,219,236,240,279,336,351,366,378,396,406,416` (all inside `asyncio.to_thread`) · `src/screens/terminal_view.py:63` (component subscribes to the singleton).
- **What:** `Observable.__setattr__` notifies listeners on the calling thread. `AppController` assigns `state.*` from inside `asyncio.to_thread` workers (`refresh_containers`, `install_distro`, `open_session`, …), and the reader thread in `session_manager` also touches entry state. Flet's own cross-thread helpers marshal with `run_coroutine_threadsafe`/`call_soon_threadsafe` (`.venv/.../flet/controls/page.py:939,1005`); `Observable` provides no such marshaling. The anyio audit reproduces `asyncio.Event.set()` from a foreign thread raising `RuntimeError: Non-thread-safe operation invoked on an event loop other than the current one` (`.venv/.../flet/messaging/session.py:61-62,673-674`).
- **Evidence:** `observable.py:204-213` has no lock/loop handling; `app_controller.py:144` `state.containers = await asyncio.to_thread(self.proot.list_containers)` runs the assignment on the event loop after the await, but `:174` `_apply_line` is invoked via `loop.call_soon_threadsafe` and then assigns `state.install_stage = line.strip()` on the loop (correct); contrast `:408` `state.session_error = ...` which runs inside `asyncio.to_thread`'s worker. UNVERIFIED which exact assignments execute off-loop vs on-loop without tracing every await boundary.
- **Fix / opportunity:** make `AppState` mutations loop-aware (inject the page loop and marshal `_notify` via `call_soon_threadsafe`), or move all `state.*` writes to the coroutine after `await asyncio.to_thread(...)`. Minimum: audit each controller method so no `state.x =` runs inside a worker.
- **Risk if ignored:** lost re-renders, `RuntimeError` tracebacks in worker/reader threads, stale UI (anyio audit F2).

### F2 · P2 · Declared types/defaults are inconsistent: `containers` and `search_results` are typed `list` but default to `None`

- **Where:** `src/core/state.py:18` (`containers: list = None`) · `src/core/state.py:23` (`search_results: list = None`) · `src/core/state.py:49-52` (`__init__` sets both to `[]`) · consumers `src/screens/views.py:346` (`st.search_results[:12]`) and `src/screens/views.py:364-365` (`if st.containers:` / iteration).
- **What:** The class-level default is `None`, not `[]`; the list default only exists after `__init__` runs. Any `AppState()` instance constructed in a context that skips `__init__`, or any field reset to `None` (e.g. a future controller doing `state.search_results = None`), breaks `views.py:346` with `TypeError: 'NoneType' object is not subscriptable`. The type annotation also lies (`list` vs `None`).
- **Evidence:** `state.py:18,23` vs `views.py:346` `ft.Column(controls=[_hit_row(hit) for hit in st.search_results[:12]], ...)`.
- **Fix / opportunity:** declare `containers: list | None = None` and `search_results: list | None = None` (matching `update_data: dict | None` at `state.py:43` and `active_session: str | None` at `state.py:46`), and make consumers None-safe (`st.search_results or []`). Alternatively seed both to `[]` at class level via a factory; but `Observable.__setattr__` wrapping plus mutable class defaults is its own hazard. Prefer the type fix + None-safe reads.
- **Risk if ignored:** crash on any code path that instantiates/resets state without the two seeds; latent type-checker blind spot.

### F3 · P2 · Only two of ~30 fields are seeded in `__init__`; the rest rely on class-level defaults

- **Where:** `src/core/state.py:49-52` (`__init__` sets only `containers` and `search_results`) · `src/core/state.py:10-47` (all other fields declared as class attributes).
- **What:** Mixed initialization strategy: collection fields are per-instance (good), but scalar fields (`probe_passed`, `theme_mode`, …) live as mutable class attributes shared until first assignment. For an immutable-default scalar this is harmless, but it means `AppState` cannot be safely subclassed or reset without re-running the full class body, and `state = AppState()` is the only construction path. There is no reset/factory for tests, so `tests/test_ui_reactive.py:28-40` mutates the global singleton in place.
- **Evidence:** `state.py:49-52` vs `tests/test_ui_reactive.py:27-40` (mutates the shared singleton).
- **Fix / opportunity:** either seed every field in `__init__` (explicit, instance-local) or expose a `reset()`/factory. Keep the singleton for production. Low priority.
- **Risk if ignored:** test-ordering leaks and surprising shared-default semantics if a second instance is ever created.

### F4 · P3 · Nested collections assigned to a field are not wrapped at construction time

- **Where:** `.venv/lib/python3.14/site-packages/flet/components/observable.py:227-234` (`ObservableList.__init__` calls `super().__init__(iterable)` without wrapping items) and `:349-350` (`ObservableDict.__init__` same) · contrast `:262-335` (`append`/`insert`/`__setitem__` do wrap) · `src/core/state.py:18,23,43` (`containers`, `search_results`, `update_data`).
- **What:** When `state.containers = [dict, …]` is assigned, `__setattr__` wraps the outer list into an `ObservableList`, but the dicts already inside it are not converted to `ObservableDict` (wrapping only happens on later `append`/`__setitem__`). Thus in-place mutation of an element dict (`state.containers[0]["name"] = …`) does not notify and will not re-render. The app currently replaces whole lists, so this is latent.
- **Evidence:** `observable.py:227-234` (no `_wrap` in `__init__`) vs `:333-335` (`__setitem__` wraps).
- **Fix / opportunity:** document that controllers must replace collection fields rather than mutate nested elements; or wrap in `__init__` (upstream change, not ours). Keep the one-to-one wrap discipline (D-017 §10).
- **Risk if ignored:** a future in-place edit of a container row would silently fail to re-render.

### F5 · P3 · No anyio/cancellation-related fields, despite the parked cancellable-install pipeline

- **Where:** `src/core/state.py:10-47` (no cancel/token fields) · `src/app_controller.py:132-133` (`_noop_cancel` is a no-op) · `src/app_controller.py:62` (`cancel_install=self._noop_cancel`) · `docs/decisions.md` D-015 item 9 (anyio pipeline parked).
- **What:** `cancel_install` is wired into `ControllerMethods` (`src/state/controller_ctx.py:28`) but is a no-op, and there is no state field to represent a cancel request, an install task handle, or anyio scope. The dependency study confirms the app uses stdlib `asyncio.to_thread` only (no anyio import in `src/` except the license list).
- **Evidence:** `app_controller.py:132-133`; `state.py` has no `install_cancelled`/`install_task` field.
- **Fix / opportunity:** when the owner un-parks the anyio pipeline (D-015 item 9), add explicit fields (`install_cancel_requested: bool`, and ideally the task/scope handle) instead of overloading `installing`. Until then, leave as-is; do not invent cancellation.
- **Risk if ignored:** none today; cancellation remains unavailable by design.

### F6 · P3 · `theme_revision` manual re-render signal is redundant with observable subscription

- **Where:** `src/core/state.py:31` (`theme_revision: int = 0`) · `src/app_controller.py:264` (`state.theme_revision += 1`) · `src/screens/terminal_view.py:122` (`ft.use_effect(_apply_theme, [state.theme_revision])`).
- **What:** `state.theme_mode` is already observable, so components re-render on a theme flip without a separate counter. `theme_revision` exists only to force `use_effect` to re-run (effects compare dependency lists between renders). It works, but it is a second source of truth for the same event and must be bumped in every theme path (`set_theme_mode`, `_restore_prefs`); a missed bump silently leaves the terminal palette stale.
- **Evidence:** `state.py:30-31`; `app_controller.py:130` (`state.theme_revision += 1` in `_restore_prefs`) and `:264`.
- **Fix / opportunity:** key the effect on `state.theme_mode` (or `state.theme_revision` alone) and centralize the bump in `set_theme_mode` only; remove the `_restore_prefs` bump if restore calls `set_theme_mode`. Verify `ft.use_effect` dependency semantics in `.venv` (UNVERIFIED exact comparison rules).
- **Risk if ignored:** terminal theme desync if a new theme path forgets the bump.

---

## Missed capabilities (dependency audits only)

Not applicable — `state.py` is app code, not a dependency. The only dependency touch is `ft.observable` (see Verified-good). The anyio study (`docs/swarm/dependency-utilization/anyio.md`) notes the app does not import anyio at all; if/when adopted, state would need cancellation fields (F5).

---

## Verified-good list

- `@ft.observable` exists and is exported in Flet 1.0.4: `.venv/lib/python3.14/site-packages/flet/__init__.py:34-36` imports `observable` from `flet.components.observable`, and `observable.py:18` defines `def observable(cls)`. Verified by `.venv/bin/python -c "import flet; print(flet.__version__)"` → `1.0.4`.
- `Observable.__setattr__` wraps `list`/`dict` into observable collections (`observable.py:196-201`), so `state.containers = [...]` reassignment notifies subscribers; `containers`/`search_results`/`update_data` mutations propagate.
- Private-name skipping (`observable.py:205`) is not triggered by any field (none start with `_`), so all fields notify correctly.
- `__init__` runs before the singleton is published (`state.py:54`), so the two seeded lists exist for every consumer.
- Field set matches controller/view usage: every `state.*` referenced in `app_controller.py`, `views.py`, and `terminal_view.py` is declared in `state.py` (spot-checked `installing`, `install_stage`, `busy_note`, `search_status`, `search_results`, `containers`, `storage_bytes`, `cached_count`, `cache_busy`, `docker_token`, `theme_mode`, `theme_revision`, `hints_dismissed`, `apt_note_dismissed`, `terminal_fullscreen`, `onboarding_done`, `update_available`, `update_data`, `active_session`, `session_error`, `probe_passed`, `probe_summary`, `probe_running`, `data_note`).
- No imperative widget mutation in `state.py`; it is pure data, consistent with D-015.

---

## Unverified

- Exact thread identity of every `state.*` assignment in `app_controller.py` (whether it lands on the event loop or a worker) — flagged in F1; requires tracing each `await` boundary or running with `PYTHONASYNCIODEBUG=1`.
- Whether `ft.use_effect` compares dependency lists by equality or identity (affects F6) — UNVERIFIED against `.venv/lib/python3.14/site-packages/flet/components/hooks/use_effect.py`.
- Whether any test instantiates `AppState` directly (would expose F2/F3 immediately) — `grep` found only the singleton import in tests.
- Whether nested-dict non-wrapping causes a real missed re-render in the current app — latent, not exercised by tests.