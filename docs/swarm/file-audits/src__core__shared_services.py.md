# src/core/shared_services.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/core/shared_services.py` (75 lines) · `src/main.py` · `src/app_controller.py` (`_mount_services` :98-113, `init` :47-97) · `docs/decisions.md` (D-015/D-017) · `docs/swarm/dependency-utilization/flet.md` (F3/F7) · installed `flet==1.0.4` (`controls/services/service.py:39-54`, `controls/page.py:92-152,228-247`, `controls/base_page.py:821-832`, `controls/core/view.py:144`, `controls/services/*.py`) · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/shared_services.py` mounts five long-lived Flet services (haptics, clipboard, share, url_launcher, prefs) once per page and exposes `shared_url_launcher`/`launch_url`. In practice only `SharedPreferences` is consumed (`AppController.prefs`, restored in `_restore_prefs`/`_restore_onboarding` and written in `set_*`), and `UrlLauncher` is consumed via `launch_url` from `screens/views.py:527` and `components/update_dialog.py:26`. `Clipboard`, `Share`, and `HapticFeedback` are constructed but have no call site in `src/`. `StoragePaths` is not used at all (hand-rolled `core/storage_paths.py` instead). Mounting happens in `AppController._mount_services` (`app_controller.py:98-113`), which also mounts `FilePicker` and `Connectivity` directly.

---

## Findings

### F1 · P2 · Keep-alive registration targets the wrong list (`page.services` instead of `page._services`)
- **Where:** `src/core/shared_services.py:42-49` (`if instance not in page.services: page.services.append(instance)`) · installed `controls/services/service.py:47-54` (`page._services.register_service(self)`) · `controls/base_page.py:823-832` (`services` → `__root_view().services`) · `controls/core/view.py:144` (`services: ... metadata={"skip": True}`)
- **What:** In Flet 1.0.4 services self-register into the real `ServiceRegistry` (`page._services`) at construction time; `page.services` is a separate `View.services` list that is skipped during serialization and never reaches the client. The manual `page.services.append(...)` therefore (a) does not keep the service alive on the client side and (b) the `instance not in page.services` guard is checked against an empty/irrelevant list, so it never dedupes against the real registry.
- **Evidence:** `service.py:50-54` calls `page._services.register_service(self)` inside `__post_init__`; `base_page.py:823-832` shows `page.services` returns `__root_view().services`; `view.py:144` marks that field `skip=True`.
- **Fix / opportunity:** drop the `page.services.append(...)` block; rely on construction-time registration. Keep-alive is already provided by the `setattr(page, attr, instance)` strong references (`shared_services.py:48`) plus `AppController` fields (`app_controller.py:100,102,108`).
- **Risk if ignored:** an undocumented dependency on Python refcounts; services can be pruned by `page._services.unregister_services()` (`controls/page.py:228-247`) if no strong ref survives, and the `page.services` list drifts from reality.

### F2 · P2 · Idempotency is keyed on a page attribute, not on the real registry
- **Where:** `src/core/shared_services.py:33-36` (`existing = getattr(page, attr, None)`) · installed `controls/page.py:120-152` (`ServiceRegistry.register_service`)
- **What:** A second call to `mount_shared_services` with the same page reuses the instance stored on `page.<attr>`, but if that attribute was cleared (or never set because construction failed and `continue`d) while the service still lives in `page._services._services`, a duplicate is constructed and registered. Conversely, if the attribute exists but the instance was pruned from the registry, the stale reference is returned.
- **Evidence:** `shared_services.py:33-49` only checks `getattr(page, attr, None)`; `register_service` has no dedup by type.
- **Fix / opportunity:** also check `page._services._services` (or track mounted instances in a module-level weak set) before constructing; on reuse, re-`register_service` only if absent.
- **Risk if ignored:** duplicate Dart services on repeated mounts (e.g. during tests or re-init); stale handles returned to callers.

### F3 · P3 · Three mounted services are never used anywhere in `src/`
- **Where:** `src/core/shared_services.py:23-25,28` (haptics/clipboard/share in `specs`) · grep of `src/` shows no `.haptics`/`.clipboard`/`.share` access; `app_controller.py` only reads `mounted.get("prefs")` (`:100`)
- **What:** `HapticFeedback`, `Clipboard`, and `Share` are constructed on every launch, each registering a Dart service (`controls/services/service.py:47-54`), although no code path calls them. `UrlLauncher` and `SharedPreferences` are genuinely used.
- **Evidence:** `grep -rn "haptics\|clipboard\|share" src/` returns only `shared_services.py` definitions; `app_controller.py:100` consumes only `"prefs"`.
- **Fix / opportunity:** remove the three unused entries from `specs` (and `_ATTR_NAMES`) until a feature needs them; alternatively wire them into the relevant UI. No new dependency (D-003) involved.
- **Risk if ignored:** extra native service bindings and startup cost on every launch for no benefit.

### F4 · P3 · `StoragePaths` capability is hand-rolled instead of using the shipped service
- **Where:** `src/core/storage_paths.py:11-18` reads `FLET_APP_STORAGE_DATA`/`FLET_APP_STORAGE_TEMP` env vars · installed `controls/services/storage_paths.py:41-63` (`get_application_documents_directory`), `:65+` (`get_application_support_directory`), `:178+` (`get_temporary_directory`)
- **What:** The app guesses at paths from env vars, while Flet 1.0.4 ships `ft.StoragePaths` with typed async accessors. The env-var chain is fragile and is not the documented source of truth.
- **Evidence:** `storage_paths.py` (app) `os.environ.get("FLET_APP_STORAGE_DATA")`; installed service exposes the accessors above.
- **Fix / opportunity:** mount `ft.StoragePaths` in this module (one upstream importer) and replace `core/storage_paths.py` consumers with calls to it. This is a separate file's change; flagged here because the audit scope names `StoragePaths`.
- **Risk if ignored:** wrong base directory on some builds; duplicated logic.

### F5 · P3 · `_current_page()` failure mode is broader than documented
- **Where:** `src/core/shared_services.py:69-75` (`from flet import context; return context.page`) · installed `controls/context.py` (Context.page property)
- **What:** The `except Exception` swallows any error (including a missing `context` module) and returns `None`, so `shared_url_launcher(None)` silently returns `None` and `launch_url` returns `False` with only a debug log. In worker threads `context.page` may raise `RuntimeError` (verified UNVERIFIED on device).
- **Evidence:** `shared_services.py:70-75`.
- **Fix / opportunity:** narrow to `RuntimeError` and log at warning level when a page was expected; optionally accept an explicit `page` (already supported) and prefer it in all callers (currently `screens/views.py:527` and `update_dialog.py:26` pass `page`).
- **Risk if ignored:** silent no-op URL launches with no user feedback.

### F6 · P3 · `launch_url` reports success whenever no exception is raised
- **Where:** `src/core/shared_services.py:58-66` (`await launcher.launch_url(url); return True`)
- **What:** `UrlLauncher.launch_url` returns `None` (`controls/services/url_launcher.py:62-76`); the wrapper cannot know whether the OS actually opened the URL. It returns `True` purely because no exception propagated.
- **Evidence:** installed `url_launcher.py:62-76` (`await self._invoke_method(...)` with no return value).
- **Fix / opportunity:** rename semantics to "attempted" or call `can_launch_url` first where meaningful; document that `True` means "no exception", not "opened".
- **Risk if ignored:** callers (update dialog) may show misleading success.

### F7 · P2 · Failures are logged at `debug`, hiding mount problems
- **Where:** `src/core/shared_services.py:39-41,45-47` (`logger.debug(...)`)
- **What:** If a service constructor or registration raises, the app continues with `mounted` missing that key and no visible signal; `AppController.prefs` becomes `None` and prefs silently no-op.
- **Evidence:** `shared_services.py:37-47`; `app_controller.py:100` (`self.prefs = mounted.get("prefs")`) with no check.
- **Fix / opportunity:** log at `warning` (or surface via `state.data_note`) for mount failures, consistent with D-017 §9 ("no swallowed bugs").
- **Risk if ignored:** missing services reported as "unavailable" only at debug level; hard to diagnose on device.

---

## Missed capabilities (dependency audits only)

- `ft.StoragePaths` (installed `controls/services/storage_paths.py`) — typed async directory accessors; app hand-rolls path resolution in `core/storage_paths.py`. Integration point: mount in this module and consume from `core/storage_paths.py`. Value: correctness; cost: small refactor. (See F4.)
- `ft.Clipboard`/`ft.Share`/`ft.HapticFeedback` are already shipped and mounted but unused; either wire them or drop the mount (F3).

---

## Verified-good list

- All five constructed classes exist in Flet 1.0.4: `ft.HapticFeedback`, `ft.Clipboard`, `ft.Share`, `ft.UrlLauncher`, `ft.SharedPreferences` (verified by instantiation in `.venv`, returns matching type names).
- `UrlLauncher.launch_url(url, ...)` signature accepts `url: str` (`controls/services/url_launcher.py:62-76`); call at `shared_services.py:62` is valid.
- `SharedPreferences.get/set` signatures match usage (`get(key) -> Optional[...]`, `set(key, value) -> bool`) at `controls/services/shared_preferences.py:18-60`; `app_controller.py` calls `await self.prefs.get("theme_mode")` / `await self.prefs.set(...)` correctly.
- `flet.context.page` exists and is a property (`controls/context.py`); `_current_page()` pattern is valid.
- `page.services` property and setter exist (`controls/base_page.py:821-832`); mutation via `.append` is syntactically valid (semantics issue only, F1).
- Attribute names map correctly: `haptics`→`haptics`, `clipboard`→`clipboard`, `share`→`share`, `url_launcher`→`url_launcher`, `prefs`→`shared_preferences` (`shared_services.py:12-18`), matching Flet's conventional page attribute names.
- No hallucinated Flet API in this file; every `ft.*` reference resolves.

---

## Unverified

- Whether `context.page` is populated when `mount_shared_services` runs inside `AppController.init` (async) — assumed yes because `init` is scheduled via `page.run_task`; not exercised by tests (UNVERIFIED).
- Whether `page._services._services` contains the service immediately after construction in this code path (registration happens in `__post_init__` only if `context.page` resolves) — UNVERIFIED on device.
- Whether removing the unused three services affects any transitive caller (grep limited to `src/`; tests not scanned exhaustively) — UNVERIFIED but grep of `tests/` shows none.