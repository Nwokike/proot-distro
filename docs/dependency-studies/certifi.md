# certifi 2026.7.22 — API reference

Verified 2026-10-16 against installed source
`/home/maikel/.zcode/workspace/default/proot-distro-flet/.venv/Lib/site-packages/certifi`
(py3.14 venv; flet stays 1.0.4 per roadmap D-010).
Context read first: `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md`.
Anti-hallucination rule: every claim cites installed file:line; anything not
verified in source is labeled **unverified**.

---

## 1. Identity

| Field | Value | Source |
|---|---|---|
| Name | `certifi` | `certifi-2026.7.22.dist-info/METADATA:2` (`Name: certifi`) |
| Version | `2026.7.22` | `certifi/__init__.py:4` (`__version__ = "2026.07.22"`); METADATA `Version: 2026.7.22` |
| License | MPL-2.0 | `certifi-2026.7.22.dist-info/METADATA:8` (`License: MPL-2.0`); classifier `License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)` (METADATA:12); `License-File: LICENSE` |
| What it is | Curated Mozilla CA bundle (`cacert.pem`) + two accessor functions | `certifi/core.py:1-7` module docstring ("returns the installation location of cacert.pem or its contents"); `certifi/__init__.py:1-4` |
| Pure-Python? | Yes — single `import sys` + `importlib.resources` + `atexit` | `certifi/core.py:7-8`, `:16`, `:51` |
| Type hints shipped | Yes (`py.typed` present; asserted by upstream's own test) | `certifi/tests/test_certify.py` (`test_py_typed_exists`); venv file listing |

Package file list (venv `certifi/` directory):
`__init__.py` (4 lines), `__main__.py` (12), `cacert.pem` (240 216 bytes),
`core.py` (83), `py.typed`, `tests/` (`__init__.py`, `test_certify.py`).
Whole directory ≈ 247 477 bytes on disk (du; includes `__pycache__`).

---

## 2. Complete API

The entire public surface is two functions (`certifi/__init__.py:1-3`:
`from .core import contents, where`; `__all__ = ["contents", "where"]`).
There is nothing else — no classes, no constants, no configuration.

### 2.1 `where() -> str` (`certifi/core.py:21-44` on py ≥ 3.11)

Returns the filesystem path of `cacert.pem`. Verified runtime value:

```
/home/maikel/.zcode/workspace/default/proot-distro-flet/.venv/Lib/site-packages/certifi/cacert.pem
```

Implementation details that matter:

- Lazy extraction: uses `importlib.resources.as_file(files("certifi")...)`
  (`core.py:16,40`); the context manager is held in module-global
  `_CACERT_CTX` with an `atexit` cleanup registration (`core.py:11`,
  `:18-19`, `:27-42`) so zipimport users get a real temp path exactly once.
- Result cached in `_CACERT_PATH` (`core.py:28,44`): first call extracts,
  subsequent calls return the stored string. Not thread-synchronized —
  **unverified** whether concurrent first-calls could double-extract (source
  shows no lock; in practice benign: same path recomputed).
- Legacy branch (`core.py:49-80`) for py < 3.11 uses deprecated
  `importlib.resources.path`/`read_text`. Dead code on our floor (py3.14)
  but still shipped.

### 2.2 `contents() -> str` (`certifi/core.py:46-47` on py ≥ 3.11)

Returns the whole bundle as one ASCII `str`:
`files("certifi").joinpath("cacert.pem").read_text(encoding="ascii")`.
Verified at runtime: `len(contents())` ≈ bundle size (240 216 chars), first
line `# Issuer: CN=COMODO ECC Certification Authority O=COMODO CA ...`.
Use when you need the PEM text (e.g. concatenating a private CA); prefer
`where()` for anything taking a file path.

### 2.3 `core` internals

- `exit_cacert_ctx()` (`core.py:10-11`) — atexit hook closing `_CACERT_CTX`.
- `_CACERT_CTX` / `_CACERT_PATH` (`core.py:18-19`, `:53-54`) — module-global
  extraction cache described above.
- `__main__.py` (12 lines): CLI — `python -m certifi` prints `where()`;
  `python -m certifi -c/--contents` prints `contents()`.
- `tests/test_certify.py`: three upstream self-tests — bundle exists,
  contents contain `-----BEGIN CERTIFICATE-----`, `py.typed` exists.

### 2.4 What is NOT in the API (common misconceptions)

- No update/download mechanism. certifi never fetches anything; freshness =
  release version only (see §4).
- No `SSLContext` factory, no `verify=` handling — that lives in httpx /
  httpcore (§3). certifi only supplies the PEM bytes/path.
- No platform trust-store bridging. It does not read Android, Windows, or
  macOS system stores (see §5).

---

## 3. How TLS trust flows (httpx / httpcore default cafile)

Two independent default paths, both terminating at `certifi.where()`:

**httpx** — `httpx/_config.py:create_ssl_context` (verified full body):

```python
def create_ssl_context(verify=True, cert=None, trust_env=True):
    ...
    if verify is True:
        if trust_env and os.environ.get("SSL_CERT_FILE"):      # _config.py:34-35
            ctx = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
        elif trust_env and os.environ.get("SSL_CERT_DIR"):     # _config.py:36-37
            ctx = ssl.create_default_context(capath=os.environ["SSL_CERT_DIR"])
        else:
            ctx = ssl.create_default_context(cafile=certifi.where())  # _config.py:40
    elif verify is False:                                      # _config.py:41-44
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    elif isinstance(verify, str):                              # _config.py:45-54
        ...deprecated... capath=verify if dir else cafile=verify
    else:
        ctx = verify                                           # _config.py:56 (caller-supplied context passes through)
```

So `httpx.AsyncClient()` defaults to `verify=True` → `cafile=certifi.where()`,
unless `SSL_CERT_FILE`/`SSL_CERT_DIR` env vars are set and `trust_env` is on
(`trust_env=True` default). A caller-supplied `ssl.SSLContext` bypasses
certifi entirely.

**httpcore** — `httpcore/_ssl.py` (whole file, 8 lines):

```python
import ssl
import certifi

def default_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.load_verify_locations(certifi.where())
    return context
```

Note the difference: httpx passes the bundle as the *sole* `cafile` to
`create_default_context`, while httpcore creates the default context first
(which loads platform defaults where the platform provides them) and then
*adds* certifi via `load_verify_locations`. On Android both effectively mean
"the pinned Mozilla bundle" since the Flet-bundled OpenSSL has no system
store to contribute — but the httpx form is the stricter of the two
(bundle-only). Exact on-device OpenSSL behaviour is **unverified** until M0.

Dormancy (same as idna): flet reaches httpx only through lazily-imported
auth code (`flet/auth/authorization_service.py:119,207,248`,
`flet/auth/providers/github_oauth_provider.py:43`), so no TLS context is
built on our launch path. Corroborates
`docs/reference/dep-httpx-cluster.md:16`.

---

## 4. Bundle size + update cadence

- **Size:** `cacert.pem` = 240 216 bytes on disk (`du -sb`); 121
  `BEGIN CERTIFICATE` blocks (grep count); `contents()` length matches at
  runtime. Matches the "240 KB" figure in
  `docs/reference/dep-httpx-cluster.md:12`.
- **Cadence:** certifi versions ARE bundle dates — `2026.7.22` = Mozilla
  bundle as of 2026-07-22. There is no in-band update: freshness advances
  only when the `certifi` version floor moves in our lockfile. Quote the
  reference doc: "certifi pins a build-time CA bundle (240 KB) instead of the
  Android trust store" (`docs/reference/dep-httpx-cluster.md:18,34` context).
- **Operational consequence:** a CA added/removed by Mozilla reaches our app
  only via dependency bump → lockfile moves → CI rebuilds (the standard
  "bump a version" update path, `docs/roadmap.md:15`). No code change, no
  store interaction. Conversely, an emergency CA distrust (e.g. a
  compromised intermediate) cannot be pushed to installed APKs except through
  an app update — accepted risk, documented here so M5/M6 planning sees it.

---

## 5. The Android trust-store divergence

Quoting the reference doc verbatim (`docs/reference/dep-httpx-cluster.md:18`):

> **certifi = build-time-pinned Mozilla bundle, not the Android system trust
> store** — OS-level CA changes are invisible to httpx calls (fine for public
> endpoints).

What this means concretely:

1. httpx/httpcore TLS in our app trusts exactly the 121 CAs in the pinned
   `cacert.pem`, regardless of what the user or OEM added/removed in Android
   Settings → Security → Trusted credentials.
2. A user-installed enterprise MITM CA (common on corporate devices) will NOT
   be trusted → TLS failures on managed devices, with no settings-screen fix.
3. Conversely, a CA the user distrusted at OS level is STILL trusted by our
   httpx calls. Exposure window ends only at the next certifi bump (§4).

### Concrete guidance for our app

**Our endpoints (all public CAs — fine, no action):**

| Endpoint | Used for | Trust basis |
|---|---|---|
| Docker Hub (`registry-1.docker.io`, `auth.docker.io`) | OCI image pulls (certified distros `ubuntu:24.04`, `debian:bookworm`, `alpine:3.21`; arbitrary OCI refs) | Public CA in Mozilla bundle |
| GitHub (`github.com`, `objects.githubusercontent.com`, `api.github.com`) | CI artifact download (`build-<sha>` prereleases → phone, `docs/roadmap.md:43`); release metadata | Public CA in Mozilla bundle |
| apt mirrors (`deb.debian.org`, `archive.ubuntu.com`, `dl-cdn.alpinelinux.org`, ports/security variants) | In-guest `apt update && apt install` (M0 gate 3) | Public CAs — **plus**: guest-side apt uses the *guest* CA store inside the rootfs, not certifi at all. certifi only covers Python-side HTTPS (OCI pulls, GitHub). Do not conflate the two. |

Note on proot-distro's own download stack: it uses stdlib `urllib`
(`proot_distro/helpers/docker/transport.py:342` comment "The program's own
opener, like every other request: urlopen()"; `push.py:36-37` imports
`urllib.error/parse`), NOT httpx — so OCI pulls go through the platform
default SSL context, not certifi. httpx+certifi only engages if/when
`flet.auth` OAuth runs. Both paths trust public CAs for our endpoints, but
they are different code paths — a future custom-CA fix must cover both (see
next paragraph).

**If a private mirror ever needs a custom CA** (corporate registry mirror,
self-hosted apt proxy — none planned today):

- httpx path: pass `verify=` explicitly. `verify=<path-to-pem>` is
  deprecated (`httpx/_config.py:46-54` DeprecationWarning); the supported
  form is `verify=ssl.create_default_context(cafile=<combined-pem>)`
  (`httpx/_config.py:47-49` message text). Build the combined PEM as
  `certifi.contents()` + private CA text, or `where()` path + extra file.
  `verify=False` exists (`_config.py:41-44`) but MUST NOT ship — it disables
  hostname checking too.
- stdlib/urllib path (proot-distro pulls): `SSL_CERT_FILE` env var is
  honoured by httpx's `trust_env` branch (`httpx/_config.py:34-35`) but
  proot-distro's urllib opener behaviour with env CAs is **unverified** — do
  not assume; test on-device in the milestone that introduces the mirror.
- Either change is public-surface configuration (constructor arg / env var),
  NOT a patch of upstream — stays inside the "no patching" owner constraint
  (`docs/roadmap.md:14`).

---

## 6. How this dependency makes our app significantly better than Termux's proot-distro

Termux inherits the device's OpenSSL + system CA store through `curl`/system
Python: trust behaviour varies by OEM, OS patch level, and user-installed
credentials. Two identical Termux installs on different phones can disagree
about whether a mirror's certificate validates — a support nightmare for a
consumer app.

Our app gets:

1. **Identical trust on every device.** The 121-CA Mozilla bundle ships IN
   the APK (`cacert.pem`, 240 216 B). A Debian mirror TLS handshake behaves
   the same on a Pixel, a Samsung, and a five-year-old OEM fork, because none
   of them consults the OEM store on the httpx path. Reproducible TLS =
   reproducible bug reports.
2. **Atomic CA updates with the app.** A certifi bump rides the normal
   version-bump → lockfile → CI → release ritual (`docs/roadmap.md:15,113`);
   every user on the new build has byte-identical trust. Termux users get CA
   changes whenever their OS/package updates them — staggered, silent, and
   outside our control.
3. **Small, auditable surface.** Two functions, no platform branches
   (`core.py` is `sys.version_info`-only). The whole trust story fits in §2
   above; there is no per-OEM matrix to maintain.
4. **Escape hatches that respect the architecture.** `verify=<SSLContext>`
   passthrough (`httpx/_config.py:56`) and `SSL_CERT_FILE`/`SSL_CERT_DIR`
   (`_config.py:34-37`) give a future private-mirror story without touching
   upstream code — versus Termux, where per-mirror CA pinning means editing
   device-global config the app doesn't own.

---

## 7. Verification

- `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md` read first;
  reference-doc quotes cited with file:line (`dep-httpx-cluster.md:12,16,18`).
- `where()` return value, `__version__`, `contents()` length/prefix verified
  at runtime via `python.exe -c`.
- httpx `create_ssl_context` body quoted from installed
  `httpx/_config.py:20-70`; httpcore `_ssl.py` quoted whole (8 lines).
- flet lazy-httpx imports verified by grep
  (`flet/auth/authorization_service.py:119,207,248`,
  `flet/auth/providers/github_oauth_provider.py:43`).
- proot-distro urllib usage verified by grep
  (`helpers/docker/transport.py:342`, `push.py:36-37`).
- Sizes: `cacert.pem` 240 216 B (`du -sb`); 121 certificates (grep count);
  `certifi/` dir 247 477 B.
- Items marked **unverified** were not observable in installed source.
