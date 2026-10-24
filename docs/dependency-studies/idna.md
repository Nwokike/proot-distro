# idna 3.20 — API reference

Verified 2026-10-16 against installed source
`/home/maikel/.zcode/workspace/default/proot-distro-flet/.venv/Lib/site-packages/idna`
(py3.14 venv; flet stays 1.0.4 per roadmap D-010).
Context read first: `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md`.
Anti-hallucination rule: every claim cites installed file:line; anything not
verified in source is labeled **unverified**.

---

## 1. Identity

| Field | Value | Source |
|---|---|---|
| Name | `idna` | `idna-3.20.dist-info/METADATA:2` (`Name: idna`) |
| Version | `3.20` | `idna/package_data.py:1` (`__version__ = "3.20"`); METADATA `Version: 3.20` |
| Summary | Internationalized Domain Names in Applications (IDNA) | `idna-3.20.dist-info/METADATA:4` |
| License | BSD-3-Clause | `METADATA:8` (`License-Expression: BSD-3-Clause`); `License-File: LICENSE.md` (`METADATA:28`) |
| Unicode data version | `18.0.0` | `idna/idnadata.py:3` (`__version__ = "18.0.0"`); `idna/uts46data.py:10` (same); re-exported as `idna.unicode_version` via `idna/__init__.py:21` |
| Standard implemented | IDNA 2008 (RFC 5891), plus UTS #46 mapping (_opt-in_) | `idna/codec.py:9-18` docstring ("Stateless IDNA 2008 codec"); `idna/compat.py:8-18,21-31` (legacy RFC 3490 shims delegate to 2008); `idna/core.py:637` (`uts46_remap`, "mapping table from UTS #46 §4") |
| Pure-Python? | Yes — stdlib only (`bisect`, `re`, `unicodedata`, `warnings`, `codecs`, `argparse`) | `idna/core.py:3-7`, `idna/codec.py:3-4`, `idna/cli.py:8-11`, `idna/uts46data.py:5` (`from array import array`) |
| Type hints shipped | Yes (`py.typed` present) | directory listing (venv `idna/py.typed`); `idna/core.py:1` (`from __future__ import annotations`) |
| Role in this project | Transitive dep of httpx/anyio (IDN hostname encoding); dormant unless OAuth used | `docs/reference/dep-httpx-cluster.md:11,16` |

Package file list (venv `idna/` directory):
`__init__.py` (47 lines), `__main__.py` (6), `cli.py` (132), `codec.py` (225),
`compat.py` (43), `core.py` (863), `idnadata.py` (1933), `intranges.py` (55),
`package_data.py` (1), `py.typed`, `uts46data.py` (17117). Whole directory
≈ 397 141 bytes on disk (du; includes `__pycache__`).

---

## 2. Complete public API

### 2.1 Package surface (`idna/__init__.py:1-47`)

Re-exports from `.core` (`__init__.py:1-20`):

```python
from .core import (
    IDNABidiError, IDNAError, InvalidCodepoint, InvalidCodepointContext,
    alabel, check_bidi, check_hyphen_ok, check_initial_combiner,
    check_label, check_nfc, decode, encode, ulabel, uts46_remap,
    valid_contextj, valid_contexto, valid_label_length,
    valid_string_length,
)
from .idnadata import __version__ as unicode_version
from .intranges import intranges_contain
from .package_data import __version__
```

`__all__` (`__init__.py:25-47`): `__version__`, `unicode_version`,
`IDNABidiError`, `IDNAError`, `InvalidCodepoint`, `InvalidCodepointContext`,
`alabel`, `check_bidi`, `check_hyphen_ok`, `check_initial_combiner`,
`check_label`, `check_nfc`, `decode`, `encode`, `intranges_contain`,
`ulabel`, `uts46_remap`, `valid_contextj`, `valid_contexto`,
`valid_label_length`, `valid_string_length`.
Note: `intranges_from_list` (build-time helper) is deliberately NOT exported.

### 2.2 `encode` — all params (`idna/core.py:732-797`)

```python
def encode(
    s: str | bytes | bytearray,
    strict: bool = False,
    uts46: bool = False,
    std3_rules: bool = False,
    transitional: bool = False,
) -> bytes:
```

Behaviour per docstring + body (`core.py:733-757` and following lines):

- Splits input on label separators — only `U+002E` when `strict=True`,
  otherwise also `U+3002`, `U+FF0E`, `U+FF61` (via `_unicode_dots_re`,
  `core.py:17`); encodes each label with `alabel`; rejoins with `.`.
- `:param s:` domain to encode. Non-`str` input is coerced with
  `str(s, "ascii")`; failure raises `IDNAError(code="invalid_ascii")`.
- `:param strict:` separator strictness (above).
- `:param uts46:` if `True`, pre-process through `uts46_remap` first.
- `:param std3_rules:` forwarded to `uts46_remap` when `uts46` is `True`.
- `:param transitional:` **deprecated and ignored** — emits
  `DeprecationWarning` via `_warn_transitional()` (`core.py:628-635`) and
  "will be removed in a future version" (`core.py:750-753`).
- `:returns:` ASCII `bytes`.
- `:raises IDNAError:` empty domain, invalid label, over-length
  (`input_too_long` guard at `len(s) > _max_input_length`, `core.py:14`
  = 1024; `domain_too_long` via `valid_string_length`).

### 2.3 `decode` — all params (`idna/core.py:799-863`)

```python
def decode(
    s: str | bytes | bytearray,
    strict: bool = False,
    uts46: bool = False,
    std3_rules: bool = False,
    display: bool = False,
) -> str:
```

- Inverse of `encode`: splits on separators (same strict rule), decodes each
  label with `ulabel`, rejoins with `.` (`core.py:800-821` docstring).
- `s`/`strict`/`uts46`/`std3_rules`: same semantics as `encode`, except the
  remap call is `uts46_remap(s, std3_rules, False)` (`core.py` decode body).
- `:param display:` (`core.py:815-821`) — if `True`, any `xn--` label that
  fails validation is passed through unchanged (lowercased) instead of
  aborting. "Intended for 'decode for display' consumers (e.g. URL libraries,
  HTTP clients)". Matches per-label recovery of UTS #46 §4 and WHATWG URL
  "domain to Unicode". Decode loop implements it as
  `except IDNAError: if display and label[:4].lower() == "xn--": u = label.lower()`.
- `:returns:` Unicode `str`. `:raises IDNAError:` non-ASCII input
  (`invalid_ascii`), invalid label, empty domain (`empty_domain`).

### 2.4 Exceptions

- `IDNAError(UnicodeError)` (`core.py:70-107`) — base for everything.
  Carries machine-readable attributes (NOT just message text):
  `code` (stable rule id), `text` (label/domain under validation),
  `codepoint` (`int`), `position` (1-based). Each `None` when N/A.
  Constructor: `__init__(*args, code=None, text=None, codepoint=None,
  position=None)` (`core.py:95-107`).
- Stable `code` vocabulary (`core.py:39-67`, `_ErrorCode` Literal):
  `input_too_long`, `label_too_long`, `domain_too_long`, `empty_label`,
  `empty_domain`, `not_nfc`, `hyphen_3_4`, `hyphen_start_end`,
  `leading_combiner`, `disallowed_codepoint`, `contextj`, `contexto`,
  `unknown_codepoint`, `bidi_rule_1`…`bidi_rule_6`,
  `bidi_unknown_direction`, `invalid_alabel`, `non_canonical_alabel`,
  `invalid_ascii`, `invalid_utf8`, `uts46_disallowed`, `uts46_std3`,
  `unsupported_errors`.
- `IDNABidiError(IDNAError)` (`core.py:110-111`) — bidi rule failure.
- `InvalidCodepoint(IDNAError)` (`core.py:114-115`) — disallowed/unallocated.
- `InvalidCodepointContext(IDNAError)` (`core.py:118-119`) — CONTEXTJ/CONTEXTO
  positional failure. Exported from `__init__` but NOT in `__all__`
  (importable as `idna.InvalidCodepointContext`, missing from `__all__` list
  at `__init__.py:25-47` — minor upstream inconsistency, still public).

### 2.5 Label primitives

- `alabel(label: str) -> bytes` (`core.py:524-556`) — single U-label → A-label
  (validate, Punycode-encode, `xn--` prefix). Pure-ASCII labels already valid
  return unchanged. Over-63-octet result → `IDNAError(code="label_too_long")`.
- `ulabel(label: str | bytes | bytearray) -> str` (`core.py:558-608`) —
  inverse. `bytes`/`bytearray` treated as ASCII; non-ASCII bytes →
  `invalid_ascii`. `xn--` labels Punycode-decode and MUST round-trip
  (`_punycode(label) != label_bytes` → `non_canonical_alabel`, `core.py`
  RFC 5891 §5.3 comment — rejects "fake A-labels" e.g. `xn---bbk`).
  Non-ACE labels validated via `check_label` and returned as `str`.
- `uts46_remap(domain, std3_rules=True, transitional=False) -> str`
  (`core.py:637-731`) — UTS #46 §4 mapping (statuses V/M/D/I/X), output NFC.
  `transitional` deprecated/ignored (Unicode 15.1 deviation codepoints always
  kept). Raises `InvalidCodepoint` (`uts46_disallowed`/`uts46_std3`).
- Validators: `valid_label_length` (`core.py:141`), `valid_string_length`
  (`core.py:156`, `len(domain) <= 253 + trailing_dot`), `check_bidi`
  (`core.py:170`, `check_ltr=False`), `check_initial_combiner`
  (`core.py:288`), `check_hyphen_ok` (`core.py:309`),
  `check_nfc` (`core.py:327`), `valid_contextj` (`core.py:339`),
  `valid_contexto` (`core.py:393`), `check_label` (`core.py:442`,
  the orchestrator calling all of the above).

### 2.6 Codec registration (`idna/codec.py` — whole file 225 lines)

- `Codec(codecs.Codec)` (`codec.py:9-36`) — stateless IDNA 2008 codec;
  `encode(data, errors="strict") -> tuple[bytes, int]`,
  `decode(data, errors="strict") -> tuple[str, int]`. Only `"strict"`
  supported; anything else → `IDNAError(code="unsupported_errors")`.
  Empty input short-circuits (`b"", 0` / `"", 0`).
- `IncrementalEncoder(codecs.BufferedIncrementalEncoder)` (`codec.py:39-115`)
  — buffers partial trailing label until separator or `final=True`; all four
  Unicode separators end a label, output always `U+002E`; enforces the
  253/254-octet domain ceiling across the stream (`_emitted`, `_trailing_dot`;
  `codec.py:56-75` state mgmt, `77-115` `_buffer_encode`).
- `IncrementalDecoder(codecs.BufferedIncrementalDecoder)`
  (`codec.py:118-190`) — mirror for decode; 254-octet input ceiling
  (`_consumed`; `codec.py:133-145` state, `147-190` `_buffer_decode`).
- `StreamWriter(Codec, codecs.StreamWriter)` (`codec.py:193-194`),
  `StreamReader(Codec, codecs.StreamReader)` (`codec.py:197-198`).
- `search_function(name)` (`codec.py:201-222`) — returns `CodecInfo` ONLY for
  `"idna2008"` (else `None`); registered at import via
  `codecs.register(search_function)` (`codec.py:225`). So
  `"münchen.de".encode("idna2008")` works through stdlib codec machinery.
  Note the registered name is `idna2008`, NOT `idna` (which is the legacy
  IDNA 2003 stdlib codec — different algorithm).

### 2.7 Compat shims (`idna/compat.py`, 43 lines)

- `ToASCII(label: str) -> bytes` (`compat.py:8-18`) — RFC 3490 shim,
  delegates to `encode`. "New code should call `idna.encode` directly."
- `ToUnicode(label: bytes | bytearray) -> str` (`compat.py:21-31`) —
  delegates to `decode`.
- `nameprep(s: Any) -> None` (`compat.py:34-43`) — stub that ALWAYS raises
  `NotImplementedError("IDNA 2008 does not utilise nameprep protocol")`.

### 2.8 CLI (`idna/cli.py` 132 lines + `idna/__main__.py` 6 lines)

`python -m idna` → `__main__.py:3` imports `main` from `.cli`,
`__main__.py:6` `sys.exit(main())`.
`main(argv=None) -> int` (`cli.py:98-128`): argparse prog
`python -m idna` (`cli.py:29`); `-e/--encode`, `-d/--decode`
(`cli.py:43-58`); `--strict` disables default UTS #46 mapping
(`cli.py:59-63`); `--version` prints `idna {__version__} (Unicode
{unicode_version})` (`cli.py:65-68`); positional `domain` args, else piped
stdin one-per-line (`cli.py:69-73`, `_iter_stdin` at `cli.py:77-83`).
Auto-direction: first input containing an `xn--` label decodes, else encodes
(`_looks_like_alabel`, `cli.py:21-24`; selection `cli.py:125`); exit 0/1
(`_convert_one`, `cli.py:85-95`).

### 2.9 `intranges` helper

`intranges_from_list` (`intranges.py:11-29`) and
`intranges_contain(int_, ranges)` (`intranges.py:40-55`) — range-tuple +
`bisect` membership in O(log #runs). Only `intranges_contain` is public
(exported, used by `core._joining_type` at `core.py:30-34`).

---

## 3. `uts46data` / `idnadata` internals + size

- `uts46data.py`: 17 117 lines, 237 174 bytes. Header
  `uts46data.py:1` ("automatically generated by tools/idna-data"),
  `uts46data.py:8` (UTS46 mapping table docstring),
  `uts46data.py:10` (`__version__ = "18.0.0"`). Exports exactly three data
  objects (verified `dir()`): `uts46_starts` (`array[int]`, 8 481 entries),
  `uts46_statuses`, `uts46_replacements`. Machine tables consumed by
  `uts46_remap` (`core.py:637+`).
- `idnadata.py`: 1 933 lines, 45 763 bytes. `idnadata.py:3`
  (`__version__ = "18.0.0"`). Exports `codepoint_classes`
  (`PVALID` 1 266 range-tuples, `CONTEXTJ` 1, `CONTEXTO` 6),
  `joining_types` (`C` 5, `D` 78, `L` 6, `R` 66, `T` 378),
  `scripts` (`Greek` 37, `Han` 21, `Hebrew` 9, `Hiragana` 7, `Katakana` 15)
  — counts verified at runtime via `dir()`/len.
- Combined table cost ≈ 283 KB source (~237 + ~46 KB), matching the
  "~283 KB Unicode tables" note in `docs/reference/dep-httpx-cluster.md:11`.
  On-device .pyc weight is **unverified** (not measured on Android build).
- Limits: `_max_input_length = 1024` (`core.py:14`, defensive pre-check on
  every entry point), `_max_domain_length = 253` (`core.py:15`, RFC 1035
  octets excl. trailing dot), `_alabel_prefix = b"xn--"` (`core.py:13`).

---

## 4. How httpx / anyio use it

| Caller | Call site (installed source) | What it does |
|---|---|---|
| httpx URL parsing | `httpx/_urlparse.py:25` (`import idna`); `httpx/_urlparse.py:390` (`idna.encode(host.lower()).decode("ascii")`, `except idna.IDNAError` at `:391`) | A-label-encode outbound hostnames |
| httpx URL display | `httpx/_urls.py:6` (`import idna`); `httpx/_urls.py:191` (`host = idna.decode(host)`) | U-label-decode for display |
| anyio sockets | `anyio/_core/_sockets.py:62-68` (`idna2008_resolve`: ASCII fast-path, else `import idna` + `idna.encode(host, uts46=True)`) | IDNA 2008 + UTS46 before DNS; used at `anyio/_core/_sockets.py:656-658` before `getaddrinfo` |
| anyio TLS streams | `anyio/streams/tls.py:147` (`from .._core._sockets import idna2008_resolve`) | Same resolver reused for TLS SNI/hostname path (**unverified** beyond import line — not traced further) |
| flet | No direct `idna` import found (grep over `flet/` hit only httpx/anyio/flet-auth lines) | Reaches idna only via `flet.auth` → httpx → `idna.encode`, and only when OAuth runs |

Dormancy: flet imports httpx lazily inside auth methods only —
`flet/auth/authorization_service.py:119,207,248` (`import httpx` inside
methods; `AsyncClient` at `:133,:221,:256`) and
`flet/auth/providers/github_oauth_provider.py:43`. Corroborates
`docs/reference/dep-httpx-cluster.md:16` ("flet imports httpx only inside
`auth/` methods (lazy)"). No OAuth flow in our app → idna never executes,
but ships inside the APK as a hard dep.

---

## 5. Android notes (no wheel needed)

- Pure-Python + stdlib-only → builds as `py3-none-any`; needs NO
  Android-native wheel. Corroborates `dep-httpx-cluster.md:20`: "pypi.flet.dev
  returns Not Found for all of them — normal: the index hosts only wheels
  needing Android-native builds; pure `py3-none-any` wheels resolve from
  PyPI."
- No `os`/`sys.platform` branches in `core.py`/`codec.py`/`uts46data.py`
  (verified by reading); behaviour is platform-independent. `array` module
  use in `uts46data.py:5` is stdlib on Android CPython — **unverified** on the
  Flet-bundled 3.14 interpreter until the device run, but no reason to doubt.
- Memory: ~283 KB of table source parsed at first `import idna`. First-use
  cost only; never imported on our app's launch path (no OAuth). No action.

---

## 6. Utilization guidance

1. **Do nothing.** idna is a transitive dep; never import it directly.
   Hostname encoding is already handled inside httpx/anyio call sites above.
2. If you ever need to normalize a hostname yourself (logging, allow-list
   comparison, custom `verify=` context), call `idna.encode(host, uts46=True)`
   — the anyio-tested form (`anyio/_core/_sockets.py:68`) — not bare
   `encode()`, so `ß`/`ς`/fullwidth variants map before comparison.
3. For *display* of untrusted hostnames use `idna.decode(host, display=True)`
   (the `display` flag exists for exactly this; `core.py:815-821`).
4. Catch `idna.IDNAError` and read `.code` (stable), never regex the message
   (message wording explicitly unstable; `core.py:77-80`).
5. Never use `compat.ToASCII/ToUnicode` in new code (shims, `compat.py:8-31`);
   never touch `uts46data`/`idnadata` tables directly (generated files).
6. Codec name `"idna2008"` (`codec.py:201-225`) is available if a stdlib-codec
   integration ever needs it; do NOT confuse with `"idna"` (IDNA 2003).

---

## 7. How this dependency makes our app significantly better than Termux's proot-distro

Termux's proot-distro is a shell-script distribution layer: downloads go
through `curl`/`wget` + system resolver, and there is no in-process
Unicode-hostname normalization story — behaviour for non-ASCII registry or
mirror hostnames depends on whatever the device's libc/toolchain does with
them (**unverified** that Termux mishandles any specific IDN today; the point
is there is no pinned, tested normalization point).

Our app gets, via this one transitive dep:

1. **Deterministic IDN handling on every device.** httpx normalizes with
   `idna.encode` (UTS 46 opt-in at the anyio socket layer,
   `anyio/_core/_sockets.py:68`) against pinned Unicode 18.0.0 tables
   (`idnadata.py:3`), independent of OEM libc/ resolver differences that a
   shell-out toolchain inherits.
2. **Display-safe hostname rendering.** `decode(..., display=True)`
   (`core.py:815-821`) gives our UI a WHATWG-aligned way to show
   internationalized hostnames without crashing on fake A-labels — a GUI app
   needs this; a shell script printing curl output does not.
3. **Structured, catchable hostname errors.** `IDNAError.code` (26 stable
   codes, `core.py:39-67`) lets `proot_service` translate a bad registry
   hostname into a friendly UI message (roadmap `friendly_job_error` pattern,
   `docs/roadmap.md:92`); Termux surfaces whatever stderr text curl produced.
4. **Zero-cost inclusion.** ~283 KB tables ship but never parse on our launch
   path (no OAuth → never imported, §4). We carry the capability without
   paying the runtime cost — impossible in a always-shell-out design where
   every feature is a fork+exec.

---

## 8. Verification

- `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md` read first.
- All signatures/line numbers above taken from the installed
  `.venv/Lib/site-packages/idna` (3.20, Unicode 18.0.0) by direct read +
  grep; table counts re-verified at runtime (`python.exe -c`:
  `idna 3.20 | unicode 18.0.0`; `uts46_starts` 8481; class/joining/script
  counts as listed).
- Downstream call sites verified by grep over installed
  `httpx/_urlparse.py`, `httpx/_urls.py`, `anyio/_core/_sockets.py`,
  `anyio/streams/tls.py`, `flet/auth/*`.
- Sizes: `uts46data.py` 237 174 B / `idnadata.py` 45 763 B (`du -sb`);
  whole `idna/` dir 397 141 B incl. `__pycache__`.
- Items marked **unverified** were not observable in installed source.
