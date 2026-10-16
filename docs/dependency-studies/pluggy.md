# pluggy 1.7.0 — Exhaustive API Reference

**Identity:** `pluggy` 1.7.0 · MIT · `Requires-Python: >=3.10`
(`pluggy-1.7.0.dist-info/METADATA`). The hook engine underneath pytest:
pytest's `PytestPluginManager` subclasses `pluggy.PluginManager` and every
`pytest_*` hook is a pluggy hookspec/hookimpl pair.
Verification: installed source under `.venv/Lib/site-packages/pluggy/` plus
live `inspect.signature` / `dir()` introspection. Unverifiable items are
marked **unverified**.

---

## 1. Module exports (`pluggy/__init__.py`, `__all__` verified)

```python
__all__ = ["HookCallError", "HookCaller", "HookImpl", "HookRelay",
           "HookimplMarker", "HookimplOpts", "HookspecMarker", "HookspecOpts",
           "PluggyTeardownRaisedWarning", "PluggyWarning", "PluginManager",
           "PluginValidationError", "Result", "__version__"]
```

`__version__` resolves lazily via `importlib.metadata.version("pluggy")`
(`__getattr__` in `__init__.py`) — there is no `pluggy.__version__` attribute
to import statically.

---

## 2. `PluginManager` — every method (signatures verified live)

Source: `pluggy/_manager.py`. Constructor: `PluginManager(project_name: str)`
(`_manager.py:158`).

| Method (line) | Verified signature | Behavior |
|---|---|---|
| `register` (:185) | `(self, plugin, name: str \| None = None) -> str \| None` | Register a plugin object/module; returns canonical name. Calls `parse_hookimpl_opts` per attribute; verifies against specs (`_verify_hook`, :431); raises `PluginValidationError` (`_manager.py:128`) on arg mismatch |
| `unregister` (:281) | `(self, plugin = None, name: str \| None = None) -> Any \| None` | Remove by object or name; returns the removed plugin |
| `set_blocked` (:325) | `(self, name: str) -> None` | Block a name from registering/loading |
| `is_blocked` (:330) | `(self, name: str) -> bool` | |
| `unblock` (:334) | `(self, name: str) -> bool` | Returns whether a block existed |
| `add_hookspecs` (:344) | `(self, module_or_class) -> None` | Register a hookspec namespace; parses `HookspecOpts` per spec |
| `parse_hookspec_opts` (:370) | `(self, module_or_class, name: str) -> HookspecOpts \| None` | Read back parsed spec opts |
| `parse_hookimpl_opts` (:258) | `(self, plugin, name: str) -> HookimplOpts \| None` | Read back parsed impl opts |
| `get_plugins` (:396) | `(self) -> set[Any]` | All registered plugin objects |
| `is_registered` (:400) | `(self, plugin) -> bool` | |
| `get_canonical_name` (:404) | `(self, plugin) -> str` | Name used at registration |
| `get_plugin` (:415) | `(self, name: str) -> Any \| None` | Lookup by name |
| `has_plugin` (:419) | `(self, name: str) -> bool` | |
| `get_name` (:423) | `(self, plugin) -> str \| None` | |
| `check_pending` (:481) | `(self) -> None` | Verify all hooks have implementations where required; raises on missing non-optional impls (**exact raise type unverified**) |
| `load_setuptools_entrypoints` (:497) | `(self, group: str, name: str \| None = None) -> int` | Load `importlib.metadata` entry points for group; returns count loaded. pytest calls this with `"pytest11"` |
| `list_plugin_distinfo` (:527) | `(self) -> list[tuple[plugin, DistFacade]]` | Plugin ↔ distribution mapping |
| `list_plugin_distributions` (:541) | signature **unverified** (exists at :541) | Distributions for registered plugins |
| `list_name_plugin` (:551) | `(self) -> list[tuple[str, plugin]]` | |
| `get_hookcallers` (:555) | `(self, plugin) -> list[HookCaller] \| None` | HookCallers a plugin implements |
| `add_hookcall_monitoring` (:570) | `(self, before, after) -> Callable[[], None]` | Install before/after tracing callbacks; returns undo callable |
| `enable_tracing` (:607) | `(self) -> Callable[[], None]` | Print-based tracing; returns undo |
| `subset_hook_caller` (:632) | `(self, name: str, remove_plugins) -> HookCaller` | Caller with selected plugins removed |
| `_hookexec` (:174) | internal | Core dispatch; wrapped by `add_hookcall_monitoring`'s `traced_hookexec` (:587, undo at :602) |

`_verify_hook` (`:431`) enforces that each hookimpl's argument names are a
subset of the hookspec's — the mechanism behind pytest's
"hookimpl got an unexpected keyword" errors.

---

## 3. `HookspecMarker` / `HookimplMarker` — every option

Constructors verified: `HookspecMarker(project_name: str)`,
`HookimplMarker(project_name: str)`.

### 3.1 `HookspecOpts` (verified annotations, `pluggy/_config.py`)

```python
HookspecOpts = {firstresult: bool, historic: bool,
                warn_on_impl: Warning | None,
                warn_on_impl_args: Mapping[str, Warning] | None}
```

- `firstresult=False` — when True, hook calling stops at the first non-`None`
  result and returns it directly (single value, not a list). pytest examples:
  collection hooks that may claim a file (**specific pytest firstresult hooks
  unverified** — consult `pytest.md` §4 against `_pytest/hookspec.py`).
- `historic=False` — historic hooks replay to late-registered plugins via
  `call_historic`; used for events plugins may join after the fact.
- `warn_on_impl` / `warn_on_impl_args` — emit a warning when an impl (or an
  impl using certain args) registers. Deprecation path for hook evolution.

### 3.2 `HookimplOpts` (verified annotations, `pluggy/_config.py`)

```python
HookimplOpts = {wrapper: bool, hookwrapper: bool, optionalhook: bool,
                tryfirst: bool, trylast: bool, specname: str | None}
```

- `tryfirst=False` / `trylast=False` — ordering hints; LIFO within the same
  bucket (later-registered run first unless ordered otherwise). pytest's
  deprecated `@pytest.mark.tryfirst/trylast` map to these.
- `wrapper=False` — **new-style** wrapper impl: `result = yield` then return
  (possibly modified) value; replaces `hookwrapper`.
- `hookwrapper=False` — **legacy** wrapper impl (old `yield`-dict protocol).
  Still present as a parameter on `pytest.hookimpl` in 9.1.1 (verified
  signature); new code must use `wrapper=True`. Whether the legacy protocol
  still executes in pluggy 1.7.0 is **unverified** — do not rely on it.
- `optionalhook=False` — impl is tolerated when no spec exists (no
  `PluginValidationError`); for forward-compatible plugins.
- `specname=None` — implement a hookspec under a different function name.

### 3.3 pytest aliases (verified signature on `pytest` object)

```python
pytest.hookimpl(function=None, hookwrapper=False, optionalhook=False,
                tryfirst=False, trylast=False, specname=None, wrapper=False)
pytest.hookspec(function=None, firstresult=False, historic=False,
                warn_on_impl=None, warn_on_impl_args=None)
```
i.e. `pytest.hookimpl = HookimplMarker("pytest")`,
`pytest.hookspec = HookspecMarker("pytest")`.

---

## 4. Hook calling semantics + `Result`

### 4.1 `HookCaller` (verified methods)

```python
HookCaller.__call__(self, **kwargs) -> Any      # normal call
call_extra(self, methods, kwargs) -> Any        # call with extra impls appended
call_historic(self, result_callback=None, kwargs=None) -> None  # historic replay
get_hookimpls(self) -> list[HookImpl]           # ordered impl list
has_spec / is_historic / name / spec / set_specification  # introspection
```

Call order: `tryfirst` impls → normal (LIFO registration) → `trylast` impls;
wrappers nest outermost-first. Non-`firstresult` calls return a **list** of
non-`None` results; `firstresult` returns the first non-`None` result.

### 4.2 `HookImpl` (verified dataclass fields)

`argnames, function, hookwrapper, kwargnames, optionalhook, opts, plugin,
plugin_name, tryfirst, trylast, wrapper`.

### 4.3 `Result` (verified methods)

```python
Result.get_result() -> ResultType        # re-raise stored exception or return value
Result.force_result(result) -> None      # wrapper override
Result.force_exception(exc) -> None      # wrapper override
Result.from_call(func) -> Result         # classmethod constructor (verified signature)
Result.exception  # property (exists; setter details unverified)
Result.excinfo / _exception / _result / _traceback  # internals (listed only)
HookCallError  # raised on call machinery failure (listed; trigger conditions unverified)
```

New-style wrapper impl shape:

```python
@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    result = yield        # run inner impls
    return result         # may inspect/modify
```

### 4.4 `HookRelay` — attribute access to a manager's `HookCaller`s
(`pluginmanager.hook.pytest_runtest_call(...)`). `PluggyWarning`,
`PluggyTeardownRaisedWarning`, `PluginValidationError` (with
`(plugin, message)` constructor, `_manager.py:135`) round out error handling.

---

## 5. How pytest builds on pluggy (big picture: hook lifecycle)

1. `PytestPluginManager()` created in `_pytest/config/__init__.py`;
   `pytest_addhooks` hook lets plugins contribute further specs.
2. `load_setuptools_entrypoints("pytest11")` autoloads installed plugins;
   conftests register as local plugins during collection.
3. Run phases dispatch through HookCallers in lifecycle order:
   configure → collection (`pytest_collection*`, `pytest_generate_tests`) →
   runtest protocol (`setup/call/teardown` + `pytest_runtest_makereport`) →
   reporting (`pytest_terminal_summary`, `pytest_report_teststatus`) →
   session finish/unconfigure. Full ordered list in `pytest.md` §4.
4. `pytest_collection_modifyitems` (deselect `-m "not live"`), `pytest_runtest_*`
   wrappers (timeout enforcement), and `pytest_report_*` reporters are all
   ordinary hookimpls — the plugin in §6 and any house conftest plugin speak
   exactly this protocol.

## 6. How OUR future testing utilities could use pluggy (honest: probably not)

pluggy is a plugin-dispatch engine; our test utilities need plain helpers, not
a hook bus. Concrete judgment:

- **Do NOT adopt pluggy for app/test code.** A `conftest.py` with fixtures
  (`FakePage`, `flet_tree`, env-guard autouse fixtures) covers every house
  need with less machinery. Introducing hookspecs for test utilities would add
  ordering/debug burden for zero gain.
- **The one legitimate use:** if we ever ship a reusable pytest plugin
  (e.g. a `proot-distro` fake-rootfs fixture plugin shared across repos), it
  would implement standard pytest hooks (`pytest_configure`,
  `pytest_collection_modifyitems`) — i.e. we *consume* pluggy through pytest,
  never instantiate `PluginManager` ourselves.
- Understanding pluggy still pays off: reading hookimpl ordering explains
  fixture/plugin interaction bugs and lets us write correct `wrapper=True`
  conftest hooks if timeout/report customization is ever needed.

---

## 7. How this dependency makes our app significantly better than Termux's proot-distro

pluggy is indirect (via pytest) but its properties shape our quality story:

1. **Plugin composition without forks.** Timeout enforcement, anyio async
   tests, junit XML for CI, and our future house plugins all coexist as
   `pytest11` entry points — no patching of pytest itself. Termux's shell
   tooling has no extension protocol; every behavior change is a fork of a
   script. Our CI gains capabilities by *installing a package*, mirroring the
   app's own "bump a version" update discipline.
2. **Ordered, debuggable test lifecycle.** `tryfirst/trylast` + wrapper hooks
   give deterministic ordering to collection tweaks (`-m "not live"`
   deselection), timeout timers, and report hooks. When CI behaves
   unexpectedly, `enable_tracing`-style hook tracing pinpoints which plugin
   acted — Termux failures are debugged by reading someone's shell history.
3. **Contract for shared test tooling.** If sibling apps standardize a house
   pytest plugin (FakePage harness, version-sync guards), pluggy's spec/impl
   verification (`_verify_hook` arg checking) catches integration mistakes at
   registration time instead of silently mis-running tests.

## 8. Verification refs

- Identity: `pluggy-1.7.0.dist-info/METADATA`.
- Exports: `pluggy/__init__.py` `__all__` + `__getattr__`.
- Manager methods/lines: `pluggy/_manager.py` def lines in §2 table; signatures
  via live `inspect.signature`.
- Opts: `pluggy/_config.py` `HookimplOpts`/`HookspecOpts` annotations (live).
- Caller/Result: `pluggy/_hooks.py`, `pluggy/_result.py` (live signatures).
- pytest integration: `_pytest/config/__init__.py:907,1364,1583`;
  `pytest.hookimpl/hookspec` live signatures.
