# httpx 0.28.1 — exhaustive API reference

Verified 2026-10-16 against the INSTALLED source in `.venv/Lib/site-packages/httpx` (live introspection via `.venv/Scripts/python.exe -c` + `grep -n` line refs). Project context: `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md`. Flet app; flet stays 1.0.4 (D-010). **Anti-hallucination rule (owner-mandated):** every API claim below is verified against installed source (`file:line`) or live introspection; anything not verifiable is labeled **unverified**. Signatures are simplified from live `inspect.signature` output (defaults shown; `UseClientDefault` sentinel abbreviated as `USE_CLIENT_DEFAULT`).

## 1. Identity

- Version `0.28.1` (`httpx/__version__.py:1-3`: `__title__`, `__description__`, `__version__ = "0.28.1"`).
- License **BSD-3-Clause** (`httpx-0.28.1.dist-info/METADATA:10`, `License: BSD-3-Clause`; `licenses/LICENSE.md` ships in dist-info).
- `py.typed` marker ships at package root — typed package.
- **Pure Python.** Package tree is `.py` only: `__init__.py`, `__version__.py`, `_api.py`, `_auth.py`, `_client.py`, `_config.py`, `_content.py`, `_decoders.py`, `_exceptions.py`, `_main.py`, `_models.py`, `_multipart.py`, `_status_codes.py`, `_types.py`, `_urlparse.py`, `_urls.py`, `_utils.py`, plus `_transports/` (`__init__.py`, `asgi.py`, `base.py`, `default.py`, `mock.py`, `wsgi.py`). No `.so`/`.pyd` found.
- Hard runtime deps (`httpx-0.28.1.dist-info/METADATA`): `anyio`, `certifi`, `httpcore==1.*`, `idna`. Optional extras: `brotli` (`brotli`/`brotlicffi`), `cli` (`click==8.*`, `pygments==2.*`, `rich<14,>=10`), `http2` (`h2<5,>=3`), `socks` (`socksio==1.*`), `zstd` (`zstandard>=0.18.0`). `Requires-Python: >=3.8`.
- Optionals present in OUR venv: `click 8.5.0`, `pygments 2.21.0`, `rich 15.0.0` (so the `httpx` CLI works). Absent: `h2`, `socksio`, `brotli`, `zstandard` — HTTP/2, SOCKS, brotli/zstd decoding paths are inert here.
- Role here: flet's OAuth HTTP client. Flet declares it as `httpx>=0.28.1; platform_system != "Emscripten"` (`flet-1.0.4.dist-info/METADATA:15`) — the Emscripten marker is what dep-httpx-cluster.md records. Console entry point: `httpx = httpx:main` (`httpx-0.28.1.dist-info/entry_points.txt`).
- Top-level `__all__` (`httpx/__init__.py:32-105`): `__description__`, `__title__`, `__version__`, `ASGITransport`, `AsyncBaseTransport`, `AsyncByteStream`, `AsyncClient`, `AsyncHTTPTransport`, `Auth`, `BaseTransport`, `BasicAuth`, `ByteStream`, `Client`, `CloseError`, `codes`, `ConnectError`, `ConnectTimeout`, `CookieConflict`, `Cookies`, `create_ssl_context`, `DecodingError`, `delete`, `DigestAuth`, `get`, `head`, `Headers`, `HTTPError`, `HTTPStatusError`, `HTTPTransport`, `InvalidURL`, `Limits`, `LocalProtocolError`, `main`, `MockTransport`, `NetRCAuth`, `NetworkError`, `options`, `patch`, `PoolTimeout`, `post`, `ProtocolError`, `Proxy`, `ProxyError`, `put`, `QueryParams`, `ReadError`, `ReadTimeout`, `RemoteProtocolError`, `request`, `Request`, `RequestError`, `RequestNotRead`, `Response`, `ResponseNotRead`, `stream`, `StreamClosed`, `StreamConsumed`, `StreamError`, `SyncByteStream`, `Timeout`, `TimeoutException`, `TooManyRedirects`, `TransportError`, `UnsupportedProtocol`, `URL`, `USE_CLIENT_DEFAULT`, `WriteError`, `WriteTimeout`, `WSGITransport`.

## 2. `Client` / `AsyncClient` — constructors (EVERY param)

`Client.__init__` (`httpx/_client.py:639`) and `AsyncClient.__init__` (`httpx/_client.py:1373`) take the same keyword-only params (live-verified; only `transport`/`mounts` types differ):

```python
Client(*, auth=None, params=None, headers=None, cookies=None,
       verify=True, cert=None, trust_env=True,
       http1=True, http2=False, proxy=None, mounts=None,
       timeout=Timeout(timeout=5.0), follow_redirects=False,
       limits=Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=5.0),
       max_redirects=20, event_hooks=None, base_url="",
       transport=None, default_encoding="utf-8")
```

| Param | Meaning |
|---|---|
| `auth` | Default auth (`BasicAuth`/`DigestAuth`/custom `Auth`/callable). Per-request override wins |
| `params` | Default query params merged into every request (`_merge_queryparams`, `_client.py:433`) |
| `headers` | Default headers merged into every request (`_merge_headers`, `_client.py:424`) |
| `cookies` | Default cookies jar (`_merge_cookies`, `_client.py:413`) |
| `verify` | `True` (certifi CA) / `False` (skip) / `SSLContext` / CA-bundle path str |
| `cert` | Client-side cert (path or `(cert, key)` tuple) — passed to transport |
| `trust_env` | Honor `SSL_CERT_FILE`/`SSL_CERT_DIR` + proxy env vars (default `True`; `_client.py:201,219`) |
| `http1` / `http2` | Protocol toggles (`http2=True` needs the `h2` extra — absent here) |
| `proxy` | `ProxyTypes`: URL str, or `Proxy` instance (see §5) |
| `mounts` | `Mapping[str, Transport | None]` — URL-pattern → transport pinning; `None` value disables a pattern |
| `timeout` | Default `TimeoutTypes` (`Timeout(timeout=5.0)` = 5 s on all four operations) |
| `follow_redirects` | Follow 301/302/303/307/308 automatically (default `False`; flet's OAuth passes `True`) |
| `limits` | Connection-pool limits (see §5) |
| `max_redirects` | Cap redirect hops (default 20; exceeded → `TooManyRedirects`) |
| `event_hooks` | `{"request": [...], "response": [...]}` — callables run around each request (`_client.py:216-217, 976-981`) |
| `base_url` | Prefix for relative-URL requests (trailing-slash enforced, `_client.py:234`) |
| `transport` | Custom transport (replaces the default pool; disables env-proxy auto-mount, `_client.py:685`) |
| `default_encoding` | Fallback response decoding (`str` or callable) |

Settable properties after construction (verified `dir()` + setters at `_client.py:254-337`): `timeout`, `event_hooks`, `auth`, `base_url`, `headers`, `cookies`, `params`, plus read-only `is_closed`, `trust_env`.

## 3. `Client` / `AsyncClient` — EVERY method

Verb signatures are identical on both classes except `stream()` returns `Iterator[Response]` (sync) vs `AsyncIterator[Response]` (async), and closing is `close()` vs `aclose()` (all live-verified):

```python
Client.build_request(method, url, *, content=None, data=None, files=None, json=None,
                     params=None, headers=None, cookies=None,
                     timeout=USE_CLIENT_DEFAULT, extensions=None) -> Request   # _client.py:340
Client.request(method, url, *, content=None, data=None, files=None, json=None,
               params=None, headers=None, cookies=None, auth=USE_CLIENT_DEFAULT,
               follow_redirects=USE_CLIENT_DEFAULT, timeout=USE_CLIENT_DEFAULT,
               extensions=None) -> Response                                    # _client.py:771
Client.stream(method, url, *same-as-request*) -> Iterator[Response]             # context manager; body via iter_bytes
Client.send(request, *, stream=False, auth=USE_CLIENT_DEFAULT,
            follow_redirects=USE_CLIENT_DEFAULT) -> Response
Client.get(url, *, params=None, headers=None, cookies=None, auth=USE_CLIENT_DEFAULT,
           follow_redirects=USE_CLIENT_DEFAULT, timeout=USE_CLIENT_DEFAULT, extensions=None) -> Response
Client.options/head/delete(url, *same-as-get*) -> Response
Client.post/put/patch(url, *, content=None, data=None, files=None, json=None, *same-as-get*) -> Response
Client.close() -> None                       # AsyncClient.aclose() instead
```

Body kwargs: `content=` (bytes/str/iterable), `data=` (form dict), `files=` (multipart), `json=` (auto-serialized + content-type). `USE_CLIENT_DEFAULT` sentinel (`_client.py:94`) means "fall back to the client-level setting". `send()` takes a prebuilt `Request` (from `build_request`); `stream=True` leaves the body unread for manual iteration. Redirect-following verbs (303→GET, 302→GET except HEAD, POST+301→GET) live in `_redirect_method` (`_client.py:494`); relative `Location` join + fragment preservation in `_redirect_url` (`_client.py:517`); cross-origin `Authorization`-header stripping on redirect hops in `_redirect_headers` (`_client.py:546-556`, `headers.pop("Authorization", None)` when origins differ) — this is the built-in twin of upstream's hand-rolled Bearer stripper (§11).
- Closing semantics: `with Client(...) as c:` / `async with AsyncClient(...) as c:` close the pool on exit; `is_closed` property (`_client.py:224`) reports state; using a closed client raises (re-open by constructing a new one — there is no `open()`).
- `extensions=` dict (`RequestExtensions`) passes per-request transport hints (e.g. timeout overrides flow through `_set_timeout`, `_client.py:584`) without touching client defaults.

## 4. `Request` / `Response`

`Request(method, url, *, params=None, headers=None, cookies=None, content=None, data=None, files=None, json=None, stream=None, extensions=None)` (`_models.py:382`). Notes: `method` is upper-cased; `cookies=` is folded into the `Cookie` header (`_models.py:382-430` region); a `ByteStream` body is eagerly `read()`, other streams stay lazy. Members: `.method`, `.url`, `.headers`, `.stream`, `.extensions`, `.content` (property), `.read() -> bytes`, `.aread() -> bytes` (live-verified).

`Response(status_code, *, headers=None, content=None, text=None, html=None, json=None, stream=None, request=None, extensions=None, history=None, default_encoding="utf-8")` (`_models.py:515`). Key members (live-verified):

```python
Response.read() -> bytes | Response.aread() -> bytes        # load body
Response.iter_bytes(chunk_size=None) / .aiter_bytes(...)     # streaming download
Response.iter_text(chunk_size=None) / .aiter_text(...)
Response.iter_lines() / .aiter_lines()
Response.iter_raw(chunk_size=None) / .aiter_raw(...)         # undecoded bytes
Response.json(**kwargs) | .text (property) | .content (property)
Response.raise_for_status() -> Response                      # raises HTTPStatusError
Response.close() / .aclose()
```

Flags/properties: `.status_code`, `.headers`, `.cookies`, `.url`, `.request`, `.history` (redirect chain), `.elapsed`, `.http_version`, `.reason_phrase`, `.encoding`, `.charset_encoding`, `.num_bytes_downloaded`, `.links`, `.is_success/.is_redirect/.is_client_error/.is_server_error/.is_error/.is_informational`, `.has_redirect_location`. Unread-body access raises `ResponseNotRead`; double-read raises `StreamConsumed`; use-after-close raises `StreamClosed` (see §8).

## 5. `URL` / `QueryParams` / `Headers` / `Cookies` / `Timeout` / `Limits` / `Proxy`

- `URL(url="", **kwargs)` (`_urls.py:15`). Props: `.scheme`, `.host`, `.port`, `.path`, `.query`, `.fragment`, `.username`, `.password`, `.userinfo`, `.netloc`, `.raw_*` variants, `.params`, `.is_absolute_url`, `.is_relative_url`. Methods: `.copy_with(**kwargs)`, `.copy_set_param/.copy_add_param/.copy_remove_param/.copy_merge_params`, `.join(relative)`, (all live-verified via `dir()`).
- `QueryParams(*args, **kwargs)` (`_urls.py:420`, a `Mapping`): `.get/.get_list/.keys/.values/.items/.multi_items`, `.set/.add/.remove/.merge/.update` (live-verified).
- `Headers(headers=None, encoding=None)` (`_models.py:139`, a `MutableMapping`, case-insensitive): `.get/.get_list/.multi_items/.keys/.values/.items/.encoding/.copy`, `__getitem__/__setitem__` (live-verified).
- `Cookies(cookies=None)` (`_models.py:1079`, a `MutableMapping`): `.set/.get/.delete/.clear/.pop/.popitem/.setdefault/.update/.keys/.values/.items`, `.extract_cookies(response)`, `.set_cookie_header(request)` (live-verified).
- `Timeout(timeout=UNSET, *, connect=UNSET, read=UNSET, write=UNSET, pool=UNSET)` (`_config.py:72`; docstring usage at `_config.py:72-88`). Accepts a float (all four), a 2–4 tuple, or another `Timeout`. Client default is `Timeout(timeout=5.0)`.
- `Limits(*, max_connections=None, max_keepalive_connections=None, keepalive_expiry=5.0)` (`_config.py:159`); client default `Limits(100, 20, 5.0)`.
- `Proxy(url, *, ssl_context=None, auth=None, headers=None)` (`_config.py:201`); `auth` is a `(username, password)` tuple. `create_ssl_context(verify=True, cert=None, trust_env=True) -> ssl.SSLContext` (`_config.py:26`): honors `SSL_CERT_FILE`/`SSL_CERT_DIR` only when `trust_env` is true (`_config.py:34-37`).
- `Timeout.as_dict() -> dict[str, float | None]` (live-verified) returns `{"connect":…, "read":…, "write":…, "pool":…}`; instance attrs `.connect/.read/.write/.pool` (verified `Timeout(5.0).connect == 5.0` etc.).
- `Limits` nuance: bare `Limits()` defaults to `(max_connections=None, max_keepalive_connections=None, keepalive_expiry=5.0)` (live-verified), but the CLIENT default is the explicit `Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=5.0)` — so an unconfigured client caps at 100 total / 20 keep-alive with 5 s expiry.
- `Cookies.set(name, value, domain="", path="/") -> None`, `Cookies.extract_cookies(response) -> None` (live-verified); `Headers.get_list(key, split_commas=False) -> list[str]`; `QueryParams.get_list(key) -> list[str]`; `URL.copy_set_param(key, value=None) -> URL`, `URL.join(url) -> URL` (all live-verified).
- Response introspection extras (`_models.py` line refs): `.elapsed -> datetime.timedelta` with setter (`:579,592`), `.num_bytes_downloaded -> int` (`:856-857`, incremented per chunk at `:947-952`), `.links -> dict` for `Link`-header parsing (`:842`), `.charset_encoding -> str | None` (`:689`), `.encoding` has both getter and setter (`_models.py:167,192` Headers-side; `:653,675` Response-side).

### 5b. Type aliases (`httpx/_types.py:1-70`, verified by source read)

These are what the signatures above abbreviate: `URLTypes = URL | str`; `QueryParamTypes` (QueryParams | mapping | list-of-tuples | tuple-of-tuples | str | bytes); `HeaderTypes` (Headers | str/bytes mappings | sequences of pairs); `CookieTypes` (Cookies | CookieJar | dict | list-of-tuples); `TimeoutTypes` (float | 4-tuple | Timeout | None); `ProxyTypes` (URL | str | Proxy); `CertTypes` (str | 2-tuple | 3-tuple); `AuthTypes` ((user, pass) tuple | callable | Auth); `RequestContent` (str | bytes | sync/async byte iterable); `ResponseContent` (+ same); `ResponseExtensions = Mapping[str, Any]`; `PrimitiveData = str | int | float | bool | None`.

## 6. Transports

Base (`_transports/base.py:26,77`): `BaseTransport.handle_request(request) -> Response`; `AsyncBaseTransport.handle_async_request(request) -> Response`. Concrete (ctor sigs live-verified):

```python
HTTPTransport(verify=True, cert=None, trust_env=True, http1=True, http2=False,
              limits=Limits(...), proxy=None, uds=None, local_address=None,
              retries=0, socket_options=None)          # _transports/default.py
AsyncHTTPTransport(*same*)                             # async twin
MockTransport(handler)                                 # sync or async callable: (request) -> Response
WSGITransport(app, raise_app_exceptions=True, script_name="", remote_addr="127.0.0.1", wsgi_errors=None)
ASGITransport(app, raise_app_exceptions=True, root_path="", client=("127.0.0.1", 123))
```

`MockTransport`/`WSGI`/`ASGI` are the offline-test path (no sockets). `retries` on the default transports is plain int re-attempts (default 0 — httpx itself has NO backoff policy; ours must live in app code, §10). `uds=` pins a unix-domain socket; `local_address=` binds the source IP; `socket_options=` passes raw socket opts through. Transport selection per URL happens in `_transport_for_url` (`_client.py:760`); explicit-`transport=` construction skips env-proxy mounting entirely (`_client.py:685,1399`) — so tests using `MockTransport` never leak proxy env, but production code passing a custom transport must re-add proxy mounts by hand if proxies matter. Auth classes: `Auth` base (`_auth.py:22`; subclass + override `auth_flow`/`async_auth_flow`; `FunctionAuth` exists in `_auth.py:113` but is NOT in top-level `__all__` — import from `httpx._auth` if ever needed); `BasicAuth(username, password)` (`_auth.py:126`), `NetRCAuth(file=None)` (`_auth.py:145`), `DigestAuth(username, password)` (`_auth.py:175`); `auth_flow(request) -> Generator[Request, Response, None]` (live-verified), `requires_request_body`/`requires_response_body` are `False` on `BasicAuth`.

## 7. Exceptions (COMPLETE tree; `_exceptions.py:74-353` line refs)

```text
HTTPError(Exception)                                   # :74 — base of everything raisable by a request
├─ RequestError(HTTPError)                             # :107 (RequestError(message, *, request=None))
│  ├─ TransportError(RequestError)                     # :123
│  │  ├─ TimeoutException(TransportError)               # :132
│  │  │  ├─ ConnectTimeout  :140 ├─ ReadTimeout :146 ├─ WriteTimeout :152 ├─ PoolTimeout :158
│  │  ├─ NetworkError(TransportError)                  # :167
│  │  │  ├─ ReadError :175 ├─ WriteError :181 ├─ ConnectError :187 ├─ CloseError :193
│  │  ├─ ProxyError :202 ├─ UnsupportedProtocol :208
│  │  └─ ProtocolError :216 ├─ LocalProtocolError :222 └─ RemoteProtocolError :232
│  ├─ DecodingError :243 └─ TooManyRedirects :249
│  └─ HTTPStatusError(HTTPError)                       # :258 (HTTPStatusError(message, *, request, response))
InvalidURL(Exception) :271 │ CookieConflict(Exception) :280
StreamError(RuntimeError) :297 ├─ StreamConsumed :309 ├─ StreamClosed :327
                               ├─ ResponseNotRead :340 └─ RequestNotRead :353
```

Catch guidance: `except httpx.HTTPStatusError` after `raise_for_status()`; `except httpx.TimeoutException` for all four timeout kinds; `except httpx.NetworkError` for connectivity; `except httpx.HTTPError` as the catch-all. `HTTPStatusError.__init__(message, *, request, response)` and `RequestError.__init__(message, *, request=None)` (live-verified).

## 8. `codes`, top-level API, CLI, streams, hooks, env

- `codes` (`_status_codes.py:8`) is an `IntEnum` of 62 members (live-counted, full list verified): `CONTINUE 100, SWITCHING_PROTOCOLS 101, PROCESSING 102, EARLY_HINTS 103, OK 200, CREATED 201, ACCEPTED 202, NON_AUTHORITATIVE_INFORMATION 203, NO_CONTENT 204, RESET_CONTENT 205, PARTIAL_CONTENT 206, MULTI_STATUS 207, ALREADY_REPORTED 208, IM_USED 226, MULTIPLE_CHOICES 300, MOVED_PERMANENTLY 301, FOUND 302, SEE_OTHER 303, NOT_MODIFIED 304, USE_PROXY 305, TEMPORARY_REDIRECT 307, PERMANENT_REDIRECT 308, BAD_REQUEST 400, UNAUTHORIZED 401, PAYMENT_REQUIRED 402, FORBIDDEN 403, NOT_FOUND 404, METHOD_NOT_ALLOWED 405, NOT_ACCEPTABLE 406, PROXY_AUTHENTICATION_REQUIRED 407, REQUEST_TIMEOUT 408, CONFLICT 409, GONE 410, LENGTH_REQUIRED 411, PRECONDITION_FAILED 412, REQUEST_ENTITY_TOO_LARGE 413, REQUEST_URI_TOO_LONG 414, UNSUPPORTED_MEDIA_TYPE 415, REQUESTED_RANGE_NOT_SATISFIABLE 416, EXPECTATION_FAILED 417, IM_A_TEAPOT 418, MISDIRECTED_REQUEST 421, UNPROCESSABLE_ENTITY 422, LOCKED 423, FAILED_DEPENDENCY 424, TOO_EARLY 425, UPGRADE_REQUIRED 426, PRECONDITION_REQUIRED 428, TOO_MANY_REQUESTS 429, REQUEST_HEADER_FIELDS_TOO_LARGE 431, UNAVAILABLE_FOR_LEGAL_REASONS 451, INTERNAL_SERVER_ERROR 500, NOT_IMPLEMENTED 501, BAD_GATEWAY 502, SERVICE_UNAVAILABLE 503, GATEWAY_TIMEOUT 504, HTTP_VERSION_NOT_SUPPORTED 505, VARIANT_ALSO_NEGOTIATES 506, INSUFFICIENT_STORAGE 507, LOOP_DETECTED 508, NOT_EXTENDED 510, NETWORK_AUTHENTICATION_REQUIRED 511`. `.phrase` (e.g. `"OK"`); class helpers `is_informational/is_success/is_redirect/is_client_error/is_server_error` (`_status_codes.py:44-80`).
- Top-level one-shot functions (`_api.py`, live-verified): `request(method, url, ...)`, `stream(method, url, ...)`, `get/options/head/post/put/patch/delete(url, ...)` — each builds a transient client (own pool, `timeout=Timeout(5.0)`, `follow_redirects=False` defaults). Never use these in app code loops — no connection reuse; prefer one `AsyncClient`.
- `main()` (`_main.py:1+`) is the `httpx` CLI (needs the `cli` extra — installed here). Full option list (verified `_main.py:38-101`): `URL` positional + `-m/--method METHOD` (default GET, or POST if a body is present), `-p/--params NAME VALUE…`, `-c/--content TEXT`, `-d/--data NAME VALUE…`, `-f/--files NAME FILENAME…`, `-j/--json TEXT`, `-h/--headers NAME VALUE…`, `--cookies NAME VALUE…`, `--auth USER PASS` (`-` prompts for the password; `-v` exposes the reversible encoding), `--proxy URL`, `--timeout FLOAT` (default 5.0), `--follow-redirects`, `--no-verify`, `--http2`, `--download FILE`, `-v/--verbose`, `--help`. Output is rich-formatted with pygments lexing by `Content-Type` (`get_lexer_for_response`, `_main.py:104`). Dev-host debugging only — irrelevant on-device; no packaging impact.
- `codes.get_reason_phrase(status)` classmethod (used at `_main.py:135`) returns the RFC phrase for a status int — handy for log lines.
- `__version__ = "0.28.1"`; `USE_CLIENT_DEFAULT` singleton (`_client.py:94`) marks "inherit client setting".
- `SyncByteStream`/`AsyncByteStream`/`ByteStream` are the body-stream ABCs (`_content.py:31` etc.); response decoders (`_decoders.py:36+`: `Identity/Deflate/GZip/Brotli/ZStandard/MultiDecoder`, `ByteChunker/TextChunker/TextDecoder/LineDecoder`) handle `Content-Encoding` transparently. Selection is header-driven: `_get_content_decoder` (`_models.py:699-716`) reads `Content-Encoding` via `get_list(..., split_commas=True)` and maps each token through a `SUPPORTED_DECODERS` table (`_models.py:710`) — so `BrotliDecoder`/`ZStandardDecoder` only engage when the corresponding extra is installed (neither is, here: a `br`/`zstd` body raises `DecodingError`, which is why OCI zstd layers in the roadmap parking lot must NOT rely on httpx decoding — verify Flet's bundled `compression.zstd` instead).
- Multipart upload path (`_multipart.py:70,115,224`, ctor sigs live-verified): `DataField(name, value: str | bytes | int | float | None)`, `FileField(name, value: FileTypes)`, assembled by `MultipartStream(SyncByteStream, AsyncByteStream)`. Reached via `files=` on verbs/`Request`; boundary reuse reads the `Content-Type` header (`get_multipart_boundary_from_content_type`, `_models.py:382-430` region). Our app uploads nothing in M1–M5 — documented for completeness, not planned use.
- `DigestAuth` (`_auth.py:175`) runs a challenge-response flow (`auth_flow` yields the 401-challenge then replays with the digest; `_DigestAuthChallenge` NamedTuple at `_auth.py:343`); `requires_request_body`/`requires_response_body` are `False` on `BasicAuth` (live-verified) — auth headers attach without buffering the body.
- Event hooks: exactly two keys, `"request"` and `"response"` (`_client.py:216-217`); each a list of callables run per request/response (`_client.py:976-981` sync, `1691-1696` async). Use: auth-token refresh, logging, metrics. Sketch:

```python
async def log_response(response: httpx.Response) -> None:
    response.read()  # hooks run before body load; read() makes .text/.json safe
    print(response.status_code, response.url, response.num_bytes_downloaded)

client = httpx.AsyncClient(event_hooks={"response": [log_response]})
```

- Mounts routing sketch (URL-pattern → transport pinning; `None` disables): `httpx.AsyncClient(mounts={"https://internal-mirror/": httpcore-free custom transport, "all://": None})` — pattern keys are URL prefixes matched in `_transport_for_url` (`_client.py:760`). Our app needs only the default pool plus `MockTransport` in tests; document mounts here so M3 planning does not re-discover them.
- Env handling: proxies come from `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY` (+ lowercase) with `NO_PROXY` bypass (`_utils.py:30-80`, incl. `NO_PROXY=*`, CIDR, `localhost` rules); mounted only when `trust_env=True` and no explicit `transport` (`_client.py:685,1399`). TLS bundle from `SSL_CERT_FILE`/`SSL_CERT_DIR` (`_config.py:34-37`). No `HTTPX_*` env vars exist in this version (grep-verified — claim would otherwise be **unverified**).

## 9. How flet uses it (every usage site, quoted)

Three lazy `import httpx` sites, all in the OAuth path (dormant unless `Page.login()`/auth runs — dep-httpx-cluster.md):

1. `flet/auth/authorization_service.py:119,133` — token exchange: `async with httpx.AsyncClient(follow_redirects=True) as client:` then `resp = await client.post(self.provider.token_endpoint, content=data, headers=headers)` + `resp.raise_for_status()`. Headers carry `User-Agent: Flet/{flet_version}` and form-encoded OAuth body (`prepare_request_body`, `:121-131`).
2. `flet/auth/authorization_service.py:207,221` — refresh: same shape against `token_endpoint` via `prepare_refresh_body`, preserves old `refresh_token` when the response omits one (`:230-233`), no-op when no expiry/refresh token (`:211-217`).
3. `flet/auth/authorization_service.py:248,256` — user fetch: `async with httpx.AsyncClient(follow_redirects=True) as client:` then `user_resp = await client.get(self.provider.user_endpoint, headers=headers)` with `Authorization: Bearer …` + `raise_for_status()` + `user_resp.json()`.
4. `flet/auth/providers/github_oauth_provider.py:43-45,76-78` — GitHub `_fetch_groups`/`_fetch_user`: `httpx.AsyncClient(base_url=GITHUB_API_BASE_URL, follow_redirects=True)`, `GET /user`, `/user/emails`, `/user/teams`, each `raise_for_status()` + `.json()`.

Concurrency pattern: short-lived `async with` clients per call (no shared session, no pooling benefit), `follow_redirects=True` always, errors surface as `httpx.HTTPStatusError`. Our app has no login flow → this whole path stays dormant; we reuse the package, not flet's pattern.

## 10. How OUR app should use it (tied to milestones)

- **M3 distro manager (registry + update checks):** one long-lived `httpx.AsyncClient(base_url=REGISTRY, follow_redirects=True, timeout=httpx.Timeout(10.0, connect=5.0), limits=httpx.Limits(max_connections=6, max_keepalive_connections=2))` owned by the network service (Data Formulator sole-importer shape: `services/http_service.py` is the only importer of httpx). Reuse across status/update polls → keep-alive instead of per-call handshakes. `HEAD`/small `GET` manifest checks with `If-Modified-Since`/ETag; `response.is_success` gates; `raise_for_status()` translated via a `friendly_http_error` mapper (roadmap M3 `friendly_job_error` pattern). `MockTransport` gives offline contract tests for every parser without sockets.
- **M3 downloads with progress:** `async with client.stream("GET", url) as r: r.raise_for_status(); async for chunk in r.aiter_bytes(chunk_size=1<<16): …` — chunk loop drives the determinate progress bar + SHA-256 update per chunk (replaces the TTY-suppressed `draw_bytes_bar` path; UI shows real bytes, not stage lines). Total from `Content-Length` header; missing header → indeterminate mode. Per-chunk accounting mirrors `Response.num_bytes_downloaded` semantics (`_models.py:856-857,947-952`); use the response's own counter or a local accumulator, not `Content-Length` arithmetic alone (compressed transfers differ).
- **M5 CI/release ritual:** `MockTransport`-backed contract tests run in the quality job (`pytest -m "not live"` per roadmap M5) with zero network; live registry checks stay behind an explicit `live` marker for nightly runs. Version skew (httpx 0.28.x → 1.x) is caught by pinning the import surface in `test_imports_vs_deps.py` (roadmap M3 scaffold): assert `httpx.__version__` major + the `__all__` names this doc records, so a breaking upstream lands as a loud test failure, not silent drift.
- **Concrete service sketch (M3 planning input, not a decision):**

```python
# services/http_service.py — sole importer of httpx (Data Formulator facade)
import httpx

METADATA_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
BLOB_TIMEOUT = httpx.Timeout(120.0, connect=10.0)

class HttpService:
    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(
            base_url=base_url, follow_redirects=True,
            timeout=METADATA_TIMEOUT,
            limits=httpx.Limits(max_connections=6, max_keepalive_connections=2),
        )
    async def fetch_json(self, path: str, *, cap: int = 16 * 1024 * 1024) -> dict:
        r = await self._client.get(path)
        r.raise_for_status()
        body = await r.aread()
        if len(body) > cap:
            raise ValueError(f"metadata over cap: {len(body)} > {cap}")
        return r.json()  # caller shape-checks; registry JSON is untrusted (§11)
    async def download(self, path: str, dest, progress_cb, *, timeout=BLOB_TIMEOUT):
        async with self._client.stream("GET", path, timeout=timeout) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0) or 0)
            async for chunk in r.aiter_bytes(chunk_size=1 << 16):
                dest.write(chunk)
                progress_cb(r.num_bytes_downloaded, total)
    async def aclose(self):
        await self._client.aclose()
```
- **Retry/timeout policy (app-owned — httpx ships none):** wrap calls in a `retry_http`-style helper mirroring upstream's `retry_http(operation, what, max_retries=5, retry_delay=5)` (`proot_distro/helpers/download.py:512`): retry only `TimeoutException` + transient 5xx/`ConnectError`, never `HTTPStatusError(4xx)`/`TooManyRedirects`/`DecodingError` — mirroring upstream's `is_retryable_http_error` gate (`download.py:481`) over its `NETWORK_ERRORS = (URLError, OSError, HTTPException)` triple (`download.py:85`). Per-call `timeout=httpx.Timeout(120.0, connect=10.0)` for blob downloads vs short `(10.0, connect=5.0)` for metadata — replacing today's single `NETWORK_TIMEOUT = 120.0` (`download.py:108`) with per-phase budgets. Upstream's metadata ceiling `MAX_METADATA_BYTES = 16 MiB` (`docker/transport.py:93`) ports directly: read registry JSON through a capped `response.aread()` + length check before `.json()`.
- **Proxy support (free):** default `trust_env=True` honors `HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY` with zero app code — Termux-side `urllib` needs hand-rolled opener policy (`http_opener`, `download.py:373`); document the env vars in Settings → Network.
- **Why httpx over urllib:** async-native (`AsyncClient` needs no `asyncio.to_thread` wrapper, so no ANR risk on the Flet UI thread); connection pooling for repeated registry polls; `stream()` + `aiter_bytes` for progress (urllib needs manual `readinto` loops); typed `Timeout(connect/read/write/pool)` vs one global float; `MockTransport` for hermetic tests. urllib stays ONLY inside vendored upstream `proot_distro` (no-patching rule) — our code never imports it for new work.
- **Mobile caveats:** certifi pins a build-time Mozilla bundle (~240 KB), NOT the Android trust store — user-installed enterprise CAs are invisible; private-mirror users need `verify=<bundle-path>` override in Settings (never `verify=False` silently). Keep `max_connections` small (radio/battery); downloads must pause on `ACCESS_NETWORK_STATE` loss and resume with `Range` (server-dependent — probe `Accept-Ranges`); no background-fetch guarantees — schedule update checks while foregrounded, persist state for resume.

## 11. How httpx makes our app significantly better than Termux's proot-distro

Baseline (what upstream ships today): `proot_distro/helpers/download.py` funnels every request through `http_opener()` (plain `urllib`, HTTP/HTTPS only, `RedirectPolicyHandler` allow-list, `NETWORK_TIMEOUT = 120.0` on every request — `download.py:108,373`), retried by `retry_http(... max_retries=5, retry_delay=5)` (`download.py:512`); the registry flow in `helpers/docker/transport.py` hand-rolls User-Agent, auth-stripping redirects (Bearer dropped across origins — Docker Hub CDN 400 workaround), `PD_DOCKER_AUTH` Basic→Bearer exchange, and a `MAX_METADATA_BYTES` ceiling with shape-checked JSON decode. Solid, but synchronous and hand-built.

What httpx buys us, concretely: (1) **async streaming downloads with real progress** — `client.stream() + aiter_bytes()` yields per-chunk callbacks on the event loop, so install progress renders live without `asyncio.to_thread` + `redirect_stderr` scraping of stage lines; (2) **per-phase timeouts** — `Timeout(connect/read/write/pool)` replaces the single 120 s float, so a stalled metadata GET fails in seconds while multi-GB blobs keep a generous read budget; (3) **pool reuse for status/update checks** — one `AsyncClient` with keep-alive turns N daily polls from N TLS handshakes into ~1 (radio- and battery-cheaper on mobile); (4) **proxy support for free** — env-proxy mounting vs upstream's custom opener policy; (5) **redirect-auth safety parity** — httpx strips `Authorization` across origins on redirect (`_redirect_headers`, `_client.py:546`) matching upstream's hand-rolled stripper, so registry→CDN blob redirects behave the same; (6) **testability** — `MockTransport`/`ASGITransport` let M3/M5 contract-test every HTTP parser offline, where upstream can only integration-test against live registries. None of this changes vendored upstream (no-patching rule): httpx powers OUR service layer; `proot_distro` internals keep their urllib path untouched.

**Migration map (upstream urllib helper → our httpx equivalent):** `new_request()` (`download.py:204`) → `client.build_request()`; `http_opener()` (`download.py:373`) → `AsyncClient` (env-proxy + redirect policy built in); `retry_http()` (`download.py:512`) → app-owned retry wrapper (same 5×5 s shape, gated by the `is_retryable_http_error` logic at `download.py:481`); `download_file()` (`download.py:553`) → `client.stream() + aiter_bytes()` sketch above; capped registry reads (`transport.py:210`, `MAX_METADATA_BYTES = 16 MiB` at `transport.py:93`) → `aread()` + length check in `fetch_json`. Upstream's `NETWORK_ERRORS = (URLError, OSError, HTTPException)` triple (`download.py:85`) maps to catching `httpx.HTTPError` (with `TimeoutException`/`NetworkError` for the retryable subset). Every row keeps behavior parity (redirect-auth stripping, per-phase budgets, metadata caps) while moving execution onto the event loop.

## 12. Android notes

- The Emscripten marker (`platform_system != "Emscripten"`) excludes httpx only on web builds; **Android APKs keep it** — no action, just don't copy the marker into our deps.
- Pure-Python + no `.so` → ships unmodified; nothing on pypi.flet.dev needed (dep-httpx-cluster.md — normal, Forge hosts only native wheels).
- `certifi` bundle vs system trust (above, §10) is the one behavioral gap that survives to device — verify against a private-CA mirror in M3 device QA, not desktop CI.
- No background-service integration: httpx sockets die with the process; long downloads belong to foregrounded sessions with resume, or a foreground service (default NO per roadmap M4 — revisit only if Play demands it).
- Sync `Client` on the UI thread blocks rendering → always `AsyncClient` from Flet event handlers; sync `Client` is for tests/scripts only.

## 13. Verification

- Installed tree + `__init__.__all__`: `ls -R .venv/Lib/site-packages/httpx` + `httpx/__init__.py:32-105`.
- Version/license/deps/entry point: `httpx/__version__.py:1-3`, `httpx-0.28.1.dist-info/METADATA:10` + `Requires-Dist` lines, `entry_points.txt` (`httpx = httpx:main`).
- All ctor/method signatures: live `inspect.signature` on `Client`, `AsyncClient`, `Request`, `Response`, `URL`, `QueryParams`, `Headers`, `Cookies`, `Timeout`, `Limits`, `Proxy`, `HTTPTransport`, `AsyncHTTPTransport`, `MockTransport`, `WSGITransport`, `ASGITransport`, `BasicAuth`, `DigestAuth`, `NetRCAuth`, `create_ssl_context`, top-level `request/stream/get/options/head/post/put/patch/delete`.
- Class line refs: `URL _urls.py:15`, `QueryParams _urls.py:420`, `Headers _models.py:139`, `Request _models.py:382`, `Response _models.py:515`, `Cookies _models.py:1079`, `Auth/Basic/NetRC/Digest _auth.py:22/126/145/175`, exceptions `_exceptions.py:74-353`, `Timeout/Limits/Proxy _config.py:72/159/201`, `codes _status_codes.py:8`, transports `_transports/{base,default,mock,wsgi,asgi}.py`, CLI `_main.py:1+`, env/proxy `_utils.py:30-80` + `_config.py:34-37` + `_client.py:685,1399`, hooks `_client.py:216-217,976-981,1691-1696`, redirects `_client.py:494,517,546`.
- Flet usage: `flet/auth/authorization_service.py:119,133,207,221,248,256`, `flet/auth/providers/github_oauth_provider.py:43-45,76-78`, marker `flet-1.0.4.dist-info/METADATA:14-15`.
- Termux baseline: `proot_distro/helpers/download.py:108 (NETWORK_TIMEOUT), 204 (new_request), 373 (http_opener), 512 (retry_http), 553 (download_file)`, `proot_distro/helpers/docker/transport.py:1-60+` (redirect/auth/metadata policy).
- Optionals in-venv: `click/click-8.5.0`, `pygments/pygments-2.21.0`, `rich/rich-15.0.0` present; `h2/socksio/brotli/zstandard` absent (`ls .venv/Lib/site-packages`).
- Sibling summary: `docs/reference/dep-httpx-cluster.md`; milestones/env rules: `docs/roadmap.md` (M3–M5, D-010 flet 1.0.4).
