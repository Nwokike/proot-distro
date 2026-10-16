# requests 2.34.2 — exhaustive API reference

Verified 2026-10-16 against the INSTALLED source in `.venv/Lib/site-packages/requests`
(`C:\Users\nwoki\.zcode\workspace\default\proot-distro-flet\.venv\Lib\site-packages\requests`).
Project context read first: `docs/roadmap.md` + `docs/reference/dep-cookiecutter-stack.md`.
Flet app; flet stays 1.0.4 (D-010).
**Anti-hallucination rule (owner-mandated):** every API claim below cites installed
source (`requests/<file>:<line>`) or the installed dist metadata; anything not verifiable
in source is labeled **unverified**.

## 1. Identity

- Name/version: `requests 2.34.2` (`requests/__version__.py`: `__version__ = "2.34.2"`,
  `__title__`, `__description__ = "Python HTTP for Humans."`; dist metadata
  `requests-2.34.2.dist-info/METADATA:2-3` `Name: requests` / `Version: 2.34.2`).
- License: **Apache-2.0** (`METADATA:9` `License: Apache-2.0`; `License-File: LICENSE, NOTICE`).
- `Requires-Python: >=3.10` (METADATA). Our venv runs 3.14 — inside the floor.
- **Pure Python.** Module tree (`requests/`): `__init__.py`, `__version__.py`, `_types.py`,
  `_internal_utils.py`, `adapters.py`, `api.py`, `auth.py`, `certs.py`, `compat.py`,
  `cookies.py`, `exceptions.py`, `help.py`, `hooks.py`, `models.py`, `packages.py`,
  `sessions.py`, `status_codes.py`, `structures.py`, `utils.py`, plus `py.typed`
  (typed package). No compiled extensions.
- Hard runtime deps (`METADATA:34-37`): `charset_normalizer<4,>=2`, `idna<4,>=2.5`,
  `urllib3<3,>=1.26`, `certifi>=2023.5.7`. Installed: charset-normalizer 3.5.2,
  urllib3 2.8.0 (both inside their ceilings — bump together per dep-cookiecutter-stack.md).
- Extras (`METADATA:40,42`): `socks` (`PySocks!=1.5.7,>=1.5.6`), `use-chardet-on-py3`
  (`chardet<8,>=3.0.2`). Our venv HAS chardet 5.2.0 (via binaryornot→cookiecutter) —
  see §9 for which detector actually wins at runtime.
- Top-level exports (`requests/__init__.py:161-200`): the 8 api shortcuts
  (`delete, get, head, options, patch, post, put, request`), exceptions
  (`ConnectionError, ConnectTimeout, FileModeWarning, HTTPError, JSONDecodeError,
  ReadTimeout, RequestException, Timeout, TooManyRedirects, URLRequired`),
  models (`PreparedRequest, Request, Response`), `Session, session`, `codes`.
  (Full `__all__` tuple continues past the verified lines — **unverified** tail.)
- Boot-time compatibility gate (`requests/__init__.py:60-125`): `check_compatibility()`
  asserts urllib3 major≥1 (minor≥21 if 1.x) and charset-normalizer in `[2.0.0, 4.0.0)`
  (or chardet in `[3.0.2, 8.0.0)`); mismatch → `RequestsDependencyWarning`, not an error.
  SNI fallback: if `ssl.HAS_SNI` is false, injects `urllib3.contrib.pyopenssl`
  (`requests/__init__.py:130-140`).

## 2. Module-level API — `requests/api.py` (every shortcut, every kwarg)

All shortcuts open a throwaway `Session` in a `with` block and close it
(`requests/api.py:69-72`) — convenient, but no connection reuse across calls.
The kwarg shapes are PEP-692 TypedDicts in `requests/_types.py:140-180`:

- `BaseRequestKwargs`: `headers, cookies, files, auth, timeout, allow_redirects,
  proxies, hooks, stream, verify, cert`.
- `RequestKwargs` (for `request/options/head/delete`) adds `params, data, json`.
- `GetKwargs` adds `data, json` (params is positional). `PostKwargs` adds `params`
  (data/json positional). `DataKwargs` (for `put/patch`) adds `params, json`.

| Function (`api.py` line) | Signature shape |
|---|---|
| `request` (:24) | `(method, url, **RequestKwargs)` — method is any verb string |
| `get` (:74) | `(url, params=None, **GetKwargs)` |
| `options` (:90) | `(url, **RequestKwargs)` |
| `head` (:102) | `(url, **RequestKwargs)` |
| `post` (:117) | `(url, data=None, json=None, **PostKwargs)` |
| `put` (:137) | `(url, data=None, **DataKwargs)` |
| `patch` (:154) | `(url, data=None, **DataKwargs)` |
| `delete` (:171) | `(url, **RequestKwargs)` |

Kwarg semantics (from the `request()` docstring, `api.py:24-68`, identical set on
`Session.request`, `sessions.py:557-654`):

- `params` — dict / list-of-tuples / bytes appended to the query string.
- `data` — dict / list-of-tuples / bytes / file-like body (`KVDataType | str | bytes |
  Buffer | SupportsRead | None`; `_types.py:95-115`).
- `json` — any JSON-serializable object; serialized with `complexjson.dumps` and sets
  `Content-Type: application/json` unless already set (models `prepare_body`).
- `headers` — `Mapping[str, str | bytes] | None`.
- `cookies` — `RequestsCookieJar | CookieJar | dict[str,str] | None`.
- `files` — `{name: fileobj | (filename, fileobj) | (filename, fileobj, content_type) |
  (filename, fileobj, content_type, custom_headers)}` → multipart upload.
- `auth` — `(user, pass)` tuple → Basic, or `AuthBase`/callable (see §6).
- `timeout` — float, or `(connect, read)` tuple; `None` = wait forever (default).
- `allow_redirects` — default `True`.
- `proxies` — `{scheme-or-scheme://host: proxy_url}`; merged with env (see §3).
- `hooks` — `{"response": callable-or-list}` — the ONLY hook event (`hooks.py:22`
  `HOOKS = ["response"]`).
- `stream` — `False` (default) downloads immediately; `True` defers to `iter_content`.
- `verify` — `True` (certifi CA) / `False` (INSECURE, testing only) / CA-bundle path.
- `cert` — client cert path str, or `(cert, key)` tuple.

## 3. `Session` — `requests/sessions.py`

Constructor (`Session.__init__`, :442) sets EVERY default; the picklable state is exactly
`__attrs__` (:415-441): `headers, cookies, auth, proxies, hooks, params, verify, cert,
adapters, stream, trust_env, max_redirects`.

| Setting | Default | Source |
|---|---|---|
| `headers` | `default_headers()` (`User-Agent: python-requests/<ver>` + `Accept-Encoding: gzip, deflate` + `Accept: */*` + `Connection: keep-alive`) | :442-448, `utils.py:942-963` |
| `auth` | `None` | :450-453 |
| `proxies` | `{}` | :455-459 |
| `hooks` | `default_hooks()` (`{"response": []}`) | :458, `hooks.py:25` |
| `params` | `{}` (merged into every request) | :460-464 |
| `stream` | `False` | :466-467 |
| `verify` | `True` | :469-479 |
| `cert` | `None` | :481-483 |
| `max_redirects` | `DEFAULT_REDIRECT_LIMIT` = 30 (`models.py:104`) | :485-488 |
| `trust_env` | `True` (read proxy/CA env vars) | :490-492 |
| `cookies` | empty `RequestsCookieJar` (`cookiejar_from_dict({})`) | :494-498 |
| `adapters` | `OrderedDict` with `HTTPAdapter()` mounted on `https://` and `http://` | :500-502 |

Methods (line refs are `sessions.py`):

- `request(method, url, params, data, headers, cookies, files, auth, timeout,
  allow_redirects=True, proxies, hooks, stream, verify, cert, json)` (:557) — builds a
  `Request` (upper-cases method, decodes bytes urls), `prepare_request()`,
  `merge_environment_settings()`, then `send()`. Bytes URL? decoded as UTF-8 first.
- Verb helpers: `get` (:655), `options` (:673), `head` (:684), `post` (:695),
  `put` (:714), `patch` (:728), `delete` (:742) — same kwarg shapes as §2.
- `prepare_request(request)` (:511) — merges session+request settings (`merge_setting`
  :76: request-level wins unless `None`; `merge_hooks` :108: session hooks run FIRST),
  builds `PreparedRequest`, applies session cookies/auth/params/headers.
- `send(request, **kwargs)` (:752) — adapter dispatch. Requires a `PreparedRequest`
  (raises `ValueError` on a raw `Request`). Sets `r.elapsed`, dispatches `response`
  hooks, persists cookies into the session jar, resolves redirects when
  `allow_redirects`, and touches `r.content` when not streaming.
- Redirect machinery lives in `SessionRedirectMixin`:
  `resolve_redirects(resp, req, ...)` (:186, generator; raises `TooManyRedirects` at
  `len(history) >= max_redirects`, :216-218), `rebuild_auth` (:309 — strips
  `Authorization` when `should_strip_auth` :154 says the host changed, except for
  allowed same-host redirect paths), `rebuild_proxies` (:334, honors `NO_PROXY`),
  `rebuild_method` (:370 — 303/302/301 rewrite POST→GET, 303 drops body; 307/308 keep
  method+body), `get_redirect_target` (:134), `should_strip_auth` (:154).
- `merge_environment_settings(url, proxies, stream, verify, cert)` (:831) — when
  `trust_env`: env proxies via `get_environ_proxies` honoring `no_proxy` (:847-852),
  and `REQUESTS_CA_BUNDLE`/`CURL_CA_BUNDLE` override `verify` (:856-860). Then merges
  explicit-arg → session-level for proxies/stream/verify/cert.
- `get_adapter(url)` (:870) — longest-prefix match over mounted adapters; no match →
  `InvalidSchema`. `mount(prefix, adapter)` (:888) — re-sorts so LONGER prefixes win.
  `close()` (:883) closes all adapters (drains urllib3 pools).
- Pickle: `__getstate__/:__setstate__` (:899-906) round-trip `__attrs__`.
- `session()` factory (:908) — **deprecated since 1.0.0**, kept for BC; use `Session()`.

## 4. `Request` / `PreparedRequest` / `Response` — `requests/models.py`

`Request` (:283): user-facing, constructor `(method, url, headers, files, data, params,
auth, cookies, hooks, json)` (:321); `prepare()` (:358) returns `PreparedRequest`;
hook mixin `register_hook/deregister_hook` (`RequestHooksMixin`, :258-281).
`RequestEncodingMixin` (:109): `path_url` property (:113), `_encode_params` (:152,
multi-overload: dict/list/tuple/str/bytes/file-like), `_encode_files` (:184,
multipart).

`PreparedRequest` (:376): blank-slate `__init__` (:405: `method/url/headers/body/hooks`
+ `_cookies=None` + `_body_position=None`); `prepare(...)` (:422) runs the pipeline
`prepare_method` (:465) → `prepare_url` (:481, IDNA-encodes host via
`_get_idna_encoded_host` :472, requotes URI) → `prepare_headers` (:563) →
`prepare_body` (:574: urlencoded vs multipart vs json vs raw stream) →
`prepare_content_length` (:652) → `prepare_auth` (:668) → `prepare_cookies` (:697,
Cookie header generated ONCE — later calls are no-ops unless the header is removed)
→ `prepare_hooks` (:720). `copy()` (:454) deep-copies for digest-auth replays.

`Response` (:730): instance attrs set in `__init__` (:763) — `status_code, headers
(CaseInsensitiveDict), raw, url, encoding (None until sniffed), history [],
reason, cookies, elapsed (timedelta), request`; `_content=False`,
`_content_consumed=False`. Properties: `ok` (:860, `<400`), `is_redirect` (:875:
`"location" in headers and status in REDIRECT_STATI`), `is_permanent_redirect`
(:882: 301/308 with `Allow` semantics), `next` (:890: next redirect when redirects
disabled), `content` (:1031: consumes `raw` ONCE via `iter_content(CONTENT_CHUNK_SIZE)`,
`CONTENT_CHUNK_SIZE = 10*1024`, :106), `text` (:1050: header charset → else
`apparent_encoding`; undecodable bytes → `errors="replace"`), `apparent_encoding`
(:895: `chardet.detect(content)["encoding"]`, `"utf-8"` fallback), `links` (:1123:
parsed `Link` header dict). Methods: `json(**kwargs)` (:1087: `guess_json_utf`
detection :1102 then `complexjson.loads`; failure → `JSONDecodeError`),
`iter_content(chunk_size=1, decode_unicode=False)` (:912: streams `raw` with
`ProtocolError→ChunkedEncodingError`, `DecodeError→ContentDecodingError`,
`ReadTimeoutError→ConnectionError` translation; consumed body → `StreamConsumedError`),
`iter_lines(chunk_size=512, decode_unicode=False, delimiter=None)` (:990),
`raise_for_status()` (:1140: 4xx→"Client Error", 5xx→"Server Error" `HTTPError` with
`response=` attached; reason bytes tried as UTF-8 then latin-1), `close()` (:1169),
context-manager + `__bool__` (`ok`) + pickle support.
Redirect set: `REDIRECT_STATI = (301, 302, 303, 307, 308)` (:96-103).

## 5. Exceptions tree — `requests/exceptions.py`

Root `RequestException(IOError)` (:20) carries `.response` + `.request` (auto-linked
from `response.request`). Tree:

- `InvalidJSONError(RequestException)` (:38) → `JSONDecodeError(InvalidJSONError,
  json.JSONDecodeError)` (:42, pickle-safe `__reduce__`).
- `HTTPError(RequestException)` (:66) — also what `raise_for_status` raises.
- `ConnectionError(RequestException)` (:70) → `ProxyError` (:74), `SSLError` (:78),
  + `ConnectTimeout(ConnectionError, Timeout)` (:91, "safe to retry").
- `Timeout(RequestException)` (:82, catches BOTH timeout flavors) → `ConnectTimeout`
  (above), `ReadTimeout` (:98).
- Flat `RequestException`s: `URLRequired` (:102), `TooManyRedirects` (:106),
  `MissingSchema/InvalidSchema/InvalidURL` (all also `ValueError`, :110-118),
  `InvalidHeader` (:122), `InvalidProxyURL(InvalidURL)` (:126),
  `ChunkedEncodingError` (:130), `ContentDecodingError(RequestException,
  urllib3.HTTPError)` (:134), `StreamConsumedError(RequestException, TypeError)`
  (:138), `RetryError` (:142), `UnrewindableBodyError` (:146).
- Warnings: `RequestsWarning(Warning)` (:153) → `FileModeWarning(+DeprecationWarning)`
  (:157), `RequestsDependencyWarning` (:161, version-mismatch path).

`HTTPAdapter.send` maps urllib3 failures onto this tree (`adapters.py:698-730`):
`(ProtocolError, OSError)→ConnectionError`; `MaxRetryError` reason-sniffing →
`ConnectTimeout` / `RetryError` (ResponseError) / `ProxyError` / `SSLError` /
fallback `ConnectionError`.

## 6. `auth` — `requests/auth.py`

- `AuthBase` (:78): `__call__(r) -> PreparedRequest` contract (raises
  `NotImplementedError`); any callable with that shape works as `auth=`.
- `HTTPBasicAuth(username, password)` (:85, str-or-bytes overloads :92-96):
  sets `Authorization: Basic base64(user:pass)` via `_basic_auth_str` (:34).
  `__eq__/__ne__` compare both fields (:100-109).
- `HTTPProxyAuth(HTTPBasicAuth)` (:116): sets `Proxy-Authorization` instead (:119).
- `HTTPDigestAuth(username, password)` (:124): per-thread state
  (`init_per_thread_state` :147: `last_nonce/nonce_count/chal/pos/num_401_calls`);
  `__call__` (:321) registers `response` hooks `handle_401` + `handle_redirect` and
  records body position for rewind; `handle_401` (:273) answers ONE 401 round-trip
  (parses `WWW-Authenticate: Digest`, replays a copied `PreparedRequest` with the
  digest header, appends original to `.history`); `build_digest_header(method, url)`
  (:157) supports MD5/MD5-SESS/SHA/SHA-256/SHA-512 (`hashlib`, `usedforsecurity=False`).
- Tuple `auth=(u, p)` auto-becomes `HTTPBasicAuth` in `prepare_auth` (`models.py:668+`).
- URL-embedded creds (`user:pass@host`) extracted by `get_auth_from_url`
  (`utils.py:1070`); netrc honored via `get_netrc_auth(url)` (`utils.py:231`,
  `NETRC` env override) during `Session.prepare_request`.

## 7. `cookies` — `requests/cookies.py`

`RequestsCookieJar(CookieJar)` (:191): dict-like over a real cookiejar —
`get/set/keys/values/items (+iter* variants)` (:211-301), `list_domains/list_paths`
(:302-318), `get_dict(domain, path)` (:331), `__getitem__/__setitem__/__delitem__`
(:358-380, ambiguous names → `CookieConflictError` :185 unless domain/path given via
`_find/_find_no_duplicates` :401-453), `update/copy/get_policy`, pickle support
(:454-474). Module helpers: `extract_cookies_to_jar` (:135, `MockRequest/MockResponse`
adapters :31-132 let stdlib cookiejar read `PreparedRequest`/urllib3 responses),
`get_cookie_header` (:153), `remove_cookie_by_name` (:164),
`create_cookie/morsel_to_cookie` (:494-563), `cookiejar_from_dict` (:564+3 overloads),
`merge_cookies` (:604). Session↔response flow: `Session.send` extracts into
`session.cookies`; `HTTPAdapter.build_response` extracts into `response.cookies`.

## 8. `adapters` (+ urllib3 Retry/TLS landscape) — `requests/adapters.py`

- `BaseAdapter` (:122): `send(request, stream, timeout, verify, cert, proxies)` (:128),
  `close()` (:153) — subclass to add transports (e.g. mock adapters in tests).
- `HTTPAdapter(BaseAdapter)` (:158): THE urllib3 bridge.
  `__init__(pool_connections=10, pool_maxsize=10, max_retries=0, pool_block=False)`
  (:201-220; module defaults `DEFAULT_POOLSIZE=10, DEFAULT_RETRIES=0,
  DEFAULT_POOLBLOCK=False, DEFAULT_POOL_TIMEOUT=None`, :79-82).
  - `max_retries`: int → `Retry.from_int()`; `0` → `Retry(0, read=False)` (:208-211).
    **Default = NO retries on connect** — idempotent CI polling must opt in with
    `HTTPAdapter(max_retries=Retry(...))` mounted via `session.mount()`.
  - `init_poolmanager/connections` (:239), `proxy_manager_for` (:269),
    `cert_verify(conn, url, verify, cert)` (:307: https+verify → `CERT_REQUIRED` with
    `DEFAULT_CA_BUNDLE_PATH = certs.where()` (`utils.py:82`, i.e. certifi); else
    `CERT_NONE`; client `cert` → `conn.cert_file/key_file` with existence checks),
    `build_response(req, urllib3_resp)` (:365: status/headers→CaseInsensitiveDict,
    `encoding = get_encoding_from_headers()`, wires `raw/reason/url/cookies/request`),
    `build_connection_pool_key_attributes` (:403: pool key includes verify+cert so
    different TLS configs never share a pool), `get_connection_with_tls_context`
    (:455), `get_connection` (:512), `request_url` (:565: proxy-aware URL),
    `add_headers` (:599: UA/keep-alive/timeout wiring), `proxy_headers` (:613).
  - `send(...)` (:634): resolves timeout (`tuple→Timeout(connect, read)`,
    urllib3-Timeout passthrough, float→both; the urllib3 class is imported AS
    `TimeoutSauce` (:32) to avoid clashing with `requests.exceptions.Timeout`),
    calls `conn.urlopen(..., redirect=False, assert_same_host=False,
    preload_content=False, decode_content=False, retries=self.max_retries, ...)`.
- urllib3 deprecation/feature landscape relevant TODAY (verified in OUR tree):
  `Retry(allowed_methods=...)` is the current knob — no `method_whitelist` string
  remains in `urllib3/util/retry.py` (grep-verified absent; the rename is complete
  in 2.8.0). `ssl_version` exact-value param of `create_urllib3_context` is
  deprecated in favor of `ssl_minimum/maximum_version` (`urllib3/util/ssl_.py`
  docstring). `RequestsDependencyWarning` silences urllib3 `DependencyWarning`
  (`requests/__init__.py` + `warnings.simplefilter`). PyOpenSSL injection happens
  ONLY when stdlib lacks SNI — inert on modern hosts.

## 9. `structures`, `status_codes`, `hooks`, `utils` highlights, `help/certs/packages`

- `structures.py`: `CaseInsensitiveDict(MutableMapping)` (:20: `__setitem__/
  __getitem__/__delitem__/__iter__/__len__/__eq__/copy/lower_items`, :49-99) —
  THE headers type everywhere; `LookupDict` (:101: attr-or-item access, `get`,
  :105-131) backs `codes`.
- `status_codes.py`: `codes` LookupDict built by `_init()` (:109) from `_codes`
  (`200: ok/okay/all_ok/...`, `418: teapot`, joke keys `"\\o/"→200` etc.); upper- and
  lower-case names both work.
- `hooks.py`: `default_hooks()` (:25) → `{"response": []}`; `dispatch_hook(key, hooks,
  data)` (:32): single callable auto-wrapped; a hook returning non-None REPLACES the
  response.
- `utils.py` toolbox (line-verified): `default_user_agent()` (:942),
  `default_headers()` (:951), `get_environ_proxies/no_proxy` handling
  (:873 `get_environ_proxies`, :810 `should_bypass_proxies` with CIDR support),
  `get_encoding_from_headers` (:569), `get_encodings_from_content` (:522),
  `guess_json_utf` (:1008), `requote_uri/unquote_unreserved` (:704/:680),
  `parse_header_links` (:965, feeds `Response.links`), `dict_from_cookiejar/
  add_dict_to_cookiejar` (:500/:511), `check_header_validity` (:1087, illegal bytes
  → `InvalidHeader`), `rewind_body` (:1139, file-body rewind for redirects/retries),
  `select_proxy/resolve_proxies` (:885/:911), `atomic_open` (:329), `super_len`
  (:160, `FileModeWarning` on text-mode files).
- Which charset detector runs HERE: `compat.py:_resolve_char_detection` tries
  `chardet` FIRST, then `charset_normalizer`. Our venv contains chardet 5.2.0
  (binaryornot dep), so `Response.apparent_encoding`/`text` currently resolve
  through **chardet**, while `charset_normalizer` 3.5.2 remains the declared hard
  dep (`METADATA:34`). Behavior note, not a bug — both satisfy
  `check_compatibility`. If chardet ever leaves the tree, detection silently
  switches to charset-normalizer with slightly different guess names.
- `help.py:info()` (:69) — bug-report dict (platform, urllib3/chardet/
  charset-normalizer/cryptography/idna versions); `certs.where()` = certifi bundle
  path (`certs.py:15`); `packages.py` aliases `requests.packages.urllib3/idna`
  (and chardet) to the real modules for ancient BC.

## 10. How it serves us — cookiecutter template-zip download (host-only)

- Single in-repo call site: `cookiecutter/zipfile.py:54`
  `r = requests.get(zip_uri, stream=True, timeout=100)` + `iter_content(chunk_size=1024)`
  write loop — the `cookiecutter --zip remote-template` download path. requests is a
  declared dep of cookiecutter (`cookiecutter-2.7.1.dist-info/METADATA:35`
  `Requires-Dist: requests>=2.23.0`), and cookiecutter is a declared dep of flet-cli
  (`flet_cli-1.0.4.dist-info/METADATA:18` `cookiecutter>=2.6.0`). No other installed
  package imports requests (repo-wide grep: only `cookiecutter/zipfile.py` + requests'
  own modules).
- Trust-boundary nuance (dep-cookiecutter-stack.md §Trust boundary): flet-cli's OWN
  `template_cache.py:38` fetches `flet-build-template.zip` via **stdlib
  `urllib.request.urlopen`** + `shutil.copyfileobj` — NOT via requests. So requests
  serves the `flet create --template <remote zip>`/cookiecutter path, while the
  main build-template fetch bypasses it. Both are network-facing: keep this stack
  current.
- CI-only presence: our `pyproject.toml` runtime `dependencies` are
  `flet, flet-ads, flet-terminal, proot-distro` — requests appears ONLY via the
  `dev` group (`flet-cli` → cookiecutter → requests). **NEVER ships in the APK.**
  Guarantee chain: (1) `uv.lock` records requests/charset-normalizer under the
  cookiecutter subtree (`uv.lock:731-737` requests entry lists
  `certifi/charset-normalizer/idna` deps — a host wheel `py3-none-any`, no Android
  tag); (2) `flet build apk` packs project runtime deps, not the `dev` group;
  (3) the on-device downloader (`proot_distro/helpers/download.py:42-44`) uses
  **stdlib `urllib.request`** — requests is not even importable on-device to lean on.
  (APK-packing claim (2) isNama build-system behavior — **unverified** from source;
  (1) and (3) are source-verified.)

## 11. How this makes our app better than Termux's proot-distro (honest, concrete)

Termux's proot-distro is POSIX shell: downloads via `curl` with ad-hoc flags, no
structured errors, no connection reuse. Our position is tooling/CI-side, NOT
on-device (proot-distro itself deliberately uses stdlib urllib — zero-dep purity
that we must NOT break by suggesting requests inside the app):

- **Reliable CI asset fetches.** `stream=True + iter_content` keeps multi-hundred-MB
  template/rootfs-adjacent downloads constant-memory; `timeout=100` precedent in
  `zipfile.py:54` bounds hangs. A Termux-style `curl -sSL` in CI gives you an exit
  code; `raise_for_status()` gives you WHICH url failed with headers attached.
- **Retryable registry polling.** `Session + HTTPAdapter(max_retries=Retry(total=…,
  backoff_factor=…, status_forcelist=[429,500,502,503,504]))` survives PyPI/GitHub
  flakiness in release tooling — shell `curl --retry` can't do Retry-After-aware
  backoff with method whitelisting.
- **Debuggable failures.** Structured exceptions (§5) + `r.elapsed` + `r.history`
  turn "CI download flaked" into an actionable log line; `help.info()` gives a
  paste-ready env report.
- **TLS without thinking.** certifi bundle via `certs.where()` + `REQUESTS_CA_BUNDLE`
  env override works on every CI runner without touching system stores.
- What it does NOT do: nothing on-device, nothing for the guest distros, nothing for
  `proot_distro` downloads (stdlib urllib there — verified §10). Any "better" claim
  beyond host/CI tooling would be dishonest.

## 12. Fullest utilization for our tooling — requests vs httpx

House position (roadmap R2): we standardized on **httpx** elsewhere — flet itself
imports httpx only for OAuth (`flet/auth/`), and the httpx/httpcore/h11/anyio/idna/
certifi cluster ships in the app tree. requests arrives ONLY as cookiecutter's
transitive dep on the host.

- **Recommendation: keep requests indirect; write NEW tooling on httpx.**
  (a) Consistency: one HTTP idiom (`httpx.Client(timeout=…, follow_redirects=…)`)
  across CI scripts, matching the in-app stack. (b) Capability: httpx gives
  sync+async from one API, HTTP/2 option, and connection `Limits` — requests is
  sync-only with 10-connection pools. (c) Footprint honesty: depending on requests
  directly would bless a second TLS/session stack in our dependency story for zero
  gain, since it is already pinned transitively (`uv.lock:731`).
- **When requests is still the right call:** inside cookiecutter's own path (not
  ours to rewrite); one-off scripts that must run where only requests is
  guaranteed (it is the most vendored lib in the ecosystem); and cases needing
  `PreparedRequest` surgery or netrc support (`get_netrc_auth`) that httpx
  equivalents handle differently. If you do use it: ALWAYS pass `timeout=`,
  ALWAYS `Session()`-as-context-manager for pooling, mount an explicit
  `Retry` adapter for registry polling, and never `verify=False` outside localhost.
- No action needed on the pin: `requests+urllib3+charset-normalizer` bump as a
  group (dep-cookiecutter-stack.md §Bump groups; ceilings `urllib3<3`,
  `charset_normalizer<4`).

## 13. Verification refs

- Installed: `.venv/Lib/site-packages/requests` (api :24/:74/:90/:102/:117/:137/:154/:171;
  sessions :76/:108/:127/:186/:309/:334/:370/:395/:442/:557/:655-742/:752/:831/:870/
  :883/:888/:899/:908; models :69/:96/:104/:109/:258/:283/:376/:730/:895/:912/:990/
  :1031/:1050/:1087/:1123/:1140/:1169; adapters :32/:79-82/:122/:158/:201/:307/:365/
  :403/:455/:512/:565/:599/:613/:634/:698; auth :34/:78/:85/:116/:124/:147/:157/:268/
  :273/:321; cookies :31/:135/:153/:164/:185/:191/:494/:564/:604; exceptions :20-161;
  structures :20/:101; status_codes :109; hooks :22/:25/:32; utils :82/:500/:569/
  :942/:951/:965/:1008/:1070/:1087; certs :15; help :69; `__init__` :60/:130).
- Dist metadata: `requests-2.34.2.dist-info/METADATA` (deps :34-37, extras :40/:42).
- Lock: `uv.lock:731-737` (requests 2.34.2 + certifi/charset-normalizer/idna edges).
- Call site: `.venv/Lib/site-packages/cookiecutter/zipfile.py:54`;
  dep edge `cookiecutter-2.7.1.dist-info/METADATA:35`;
  `flet_cli-1.0.4.dist-info/METADATA:18` (cookiecutter≥2.6.0);
  `flet_cli/utils/template_cache.py:38` (stdlib urllib path, NOT requests).
- On-device contrast: `.venv/Lib/site-packages/proot_distro/helpers/download.py:42-44`
  (stdlib urllib).
- Context: `docs/roadmap.md` (dep table D3, §5 trust boundary), `pyproject.toml:9-26`
  (runtime vs dev groups).
