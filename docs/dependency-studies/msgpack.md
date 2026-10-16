# msgpack — exhaustive API reference (dependency study)

**Package:** `msgpack` **1.2.3** · **License:** Apache-2.0 · **Role in this project:** flet's Python↔Dart wire protocol — load-bearing every session (R3 cluster; roadmap D-010: flet stays 1.0.4)
**Verified:** 2026-10-16 against installed source `.venv/Lib/site-packages/msgpack` (1.2.3) and `.venv/Lib/site-packages/flet/messaging/*` (flet 1.0.4).
**Context docs:** `docs/roadmap.md` (§3 R3 row, §4 parking lot msgpack entry) + `docs/reference/dep-flet-runtime-utils.md` (R3 study).

**Anti-hallucination rule (owner-mandated):** every API claim below is verified against installed source (`file:line`) or live introspection output. Anything not verifiable from those two sources is explicitly labeled **unverified**. Nothing is guessed.

---

## 1. Identity

| Fact | Value | Source |
|---|---|---|
| Installed version | `version = (1, 2, 3)`, `__version__ = "1.2.3"` | `msgpack/__init__.py:7-8` |
| License | Apache-2.0 (`License-Expression: Apache-2.0`, `License-File: COPYING`) | `.venv/Lib/site-packages/msgpack-1.2.3.dist-info/METADATA:6,21`; license text dir `msgpack-1.2.3.dist-info/licenses/COPYING` |
| flet's requirement | `Requires-Dist: msgpack>=1.1.0` (lower floor only, no upper cap) | `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:17` |
| Our project's declaration | No direct pin; msgpack arrives transitively via `flet>=1.0.4`; lock resolves 1.2.3 on desktop (sdist hash `sha256:32ed…708db186`) | `pyproject.toml` (`flet>=1.0.4`, no msgpack line); `uv.lock:443-453` |
| Implementation | C extension with pure-Python fallback | `msgpack/__init__.py:11-17` (below) |
| Installed C artifact (Windows host) | `msgpack/_cmsgpack.cp314-win_amd64.pyd` (live introspection: `Packer.__module__ == 'msgpack._cmsgpack'`) | directory listing + live `inspect` |

### 1.1 C extension + pure-Python fallback (exact mechanism)

Quoted verbatim from `msgpack/__init__.py:11-17`:

```python
if os.environ.get("MSGPACK_PUREPYTHON"):
    from .fallback import Packer, Unpacker, unpackb
else:
    try:
        from ._cmsgpack import Packer, Unpacker, unpackb
    except ImportError:
        from .fallback import Packer, Unpacker, unpackb
```

Consequences (all directly entailed by the quoted code, no further source needed):

- Setting the environment variable `MSGPACK_PUREPYTHON` (to any non-empty string — `os.environ.get` truthiness test) forces the pure-Python implementation even when the C extension is present.
- Without the env var, the C extension (`._cmsgpack`) is preferred; any `ImportError` (missing/broken binary) silently falls back to `.fallback`.
- Only `Packer`, `Unpacker`, and `unpackb` are swapped by this branch. `pack`, `packb`, `unpack`, and the `load`/`loads`/`dump`/`dumps` aliases are thin wrappers defined once in `__init__.py` (`__init__.py:20-55`) and delegate to whichever `Packer`/`unpackb` was imported — so **they follow the active implementation automatically**.
- `ExtType`, `Timestamp`, and all of `exceptions` are implementation-independent (imported unconditionally at `__init__.py:4-5`).
- The fallback module additionally contains a PyPy fast path (`fallback.py:7-34`: `BytesBuilder`-backed `BytesIO` when `sys.pypy_version_info` exists) and a `frozendict` compatibility shim (`fallback.py:40-48`: real `builtins.frozendict` only on Python ≥ 3.15, else a placeholder class — meaning `dict_types = (dict, frozendict)` at `fallback.py:709` accepts only real dicts on our Python 3.14).
- Fallback recursion guard: `DEFAULT_RECURSE_LIMIT = 1024` (`fallback.py:66`); exceeding it raises `ValueError("recursion limit exceeded")` (`fallback.py:711-712`). The C extension's exact nesting limit is **unverified** (C source not installed; only the fallback constant is observable).

### 1.2 The Android wheel situation (exact rule)

Quoted from the reference doc (`docs/reference/dep-flet-runtime-utils.md:8`):

> **Android wheel trap**: pypi.flet.dev ships msgpack Android wheels only for **1.1.x** (incl. `msgpack-1.1.2-1-cp314-cp314-android_24_arm64_v8a.whl`), NOT 1.2.3 (desktop-only). flet's spec is `msgpack>=1.1.0` → **never pin ≥1.2.0 anywhere in this project**; keep it floating so the mobile resolver settles on 1.1.2 while desktop keeps 1.2.3.

Quoted from the roadmap parking lot (`docs/roadmap.md:155`):

> - msgpack: RESOLVED — never pin above 1.1.x for Android (Forge index tops at 1.1.2; 1.2.3 is desktop-only). Keep it floating in the lock.

**The resolution rule (binding):**

1. **Never add `msgpack` to our direct dependencies, and never pin `msgpack>=1.2.0` / `==1.2.3` anywhere** — not in `pyproject.toml`, not in CI (`uv pip compile`), not in M0-spike or example projects.
2. Keep it floating/transitive so the desktop resolver takes 1.2.3 while the Android resolver (`--python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/`, cf. roadmap M5) settles on 1.1.2, the newest build with a Forge Android wheel.
3. Rationale: flet's floor is `>=1.1.0`, so 1.1.2 satisfies the flet 1.0.4 contract; pinning 1.2.x would force a source/C build on Android or break the mobile resolve entirely.
4. Corollary for this document: every 1.2.3 API detail below must be read with the question "does 1.1.2 also have this?" — where the answer matters (packb/unpackb keywords our app might use directly), §5 gives the safe subset. Behavior deltas between 1.1.2 and 1.2.3 are **unverified** (1.1.2 source is not installed here).

Note on the reference doc's umbrella note (`dep-flet-runtime-utils.md:18`: "None of these four are on pypi.flet.dev, and none need to be — pure universal wheels ride in as source"): read literally, that sentence conflicts with the msgpack section's statement that Forge ships 1.1.x Android wheels. Both sentences are quoted faithfully here; the operative, binding statement for this project is the pin rule above (also re-affirmed as RESOLVED in the roadmap). Whether current Forge index state matches either sentence is **unverified** from this checkout (no index query was performed).

---

## 2. Complete public API

Live introspection of the installed (C-backed) package reports these public names (`dir(msgpack)`, non-underscore):

```
BufferFull, ExtType, ExtraData, FormatError, OutOfData, PackException,
PackOverflowError, PackValueError, Packer, StackError, Timestamp,
UnpackException, UnpackValueError, Unpacker, dump, dumps, exceptions,
ext, load, loads, os, pack, packb, unpack, unpackb, version
```

(`os` is visible only because `__init__.py` does `import os` at module scope — not API. `exceptions` and `ext` are the submodules. `__version__` exists but starts with underscores so it is absent from the list; it is defined at `__init__.py:8`.)

### 2.1 One-shot functions: `pack` / `packb` / `unpack` / `unpackb` (+ aliases)

Defined in `msgpack/__init__.py:20-55`. Quoted in full (docstrings included — they *are* the upstream API contract):

```python
def pack(o, stream, **kwargs):      # __init__.py:20
    """Pack object `o` and write it to `stream`. See :class:`Packer` for options."""
    packer = Packer(**kwargs)
    stream.write(packer.pack(o))

def packb(o, **kwargs):             # __init__.py:30
    """Pack object `o` and return packed bytes. See :class:`Packer` for options."""
    return Packer(**kwargs).pack(o)

def unpack(stream, **kwargs):       # __init__.py:39
    """Unpack an object from `stream`. Raises `ExtraData` when `stream` contains
    extra bytes. See :class:`Unpacker` for options."""
    data = stream.read()
    return unpackb(data, **kwargs)

load = unpack; loads = unpackb     # __init__.py:51-52 (simplejson/marshal/pickle compat)
dump = pack;   dumps = packb       # __init__.py:54-55
```

Keyword arguments:

- `pack` / `packb` / `dump` / `dumps` accept **exactly the `Packer` constructor keywords** (§2.2) — they construct a throwaway `Packer(**kwargs)` per call. There are no additional per-call keywords.
- `unpack` / `unpackb` / `load` / `loads` accept **exactly the `Unpacker`/`unpackb` keywords** (§2.3).
- One-shot `unpackb` semantics (fallback, `fallback.py:83-105`): builds `Unpacker(None, max_buffer_size=len(packed))`, feeds the whole input, raises `ValueError("Unpack failed: incomplete input")` on truncation (converting `OutOfData`), converts `RecursionError` to `StackError`, and raises `ExtraData(ret, extra)` on trailing bytes. So **one-shot unpack never returns partial data and never silently ignores trailing bytes** — both conditions raise.
- Live C signature of `unpackb` (introspected, C-backed install): `(packed, *, object_hook=None, list_hook=None, use_list=True, raw=False, timestamp=0, strict_map_key=True, unicode_errors=None, object_pairs_hook=None, ext_hook=<class 'msgpack.ext.ExtType'>, max_str_len=-1, max_bin_len=-1, max_array_len=-1, max_map_len=-1, max_ext_len=-1)`. Note the C one-shot form has **no** `file_like`, `read_size`, or `max_buffer_size` keyword (those are streaming-`Unpacker`-only). Every other keyword matches the fallback `Unpacker` defaults, confirming the C and fallback option sets agree on the one-shot path.

### 2.2 `Packer` — every parameter and every method

Constructor parameters (fallback source of truth, `fallback.py:673-694`; the installed C `Packer.__init__` introspects opaquely as `(self, /, *args, **kwargs)`, so C-side acceptance of each keyword is **unverified** individually — but the live C `unpackb` keyword list above and flet's live use of `packb(..., default=...)` confirm the C packer honors at least `default`, and the fallback docstrings below are the documented contract for both):

| Keyword (all keyword-only in fallback) | Default | Meaning (quoted/paraphrased from `fallback.py:630-671` docstring) |
|---|---|---|
| `default` | `None` | Callable converting user types to packable builtins (simplejson-style). Invoked at most once per object (`default_used` guard, `fallback.py:740-743, 811-814`). Non-callable non-None → `TypeError("default must be callable")` (`fallback.py:692-693`). Objects it cannot handle → `TypeError(f"Cannot serialize {obj!r}")` (`fallback.py:819`). |
| `use_single_float` | `False` | Pack `float` as single-precision (`0xCA`) instead of double (`0xCB`) (`fallback.py:764-767`). Precision loss is silent by design. |
| `autoreset` | `True` | Reset the internal buffer after each `pack` and return bytes. With `False`, `pack` returns `None` and you accumulate via `bytes()` / `getbuffer()`, clearing with `reset()` (`fallback.py:821-830`, `942-958`). |
| `use_bin_type` | `True` | Use msgpack-spec-2.0 `bin` family (`0xC4-0xC6`) for `bytes`/`bytearray`/`memoryview`, and enables `str8` (`0xD9`) for `str`. With `False`, bytes degrade to `raw` headers (`fallback.py:930-940`, `918-928`). **Safety guidance: always leave `True`** (see §5.3). |
| `strict_types` | `False` | Exact-type checking: subclasses of serializable types are NOT serialized (forwarded to `default`); `tuple` is NOT packed as list (`fallback.py:704-708`). |
| `datetime` | `False` | Pack tz-aware `datetime` as Timestamp ext (`-1`); tz-naive with this flag → `ValueError` (`fallback.py:806-817`). flet does **not** use this flag — it encodes datetimes via `default=` + `ExtType(1, …)` instead (§3.2). |
| `unicode_errors` | `"strict"` (via `None` → `"strict"`, `fallback.py:691`) | Error handler for `str.encode`. Upstream docstring warns verbatim: **"DO NOT USE THIS!! This option is kept for very specific usage."** (`fallback.py:665-667`). Leave at default. |
| `buf_size` | `None` | "Internal buffer size. This option is used only for C implementation." (`fallback.py:669-670`). Fallback ignores it. |

Type mapping performed by `Packer._pack` (`fallback.py:696-819`, verified branch by branch): `None→0xC0`; `bool→0xC2/0xC3` (checked **before** int — `check(obj, bool)` precedes `check(obj, int)`); int → smallest fitting fixint/uint/int family, out-of-range (>u64/<-i64) → `default` if given else `OverflowError("Integer value out of range")`; `bytes`/`bytearray` → bin header + raw payload; `str` → UTF-8 + raw header (str8 only when `use_bin_type`); `memoryview` → bin header; `float` → `0xCB` (or `0xCA` with `use_single_float`); `ExtType`/`Timestamp` → ext family with fixext shortcuts for 1/2/4/8/16-byte payloads (`fallback.py:777-796`); `list`/`tuple` → array header + items (tuple only when not `strict_types`); `dict` (and `frozendict` on 3.15+) → map; `datetime` with tzinfo → Timestamp only when `datetime=True`.

Methods (all verified at `fallback.py:821-958`):

- `pack(obj)` — pack one object; returns bytes iff `autoreset` (else appends to the buffer). On any exception the buffer is force-reset before re-raise (`fallback.py:822-826`).
- `pack_map_pairs(pairs)` (`fallback.py:832`), `pack_array_header(n)` (`839`), `pack_map_header(n)` (`850`), `pack_ext_type(typecode, data)` (`861`, validates `0 <= typecode <= 127` and bytes payload) — incremental/streaming packing primitives; each returns bytes iff `autoreset`.
- `bytes()` (`942`) — "Return internal buffer contents as bytes object". `reset()` (`946`) — clear buffer ("useful only when autoreset=False"). `getbuffer()` (`953`) — buffer view (PyPy returns a `memoryview` over bytes; CPython the underlying buffer view).
- Negative/oversize header counts raise `ValueError` (`pack_array_header`/`pack_map_header` reject `n < 0` and `n >= 2**32`).

### 2.3 `Unpacker` — every parameter and every method (incl. streaming)

Constructor parameters (fallback, `fallback.py:237-328`; docstring `fallback.py:141-235`):

| Keyword | Default | Meaning |
|---|---|---|
| `file_like` (positional-or-kw) | `None` | Object with `.read(n)`; when given, the unpacker pulls from it and **`.feed()` becomes unusable** (`_feeding=False`, `fallback.py:261-267`). Non-callable `.read` → `TypeError`. |
| `read_size` | `0` → `min(max_buffer_size, 16 KiB)` | Chunk size for `file_like.read()` (`fallback.py:299`). Must be ≤ `max_buffer_size` else `ValueError` (`297-298`). |
| `use_list` | `True` | Arrays → `list`; `False` → `tuple` (`fallback.py:558`, also `153-155`). |
| `raw` | `False` | `True`: msgpack `raw` → `bytes`. `False` (default): decode UTF-8 → `str` (`fallback.py:157-159`, `546-551`). |
| `timestamp` | `0` | How ext `-1` (Timestamp) is returned: `0` → `Timestamp`, `1` → float seconds, `2` → int nanoseconds, `3` → UTC `datetime` (`fallback.py:161-167`, `552-561`). Outside 0–3 → `ValueError` (`304-305`). |
| `strict_map_key` | `True` | Only `str`/`bytes` map keys accepted; else `ValueError("%s is not allowed for map key")` (`fallback.py:544-548`; check is exact-type `type(key) not in (str, bytes)`). **Safety guidance: leave `True`** (§5.3). |
| `object_hook` | `None` | Callable applied to each unpacked map (dict arg). Must be callable; **mutually exclusive with `object_pairs_hook`** (both set → `TypeError`, `fallback.py:324-325`). |
| `object_pairs_hook` | `None` | Callable applied to a generator of key-value pairs per map (simplejson-style). |
| `list_hook` | `None` | Callable applied to each unpacked array (`fallback.py:554-555`). Must be callable if given (`318-319`). |
| `unicode_errors` | `"strict"` (via `None`) | Handler for raw→str decoding; "should be used only when you have msgpack data which contains invalid UTF-8" (`fallback.py:182-185`). |
| `max_buffer_size` | `100 MiB` (`100*1024*1024`) | Cap on pending undecoded data; `0` means `2**31-1` (`283-284`); exceeded on `feed` → `BufferFull` (`332-333`). "You should set this parameter when unpacking data from untrusted source." (`187-191`). |
| `ext_hook` | `ExtType` | Callable `(code, data)` for ext types (default reconstructs `ExtType`). Non-callable → `TypeError` (`326-327`). flet passes `decode_ext_from_msgpack` (§3.2). |
| `max_str_len` / `max_bin_len` / `max_array_len` / `max_map_len` / `max_ext_len` | `-1` → derived from `max_buffer_size` (`max_map_len` → half) | Per-type caps; exceeded → `ValueError(f"{n} exceeds max_*_len(...)")` throughout `_read_header` (`fallback.py:193-210`, `285-294`). Note `max_str_len`, `max_bin_len`, `max_ext_len` are marked "Deprecated, use *max_buffer_size* instead" in the docstring but remain enforced. |

Streaming / iteration methods (verified `fallback.py:329-622`):

- `feed(next_bytes)` (`329`) — append bytes/chunks (`bytes`-like via memoryview; multi-byte itemsize → `ValueError`, `fallback.py:76-80`). Feeding a `file_like`-bound unpacker hits `assert self._feeding` (i.e. `AssertionError` — do not mix modes).
- Iterator protocol: `__iter__` returns self (`579`); `__next__`/`next` unpacks one object, consuming buffer; `OutOfData` → buffered rollback + `StopIteration` (`582-593`). Canonical socket loop is the docstring's own example (`fallback.py:219-228`): `feed(buf)` then `for o in unpacker: process(o)`.
- `unpack()` (`602`) — unpack exactly one object from the buffer, consume it. `skip()` (`595`) — walk past one object without constructing it (`EX_SKIP`). `read_array_header()` (`610`) / `read_map_header()` (`615`) — return the element count without unpacking contents (non-container → `ValueError("Expected array"/"Expected map")`, `_unpack` `505-513`). `read_bytes(n)` (`356`) — read `n` raw bytes, consume. `tell()` (`620`) — stream offset of consumed bytes (`_stream_offset`).
- Key decoder detail: unpacked `str` map keys are `sys.intern`ed (`fallback.py:547-548`) — a small memory optimization with a known unbounded-interning consideration for hostile inputs (mitigate with `max_*_len` caps; our wire peer is our own Dart client, §3.4).

### 2.4 `exceptions` tree (complete, quoted from `exceptions.py`)

Whole module is 48 lines; hierarchy verified verbatim (`exceptions.py:1-48`):

- `UnpackException(Exception)` (`1`) — "Base class for **some** exceptions raised while unpacking. NOTE: unpack may raise exception other than subclass of UnpackException. If you want to catch all error, catch Exception instead." (`2-7`). **This caveat is load-bearing: never `except UnpackException` as a total unpack guard — catch `Exception`** (flet's own servers do exactly this, §3.4).
- `BufferFull(UnpackException)` (`10`), `OutOfData(UnpackException)` (`14`).
- `FormatError(ValueError, UnpackException)` (`18`) — "Invalid msgpack format". Raised e.g. on unknown header byte (`fallback.py:497`: `raise FormatError("Unknown header: 0x%x" % b)`).
- `StackError(ValueError, UnpackException)` (`22`) — "Too nested". Raised from `RecursionError` conversion in `unpackb` (`fallback.py:101-102`), `unpack`/`skip`/`__next__` (`586-587, 598-599, 604-605`).
- `UnpackValueError = ValueError` (`27`, deprecated alias).
- `ExtraData(UnpackValueError)` (`30-42`) — "raised when there is trailing data… only [in] one-shot (not streaming) unpack." Carries `.unpacked` (first object) and `.extra` (trailing bytes); `str()` is `"unpack(b) received extra data."` (`37-42`).
- `PackException = Exception`, `PackValueError = ValueError`, `PackOverflowError = OverflowError` (`46-48`, deprecated aliases — "Use Exception instead to catch all exception during packing", `45`).

### 2.5 `ExtType` (+ `Timestamp`) — complete

`ExtType` (`ext.py:8-18`): `namedtuple("ExtType", "code data")` with validating `__new__` — `code` must be `int` (`TypeError` otherwise), `data` must be `bytes`, and `0 <= code <= 127` (`ValueError` otherwise). Note the msgpack timestamp ext (`-1`) is *outside* this range by design — `Timestamp` is the separate type for code `-1` (packer special-cases it at `fallback.py:769-771`).

`Timestamp` (`ext.py:21-184`): immutable-by-convention (`__slots__ = ["seconds", "nanoseconds"]`, `33`; "Do not override seconds and nanoseconds", `28`), `__eq__`/`__ne__`/`__hash__` over the pair (`59-70`), `__repr__` as `Timestamp(seconds=…, nanoseconds=…)` (`55-57`).

| Method | Signature / behavior | Source |
|---|---|---|
| `__init__` | `(seconds: int, nanoseconds: int = 0)`; nanoseconds must satisfy `0 <= ns < 10**9` (`ValueError` otherwise); both must be `int` (`TypeError`). Negative (pre-epoch) times = negative seconds + positive ns. | `ext.py:34-53` |
| `from_bytes(b)` / `to_bytes()` | 4-byte → timestamp32, 8-byte → timestamp64, 12-byte → timestamp96; anything else → `ValueError`. Pure-Python (un)packing path ("When built with Cython, msgpack uses C methods…", `24-26` — the Cython path itself is **unverified**). | `ext.py:72-118` |
| `from_unix(x)` / `to_unix()` | float POSIX seconds ↔ Timestamp. | `ext.py:120-137` |
| `from_unix_nano(ns)` / `to_unix_nano()` | int POSIX nanoseconds ↔ Timestamp (`divmod`). | `ext.py:139-154` |
| `to_datetime()` / `from_datetime(dt)` | UTC `datetime` ↔ Timestamp via `_EPOCH` (`ext.py:5`); naive datetimes treated as local time (matches `datetime.timestamp()`); microsecond precision only (ns = µs×1000). | `ext.py:156-184` |

### 2.6 `version` / `__version__`

`version = (1, 2, 3)` (tuple), `__version__ = "1.2.3"` (string) — `__init__.py:7-8`. Live check confirms `msgpack.version == (1, 2, 3)`.

### 2.7 Fallback-module behavior + limitations (summary)

- Activation: `MSGPACK_PUREPYTHON` set, or `_cmsgpack` import failure (`__init__.py:11-17`).
- Faithful wire compatibility (same headers, same ext framing, same `Timestamp` byte layouts) but pure-Python speed; recursion is real Python recursion subject to `DEFAULT_RECURSE_LIMIT = 1024` *and* the interpreter stack (`RecursionError → StackError` conversions throughout).
- `sys.intern` on str map keys (`fallback.py:547-548`); unbounded distinct keys from untrusted input accumulate interned strings — cap with `max_map_len`/`max_buffer_size`.
- Whether the C extension interns keys, enforces identical limits, or matches each fallback error message is **unverified** (no C source in the wheel; only `unpackb`'s keyword list was introspected).

---

## 3. How flet uses it

flet 1.0.4 uses msgpack as its **sole Python↔Dart serialization transport**. Four modules touch it (verified by grep over `.venv/Lib/site-packages/flet`): `messaging/protocol.py`, `messaging/flet_dart_bridge_server.py` (embedded/Android transport), `messaging/flet_socket_server.py` (socket transport), `messaging/pyodide_connection.py` (web transport). Every session loads it at session start, not at cold import (roadmap §3 R1/R3 rows).

### 3.1 The exact protocol calls (quoted)

**Send path** — identical in all three servers (dart_bridge `flet_dart_bridge_server.py:229-233`; socket `flet_socket_server.py:438-442`; pyodide `pyodide_connection.py:206-210`):

```python
body = msgpack.packb(
    [message.action, message.body],
    default=configure_encode_object_for_msgpack(BaseControl),
)
```

with the encoder documented at `protocol.py:26-48`, whose operative line is quoted at `protocol.py:30`:

```python
The returned function is passed to `msgpack.packb(..., default=...)` and handles
protocol-specific serialization rules for dataclasses, enums, date/time objects,
:class:`~flet.Duration`, and extension values exchanged with Dart.
```

**Receive path** — dart_bridge (`flet_dart_bridge_server.py:129-131`), socket (`flet_socket_server.py:287`), pyodide (`pyodide_connection.py:92`):

```python
msg = msgpack.unpackb(packet[1:], ext_hook=decode_ext_from_msgpack)
```

### 3.2 Message shapes — what actually crosses the wire

- **Frame:** every protocol message serializes as a **two-item array `[action_code, body]`** (`Message` dataclass docstring, `protocol.py:278-285`: "Serialized as a two-item sequence: `[action_code, body]`"), wrapped with a **leading `0x00` type byte**: `packet = b"\x00" + body` (dart_bridge `send_message`, `flet_dart_bridge_server.py:229-236`, whose docstring states the wire format explicitly: `"Wire format: [0x00][msgpack body] — no length prefix (the bridge preserves message boundaries)."`). The socket transport additionally length-prefixes with 4 little-endian bytes (`framed = len(packet).to_bytes(4, "little", signed=False) + packet`).
- **Actions** (`MessageAction`, `protocol.py:231-275`; "Integer values must stay in sync with the Dart enum of the same name (`protocol/message.dart`) because protocol frames are encoded as `[action_code, body]`", `protocol.py:235-237`): `1 REGISTER_CLIENT` (handshake + page snapshot), `2 PATCH_CONTROL` (server→client control-tree patch `{id, patch}`), `3 CONTROL_EVENT` (client→server `{target, name, data}`), `4 UPDATE_CONTROL_PROPS` (client→server `{id, props}`), `5 INVOKE_METHOD` (bidirectional `{control_id, call_id, name, args}` → `{…, result, error}`), `6 SESSION_CRASHED` (`{message}`), `7 PYTHON_OUTPUT` (`{text, is_stderr}`, Pyodide/embedded-stdout only).
- **Control trees** cross as sparse dataclass→dict conversions (`encode_object_for_msgpack`, `protocol.py:50-215`): only non-default values emitted; `on_*` handlers become booleans (`True` when set); list/dict/dataclass snapshots cached in `__prev_*` for patch diffing; callables rejected (`raise RuntimeError(f"Cannot serialize method: {obj}")`, `protocol.py:211-212`).
- **Events** cross back as `ControlEventBody{target: int, name: str, data: Any}` (`protocol.py:410-429`) — name without the `on_` prefix.
- **Flet's ext codes** (`decode_ext_from_msgpack`, `protocol.py:218-228`): `1` → ISO-8601 datetime string; `2` → `HH:MM` time string; `3` → `Duration` microseconds (int); `4` → UTF-8 string; anything else → passthrough `ExtType(code, data)`. Encoder side (`protocol.py:190-210`): `datetime/date → ExtType(1, isoformat)`, `time → ExtType(2, …)`, `Duration → ExtType(3, microseconds)`. Note flet does **not** use msgpack's native Timestamp ext (`-1`) or `Packer(datetime=True)` — datetimes ride as ext 1 strings.
- **Data-channel framing is NOT msgpack:** `0x01` frames are `[0x01][channel_id:u32 LE][raw bytes]` — "raw DataChannel frame" / "Single-copy assembly" comments in `flet_socket_server.py` (`257-258`, `send_data_channel_frame`). On embedded/Android each DataChannel rides its own dedicated native port (`flet_dart_bridge_server.py: data_channel_for`). Only the `0x00` control channel is msgpack.

### 3.3 Implications — what breaks when serialization fails

- **Pack failure (Python→Dart):** `packb` raising (e.g. `TypeError: Cannot serialize …` for an unencodable control value, `OverflowError` for out-of-range int) aborts that `send_message`; the Dart side never receives the patch/event-result, so the UI silently stops reflecting state (no client update, no crash on the client). Because the encoder snapshots `__prev_*` *before* the pack completes, a failed pack can additionally leave differ snapshots inconsistent with what the client holds — worst case a silent protocol mismatch of exactly the kind the roadmap flags for unversioned wire contracts (roadmap M1 R1 note).
- **Unpack failure (Dart→Python):** the dart_bridge receive loop catches **broad `Exception`** around `unpackb` + dispatch and logs `"Error dispatching dart_bridge frame"` (`flet_dart_bridge_server.py:129-137`) — a malformed client frame is dropped, the session survives. The socket server drops malformed data-channel frames (`len(packet) < 5` → debug log, `continue`) and aborts the receive loop on truncated reads (`asyncio.IncompleteReadError` → break). Unknown leading bytes (`not 0x00/0x01`) are dropped with a debug log in all transports. Net: **corrupt inbound frames degrade to dropped messages, never session crashes** — but a dropped `CONTROL_EVENT` means a lost tap/keystroke with no user-visible error.
- **Version-skew hazard:** action codes and ext codes must match the Dart enum/decoder compiled into the client at build time (`protocol.py:235-237`). The wire has no version negotiation visible in these modules (**unverified** whether any handshake negotiates format — `RegisterClientRequestBody{session_id, page_name, page}` at `protocol.py:298-322` carries session/page state, not a protocol version). Practical consequence for us: flet Python package and the built client must stay lock-stepped (roadmap §3 R1 row already mandates this for flet-cli/web/desktop).

---

## 4. How msgpack makes our app significantly better than Termux's proot-distro

(Terms: "Termux's proot-distro" = the upstream console/Termux distribution model — a shell in a terminal emulator, no app UI layer, no structured client↔backend protocol. This section is the owner-requested comparison; the technical claims in it rest on §§1–3 above.)

1. **The app itself is rendered through the msgpack wire.** Termux's proot-distro shows a raw PTY: every pixel is terminal-cell text. Our app's *entire UI* — distro list, install progress, session screen, settings — is a Flet control tree diffed in Python, packed with `packb([action, body], default=…)` (§3.1), and applied as `PATCH_CONTROL` operations on the Dart client (§3.2). Concretely: installing Ubuntu shows a live stage-level progress screen, not a scrolling `apt` log; container start/stop/remove are buttons bound to `CONTROL_EVENT`s, not typed commands. That UI layer exists only because the msgpack transport carries structured control state at ~binary-compact sizes on every frame. If the wire were JSON-over-websocket instead, the same architecture would work but with larger frames and stringly-typed datetimes; msgpack's binary arrays + ext codes are what make per-keystroke terminal bridging (§3.2, `0x01` data frames alongside the msgpack control channel) affordable on a phone.
2. **Efficient binary records for container metadata and session state — available to us for free.** The same `packb`/`unpackb` primitives that carry control trees serialize plain Python dicts/lists/bytes with no schema code: container manifests (`containers/<name>/manifest.json` data), install-stage records, `ProotSession` scrollback checkpoints, and structured-mode cell outputs (`{"type": stream|execute_result|display_data|error, …}`, roadmap §1c) can all be persisted or passed between services as compact msgpack blobs instead of JSON text — smaller on disk, faster to parse, bytes-safe without base64. flet already proves the pattern in-process (sparse dict packing, §3.2); reusing it for our own records is zero new dependencies (see §5 for the gated recommendations).
3. **The Android 1.1.x wheel rule is what keeps (1) and (2) shippable.** The whole rendering story collapses if the APK cannot import msgpack: no wire protocol, no control tree, no app. The Forge index carries 1.1.x Android wheels (`msgpack-1.1.2-1-cp314-cp314-android_24_arm64_v8a.whl` quoted in §1.2) while 1.2.3 is desktop-only — so the binding rule is: **keep msgpack floating, never pin ≥1.2.0** (§1.2). Follow it and the exact same wire code that runs on the dev desktop packs inside the APK; break it and the M5 Android compile-proof step (`uv pip compile --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/`, roadmap M5) fails at resolve time. Termux's stack has no equivalent single point of leverage — and no equivalent single point of failure, which is why this document treats the pin rule as release-blocking.
4. **Failure behavior favors an app over a shell.** §3.3 shows corrupt frames degrade to dropped messages with the session surviving — in a shell that would be a garbled screen; in our app it is at worst a missed progress tick, and `SESSION_CRASHED` / probe-gating (`core/proot_probe.py`, roadmap M3) give us structured places to surface real errors instead of dumping tracebacks into a terminal.

Net: Termux gives the user a window into a guest; msgpack's wire protocol lets us build a product *around* the guest — managed lifecycle UI, structured output modes, and binary-efficient local state — with the 1.1.x pin rule as the one hard constraint that keeps it deployable.

---

## 5. Fullest utilization — should OUR app use msgpack directly?

**Short answer: yes, but only for local plain-data records and in-process/service IPC — never on the flet wire path, never as a cross-version store without a version byte, and always inside the 1.1.x-compatible safe subset.** Detail by milestone:

### 5.1 M3 (app scaffold + distro manager) — recommended uses

- **Persisting container metadata snapshots** (certified-distro catalog entries, install-stage records, `manifest.json` projections, storage-size reports): `msgpack.packb(record, use_bin_type=True)` to app-private storage, `unpackb` on read. Smaller and faster than the JSON files upstream uses, bytes-safe for hashes/checksums without base64. Wrap behind `services/proot_service.py` (the sole-importer facade — msgpack import lives there or in a new `core/codec.py`, never scattered across screens).
- **Crash-safe progress checkpoints**: stage-level install state (`{ref, stage, bytes_done, ts}`) packed per stage completion; on restart, unpack and resume/skip. One-shot `unpackb`'s `ExtraData`-on-trailing-bytes behavior (§2.1) is an integrity feature here — a torn write fails loudly instead of loading half a record (pair with atomic file replace regardless).
- **Do NOT use for anything the user might copy between app versions** without a leading format-version byte you check before `unpackb` (msgpack has no schema evolution; a field rename silently yields wrong-shaped dicts).

### 5.2 M4 (terminal integration) — recommended uses

- **Structured-mode cell outputs** (`{"type": …, …}` dicts, roadmap §1c/§M4): pack output batches for the append-only output list persistence and for scrollback-replay across screen switches. Compact binary appends beat JSON-lines on long sessions.
- **Session handoff between service and UI** (stdin-hook answers, resize records, exit statuses): small dicts over the existing in-process path — msgpack keeps bytes payloads (terminal I/O chunks) exact, where JSON would force base64 or lossy decode.
- **Do NOT touch the `0x01` data-channel path or the flet `0x00` protocol path** — those belong to flet's transport (no-patching rule, roadmap §0). Our bytes ride *inside* event data / our own channels, never as forged frames.

### 5.3 Safety rules for any direct use (binding)

1. **The 1.1.x pin rule applies to our usage too** (§1.2): use only API surface stable across 1.1.x→1.2.x. Safe subset (all verified in this 1.2.3 checkout; 1.1.x parity **unverified** but these are long-stable core API): `packb`/`unpackb` with `default`, `use_bin_type`, `raw`, `strict_map_key`, `object_hook`, `ext_hook`, `use_list`; `ExtType`; the `exceptions` names. Avoid `list_hook`, `timestamp=1/2/3` decoding modes, and `datetime=True` packing in app code until 1.1.x parity is confirmed against 1.1.2 source.
2. **`use_bin_type=True` always** (it is the default; never set `False`): with `False`, `bytes` silently degrade to `raw/str8` and a `raw=False` unpacker returns them as `str` — binary hashes, terminal bytes, and checksums corrupt across the round trip with no error. This is the single most dangerous knob for our byte-carrying uses.
3. **`strict_map_key=True` always** (the default; never disable): our records are str-keyed dicts; disabling it admits int/tuple-keyed maps that JSON-minded code mishandles and that diverge from flet's own wire expectations.
4. **Unpack defensively**: catch `Exception` (not just `UnpackException` — see the `exceptions.py:2-7` caveat quoted in §2.4); set `max_buffer_size` when unpacking anything that touched disk/network; treat `ExtraData` as corruption, not as "two records" (use the streaming `Unpacker.feed`/iterate form, §2.3, for multi-record streams).
5. **No wire-protocol coupling**: never import flet's `encode_object_for_msgpack` / `decode_ext_from_msgpack` / ext codes 1–4 for our own records — those are flet's unversioned internal contract (roadmap M1 R1 note) and may change under us. Our records use our own `default=`/`ext_hook=` functions and our own ext code registry (avoid codes 1–4 to prevent confusion with flet's).

### 5.4 Explicit non-uses

- No msgpack in the M0 spike (plain subprocess + text there; keep the harness dependency-free).
- No msgpack for IPC *between processes* (we have none — everything is in-process/services; if a Dart-side spawn ever lands via flet-terminal, its bridge is Dart-owned, not ours to reframe).
- No `MSGPACK_PUREPYTHON` manipulation in app code (test-only lever; the C extension ships in both desktop and Forge wheels).

---

## 6. Android notes

- **C extension vs fallback on-device:** the Forge 1.1.x Android wheel (`…-android_24_arm64_v8a.whl`) ships the compiled extension, so the APK runs the C path — full session-rate packing (every control patch, every keystroke event) at native speed. If the C library ever fails to load on-device, `__init__.py:11-17` falls back to pure Python silently: the app still works but per-frame `packb`/`unpackb` cost rises substantially (pure-Python `_pack`/`_unpack` recursion, `BytesIO` buffering). There is no log line on fallback — a sluggish session with no other explanation should prompt checking `msgpack.Packer.__module__` on-device (expect `msgpack._cmsgpack`). Forcing the fallback for diagnostics is `MSGPACK_PUREPYTHON=1` (dev/test only, §5.4).
- **Wheel tag rules:** Android wheels are tagged `android_24_arm64_v8a` (API 24 floor, arm64) for CPython 3.14 (`cp314-cp314`). This composes with the M5 CI proof step (`uv pip compile --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/`, roadmap M5): that step is the executable form of the §1.2 pin rule — if anyone pins `≥1.2.0`, the Android resolve fails there instead of at APK build time. x86_64 emulator coverage follows the M2 ABI decision (roadmap §4 parking lot); msgpack-side, whatever the wheel set covers is what resolves — no app-side action either way.
- **Size/perf posture:** msgpack is a small native module (desktop win_amd64 wheel ≈ 92 KB per `uv.lock:448` entry `…-macosx_10_15_x86_64.whl` hash line family — exact Android wheel size **unverified**); no `[tool.flet.cleanup]` glob should touch it (contrast `oauthlib/**`, which is prunable precisely because msgpack is not). Runtime memory: bound unpacker growth with `max_buffer_size` on any stream we feed from disk/network (§2.3).

---

## 7. Verification

| # | Claim | Evidence |
|---|---|---|
| 1 | Version 1.2.3, Apache-2.0 | `msgpack/__init__.py:7-8`; `msgpack-1.2.3.dist-info/METADATA:6,21` |
| 2 | Fallback selection logic | `msgpack/__init__.py:11-17` (quoted §1.1) |
| 3 | Android 1.1.x-only Forge wheels + filename + never-pin rule | `docs/reference/dep-flet-runtime-utils.md:8` (quoted §1.2); re-affirmed `docs/roadmap.md:155` |
| 4 | flet requires `msgpack>=1.1.0` | `flet-1.0.4.dist-info/METADATA:17` |
| 5 | Public export list | live `dir(msgpack)` introspection (§2 header) |
| 6 | `pack/packb/unpack/unpack` + 4 aliases | `msgpack/__init__.py:20-55` (quoted §2.1) |
| 7 | C `unpackb` keyword set | live `inspect.signature` (§2.1) |
| 8 | `Packer` params/defaults/methods | `msgpack/fallback.py:624-694` (docstring), `696-958` (impl) |
| 9 | `Unpacker` params/defaults/methods/streaming | `msgpack/fallback.py:141-328` (docstring+init), `329-622` (methods) |
| 10 | Exceptions tree + catch-all caveat | `msgpack/exceptions.py:1-48` (quoted §2.4) |
| 11 | `ExtType` validation, `Timestamp` full API | `msgpack/ext.py:8-18`, `21-184` |
| 12 | flet send/receive calls | `flet/messaging/flet_dart_bridge_server.py:129-131,229-233`; `flet/messaging/flet_socket_server.py:287,438-442`; `flet/messaging/pyodide_connection.py:92,206-210`; `flet/messaging/protocol.py:30` |
| 13 | Frame shape `[action, body]`, `0x00` byte, no-length-prefix (bridge) / LE-length (socket) | `flet/messaging/protocol.py:278-285`; `flet_dart_bridge_server.py:send_message` docstring; socket `framed = …` line |
| 14 | Action codes 1–7 + Dart-sync requirement | `flet/messaging/protocol.py:231-275` |
| 15 | Ext codes 1–4 + passthrough | `flet/messaging/protocol.py:190-210,218-228` |
| 16 | Data-channel `0x01` raw-byte framing (not msgpack) | `flet/messaging/flet_socket_server.py:257-258`, `send_data_channel_frame`; `flet_dart_bridge_server.py:data_channel_for` |
| 17 | Drop-not-crash error handling | `flet_dart_bridge_server.py:129-137` (`"Error dispatching dart_bridge frame"`); socket truncated-read/malformed-frame paths |
| 18 | Roadmap status (flet 1.0.4 pin, M3/M4/M5 hooks, no-patch rule) | `docs/roadmap.md:§0 constraints, §2 M3/M4/M5, §3 R3 row, §4 parking lot` |

**Deliberately unverified (labeled inline, not investigated):** C-extension internals beyond the introspected `unpackb` signature (nesting limits, key interning, exact error parity with fallback); 1.1.2↔1.2.3 behavior deltas; current live Forge index state; whether the wire handshake negotiates any format version; Android wheel byte size.
