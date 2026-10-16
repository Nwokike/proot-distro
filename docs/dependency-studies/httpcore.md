# httpcore 1.0.9 — exhaustive API reference

Verified 2026-10-16 against the INSTALLED source in `.venv/Lib/site-packages/httpcore` (live introspection + `grep -n` line refs). Project context: `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md`. Flet app; this package is an httpx engine (flet stays 1.0.4, D-010). Every API claim below carries a `file:line` ref or is marked **unverified**.

## 1. Identity

- Version `1.0.9` (`httpcore/__init__.py:134`, `__version__ = "1.0.9"`).
- License BSD-3-Clause (dep-httpx-cluster.md; dist-info license file **unverified** — not re-checked in this pass).
- `py.typed` marker ships at package root (verified by tree listing) — typed package.
- **Pure Python.** Tree is `.py` only: `__init__.py`, `_api.py`, `_exceptions.py`, `_models.py`, `_ssl.py`, `_synchronization.py`, `_trace.py`, `_utils.py`, plus three subpackages `_sync/`, `_async/`, `_backends/` (verified by `ls -R`). No `.so` files.
- Role here: connection pooling + HTTP/1.1 state-machine driving (via h11) + HTTP/2 framing (via `h2`, when installed). flet imports it only through httpx inside `auth/` (lazy) — **dormant unless OAuth is used** (dep-httpx-cluster.md).
- Top-level `__all__` (`httpcore/__init__.py:73+`, verified by live `httpcore.__all__`): `request`, `stream`, `Origin`, `URL`, `Request`, `Response`, `Proxy`, `AsyncHTTPConnection`, `AsyncConnectionPool`, `AsyncHTTPProxy`, `AsyncHTTP11Connection`, `AsyncHTTP2Connection`, `AsyncConnectionInterface`, `AsyncSOCKSProxy`, `HTTPConnection`, `ConnectionPool`, `HTTPProxy`, `HTTP11Connection`, `HTTP2Connection`, `ConnectionInterface`, `SOCKSProxy`, `SyncBackend`, `AnyIOBackend`, `TrioBackend`, `AsyncMockBackend`, `AsyncMockStream`, `MockBackend`, `MockStream`, `AsyncNetworkStream`, `AsyncNetworkBackend`, `NetworkStream`, `NetworkBackend`, `default_ssl_context`, `SOCKET_OPTION`, plus all 15 exceptions below.
- **Optional-dependency stubs** (`httpcore/__init__.py:52-65`, `try/except ImportError`): `HTTP2Connection`/`AsyncHTTP2Connection` degrade when `h2` is absent; `SOCKSProxy`/`AsyncSOCKSProxy` degrade when `socksio` is absent. Both names stay exported; import of the underlying module fails lazily. In OUR venv **both optionals are missing** (see §7) — the stubs matter.

## 2. Top-level functions (`httpcore/_api.py`)

```python
def request(method: bytes | str, url: URL | bytes | str, *, headers: HeaderTypes = None,
            content: bytes | Iterator[bytes] | None = None,
            extensions: Extensions | None = None) -> Response   # _api.py:10
def stream(method: bytes | str, url: URL | bytes | str, *, headers: HeaderTypes = None,
           content: bytes | Iterator[bytes] | None = None,
           extensions: Extensions | None = None) -> Iterator[Response]  # _api.py:51
```

One-shot convenience wrappers that build a transient `ConnectionPool`, run one request, and close it. `request()` reads the full body; `stream()` yields a `Response` whose body is lazily iterated. You never use these through httpx — httpx owns its pools. Direct use is for scripts/tests only.

## 3. Models (`httpcore/_models.py`)

### `ByteStream` (`_models.py:142`)
```python
class ByteStream:
    def __init__(self, content: bytes) -> None
    def __iter__(self) -> Iterator[bytes]      # yields content once
    async def __aiter__(self) -> AsyncIterator[bytes]
```
Container for non-streaming bodies. **Anti-hallucination note:** there is NO `SyncByteStream`/`AsyncByteStream` in 1.0.9 — `from httpcore._models import SyncByteStream` raises `ImportError` (verified live). Older tutorials name those classes; the unified `ByteStream` plus per-connection stream classes below replaced them.

### `Origin` (`_models.py:161`)
```python
Origin(scheme: bytes, host: bytes, port: int)
```
Connection identity triple. `can_handle_request(origin)` compares against it. Attributes are plain (verified by constructor signature `(self, scheme: bytes, host: bytes, port: int)`).

### `URL` (`_models.py:182`)
```python
URL(url: bytes | str = "", *, scheme: bytes | str = b"", host: bytes | str = b"",
    port: int | None = None, target: bytes | str = b"")
@property origin -> Origin
```
Minimal URL value object. `Request` coerces `str | bytes | URL` via `enforce_url` (`_models.py:40`). `extensions["target"]` overrides the target on a `Request` (`_models.py:339-345` region, verified by attribute grep).

### `Request` (`_models.py:316`)
```python
Request(method: bytes | str, url: URL | bytes | str, *, headers: HeaderTypes = None,
        content: bytes | Iterable[bytes] | AsyncIterable[bytes] | None = None,
        extensions: Extensions | None = None)
```
Attributes (verified by source grep): `method: bytes`, `url: URL`, `headers: list[tuple[bytes, bytes]]`, `stream: Iterable[bytes] | AsyncIterable[bytes]`, `extensions: dict`. Header coercion via `enforce_headers` (`_models.py:53`), body via `enforce_stream` (`_models.py:85`), defaults via `include_request_headers` (`_models.py:109`, adds Host/Content-Length as needed). `__repr__` → `<Request [b'GET']>`.

### `Response` (`_models.py:366`)
```python
Response(status: int, *, headers: HeaderTypes = None,
         content: bytes | Iterable[bytes] | AsyncIterable[bytes] | None = None,
         extensions: Extensions | None = None)
```
Attributes: `status: int`, `headers`, `stream`, `extensions`, `_stream_consumed: bool`. Members (verified by live `dir` + source grep):
- `content -> bytes` (property; joins sync stream)
- `read() -> bytes` / `iter_stream() -> Iterator[bytes]` (sync)
- `aread() -> bytes` / `aiter_stream() -> AsyncIterator[bytes]` (async)
- `close() -> None` / `aclose() -> None`
- `__repr__` → `<Response [200]>`
Single-consumption rule: `iter_stream()` sets `_stream_consumed = True`; a second iteration raises (verified by source at `_models.py:124-129` region). `close()` closes the underlying stream if it has `close` (`_models.py:138-139`).

### `Proxy` (`_models.py:496`)
```python
Proxy(url: URL | bytes | str, auth: tuple[bytes | str, bytes | str] | None = None,
      headers: HeadersAsMapping | HeadersAsSequence | None = None,
      ssl_context: ssl.SSLContext | None = None)
```
Value object passed to `ConnectionPool(proxy=...)` or converted by httpx from its own proxy config (`httpx/_transports/default.py:170-177` builds `httpcore.URL` + `proxy_auth` + `proxy_headers`).

## 4. `ConnectionInterface` abstraction (`_sync/interfaces.py:87`, `_async/interfaces.py` — mirrored)

Sync `RequestInterface` (`_sync/interfaces.py:20`) declares:
```python
def request(self, method, url, *, headers=None, content=None, extensions=None) -> Response      # :21
def stream(self, method, url, *, headers=None, content=None, extensions=None) -> Iterator[Response]  # :53
def handle_request(self, request: Request) -> Response   # :83
```
`ConnectionInterface(RequestInterface)` (`:87`) adds the pool-management contract (all verified by grep):
```python
def close(self) -> None                 # :88
def info(self) -> str                   # :91  ("HTTP/1.1, ...", used in pool reprs)
def can_handle_request(self, origin: Origin) -> bool  # :94
def is_available(self) -> bool          # :97
def has_expired(self) -> bool           # :115
def is_idle(self) -> bool               # :124
def is_closed(self) -> bool             # :130
```
Async mirror (`_async/interfaces.py`, verified by live signature dump of `AsyncConnectionInterface`): identical names with `aclose()` replacing `close()` and `handle_async_request()` replacing `handle_request()`; `request()`/`stream()` accept `AsyncIterator[bytes]` content and return `Response` / `AsyncIterator[Response]`.

## 5. `ConnectionPool` / `AsyncConnectionPool`

Sync (`_sync/connection_pool.py:43`), async mirror in `_async/connection_pool.py` (verified by live dump).

```python
ConnectionPool(ssl_context: SSLContext | None = None, proxy: Proxy | None = None,
    max_connections: int | None = 10, max_keepalive_connections: int | None = None,
    keepalive_expiry: float | None = None, http1: bool = True, http2: bool = False,
    retries: int = 0, local_address: str | None = None, uds: str | None = None,
    network_backend: NetworkBackend | None = None,
    socket_options: Iterable[SOCKET_OPTION] | None = None)   # :48 (live signature)
```
Parameter semantics (names verified by signature; prose is standard httpcore semantics):
- `ssl_context` — verification context; default `default_ssl_context()` (certifi bundle).
- `proxy` — `Proxy` value object; pool routes via proxy connection classes.
- `max_connections=10` — cap on concurrent connections; excess requests queue.
- `max_keepalive_connections` — cap on idle kept-alive connections (`None` = unlimited up to max).
- `keepalive_expiry` — seconds an idle connection is kept before expiry (`has_expired()`).
- `http1=True, http2=False` — protocol support flags. `http2=True` requires `h2` (absent here — see §7).
- `retries=0` — connection-establishment retries with exponential backoff (`exponential_backoff` at `_sync/connection.py:25`).
- `local_address` — source address bind; `uds` — unix-domain-socket path; `network_backend` — injectable backend (tests); `socket_options` — raw socket options passthrough.
Methods (sync; async adds `a` prefix / `async` variants):
- `handle_request(request) -> Response` (`:199`) / `handle_async_request` (async) — the method httpx actually calls.
- `request(...)` / `stream(...)` — convenience wrappers (inherited from `RequestInterface`).
- `create_connection(origin) -> ConnectionInterface` (`:128`) — factory used by the assignment loop.
- `connections -> list[ConnectionInterface]` (property, `:182`).
- `_assign_requests_to_connections()` (`:270`), `_close_connections(closing)` (`:341`) — internal scheduling.
- `close()` (`:347`) / `aclose()` (async) — drains the pool. Also context-manager (`__enter__/__exit__` `:355-358`; async uses `__aenter__/__aexit__`, **unverified** exact lines — mirror assumed, labeled unverified).
- `PoolRequest` (`:17`) with `assign_to_connection` (`:23`), `clear_connection` (`:27`), `wait_for_connection` (`:31`), `is_queued` (`:39`) — internal queue slots; `PoolTimeout` surfaces here when `max_connections` is saturated.
- `PoolByteStream` (`:389`): `__iter__` (`:401`), `close` (`:409`) — the lazy body stream returned for pooled responses; closing it returns the connection to the pool.

## 6. `HTTPConnection` / `AsyncHTTPConnection` (single-origin connection)

Sync (`_sync/connection.py:38`):
```python
HTTPConnection(origin: Origin, ssl_context=None, keepalive_expiry=None, http1=True,
    http2=False, retries=0, local_address=None, uds=None,
    network_backend=None, socket_options=None)   # :39 (live signature)
```
- `handle_request(request)` (`:69`) — connect (with retries) then delegate to the negotiated `HTTP11Connection`/`HTTP2Connection`.
- `_connect(request) -> NetworkStream` (`:105`) — TCP connect → optional TLS upgrade; reads `request.extensions["timeout"]["connect"]`, `request.extensions["sni_hostname"]`, wraps each phase in `Trace("connect_tcp"/...)` (verified by grep `:106-153`).
- Lifecycle: `can_handle_request` (`:167`), `close` (`:170`), `is_available` (`:175`), `has_expired` (`:187`), `is_idle` (`:192`), `is_closed` (`:197`), `info` (`:202`). Context-manager `__enter__/__exit__` (`:213-216`).
- Async mirror `AsyncHTTPConnection` adds `_connect`, `aclose`, `handle_async_request` (verified by live dump).

## 7. `HTTP11Connection` / `HTTP2Connection` — the `(?)` resolved

### `HTTP11Connection` — YES, real, and the only protocol connection usable in our venv
Sync (`_sync/http11.py:43`):
```python
HTTP11Connection(origin: Origin, stream: NetworkStream, keepalive_expiry: float | None = None)  # :47
```
- `HTTPConnectionState` enum (`:36`); class constants `MAX_INCOMPLETE_EVENT_SIZE = 102400`, `READ_NUM_BYTES = 65536` (verified by live dump — note these are httpcore-level, distinct from h11's own `max_incomplete_event_size=16384` default).
- `handle_request` (`:65`) → `_send_request_headers` (`:140`) → `_send_request_body` (`:152`) → `_receive_response_headers` (`:170`) → `_receive_response_body` (`:196`), with `_send_event` (`:163`) / `_receive_event` (`:209`) driving the h11 state machine and `_response_closed` (`:238`) returning the connection to IDLE.
- Same lifecycle set as above: `close` (`:254`), `can_handle_request` (`:264`), `is_available` (`:267`), `has_expired` (`:274`), `is_idle` (`:288`), `is_closed` (`:291`), `info` (`:294`).
- `HTTP11ConnectionByteStream` (`:324`): `__init__(connection, request)` (`:325`), `__iter__` (`:330`), `close` (`:344`).
- `HTTP11UpgradeStream(NetworkStream)` (`:351`): `read` (`:356`), `write` (`:364`), `close` (`:367`), `start_tls` (`:370`), `get_extra_info` (`:378`) — post-101-Switching-Protocols raw stream.

### `HTTP2Connection` — exists in source but DEAD in our venv
Source (`_sync/http2.py:42`, `__init__` `:46`, `handle_request` `:85`, `_send_connection_init` `:189`) imports `h2.config/connection/events/exceptions/settings` at module top (verified lines 1-28). `h2` is **not installed** (verified: no `h2`/`hyper` in `site-packages`). Consequence: `import httpcore._sync.http2` raises `ImportError`; the top-level `HTTP2Connection` name only survives via the `except ImportError` stub (`__init__.py:52-65`). Passing `http2=True` to any pool/connection in our venv therefore fails. httpx's default (`http1=True, http2=False`) never touches it.

## 8. Proxy classes

### `HTTPProxy` / `AsyncHTTPProxy`
Sync (`_sync/http_proxy.py:54`, `class HTTPProxy(ConnectionPool)`; `__init__` `:59` — full 15-param signature verified live: `proxy_url, proxy_auth, proxy_headers, ssl_context, proxy_ssl_context, max_connections, max_keepalive_connections, keepalive_expiry, http1, http2, retries, local_address, uds, network_backend, socket_options`).
- `create_connection(origin)` (`:146`) picks per-origin strategy:
- `ForwardHTTPConnection` (`:169`, `__init__` `:170`, `handle_request` `:191`) — plain-HTTP requests are forwarded absolute-URI to the proxy.
- `TunnelHTTPConnection` (`:233`, `__init__` `:234`, `handle_request` `:265`) — HTTPS goes through `CONNECT` tunnel establishment, then TLS over the tunnel; `connect_response.extensions["network_stream"]` (`:299`) is the established tunnel stream.
- `merge_headers` helper (`:35`).

### `SOCKSProxy` / `AsyncSOCKSProxy` — source-real, runtime-dead here
Sync (`_sync/socks_proxy.py:105`, `class SOCKSProxy(ConnectionPool)`; `__init__` `:110` params verified by `sed`: `proxy_url, proxy_auth=None, ssl_context=None, max_connections=10, max_keepalive_connections=None, keepalive_expiry=None, http1=True, http2=False, retries=0, network_backend=None`). Helpers `Socks5Connection` (`:189`), `AUTH_METHODS`/`REPLY_CODES` tables, `_init_socks5_connection()` (verified by file head). **But `import httpcore._sync.socks_proxy` raises `ModuleNotFoundError: No module named 'socksio'`** (verified live) — `socksio` is not in our venv, so neither SOCKS class is instantiable here. Async mirror (`_async/socks_proxy.py:105/110`, `AsyncSocks5Connection` `:189`) shares the fate.

## 9. `NetworkBackend` system (`httpcore/_backends/`)

Base contracts (`_backends/base.py`):
- `NetworkStream` (`:14`): `read(max_bytes, timeout=None) -> bytes` (`:15`), `write(buffer, timeout=None)` (`:18`), `close` (`:21`), `start_tls(ssl_context, server_hostname=None, timeout=None)` (`:24`), `get_extra_info(info) -> Any` (`:32`).
- `NetworkBackend` (`:36`): `connect_tcp(host, port, timeout=None, local_address=None, socket_options=None)` (`:37`), `connect_unix_socket(path, timeout=None, socket_options=None)` (`:47`), `sleep(seconds)` (`:55`).
- `AsyncNetworkStream` (`:59`) / `AsyncNetworkBackend` (`:81`) — same shapes with `aclose()` and coroutines (verified by live dump).

Concrete backends:
- `SyncBackend(NetworkBackend)` (`_backends/sync.py:187`): `connect_tcp` (`:188`), `connect_unix_socket` (`:218`). Streams: `SyncStream` (`:120`, wraps `socket.socket`) and `TLSinTLSStream` (`:23`, `# pragma: no cover` — TLS-over-proxy path).
- `AnyIOBackend(AsyncNetworkBackend)` (`_backends/anyio.py:97`) with `AnyIOStream` (`:21`). This is the backend httpx actually exercises under asyncio.
- `TrioBackend(AsyncNetworkBackend)` (`_backends/trio.py:109`) with `TrioStream` (`:21`, `_get_socket_stream` `:101`). trio is not in our dependency closure (**unverified** whether installed — not checked; treat trio path as unavailable until proven).
- `AutoBackend(AsyncNetworkBackend)` (`_backends/auto.py`, full source verified): lazy `_init_backend()` calls `current_async_library()` (`_synchronization.py`) and picks `TrioBackend` under trio, else `AnyIOBackend`. `connect_tcp`/`connect_unix_socket`/`sleep` all delegate after init.
- `MockBackend(NetworkBackend)` (`_backends/mock.py:58`, `__init__(buffer: list[bytes], http2=False)` `:59`) with `MockStream` (`:24`); async twins `AsyncMockBackend` (`:119`) / `AsyncMockStream` (`:85`); `MockSSLObject` (`:16`, `selected_alpn_protocol`). Test-only fakes exported at top level.

## 10. Exceptions (`httpcore/_exceptions.py`) — ALL 15

| Class | Line | Base | Meaning |
|---|---|---|---|
| `ConnectionNotAvailable` | :18 | `Exception` | Pool has no usable connection (saturated/closed) |
| `ProxyError` | :22 | `Exception` | Proxy handshake/tunnel failure (incl. SOCKS auth mismatch) |
| `UnsupportedProtocol` | :26 | `Exception` | Requested protocol unsupported (e.g. http2 without `h2`) |
| `ProtocolError` | :30 | `Exception` | Base for wire-protocol violations |
| `RemoteProtocolError` | :34 | `ProtocolError` | Server sent garbage / violated HTTP |
| `LocalProtocolError` | :38 | `ProtocolError` | We attempted an illegal protocol action |
| `TimeoutException` | :45 | `Exception` | Base for all timeouts |
| `PoolTimeout` | :49 | `TimeoutException` | Waited too long for a pooled connection |
| `ConnectTimeout` | :53 | `TimeoutException` | TCP/TLS establishment timed out |
| `ReadTimeout` | :57 | `TimeoutException` | Response read stalled |
| `WriteTimeout` | :61 | `TimeoutException` | Request-body write stalled |
| `NetworkError` | :68 | `Exception` | Base for transport failures |
| `ConnectError` | :72 | `NetworkError` | TCP/TLS connect failed (refused/unreachable) |
| `ReadError` | :76 | `NetworkError` | Socket read failed mid-response |
| `WriteError` | :80 | `NetworkError` | Socket write failed mid-request |

`map_exceptions` context manager (`:8`) translates backend exceptions into the above. httpx maps every one of these to its own hierarchy (`httpx/_transports/default.py:74-91`, verified by grep).

## 11. SSL, tracing, extensions

- `default_ssl_context()` (`_ssl.py:6`): `ssl.create_default_context()` + `load_verify_locations(certifi.where())` — i.e. the **certifi CA bundle**, not the Android trust store (dep-httpx-cluster.md).
- `Trace` (`_trace.py:11`): `__init__` (`:12`), `trace(name, info)` (`:30`), sync `__enter__/__exit__` (`:49/:55`), async `atrace` (`:69`), `__aenter__/__aexit__` (`:89/:95`). Enabled via `request.extensions["trace"]` hook.
- `extensions` keys observed in installed source (all verified by grep): `timeout` dict with `connect/read/write/pool` sub-keys (`_sync/connection.py:106-108`), `sni_hostname` (`:107`), `trace` (above), `target` (request-target override, `_models.py`), `network_stream` (tunnel/upgrade handoff, `http_proxy.py:299`). Timeout values flow from httpx's `Timeout` config; unset keys mean no timeout for that phase.

## 12. Internal layout — which half is dead code for us

Mirrored trees: `_sync/` (connection.py, connection_pool.py, http11.py, http2.py, http_proxy.py, interfaces.py, socks_proxy.py) and `_async/` (same filenames, `Async*` names). `_backends/` holds both sync (`sync.py`, `mock.py` sync halves) and async (`anyio.py`, `trio.py`, `auto.py`, `mock.py` async halves) implementations. `__init__.py` re-exports both halves unconditionally (except the two optional stubs).

For OUR app: **both halves are currently dormant** — flet imports httpx only inside `auth/` methods and we ship no OAuth flow (dep-httpx-cluster.md), so no pool, connection, or backend code executes at runtime. If OAuth is ever added, the reachable half is determined by the httpx client flavor used (`Client` → sync tree + `SyncBackend`; `AsyncClient` → async tree + `AutoBackend`→`AnyIOBackend` on asyncio). The `h2`/`socksio` branches are dead regardless until those packages are added.

## 13. How it serves us — httpx → httpcore call chain

httpx transport selection (`httpx/_transports/default.py`, verified lines): `HTTPTransport.__init__` builds `httpcore.ConnectionPool(...)` (`:156-164`, passing `ssl_context, max_connections, max_keepalive_connections, keepalive_expiry, http1, http2, uds, local_address`) or `httpcore.HTTPProxy(...)` (`:169-177`) / `httpcore.SOCKSProxy(...)` (`:196-204`) when a proxy is configured; `AsyncHTTPTransport` mirrors with `AsyncConnectionPool` (`:300-308`). Requests become `httpcore.Request(...)` (`:237-239`) and flow `httpx.Client.handle_request → transport.handle_request → pool.handle_request → HTTPConnection._connect → HTTP11Connection (h11) → socket`. Exception translation is total: every httpcore exception in §10 maps to an `httpx.*Error` (`:74-91`).

What breaks at each layer and what you actually see (via httpx):
- Pool saturation → `httpcore.PoolTimeout` → `httpx.PoolTimeout`.
- TCP refused/DNS fail → `httpcore.ConnectError` → `httpx.ConnectError`.
- TLS verify fail (certifi bundle) → `ConnectError`-family → `httpx.ConnectError` (check `ssl_context`/`certifi` first).
- Server garbage → `httpcore.RemoteProtocolError` → `httpx.RemoteProtocolError`.
- Proxy CONNECT/SOCKS failure → `httpcore.ProxyError` → `httpx.ProxyError`.
- Phase timeouts → `ConnectTimeout/ReadTimeout/WriteTimeout` → matching `httpx.*Timeout`.

Async backend selection on Android (practical): `AutoBackend` sniffs the running loop (`current_async_library`); under Flet's asyncio runtime that resolves to `AnyIOBackend` (asyncio path). No trio dependency, no special Android socket code — plain BSD sockets through anyio. Keep network I/O off the Flet UI thread exactly as M3 prescribes for proot-distro (`asyncio.to_thread` for sync clients; `await AsyncClient` for async).

## 14. Fullest utilization — direct use vs httpx, tied to milestones

Honest default: **stay on httpx.** It owns timeout config, exception mapping, proxy routing, and connection limits with a stable API; dropping to httpcore buys control at the cost of owning all of that. Reach for httpcore directly only for:
- **M3 distro-manager downloads (only if we ever bypass httpx):** `ConnectionPool(max_connections, keepalive_expiry, retries)` tuning + `stream()` + `iter_stream()` for large rootfs layers with backpressure; `Trace` hook for byte-level progress (note: proot-distro itself uses sync `urllib`, not httpcore — this applies to OUR supplementary downloads, not upstream's).
- **Proxy control:** `HTTPProxy(proxy_url, proxy_auth, proxy_headers, proxy_ssl_context)` for authenticated corporate proxies; `SOCKSProxy` only after adding `socksio` to deps (currently uninstallable — do not plan on it for M3).
- **Tests:** `MockBackend(buffer=[...])` / `AsyncMockBackend` for offline OAuth-flow tests without sockets (ports to the M3 `FakePage`-style offline suite).
- **Protocol debugging:** `HTTP11Connection` + `info()`/`is_idle()`/`has_expired()` introspection when diagnosing keepalive bugs against a misbehaving mirror.
- Never for: general GET/POST (httpx), HTTP/2 (package absent), SOCKS today (package absent).

## 15. How this dependency makes our app significantly better than Termux's proot-distro

Termux's proot-distro is a shell-script + `proot` + `curl/wget` world: downloads are opaque subprocess pipes with no programmatic retry, no connection reuse across mirrors, and proxy support that depends on whatever the user's environment exports. httpcore (via httpx) gives our Flet app a structural edge:
1. **Pooled, keep-alive image downloads.** `max_connections`/`max_keepalive_connections`/`keepalive_expiry` let us pull multiple OCI layers over reused TLS connections instead of Termux's one-process-per-layer fetches — measurably faster multi-layer pulls on high-latency mobile networks.
2. **First-class proxy + auth.** `HTTPProxy` with `proxy_auth`/`proxy_headers` and per-origin tunneling beats Termux's env-var lottery — enterprise/campus users behind authenticating proxies can install distros where Termux scripts fail.
3. **Retry with backoff + phase timeouts.** `retries` (exponential backoff, `_sync/connection.py:25`) plus per-phase `connect/read/write/pool` timeouts turn flaky-mobile-network installs from hard failures into recoverable waits — Termux surfaces a dead `curl` exit code.
4. **Streaming with backpressure.** `stream()` + `iter_stream()` + `PoolByteStream.close()` let us write layers to disk chunk-by-chunk with progress and cancellation, instead of buffering whole layers in memory or shell pipes.
5. **Testable networking.** `MockBackend` lets us regression-test install-failure paths (timeouts, proxy errors, corrupt registries) fully offline in CI — Termux can only test against the live network.
Caveat (honest): items 1–4 activate only for HTTP we issue through httpx/httpcore; upstream proot-distro's own `pull_image` path uses `urllib` and is unaffected. The differentiator lands in OUR download/UI layers (M3), not inside upstream.

## 16. Verification

- Versions/exports: live `httpcore.__version__` + `httpcore.__all__`; `__init__.py:73-134`.
- Top-level API: `_api.py:10,51`.
- Models: `_models.py:19,40,53,85,109,142,161,182,316,366,496`.
- Pool: `_sync/connection_pool.py:17,43,48,128,182,199,270,341,347,389`.
- Connection: `_sync/connection.py:25,38,39,69,105,167,170,175,187,192,197,202,213`.
- HTTP/1.1: `_sync/http11.py:36,43,47,65,140,152,163,170,196,209,238,254,264,267,274,288,291,294,324,351`.
- HTTP/2 gating: `_sync/http2.py:1-46`; `h2` absence verified by `site-packages` listing.
- HTTP proxy: `_sync/http_proxy.py:35,54,59,146,169,233,299`.
- SOCKS: `_sync/socks_proxy.py:105,110,189`; `_async/socks_proxy.py:105,110,189`; `socksio` absence verified by live `ImportError`.
- Interfaces: `_sync/interfaces.py:20,21,53,83,87-130`.
- Backends: `_backends/base.py:14-81`; `_backends/sync.py:23,120,187`; `_backends/anyio.py:21,97`; `_backends/trio.py:21,109`; `_backends/auto.py` (full source); `_backends/mock.py:16-120`.
- Exceptions: `_exceptions.py:8-80`.
- SSL/trace: `_ssl.py:6`; `_trace.py:11-95`.
- httpx chain: `httpx/_transports/default.py:74-91,156-177,196-204,237-239,300-308`.
- Context: `docs/roadmap.md` (M3 service/progress rules), `docs/reference/dep-httpx-cluster.md` (dormancy, certifi, anyio notes).
