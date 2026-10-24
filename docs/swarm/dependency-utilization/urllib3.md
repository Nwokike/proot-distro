# urllib3 2.8.0 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/dependency-studies/urllib3.md`; `docs/decisions.md` (D-003); `pyproject.toml`; `uv.lock`; `build_flet_proot_wheel.py`; `src/services/update_service.py`; `src/services/proot_service.py`; `src/screens/views.py`; `.github/workflows/app.yml`; `.venv/Lib/site-packages/urllib3/` (`__init__.py`, `_version.py`, `util/retry.py`, `util/timeout.py`, `util/ssl_.py`, `poolmanager.py`, `connectionpool.py`); `.venv/Lib/site-packages/requests/adapters.py`; `.venv/Lib/site-packages/cookiecutter/zipfile.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/flet_cli/utils/template_cache.py`; `.venv/Lib/site-packages/proot_distro/helpers/download.py`; `.venv/Lib/site-packages/proot_distro/dirfd.py`; `.venv/Lib/site-packages/httpx/_client.py`; `.venv/Lib/site-packages/httpx/_config.py`; `.venv/Lib/site-packages/httpx/_transports/default.py`; `.venv/Lib/site-packages/httpcore/_sync/connection.py` · **Date:** 2026-10-20

## What it does / how the app uses it

**urllib3 2.8.0 is a build-host transitive dependency that our code never imports — not once, anywhere.** The chain is provable end to end from installed dist metadata:

- `.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA:18` → `Requires-Dist: cookiecutter>=2.6.0`
- `.venv/Lib/site-packages/cookiecutter-2.7.1.dist-info/METADATA:35` → `Requires-Dist: requests>=2.23.0`
- `.venv/Lib/site-packages/requests-2.34.2.dist-info/METADATA:36` → `Requires-Dist: urllib3<3,>=1.26`
- `.venv/Lib/site-packages/urllib3-2.8.0.dist-info/METADATA:34-41` → extras only (`brotli`, `h2`, `socks`, `zstd`); **no unconditional `Requires-Dist`** — urllib3 pulls in nothing of its own.

`flet-cli` is a **dev-group** member (`pyproject.toml:77-84`, `uv.lock:594-601` `[package.dev-dependencies] dev = [...]`), so the whole chain is dev-only.

**Is urllib3 in the shipped runtime closure? No.** `uv tree --no-dev` (the closure that becomes the APK) resolves to `flet, flet-ads, httpx, flet-terminal, proot-distro` and their transitives — **urllib3, requests, charset-normalizer and cookiecutter are absent**. Independently confirmed at the packaging layer: flet-cli builds the APK requirement list from `project.dependencies` + `tool.flet.<platform>.dependencies` only (`.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576`, `.venv/Lib/site-packages/flet_cli/utils/project_dependencies.py:110-133`), and our own shipped-dist inventory agrees (`src/screens/views.py:26-42` `_PY_DISTS` = proot-distro, flet, flet-ads, flet-terminal, msgpack, anyio, httpx, httpcore, h11, idna, certifi, typing-extensions, oauthlib, repath, six — **no urllib3**).

**Does any app or host path use urllib3 directly? No.** A repo-wide grep over `*.py`, `*.toml`, `*.yml`, `*.yaml`, `*.md` (excluding `.venv`, `.git`, `docs`) for the string `urllib3` returns **zero hits** — no import, no `HTTPAdapter(max_retries=Retry(...))`, no `PoolManager`, no `from urllib3.util.retry import Retry`. The only urllib reference in `src/` is the stdlib `urllib.parse` (`src/services/update_service.py:28`).

**Answers to the assignment's three questions, up front:**

1. **Dev-only?** Yes, provably (metadata chain above + `uv tree --no-dev` + the APK requirement builder + `_PY_DISTS`).
2. **Any app or host path uses urllib3 directly?** No. The two audited HTTP paths use **stdlib `urllib.request`** (builder) and **httpx** (app); neither reaches urllib3, and httpx cannot — httpx's stack is `httpx → httpcore → h11`, with urllib3 absent from its closure (`uv tree --no-dev` above).
3. **Does the builder's hand-rolled download loop reimplement urllib3's retry logic?** **No — the builder implements no retry logic at all.** `build_flet_proot_wheel.py:196-199` `_fetch` is a single `urllib.request.urlopen(req, timeout=TIMEOUT)` with no `try`/`except` anywhere on the fetch path. There is nothing to reimplement; the gap is *missing* retry, not *duplicated* retry. **Is that a real robustness gap? Yes** (F2) — but the fix is stdlib, because urllib3 is not reachable from that script (F3). The place where urllib3's retry semantics genuinely *are* partially reimplemented is the **runtime** dependency `proot-distro`'s `retry_http` (F1).

## Findings

### F1 · P2 · The runtime download path hand-rolls a *partial* reimplementation of urllib3's `Retry`: flat 5 s delay, no exponential backoff, no jitter, no `Retry-After`

- **Where:** `.venv/Lib/site-packages/proot_distro/helpers/download.py:512-536` (`retry_http`, `max_retries=5`, `retry_delay=5`), `:481-509` (`is_retryable_http_error`); reached from the app at `src/services/proot_service.py:212-223` (`install` → `proot_distro.commands.install` → `.venv/Lib/site-packages/proot_distro/commands/install.py:314` `download_file(...)` → `.venv/Lib/site-packages/proot_distro/helpers/download.py:595` `retry_http(...)`) and `src/services/proot_service.py:263-269` (`search_images` → `.venv/Lib/site-packages/proot_distro/helpers/docker/search.py:165`); also `.venv/Lib/site-packages/proot_distro/helpers/docker/pull.py:133`, `.venv/Lib/site-packages/proot_distro/helpers/docker/pull.py:346`, `.venv/Lib/site-packages/proot_distro/helpers/docker/layers.py:119`, `.venv/Lib/site-packages/proot_distro/helpers/docker/transport.py:226`.
- **What:** `retry_http` is a competent classifier (deterministic vs transient: `.venv/Lib/site-packages/proot_distro/helpers/download.py:494-495` re-raises 4xx except 408/429; `:496-498` refuses cert-verification and plaintext-HTTP-on-https; `:499-508` refuses `InvalidURL`/`RedirectRefused`/`InvalidRequest`) and it does bound attempts at 5 — but its delay is **constant** (`time.sleep(retry_delay)` with `retry_delay=5`, `.venv/Lib/site-packages/proot_distro/helpers/download.py:513`, `:536`) and it **never parses `Retry-After`**. Verified: `grep -rn "retry_after" .venv/Lib/site-packages/proot_distro/` returns **zero matches**, as does `grep -rniE "backoff|jitter|exponential"`.
  urllib3's `Retry` has all three: exponential backoff `backoff_factor * 2**(n-1)` capped at `backoff_max` (`.venv/Lib/site-packages/urllib3/util/retry.py:321-338`, `:232-233`, `:213`), jitter (`:241`, `:336-337`), and `Retry-After` parsing plus honouring (`:340-359` `parse_retry_after`, `:361-369` `get_retry_after`, `:394-397` `sleep` → `sleep_for_retry`, status set `{413,429,503}` at `:205`), plus per-cause budgets (connect/read/status/redirect/other, `:500-537`) and `status_forcelist` (`:435-436`).
- **Evidence:**
  ```
  $ grep -rn "retry_after" .venv/Lib/site-packages/proot_distro/
  (no output)
  $ grep -rniE "backoff|jitter|exponential" .venv/Lib/site-packages/proot_distro/
  (no output)
  $ .venv/Scripts/python.exe -c "import proot_distro.helpers.download"   # the retry module itself
  AttributeError: module 'os' has no attribute 'O_DIRECTORY'
  ```
  (`.venv/Lib/site-packages/proot_distro/helpers/download.py:512-536` in full:)
  ```python
  def retry_http(operation, *, what: str, max_retries: int = 5,
                 retry_delay: int = 5):
      for attempt in range(max_retries):
          try:
              return operation()
          except KeyboardInterrupt:
              raise
          except NETWORK_ERRORS as exc:
              if not is_retryable_http_error(exc) or attempt >= max_retries - 1:
                  raise
              log_info(...)
              time.sleep(retry_delay)
  ```
- **Fix / opportunity:** **this cannot be fixed in this repository.** `proot-distro` is a PyPI dependency (`pyproject.toml:14`), and BRIEF rule 4 forbids forking/vendoring/patching a third-party package; D-003 (`docs/decisions.md:12-13`) freezes the dependency set. The correct actions are: (a) **report upstream** — "honour `Retry-After` and use exponential backoff with jitter in `retry_http`", with the urllib3 `Retry` line references above as the model; (b) in the meantime, make the *symptom* legible — surface the last `Retry-After`/status in the app's failure message so a user can tell "server asked us to wait" from "network is down"; (c) **do not** reach for urllib3 (see F3). Also note the module is **not importable on Windows** — `proot_distro.helpers.download` fails at import with `AttributeError: module 'os' has no attribute 'O_DIRECTORY'` (`.venv/Lib/site-packages/proot_distro/dirfd.py:73`), so even a local port of the policy must be copied, not imported. (Correction to `docs/swarm/dependency-utilization/requests.md` F1, which says `proot_distro` "is not importable off-Linux": the **top-level package imports fine** on this Windows venv — `import proot_distro` → `OK` — it is the `helpers.download` / `dirfd` submodules that fail.)
- **Risk if ignored:** the app runs on phones over cellular/Wi-Fi, where transient failures and registry rate-limits are the norm. A registry that answers `429`/`503` with `Retry-After: 120` is retried 5 times, 5 seconds apart (20 s of hammering), and then fails — exactly the behaviour urllib3's `Retry` is designed to avoid. The user sees "install failed" with no way to know the server merely asked us to wait.

### F2 · P2 · The builder's download loop has **no** retry — it does not reimplement urllib3's retry logic, because it has none; one transient mirror error fails the whole release build

- **Where:** `build_flet_proot_wheel.py:196-199` (`_fetch`), `:202-210` (`_fetch_verified`), `:447-463` (`download_sources`), `:27` (`TIMEOUT = 120.0`), `:491-495` (per-arch loop → 3 `.deb` fetches per arch, 2 arches = 6 fetches); CI invocations `.github/workflows/app.yml:141` (apk job) and `:195` (aab job) — one bare command each, no retry wrapper.
- **What:** `_fetch` performs a **single** `urllib.request.urlopen(req, timeout=TIMEOUT)` and returns `resp.read()`; `_fetch_verified` calls it exactly once per package and then compares the sha256. There is no `try`/`except` on the fetch path — the file's only `try` blocks are in `collect_payloads` (`:274`, `:311`), never around `_fetch`. `urllib.request`'s default opener carries no retry handler (it is `HTTPDefaultErrorHandler` + `HTTPRedirectHandler` + the protocol handlers — no retry). So a TCP reset, a 502/503 from the `packages.termux.dev` mirror, or a DNS blip aborts the run with a raw traceback, and the whole APK/AAB job dies. urllib3's `Retry` — sitting unused in the same venv — is the only ready-made retry engine in the tree (`.venv/Lib/site-packages/urllib3/util/retry.py:43`, `:222-276`).
- **Evidence:**
  ```
  $ grep -n "try:\|except" build_flet_proot_wheel.py
  274:        try:                      # collect_payloads, ELF parse
  311:            try:                  # collect_payloads, optional dep
  ```
  (no handler around `_fetch`/`_fetch_verified`/`download_sources`.)
  ```python
  # build_flet_proot_wheel.py:196-199
  def _fetch(url: str) -> bytes:
      req = urllib.request.Request(url, headers={"User-Agent": UA})
      with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
          return resp.read()
  ```
- **Fix / opportunity:** add a small **stdlib** retry loop inside `_fetch` (3-5 attempts, exponential backoff with jitter, retry only on `urllib.error.URLError`/`OSError`/`http.client.HTTPException` and on 5xx/408/429; never on a deterministic 4xx) and abort the final URL if it is not `https://`. Port the *semantics* of `proot_distro.helpers.download.is_retryable_http_error` (`:481-509`) rather than importing it — the module is unimportable on Windows (F1) and the file's own docstring promises "**Stdlib only**" (`build_flet_proot_wheel.py:4-5`). **Do not** use urllib3 here: it is a dev-group transitive (F3) and depending on it would be a new dependency group, forbidden by D-003 without owner sign-off.
- **Overlap with the swarm:** this is the same defect already filed as `docs/swarm/dependency-utilization/requests.md` **F1 (P2)** — do not double-count it in the synthesis. This report adds only the urllib3-specific framing: urllib3's `Retry` is *present in the venv but unreachable from this script*, and the builder's loop does not reimplement it (there is nothing to reimplement).
- **Risk if ignored:** a flaky public mirror turns a green pipeline red for no product reason, twice per release (apk + aab jobs), costing a full CI cycle to re-run.

### F3 · P2 · urllib3 is dev-only and **structurally cannot** serve either audited HTTP path — so F1/F2 must be closed in stdlib, not by reaching for urllib3

- **Where:** `pyproject.toml:9-15` (runtime: flet, flet-ads, httpx, flet-terminal, proot-distro) vs `:77-84` (dev group: flet-cli, flet-desktop, pytest, pytest-timeout, ruff); `uv.lock:594-601`; `docs/decisions.md:12-13` (D-003 — "Any addition needs owner sign-off"); `src/screens/views.py:26-42`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576`.
- **What:** urllib3's three headline capabilities all live **outside** the app's reach:
  - **`Retry`** (`.venv/Lib/site-packages/urllib3/util/retry.py:43`, exported as `urllib3.Retry` at `.venv/Lib/site-packages/urllib3/__init__.py:23`, `:59`) — unreachable on-device (not a runtime dependency) and unreachable from the builder (not a declared dependency; the builder is stdlib-only by contract, `build_flet_proot_wheel.py:4-5`).
  - **Pooling** (`.venv/Lib/site-packages/urllib3/poolmanager.py:201-231`, `.venv/Lib/site-packages/urllib3/connectionpool.py:181-240`) — the app path already pools via httpx/httpcore (`.venv/Lib/site-packages/httpx/_config.py:159-182` `Limits`, `.venv/Lib/site-packages/httpx/_transports/default.py:299-311` `httpcore.AsyncConnectionPool`), and urllib3's *pool-level* default is `maxsize=1` (`.venv/Lib/site-packages/urllib3/connectionpool.py:186`) — weaker than what httpx already gives.
  - **TLS controls** (`.venv/Lib/site-packages/urllib3/util/ssl_.py:184-215` `create_urllib3_context` with `ssl_minimum_version`/`ssl_maximum_version`/`cert_reqs`/`ciphers`; `:108` `assert_fingerprint`; `.venv/Lib/site-packages/urllib3/connectionpool.py:1012-1033` `HTTPSConnectionPool` kwargs) — the app path gets its TLS from httpx's `create_ssl_context` (`.venv/Lib/site-packages/httpx/_transports/default.py:153`), the builder from the stdlib system trust store; neither could adopt urllib3's knobs without the dependency.
  And in the one place urllib3 *is* legally reachable — the `requests` adapter — **the retry is disabled by default**: `.venv/Lib/site-packages/requests/adapters.py:81` `DEFAULT_RETRIES = 0` and `:208-209` `self.max_retries = Retry(0, read=False)`, i.e. **zero** retries. So even mounting urllib3 through requests would give nothing until the adapter is explicitly configured.
- **Evidence:** `uv tree --no-dev` (full output, urllib3 absent):
  ```
  proot-distro-flet v1.0.0
  ├── flet v1.0.4
  │   ├── httpx v0.28.1
  │   │   ├── anyio v4.15.1 …
  │   │   ├── certifi v2026.7.22
  │   │   ├── httpcore v1.0.9
  │   │   └── idna v3.20
  │   ├── msgpack v1.2.3
  │   ├── oauthlib v4.0.0
  │   └── repath v0.9.0
  ├── flet-ads v1.0.4 …
  ├── flet-terminal v0.4.0 …
  ├── httpx v0.28.1 …
  └── proot-distro v5.10.0
  ```
- **Fix / opportunity:** none in code — this finding exists to **stop** the synthesis from proposing "use urllib3" as the fix for F1/F2. The sanctioned remedies are stdlib retry in the builder (F2) and an upstream report for `proot-distro` (F1). If the owner ever *does* want urllib3 in the host toolchain, the legal shape is `urllib3.Retry(total=5, backoff_factor=0.5, backoff_jitter=0.5, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","HEAD"], respect_retry_after_header=True)` mounted via `requests.adapters.HTTPAdapter(max_retries=…)` (`.venv/Lib/site-packages/requests/adapters.py:201-211`) — but that adds a declared dependency group and needs D-003 sign-off.
- **Risk if ignored:** the synthesis wastes a cycle on an out-of-scope proposal, or (worse) someone "fixes" the builder by `pip install urllib3` into a script whose contract says stdlib-only, reintroducing a supply-chain dependency into the release pipeline for no gain.

### F4 · P3 · Neither HTTP path has a total deadline; urllib3's `Timeout(total=…)` is the only total-budget primitive in the tree and is unused by both

- **Where:** builder `build_flet_proot_wheel.py:27` (`TIMEOUT = 120.0`) and `:198` (`urllib.request.urlopen(req, timeout=TIMEOUT)`); app `src/services/update_service.py:75` (`httpx.AsyncClient(timeout=4.0, follow_redirects=True)`).
- **What:** `urllib.request.urlopen(timeout=…)` sets a **per-socket-operation** timeout (connect and each read); a server that dribbles one byte every 119 s can hold the builder indefinitely. httpx's `timeout=4.0` sets **each** of connect/read/write/pool to 4 s (`.venv/Lib/site-packages/httpx/_config.py:127-130`) — again a per-phase budget, with no overall deadline. urllib3's `Timeout` is the one API in the tree with a real total budget: `.venv/Lib/site-packages/urllib3/util/timeout.py:109-118` (`total`, `connect`, `read`) with the docstring at `:56-60` — "the read timeout will be set to the time leftover from the connect attempt".
- **Evidence:** `.venv/Lib/site-packages/httpx/_config.py:127-130`
  ```python
  self.connect = timeout if isinstance(connect, UnsetType) else connect
  self.read    = timeout if isinstance(read, UnsetType) else read
  self.write   = timeout if isinstance(write, UnsetType) else write
  self.pool    = timeout if isinstance(pool, UnsetType) else pool
  ```
  (`Timeout.total` does not exist in httpx; `.venv/Lib/site-packages/urllib3/util/timeout.py:117` `self.total = self._validate_timeout(total, "total")`.)
- **Fix / opportunity:** stdlib, not urllib3 — wrap the builder's fetch in a `time.monotonic()` deadline and abort when exceeded (a two-line change in `_fetch`), and give the app's update check an overall deadline around `client.get` (the app-side half of this is already filed as `docs/swarm/dependency-utilization/httpx.md` **F7**; the builder half is new here).
- **Risk if ignored:** a slow or hostile mirror can pin a CI runner for hours instead of failing fast; on-device, an update check can outlive the screen it was scheduled from.

### F5 · P3 · urllib3's `Retry` is mounted nowhere even on the one path where it would be legal — and that path is dead in our CI, so the missed capability is worth ≈ 0

- **Where:** `.venv/Lib/site-packages/cookiecutter/zipfile.py:54` — `r = requests.get(zip_uri, stream=True, timeout=100)` — no `Retry` mounted, and requests' default adapter gives `Retry(0, read=False)` (`.venv/Lib/site-packages/requests/adapters.py:81`, `:208-209`), i.e. zero retries and no `status_forcelist`.
- **What:** this is the only place in the tree where a `Retry` object could legally be attached to urllib3 without a new dependency declaration. It is also **never taken by our CI**: flet-cli resolves the build template through its own stdlib cache — `.venv/Lib/site-packages/flet_cli/utils/template_cache.py:38` `urllib.request.urlopen(url)` + `shutil.copyfileobj` — and then hands cookiecutter a **local** path: `.venv/Lib/site-packages/flet_cli/commands/build_base.py:1859-1861` `template_url = str(get_cached_template_zip(template_source, template_ref))`, passed as `cookiecutter(template=template_url, …)` at `:1895-1905`. cookiecutter's `is_url` branch (the only one that calls `requests.get`) is selected by `is_repo_url`, which matches only `git://`, `ssh://`, `file://`, `http(s)://`, `user@host` — a local cache path is none of those.
- **Evidence:** `.venv/Lib/site-packages/flet_cli/utils/template_cache.py:38` uses **stdlib** `urllib.request`, not requests; `.venv/Lib/site-packages/flet_cli/commands/build_base.py:1895-1896` passes `template=template_url` (a `Path` stringified from the cache).
- **Fix / opportunity:** **none** — the branch is unreachable for us and the code is upstream's, not ours. Recorded so the synthesis does not treat it as an open opportunity.
- **Risk if ignored:** none for us. (For a hypothetical `flet create` against a *remote* template URL, cookiecutter's fetch would be retry-less — but that is upstream's surface, not this project's.)

## Missed capabilities (dependency audits only)

| Capability in urllib3 | API location | Proposed integration point | Value vs cost |
|---|---|---|---|
| Exponential backoff with jitter | `.venv/Lib/site-packages/urllib3/util/retry.py:321-338` (`get_backoff_time`), `:241` (`backoff_jitter`), `:213` (`backoff_max`) | `proot_distro.helpers.download.retry_http` — `.venv/Lib/site-packages/proot_distro/helpers/download.py:512-536` (runtime, on the app's install/search/pull path) | **High value** (mobile networks; five 5 s naps → proper ramp) / **Zero install cost** — but it is a third-party package, so this is an **upstream PR**, not a local change (BRIEF rule 4 forbids forks). |
| `Retry-After` honouring + 6 h clamp | `.venv/Lib/site-packages/urllib3/util/retry.py:340-359` (`parse_retry_after`), `:361-369` (`get_retry_after`), `:394-397` (`sleep`), `:205` (`RETRY_AFTER_STATUS_CODES`), `:217` (`retry_after_max`) | same as above | **High value** for registry `429`/`503` / **Zero install cost** / upstream-only. |
| `status_forcelist` retry on 5xx/429 | `.venv/Lib/site-packages/urllib3/util/retry.py:231`, `:435-436`, `:529-537` | same as above; today `retry_http` retries 5xx by accident of `HTTPError` classification (`.venv/Lib/site-packages/proot_distro/helpers/download.py:494-495`), not by an explicit list | Medium value / upstream-only. |
| Per-cause retry budgets (connect vs read vs status) | `.venv/Lib/site-packages/urllib3/util/retry.py:487-537` (`increment`) | `proot_distro` retry classifier | Medium — separates "server is down" from "your socket died" / upstream-only. |
| Total-deadline timeout | `.venv/Lib/site-packages/urllib3/util/timeout.py:109-118`, docstring `:56-60` | builder `_fetch` (`build_flet_proot_wheel.py:196-199`) — but implement in stdlib (`time.monotonic()` deadline), **not** by importing urllib3 | Medium value / very low cost / **stdlib**, because urllib3 is dev-only (F3). |
| TLS min/max version, fingerprint pinning | `.venv/Lib/site-packages/urllib3/util/ssl_.py:184-215`, `:108` (`assert_fingerprint`); `.venv/Lib/site-packages/urllib3/connectionpool.py:1028-1032` | none — our two hosts fetch public artifacts over verified TLS; the sha256 pin (`build_flet_proot_wheel.py:204-209`) is the stronger control | Low value / would add a dependency / **not recommended**. |
| Connection pooling + keep-alive | `.venv/Lib/site-packages/urllib3/poolmanager.py:201-231`, `.venv/Lib/site-packages/urllib3/connectionpool.py:181-240` | none — httpx/httpcore already pool on the app path (`.venv/Lib/site-packages/httpx/_transports/default.py:299-311`); the builder fetches 3 files per arch, too few to matter; urllib3's pool default `maxsize=1` (`.venv/Lib/site-packages/urllib3/connectionpool.py:186`) is no better | Low value / **not recommended**. |
| Cross-origin credential stripping on redirect | `.venv/Lib/site-packages/urllib3/util/retry.py:207-210` (`DEFAULT_REMOVE_HEADERS_ON_REDIRECT`), applied at `.venv/Lib/site-packages/urllib3/connectionpool.py:922-929` and `.venv/Lib/site-packages/urllib3/poolmanager.py:487-494` | none — neither of our paths sends `Authorization`/`Cookie` (builder sets only `User-Agent`, `build_flet_proot_wheel.py:197`), and `proot-distro` already strips credentials across origins on its registry transport (`.venv/Lib/site-packages/proot_distro/helpers/download.py:29-32`) | **Zero gap** — already covered. |

## Verified-good list

- **urllib3 is genuinely dev-only and genuinely unused by us.** Zero direct imports repo-wide; absent from `uv tree --no-dev`; absent from the APK requirement build (`.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576`); absent from `_PY_DISTS` (`src/screens/views.py:26-42`); `flet-cli` is dev-group only (`pyproject.toml:79`, `uv.lock:594-601`). Nothing about urllib3 can reach the device.
- **urllib3 is the reason the dev toolchain has a modern TLS floor.** `.venv/Lib/site-packages/urllib3/__init__.py:29-46` raises `ImportError` on OpenSSL < 1.1.1 and warns `NotOpenSSLWarning` on non-OpenSSL builds — a free CI-runner hygiene check that fails loudly instead of negotiating weak TLS. Verified at the installed source.
- **urllib3 2.8.0 has no runtime dependencies of its own** — `urllib3-2.8.0.dist-info/METADATA:34-41` lists only extras (`brotli`, `h2`, `socks`, `zstd`). It cannot drag anything into the closure.
- **The `Retry` API surface the study documented is intact in the installed tree** — `Retry.__init__` at `.venv/Lib/site-packages/urllib3/util/retry.py:222-276` with every knob (`total=10` default at `:224`, `allowed_methods` at `:230`, `status_forcelist` at `:231`, `backoff_factor` at `:232`, `backoff_max` at `:233`, `respect_retry_after_header` at `:237`, `remove_headers_on_redirect` at `:238-240`, `backoff_jitter` at `:241`, `retry_after_max` at `:242`); `from_int` at `:303-319`; `Retry.DEFAULT = Retry(3)` at `:569`; `method_whitelist` is indeed **gone** (no hits in `retry.py`; only `allowed_methods` at `:230`, `:265`, `:419`). The study's §4 is accurate.
- **`remove_headers_on_redirect` really is applied**, not merely declared: `.venv/Lib/site-packages/urllib3/connectionpool.py:922-929` (pool-level) and `.venv/Lib/site-packages/urllib3/poolmanager.py:487-494` (manager-level) strip `Cookie`/`Authorization`/`Proxy-Authorization` on a cross-host redirect.
- **Our own paths never send credentials**, so the urllib3 redirect-stripping gap does not exist for us: the builder sets only `User-Agent` (`build_flet_proot_wheel.py:197`, `:28`); `update_service.py` sends no auth headers; and `proot-distro`'s registry transport already strips credentials across origins (`.venv/Lib/site-packages/proot_distro/helpers/download.py:29-32`).
- **`httpx` genuinely cannot do status-based retries**, so the urllib3 `status_forcelist` capability has no httpx equivalent we could switch to: `.venv/Lib/site-packages/httpx/_transports/default.py:147`, `:291` (`retries: int = 0`) is forwarded to `httpcore`, whose retry block catches **only** `ConnectError`/`ConnectTimeout` (`.venv/Lib/site-packages/httpcore/_sync/connection.py:159-165`). The app's `AsyncClient` builds its default transport with no `retries` argument (`.venv/Lib/site-packages/httpx/_client.py:1445-1452`), i.e. `retries=0`.
- **`src/services/update_service.py` is syntactically valid on this interpreter** — `except TypeError, ValueError:` at `:63` is legal under PEP 758 in Python 3.14.7; `ast.parse` yields `Tuple(elts=[Name('TypeError'), Name('ValueError')])`, `py_compile` succeeds, and `ruff check` passes. (Flagged here only so a sibling file-audit does not report it as a syntax error.)
- **The builder's integrity control is strong and independent of the transport**: every fetched `.deb` is sha256-pinned and verified before use (`build_flet_proot_wheel.py:202-210`, pins at `:44`, `:48`, `:58`, `:63`, `:68`, `:73`), so a corrupted or tampered download fails the build loudly rather than shipping.

## Unverified

- **Whether the CI mirror `packages.termux.dev` actually returns transient 5xx/429 under load.** The absence of retry in the builder is proven from source (`build_flet_proot_wheel.py:196-210`); the *frequency* of transient failures is not measured — no production incident data was available to this audit.
- **Whether flet-cli's APK packager would pick up urllib3 if it were somehow a runtime dependency.** The current exclusion is proven (`.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576` reads only `project.dependencies` + `tool.flet.<platform>.dependencies`), but the packager's full resolution rules for `tool.flet.<platform>.dependencies` extras were not traced end to end.
- **Whether `proot-distro` upstream would accept a `Retry-After`/backoff change to `retry_http`.** The defect is proven in the installed 5.10.0 source; the upstream disposition is unknown.
- **The `Retry` counters' exact exhaustion semantics for `total=None` combos** (e.g. `Retry(total=None, read=0)`) were read from `increment`/`is_exhausted` (`.venv/Lib/site-packages/urllib3/util/retry.py:445-462`, `:464-559`) but not exercised at runtime.
- **Whether the `Retry` capability gap on the app's update-check path (`src/services/update_service.py:70-102`) is better solved by urllib3 or by httpx.** `httpx.md` F4 already owns that finding; this audit did not re-litigate it.
- **The claim that urllib3's `Timeout(total=…)` is *the only* total-budget primitive in the tree** was checked against `urllib3/util/timeout.py` and `httpx/_config.py`; the stdlib `http.client`/`urllib.request` timeout model was reasoned about from the stdlib docs but **not** re-verified line-by-line in `.venv` (the stdlib is not vendored in the venv tree).
