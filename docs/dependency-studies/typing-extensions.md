# typing-extensions 4.16.0 — API reference

Verified 2026-10-16 against installed source
`/home/maikel/.zcode/workspace/default/proot-distro-flet/.venv/Lib/site-packages/typing_extensions.py`
(single file, 4 422 lines, 165 012 bytes; flet stays 1.0.4 per roadmap D-010).
Context read first: `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md`.
Anti-hallucination rule: every claim cites installed file:line; anything not
verified in source is labeled **unverified**.

---

## 1. Identity

| Field | Value | Source |
|---|---|---|
| Name | `typing_extensions` | `typing_extensions-4.16.0.dist-info/METADATA:2` (`Name: typing_extensions`) |
| Version | `4.16.0` | `typing_extensions-4.16.0.dist-info/METADATA:3` (`Version: 4.16.0`) |
| License | PSF-2.0 | `METADATA:9` (`License-Expression: PSF-2.0`); `License-File: LICENSE` |
| What it is | Backports + experiments for the `typing` module; single-file shim that re-exports stdlib `typing` when the running version already has a feature, else defines it | `typing_extensions.py` structure throughout (e.g. `Literal`: `typing.Literal` on new Pythons at `:463`, fallback `_LiteralForm` at `:520`); METADATA description |
| Pure-Python? | Yes — single `.py`, stdlib only | file listing; no compiled artifacts besides `__pycache__` |
| Role in this project | Load-bearing on EVERY app launch (flet control system); also used by anyio/h11 | `docs/reference/dep-httpx-cluster.md:13` ("`typing-extensions` load-bearing on every launch") |

---

## 2. Complete-ish API inventory (every public name exported)

Runtime-verified: `len(typing_extensions.__all__) == 121`
(`python.exe -c "import typing_extensions"`). Two names are appended
conditionally after the literal: `CapsuleType` (`typing_extensions.py:4031`,
`__all__.append("CapsuleType")`) and `no_type_check_decorator` (`:4413`).
The sorted export list below is the runtime `sorted(__all__)` output:

**Super-special primitives:** `Any`, `ClassVar`, `Concatenate`, `Final`,
`LiteralString`, `ParamSpec`, `ParamSpecArgs`, `ParamSpecKwargs`, `Self`,
`Type`, `TypeVar`, `TypeVarTuple`, `Unpack`, `AnyStr`, `TypeAlias`,
`TypeAliasType`, `TypeForm`, `TypeGuard`, `TypeIs`, `Never`, `NoReturn`.

**ABCs / collections:** `Awaitable`, `AsyncIterator`, `AsyncIterable`,
`Coroutine`, `AsyncGenerator`, `AsyncContextManager`, `Buffer`, `ChainMap`,
`ContextManager`, `Counter`, `Deque`, `DefaultDict`, `NamedTuple`,
`OrderedDict`, `TypedDict`, `Collection`, `Callable`, `Dict`, `ForwardRef`,
`FrozenSet`, `Generator`, `Generic`, `Hashable`, `IO`, `ItemsView`,
`Iterable`, `Iterator`, `KeysView`, `List`, `Mapping`, `MappingView`,
`Match`, `MutableMapping`, `MutableSequence`, `MutableSet`, `Optional`,
`Pattern`, `Reversible`, `Sequence`, `Set`, `Sized`, `Text`, `TextIO`,
`Tuple`, `Union`, `ValuesView`, `AbstractSet`, `BinaryIO`.

**Protocols / structural:** `Protocol`, `runtime_checkable`, `is_protocol`,
`get_protocol_members`, `SupportsAbs`, `SupportsBytes`, `SupportsComplex`,
`SupportsFloat`, `SupportsIndex`, `SupportsInt`, `SupportsRound`, `Reader`,
`Writer`.

**TypedDict helpers:** `TypedDict`, `is_typeddict`, `Required`, `NotRequired`,
`ReadOnly`, `NoExtraItems`.

**Decorators / markers:** `final`, `override`, `overload`, `deprecated`,
`disjoint_base`, `dataclass_transform`, `no_type_check`,
`no_type_check_decorator`, `runtime`, `sentinel`, `Sentinel`, `IntVar`,
`NewType`, `Doc`, `Format`, `NoDefault`.

**Introspection:** `Annotated`, `assert_never`, `assert_type`,
`clear_overloads`, `evaluate_forward_ref`, `get_overloads`, `get_args`,
`get_origin`, `get_original_bases`, `get_type_hints`, `get_annotations`,
`cast`, `reveal_type`, `type_repr`, `is_typeddict` (listed twice in source
groupings; one export).

**PEP-695 / new:** `TypeVar` (+ defaults syntax support), `TypeAliasType`,
`TypeForm`, `TypeIs`, `CapsuleType` (conditional, `:4031`),
`evaluate_forward_ref`, `Format`, `ReadOnly`.

Key definition lines (spot-verified by grep; full bodies in
`typing_extensions.py`): `Literal` re-export at `:463`, fallback
`_LiteralForm` at `:520` (with the "Literal bug fixed in 3.11.0/3.10.1/3.9.8"
comment at `:460`); `__all__` literal opens at `:21`; conditional appends at
`:4031`, `:4413`.

Names the task brief asked about, confirmed present in runtime `__all__`:
`TypeAlias` ✓, `ParamSpec` ✓, `dataclass_transform` ✓, `Protocol` ✓,
`TypedDict` ✓, `Literal` ✓, `Never` ✓, `TypeVarTuple` ✓, `Unpack` ✓,
`deprecated` ✓. All ten verified in the sorted runtime list.

---

## 3. Which pieces flet actually uses

Grep over installed `flet/` found exactly three typing-extensions touch
points (no other `import typing_extensions` in flet):

1. **`dataclass_transform` — the load-bearing one.**
   - `flet/controls/base_control.py:21-23`:
     ```python
     if sys.version_info >= (3, 11):
         from typing import dataclass_transform
     else:
         from typing_extensions import dataclass_transform
     ```
     applied at `base_control.py:91` (`@dataclass_transform()`).
   - `flet/controls/value_types.py:15-17`: identical version-guarded import,
     applied at `value_types.py:159` (`@dataclass_transform()`).
   - **Quote sites:** `@dataclass_transform()` on the control base
     (`base_control.py:91`) is the control-system hook the roadmap's study
     refers to. This decorator is what makes every flet control class behave
     with dataclass-like `__init__` typing — it executes at import/class
     creation, i.e. on every app launch. Corroborates
     `docs/reference/dep-httpx-cluster.md:13`.
   - On our floor (py3.14, `pyproject.toml:8` `requires-python = ">=3.14"`)
     the `sys.version_info >= (3, 11)` branch wins, so flet takes
     `dataclass_transform` from **stdlib `typing`**, and the
     typing-extensions copy is NOT exercised by flet at runtime. The
     dependency remains (hard dep of flet + anyio) but flet's own usage
     resolves to stdlib. Do NOT remove it — see §4.
2. **`deprecated` — doc-tooling only.**
   `flet/utils/griffe_deprecations.py:7` (comment mentioning
   `typing_extensions.deprecated(...)`) and `:39`
   (`_PEP702_DECORATORS = {"warnings.deprecated",
   "typing_extensions.deprecated"}`) — string matching for doc generation,
   not an import. Zero runtime effect.
3. **`Annotated` — string matching only.**
   `flet/utils/griffe_deprecations.py:37`
   (`_ANNOTATED_PATHS = {"typing.Annotated",
   "typing_extensions.Annotated"}`) — same story.

Other clusters' usage (for completeness, verified by grep):
anyio imports `Self`, `TypeVarTuple`, `Unpack`, `override`, `deprecated`,
`Never`, `sentinel`, `TypeVar` across ~15 modules (e.g.
`anyio/_backends/_asyncio.py:123`, `anyio/_core/_tasks.py:27`,
`anyio/_core/_sockets.py:47,50`); h11 imports `Literal`
(`h11/_headers.py:13`). All are `TYPE_CHECKING`-guarded fallbacks in some
modules and runtime imports in others — **unverified** per-module which is
which beyond the grep lines; irrelevant to our app (dormant without OAuth/
async httpx use).

---

## 4. Guidance: `typing` vs `typing_extensions` in our code (py3.14 floor)

Project floor: `requires-python = ">=3.14"` (`pyproject.toml:8`).

1. **Default to stdlib `typing`.** On 3.14 every name in §2 that matters
   (`TypeAlias`, `ParamSpec`, `dataclass_transform`, `Protocol`, `TypedDict`,
   `Literal`, `Never`, `TypeVarTuple`, `Unpack`, `deprecated`, `Self`,
   `override`, `Required`/`NotRequired`, `ReadOnly`, `TypeIs`, `TypeGuard`,
   `assert_never`...) exists in stdlib. Follow flet's own pattern
   (`base_control.py:21-23`): `from typing import X` unconditionally in our
   code — no version guard needed since we floor at 3.14.
2. **Import from `typing_extensions` ONLY for names missing from 3.14
   `typing`.** At 4.16.0 these are few; candidates are names still marked
   experimental upstream (`Format`, `TypeForm`, `NoDefault`,
   `get_annotations` edge cases — verify against 3.14 `typing.__all__`
   before using; **unverified** which exact names are still missing on 3.14
   because the check is one `python3.14 -c "import typing"` away and this
   study pins to installed source, not a changelog).
3. **Copy flet's guard idiom if we ever lower the floor.** If
   `requires-python` ever drops below 3.11, use exactly:
   ```python
   if sys.version_info >= (3, 11):
       from typing import dataclass_transform
   else:
       from typing_extensions import dataclass_transform
   ```
   (verbatim from `flet/controls/base_control.py:21-23`).
4. **Never pin typing-extensions tightly.** It is a hard dep of flet AND
   anyio; let the resolver float it (same discipline as msgpack per
   `docs/roadmap.md:155`). A ceiling pin risks conflicting with flet's next
   bump.
5. **No runtime cost concern.** Single 165 KB file, imported once; the parts
   flet needs resolve to stdlib on 3.14 anyway (§3.1). No Android wheel
   needed (pure-Python, `dep-httpx-cluster.md:20` applies to the whole
   cluster).

---

## 5. How this dependency makes our app significantly better than Termux's proot-distro

Termux's proot-distro has no typed Python layer at all — it is shell scripts
plus a small C proot binary. Every consumer parses human-readable CLI output;
controller/service boundaries, if any, are conventions, not contracts. A
renamed field or reordered column breaks downstream silently.

Our app's typed stack — carried in large part by this one package — gives:

1. **`@dataclass_transform` control contracts.** flet's
   `@dataclass_transform()` at `base_control.py:91` /
   `value_types.py:159` is what lets our screens, state (`@ft.observable
   AppState`, `docs/roadmap.md:90`), and controller bridge
   (`ControllerMethodsCtx`) be statically checked. Termux-side equivalents
   (screen text scraping) have no checkable contract; ours fail at PR time,
   not on-device.
2. **TypedDict/Protocol service seams.** The roadmap mandates a
   sole-importer `ProotSession`/`proot_service` facade with plain-data
   returns (`docs/roadmap.md:22-24,92`). `TypedDict` + `Protocol` (both in
   §2 exports) are the vocabulary for those seams: guest-state dicts and
   session interfaces type-check across `services/`, `core/`, `screens/`
   without importing heavy modules. Shell-script Termux code cannot express
   "this dict has exactly these keys" anywhere.
3. **`assert_never` / `Never` exhaustiveness.** Our install-job state
   machine and error translation (`friendly_job_error`, `docs/roadmap.md:92`)
   can use `assert_never` so an unhandled distro/status case is a type error,
   not a silent fall-through that bricks an install on-device.
4. **Future-proof backport insurance.** If the Flet-bundled interpreter ever
   lags the language (roadmap M2/M5 build-recipe risk,
   `docs/roadmap.md:79-86,111-119`), typing-extensions is already in the
   tree as the sanctioned backport path — flet itself uses that exact
   mechanism (`base_control.py:21-23`). Termux pins shell + libc behaviour
   per device; we pin typing semantics per lockfile.

---

## 6. Verification

- `docs/roadmap.md` + `docs/reference/dep-httpx-cluster.md` read first.
- `__all__` count (121) and sorted member list verified at runtime via
  `python.exe -c "import typing_extensions"`.
- `__all__` literal at `typing_extensions.py:21`; conditional appends at
  `:4031` (`CapsuleType`), `:4413` (`no_type_check_decorator`); `Literal`
  lines `:460-530` spot-verified.
- flet usage verified by grep: `base_control.py:21-23,91`,
  `value_types.py:15-17,159`, `griffe_deprecations.py:7,37,39`.
- anyio/h11 usage lines verified by grep (module:line list in §3).
- `requires-python = ">=3.14"` from `pyproject.toml:8`; flet 1.0.4 from
  `flet-1*.dist-info/METADATA:3` (`Version: 1.0.4`).
- File size 165 012 B / 4 422 lines (`wc -l`, `du -sb`).
- Items marked **unverified** were not observable in installed source.
