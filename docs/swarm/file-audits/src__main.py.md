# src/main.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/main.py` (41 lines) · `src/app_controller.py` · `src/services/session_manager.py` · `src/services/session_service.py` · `src/services/ad_service.py` · `src/services/proot_service.py` · `src/core/proot_probe.py` · `src/core/storage_paths.py` · `src/core/posixdb.py` · `src/core/theme.py` · `tests/conftest.py` · `tests/check_flet_api.py` · `tests/test_flet_api_guard.py` · `tests/test_imports_vs_deps.py` · `docs/decisions.md` · `docs/reference/house-ui-design.md` · `docs/reference/dep-flet.md` · `docs/reference/dep-proot-distro.md` · `docs/reference/app-collabshell.md` · `docs/reference/app-sherlock.md` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` (279 files) · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/main.py` is the application entry point (41 lines). It sets up `sys.path` to root local imports in `src/`, configures root logging via `logging.basicConfig`, runs the application via `flet.run(main, assets_dir=...)` pointing at `src/assets`, and inside `main(page)` instantiates `AppController(page)`, hooks `page.on_close` and `page.on_disconnect`, registers `atexit.register(controller.session_manager.close_all)`, and launches `controller.init` via `page.run_task`.

---

## Findings

### F1 · P1 · Synchronous `main()` and `page.run_task(controller.init)` bypasses Flet error boundary and creates un-themed launch flash
- **Where:** `src/main.py:19-32` (`def main(page) -> None:`, `:32 page.run_task(controller.init)`) · `.venv/lib/python3.14/site-packages/flet/app.py:367-385` (`main` handler execution & error boundary) · `.venv/lib/python3.14/site-packages/flet/controls/page.py:943-964` (`run_task` implementation)
- **What:** Flet 1.0.4 natively supports asynchronous entry points: `flet/app.py:367-368` checks `inspect.iscoroutinefunction(main)` and awaits it before flushing the initial frame via `await session.after_event(session.page)` (`app.py:381`). Because `main` is synchronous and schedules `controller.init` via `page.run_task`, `main` returns immediately. Flet sends an initial un-themed frame with no controls to the client before `theme.build_theme()` (`src/app_controller.py:53`) and `page.render()` (`src/app_controller.py:85`) ever run. Furthermore, if `controller.init` fails (e.g. fatal probe failure, corrupt storage, missing dependency), Flet's session error screen (`session.error(...)` at `flet/app.py:385`) is never shown because `main()` already exited cleanly; the exception is swallowed into the asyncio background task done-callback (`page.py:956-958`), leaving the user stuck on an empty blank screen.
- **Evidence:** Executing `main(FakePage())` logs `RuntimeWarning: coroutine 'AppController.init' was never awaited`. Sibling house apps all declare async entry points (`Sherlock/src/main.py:2098`: `async def main(page: ft.Page) -> None: ... await controller.init()`; `CollabShell/src/main.py:157`: `async def main(page: ft.Page): ... await AppController(page).init()`; `DDGS/src/main.py:19`: `async def main(page: ft.Page): ... await controller.init()`).
- **Fix / opportunity:** Declare `async def main(page: ft.Page) -> None:`, create `controller`, and `await controller.init()`.
- **Risk if ignored:** Blank/un-themed visual flash on startup; fatal startup failures leave the app permanently frozen on a blank screen with zero crash feedback.

### F2 · P1 · Desktop window close does not trigger `_on_close` — guest sessions and child processes leak on exit
- **Where:** `src/main.py:24-30` (`page.on_close = _on_close`) · `.venv/lib/python3.14/site-packages/flet/controls/page.py:676-680` · `.venv/lib/python3.14/site-packages/flet/controls/core/window.py:26, 257-262, 341-345` · `CollabShell/src/main.py:190-220`
- **What:** In Flet 1.0.4, `page.on_close` is documented as "Called when a session has expired after configured amount of time (60 minutes by default)" (`page.py:678-679`) and is dispatched by `messaging/session.py:234` only upon session expiration. Closing a desktop window (Windows/Linux/macOS) sends an OS close event to `page.window.on_event` (`window.py:341`), NOT `page.on_close`. Because `page.window.prevent_close` is `False` and `page.window.on_event` is unhandled, clicking the window close button abruptly exits the Flutter desktop runner without `_on_close` ever firing.
- **Evidence:** Citing `CollabShell/src/main.py:190-220` (which documented this exact trap):
  `# Window-close -> auto-stop sessions (when enabled). page.on_disconnect fires only for web clients; on desktop the OS window closing is the only signal. prevent_close intercepts the close button, we terminate the subprocesses, then destroy the window ourselves.`
  In `.venv/lib/python3.14/site-packages/flet/controls/core/window.py:26`: `CLOSE = "close"`, `:257`: `prevent_close: bool = False`, `:341`: `on_event: Optional[EventHandler[WindowEvent]] = None`.
- **Fix / opportunity:** On desktop platforms (`if not page.web and page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.LINUX, ft.PagePlatform.MACOS):`), set `page.window.prevent_close = True` and handle `page.window.on_event` to intercept `e.type == "close"`, invoke `controller.session_manager.close_all()`, and then `await page.window.destroy()`.
- **Risk if ignored:** Leaked background guest processes, orphaned PTY file descriptors, and locked container directories on desktop when the window is closed.

### F3 · P2 · Misunderstood mobile lifecycle — `on_disconnect` is a web-only event, not mobile backgrounding
- **Where:** `src/main.py:27-29` (`page.on_disconnect = lambda _e=None: None`) · `.venv/lib/python3.14/site-packages/flet/controls/page.py:436-446, 629-634, 670-674`
- **What:** The comment on lines 27-28 claims: `"A disconnect is not a shutdown: the app may just be backgrounded, and the shells (with their scrollback) must survive the resume."` In Flet 1.0.4, mobile backgrounding never triggers `on_disconnect`. `page.on_disconnect` is only triggered when a web browser tab or socket disconnects (`page.py:672`). Backgrounding on Android fires `AppLifecycleStateChangeEvent` to `page.on_app_lifecycle_state_change` (`page.py:629-634`) with `AppLifecycleState.PAUSE` / `HIDE`.
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/controls/page.py:672-674`:
  `Called when a web user disconnects from a page session, i.e. closes browser tab/window.`
  `.venv/lib/python3.14/site-packages/flet/controls/page.py:629-634`:
  `on_app_lifecycle_state_change: Optional[EventHandler[AppLifecycleStateChangeEvent]] = None`.
- **Fix / opportunity:** Wire `page.on_app_lifecycle_state_change` to monitor lifecycle states (`PAUSE`, `RESUME`, `DETACH`) and update comment to reflect true Flet semantics.
- **Risk if ignored:** Architectural misunderstanding; the app has no hook to pause background activities or perform state preservation upon Android app detachment.

### F4 · P2 · `_on_close` omits `AdService.close()` teardown — violates D-017 §6
- **Where:** `src/main.py:24-26` (`def _on_close(_e=None): controller.session_manager.close_all()`) · `src/services/ad_service.py:229-236` (`async def close(self): self._is_shutting_down = True ...`) · `docs/decisions.md:112-115` (D-017 §6)
- **What:** D-017 §6 mandates: `"Ads follow Sherlock's AdService exactly — UMP flow at launch, preload -> show with a 30-second minimum-interval guard, service release on close..."`. `AdService` defines `async def close(self)` to set `_is_shutting_down = True` and release cached interstitial ads from `page.services`. However, `_on_close` only calls `controller.session_manager.close_all()`, completely omitting `controller.ad_service.close()`.
- **Evidence:** `src/main.py:24-26` vs `Sherlock/src/main.py:2131-2133`:
  ```python
  with contextlib.suppress(Exception):
      if controller.ad_service:
          await controller.ad_service.close()
  ```
- **Fix / opportunity:** Call `await controller.ad_service.close()` (guarded by `contextlib.suppress(Exception)`) during shutdown.
- **Risk if ignored:** Violation of D-017 §6; interstitial ad instances remain mounted in `page.services`.

### F5 · P2 · Unbounded `atexit.register` handler accumulation and instance retention
- **Where:** `src/main.py:31` (`atexit.register(controller.session_manager.close_all)`)
- **What:** `main(page)` is invoked on each new session. Calling `atexit.register(controller.session_manager.close_all)` registers a bound method callback into the process-global `atexit` table on every connection. Bound methods strongly reference `self` (`controller.session_manager`), preventing `controller` and session entries from being garbage collected.
- **Evidence:** Live test in Python 3.14.9 with `FakePage`: `atexit._ncallbacks()` increments on every `main(p)` invocation (1 -> 2 -> 3).
- **Fix / opportunity:** Register `atexit` once at module scope or in `if __name__ == "__main__":`, or rely on lifecycle events (`page.window.on_event`, `page.on_close`).
- **Risk if ignored:** Memory leak across session lifecycles; redundant teardown executions on process exit.

### F6 · P2 · Unconditional `logging.basicConfig` at module import time overrides `FLET_LOG_LEVEL` and pollutes test runners
- **Where:** `src/main.py:12-16` (`logging.basicConfig(...)`) · `.venv/lib/python3.14/site-packages/flet/app.py:48-66` (`__configure_logging_from_env`)
- **What:** `logging.basicConfig(...)` is called at top-level module scope when `src/main.py` is imported. In Flet 1.0.4, `flet.app.py:48-66` checks the `FLET_LOG_LEVEL` environment variable (set e.g. via `flet run -v`), but `basicConfig` does nothing if the root logger already has handlers. Calling `basicConfig` unconditionally at import time locks the root logger to `INFO`, ignoring `FLET_LOG_LEVEL=DEBUG`. Furthermore, importing `src/main.py` in test suites mutates global logging configuration for the entire test process.
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/app.py:53-55`:
  `basicConfig does nothing once the root logger has a handler, so an app that configures logging itself keeps the setup it chose.`
  `Sherlock/src/main.py:2098-2102` isolates `logging.basicConfig` inside `main()` or CLI blocks.
- **Fix / opportunity:** Move `logging.basicConfig` inside `main()` or `if __name__ == "__main__":`, and check `os.getenv("FLET_LOG_LEVEL")`.
- **Risk if ignored:** `flet run -v` fails to surface framework debug logs; importing `main.py` mutates test runner logging.

### F7 · P3 · Missing page title, zero-padding, zero-spacing, and desktop window minimum constraints
- **Where:** `src/main.py:19-33` · `pyproject.toml:24` (`product = "Proot Distro"`) · `docs/reference/house-ui-design.md:8-19` · `.venv/lib/python3.14/site-packages/flet/controls/base_page.py:208` (`title`), `.venv/lib/python3.14/site-packages/flet/controls/core/view.py:119` (`padding`), `:127` (`spacing`), `.venv/lib/python3.14/site-packages/flet/controls/core/window.py:142-149` (`min_width`, `min_height`)
- **What:**
  1. `page.title` is never set in `main.py` or `app_controller.py`. On desktop, the window displays default `"Flet"` rather than `"Proot Distro"`.
  2. `page.padding` and `page.spacing` are not configured. Flet 1.0.4's root `View` defaults `padding` to `Padding.all(10)` (`view.py:119`) and `spacing` to `10` (`view.py:127`). `docs/reference/house-ui-design.md` §1 requires full-bleed columns with bottom `NavigationBar`. Sibling apps (`Sherlock`, `CollabShell`) set `page.padding = 0` and `page.spacing = 0`.
  3. `page.window.min_width` and `page.window.min_height` are unset, allowing the desktop window to collapse to unusable dimensions.
- **Evidence:** `git grep "page.title" src/` yields 0 hits. `CollabShell/src/main.py:162-177`: `page.title = constants.APP_NAME`, `page.padding = 0`, `page.spacing = 0`, `page.window.min_width = tokens.WINDOW_MIN_WIDTH`.
- **Fix / opportunity:** Set `page.title = "Proot Distro"`, `page.padding = 0`, `page.spacing = 0`, and `page.window.min_width = 360`, `page.window.min_height = 600`.
- **Risk if ignored:** Default 10px margin breaks full-bleed navigation bar styling; desktop window shows placeholder "Flet" title.

### F8 · P3 · Missing `page.on_error` and `page.on_view_pop` handlers
- **Where:** `src/main.py:19-33` · `.venv/lib/python3.14/site-packages/flet/controls/page.py:642` (`on_view_pop`), `:695` (`on_error`)
- **What:** `page.on_error` is not wired, so uncaught exceptions in event handlers only write to stderr without surfacing user snacks or diagnostics. `page.on_view_pop` is not wired, so system back navigation or gestures on Android cannot dismiss active modal dialogs (licenses, settings, install dialogs) or navigate back to the home tab.
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/controls/page.py:642`: `on_view_pop: Optional[EventHandler[ViewPopEvent]] = None`, `:695`: `on_error: Optional[ControlEventHandler["Page"]] = None`. Both are handled in `Sherlock/src/main.py:573, 2113`.
- **Fix / opportunity:** Wire `page.on_error = controller.on_error` and handle `page.on_view_pop` to pop dialogs or switch tabs.
- **Risk if ignored:** Broken Android system back button UX; silent unhandled event exceptions.

### F9 · P3 · Untyped `page` parameter in `main(page)` and deferred `AppController` import
- **Where:** `src/main.py:19-20` (`def main(page) -> None: from app_controller import AppController`) · `.venv/lib/python3.14/site-packages/flet/app.py:38-45` (`AppCallable`)
- **What:** `def main(page) -> None:` lacks a type annotation for `page: ft.Page`. `from __future__ import annotations` is already present at line 3. `AppController` is imported locally inside `main()`, even though no module in `src/` imports `main.py` (no circular dependency exists).
- **Evidence:** `git grep "main" src/` confirms no circular dependency on `src/main.py`. `.venv/lib/python3.14/site-packages/flet/app.py:38`: `AppCallable = Callable[[Page], Union[Any, Awaitable[Any]]]`.
- **Fix / opportunity:** Import `flet as ft` and `from app_controller import AppController` at module top-level; annotate `async def main(page: ft.Page) -> None:`.
- **Risk if ignored:** Missing IDE autocompletion and static type checking for `page` and `controller` interactions.

### F10 · P3 · Environment contract and `posixdb` shims not initialized at `main.py` entry point
- **Where:** `src/main.py:1-41` · `src/core/storage_paths.py:45-53` · `src/services/proot_service.py:32-41` (`bootstrap()`) · `docs/decisions.md:5-7` (D-001) · `docs/reference/dep-proot-distro.md:17-19`
- **What:** D-001 and `dep-proot-distro.md` require: `"The env proot-distro must see BEFORE its first import — constants are computed at import time"`. `src/main.py` performs no environment initialization. Shims and env setup are split between `proot_probe.bootstrap_env()` and lazy `proot_service.bootstrap()`. If any background task or import touched `proot_distro` prematurely, `constants.py` would evaluate before `XDG_DATA_HOME` and `TERMUX_APP__PACKAGE_NAME` are set. Sibling apps (`DDGS/src/main.py:16`, `CollabShell/src/main.py:46-47`) initialize runtime shims and trust stores at the top of `main.py` before importing controllers.
- **Evidence:** `src/services/proot_service.py:32-41` defines idempotent `bootstrap()`, but `main.py` never calls it.
- **Fix / opportunity:** Call `proot_service.bootstrap()` at the top of `main.py` before importing `AppController`.
- **Risk if ignored:** Import ordering fragility could allow `proot_distro.constants` to evaluate default paths.

---

## Verified-good list

- **`ft.run` API and parameter contract:** `src/main.py:40` calls `ft.run(main, assets_dir=str(assets) if assets.is_dir() else None)`. Matches `.venv/lib/python3.14/site-packages/flet/app.py:68-81`; `assets_dir` resolution handles absolute paths via `app.py:677-702`.
- **AST API guard clean:** Verified via `tests/check_flet_api.py src/main.py` — 1 chain referenced (`ft.run`), 0 missing APIs.
- **Declared dependencies compliance:** `src/main.py` only imports stdlib (`sys`, `logging`, `pathlib`, `atexit`) and declared `flet`; passes `tests/test_imports_vs_deps.py`.
- **Working directory independence:** `sys.path.insert(0, str(Path(__file__).resolve().parent))` at line 10 ensures `src/` packages resolve regardless of invocation working directory.
- **Assets packaging path:** `assets = Path(__file__).resolve().parent / "assets"` points to existing `src/assets` containing `icon.png` and `icon.svg`.
- **Declarative architecture compliance:** `src/main.py` creates zero UI widgets, performs zero imperative state mutations, and delegates directly to `AppController`.

---

## Unverified

- Child process PTY termination behavior under Android low-memory-killer (LMK) process eviction when backgrounded without an active Dart bridge connection (requires physical Android device verification per D-005).
