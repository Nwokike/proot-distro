# src/app_controller.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/app_controller.py` (419 lines) · `src/state/controller_ctx.py` · `src/services/ad_service.py` · `src/services/session_manager.py` · `src/services/proot_service.py` · `src/core/shared_services.py` · `tests/conftest.py` · `tests/test_proot_surfaces.py` · `tests/test_ads.py` · `tests/test_sessions.py` · `tests/test_terminal_wiring.py` · `tests/test_ui_reactive.py` · `docs/decisions.md` (D-015, D-017) · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/app_controller.py` defines `AppController`, the single owner of the app's services (`proot_service` facade, `SessionManager`, `AdService`) and every user action. `init()` bootstraps the env probe, mounts services, builds/install themes, restores prefs/onboarding, publishes a `ControllerMethods` bundle into `ControllerMethodsCtx`, schedules background update + consent/preload tasks, and renders `AppShell`. All controller methods are async and mutate the `@ft.observable` `core.state.state` (or call services) instead of widgets (D-015). `show_snack` is the only sync method and is the sole snack-bar surface.

---

## Findings

### F1 · P1 · Install cancellation is a no-op despite a wired `cancel_install` slot
- **Where:** `src/app_controller.py:62` (`cancel_install=self._noop_cancel`) and `:132-133` (`def _noop_cancel(self) -> None: return None`); `src/state/controller_ctx.py:28` (`cancel_install: Callable[[], None]`)
- **What:** D-015 defers the cancellable install pipeline, and the controller exposes `cancel_install` only as `_noop_cancel`. No UI calls it (grep shows zero callers outside wiring), so a long-running pull cannot be cancelled; the button is effectively dead.
- **Evidence:** `grep -rn "cancel_install" src/ tests/` returns only `src/app_controller.py:62` and the context default.
- **Fix / opportunity:** Either implement cancellation (token/`asyncio.Task` tracked in `install_distro`, cancelled in `cancel_install`) or remove the slot and the UI affordance; do not ship a no-op wired as a capability.
- **Risk if ignored:** Users cannot abort a hung/long pull; perceived hang with no escape.

### F2 · P1 · `backup_container` calls `FilePicker.save_file` without `src_bytes`, which raises on mobile
- **Where:** `src/app_controller.py:346-348` (`target = await self.file_picker.save_file(dialog_title=..., file_name=...)`); `.venv/lib/python3.14/site-packages/flet/controls/services/file_picker.py:278-293`
- **What:** Flet 1.0.4's `save_file` requires `src_bytes` on web/mobile: `if (self.page.web or self.page.platform.is_mobile()) and not src_bytes: raise ValueError(...)`. The app targets Android (D-017), so invoking backup on-device raises `ValueError` inside the controller coroutine; the exception is not caught and no snack is shown.
- **Evidence:** file_picker.py:288-293 quoted above.
- **Fix / opportunity:** Generate the archive bytes in-memory or to a temp path first, then call `save_file(..., src_bytes=...)`; or restrict backup to desktop and surface "not supported on this platform".
- **Risk if ignored:** Backup action crashes the background task on Android; user sees nothing (or an unhandled-task exception).

### F3 · P2 · Inconsistent exception handling across container actions
- **Where:** `src/app_controller.py:204-215` (`remove_container`, `reset_container`), `:332-400` (`rename_container`, `backup_container`, `restore_container`, `copy_path`, `list_sessions`, `kill_session`, `close_session`); contrast `:141-160` (`refresh_containers`) and `:216-229` (`search_distro`) which catch.
- **What:** Most actions do `outcome = await asyncio.to_thread(self.proot.<x>, ...)` and immediately read `outcome.ok` without guarding. `_run_command` catches most upstream failures into `Outcome(ok=False)`, but `bootstrap()`/import can raise `ProotUnavailable` (proot_service.py:78-81) and `session_manager`/`proot.active_sessions` can raise; an unhandled exception in a `run_task`-scheduled coroutine surfaces only via the done-callback and never reaches the UI.
- **Evidence:** proot_service.py:73-90 (`_run_command` raises `ProotUnavailable` on import failure before the try).
- **Fix / opportunity:** Wrap each action body in try/except and call `self.show_snack(f"{action} failed: {_reason(exc)}")` (mirroring `refresh_containers`/`search_distro`), so failures are user-visible.
- **Risk if ignored:** Silent task failures; inconsistent UX between actions.

### F4 · P2 · `restore_container` dereferences `picked[0].path` without a None/empty guard for mobile
- **Where:** `src/app_controller.py:360-365` (`picked = await self.file_picker.pick_files(...)`; `path = picked[0].path`)
- **What:** On Android/iOS, `FilePickerFile.path` may be `None` (bytes are delivered via `with_data=True`). The code assumes a filesystem path and passes it to `proot.restore_container`, which expects a host path. `picked[0].path` can also be `None` on cancel edge cases.
- **Evidence:** file_picker.py pick_files returns `FilePickerFile(**...)`; mobile flows typically need `with_data=True`. UNVERIFIED on device.
- **Fix / opportunity:** Use `with_data=True` and write bytes to a temp file, or guard `if not path: show_snack(...); return`.
- **Risk if ignored:** Restore fails on mobile with an unhandled `TypeError`/`None` path.

### F5 · P2 · `close_session` and `open_session` concurrency/state ordering
- **Where:** `src/app_controller.py:403-419` (`open_session`, `leave_session`, `close_session`)
- **What:** `open_session` sets `state.active_session = container` only after `session_manager.open` succeeds, but `close_session` mutates `state.active_session` without awaiting UI refresh; concurrent calls (tab switch + close) can leave `active_session` pointing at a closed container. `session_manager.close` is called in a worker thread while `state` is read/written on the event loop.
- **Evidence:** `src/services/session_manager.py:62-86` (`close` pops entry and stops session).
- **Fix / opportunity:** Serialize session mutations (or move `state.active_session` updates into `session_manager`), and clear `active_session` before/after close consistently.
- **Risk if ignored:** Stale terminal tab / dangling session reference after close.

### F6 · P2 · Race on `state.installing` guard in `install_distro`
- **Where:** `src/app_controller.py:161-167` (`if state.installing: return`; `if await asyncio.to_thread(self.proot.busy_locks): ...`)
- **What:** The `state.installing` check-then-set is not atomic across awaits (`busy_locks` await sits between check and set), so two concurrent invocations can both pass and start overlapping installs. The `busy_locks` check covers other processes only.
- **Evidence:** lines 162-168.
- **Fix / opportunity:** Set `state.installing` (or a local lock) before the `busy_locks` await, or guard with an `asyncio.Lock`.
- **Risk if ignored:** Overlapping installs / corrupted container state.

### F7 · P3 · `_on_connectivity` is a no-op; mounted service unused
- **Where:** `src/app_controller.py:107-113` (mounts `ft.Connectivity`), `:135-138` (`_on_connectivity` returns None)
- **What:** Connectivity is mounted and subscribed, but changes are ignored. D-017 §6 / house standards expect connectivity to gate retries or surface offline state; currently dead.
- **Evidence:** lines 135-138.
- **Fix / opportunity:** Either remove the service mount (simpler) or implement `_on_connectivity` to set a state flag / snack.
- **Risk if ignored:** Dead wiring; misleading "mounted service" claim.

### F8 · P3 · `list_sessions` truncates to 4 with no total count
- **Where:** `src/app_controller.py:385-393` (`self.show_snack(" · ".join(lines[:4]))`)
- **What:** If more than 4 sessions exist, the snack hides the rest with no indication of overflow.
- **Evidence:** line 393.
- **Fix / opportunity:** Append `… (+N more)` when `len(lines) > 4`.
- **Risk if ignored:** Minor UX; hidden sessions.

### F9 · P3 · `show_snack` silently swallows dialog errors and can stack SnackBars
- **Where:** `src/app_controller.py:289-291` (`with contextlib.suppress(Exception): self.page.show_dialog(ft.SnackBar(ft.Text(message)))`)
- **What:** Every call appends a new `SnackBar` DialogControl via `show_dialog` (base_page.py:402-414); rapid calls stack dialogs and `suppress` hides failures (e.g., duplicate-open RuntimeError at base_page.py:406).
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/controls/base_page.py:402-414`.
- **Fix / opportunity:** Use a single reusable SnackBar control or guard with `page._dialogs` membership; at minimum log suppressed exceptions.
- **Risk if ignored:** Stacked/queued snacks; swallowed UI errors.

### F10 · P3 · `_noop_cancel` and `page._controller` are private/undocumented hooks
- **Where:** `src/app_controller.py:84` (`self.page._controller = self`), `:132-133`
- **What:** Stores controller on a private page attribute (`_controller`); no public Flet API. Fragile across Flet versions.
- **Evidence:** No `page._controller` in `.venv` flet source.
- **Fix / opportunity:** Use a module-level or context-based holder, or document the private contract.
- **Risk if ignored:** Breakage on Flet upgrade. UNVERIFIED whether any view reads `page._controller`.

### F11 · P2 · `_check_for_updates` task exceptions propagate through `run_task` done-callback
- **Where:** `src/app_controller.py:88` (`self.page.run_task(self._check_for_updates)`), `:309-318`; `.venv/lib/python3.14/site-packages/flet/controls/page.py:943-964`
- **What:** `run_task` schedules via `asyncio.run_coroutine_threadsafe` and its done-callback re-raises any exception (`page.py:956-958`). `check_for_update` catches internally, but a future change (or httpx import failure at module load) could raise and be re-raised in the loop. `_consent_and_preload` (line 91-95) is similarly unguarded.
- **Evidence:** page.py:950-958.
- **Fix / opportunity:** Wrap both background coroutines in try/except + logger.debug (keep silent UX).
- **Risk if ignored:** Unhandled background-task exceptions in the event loop.

### F12 · P3 · `cancel_install` slot signature is sync but controller methods are otherwise async
- **Where:** `src/state/controller_ctx.py:28` (`cancel_install: Callable[[], None]`); `src/app_controller.py:62`
- **What:** Inconsistent with the async contract; if implemented, must be sync per context, complicating async cancellation.
- **Evidence:** lines above.
- **Fix / opportunity:** Change to `Callable[[], Awaitable[None]]` if cancellation is implemented.
- **Risk if ignored:** API churn when cancellation lands.

---

## Missed capabilities (dependency audits only)

Not applicable (this is an app file, not a dependency).

---

## Verified-good list

- Flet APIs used all exist in 1.0.4: `ft.Page.loop` (controls/page.py:1334), `page.render` (controls/page.py:750), `page.run_task` (controls/page.py:929), `page.show_dialog` (controls/base_page.py:402), `ft.FilePicker` + async `save_file`/`pick_files` (controls/services/file_picker.py:186/278/333), `ft.Connectivity` (controls/services/connectivity.py:58), `ft.SnackBar` (controls/material/snack_bar.py:155), `ft.ThemeMode` (controls/types.py:860), `ft.create_context` (components/hooks/use_context.py:50).
- `page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))` matches the context-provider contract (use_context.py:44-62).
- `asyncio.to_thread` usage for blocking proot/session work is correct; `_on_line` uses `loop.call_soon_threadsafe` for thread-safe state writes.
- Observable writes happen on the event loop; `_apply_line` is marshalled via `call_soon_threadsafe`.
- `AdService.show_interstitial` is awaited after successful install/remove (D-017 §6).
- `_restore_prefs`/`_restore_onboarding` correctly suppress and log.
- `init` mounts services before render; theme installed before render.
- Sole-importer rule intact: `app_controller.py` does not import `proot_distro` (test_proot_surfaces.py).

---

## Unverified

- Whether `FilePicker.save_file`/`pick_files` return paths usable by `proot` on Android (content URIs vs filesystem paths) — requires device verification (D-005).
- Whether `self.page.loop` equals `self.session.connection.loop` used by `run_task` in all Flet 1.0.4 configurations (desktop vs mobile) — not proven by source inspection.
- Whether any view reads `page._controller` (no grep hit, but dynamic access possible).
- Whether `_consent_and_preload` runs before `refresh_containers` await completes ordering on slow devices — task scheduling order is best-effort.
- Concurrency behavior of `session_manager.open` called via `asyncio.to_thread` under Android (process spawn + PTY) — requires device verification.
