# urllib3 2.8.0 — exhaustive API reference

Verified 2026-10-16 against the INSTALLED source in `.venv/Lib/site-packages/urllib3`
(`C:\Users\nwoki\.zcode\workspace\default\proot-distro-flet\.venv\Lib\site-packages\urllib3`).
Project context read first: `docs/roadmap.md` + `docs/reference/dep-cookiecutter-stack.md`.
Flet app; flet stays 1.0.4 (D-010).
**Anti-hallucination rule (owner-mandated):** every API claim below cites installed
source (`urllib3/<file>:<line>`) or installed dist metadata; anything not verifiable
in source is labeled **unverified**.

## 1. Identity

- Name/version: `urllib3 2.8.0` (`urllib3/_version.py`: `__version__ = version = '2.8.0'`,
  tuple `(2, 8, 0)`; dist metadata `urllib3-2.8.0.dist-info/METADATA:3`).
- Tagline (METADATA:4): "HTTP library with thread-safe connection pooling, file post,
  and more." License: **MIT** (`License-Expression: MIT`).
- `Requires-Python: >=3.10` (verified from dist METADATA). Our 3.14 venv is inside.
- **Pure Python** (+ optional compiled helpers elsewhere): tree is `.py` —
  `__init__.py`, `_base_connection.py`, `_collections.py`, `_request_methods.py`,
  `connection.py`, `connectionpool.py`, `exceptions.py`, `fields.py`, `filepost.py`,
  `poolmanager.py`, `response.py`, `util/` (`__init__, connection, proxy, request,
  response, retry, ssl_, ssl_match_hostname, ssltransport, timeout, url, util,
  wait`), `contrib/` (`__init__, emscripten, pyopenssl, socks`), `http2/`
  (`__init__, connection, probe`), plus `py.typed`.
- Deps: NONE required at runtime (no `Requires-Dist` for installs in METADATA —
  optional extras only: `brotli/brotlicffi`, `h2`, `socks`, `zstandard`, PyOpenSSL/
  cryptography for the contrib path — **unverified** exact extra names from memory,
  check METADATA `Provides-Extra` if it matters). Compression imports are lazy
  (`response.py:22-24` try `brotlicffi`, then `brotli`); absent here, so brotli bodies
  are inert in our tree.
- OpenSSL floor enforced at import (`urllib3/__init__.py:27-46`): **OpenSSL 1.1.1+**
  required; non-OpenSSL TLS backends → `NotOpenSSLWarning`; older → `ImportError`.
- Top-level exports (`urllib3/__init__.py:55-72`): `HTTPConnectionPool,
  HTTPSConnectionPool, PoolManager, ProxyManager, HTTPResponse, BaseHTTPResponse,
  Retry, Timeout, HTTPHeaderDict, connection_from_url, encode_multipart_formdata,
  make_headers, proxy_from_url, request, add_stderr_logger, disable_warnings`.
- Logging: `NullHandler` on the package logger; `add_stderr_logger()` (:74) and
  `disable_warnings()` (:107) are the two public logging helpers.

## 2. `PoolManager` / `ProxyManager` — `urllib3/poolmanager.py`

`PoolManager(RequestMethods)` (:164): "arbitrary requests while transparently keeping
track of necessary connection pools". `__init__(num_pools=10, headers=None,
**connection_pool_kw)` (:192-214): LRU pool cache (`RecentlyUsedContainer(num_pools)`,
:209), per-scheme pool classes/keys overridable (`pool_classes_by_scheme`,
`key_fn_by_scheme`, :213-214). `retries=` kwarg is normalized via `Retry.from_int`
when not already a `Retry` (:200-207) — redirect handling stays with the manager.

Key methods (grep-verified names; exact line numbers **unverified** — read
`poolmanager.py:164-513` for lines): `connection_from_host(host, port, scheme)`,
`connection_from_url(url, pool_kwargs)`, `connection_from_context(request_context)`,
`urlopen(method, url, redirect=True, ...)` (manager-level redirect loop),
`request(...)`, `request_encode_url/request_encode_body` (via `RequestMethods`),
`clear()` (drop all pools, in-flight unaffected), context-manager (`__enter__/__exit__`
closes pools), `proxy_from_url(url, **kw)` module fn (:676).

`ProxyManager(PoolManager)` (:513): `__init__(proxy_url, num_pools=10, headers=None,
proxy_headers=None, proxy_ssl_context=None, use_forwarding_for_https=False,
proxy_assert_hostname=None, proxy_assert_fingerprint=None, **connection_pool_kw)`
(:555+). HTTPS targets tunnel via CONNECT by default; `use_forwarding_for_https=True`
forwards in clear (headers+body VISIBLE to the proxy — docstring warns, :530-542).
Non-http(s) proxy scheme → `ProxySchemeUnknown` (:~575). Note the deprecated
`ssl_context`+forwarding combo warns (:~580+).

`PoolKey` NamedTuple (:58) + `_default_key_normalizer` (:97): pool identity =
scheme/host/port + normalized extra kwargs (timeout/retries/TLS settings flow into
the key — different TLS configs never share a pool).

## 3. Pool classes — `urllib3/connectionpool.py`

- `ConnectionPool` (:68): `__init__(host, port=None)` (:82); `close()` (:111);
  context-manager (:98-109); `_new_pool_queue(maxsize)` (:116, `LifoQueue`).
- `HTTPConnectionPool(ConnectionPool, RequestMethods)` (:126):
  `__init__(host, port=None, timeout=_DEFAULT_TIMEOUT, maxsize=1, block=False,
  headers=None, retries=None, _proxy=None, _proxy_headers=None, _proxy_config=None,
  **conn_kw)` (:181-240). `timeout` non-`Timeout` → `Timeout.from_float`;
  `retries=None` → `Retry.DEFAULT` (= `Retry(3)`, `retry.py:569`); pre-fills a
  `LifoQueue(maxsize)` with `None` sentinels; `num_connections/num_requests`
  counters; `weakref.finalize` drains sockets on GC. NOTE `maxsize=1` default —
  one connection per host unless raised (requests sets 10 via its adapter).
  - Internals: `_new_conn()` (:242: `ConnectionCls(host, port,
    timeout=connect_timeout, **conn_kw)`), `_get_conn(timeout)` (:262),
    `_put_conn(conn)` (:300), `_validate_conn` (:343), `_prepare_proxy` (:348),
    `_get_timeout` (:352), `_raise_timeout` (:364), `_make_request(...)` (:383:
    low-level send with `chunked/body_pos` support), `urlopen(method, url, body,
    headers, retries, redirect=True, assert_same_host=True, timeout, pool_timeout,
    release_conn, chunked, body_pos, preload_content=True, decode_content=True,
    **response_kw)` (:598-...) — THE workhorse; `is_same_host` (:576),
    `close()` (:564).
- `HTTPSConnectionPool(HTTPConnectionPool)` (:995): adds `key_file, cert_file,
  cert_reqs, key_password, ca_certs, ssl_version (deprecated exact),
  ssl_minimum_version, ssl_maximum_version, assert_hostname, assert_fingerprint,
  ca_cert_dir` (:1012-1039); `_prepare_proxy` tunnels CONNECT (:1061);
  `_new_conn` (:1076) and `_validate_conn` (:1117) enforce TLS.
- Module fns: `connection_from_url(url, pool_kwargs)` (:1140),
  `_normalize_host` (:1171+ overloads — IDNA/zone-ID aware), `_url_from_pool`
  (:1196), `_close_pool_connections` (:1203, GC finalizer).

## 4. `Retry` — EVERY knob — `urllib3/util/retry.py`

Class `Retry` (:43), `RequestHistory` NamedTuple (:35). THE class requests exposes
as `HTTPAdapter(max_retries=...)`. Constructor (:222):

```python
Retry(total=10, connect=None, read=None, redirect=None, status=None, other=None,
      allowed_methods=frozenset({"HEAD","GET","PUT","DELETE","OPTIONS","TRACE"}),
      status_forcelist=None, backoff_factor=0, backoff_max=120,
      raise_on_redirect=True, raise_on_status=True, history=None,
      respect_retry_after_header=True,
      remove_headers_on_redirect=frozenset({"Cookie","Authorization","Proxy-Authorization"}),
      backoff_jitter=0.0, retry_after_max=21600)
```

| Knob | Meaning (docstrings :60-197) |
|---|---|
| `total` | Budget across ALL retry types; `None` = unlimited-ish per-sub-counter; `False` disables + implies `raise_on_redirect=False` |
| `connect` | Retries on connection errors (DNS/TCP refused). `None` (default) follows `total` |
| `read` | Retries on read errors; method must be in `allowed_methods` or it re-raises (`increment`, :505+) |
| `redirect` | Max redirects followed; `False/0` = fail fast / return 3xx when `raise_on_redirect=False` |
| `status` | Retries when response status ∈ `status_forcelist` |
| `other` | Retries on errors that are not connect/read/redirect/status (post-send errors — may have side effects); docs advise setting `0` if `total` unset to avoid infinite loops |
| `allowed_methods` | Idempotent-method whitelist (`DEFAULT_ALLOWED_METHODS`, :199-203); `None` = retry ANY verb (empty collection = deprecated no-retry-all, warns `FutureWarning`) |
| `status_forcelist` | e.g. `{429, 500, 502, 503, 504}` for registry polling |
| `backoff_factor` | Sleep `factor * 2**(retries-1)` after the 2nd try: 0.1 → `[0.0, 0.2, 0.4, 0.8, …]`; capped by `backoff_max` |
| `backoff_max` | Cap, default `DEFAULT_BACKOFF_MAX = 120` (:213) |
| `backoff_jitter` | Adds `random.uniform(0, jitter)` seconds |
| `raise_on_redirect / raise_on_status` | `True` = exhaust → `MaxRetryError`; `False` = return the 3xx/bad-status response |
| `history` | Tuple of `RequestHistory` — audit trail of attempts |
| `respect_retry_after_header` | Honor `Retry-After` on `RETRY_AFTER_STATUS_CODES = {413, 429, 503}` (:205) |
| `remove_headers_on_redirect` | Stripped on redirect (default Cookie/Authorization/Proxy-Authorization — mirrors requests' `should_strip_auth`) |
| `retry_after_max` | Clamp for huge `Retry-After`, default `21600` (6 h, :217) |

Methods: `new(**kw)` (:278, clone-with-overrides), `from_int(retries, redirect=True,
default=None)` (:303: int/bool/None → `Retry`; THE bridge requests uses for
`max_retries=<int>`), `get_backoff_time()` (:321), `parse_retry_after(str)` (:340),
`get_retry_after(response)` (:361), `sleep_for_retry/sleep/_sleep_backoff`
(:371-399, `time.sleep`), `is_retry(method, status_code, has_retry_after=False)`
(:423), `is_exhausted()` (:445), `increment(method, url, response, error, _pool,
_stacktrace)` (:464: decrements the right counter per cause — connect (:501),
read (:508), other (:515), redirect (:520+), status (:530+) — returns a NEW `Retry`),
`__repr__` (:561). Class attr `Retry.DEFAULT = Retry(3)` (:569).
**Migration note:** `method_whitelist` is GONE in 2.8.0 (grep finds zero hits in
`retry.py` — only `allowed_methods`); `ssl_version` exact pin is deprecated in
favor of min/max (`ssl_.py` docstring). `Retry(0, read=False)` (what requests uses
for its default) = zero total with read-counter disabled.

## 5. `HTTPResponse` — `urllib3/response.py`

- Decoders: `ContentDecoder` (:64), `DeflateDecoder` (:76), `GzipDecoder` (:147,
  with `GzipDecoderState` :141), `MultiDecoder` (:316), `_get_decoder` (:372);
  `BytesQueueBuffer` (:390: `put/get/get_all`, :408-450).
- `BaseHTTPResponse` (:467): `__init__(*, headers, status, version, version_string,
  reason, decode_content, request_url, retries)` (:482); auto `chunked` detection
  from `transfer-encoding`; `get_redirect_location()` (:519:
  status∈`REDIRECT_STATUSES` → `location` header else `False`); `data` (abstract),
  `json()` (:535, UTF-8 per RFC 8259), `url` prop (:557), `connection/retries` props,
  `stream(amt, read1)` (:579), `read(amt, decode_content, cache_content)` (:584),
  `read1` (:592), `read_chunked` (:599), `release_conn/drain_conn/shutdown/close`
  (:606-615), decoder plumbing `_init_decoder/_decode/_flush_decoder` (:618-689),
  `readinto` (:689), `getheaders/getheader/info/geturl` (:698-708).
- `HTTPResponse(BaseHTTPResponse)` (:712): full ctor `(body="", headers, status=0,
  version=0, version_string="HTTP/?", reason, preload_content=True,
  decode_content=True, original_response, pool, connection, msg, retries,
  enforce_content_length=True, request_method, request_url, auto_close=True,
  sock_shutdown)` (:745); `data` prop (:835, reads+caches), `release_conn` (:810) /
  `drain_conn` (:817) return conns to the pool, `isclosed/tell` (:849-852),
  `_init_length(request_method)` (:860: HEAD/1xx/204/304 → no body),
  `_error_catcher` (:917: maps httplib errors), `_fp_read/_raw_read` (:978-1083),
  `read/read1/stream` with `preload_content/decode_content` semantics
  (:1083-1290+; exact end lines **unverified**).
- requests sets `preload_content=False, decode_content=False` in its adapter call
  and decodes itself — so THESE paths matter to us mainly via `raw.stream()`.

## 6. `Timeout` — `urllib3/util/timeout.py`

`Timeout(total=None, connect=_DEFAULT_TIMEOUT, read=_DEFAULT_TIMEOUT)` (:109):
`connect` = TCP-handshake budget, `read` = between-bytes budget, `total` = overall
cap with leftover semantics (docstring :25-107: "the read timeout will be set to the
time leftover"). `None` disables that leg; `DEFAULT_TIMEOUT` sentinel =
"system/socket default". Classmethods: `from_float(timeout)` (float→both legs;
**unverified** name — confirm at `timeout.py` before use), `resolve_default_timeout`,
`clone()` (**unverified**). Read the :25-107 docstring before tuning: DNS does NOT
obey socket timeouts, and `read` measures inter-byte gaps, not total time.
requests maps its `timeout=` through this class (`TimeoutSauce` alias,
`requests/adapters.py:32,684-693`).

## 7. Exceptions tree — `urllib3/exceptions.py` (bases VERIFIED by grep)

- `HTTPError(Exception)` (:18) — root. `HTTPWarning(Warning)` (:22).
- `PoolError(HTTPError)` (:29) → `RequestError(PoolError)` (:42) →
  `MaxRetryError(RequestError)` (:84, carries `.reason`, `.url`, `.pool`),
  `HostChangedError(RequestError)` (:109), `ReadTimeoutError(TimeoutError,
  RequestError)` (:132).
- `TimeoutError(HTTPError)` (:124) → `ReadTimeoutError` (above),
  `ConnectTimeoutError(TimeoutError)` (:138) → `NewConnectionError(ConnectTimeoutError,
  HTTPError)` (:142, ECONNREFUSED-style) → `NameResolutionError(NewConnectionError)`
  (:166, DNS, carries `.host`).
- `SSLError(HTTPError)` (:54), `ProxyError(HTTPError)` (:58, `__cause__` = origin),
  `DecodeError(HTTPError)` (:69), `ProtocolError(HTTPError)` (:73) →
  `ResponseNotChunked(ProtocolError, ValueError)` (:250).
- Pool-state: `EmptyPoolError/FullPoolError/ClosedPoolError(PoolError)` (:180-190).
- URL: `LocationValueError(ValueError, HTTPError)` (:192) →
  `LocationParseError` (:196), `URLSchemeUnknown` (:206, carries `.scheme`),
  `ProxySchemeUnknown(AssertionError, URLSchemeUnknown)` (:303);
  sibling `ProxySchemeUnsupported(ValueError)` (:320).
- Body/response: `ResponseError(HTTPError)` (:216, `GENERIC_ERROR/SPECIFIC_ERROR`
  templates), `IncompleteRead(HTTPError, httplib_IncompleteRead)` (:261),
  `InvalidChunkLength(HTTPError, httplib_IncompleteRead)` (:283),
  `InvalidHeader(HTTPError)` (:299), `HeaderParsingError(HTTPError)` (:324),
  `BodyNotHttplibCompatible(HTTPError)` (:254), `UnrewindableBodyError(HTTPError)`
  (:334), `TimeoutStateError(HTTPError)` (:120).
- Warnings: `SecurityWarning(HTTPWarning)` (:223) → `InsecureRequestWarning` (:227),
  `NotOpenSSLWarning` (:231), `SystemTimeWarning` (:235), `InsecurePlatformWarning`
  (:239); `DependencyWarning(HTTPWarning)` (:243, silenced by requests).
- requests maps: `ProtocolError/OSError→ConnectionError`,
  `MaxRetryError(ConnectTimeoutError)→ConnectTimeout`,
  `(ResponseError)→RetryError`, `(proxy)→ProxyError`, `(ssl)→SSLError`
  (`requests/adapters.py:698-730`).

## 8. `connectionpool` internals worth knowing

- Pools are per-(scheme, host, port, +TLS/retries/timeout kwargs) with LRU eviction
  (`num_pools=10` default at the manager). Per-pool `maxsize=1` default at the pool
  level — raise for parallel CI downloads.
- Queue model: `LifoQueue` pre-filled with `None`s; `block=False` default →
  pool-exhausted creates a NEW connection instead of raising `EmptyPoolError`
  (only with `block=True` + exhausted `maxsize`).
- `body_pos` (`urlopen` kwarg): rewind position for retried file bodies — the
  urllib3 side of requests' `rewind_body`.
- `assert_same_host=False` + `retries=` are what let requests implement its OWN
  redirect loop on top of `conn.urlopen(redirect=False)`.
- `HTTPConnection` (`connection.py:113`): `__init__(host, port, *, timeout,
  source_address, blocksize=16384, socket_options, proxy, proxy_config)` (first
  `__init__` in file; exact line **unverified**); `set_tunnel`, `_new_conn`
  socket creation, `_tunnel` CONNECT logic; `HTTPSConnection` (:671) adds cert/key/
  context handling; `_WrappedAndVerifiedSocket` (:996), `_match_hostname` (:1131),
  `_get_default_user_agent` (:1182), `DummyConnection` (:1186, testing).

## 9. TLS context helpers — `urllib3/util/ssl_.py`

- `create_urllib3_context(ssl_version=None [deprecated exact], cert_reqs=None
  [default CERT_REQUIRED], options=None [default OP_NO_SSLv2|OP_NO_SSLv3|
  OP_NO_COMPRESSION|OP_NO_TICKET], ciphers=None [system ciphers on OpenSSL 1.1.1+],
  ssl_minimum_version=None, ssl_maximum_version=None [default MAXIMUM_SUPPORTED],
  verify_flags=None [VERIFY_X509_PARTIAL_CHAIN|STRICT on 3.13+])` (:184; docstring
  :184-240 verified, body lines **unverified**). Passing BOTH `ssl_version` and
  min/max → `ValueError`.
- `resolve_cert_reqs` (:145), `resolve_ssl_version` (:168),
  `assert_fingerprint` (:108, pin-a-cert workflows), `ssl_wrap_socket` overloads
  (:332-367) → `_ssl_wrap_socket_impl` (:465), `is_ipaddress` (:441),
  `_is_key_file_encrypted` (:454).
- requests' `cert_verify` sets `conn.cert_reqs/ca_certs/ca_cert_dir/cert_file/
  key_file` on the POOL object (not a context) — pool-key separation keeps TLS
  configs isolated (`requests/adapters.py:307-363`).

## 10. Util helpers commonly used

- `Retry.from_int(retries, redirect=True, default=None)` (`retry.py:303`) — int/bool/
  None → `Retry`; the int form `requests` accepts for `max_retries`.
- `parse_url(url) -> Url` (`util/url.py:471`): RFC 3986/6874 parser → `Url` NamedTuple
  (`scheme/auth/host/port/path/query/fragment`, :86; scheme lowercased, path
  slash-prefixed in `__new__`; `auth_decoded` prop). Helpers: `_encode_invalid_chars`
  (:264+3 overloads), `_remove_path_dot_segments` (:323), `_normalize_host`
  (:354+3 overloads, IDNA), `_idna_encode` (:432), `_encode_target` (:453).
- `make_headers(keep_alive, accept_encoding, user_agent, basic_auth,
  proxy_basic_auth, disable_cache, *, basic_auth_encoding="latin-1",
  proxy_basic_auth_encoding=...)` (`util/request.py:60-70` signature verified).
- `encode_multipart_formdata(fields, boundary=None) -> (bytes, content_type)`
  (`filepost.py`); `RequestField(name, data, filename, headers,
  header_formatter [deprecated, FutureWarning])` (`fields.py`), with
  `RequestField.from_tuples(fieldname, value)` factory (:200),
  `format_header_param*` helpers, `guess_content_type` (:15).
- `HTTPHeaderDict` (`_collections.py:204`): multi-value dict — `add(key, val,
  combine=)`, `getlist`, `extend`, `discard`, case-insensitive get/set;
  `RecentlyUsedContainer` LRU (:63), `ensure_can_construct_http_header_dict` (:43).
- `RequestMethods` (`_request_methods.py:20`): `urlopen` (:54), `request` (:69),
  `request_encode_url` (:147), `request_encode_body` (:184) — the shared verbs
  `PoolManager` AND pools both inherit.
- `Timeout` construction forms: `Timeout(connect, read, total)` or the float
  shorthand at pool/request level.
- Contrib: `pyopenssl.inject_into_urllib3()/extract_from_urllib3()` (:141/:152,
  SNI fallback only), `contrib/socks.py` (`SOCKSProxyManager`, needs PySocks —
  class names **unverified**), `contrib/emscripten/` (Pyodide/WASM fetch bridge —
  presence verified via `ls`, API **unverified**), `http2/` (`connection.py`,
  `probe.py` — needs `h2`, absent here).

## 11. How it serves us — cookiecutter path, CI-only, never in the APK

urllib3 reaches us ONLY as `requests → cookiecutter → flet-cli(dev)` transitive:
cookiecutter needs `requests>=2.23.0`; requests needs `urllib3<3,>=1.26`; we resolve
2.8.0 (inside the ceiling — no conflict). Same guarantee chain as requests.md §10:
(1) `uv.lock` subtree under cookiecutter; (2) `pyproject.toml` dev-group-only;
(3) on-device downloader is stdlib `urllib.request`
(`proot_distro/helpers/download.py:42-44`) — urllib3 is not importable on-device.
What urllib3 DOES for the host path today: pooling + keep-alive for
`zipfile.py:54`'s streamed template-zip GET (10-conn/session pools,
`HTTPAdapter` defaults), TLS verification against certifi, and the `Retry` engine
available to any tooling that mounts it. Its OpenSSL-1.1.1+ import floor
(`__init__.py:27-46`) is a free CI-runner hygiene check: ancient runners fail
loudly instead of negotiating weak TLS.

## 12. How this makes our app better than Termux's proot-distro (honest, concrete)

Again tooling/CI-side only — Termux shell scripts `curl` assets with flags baked
into scripts; every behavior below is something our HOST tooling can do that shell
can't express cleanly:

- **One pool, many assets.** `PoolManager(num_pools=10)` reuses TCP+TLS across
  template zips, checksum files, and registry API calls — Termux pays a handshake
  per `curl` invocation. (Capped LRU = bounded memory in long CI jobs.)
- **Surgical retries.** Per-class budgets (`connect` vs `read` vs `status`) +
  `status_forcelist={429,500,502,503,504}` + `Retry-After` respect + exponential
  backoff with jitter + 6 h clamp = registry polling that backs off like a good
  citizen instead of hammering. `Retry(3)` default exists (`retry.py:569`) but
  requests zeroes it — you must OPT IN via the adapter (documented trap).
- **Redirect hygiene.** `remove_headers_on_redirect` drops `Authorization` on
  cross-host redirects by default — a credential-leak class that shell scripts
  routinely get wrong when following GitHub release-asset redirects (which 302 to
  S3-like hosts).
- **TLS explicitness.** Min/max TLS versions, CA dirs, fingerprint pinning
  (`assert_fingerprint`), hostname assertion — all one constructor away when CI
  needs to pin an internal mirror.
- Non-goals (honest): nothing on-device; `proot_distro` keeps stdlib urllib with
  zero deps and that's CORRECT for the APK.

## 13. Fullest utilization for our tooling — guidance + consistency call

Same house call as requests.md §12: **new code on httpx; urllib3 stays indirect.**
Rationale specific to urllib3: reaching past requests to use urllib3 directly buys
pool-level control (per-host `maxsize`, `block=True` backpressure, `body_pos`
rewinds) that CI asset scripts don't need, while splitting the codebase across two
HTTP idioms. The ONE sanctioned direct use: `from urllib3.util.retry import Retry`
passed as `HTTPAdapter(max_retries=Retry(total=5, backoff_factor=0.5,
status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET", "HEAD"],
respect_retry_after_header=True))` mounted on a `requests.Session` (or the httpx
equivalent) for release-asset polling — `Retry` is import-stable public API
(`urllib3.__all__`). Never touch `connectionpool`/`connection` internals from
tooling; never `PoolManager` directly when `requests.Session`/`httpx.Client`
suffices. Bump with the group (`urllib3<3` ceiling; urllib3 v3 will rename/remove
deprecated surfaces — re-verify `allowed_methods`/context params then).

## 14. Verification refs

- Installed: `.venv/Lib/site-packages/urllib3` (`__init__.py:27-72/:74/:107/:117`;
  `poolmanager.py:58/:97/:164/:192/:513/:555/:676`; `connectionpool.py:68/:82/:126/
  :181/:242/:262/:300/:343/:348/:352/:364/:383/:564/:576/:598/:995/:1012/:1061/
  :1076/:1117/:1140/:1171/:1196/:1203`; `response.py:22/:64/:76/:141/:147/:316/
  :372/:390/:467/:482/:519/:535/:557/:565/:579/:584/:592/:599/:606/:689/:698/
  :712/:745/:810/:817/:835/:849/:860/:917/:978`; `connection.py:113/:671/:996/
  :1006/:1131/:1157/:1182/:1186`; `exceptions.py:18-334` (bases grep-verified);
  `util/retry.py:35/:43/:100-217/:222/:278/:303/:321/:340/:361/:371/:385/:401/
  :409/:415/:423/:445/:464/:561/:569`; `util/timeout.py:25-140/:109`;
  `util/url.py:86/:264/:323/:354/:402/:415/:425/:432/:453/:471`;
  `util/ssl_.py:31/:108/:145/:168/:184/:332/:441/:454/:465`;
  `util/request.py:60`; `fields.py:15/:31/:79/:117/:135/:153/:200`;
  `filepost.py:22/:29/:51`; `_collections.py:39/:43/:63/:156/:204`;
  `_request_methods.py:20/:51/:54/:69/:147/:184`; `contrib/pyopenssl.py:141/:152`;
  `_version.py` 2.8.0).
- Dist: `urllib3-2.8.0.dist-info/METADATA` (MIT, `Requires-Python >=3.10`).
- Call chain: `cookiecutter/zipfile.py:54` → `requests/adapters.py:634,698` →
  `conn.urlopen` → `Retry.increment`; `requests` dep line
  `requests-2.34.2.dist-info/METADATA:36` (`urllib3<3,>=1.26`).
- Context: `docs/roadmap.md` (D3 row, bump groups), `docs/reference/dep-cookiecutter-stack.md:16,19`.
