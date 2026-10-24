# six — exhaustive API reference (installed 1.17.0)

Verified 2026-10-16 against `.venv/Lib/site-packages/six.py` (1.17.0, single
file, 1003 lines) via `dir()` inventory + source line reads. Context:
`docs/roadmap.md`, `docs/reference/dep-flet-runtime-utils.md`, D-010
(`docs/decisions.md:33-34` — flet stays 1.0.4). Anti-hallucination rule: the
member list below is the live `dir(six)` output (71 public names, no
`_`-privates); line refs point at the installed `six.py`; anything not read is
marked **unverified**.

## 1. Identity

| Fact | Value (verified) |
|---|---|
| Version | **1.17.0** (`six.py:32` `__version__ = "1.17.0"`; `six-1.17.0.dist-info/METADATA` concurs) |
| License | **MIT** (METADATA `License:`) |
| Summary | "Python 2 and 3 compatibility utilities" (METADATA) |
| Requires-Python | `>=2.7, !=3.0.*, !=3.1.*, !=3.2.*` (METADATA) — runs everywhere, including our 3.14 runtime where every `PY2` branch is dead code |
| Dependencies | **None** — stdlib only (`from __future__ import absolute_import (:23)`; `functools, itertools, operator, sys, types (:25-29)`). Nothing depends on six proceeding it; removing it breaks only its importers |
| Size | **34,703 bytes, 1003 lines, one file** (`six.py`) |
| What it is | The Python-2/3 compatibility shim (by Benjamin Peterson): `PY2`/`PY3` flags, `string_types`/`text_type` aliases, `six.moves` virtual namespace, `urllib.parse` backports. Frozen since 1.17.0 — no new features will ever land |

## 2. Why it's here (repath import)

Exactly one flet-path importer: `repath.py:3-4` (verified full read):

```python
import six
from six.moves.urllib import parse as urllib
```

repath uses three six surfaces (verified `grep "six\." repath.py`): `isinstance
(token, six.string_types)` (`:144`, `:204`, `:207`), `six.text_type(val)` /
`six.text_type(value)` (`:174`, `:185`), and `urllib.quote(...)` (`:182`,
`:191`) via the `six.moves.urllib.parse` lazy module. On our Python 3.14 these
are all trivially `str` / stdlib `urllib.parse.quote` — six contributes zero
behavior, only names.

Wider environment: `grep -rln "^import six\|^from six" site-packages/` finds
**ten** importers total, but nine are `dateutil/*` (`parser/isoparser.py`,
`tz/*`, `rrule.py`, `relativedelta.py`, ...). dateutil is NOT in our dependency
closure (it arrived as a transitive env extra; flet never imports it — verified
`grep -rn "import six" flet/` → zero hits). So on OUR path the reverse-dependency
set is exactly `{repath}`.

## 3. Complete public API inventory (all 71 names, live `dir()`)

Grouped by role; line refs are definition sites in `six.py`.

### 3.1 Version flags (`:36-38`)

`PY2 = sys.version_info[0] == 2`, `PY3 = ... == 3`, `PY34 = ... >= (3, 4)`.
On our runtime: `PY2=False, PY3=True, PY34=True` — every `if PY2:` branch
(roughly half the file: the `:49-53` py2 alias block, `:552-581` iterator shims,
`:681-690` byte helpers, `:718-742` reraise) is unreachable dead code we ship
verbatim.

### 3.2 Type aliases (py3 values live at `:41-47`; py2 at `:49-53`)

`string_types` (`str,`), `integer_types` (`int,`), `class_types` (`type,`),
`text_type` (`str`), `binary_type` (`bytes`), `MAXSIZE` (`sys.maxsize`, `:47`
with 32/64-bit fallbacks at `:57-71`). `unichr` (= `chr` on py3), `int2byte`
(`struct.Struct(">B").pack`, `:655`), `byte2int` (`operator.itemgetter(0)`,
`:657`), `indexbytes` (`operator.getitem`, `:658`), `iterbytes` (`iter`, `:659`),
`StringIO`/`BytesIO` (`io.StringIO`/`io.BytesIO`, `:661-662`).

### 3.3 Functions

- Metaclass helpers: `with_metaclass(meta, *bases) (:861)`,
  `add_metaclass(metaclass) (:885)`,
  `python_2_unicode_compatible(klass) (:963)` (noop on py3).
- Ensure family: `ensure_binary(s, encoding='utf-8', errors='strict') (:903)`,
  `ensure_str(...) (:921)`, `ensure_text(...) (:944)`.
- Moves registry: `add_move(move) (:515)`, `remove_move(name) (:520)`.
- Test shims (unittest backports, `:699-711`): `assertCountEqual`,
  `assertRaisesRegex`, `assertRegex`, `assertNotRegex`.
- Bound descriptors / re-exports (verified assignments): `advance_iterator`
  (`= next`, `:550`), `next` (`= advance_iterator`, `:554`), `callable`
  (`:558/:589`), `get_unbound_function` (`:565/:575`), `create_bound_method`
  (`types.MethodType`, `:568`), `create_unbound_method` (`:570/:581`),
  `get_method_function` / `get_method_self` / `get_function_closure` /
  `get_function_code` / `get_function_defaults` / `get_function_globals`
  (`operator.attrgetter(...)`, `:594-599`), `exec_` (from `moves.builtins`,
  `:716`, with py2 fallback `:742`), `reraise(tp, value, tb=None)` (`:718`),
  `raise_from` (**unverified** — in `dir()` but its def line was outside the
  read windows; expected `raise ... from ...` wrapper), `print_` (from
  `moves.builtins`, `:762`), `wraps` (= `functools.wraps`), `b` / `u` (bytes /
  text literal helpers), `indexbytes`, `iteritems` / `iterkeys` / `itervalues`
  / `iterlists`, `viewitems` / `viewkeys` / `viewvalues`, `Iterator`.
- Module re-exports: `functools`, `itertools`, `operator`, `sys`, `types`,
  `absolute_import`, `spec_from_loader`.

### 3.4 `six.moves` + the urllib surface repath actually uses

`MovedModule (:108)` / `MovedAttribute (:144)` descriptors back the lazy
`six.moves` registry (`_LazyDescr`, `_LazyModule`, `_SixMetaPathImporter`
— machinery, **unverified** internals). The urllib entries repath depends on
(`:315-317`, `:340-350`):

```text
MovedModule("urllib_parse", "six.moves.urllib_parse", "urllib.parse")
MovedModule("urllib_error",  "six.moves.urllib_error",  "urllib.error")
MovedModule("urllib",        "six.moves.urllib",        "six.moves.urllib")
Module_six_moves_urllib_parse  +  _urllib_parse_moved_attributes
  (ParseResult, SplitResult, parse_qs, parse_qsl, urldefrag, ... + quote)
```

So `from six.moves.urllib import parse as urllib` resolves to stdlib
`urllib.parse` on py3. Remaining `dir()` names not grouped above:
`Module_six_moves_urllib{,_error,_parse,_request,_response,_robotparser}`
(the sibling lazy urllib submodules) — present, unused by us.

## 4. Removal chain (repath → six; prune both or neither)

Dependency direction is one-way: **repath → six** (`repath-0.9.0.dist-info`
`Requires-Dist: six (>=1.9.0)`; `repath.py:3` hard-imports it at module top, so
`import repath` raises `ModuleNotFoundError: No module named 'six'` the instant
six is missing — no fallback, no try/except). Nothing imports in the reverse
direction (verified: no `import repath` anywhere in `six.py`; flet never imports
six directly — zero hits).

Consequences:

| Action | Effect (verified mechanics) |
|---|---|
| Remove six only | `flet.components.router` + `flet.controls.template_route` break at THEIR import (`repath.py:3`), i.e. all routing dies while repath's 8 KB still ships — pure loss |
| Remove repath only | Legal (nothing else on our path imports repath) but kills routing (§repath study §4); six stays as a 34 KB orphan imported only by dateutil (also unused) |
| Remove both | Coherent: routing gone AND its shim gone. Only valid if the app permanently abandons `Router`/`TemplateRoute` — contradicts the M3 multi-screen plan, so not recommended |
| **Keep both (recommended)** | **~43 KB combined** (8,205 + 34,703 bytes verified) for the entire routing foundation. Zero config, zero native risk, pure-Python |

There is deliberately NO cleanup glob for either: the Sherlock precedent is
"only `oauthlib/**`" (§oauthlib study §4), and these two are the matching
"never prune" pair. If a future audit insists on trimming, the only honest
target is the dead `if PY2:` half of `six.py` — but that means forking/patching
upstream, which the no-patching rule forbids. Ship it whole.

## 5. How six makes our app significantly better than Termux's proot-distro

Short version: it doesn't — and that's the correct finding. six contributes no
user-facing capability; Termux's proot-distro (Bash, no Python compat layer)
needs nothing like it either. Its value is exactly one level removed:

- **It is repath's import.** Without six, `import repath` raises, the Router
  dies, and §4 of the repath study (deep-linkable distro screens, guarded
  install flows) collapses. six's 34 KB is the load-bearing foundation under the
  routing story that differentiates our app from a Termux shell session — it
  enables the enabler.
- **It is frozen and therefore free.** 1.17.0 is the terminal release; the API
  above will never change, so it can never surprise an update bump. No floor to
  track, no drift to matrix-test (contrast the msgpack pin rule in
  `dep-flet-runtime-utils.md`).
- **Honest cost:** ~34 KB of which roughly half is unreachable py2 branches on
  3.14 — the only "waste" in the pair, and unfixable without violating the
  no-patching rule. Accept it.

## 6. Verification refs

- Source: `.venv/Lib/site-packages/six.py` (`__version__` at `:32`; 71-name
  inventory from live `dir(six)`); METADATA `Requires-Python` (no
  `Requires-Dist` — dependency-free).
- repath link: `repath.py:3-4,144,174,182,185,191,204,207`;
  `repath-0.9.0.dist-info/METADATA:20`.
- Reverse deps: `grep -rln "import six\|from six" site-packages/` (repath +
  9× dateutil); `grep -rn "import six" flet/` → zero; eager-import test
  (`import flet` → six absent from `sys.modules`).
- Repo-zero-usage: `grep -rn "import six\|import repath" src/ tests/`
  → no hits.
- **Unverified** (explicitly): `raise_from` def line; `six.moves` importer
  machinery (`_LazyDescr`, `_SixMetaPathImporter` internals); py2-branch
  behavior (unreachable on 3.14, intentionally unread).
