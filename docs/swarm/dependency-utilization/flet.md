# flet 1.0.4 — utilization audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** all 32 `.py` files under `src/` (`main.py`, `app_controller.py`, `app_shell.py`, `core/*`, `components/*`, `screens/*`, `services/*`, `state/*`) · `docs/dependency-studies/flet.md` (prior study) · installed `flet==1.0.4` at `.venv/Lib/site-packages/flet/` (279 `.py`) · **Date:** 2026-10-20

---

## What it does / how the app uses it

The app uses Flet 1.0.4 in the modern declarative style required by D-015: a single `@ft.observable AppState`
(`src/core/state.py:8`) is the only mutable state, `@ft.component` views read it during render, and every
handler only writes state or calls an `AppController` coroutine. The surface actually used is **61 distinct
`ft.*` names** — 38 constructor callables, 8 enums, and the component/hook/context API:

| Area | App usage | Flet API used |
|---|---|---|
| Shell | `src/app_shell.py` root component, 3-tab `NavigationBar` | `@ft.component`, `ft.use_state`, `ft.use_context`, `ft.context.page`, `ft.NavigationBar` |
| State | `src/core/state.py` singleton | `@ft.observable`, `Observable.__setattr__` notifications |
| Controller bridge | `src/state/controller_ctx.py:61` | `ft.create_context` → `use_context` provider pattern |
| Services | `src/core/shared_services.py`, `src/app_controller.py:98-113` | `ft.SharedPreferences`, `ft.FilePicker`, `ft.Connectivity`, `ft.Clipboard`, `ft.Share`, `ft.HapticFeedback`, `ft.UrlLauncher` |
| Dialogs/toasts | 11 `show_dialog` / 18 `pop_dialog` call sites | `page.show_dialog`, `page.pop_dialog`, `ft.AlertDialog`, `ft.SnackBar` |
| Async | 30 `page.run_task` call sites | `page.run_task` (coroutine-only), `asyncio.to_thread` |
| Theme | `src/core/theme.py` | `ft.Theme`, `ft.ColorScheme`, `ft.ThemeMode`, `ft.Brightness`, `page.theme_mode`, `page.platform_brightness` |
| Terminal | `src/screens/terminal_view.py` | `ft.use_effect`, `ft.use_state`, `ft.Icon/IconButton/TextButton`, `flet_terminal.MobileTerminal` |
| Ads | `src/services/ad_service.py`, `src/components/banner_ad.py` | `flet_ads.{BannerAd,InterstitialAd,ConsentManager}` mounted through `page.services` |

**Existence check: clean.** Every `ft.*` chain referenced in `src/` exists in the installed wheel. The repo's own
guard (`tests/check_flet_api.py`, run over all 32 source files) passes with zero failures; `len(flet.__all__) == 538`
live-verified; `flet.version.flet_version == "1.0.4"` (`.venv/Lib/site-packages/flet/version.py:19`).
**There are no hallucinated APIs.** Every constructor kwarg the app passes was checked against
`inspect.signature(ft.X.__init__)` — **0 unknown kwargs across 38 constructor callables** — and every enum member
(`ft.Icons.*`, `ft.FontWeight.W_600`, `ft.MarkdownExtensionSet.GITHUB_WEB`, `ft.Brightness.LIGHT`, …) exists.
The defects below are **semantic**, not API-existence, defects.

---

## Findings

### F1 · P0 · `AppShell` does not subscribe to the observable `state` — the onboarding deck never dismisses and the shell never switches to a terminal
- **Where:** `src/app_shell.py:41-77` (the component body; `:44` `ft.use_state(TAB_DISTRO)`, `:50` `if not state.onboarding_done:`, `:35` `container = state.active_session`) · `src/app_controller.py:304` (`state.onboarding_done = True`) and `:410` (`state.active_session = container`) · `src/core/state.py:8` (`@ft.observable class AppState`)
- **What:** In Flet 1.0.4 an observable change re-renders **only the components that subscribed**. A component subscribes through exactly three routes: `ft.use_state(<observable>)` (`components/hooks/use_state.py:90-91`), `ft.use_context` where the resolved value is an `Observable` (`components/hooks/use_context.py:106-107`), or an `Observable` passed as a component argument (`components/component.py:234-248`). `AppShell` does **none** of the three — it only *reads* `state.onboarding_done` (`:50`) and `state.active_session` (`:35`). Reading an attribute never subscribes: `Observable` overrides only `__setattr__`/`__delattr__` (`components/observable.py:204-219`), never `__getattr__`. When `state` changes, `Observable._notify` (`components/observable.py:165-176`) calls the subscriber's `__on_change` → `component._schedule_update()` (`components/observable.py:82-92`), and `Component._schedule_update` (`components/component.py:207-220`) queues **only that component**; the session scheduler then calls `control.update()` on each queued control with **no parent traversal** (`messaging/session.py:719-721`). `_parent_component` is used solely for context lookup, never for re-render propagation (`components/component.py:511`, `components/hooks/use_context.py:100-104`). Nothing else rescues it either: in components mode `context.auto_update_enabled()` is `False` (`controls/context.py:169-179`; components mode is switched on by `Page.__render` at `controls/page.py:809`), so no page-wide auto-update re-renders the shell, and the app never calls `page.update()` itself. ⇒ **`AppShell` never re-renders.**
- **Evidence (runnable, read-only):** the regression was introduced by commit `4ad4593` (2026-10-20,
  "fix: the verification pass … drop the redundant use_state") — `git show 4ad4593 -- src/app_shell.py`:
  ```
  -    _st, _ = ft.use_state(state)
  +  (removed; commit message: "AppShell: drop the redundant ft.use_state(state) —
  +   AppState is @ft.observable and already re-renders subscribers")
  ```
  The commit's premise is wrong: `@ft.observable` notifies *subscribers*, and `AppShell` was the subscriber.
  A harness (`%TEMP%/flet_audit_harness.py`, run with the repo venv python; it builds a real `Session`+`Page`
  via `flet.messaging.session.Session`, renders `page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))`
  exactly as `src/app_controller.py:85` does, then mutates the observable) prints:
  ```
  --- CURRENT src/app_shell.py (no ft.use_state(state)) ---
     onboarding deck visible before          : True
     onboarding deck STILL visible after     : True
     control tree changed                    : False
  --- COUNTERFACTUAL copy with ft.use_state(state) restored ---
     onboarding deck visible before          : True
     onboarding deck STILL visible after     : False
     control tree changed                    : True
  ```
  The same root cause breaks "Open shell": `src/app_controller.py:410` sets `state.active_session`, but `AppShell`
  (the only place that decides between `TerminalView` and `DistroView`, `src/app_shell.py:53-61`) never re-renders,
  so the terminal view is never mounted. The existing regression test `tests/test_ui_reactive.py` only *constructs*
  components (`_render(screens.DistroView) is not None`) and never asserts that a state change re-renders a
  specific component — which is why the regression passed CI.
- **Fix / opportunity:** restore the subscription in `AppShell` (one line, `src/app_shell.py:44`):
  `_st, _ = ft.use_state(state)`. Better still, keep `AppShell` pure and move the branch decision into a small
  subscribed child (e.g. `SessionGate`) so the subscription lives next to the value it reads. Either way, add a
  test that asserts *re-render* (not just construction): render `AppShell`, mutate `state.onboarding_done`, assert
  the onboarding text is gone from the patched control tree.
- **Risk if ignored:** **a first-run dead end, and a dead "Open shell" button.** Tapping "Get Started"/"Skip" runs
  `finish_onboarding`, which persists the pref (`src/app_controller.py:307`) *and* sets `state.onboarding_done = True`
  (`:304`) — but the deck stays on screen because nothing re-renders `AppShell`. The user must kill and relaunch the
  app; the second launch is clean because `_restore_onboarding` (`src/app_controller.py:293-301`) runs **before**
  `page.render` (`:56-57` vs `:85`) and sets the flag in time. Likewise "Open shell" sets `state.active_session`
  (`:410`) and the shell never switches to `TerminalView`. P0 user-visible breakage on the only shipping platform.

### F2 · P1 · "Backup to a file" always fails on Android — `FilePicker.save_file` requires `src_bytes` on mobile
- **Where:** `src/app_controller.py:346-348` (`await self.file_picker.save_file(dialog_title=…, file_name=…)`) · `src/app_controller.py:351` (the backup that never runs) · installed `controls/services/file_picker.py:312-318`
- **What:** `FilePicker.save_file` raises `ValueError` when called on web **or mobile** without `src_bytes`:
  ```python
  if (self.page.web or self.page.platform.is_mobile()) and not src_bytes:
      raise ValueError('"src_bytes" is required when saving a file in web mode,'
                       "or on mobile (Android & iOS).")
  ```
  The app's only target is Android (`pyproject.toml [tool.flet.android]`), so `page.platform.is_mobile()` is
  `True` and the call raises **before** the tarball is produced. `AppController.backup_container` has **no**
  `try/except` (contrast `install_distro` at `:194-196`, which does), so the `ValueError` escapes the coroutine
  into `page.run_task`'s completion callback (`controls/page.py:947-962`, "Surface background task exceptions to
  default error handling"). The user gets **no snackbar, no dialog, no error** — the menu item silently does nothing.
- **Evidence (runnable):** harness, Android platform simulated (`page.platform = ft.PagePlatform.ANDROID`):
  ```
  --- FilePicker.save_file on Android (no src_bytes) ---
     raised ValueError: "src_bytes" is required when saving a file in web mode,or on mobile (Android & iOS).
  ```
- **Fix / opportunity:** build the archive into app storage first (`proot_service.backup_container(container, tmp)`
  → `tmp` under the app support dir), read the bytes, then
  `await self.file_picker.save_file(dialog_title=…, file_name=f"{container}.tar.gz", src_bytes=data)`.
  Alternatively (and more usefully on Android) write the archive into app storage and hand it to the already-mounted
  `ft.Share.share_files([...])` — see Missed capabilities. Either way, wrap the call in `try/except` and surface a
  `show_snack` so a failure is never silent.
- **Risk if ignored:** "Backup to a file" is dead on the only shipping platform, and the user is told nothing.

### F3 · P2 · Services are mounted through the wrong list (`page.services`), so the app's teardown path targets a list that is never sent to the client
- **Where:** `src/core/shared_services.py:42-49`, `src/app_controller.py:102-113`, `src/services/ad_service.py:71-72`, `:148-149`, `:220-221`, `:239-243` · installed `controls/services/service.py:39-54`, `controls/page.py:120-152`, `controls/base_page.py:823-832`, `controls/core/view.py:144`, `controls/page.py:228-247`
- **What:** Flet 1.0.4 services **self-register at construction**: `Service.__post_init__` resolves `context.page`
  and calls `page._services.register_service(self)` (`controls/services/service.py:47-54`). `page._services` is the
  `ServiceRegistry` control whose `_services` list *is* serialized to the client (`controls/page.py:92-152`).
  `page.services` is a **different list**: `BasePage.services` returns `self.__root_view().services`
  (`controls/base_page.py:823-832`), and `View.services` is declared with `metadata={"skip": True}`
  (`controls/core/view.py:144`) — i.e. **excluded from the wire** (`controls/object_patch.py:1205/1271/1397/1660/1714`).
  The app appends to that non-serialized list in six places and treats it as the registration point
  (`src/core/shared_services.py:43` `if instance not in page.services: page.services.append(instance)`).
  It works only by accident of the constructor. Two concrete consequences:
  1. **The ad teardown targets the wrong list.** `ad_service._release_service(self.page.services, ad_to_show)`
     (`src/services/ad_service.py:239-243`) removes the ad from `View.services`, but the ad stays in
     `page._services._services` — the list the client actually sees. It survives only because
     `messaging/session.py:570` calls `page._services.unregister_services()` (a **refcount** prune,
     `controls/page.py:228-247`) after every event; but `page.services` holds an extra strong reference to every
     service the app ever mounted, which is exactly what that refcount prune is designed to drop. The two
     mechanisms fight each other and the outcome depends on Python refcounts rather than on intent.
  2. **The `in` test is value-based, not identity-based.** `@control` classes get dataclass `__eq__`, and the
     internal wire id has `compare=False` (`controls/base_control.py:212` — `_i: int = field(init=False, compare=False)`)
     — verified live:
     `ft.Clipboard() == ft.Clipboard()` → `True`, `fta.InterstitialAd(unit_id='u') == fta.InterstitialAd(unit_id='u')`
     → `True`. So `if ad not in self.page.services` is a *value* comparison, and `services.remove(item)` removes the
     first *equal* element, not necessarily the same instance.
- **Evidence (runnable):**
  ```
  --- service registration ---
     page.services (View.services) after construction   : []
     page._services._services (real registry)           : ['FilePicker']
     after page.services.append(fp) -> registry         : ['FilePicker']
  ```
  The service is in the real registry **before** anything is appended; the append changes nothing on the wire.
- **Fix / opportunity:** drop the `page.services.append(...)` calls entirely and rely on construction-time
  registration (keep the Python reference in the controller, which is what actually keeps the service alive).
  For deliberate teardown, release the Python reference and call the public `page.unregister_services()`
  (`controls/page.py:228`) rather than hand-editing a list. Also replace the `in`/`remove` value comparisons with
  identity comparisons (`any(s is item for s in ...)`) where identity is what is meant.
- **Risk if ignored:** an undocumented, load-bearing dependency on Python refcounts; ad services can leak into the
  client registry; the app has no supported way to unregister a service.

### F4 · P2 · "Restore from an archive" reads `picked[0].path`, which the native picker may leave `None`
- **Where:** `src/app_controller.py:360-366` (`path = picked[0].path` → `self.proot.restore_container(path)`) · installed `controls/services/file_picker.py:127-135`
- **What:** `FilePickerFile.path` is `Optional[str]` and the docstring states: *"Absolute path to the selected file,
  when available. — Web mode always returns `None`. — On native platforms, this can still be `None` if the platform
  picker does not expose a filesystem path."* The app passes the value straight into
  `proot_service.restore_container(archive)` with no `None` check and no `try/except` → the call raises inside the
  `asyncio.to_thread`, the exception escapes the controller coroutine and reaches `page.run_task`'s completion
  handler (`controls/page.py:947-962`) → **no user-visible error**, same silent failure mode as F2.
- **Evidence:** installed `controls/services/file_picker.py:127-135` (quoted above) — the optionality is
  documented by Flet itself; whether the Android picker returns `None` for a content-URI selection is
  **UNVERIFIED** (Dart-side, see below).
- **Fix / opportunity:** pick with `with_data=True` (`controls/services/file_picker.py:340`) and restore from bytes
  (`picked[0].bytes`) — or, if `path` is `None`, fall back to copying the bytes into app storage first and pass that
  path. Always wrap the restore in `try/except` and `show_snack` the failure.
- **Risk if ignored:** "Restore from an archive" fails silently for any device whose picker does not expose a path.

### F5 · P2 · `AppController.set_theme_mode` is a no-op for the shell until F1 is fixed, and the "System" theme never follows a runtime system-theme change
- **Where:** `src/app_controller.py:260-274` (`state.theme_mode = mode; state.theme_revision += 1; self.page.theme_mode = _THEME_MODES[mode]`) · `src/core/theme.py:43-68` (`is_light_theme`) · installed `controls/page.py:571` (`platform_brightness: Optional[Brightness] = None`), `:614` (`on_platform_brightness_change`)
- **What:** two independent issues.
  1. The theme flip works for the leaf views (they call `ft.use_state(state)` — `src/screens/views.py:75`, `:387`;
     `src/screens/terminal_view.py:63`, `:234`) but **not** for `AppShell`, for the reason in F1. Since
     `AppShell` renders the `NavigationBar` chrome and the shell background, the theme flip is *partially* applied:
     the body repaints but the shell chrome does not.
  2. In "system" mode `is_light_theme()` resolves the effective palette from `page.platform_brightness`
     (`src/core/theme.py:67-68`) — a **snapshot** field. The app never registers
     `page.on_platform_brightness_change` (no occurrence anywhere in `src/`; the field exists at
     `controls/page.py:614`), so when Android switches the system theme at runtime the app keeps painting the old
     palette until the next full re-render triggered by something else.
- **Fix / opportunity:** (1) fixed by F1; (2) register `page.on_platform_brightness_change` in `main()` and bump
  `state.theme_revision` (or set `page.theme_mode = ft.ThemeMode.SYSTEM` → re-render) so the "System" option
  genuinely follows the system. This is a first-class Flet capability the app ships but never uses.
- **Risk if ignored:** the app advertises "Theme follows the system unless you pick one" (`src/screens/views.py:437`)
  but does not follow it at runtime; a theme flip leaves part of the UI in the old palette.

### F6 · P3 · `src/core/theme.py:52` documents a Flet mechanism that does not exist ("underscore is exempt")
- **Where:** `src/core/theme.py:49-52` — `_ = _state.theme_revision  # read for subscription; underscore is exempt`
- **What:** there is no "underscore is exempt" rule anywhere in Flet 1.0.4. The only underscore rule is in
  `Observable.__setattr__`: `if name.startswith("_"):  # private/internal, don't notify`
  (`components/observable.py:204-207`) — that governs **notification**, not **subscription**. Reading
  `_state.theme_revision` subscribes to nothing: subscription requires `ft.use_state(<observable>)`
  (`components/hooks/use_state.py:90-91`), `ft.use_context` with an `Observable` value
  (`components/hooks/use_context.py:106-107`), or an `Observable` component argument
  (`components/component.py:234-248`). The views *are* subscribed — via their own `ft.use_state(state)` — so the
  behaviour is correct by accident; the comment is the only thing that is wrong.
- **Fix / opportunity:** delete the dead read and fix the comment to say "the views subscribe via
  `ft.use_state(state)`". A wrong comment about framework semantics is how F1 happened.
- **Risk if ignored:** a future maintainer "simplifies" the real `ft.use_state(state)` calls because the comment
  says reads subscribe.

### F7 · P3 · Three native services are mounted on the client and never called: `Clipboard`, `Share`, `HapticFeedback`
- **Where:** `src/core/shared_services.py:12-29` (mount table), `:42-49` (construction + registration) — grep shows **no call site** for any of the three in `src/`
- **What:** each construction registers a service with the Dart client (`controls/services/service.py:47-54`), so
  three native plugins are instantiated per session and held for the session's lifetime, for features the app
  never uses. `Clipboard` is especially ironic: `AppController.copy_path` (`src/app_controller.py:372-383`) copies a
  path *inside proot*, not to the OS clipboard.
- **Fix / opportunity:** either wire them (see Missed capabilities — all three have obvious homes) or drop them from
  the mount table so the app does not pay for services it never uses.
- **Risk if ignored:** low direct risk, but it is dead weight on the client and it hides three ready-made features.

### F8 · P3 · `src/core/storage_paths.py` hand-rolls the storage-root lookup instead of using the shipped `ft.StoragePaths`
- **Where:** `src/core/storage_paths.py:11-18` — `env = os.environ.get("FLET_APP_STORAGE_DATA") or os.environ.get("FLET_APP_STORAGE_TEMP")` · installed `controls/services/storage_paths.py:41-63` (`get_application_documents_directory`) and `:65+` (`get_application_support_directory`)
- **What:** the app decides where every proot container, OCI layer and lock file lives by reading two environment
  variables directly. Flet ships `ft.StoragePaths` with `get_application_support_directory()` /
  `get_application_documents_directory()` / `get_application_cache_directory()` /
  `get_external_storage_directories()` / `get_temporary_directory()`, whose docstrings name the very env vars the app
  guesses at (`controls/services/storage_paths.py:27`, `:72`, `:188`). The app's fallback chain is semantically wrong:
  `FLET_APP_STORAGE_TEMP` is the **temporary** directory, which the OS may reclaim — falling back to it would place
  the entire container store in a wipeable location. The Python package only *documents* that the client sets
  `FLET_APP_STORAGE_DATA` (`controls/services/storage_paths.py:72`); the actual setting happens Dart-side and is
  therefore **UNVERIFIED** from Python.
- **Fix / opportunity:** ask `ft.StoragePaths` for the support directory (the correct home for rootfs homes per the
  prior study §3.6) instead of parsing env vars; keep the env-var read only as a desktop-dev fallback, and drop the
  `FLET_APP_STORAGE_TEMP` leg for anything durable. `get_external_storage_directories()` also lets the app offer an
  SD-card install location instead of forcing app-private storage.
- **Risk if ignored:** if `FLET_APP_STORAGE_DATA` is ever absent, installed containers would live in a temp dir and
  could be wiped by the OS — silent loss of every installed distro.

### F9 · P3 · Dead house helpers: `styles.chip()` and `styles.loading_state()` are never called
- **Where:** `src/core/styles.py:69` (`chip`) and `:146` (`loading_state`) — no call site in `src/`
- **What:** `loading_state` is the house's spinner (`ft.ProgressRing` + label), yet the install flow
  (`src/screens/views.py:355-361`) and the search flow (`:344`) render only an `ft.Text` line. Flet ships
  `ft.ProgressRing` and `ft.ProgressBar`; the app ships a wrapper for the spinner and never uses it.
- **Fix / opportunity:** use `loading_state` for the search/install busy states (or `ft.ProgressBar` for a
  determinate install progress if the proot layer can report one), and delete `chip` if the house does not want it.
- **Risk if ignored:** low; the install progress is currently a bare text line with no affordance.

### F10 · P3 · `AdService.close()` is dead code — the ad service is never torn down
- **Where:** `src/services/ad_service.py:229-236` (`async def close()` sets `_is_shutting_down` and releases the ads) — no call site in `src/`
- **What:** `AppController` holds the `AdService` for the whole session and never calls `close()` on exit
  (`src/main.py:24-31` only closes sessions). `_is_shutting_down` therefore stays `False`, so
  `preload_interstitial` keeps preloading during shutdown and the preloaded ad is never released from
  `page._services._services`.
- **Fix / opportunity:** call `await self.ad_service.close()` from `main()`'s `_on_close` handler
  (`src/main.py:24-26`) and/or from `AppController`.
- **Risk if ignored:** low; a preloaded interstitial may outlive the session it was preloaded for.

### F11 · P3 · PEP 758 unparenthesised `except A, B:` ties the app to Python ≥ 3.14 while flet supports ≥ 3.10
- **Where:** `src/components/update_dialog.py:33` (`except TypeError, ValueError:`) and `src/services/session_service.py:123` (`except OSError, ValueError:`)
- **What:** these are **valid** on the pinned interpreter — PEP 758 (Python 3.14) allows an unparenthesised
  multi-exception `except`. Verified live: `.venv/Scripts/python.exe -c "raise TypeError('x')\nexcept TypeError, ValueError: print('ok')"`
  → `ok`; `python -VV` → `Python 3.14.7`. `pyproject.toml:8` pins `requires-python = ">=3.14"`, so the app is
  self-consistent — but `flet-1.0.4.dist-info/METADATA:10` declares `Requires-Python: >=3.10`, and the parenthesised
  form works on every supported interpreter.
- **Fix / opportunity:** use `except (TypeError, ValueError):`. Zero behavioural change, removes a gratuitous
  portability cliff (and the lint-style oddity it invites).
- **Risk if ignored:** low, but the app cannot be installed on 3.10–3.13 even though its only hard dependency allows it.

### F12 · P3 · `TerminalView` constructs `MobileTerminal` and mutates the observable during render
- **Where:** `src/screens/terminal_view.py:68-78` (`entry.mt = MobileTerminal(...)` inside the render body) and `:112` (`entry.wired = True`) · installed `components/component.py:234-248` + `components/observable.py:165-176`
- **What:** `entry` is a `@ft.observable` (`src/services/session_manager.py:24`) and is also passed as a component
  **argument** to `TerminalView(entry)` (`src/app_shell.py:55`), so Flet auto-subscribes the component to the entry
  (`components/component.py:234-248`). Writing `entry.mt` / `entry.wired` from inside the render therefore notifies
  the component that is currently rendering, scheduling an extra update pass each time (`entry.ready`, `entry.title`
  and `entry.error` do the same, by design). Flet's own component model expects the body to be a pure function of
  state; D-015 §1 already codified that rule for the screens.
- **Fix / opportunity:** build the `MobileTerminal` once when the session is opened (in `SessionManager.open`,
  `src/services/session_manager.py:63-82`) and keep only the *wiring* in the render, or mark the assignment with a
  private attribute (`entry._mt`) so `Observable.__setattr__` skips notification
  (`components/observable.py:205`).
- **Risk if ignored:** one extra render pass per session open; more importantly it re-introduces the "mutate during
  render" pattern D-015 §1 banned, which is what caused the original "Frozen controls cannot be updated" crash class.

---

## Missed capabilities (dependency audits only)

Shipped by the installed `flet==1.0.4`, unused by the app, with a concrete insertion point. Nothing here requires a
new package (D-003 frozen).

| # | Capability | Installed API (verified) | Proposed integration point | Value vs cost |
|---|---|---|---|---|
| M1 | **Concurrent shell tabs** — `SessionManager` allows 4 live shells (`src/services/session_manager.py:20`) but the UI can only show one | `ft.Tabs` / `ft.Tab` exist (`flet.__all__`) | `src/app_shell.py:53-61`: replace the single `TerminalView(entry)` with a `ft.Tabs` whose tab list is `manager.entries.values()` | High value — turns a hidden 4-shell capability into a visible one. Low cost: one control swap in the shell |
| M2 | **Clipboard** — mounted, never called (`src/core/shared_services.py:25`) | `ft.Clipboard.set/get` (`controls/services/clipboard.py:19-28`); `ft.CopyToClipboard` client action (`controls/client_action.py:61-118`) | "Copy install command" / "Copy container path" in the container row menu (`src/screens/views.py:184-190`) | High value, ~10 lines; gives the user the `proot-distro login <name>` argv on the clipboard |
| M3 | **Share sheet** — mounted, never called (`src/core/shared_services.py:26`) | `ft.Share.share_files/share_text` (`controls/services/share.py:157-240`) | After a successful backup (`src/app_controller.py:342-354`), offer "Share container archive" instead of the broken `save_file` path (F2) | High value: it is the *correct* Android answer to F2 — the share sheet writes the archive wherever the user picks |
| M4 | **Haptics** — mounted, never called (`src/core/shared_services.py:24`) | `ft.HapticFeedback.selection_click/light_impact/medium_impact` (`controls/services/haptic_feedback.py:13-40`) | Install success (`src/app_controller.py:186`) and the probe pass (`src/app_controller.py:280`) | Medium value, 3 lines; the house already uses haptics in the roadmap for gate passes |
| M5 | **Storage paths API** — hand-rolled env-var lookup (`src/core/storage_paths.py:13`) | `ft.StoragePaths` + 10 async methods (`controls/services/storage_paths.py:20-210`) | `src/core/storage_paths.py:support_root()` | High value: correct semantics, platform-correct, and `get_external_storage_directories()` unlocks an SD-card install target |
| M6 | **App lifecycle** — no handler anywhere in `src/` | `page.on_app_lifecycle_state_change` (`controls/page.py:629`), `AppLifecycleStateChangeEvent.state` (`controls/page.py:444`), `page.app_visible` (`controls/page.py:897`) | `src/main.py` `main()` | Medium-high value: pause/resume the terminal (`session_manager`), re-check the update feed on resume, and stop polling while backgrounded — the prior study §4.2 recommends exactly this |
| M7 | **Platform brightness events** — `page.platform_brightness` is read as a snapshot (`src/core/theme.py:67`) | `page.on_platform_brightness_change` (`controls/page.py:614`) | `src/main.py` `main()` | Medium value: makes the "System" theme option honest (see F5) |
| M8 | **Determinate progress** — install progress is a `ft.Text` line (`src/screens/views.py:355-361`) | `ft.ProgressBar` (determinate) and `ft.ProgressRing` (indeterminate) both exist; the house already wraps the spinner in `src/core/styles.py:146` (`loading_state`) | `src/screens/views.py:355-361` | Medium value: a multi-hundred-MB pull with a text line is invisible progress |
| M9 | **Wake lock / screen brightness** — a long download can let the screen sleep mid-install | `ft.Wakelock` and `ft.ScreenBrightness` exist in the installed wheel | Around `AppController.install_distro` (`src/app_controller.py:161-202`) | Medium value: prevents the install being killed by screen-off on Android |
| M10 | **Real theme picker** — Settings shows a text label plus a cycling icon (`src/screens/views.py:427-450`) | `ft.SegmentedButton` / `ft.RadioGroup` / `ft.Switch` / `ft.Dropdown` all exist | `src/screens/views.py:433-456` | Medium value: replaces a 3-way cycle with a visible 3-way choice; the controller already has `set_theme_mode(mode)` (`src/app_controller.py:260`) |
| M11 | **Unmount cleanup hook** — nothing releases the terminal when the view goes away | `ft.on_unmounted` / `ft.on_mounted` / `ft.on_updated` (`components/hooks/use_effect.py:80-123`) | `src/screens/terminal_view.py:59` | Medium value: the framework's documented place to drop the terminal handle (relates to F12) |
| M12 | **UrlLauncher pre-flight + in-app web view** — `launch_url` is called blind (`src/core/shared_services.py:58-66`) | `UrlLauncher.can_launch_url` (`controls/services/url_launcher.py:102`), `LaunchMode`, `open_window` (`:133`) | `src/core/shared_services.py:launch_url` | Low-medium value: a "cannot open this link" snackbar instead of silence; `open_window` for the privacy policy |
| M13 | **Upload path for web/desktop restore** — not needed on Android but the code is shared | `page.get_upload_url` (`controls/page.py:1172`) + `FilePicker.upload` (`controls/services/file_picker.py:226-244`) | `AppController.restore_container` (`src/app_controller.py:356-370`) | Low value for the Android product, but it is the documented way to restore an archive on web, and `flet run` desktop is a dev target |

---

## Verified-good list

Checked and correct — the synthesis should not re-open these.

- **No hallucinated APIs.** All 61 `ft.*` names used in `src/` exist in the installed wheel; `tests/check_flet_api.py`
  passes over all 32 source files; `flet.__all__` has 538 entries; `flet.version.flet_version == "1.0.4"`
  (`version.py:19`).
- **All constructor kwargs are valid.** An AST sweep of every `ft.X(...)` call in `src/` compared each keyword against
  `inspect.signature(ft.X.__init__)`: **0 unknown kwargs over 38 constructor callables**. Every enum member used
  (`ft.Icons.*`, `ft.FontWeight.W_600/W_400/BOLD`, `ft.ThemeMode.*`, `ft.Brightness.LIGHT/DARK`,
  `ft.MarkdownExtensionSet.GITHUB_WEB`, `ft.BoxFit.CONTAIN`, `ft.TextAlign.CENTER`, `ft.MainAxisAlignment.*`,
  `ft.CrossAxisAlignment.CENTER`, `ft.ScrollMode.AUTO`, `ft.Alignment.CENTER/TOP_LEFT`) exists.
- **`ft.use_state(state)` on an observable is the right idiom.** `use_state.py:90-91` attaches an
  `ObservableSubscription` to the value when it is an `Observable`; `component.py:250-267` owns the subscription and
  `component.py:281-288` disposes it on re-render. The four leaf views do this correctly
  (`src/screens/views.py:75`, `:387`; `src/screens/terminal_view.py:63`, `:234`).
- **`ft.create_context` / `ft.use_context` pairing is correct.** `create_context(default)` returns a provider callable
  `(value, callback)` with `.default_value` and `._key` (`components/hooks/use_context.py:50-81`); the app's
  `ControllerMethodsCtx(methods, lambda: AppShell())` (`src/app_controller.py:85`) matches that shape exactly, and
  `use_context` walks the component tree for the nearest provider (`use_context.py:97-104`).
- **`page.render(lambda: …)` is the correct 1.0.4 entry point** (`controls/page.py:750-773`): it replaces
  `page.views[0].controls` with `Renderer().render(component)` and then starts the components-mode update scheduler
  (`page.py:800-810`).
- **`page.run_task` usage is correct everywhere** (30 call sites). It requires a coroutine function
  (`controls/page.py:940-941` raises `TypeError` otherwise) and every handler passed to it is an `async def`
  (`AppController.*` or `core.shared_services.launch_url`); `page.run_task` binds the page context
  (`page.py:939`) before scheduling on the connection loop (`page.py:943-945`).
- **`page.show_dialog` / `page.pop_dialog` are used correctly.** `show_dialog` manages the dismissal lifecycle and
  wraps `on_dismiss` (`controls/base_page.py:402-425`, `:460-478`); `pop_dialog` closes the **topmost open** dialog
  (`:427-445`). The app's `show_dialog(ft.AlertDialog(...))` + `pop_dialog()` + `run_task(...)` sequence is the
  documented pattern, and `ft.SnackBar` is a `DialogControl` (`controls/material/snack_bar.py:154-155`) whose own
  docstring shows `page.show_dialog(ft.SnackBar(ft.Text(...)))` (`snack_bar.py:162`) — exactly what
  `src/app_controller.py:291` does.
- **`ft.SnackBar` auto-dismisses** — `duration` defaults to 4000 ms (`snack_bar.py:233`), so the toast stack does not
  need manual popping.
- **Repeated identical toasts are *not* a bug.** Two identical `ft.SnackBar(ft.Text("x"))` compare equal
  (`ft.Text("hi") == ft.Text("hi")` → `True`, dataclass `__eq__`), but `show_dialog` would only reject a duplicate if
  the *same instance* were already open (`base_page.py:418` uses list membership), and each call builds a fresh
  instance — verified live: the second identical snackbar is accepted, no `RuntimeError`. (`_remove_dialog` at
  `base_page.py:488-491` uses the same value-based membership, but `show_dialog` wraps each dialog's `on_dismiss` in
  its own closure (`:460-478`), so live dialogs are never value-equal to each other. No finding here.)
- **Theme plumbing is sound.** `ft.Theme(color_scheme=ft.ColorScheme(...))` (`src/core/theme.py:95-124`) matches the
  installed `Theme`/`ColorScheme` fields; `page.theme_mode` is a `BasePage` field
  (`controls/base_page.py:169`); `page.platform_brightness` is `Optional[Brightness]`
  (`controls/page.py:571`) and `ft.Brightness.LIGHT/DARK` exist; `page.platform.is_mobile()` exists on the
  `PagePlatform` enum (`controls/types.py:804`).
- **`ft.use_effect(_apply_theme, [state.theme_revision])`** (`src/screens/terminal_view.py:122`) is correct: deps are
  compared by value (`components/component.py:337-346`), the effect re-runs on change and on mount
  (`components/hooks/use_effect.py:42-77`), and the terminal palette does repaint on a theme flip.
- **`page.on_disconnect` / `page.on_close` are wired correctly.** `disconnect` is dispatched as an ordinary page event
  (`messaging/session.py:217`), so the no-op handler in `src/main.py:29` cannot break the session; `on_close`
  (`controls/page.py:676`) closes the guest shells.
- **`ft.run(main, assets_dir=…)`** (`src/main.py:40`) matches the installed signature (`app.py:68-80`); `assets_dir=None`
  is handled (`app.py:705-731`).
- **PEP 758 `except A, B:` is legal on the pinned interpreter** — verified on Python 3.14.7 (see F11 for the
  portability note; **not** a crash).
- **D-015 §2 landmine respected.** Nothing built inside an event handler is a `@ft.component`: the license content
  is the plain function `licenses_view()` (`src/screens/views.py:609-611`) and the update dialog is a plain function
  (`src/components/update_dialog.py:40`).

---

## Unverified

- **Whether the Android native file picker returns a usable `path`** (F4). The optionality is documented by Flet
  (`controls/services/file_picker.py:127-135`), but the Dart picker's behaviour is not observable from the Python
  package; the platform-specific truth needs a device run (CI APK per D-005).
- **Whether the Android client always exports `FLET_APP_STORAGE_DATA`** (F8). The Python package only mentions it in a
  docstring (`controls/services/storage_paths.py:72`); the variable is set Dart-side.
- **The exact payload of `NavigationBar.on_change` (`e.data` as a string index) and `Markdown.on_tap_link` (`e.data` as
  the URL).** `Event.data`/`Event.control` exist (`controls/control_event.py:109-127`) and the app's
  `int(e.data)` (`src/app_shell.py:48`) / `e.data` (`src/components/update_dialog.py:71`) are the conventional Flet
  shapes, but the Dart-side contract is not verifiable from the Python wheel.
- **Whether `page.platform_brightness` is populated at session start** (F5). The field defaults to `None`
  (`controls/page.py:571`); the initial value comes from the client.
- **Device-side rendering of `flet_terminal.MobileTerminal` 0.4.0** (F12) — out of scope here; it is audited by the
  `flet-terminal` agent.
- **Whether the `flete_ads` UMP consent form actually appears on-device** — the Python side of the flow was reviewed,
  but UMP's regional gating is client-side.

---

### Reproducing the evidence

```
.venv/Scripts/python.exe tests/check_flet_api.py <each file in src/>   # 0 failures
.venv/Scripts/python.exe %TEMP%/flet_audit_harness.py                  # F1, F2, F3 evidence blocks
```

The harness builds a real `flet.messaging.session.Session` over a stub `Connection`, renders
`page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))` exactly as `src/app_controller.py:85` does,
and compares the current `src/app_shell.py` against a patched copy written to the OS temp dir. **No file under `src/`
was modified.**
