# httpx 0.28.1 utilization — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `docs/dependency-studies/httpx.md`; `src/services/update_service.py`; `src/app_controller.py`; `src/components/update_dialog.py`; `src/components/app_header.py`; `src/core/constants.py`; `src/core/state.py`; `src/main.py`; `src/screens/views.py`; `pyproject.toml`; `uv.lock`; `.venv/Lib/site-packages/httpx/`; `.venv/Lib/site-packages/flet/controls/base_control.py`; `.venv/Lib/site-packages/flet/auth/`; `.venv/Lib/site-packages/httpcore/_async/http11.py` · **Date:** 2026-10-20

## What it does / how the app uses it

`services/update_service.py` is the app's only httpx consumer. `check_for_update()` lazily imports httpx and performs one `GET` against `UPDATE_CONFIG_URL` (raw.githubusercontent.com) with a fresh `httpx.AsyncClient(timeout=4.0, follow_redirects=True)` (`src/services/update_service.py:70-80`), manually gates on status 200, calls `response.json()`, shape-checks/truncates fields, and returns a dict or `None`. It is invoked once at startup from a background task (`src/app_controller.py:88,309-317`) and from the "Check for Updates" button in the up-to-date dialog (`src/components/update_dialog.py:102,149-161`). Navigation/launch URLs from the feed are allow-listed separately (`src/services/update_service.py:23-37`; `src/components/update_dialog.py:23-26`).

Flet's own httpx use is separate and dormant: flet declares it for OAuth (`flet-1.0.4.dist-info/METADATA:15`) and imports it lazily only in `flet/auth/authorization_service.py:119,207,248` and `flet/auth/providers/github_oauth_provider.py:43,76`. This app ships no login flow (`pyproject.toml:60-63`; no `page.login` in `src/`), so **all** httpx traffic in this app is `update_service.py`'s. The `"httpx"` entry at `src/screens/views.py:33` is only a third-party license-list name, not a usage.

## Findings

### F1 · P1 · "Check for Updates" button never runs the check

- **Where:** `src/components/update_dialog.py:102` and `:149`; `.venv/Lib/site-packages/flet/controls/base_control.py:516-521` vs `:548-552`.
- **What:** `on_click=lambda _e: _check_again(page)` is a *synchronous* callable that returns a coroutine object. Flet's dispatcher awaits only `inspect.iscoroutinefunction(event_handler)` (`base_control.py:516-521`); a plain callable falls into the branch at `:548-552` which calls it and discards the return value. The coroutine is never scheduled, so the manual update check is a no-op (plus a `RuntimeWarning: coroutine ... was never awaited`).
- **Evidence:** `update_dialog.py:102` — `ft.TextButton("Check for Updates", on_click=lambda _e: _check_again(page))`; `_check_again` is `async def` at `:149`. Runtime predicate check: `inspect.iscoroutinefunction(lambda _e: _check_again(page))` → `False`; calling it returns `<class 'coroutine'>`. The house pattern elsewhere wraps async work explicitly: `src/screens/views.py:392-393` — `def _save_token(): page.run_task(methods.set_docker_token, token)`.
- **Fix / opportunity:** `on_click=lambda _e: page.run_task(_check_again, page)` (house pattern), or pass an `async def _on_check(_e): await _check_again(page)` directly (Flet does await coroutine functions). Same one-line change for any other async handler passed through a sync lambda.
- **Risk if ignored:** the only manual re-check silently does nothing. If the startup check failed (offline, transient timeout), the user is permanently stuck with the bundled "You're up to date" view and can never learn about a newer release through the UI.

### F2 · P2 · Network failure is reported to the user as "up to date"

- **Where:** `src/services/update_service.py:77-79` and `:100-102`; `src/components/update_dialog.py:157-161`; `src/main.py:12-16`.
- **What:** every non-200 response and every exception returns `None`, exactly like "no newer build". `_check_again` then shows `"{APP_NAME} v{APP_VERSION} is up to date"`. Failures are logged at `logger.debug` (`update_service.py:101`) while the app configures the root logger at `INFO` (`main.py:13`), so release builds produce no diagnostic at all.
- **Evidence:** `update_service.py:77-79` returns `None` for any status != 200; `:100-102` catches `Exception`, logs debug, returns `None`; `update_dialog.py:158-161` — `if result: ... else: page.show_dialog(ft.SnackBar(ft.Text(f"{APP_NAME} v{APP_VERSION} is up to date")))`.
- **Fix / opportunity:** make the result tri-state (e.g. `{"status": "update"|"current"|"error", ...}` or raise a typed `UpdateCheckError` and return `None` only for "current"). The dialog then shows "Couldn't check for updates" on error and never asserts freshness it did not verify.
- **Risk if ignored:** false assurance of being current; a mandatory update can be missed indefinitely and the user has no signal that the check failed.

### F3 · P2 · No response size cap; full body buffered and JSON parsed on the event loop

- **Where:** `src/services/update_service.py:76-80`; `.venv/Lib/site-packages/httpx/_client.py:1594,1636-1637`; `.venv/Lib/site-packages/httpx/_models.py:831-832`.
- **What:** `client.get(...)` uses `send(stream=False)`, which calls `await response.aread()` and loads the entire (already gzip/deflate-decoded) body into memory before returning (`_client.py:1636-1637`). There is no `Content-Length` check, no byte cap, and `response.json()` runs `jsonlib.loads(self.content)` synchronously on the Flet session event loop (`_models.py:831-832`). The default `Accept-Encoding` advertises `gzip, deflate` (verified at runtime; `_client.py:120`), so a small compressed body can expand to a very large buffer. The module docstring's "length caps" (`update_service.py:3-6`) only truncate individual output fields (`_safe_text`, `:40-41,91-95`), not the response body.
- **Evidence:** installed source above; feed `version.json` is ~0.5 KB (`version.json:1-10`), so a 1 MiB cap is orders of magnitude of headroom.
- **Fix / opportunity:** `async with client.stream("GET", config_url) as response:` then accumulate `response.aiter_bytes()` with a hard cap (abort > 1 MiB) before decoding; or read `Content-Length` first and use capped `aread()`. `Response.aiter_bytes` is at `_models.py:982`; `num_bytes_downloaded` at `:856`.
- **Risk if ignored:** a compromised/incorrect endpoint or a decompression bomb can OOM the Android process (app kill) or stall rendering during the synchronous parse. Low likelihood for a GitHub-owned feed, but the mitigation is ~10 lines.

### F4 · P2 · No retry and one 4 s budget per phase; transient failures silently drop the check

- **Where:** `src/services/update_service.py:75`; `.venv/Lib/site-packages/httpx/_config.py:72-88,246`; `.venv/Lib/site-packages/httpx/_transports/default.py:291`.
- **What:** `timeout=4.0` becomes `Timeout(connect=4.0, read=4.0, write=4.0, pool=4.0)` (runtime `as_dict()` verified). There is no retry anywhere: httpx ships none for timeouts/5xx, and `AsyncHTTPTransport(retries=N)` (`_transports/default.py:291`) only retries connection establishment and requires passing a custom `transport=` (which in turn disables automatic env-proxy mounting, `_client.py:687-699`). A single DNS blip, TLS stall, or 5xx therefore suppresses the update notice for the whole session.
- **Evidence:** source refs above; the exception taxonomy to gate on is `TimeoutException`/`NetworkError`/5xx (`httpx/_exceptions.py:132-206,258`).
- **Fix / opportunity:** give the read phase more headroom than connect (e.g. `timeout=httpx.Timeout(10.0, connect=5.0)`) and wrap the request in a 2–3 attempt loop with short jittered `asyncio.sleep` backoff, retrying only `TimeoutException`, `ConnectError`/`NetworkError`, and 5xx (classify via `response.status_code` or `raise_for_status()`). Do not retry `HTTPStatusError` 4xx, `TooManyRedirects`, or `DecodingError`.
- **Risk if ignored:** update checks fail on exactly the flaky mobile networks the app targets, silently and repeatedly.

### F5 · P3 · A fresh client per check; no pooling, no injection seam, no test coverage

- **Where:** `src/services/update_service.py:75`; `.venv/Lib/site-packages/httpx/_client.py:1311-1313,1353`; `.venv/Lib/site-packages/httpx/_transports/mock.py:15-16`.
- **What:** each call constructs and tears down an `AsyncClient`. httpx explicitly supports sharing one `AsyncClient` between tasks (`_client.py:1311-1313`: "It can be shared between tasks"), and transport construction eagerly builds an SSL context from certifi (`_transports/default.py:291-300`, `_config.py:40`), so every check pays pool + TLS-context setup and a fresh handshake. Because the client is hard-coded, `MockTransport` cannot be injected and there are no tests for this service (`grep` over `tests/` finds no `check_for_update`/`update_service` references).
- **Evidence:** refs above; `tests/` has no update-service test file.
- **Fix / opportunity:** add an optional `client: httpx.AsyncClient | None = None` parameter (construct-and-close only when `None`), or own one client in `AppController` and close it from `page.on_close` (`src/main.py:24-31` closes sessions but nothing HTTP). This enables keep-alive across the startup + manual checks and lets tests pass `httpx.MockTransport` (`_transports/mock.py:15-29`) without sockets.
- **Risk if ignored:** one extra TLS handshake per check (minor radio/battery cost) and this parser stays the only network service with no hermetic test path.

### F6 · P3 · Redirects may downgrade HTTPS to HTTP; final host is never validated

- **Where:** `src/services/update_service.py:75-80`; `.venv/Lib/site-packages/httpx/_client.py:517-551`.
- **What:** `follow_redirects=True` follows `Location` through `_redirect_url`, which imposes no scheme restriction (`_client.py:517-551`). An `https://` endpoint that answers `302 Location: http://...` is fetched in cleartext. The app never checks `response.url` after the redirect, so the update payload (version, mandatory flag, notes) can come from any host/scheme the original server names. `_redirect_headers` only strips `Authorization` on cross-origin hops (`_client.py:546-556`); no auth is used here.
- **Evidence:** live check with the installed package: first request to `https://raw.githubusercontent.com/a/version.json`, handler returns `302` with `Location: http://raw.githubusercontent.com/x/version.json`; the client issued the second request over `http://` and returned 200 (command output: `redirect chain: ['https://raw.githubusercontent.com/a/version.json', 'http://raw.githubusercontent.com/x/version.json']`).
- **Fix / opportunity:** after `client.get`, require `response.url.scheme == "https"` and `response.url.host` inside the same allow-list used for launch URLs (`src/services/update_service.py:23-37`), otherwise treat the check as failed. Alternatively set `follow_redirects=False` — the pinned raw URL is not expected to redirect; a redirect then fails the status gate.
- **Risk if ignored:** an active network attacker who can influence a redirect can tamper with update metadata over plaintext. Launch targets remain host-allow-listed, so the impact is limited to version/mandatory/notes social engineering, but the "https-only" claim in the module docstring (`update_service.py:3-6`) is not actually enforced for the fetch itself.

### F7 · P3 · No overall deadline and no cancellation handle for the background check

- **Where:** `src/app_controller.py:88`; `.venv/Lib/site-packages/httpx/_config.py:72-88`; `.venv/Lib/site-packages/httpcore/_async/http11.py:173-177`.
- **What:** `Timeout.read` is applied per socket read event (`httpcore/_async/http11.py:173-177`), not as a deadline for the whole request; each redirect hop also gets a fresh budget (`.venv/Lib/site-packages/httpx/_client.py:1679-1711`). A server that trickles one byte per few seconds can keep the task alive indefinitely. `page.run_task(self._check_for_updates)` at `app_controller.py:88` discards the returned `Future`, and `page.on_close` (`src/main.py:24-31`) only closes terminal sessions, so the task cannot be cancelled on teardown.
- **Evidence:** refs above. The UI itself is not blocked: the check runs as a background task via `page.run_task` (`flet/controls/page.py:929-954`, `asyncio.run_coroutine_threadsafe`), and `async with AsyncClient` closes the transport on normal/cancelled exit (`_client.py:1990-2022`).
- **Fix / opportunity:** wrap the body of `check_for_update` in `async with asyncio.timeout(15):` (or keep the per-phase timeouts and add a total deadline), and store the `Future` returned by `run_task` so `page.on_close` can `cancel()` it. Keep `except Exception` as-is — `CancelledError` is a `BaseException` and already propagates (runtime MRO verified).
- **Risk if ignored:** a pathological/drip-fed response leaves a task and socket alive for the session; user-visible impact is a lingering connection/battery cost, not a frozen UI.

## Missed capabilities (dependency audits only)

- **Streaming with a hard size cap** · API: `AsyncClient.stream()` (`httpx/_client.py:1543`), `Response.aiter_bytes()` (`_models.py:982`), `Response.num_bytes_downloaded` (`_models.py:856`) · Integration: `update_service.py:76` replace `client.get` with `async with client.stream(...)` and abort past a 1 MiB accumulator · Value: bounds memory and lets JSON parsing happen only on capped bytes; fixes F3. Cost: ~10 lines, no new dependency.
- **App-level retry/backoff** · API: no built-in retry; `AsyncHTTPTransport(retries=)` (`_transports/default.py:291`) is connect-only and replaces env-proxy mounting · Integration: small loop around the request in `check_for_update` using `asyncio.sleep` and the `TimeoutException`/`NetworkError` hierarchy (`_exceptions.py:132-206`) · Value: fixes F4; survives mobile-network transients. Cost: ~15 lines; no exponential-backoff library exists in the frozen dependency set, so keep it simple (2 retries, fixed/jittered 300–700 ms).
- **Shared, injectable client** · API: `AsyncClient` is documented as shareable between tasks (`_client.py:1311-1313`); `MockTransport` (`_transports/mock.py:15-29`) · Integration: optional `client=` parameter on `check_for_update`, or one client owned by `AppController` and closed from `page.on_close` · Value: keep-alive across the two checks, one TLS context, and offline contract tests for `is_newer`/feed shape. Cost: small signature/lifecycle change; beware module-level globals across Flet sessions.
- **Per-phase `Timeout`** · API: `httpx.Timeout(connect=, read=, write=, pool=)` (`_config.py:72-88`; default `DEFAULT_TIMEOUT_CONFIG` at `:246`) · Integration: `update_service.py:75` replace `timeout=4.0` with `httpx.Timeout(10.0, connect=5.0)` (or similar) · Value: fail fast on an unreachable host while tolerating a slow cellular read; part of F4. Cost: one line.
- **Typed status handling** · API: `Response.raise_for_status()` (`_models.py:794`) and `HTTPStatusError` (`_exceptions.py:258`) · Integration: replace the manual `status_code != 200` gate at `update_service.py:77-79` when implementing F2/F4 so 404 (feed missing), 429 (rate limit), and 5xx are distinguishable/retryable · Value: enables a correct retry policy and honest error message. Cost: a few lines; note `raise_for_status` treats any 2xx as success, slightly broader than the current 200-only gate.
- **Event hooks for diagnostics** · API: `event_hooks={"request": [...], "response": [...]}` (`_client.py:216-217`; async invocation `:1691-1696`) · Integration: optional `event_hooks` on the client to log final status/latency at debug in dev builds · Value: makes silent failures observable without sprinkling logging through the parser. Cost: low, but not needed if F2 returns a tri-state result.
- **Conditional GET** · API: plain request header `If-None-Match`/`If-Modified-Since` (no httpx-specific API) · Integration: send GitHub's `ETag` on subsequent checks and accept 304 as "current" · Value: saves bandwidth and rate-limit budget; low impact for a ~0.5 KB file. Cost: state persistence for the ETag; optional.

## Verified-good list

- Installed `httpx` is **0.28.1** (`python -c "httpx.__version__"`) and the lock agrees (`uv.lock:299-300`); `pyproject.toml:12` declares `httpx>=0.28.1`. Pure-Python package, so the Android packaging path is unchanged from the study.
- Only our consumer imports httpx in `src/` (`update_service.py:73-75`); flet's OAuth imports (`flet/auth/authorization_service.py:119,207,248`; `github_oauth_provider.py:43,76`) are dormant because the app has no login flow.
- `AsyncClient(timeout=4.0, follow_redirects=True)` matches the installed constructor (`_client.py:1353-1367`); `client.get` (`_client.py:1751`), `response.status_code`, and `response.json()` (`_models.py:831`) all exist with the expected semantics.
- The check is genuinely async and does not block rendering: `page.run_task` schedules onto the session loop via `asyncio.run_coroutine_threadsafe` (`flet/controls/page.py:929-954`), and no sync `httpx.Client` exists anywhere in `src/`.
- Client lifetime is safe in the normal path: `async with` closes transport and proxy mounts (`_client.py:1978-2022`); cancellation is not swallowed because `except Exception` at `update_service.py:100` excludes `CancelledError` (`asyncio.CancelledError.__mro__` verified: `BaseException`).
- TLS verification is on by default and anchored to certifi: `verify=True` → `ssl.create_default_context(cafile=certifi.where())` (`_config.py:23-40`); certifi 2026.7.22 is installed and locked (`uv.lock:44-45`). No `verify=False` or custom SSL context exists in `src/`.
- `timeout=4.0` is applied to all four phases (`Timeout(4.0).as_dict()` → `connect/read/write/pool = 4.0`), not silently dropped.
- Parsing is defensive: non-dict payloads return `None` (`update_service.py:81-82`), build-number conversion catches `TypeError`/`ValueError` (`:60-64`), malformed JSON raises `json.JSONDecodeError` (a `ValueError`, runtime verified) which the broad handler contains, every string field is truncated (`:91-95`), and output URLs are scheme/host allow-listed (`:26-47,97-98`).
- Redirect mechanics themselves are sound: default `max_redirects=20` (`_config.py:248`), a loop raises `TooManyRedirects` (caught), and httpx strips `Authorization` across origins (`_client.py:546-556`) — no auth header is used here in any case.
- `except TypeError, ValueError:` at `update_service.py:63` (PEP 758, no parentheses) is valid on this project's pinned Python 3.14 (`pyproject.toml:8`; `.python-version` = `3.14`; CI `UV_PYTHON: "3.14"`; runtime check caught both types). It would be a `SyntaxError` on Python ≤3.13, but 3.14 is the declared runtime and ruff target (`pyproject.toml:101`).
- The `httpx` import is function-local (`update_service.py:73`), so a missing/broken httpx install degrades to "no update" rather than breaking app import.

## Unverified

- On-device Android behavior of certifi/store and radio timeouts — no device run was performed; this report only verifies the desktop `.venv` source and config.
- Whether Flet cancels outstanding `run_task` futures when a session closes — the Future is discarded (`app_controller.py:88`) and `page.on_close` (`main.py:24-31`) does not touch it; I did not trace the session teardown implementation.
- Actual behavior of the live feed (`raw.githubusercontent.com/Nwokike/proot-distro/main/version.json`): no network request was made during this audit. Redirect/downgrade behavior was proven with `httpx.MockTransport`, not the real host.
- Real-world failure rate/body sizes of the feed (no telemetry); the 1 MiB cap recommendation is based on the repo's `version.json` being ~0.5 KB.
