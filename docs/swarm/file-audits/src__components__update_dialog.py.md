# src/components/update_dialog.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/components/update_dialog.py` (162 lines) · `src/services/update_service.py` · `src/core/shared_services.py` · `src/core/changelog.py` · `src/core/constants.py` · `src/core/tokens.py` · `src/core/theme.py` · `tests/check_flet_api.py` · `tests/test_flet_api_guard.py` · `tests/conftest.py` · `tests/test_ui_reactive.py` · `tests/test_version_sync.py` · `tests/test_imports_vs_deps.py` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-24

---

## What it does / how the app uses it

`show_update_dialog(page, update_data)` renders the "What's New"/update AlertDialog in two modes. Update-available mode: a title row, a `ft.Text` lead-in, a "What's New:" bold label, and a remote-markdown `ft.Markdown` (release notes, `GITHUB_WEB` extension, `on_tap_link` → `_launch`) inside a scrolling `ft.Column`, plus `_update_actions` (Google Play / Release page / Later) and `modal=mandatory`. Up-to-date mode: title "You're up to date", the bundled `notes_for(APP_VERSION)` markdown, and two actions — "Check for Updates" (`_check_again`) and "Close" (`page.pop_dialog`). `_launch(page, url)` consults `is_allowed_launch_url` (update_service.py:26-37, https-only allow-list: github.com/raw.githubusercontent.com/play.google.com + subdomains) then schedules `launch_url` (shared_services.py:58-66, uses the mounted `ft.UrlLauncher`) via `page.run_task`. `_check_again` is `async def` (update_dialog.py:149): pops the dialog, `await check_for_update()`, re-shows the dialog or shows a SnackBar. `_dialog_width` clamps to `page.width`. Every Flet chain referenced passes the installed-API guard (25 chains, exit 0).

---

## Findings

### F1 · P0 · Dead "Check for Updates" button — sync lambda returns an unevaluated coroutine
- **Where:** `src/components/update_dialog.py:102` (`on_click=lambda _e: _check_again(page)`) · `src/components/update_dialog.py:149-161` (`async def _check_again`) · `.venv/lib/python3.14/site-packages/flet/controls/base_control.py:548-552` (sync event-handler dispatch: `event_handler(e)`, result discarded) · `.venv/lib/python3.14/site-packages/flet/controls/base_page.py:940-941` (`run_task` requires a coroutine function)
- **What:** `_check_again` is declared `async def`, so calling it (as the lambda does at :102) returns a coroutine object without executing its body. Flet's event dispatch treats the lambda as a plain sync callable (base_control.py:548-552: `else event_handler(e)`), calls it, and discards the returned coroutine. None of the re-check body ever runs — `page.pop_dialog()`, `check_for_update()`, `show_update_dialog(...)`, and the SnackBar are all dead code from this button. The user taps "Check for Updates" and nothing happens. API guard passes because the *names* exist; the defect is semantic, not a missing API.
- **Evidence:** update_dialog.py:102 lambda wraps `async def _check_again` (:149). base_control.py:548-552 confirms sync handlers are invoked and their return value is dropped (no `await`/task creation for `callable` branch). Runtime probe of the exact `except` pattern (below) confirms lambda+eager-coroutine behavior class. `tests/check_flet_api.py` exit 0 on update_dialog.py proves every `ft.*` chain exists, so the silence is not an AttributeError.
- **Fix / opportunity:** Make the handler async-aware. Since Flet dispatches sync lambdas directly, either (a) register `_check_again` itself via `page.run_task(_check_again, page)` (it's a coroutine function, satisfying base_page.py:940-941), or (b) keep a thin sync lambda that calls `page.run_task(_check_again, page)`. Do not `await` inside a sync lambda. Minimal, architecture-respecting, no new dependency.
- **Risk if ignored:** The only user-triggered path to re-check for an update is broken; on the "up to date" dialog the user is permanently stuck with no recovery.

### F2 · P1 · `except TypeError, ValueError` catches only `TypeError` (Python-2 tuple-exception semantics)
- **Where:** `src/components/update_dialog.py:33` (`_dialog_width`) · `src/services/update_service.py:63` (`is_newer`) · same pattern in `tests/conftest.py` not relevant
- **What:** In Python 3, `except TypeError, ValueError` is `except TypeError as ValueError` — it catches **only** `TypeError` and binds the instance to the name `ValueError`. A real `ValueError` is NOT caught. Runtime-confirmed: raising `ValueError` is not handled by this clause; raising `TypeError` is. In `is_newer` (:58-67), `int(remote_build)` can raise `ValueError` when the feed sends a non-numeric `build_number` string — that `ValueError` escapes this clause (it is only caught later by `check_for_update`'s broad `except Exception` at :100). In `_dialog_width`, `int(getattr(page, "width", 0) or 0)` could raise `ValueError` if `page.width` is a non-numeric string — also escapes.
- **Evidence:** update_dialog.py:33 `except TypeError, ValueError:`; update_service.py:63 `except TypeError, ValueError:`. Runtime test: `raise ValueError` not caught by `except TypeError, ValueError`; `raise TypeError` caught. Python 3.14.9 compiles the syntax (no SyntaxError) — so it is a silent semantic bug, labeled as such rather than a syntax error.
- **Fix / opportunity:** Replace both clauses with `except (TypeError, ValueError):`. In `is_newer`, consider coercing `server_build` defensively before `int()`. No new dependency.
- **Risk if ignored:** A malformed feed (`build_number` that's a non-numeric string) propagates an uncaught `ValueError` out of `is_newer`; although `check_for_update` catches it broadly and returns None, the narrow clause is dead/misleading and masks intent. Robustness defect.

### F3 · P1 · Dialog lifecycle: `show_dialog` raises `RuntimeError` if a dialog is already open; `_check_again` has no guard
- **Where:** `src/components/update_dialog.py:107-120` (`page.show_dialog(ft.AlertDialog(...))`) · `src/components/update_dialog.py:154-156` (`page.pop_dialog()` wrapped in try/except) · `src/components/update_dialog.py:149-159` (`_check_again` pops then re-shows) · `.venv/lib/python3.14/site-packages/flet/controls/base_page.py:402-425` (`show_dialog` raises `RuntimeError("Dialog is already opened")` if dialog in `self._dialogs.controls`)
- **What:** `show_update_dialog` unconditionally calls `page.show_dialog(...)`. If any dialog is already open (re-entrancy, or a prior `_check_again` whose pop didn't take effect), Flet raises `RuntimeError` (base_page.py:418-419), crashing the re-check path. `_check_again` calls `page.pop_dialog()` first, but `pop_dialog` returns `None` when no dialog is open (base_page.py:427-445: `if not dialog: return None`) — it never raises — so the `try/except` at update_dialog.py:154-156 is misleading/dead code (UNVERIFIED whether it ever catches anything). After pop, `show_update_dialog` → `show_dialog` is safe only if pop actually closed the open dialog.
- **Evidence:** update_dialog.py:107 `page.show_dialog(`; :154-156 `try: page.pop_dialog() except Exception`. base_page.py:418 `if dialog in self._dialogs.controls: raise RuntimeError("Dialog is already opened")`; base_page.py:427-445 `pop_dialog` returns `None` when no open dialog (no raise).
- **Fix / opportunity:** Guard `show_update_dialog` / `_check_again` so `show_dialog` is not called while a dialog is open (e.g., check `any(d.open for d in page._dialogs.controls)` or wrap `show_dialog` in try/except RuntimeError). Keep `pop_dialog` then re-show. No new dependency.
- **Risk if ignored:** Rapid re-check taps or concurrent dialog open raise `RuntimeError`, crashing the update flow.

### F4 · P2 · `page.platform` may be `None` or a non-enum; `is_mobile()` call is unguarded
- **Where:** `src/components/update_dialog.py:125` (`is_android = bool(getattr(page, "platform", None)) and page.platform.is_mobile()`) · `.venv/lib/python3.14/site-packages/flet/controls/page.py:595` (`platform: Optional[PagePlatform] = None`) · `.venv/lib/python3.14/site-packages/flet/controls/types.py:804-849` (`PagePlatform.is_mobile()`)
- **What:** `Page.platform` is `Optional[PagePlatform]`. `bool(None)` short-circuits safely (so `is_android = False` on unset platform — correct for desktop), but if `platform` is a truthy non-Enum object lacking `is_mobile()`, `page.platform.is_mobile()` raises `AttributeError`. UNVERIFIED whether `platform` is always the `PagePlatform` enum at runtime on all targets (desktop may leave it None — handled; Android sets ANDROID — handled). The short-circuit makes the common cases safe, but the contract is implicit.
- **Evidence:** update_dialog.py:125; page.py:595 `platform: Optional[PagePlatform] = None`; types.py:843-849 `PagePlatform.is_mobile()` returns membership in `{IOS, ANDROID}`.
- **Fix / opportunity:** Make the intent explicit: `is_android = isinstance(page.platform, PagePlatform) and page.platform == PagePlatform.ANDROID` (import `PagePlatform` from flet), or keep the `bool(...)` short-circuit but document it. Minimal.
- **Risk if ignored:** `AttributeError` on an unexpected platform value crashes the dialog build.

### F5 · P2 · Error states are swallowed / not surfaced to the user
- **Where:** `src/components/update_dialog.py:23-26` (`_launch` discards the bool return of `launch_url`) · `src/core/shared_services.py:58-66` (`launch_url` catches all exceptions, logs at debug, returns `False`) · `src/components/update_dialog.py:161` (`page.show_dialog(ft.SnackBar(...))` for the up-to-date message)
- **What:** `_launch` calls `page.run_task(launch_url, ...)` and ignores whether launching succeeded. `launch_url` itself swallows every exception and returns `False`. The user gets no feedback when a link (Play Store / release page) fails to open. Separately, `_check_again` shows the "up to date" message via `page.show_dialog(ft.SnackBar(...))` — `SnackBar` is a `DialogControl` (snack_bar.py:155), so it is managed as a dialog rather than through `page.snack_bar`/`page.open`; this is semantically odd and its visual behavior is UNVERIFIED (it renders as a managed dialog, not an ephemeral snackbar).
- **Evidence:** update_dialog.py:26 `page.run_task(launch_url, url, page)` (return value ignored); shared_services.py:64-66 `except Exception: logger.debug(...); return False`; snackbar.py:155 `class SnackBar(DialogControl)`; update_dialog.py:161.
- **Fix / opportunity:** Surface launch failures (e.g., a transient SnackBar via `page.snack_bar = ft.SnackBar(...); page.snack_bar.open = True; page.update()` — but D-015 forbids imperative mutation; instead return the bool from `_launch` and let the caller render an error state in the next render, or keep silent failure as designed). Clarify the SnackBar usage: use `page.open(snack_bar)` if Flet 1.0.4 supports it (UNVERIFIED) or keep as managed dialog but document. No new dependency.
- **Risk if ignored:** Tapped links that fail silently look like a frozen app; up-to-date confirmation may not render as intended.

### F6 · P2 · Async/sync boundary at the markdown `on_tap_link` / `_launch` / `run_task` seam is fragile but currently correct
- **Where:** `src/components/update_dialog.py:71` (`on_tap_link=lambda e: _launch(page, e.data)`) · `src/components/update_dialog.py:23-26` (`_launch` sync, calls `page.run_task`) · `.venv/lib/python3.14/site-packages/flet/controls/base_page.py:929-941` (`run_task` raises `TypeError` if handler is not a coroutine function) · `src/core/shared_services.py:58` (`async def launch_url`)
- **What:** `on_tap_link` fires a sync lambda (Flet dispatches sync handlers directly, base_control.py:548-552). Inside, `_launch` is sync and calls `page.run_task(launch_url, ...)`; `run_task` requires a coroutine function and `launch_url` is `async def` (shared_services.py:58), so it schedules correctly today. This works, but if `launch_url` were ever changed to sync, `run_task` would raise `TypeError` (base_page.py:940-941). The boundary is correct but relies on `launch_url` staying async. Verified working, no bug — listed for completeness and as a regression point.
- **Evidence:** update_dialog.py:71, :23-26; base_page.py:940-941; shared_services.py:58.
- **Fix / opportunity:** Add a comment at `_launch` noting `launch_url` must remain a coroutine function for `run_task`. No code change required.
- **Risk if ignored:** A future refactor making `launch_url` sync crashes link taps with `TypeError`.

### F7 · P3 · No test coverage exercises `update_dialog` runtime behavior
- **Where:** `tests/` (no file imports `show_update_dialog`, `_check_again`, `_launch`, or `is_allowed_launch_url` from `components.update_dialog`) · `tests/conftest.py` (`FakePage` stand-in exists but is unused by the dialog) · `tests/test_flet_api_guard.py` (covers `ft.*` chain existence only, not runtime semantics)
- **What:** The Flet API guard (`tests/check_flet_api.py`, driven by `test_flet_api_guard.py`) verifies every `ft.*` chain exists (exit 0), which caught the `ft.ElevatedButton`/`ft.border.all` class of crash, but it does not catch the dead-button (F1), the `except` semantics (F2), or the dialog-lifecycle `RuntimeError` (F3). `FakePage` in conftest.py (`show_dialog`/`pop_dialog`/`run_task` stand-ins) is sufficient to write these tests but none exist for `update_dialog`.
- **Evidence:** `grep -rn "update_dialog\|show_update_dialog\|_check_again\|_launch\|is_allowed_launch_url" tests` returns no matches. conftest.py:10-49 `FakePage` with `dialogs`, `tasks`, `show_dialog`, `pop_dialog`, `run_task`.
- **Fix / opportunity:** Add tests using `FakePage`: (a) "Check for Updates" click schedules `_check_again` via run_task and the coroutine body executes (catches F1); (b) `is_allowed_launch_url` allow-list cases (catches F2 regression); (c) `show_dialog` when a dialog is open raises/guards (catches F3). No new dependency.
- **Risk if ignored:** F1/F2/F3 regress silently; the guard suite gives false confidence.

### F8 · P0/P1 (verified-good, not a bug) · URL allow-list is correctly enforced
- **Where:** `src/services/update_service.py:26-37` (`is_allowed_launch_url`) · `src/components/update_dialog.py:24` (`if not is_allowed_launch_url(url): return`) · `src/services/update_service.py:44-47` (`_safe_url` defaults disallowed URLs) · `src/services/update_service.py:97` (`github_url` defaults to `GITHUB_RELEASES_URL`) · `src/services/update_service.py:98` (`playstore_url` defaults to None if not allowed)
- **What:** Only https URLs into github.com/raw.githubusercontent.com/play.google.com (+ subdomains) may launch. `is_allowed_launch_url` is verified correct: scheme check, hostname lowercasing, exact-or-subdomain match. `_safe_url` returns the default for disallowed values, so `playstore_url` and `github_url` from an untrusted feed cannot escape the allow-list. No bug — documented as verified-good.
- **Evidence:** update_service.py:26-37 (re-read and logic-checked); :97-98 defaults. No flet source needed (pure stdlib `urlsplit`).
- **Risk if ignored:** None (control is correct).

---

## Verified-good list

1. **All 25 `ft.*` chains referenced in `update_dialog.py` exist in flet 1.0.4** — `tests/check_flet_api.py` exit 0 (chains: `ft.AlertDialog`, `ft.Column`, `ft.Container`, `ft.Control`, `ft.FilledButton`, `ft.FontWeight`, `ft.FontWeight.BOLD`, `ft.Icon`, `ft.Icons`, `ft.Icons.CAMPAIGN_ROUNDED/DOWNLOAD_ROUNDED/ROCKET_LAUNCH_ROUNDED/SHOP_ROUNDED/VERIFIED_ROUNDED`, `ft.Markdown`, `ft.MarkdownExtensionSet`, `ft.MarkdownExtensionSet.GITHUB_WEB`, `ft.OutlinedButton`, `ft.Page`, `ft.Row`, `ft.ScrollMode`, `ft.ScrollMode.AUTO`, `ft.SnackBar`, `ft.Text`, `ft.TextButton`).
2. **Enum members exist**: `ft.Icons.*` (all five used), `ft.MarkdownExtensionSet.GITHUB_WEB`, `ft.ScrollMode.AUTO`, `ft.FontWeight.BOLD` (verified via `hasattr`).
3. **`Markdown.on_tap_link` `Event.data` contains the clicked URL** — `.venv/.../controls/core/markdown.py:1031-1036`. Link taps pass the URL to `_launch`, which enforces the allow-list.
4. **`Page.show_dialog`/`pop_dialog`/`run_task` signatures verified** — `base_page.py:402-425`, `:427-445`, `:929-965`. `run_task` requires a coroutine function; `launch_url` is `async def` (shared_services.py:58).
5. **`Page.services` property** (base_page.py:823-832) and `View.services` field (view.py:144) — `shared_services.py:43` `instance not in page.services` works.
6. **`UrlLauncher.launch_url` is `async def`** (url_launcher.py:72-80) — satisfies `run_task`.
7. **`Icon(icon, size=20, color=...)` positional `icon` first param** — icon.py:26-48. `update_dialog.py:111` uses `ft.Icon(icon, size=20, color=...)` correctly.
8. **`Page.width` attribute exists** (`width in dir(ft.Page)` True) — `_dialog_width` `getattr(page, "width", 0)` is safe.
9. **`theme.primary()`, `theme.text()`, `tokens.FONT_MD/LG`, `tokens.SPACE_SM`, `tokens.DIALOG_WIDTH/MIN_WIDTH` all resolve at runtime** (PYTHONPATH=src probe).
10. **`except TypeError, ValueError:` compiles in Python 3.14.9** (not a syntax error) — the bug is semantic (F2), not syntactic.
11. **No imperative control mutation in `update_dialog.py`** — no `.value =`, `page.update()`, or `.controls.append/clear` (D-015 compliant). Views are pure functions of inputs.
12. **`is_allowed_launch_url` allow-list is correct** (F8).

---

## Unverified

1. Whether `page.platform` is always a `PagePlatform` enum at runtime on every target (desktop `None` is short-circuited safely; a truthy non-enum value is not covered) — F4 labeled UNVERIFIED.
2. Whether `int(remote_build)` ever receives a non-numeric string in practice (feed is trusted; `check_for_update`'s broad `except` catches it anyway) — F2 escape path labeled UNVERIFIED.
3. Whether `pop_dialog`'s `try/except` at update_dialog.py:154-156 ever catches an exception (`pop_dialog` returns `None` rather than raising) — labeled UNVERIFIED/dead code.
4. Visual behavior of `page.show_dialog(ft.SnackBar(...))` — SnackBar is a `DialogControl`; whether it renders as an ephemeral snackbar or a managed dialog is UNVERIFIED (F5).
5. Whether `page.open(snack_bar)` exists in flet 1.0.4 as an alternative to `show_dialog` for SnackBar — not checked (F5).
6. No runtime/behavioral tests exist for `update_dialog` (F7) — covered by F7, not independently verified.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-component audit, not a dependency audit. No new packages proposed (D-003 frozen dependency set).

---