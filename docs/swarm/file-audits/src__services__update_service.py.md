# src/services/update_service.py — audit

**Verdict:** BUG (MIXED)
**Confidence:** high
**Scope:** `src/services/update_service.py` · `src/app_controller.py` · `src/components/update_dialog.py` · `src/core/constants.py` · `src/core/state.py` · `src/core/shared_services.py` · tests (none target this service) · `.venv/lib/python3.14/site-packages/` (httpx 0.28.1, flet 1.0.4, packaging 26.3) · **Date:** 2026-10-24

## What it does / how the app uses it

`src/services/update_service.py` is the release-feed update check. `check_for_update()` GETs `UPDATE_CONFIG_URL` (`raw.githubusercontent.com/.../version.json`) via a short-lived `httpx.AsyncClient`, compares the feed's `build_number`/`version` against `APP_BUILD_NUMBER`/`APP_VERSION`, and returns an update-info dict (or `None` when not newer or on any error). `src/app_controller.py:309-317` (`_check_for_updates`) runs it as a background task and flips `state.update_available`/`state.update_data`. `src/components/update_dialog.py` renders the update/up-to-date dialog and launches allow-listed URLs through `core.shared_services.launch_url` → `ft.UrlLauncher`. Allow-list: `github.com`, `raw.githubusercontent.com`, `play.google.com` (update_service.py:23).

## Findings

### F1 · P0 · URL allow-list bypassable via urlsplit backslash (open redirect / allow-list escape)
- **Where:** `src/services/update_service.py:26-37` (`is_allowed_launch_url`); used by `src/components/update_dialog.py:24` (`_launch`) and `src/services/update_service.py:44-47` (`_safe_url`). Verified against `urllib.parse.urlsplit` semantics.
- **What:** Python's `urlsplit` treats `\` as a netloc path separator. `https://evil.com\@github.com` yields `hostname="github.com"` (allowed) while the OS launcher/browser may navigate to `evil.com`. Empirically: `urlsplit("https://evil.com\\@github.com")` → `scheme='https' host='github.com' netloc='evil.com\\@github.com' path=''` (test reproduced). A malicious feed record can therefore pass `is_allowed_launch_url` / `_safe_url` and cause the dialog to launch an arbitrary host. `_safe_url` falls back to `GITHUB_RELEASES_URL` only when `is_allowed_launch_url` says no, so the bypass defeats both call sites.
- **Evidence:** reproduced with `urlsplit` (see `/tmp/test_urlsplit.py` output: `https://evil.com\@github.com` → host `github.com`).
- **Fix / opportunity:** Validate the URL against the allow-list using the same parser the launcher uses, or reject/normalize backslashes and credentials (`userinfo`, `@`) before the host check. Prefer `packaging.util.urlparse`-style or a strict host allow-list that also rejects userinfo/`@` and backslashes. Minimal, architecture-respecting: keep `_ALLOWED_HOSTS` but add a pre-check that rejects any URL containing `\` or `@` in the authority, and compare the *effective* host.
- **Risk if ignored:** P0/P1 — a compromised or malicious feed can trick the app into launching an attacker-controlled URL from the update dialog (user-visible security/compliance defect).

### F2 · P1 · Sync-lambda coroutine bug — "Check for Updates" button never re-checks
- **Where:** `src/components/update_dialog.py:102` (`on_click=lambda _e: _check_again(page)`). `_check_again` is `async def` (line 149). Verified against flet's event dispatch: `flet/controls/base_control.py:468-552` (`_trigger_event`) awaits only `inspect.iscoroutinefunction(event_handler)` handlers; a plain sync `callable` is invoked and **any coroutine it returns is discarded** (base_control.py:548-552).
- **What:** The lambda is a sync callable, so flet calls it, obtains a coroutine object from `_check_again`, and drops it without awaiting or scheduling. The re-check never runs; the button silently does nothing (and an unawaited-coroutine warning may surface at GC time). Flet's own docs show the intended pattern: `on_click=lambda: asyncio.create_task(...)` (page.py:1039).
- **Evidence:** `base_control.py:514-552` branches; line 548 `elif callable(event_handler):` → `event_handler(e)` with no await/create_task of the result.
- **Fix / opportunity:** Change line 102 to `on_click=lambda _e: asyncio.create_task(_check_again(page))` (or register an `async def` handler). Minimal, no new imports beyond `asyncio` (already importable).
- **Risk if ignored:** P1 — user-visible broken behavior: the explicit "Check for Updates" action is non-functional.

### F3 · P2 · Error vs. no-update conflation — failure indistinguishable from "up to date"
- **Where:** `src/services/update_service.py:70-102` (`check_for_update` returns `None` on every `except Exception` path, line 100-102); `src/app_controller.py:309-317` (`_check_for_updates` treats any falsy result as "no update" and returns silently).
- **What:** `check_for_update` returns `None` both when the feed says "no newer build" AND when any exception occurs (network timeout/DNS, non-200, invalid JSON, missing keys). The caller has no way to distinguish offline/failure from genuinely up-to-date, so the user is never informed of a failed check. Broad `except Exception` (line 100) swallows `httpx.HTTPError`, `json.JSONDecodeError`, etc. Module docstring itself promises "silent failure", but the conflation means failure looks identical to success-no-update.
- **Evidence:** `update_service.py:80` (non-200 → None), `80-82` (non-dict → None), `100-102` (any exception → None, logged only at debug); `app_controller.py:314-315` (`if not data: return`).
- **Fix / opportunity:** Return a discriminated result (e.g. `{"update": ...}` | `{"error": ...}` | `None`) or let the caller log/retries; at minimum surface a one-off snack on repeated failure rather than silently presenting "up to date". Respect the "silent failure" design intent but decouple it from the no-update signal.
- **Risk if ignored:** P2 — users cannot tell whether they're on the latest build or the check failed (offline), leading to stale-build uncertainty.

### F4 · P2 · httpx client has timeout but no retries; transient failure silently becomes "no update"
- **Where:** `src/services/update_service.py:75` (`async with httpx.AsyncClient(timeout=4.0, follow_redirects=True)`).
- **What:** `timeout=4.0` is a total timeout (httpx `_client.py:195-214`, `_config.py:246` default 5.0; here 4.0). `follow_redirects=True` with `max_redirects` default 20 (`_client.py:197`, `_config.py:248`). **No retry transport** is configured — httpx performs no automatic retries by default, so a transient blip (DNS, TCP reset, 5xx) fails the whole check and is conflated with "no update" (F3). Client lifetime is correct (context manager closes it). `response.json()` is `jsonlib.loads` (`httpx/_models.py:831`) and can raise `JSONDecodeError`, caught by the broad `except`.
- **Evidence:** httpx `_client.py` init signature; `_config.py:246 DEFAULT_TIMEOUT_CONFIG = Timeout(timeout=5.0)`, `:248 DEFAULT_MAX_REDIRECTS = 20`.
- **Fix / opportunity:** Add a small retry (e.g. `httpx` `Retry`/transport or 1-2 `asyncio` retries on transient `httpx.TransportError`/5xx) inside `check_for_update`, keeping the 4.0s budget. Do not add a new dependency — implement the retry loop manually (dependency set frozen by D-003).
- **Risk if ignored:** P2 — flaky networks cause silent missed update notifications.

### F5 · P3 (UNVERIFIED whether it causes real harm) · Version comparison is int-tuple, not PEP 440 — `packaging` is already installed and unused
- **Where:** `src/services/update_service.py:50-67` (`_release_tuple`, `is_newer`). `APP_VERSION="1.0.0"`, `APP_BUILD_NUMBER=1` in `src/core/constants.py:11-12`.
- **What:** `_release_tuple` splits on `[-+]` then `.` and requires every part `isdigit()`, returning an int tuple compared with `>`. Build number is the primary signal (`int(remote_build) > APP_BUILD_NUMBER`). This is *not* PEP 440: no epoch (`1:0.0`), pre-release (`1.0.0a1` → tuple conversion fails → `None` → treated as not newer), post-release, or local segments. `packaging` 26.3 **is installed** (`.venv/.../packaging-26.3.dist-info`) and provides `packaging.version.parse` for correct PEP 440 comparison; the app uses none of it.
- **Evidence:** `_release_tuple` rejects `"1.0.0a1"` (`"0a1".isdigit()` is False → None). `packaging` present in site-packages (not listed as a dependency the app imports).
- **Fix / opportunity:** Since `APP_VERSION` is simple `1.0.0` and the build number drives the decision, risk is low today. Opportunity: use `packaging.version.parse` for the version leg if the feed ever ships pre/post releases. Zero new dependencies (`packaging` already ships). Label UNVERIFIED whether any feed version currently trips this.
- **Risk if ignored:** P3 — incorrect ordering for non-integer feed versions (e.g. `1.0.0-rc1` vs `1.0.0`); low current impact because `APP_VERSION`/`feed` are simple integers.

### F6 · P3 · `except TypeError, ValueError:` is unusual (comma form) but functionally valid — NOT a defect
- **Where:** `src/services/update_service.py:63` (`is_newer`), `src/components/update_dialog.py:33` (`_dialog_width`).
- **What:** Python 3.14 still accepts `except TypeError, ValueError:` as tuple semantics — it catches **both** `TypeError` and `ValueError` (verified empirically: `int("x")` ValueError and `1+"a"` TypeError both caught; `1/0` ZeroDivisionError propagates). It works, but the bare comma form is non-idiomatic (parenthesized tuple or separate handlers preferred). No bug.
- **Risk if ignored:** none; cosmetic only.

## Verified-good list (checked against `.venv`, so synthesis will not re-open)
- `httpx.AsyncClient(timeout=..., follow_redirects=..., max_redirects=...)` params exist; client closed via context manager (`httpx/_client.py:195-214`).
- `httpx` default `timeout=5.0` (`_config.py:246`), `max_redirects=20` (`_config.py:248`); here `timeout=4.0`, `follow_redirects=True`. Redirect target is the fixed `UPDATE_CONFIG_URL` (no user-controlled redirect → no open-redirect via redirects).
- `response.json()` = `jsonlib.loads(self.content)` (`httpx/_models.py:831`); `JSONDecodeError` is a subclass of `ValueError`, caught by the broad handler (but conflated, F3).
- `page.run_task` requires `inspect.iscoroutinefunction(handler)` and schedules via `run_coroutine_threadsafe` (`flet/controls/page.py:929-943`).
- `page.show_dialog(dialog: DialogControl)` / `pop_dialog()` (`flet/controls/base_page.py:402,427`); `ft.SnackBar` subclasses `DialogControl` (`flet/controls/material/snack_bar.py:155`), so `show_dialog(ft.SnackBar(...))` is type-correct and even shown in SnackBar's own docstring example.
- `page.platform.is_mobile()` → True for `IOS`/`ANDROID` (`flet/controls/types.py:843-847`).
- `ft.ScrollMode.AUTO` (`types.py:692`), `ft.MarkdownExtensionSet.GITHUB_WEB` (`flet/controls/core/markdown.py:46`).
- All `ft.Icons.*` used (`CAMPAIGN_ROUNDED`, `ROCKET_LAUNCH_ROUNDED`, `VERIFIED_ROUNDED`, `SHOP_ROUNDED`, `DOWNLOAD_ROUNDED`) exist (verified via import).
- `ft.AlertDialog(modal=...)` accepts `modal` (`page.py` signature includes `modal`).
- `data.get("mandatory") is True` is a strict bool check (good).
- `page.width` is `Optional[Number]`; `int(None)` raises `TypeError`, caught by the `except TypeError, ValueError` in `_dialog_width` (defensive, handled).
- `except TypeError, ValueError:` catches both exceptions (valid Python 3 tuple semantics) — not a bug (F6).

## Missed capabilities
(n/a — this is a service audit, not a dependency audit. The one relevant note: `packaging` 26.3 is installed and provides PEP 440 version comparison that `_release_tuple` hand-rolls poorly — see F5.)

## Unverified
- Whether any real feed/version string trips the non-PEP-440 `_release_tuple` (F5) — no `version.json` is present in a clean clone (`tests/test_version_sync.py:34-37` skips when absent).
- Whether `page.show_dialog(ft.SnackBar(...))` renders correctly on the target Android/web platforms (type-correct per flet source; runtime behavior platform-dependent) — UNVERIFIED.
- Whether an unawaited-coroutine warning actually surfaces for the broken `_check_again` lambda on this Python/flet combination — the discard is proven in source (base_control.py:548-552); the warning is implementation-dependent — UNVERIFIED.
- Whether a real browser/OS launcher navigates to `evil.com` for `https://evil.com\@github.com` (urlsplit host is `github.com`, confirmed; launcher-side parsing is not part of the installed Python env) — the urlsplit/launcher mismatch is the defect class; confirmed at the Python level — UNVERIFIED at OS-launcher level.

## Tests
No test file targets `src/services/update_service.py` or `src/components/update_dialog.py` (test listing: `test_ads`, `test_core`, `test_flet_api_guard`, `test_imports_vs_deps`, `test_proot_surfaces`, `test_sessions`, `test_terminal_wiring`, `test_ui_reactive`, `test_version_sync`, `check_flet_api`). The update-service behavior (allow-list bypass, coroutine button, error conflation, retries) is **uncovered by tests**.
