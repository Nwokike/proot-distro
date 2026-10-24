# typing-extensions — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `.venv/Lib/site-packages/typing_extensions.py:1-4422` · `.venv/Lib/site-packages/typing_extensions-4.16.0.dist-info/METADATA` · `.venv/Lib/site-packages/flet/controls/base_control.py:15-23,85-95,150-161` · `.venv/Lib/site-packages/flet/controls/value_types.py:10-17,155-165` · `.venv/Lib/site-packages/flet/utils/griffe_deprecations.py:1-45` · `.venv/Lib/site-packages/flet/components/observable.py:18-49` · `.venv/Lib/site-packages/flet/components/component_decorator.py:1-30` · `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:12-18` · `.venv/Lib/site-packages/anyio/__init__.py:1-40` · `.venv/Lib/site-packages/anyio/_core/_typedattr.py:1-14` · `.venv/Lib/site-packages/anyio/_core/_sockets.py:44-52` · `.venv/Lib/site-packages/anyio/_core/_tasks.py:19-27` · `.venv/Lib/site-packages/anyio/itertools.py:41-50` · `.venv/Lib/site-packages/anyio/abc/_streams.py:8` · `.venv/Lib/site-packages/anyio/abc/_sockets.py:14` · `.venv/Lib/site-packages/anyio/streams/tls.py:37-45` · `.venv/Lib/site-packages/anyio-4.15.1.dist-info/METADATA:27-29` · `.venv/Lib/site-packages/httpcore/_backends/anyio.py:6` · `src/` (all 32 `.py`) · `tests/test_imports_vs_deps.py:1-68` · `tests/conftest.py:5` · `pyproject.toml:8-15,99-105` · `uv.lock:5-16,192-205,298-311,803-810` · `docs/dependency-studies/typing-extensions.md` (study, prior knowledge) · `docs/reference/dep-httpx-cluster.md:1-20` · `docs/decisions.md:12-13` (D-003) · `.github/workflows/app.yml:47,52-53,108` · `docs/swarm/dependency-tree/uv-tree.txt:7` · `docs/swarm/dependency-tree/uv-tree-inverted.txt:97-99` · **Date:** 2026-10-22

## What it does / how the app uses it

typing-extensions 4.16.0 is a **single-file, 165,012-byte, 4,422-line** backport/experiment shim for
`typing` (`.venv/Lib/site-packages/typing_extensions.py`; size and line count measured).
`__all__` is a literal opening at `typing_extensions.py:21` with two conditional appends
(`:4031` `CapsuleType`, `:4413` `no_type_check_decorator`); runtime length is **121** — matches the
prior study (`docs/dependency-studies/typing-extensions.md:27`).

**The app never imports it — zero occurrences in `src/`, `tests/`, `pyproject.toml`,
`build_flet_proot_wheel.py`.** The app's entire typing footprint is two `from typing import Any`
(`src/core/shared_services.py:6`, `src/services/session_manager.py:12`) plus `collections.abc`
`Callable`/`Awaitable` (`src/state/controller_ctx.py:9`, `src/components/app_header.py:9`,
`src/services/ad_service.py:8`, `src/services/session_service.py:23`) and one in tests
(`tests/conftest.py:5`). There is **no** `TypedDict`, `Protocol`, `cast`, `override`, `Self`,
`Literal`, `Never`, `assert_never`, `TypeAlias`, `ParamSpec`, `TypeVarTuple`, `Unpack`,
`Required`/`NotRequired`, `ReadOnly`, `TypeIs`, `TypeGuard`, `dataclass_transform` or
`Annotated` anywhere in `src/`.

**Who actually pulls it in: `anyio`, not `flet`.** The declared dependency chain is
`typing-extensions → anyio → httpx → flet`:

```text
$ grep -n "Requires-Dist" .venv/Lib/site-packages/anyio-4.15.1.dist-info/METADATA
29:Requires-Dist: typing_extensions>=4.16.0; python_version < "3.15"
$ grep -n "Requires-Dist" .venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA
18:Requires-Dist: typing-extensions; python_version < "3.11"
$ grep -n "typing-extensions" uv.lock
11:    { name = "typing-extensions", marker = "python_full_version < '3.15'" },
804:name = "typing-extensions"
```

`flet-1.0.4.dist-info/METADATA:18` is marked `python_version < "3.11"`; the project floor is
`requires-python = ">=3.14"` (`pyproject.toml:8`), so **flet does not cause typing-extensions to be
installed at all** on our target. `anyio`'s marker is `python_version < "3.15"`, which **is** true
on 3.14 — anyio is the sole reason the package is in the tree. The inverted tree agrees:
`docs/swarm/dependency-tree/uv-tree-inverted.txt:97-99` (`typing-extensions v4.16.0 └── anyio
v4.15.1 └── httpx v0.28.1`). It ships in the APK, and the app's own in-app licence list declares
it correctly at `src/screens/views.py:38`.

## Findings

### F1 · P2 · `dataclass_transform` is **not** load-bearing on app launch — the house reference doc and the study misattribute typing-extensions to flet
- **Where:** `docs/reference/dep-httpx-cluster.md:13` ("`typing-extensions` … Parent: flet + anyio
  · `dataclass_transform` used EVERY app launch"); `docs/dependency-studies/typing-extensions.md:21`
  ("Load-bearing on EVERY app launch (flet control system)");
  `.venv/Lib/site-packages/flet/controls/base_control.py:20-23`;
  `.venv/Lib/site-packages/flet/controls/value_types.py:14-17`;
  `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:18`; `pyproject.toml:8`
- **What:** both flet import guards take the **stdlib** branch on our floor, so flet never touches
  typing-extensions at runtime, and the "every app launch" claim is false. The study's own §3.1
  (`docs/dependency-studies/typing-extensions.md:106-111`) already contradicts its §1 — §1 was
  never corrected.
- **Evidence:**

  ```text
  $ .venv/Lib/Scripts/python.exe -c "import flet, sys; print('typing_extensions' in sys.modules)"
  False
  $ .venv/Lib/Scripts/python.exe -c "
  import sys, pathlib; sys.path.insert(0, str(pathlib.Path('src').resolve()))
  import importlib
  mods=['.'.join(p.relative_to('src').with_suffix('').parts) for p in sorted(pathlib.Path('src').rglob('*.py'))]
  mods=[m for m in mods if m and not m.endswith('__init__')]
  for m in mods: importlib.import_module(m)
  print('typing_extensions in sys.modules =', 'typing_extensions' in sys.modules)"
  typing_extensions in sys.modules = False
  ```

  ```python
  # .venv/Lib/site-packages/flet/controls/base_control.py:20-23
  20: if sys.version_info >= (3, 11):
  21:     from typing import dataclass_transform
  22: else:
  23:     from typing_extensions import dataclass_transform
  ```

  ```python
  # .venv/Lib/site-packages/flet/controls/value_types.py:14-17
  14: if sys.version_info >= (3, 11):
  15:     from typing import dataclass_transform
  16: else:
  17:     from typing_extensions import dataclass_transform
  ```
- **Fix / opportunity:** correct `docs/reference/dep-httpx-cluster.md:13` to "Parent: **anyio**
  (via httpx); `sentinel` used on the async update-check path" and `docs/dependency-studies/typing-extensions.md:21`
  to the same. No code change.
- **Risk if ignored:** every future dependency/attribution audit inherits a false parent
  relationship. If someone "fixed" it by adding `typing-extensions` to `pyproject.toml` to make
  flet's import safe, they would add an unnecessary direct dependency to a set frozen by D-003
  (`docs/decisions.md:12-13`).

### F2 · P2 · The one *real* runtime consumer is `anyio`'s `sentinel` — reached only through the async update-check path
- **Where:** `.venv/Lib/site-packages/anyio/_core/_typedattr.py:9-14`;
  `.venv/Lib/site-packages/anyio/itertools.py:45-50`; `.venv/Lib/site-packages/anyio/abc/_streams.py:8`;
  `.venv/Lib/site-packages/anyio/abc/_sockets.py:14`; `.venv/Lib/site-packages/anyio/__init__.py:11`;
  `.venv/Lib/site-packages/httpcore/_backends/anyio.py:6`; `src/services/update_service.py:70-76`;
  `src/app_controller.py:88,309-317`
- **What:** `anyio` imports `sentinel` from typing-extensions at **module level** on Python < 3.15
  and calls it immediately. Every other anyio import is a `sys.version_info` guard that resolves to
  stdlib on 3.14. So typing-extensions **is** required at runtime — but only when the app performs
  an async HTTP request, not at launch, and not by flet.
- **Evidence:**

  ```python
  # .venv/Lib/site-packages/anyio/_core/_typedattr.py:9-14
   9: if sys.version_info < (3, 15):
  10:     from typing_extensions import sentinel
  ...
  14: undefined = sentinel("undefined")
  ```

  ```python
  # .venv/Lib/site-packages/anyio/itertools.py:45-50
  45: if sys.version_info < (3, 15):
  46:     from typing_extensions import sentinel
  ...
  50: _tee_end = sentinel("_tee_end")
  ```

  ```python
  # .venv/Lib/site-packages/anyio/_core/_sockets.py:44-52  → stdlib on 3.14
  44: if sys.version_info >= (3, 12):
  45:     from typing import override
  46: else:
  47:     from typing_extensions import override
  48:
  49: if sys.version_info < (3, 13):
  50:     from typing_extensions import deprecated
  51: else:
  52:     from warnings import deprecated
  ```

  ```python
  # .venv/Lib/site-packages/anyio/_core/_tasks.py:24-27 → stdlib on 3.14
  24: if sys.version_info >= (3, 11):
  25:     from typing import Never, Self, TypeVarTuple
  26: else:
  27:     from typing_extensions import Never, Self, TypeVarTuple
  ```

  Runtime proof of *when* it is loaded (plain `import anyio` is lazy —
  `.venv/Lib/site-packages/anyio/__init__.py:11` `if TYPE_CHECKING or not install_lazy_importer():`):

  ```text
  $ .venv/Scripts/python.exe -c "import anyio, sys; print('typing_extensions' in sys.modules)"
  False
  $ .venv/Scripts/python.exe -c "import anyio.abc._streams, sys; print('typing_extensions' in sys.modules)"
  True
  $ .venv/Scripts/python.exe -c "
  import asyncio, httpx, sys
  async def go():
      async with httpx.AsyncClient(timeout=4.0) as c:
          try: await c.get('http://127.0.0.1:9/x')
          except Exception: pass
  asyncio.run(go())
  print('typing_extensions in sys.modules =', 'typing_extensions' in sys.modules)"
  typing_extensions in sys.modules = True
  ```

  The app's own trigger is live: `src/app_controller.py:88` `self.page.run_task(self._check_for_updates)`
  → `:311-313` `from services.update_service import check_for_update; data = await check_for_update()`
  → `src/services/update_service.py:73-76` `import httpx` + `httpx.AsyncClient(...)`.
- **Fix / opportunity:** none needed — the dependency is correct and declared by its own upstream.
  The audit-relevant action is documentation only (see F1). Do **not** add `typing-extensions` to
  `pyproject.toml`; `anyio` already declares it with the right marker.
- **Risk if ignored:** none user-visible. The risk is mis-attribution (F1) leading to a wrong
  "we can drop typing-extensions" or "we must declare typing-extensions" conclusion.

### F3 · P3 · `dataclass_transform` is inert for this project — it is type-checker metadata, and this repo runs no type checker
- **Where:** `.venv/Lib/site-packages/flet/controls/base_control.py:91`;
  `.venv/Lib/site-packages/flet/controls/value_types.py:159`;
  `.venv/Lib/site-packages/flet/controls/base_control.py:160`;
  `.venv/Lib/site-packages/flet/components/observable.py:18-49`;
  `.venv/Lib/site-packages/flet/components/component_decorator.py:10-14`;
  `.github/workflows/app.yml:52-53,108`; `pyproject.toml:99-105`
- **What:** flet's actual dataclass behaviour comes from stdlib `dataclasses`
  (`base_control.py:160` `cls = dataclass(**dataclass_kwargs)(cls)`); `dataclass_transform` only
  stamps `__dataclass_transform__` metadata that **type checkers** read. The app's two state-bearing
  decorators do not even use it: `@ft.observable` is a plain mixin factory
  (`flet/components/observable.py:18-49`) and `@ft.component` is a plain wrapper
  (`flet/components/component_decorator.py:10-14`). With no mypy/pyright installed or configured,
  the metadata has **no consumer at all**.
- **Evidence:**

  ```python
  # .venv/Lib/site-packages/flet/controls/base_control.py:91,160
   91: @dataclass_transform()
   92: def control(
  ...
  160:     cls = dataclass(**dataclass_kwargs)(cls)  # Apply @dataclass first
  ```

  ```text
  $ ls -a | grep -iE "mypy|pyright|setup.cfg|tox.ini"   # no output
  $ ls .venv/Lib/site-packages | grep -iE "mypy|pyright"  # no output
  $ grep -n "ruff\|pytest" .github/workflows/app.yml
  52:          uv run ruff check src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
  53:          uv run ruff format --check src tests ...
  108:        run: uv run pytest -q -m "not live"
  ```

  `typing.dataclass_transform` (stdlib, 3.14) sets `cls_or_fn.__dataclass_transform__ = {...}`
  and nothing else — see `typing_extensions.py:2960` for the mirror implementation.
- **Fix / opportunity:** none for the dependency. The study's claim that "`@dataclass_transform`
  … is what lets our screens, state and controller bridge be statically checked"
  (`docs/dependency-studies/typing-extensions.md:182-188`) is currently unrealised — it would become
  true only if a type checker were added to CI. Flag that as a separate roadmap decision; it is not
  a typing-extensions defect.
- **Risk if ignored:** a future reader assumes the app is statically type-checked. It is not. A
  genuinely wrong annotation would not be caught by CI.

### F4 · P2 · The app uses **zero** typing-extensions features and barely uses `typing` at all — the study's §5.2/§5.3 opportunities are unrealised
- **Where:** `src/core/state.py:18,23,30,43`; `src/services/proot_service.py:184,206,263,272,393`;
  `src/services/update_service.py:70,89`; `src/services/session_manager.py:34-35`;
  `src/core/shared_services.py:21,30`; `src/screens/terminal_view.py:12,69`
- **What:** the app's data seams are untyped `dict`/`list`/`Any`, exactly where the study predicted
  `TypedDict`/`Protocol`/`Literal`/`assert_never` would pay off. The type-checker-friendly
  vocabulary the study recommends (`docs/dependency-studies/typing-extensions.md:186-203`) is
  absent from the codebase.
- **Evidence:**

  ```python
  # src/core/state.py:18,23,30,43
  18:     containers: list = None  # list[dict] — installed containers
  23:     search_results: list = None  # list[dict] — Docker Hub hits
  30:     theme_mode: str = "system"  # "system" | "light" | "dark"
  43:     update_data: dict | None = None
  ```

  ```python
  # src/services/proot_service.py:184,206,263,272,393
  184: def _container_rows() -> list[dict]:
  206: def list_containers() -> list[dict]:
  263: def search_images(query: str, limit: int = 20) -> list[dict]:
  272: def cached_images() -> list[dict]:
  393: def active_sessions() -> list[dict]:
  ```

  ```python
  # src/services/update_service.py:70,89
  70: async def check_for_update(config_url: str = UPDATE_CONFIG_URL) -> dict | None:
  89:         kind = raw_type if raw_type in ("update", "announcement") else "update"
  ```

  ```python
  # src/services/session_manager.py:34-35
  34:         self.session: Any = None
  35:         self.mt: Any = None
  ```

  ```python
  # src/core/shared_services.py:21,30
  21: def mount_shared_services(page: ft.Page) -> dict[str, Any]:
  30:     mounted: dict[str, Any] = {}
  ```

  `src/screens/terminal_view.py:12` imports `MobileTerminal` from `flet_terminal`, and
  `terminal_view.py:69` assigns it to `entry.mt` — so `session_manager.py:35` `self.mt: Any` has a
  concrete type available (`MobileTerminal | None`).
- **Fix / opportunity:** **stdlib-only**, no new dependency (see F5). Introduce
  `typing.TypedDict` row shapes for the container / search / cached-image / session rows and the
  update feed; `typing.Literal["system", "light", "dark"]` for `state.theme_mode`;
  `typing.Literal["update", "announcement"]` for the feed `type`; replace `Any` at
  `session_manager.py:34-35` with `ProotSession | None` / `MobileTerminal | None`; `typing.Protocol`
  for the `proot_service` / `session_service` seams the roadmap mandates.
- **Risk if ignored:** a renamed upstream key (e.g. `proot_service.py:200` `"size_bytes"`) silently
  becomes `None` in the UI instead of failing loudly — the exact failure mode the study contrasts
  with Termux's untyped CLI scraping.

### F5 · P2 · The app **cannot** import `typing_extensions` even if it wanted to — the import guard forbids it, which makes "use stdlib equivalents" mandatory rather than preferred
- **Where:** `tests/test_imports_vs_deps.py:46-59`; `pyproject.toml:9-15`; `docs/decisions.md:12-13` (D-003)
- **What:** `tests/test_imports_vs_deps.py` asserts that every non-stdlib, non-local import in
  `src/` is provided by a **declared** dependency. `typing-extensions` is not declared, so
  `from typing_extensions import X` in `src/` would fail CI. D-003 freezes the dependency set and
  requires owner sign-off for additions.
- **Evidence:**

  ```text
  $ .venv/Scripts/python.exe -m pytest tests/test_imports_vs_deps.py -q
  .                                                                        [100%]
  $ .venv/Scripts/python.exe -c "<read pyproject [project].dependencies>"
  declared deps: ['flet', 'flet_ads', 'flet_terminal', 'httpx', 'proot_distro']
  typing_extensions declared? False
  ```

  ```python
  # tests/test_imports_vs_deps.py:56-59
  56:             providers = {d.lower().replace("-", "_") for d in (dist_map.get(mod) or [])}
  57:             if not (providers & declared) and mod.lower() not in declared:
  58:                 missing.add(f"{path.relative_to(ROOT)}: {mod}")
  59:     assert not missing, "imports without a declared dependency:\n" + "\n".join(sorted(missing))
  ```

  Every name the app could plausibly want **already exists in stdlib `typing` on 3.14** (measured on
  the installed interpreter):

  ```text
  $ .venv/Scripts/python.exe -c "
  import typing
  names=['Self','override','TypedDict','Protocol','Required','NotRequired','ReadOnly','TypeAlias',
         'TypeAliasType','TypeGuard','TypeIs','Literal','Never','NoReturn','Final','ClassVar',
         'ParamSpec','TypeVarTuple','Unpack','dataclass_transform','assert_never','assert_type',
         'get_origin','get_args','get_type_hints','cast','runtime_checkable','Annotated',
         'Concatenate','TypeVar','NewType','overload']
  print('MISSING from stdlib typing 3.14:', [n for n in names if not hasattr(typing,n)])"
  MISSING from stdlib typing 3.14: []
  ```

  The names typing-extensions 4.16.0 adds that stdlib 3.14 genuinely lacks are all
  experimental/rare — `TypeForm`, `Format`, `sentinel`/`Sentinel`, `CapsuleType`, `runtime`,
  `Doc`, `Buffer`, `get_annotations` (3.14 exposes the latter via `annotationlib`,
  `typing_extensions.py:4034-4035`) — and `deprecated` lives in `warnings`, not `typing`. None is
  needed by the app.
- **Fix / opportunity:** keep it that way. State the rule in the house docs: *the app's typing
  vocabulary is stdlib `typing` only; `typing-extensions` is a transitive runtime artefact of
  `anyio` and must never be imported by `src/`.*
- **Risk if ignored:** someone adds `from typing_extensions import TypedDict` to satisfy F4 and
  breaks CI (`tests/test_imports_vs_deps.py:59`), or adds the package to `pyproject.toml` and
  breaks D-003.

### F6 · P3 · Prior-study §4.2 "unverified" item is now resolved — the exact set of names missing from stdlib `typing` on 3.14
- **Where:** `docs/dependency-studies/typing-extensions.md:147-152`; `.venv/Lib/site-packages/typing_extensions.py:179-182,271,4031,4034-4035`
- **What:** the study explicitly left "which exact names are still missing on 3.14" unverified. It is
  now verified against the installed interpreter.
- **Evidence:**

  ```text
  MISSING from stdlib typing 3.14: ['deprecated', 'TypeForm', 'Format', 'sentinel', 'Sentinel',
  'CapsuleType', 'runtime', 'get_annotations', 'Doc', 'Buffer']
  ```

  ```python
  # .venv/Lib/site-packages/typing_extensions.py:179-182
  179: if hasattr(builtins, "sentinel"):  # 3.15+
  180:     sentinel = builtins.sentinel
  181: else:
  182:     class sentinel:
  ```

  ```python
  # .venv/Lib/site-packages/typing_extensions.py:4034-4035
  4034: if sys.version_info >= (3, 14):
  4035:     from annotationlib import Format, get_annotations
  ```

  Also worth recording for the next audit: on 3.14 `typing_extensions.TypedDict is not
  typing.TypedDict` (measured `False` — typing-extensions ships its own at
  `typing_extensions.py:1359-1447` because 3.14's lacks `ReadOnly`/`extra_items` support), while
  `Self`, `override`, `cast`, `Protocol`, `Literal`, `TypeIs`, `TypeGuard`, `Never`,
  `Required`, `NotRequired`, `ReadOnly`, `ParamSpec`, `Unpack`, `dataclass_transform`,
  `assert_never`, `assert_type`, `get_origin`, `get_args`, `get_type_hints`, `TypeAlias` are all
  the **identical stdlib objects** (measured `True` for each `is` comparison).
- **Fix / opportunity:** update the study's §4.2 with this list.
- **Risk if ignored:** none directly; it removes an open item that would otherwise be re-litigated.

## Missed capabilities (dependency audits only)

`typing-extensions` is a **transitive runtime artefact of `anyio`** — the app must not import it
(F5). The capabilities worth adopting therefore come from **stdlib `typing` on 3.14**, which
typing-extensions exists only to back-port for older interpreters. Ordered by value:

1. **`TypedDict` — the row/feed shapes.** API: stdlib `typing.TypedDict` (3.14) /
   `typing_extensions.py:1359-1447` (`_create_typeddict`), `:1447` (`TypedDict` special form),
   `:1511` (`is_typeddict`). Integration points:
   `src/core/state.py:18` (`containers: list`), `:23` (`search_results: list`), `:43`
   (`update_data: dict | None`); `src/services/proot_service.py:184,206,263,272,393`
   (`-> list[dict]`); `src/services/update_service.py:70` (`-> dict | None`).
   Value: a renamed upstream key becomes a type error, not a silent `None` in the UI.
   Cost: ~5 small `TypedDict` declarations; zero new dependencies.
2. **`Literal` — the closed value sets already written in comments.**
   API: stdlib `typing.Literal` (`typing_extensions.py:462-463` re-export).
   Integration points: `src/core/state.py:30` (`# "system" | "light" | "dark"`),
   `src/services/update_service.py:89` (`("update", "announcement")`).
   Value: encodes an invariant the code already documents in prose.
   Cost: two one-line changes.
3. **`Protocol` — the service seams the roadmap mandates.**
   API: stdlib `typing.Protocol` (`typing_extensions.py:881`, `runtime_checkable` at `:907`).
   Integration points: `src/services/proot_service.py` (the sole importer of `proot_distro`,
   `proot_service.py:1`) and `src/services/session_service.py:72` (`ProotSession`).
   Value: a test double satisfies the seam without inheriting from it — the study's §5.2 point.
   Cost: two small protocol declarations.
4. **`assert_never` / `Never` — exhaustive status mapping.**
   API: stdlib `typing.assert_never` (`typing_extensions.py:1529` `assert_type` is the sibling;
   `assert_never` re-exported from `typing`).
   Integration points: `src/core/state.py:20` (`install_stage: str`) and the install-job status
   machine the study names (`docs/dependency-studies/typing-extensions.md:196-199`).
   Value: an unhandled distro/status case becomes a type error instead of a silent fall-through
   that bricks an install on-device.
   Cost: one `assert_never` at the default branch of an existing `match`.
5. **`Self` — fluent builders.** API: stdlib `typing.Self`
   (`typing_extensions.py:2429-2430`). Integration points: none today; relevant only if a builder
   is introduced. **Not worth doing now** — no such pattern exists in `src/`.
6. **`override` — explicit override marking.** API: stdlib `typing.override`
   (`typing_extensions.py:2972-2973`). Integration points: `src/services/session_manager.py` /
   `src/services/session_service.py` overrides. Value is low while no type checker runs (F3);
   **defer**.

**What typing-extensions itself offers that stdlib 3.14 lacks — and that the app should NOT use:**
`sentinel`/`Sentinel` (`typing_extensions.py:182`, `:271`) — anyio's only live use
(`anyio/_core/_typedattr.py:14`, `anyio/itertools.py:50`); `TypeForm` (`:2382`); `Format` /
`get_annotations` (`:4034-4035`, `annotationlib` on 3.14); `CapsuleType` (`:4031`); `Doc`; `Buffer`;
`runtime`. None is needed by an app whose floor is 3.14.

## Verified-good list

- **The package is correctly installed and correctly declared by its upstream.**
  `anyio-4.15.1.dist-info/METADATA:29` (`typing_extensions>=4.16.0; python_version < "3.15"`)
  resolves on our 3.14 floor; `uv.lock:11` carries the same marker and `uv.lock:803-810` pins
  4.16.0 with hashes. No manual pin is needed and none should be added (D-004 discipline).
- **flet's usage is version-guarded correctly.** `flet/controls/base_control.py:20-23` and
  `flet/controls/value_types.py:14-17` both take the stdlib branch on 3.14; the
  `typing_extensions` branches (`:23`, `:17`) are dead code here, exactly as the study's §3.1 said.
- **flet's other two typing-extensions mentions are doc-tooling string matches, not imports.**
  `flet/utils/griffe_deprecations.py:7` (docstring), `:37` (`_ANNOTATED_PATHS`),
  `:39` (`_PEP702_DECORATORS`) — all string literals for the Griffe docs extension.
- **The app's in-app licence list is right.** `src/screens/views.py:38` lists `typing-extensions`;
  it genuinely ships in the APK (anyio → typing-extensions) and is correctly rendered with the
  PSF-2.0 licence (`src/screens/views.py:50` `("PSF-2.0.txt", "PSF-2.0")`).
- **The app's typing usage is already stdlib-clean.** `Callable`/`Awaitable` come from
  `collections.abc` (`src/state/controller_ctx.py:9`, `src/components/app_header.py:9`,
  `src/services/ad_service.py:8`, `src/services/session_service.py:23`); `Any` comes from
  `typing` (`src/core/shared_services.py:6`, `src/services/session_manager.py:12`,
  `tests/conftest.py:5`). Ruff's `UP` rules are enabled (`pyproject.toml:104`) with
  `target-version = "py314"` (`:101`) and pass in CI (`.github/workflows/app.yml:52-53`).
- **The prior study's inventory numbers are accurate.** `__all__` = 121 (runtime),
  literal at `typing_extensions.py:21`, conditional appends at `:4031` and `:4413`,
  `Literal` re-export at `:462-463`, file = 4,422 lines / 165,012 bytes.
- **`pyproject.toml:8` `requires-python = ">=3.14"`** matches the installed interpreter
  (3.14.7) and matches `flet_cli/utils/python_versions.py:165-183` (highest stable row satisfying
  the `>=3.14` specifier), so the Android runtime is a 3.14.x CPython — the same marker
  evaluation as the dev environment.
- **PEP 758 unparenthesised `except` is valid on this floor** and is not a defect:
  `src/services/update_service.py:63` (`except TypeError, ValueError:`) and
  `src/services/session_service.py:123` (`except OSError, ValueError:`) both parse — verified with
  `.venv/Scripts/python.exe -m compileall src/services/update_service.py` (exit 0) and
  `ast.parse` on Python 3.14.7. Do not "fix" them.

## Unverified

- **Whether the Android CPython is exactly 3.14.x.** `flet_cli/utils/python_versions.py:36-38`
  fetches the manifest from `https://github.com/flet-dev/python-build/releases/download/20260921/manifest.json`
  at build time; the manifest was not fetched here (no network). The conclusion "`typing_extensions`
  is installed on device" rests on `pyproject.toml:8` (`>=3.14`) plus the resolution rule at
  `:165-183`, which yields a 3.14.x row — not on the manifest itself.
- **Which anyio sub-module is the *first* to import typing-extensions in the real device run.**
  The chain `anyio.abc._streams`/`anyio.abc._sockets` → `anyio._core._typedattr` → `sentinel` is
  proven by isolation; the exact first importer in a full app launch was not traced module-by-module.
- **The `flet` build recipe's `pip` marker evaluation on device.** `flet build` resolves the
  Android payload from `pyproject.toml:9-15` + `pyproject.toml:52`; the on-device `pip` marker
  resolution for `python_version < "3.15"` was not executed (no Android build here). The APK
  payload itself was not inspected.
- **`typing_extensions` behaviour on Python 3.15.** The `builtins.sentinel` branch
  (`typing_extensions.py:179-180`) and the `sys.version_info < (3, 15)` guard at `:4411` imply
  3.15 drops the `sentinel` requirement for anyio; not executed on a 3.15 interpreter.
- **Static type-checking outcomes.** No type checker is installed, so no claim is made about
  whether the app's current annotations would pass mypy/pyright; the "inert" claim in F3 is about
  the absence of a checker, verified by config/dependency inspection only.
