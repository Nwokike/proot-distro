# pytest 9.1.1 — Exhaustive API Reference

**Identity:** `pytest` 9.1.1 · MIT (`License-Expression: MIT`) · `Requires-Python: >=3.10`
· entry points `py.test` / `pytest` → `_pytest.config:_console_main`
(`.venv/Lib/site-packages/pytest-9.1.1.dist-info/entry_points.txt`).
Verification method: every claim below is traced to installed source (`file:line`)
or live introspection via `.venv/Scripts/python.exe`; anything not verifiable is
marked **unverified**.

House config (from `docs/reference/dep-test-and-lint-stack.md`): `pythonpath=["src"]`,
`timeout = 60`, `timeout_method = "thread"`, `strict_config` / `strict_markers`,
own-module warnings as errors, a `live` marker for device tests.

---

## 1. Fixture system

### 1.1 `@pytest.fixture` signature

Live introspection of `pytest.fixture`:

```python
fixture(fixture_function=None, *, scope='function', params=None, autouse=False,
        ids=None, name=None)
```

Overloads live at `.venv/Lib/site-packages/_pytest/fixtures.py:1435,1447,1458`.
`ids` accepts a sequence or a callable mapping each param value to an id.
`scope` accepts a name or a callable `(name: str, config: Config) -> ScopeName`
for dynamic scopes.

### 1.2 Scopes

`.venv/Lib/site-packages/_pytest/scope.py:18`:

```python
ScopeName = Literal["session", "package", "module", "class", "function"]
```

`Scope.from_user(scope_name, descr, where)` validates user input
(`_pytest/scope.py:63-83`); an invalid scope name calls `pytest.fail` with a
message. Scope ordering high→low: session > package > module > class > function.
A fixture may only depend on fixtures of equal or wider scope (narrower raises
`ScopeMismatch`).

### 1.3 Fixture request object

`FixtureRequest` ABC at `_pytest/fixtures.py:440`; concrete `TopRequest`
(`:771`) and `SubRequest` (`:813`). Practically used attributes (verified by
source read): `request.param` (indirect parametrization value), `request.config`,
`request.node`, `request.scope`, `request.fixturename`, `request.addfinalizer(fn)`.
`yield`-fixtures preferred over `addfinalizer` in new code.

### 1.4 ALL built-in fixtures (verified via `pytest --fixtures` on this install)

| Fixture | Scope | Source | Notes |
|---|---|---|---|
| `cache` | function | `_pytest/cacheprovider.py:560` | `Cache.get(key, default)`, `.set(key, value)`, `.mkdir(name)` (`cacheprovider.py:163,187,206`); persists in `.pytest_cache`; backs `--lf/--ff/--sw` |
| `capsys` | function | `_pytest/capture.py:1007` | text capture of `sys.stdout/stderr`; API `readouterr()`, `disabled()`, `close()` (verified on `CaptureFixture`) |
| `capteesys` | function | `_pytest/capture.py:1035` | capture + pass-through per `--capture=` |
| `capsysbinary` | function | `_pytest/capture.py:1070` | bytes capture of `sys.stdout/stderr` |
| `capfd` | function | `_pytest/capture.py:1098` | file-descriptor-level text capture (fd 1/2); sees C-extension output |
| `capfdbinary` | function | `_pytest/capture.py:1126` | fd-level bytes capture |
| `doctest_namespace` | session | `_pytest/doctest.py:721` | dict injected into doctest namespace |
| `pytestconfig` | session | `_pytest/fixtures.py:1564` | the session `Config` object |
| `record_property` | function | `_pytest/junitxml.py:275` | extra `<property>` on the test (deprecated alias path — prefer `record_xml_attribute` where possible; both present in 9.1.1) |
| `record_xml_attribute` | function | `_pytest/junitxml.py:298` | extra XML attribute on test tag |
| `record_testsuite_property` | session | `_pytest/junitxml.py:336` | `<property>` on root `<testsuite>` |
| `tmpdir_factory` | session | `_pytest/legacypath.py:298` | legacy `py.path` factory (legacy path; prefer `tmp_path_factory`) |
| `tmpdir` | function | `_pytest/legacypath.py:305` | legacy per-test dir (prefer `tmp_path`) |
| `caplog` | function | `_pytest/logging.py:611` | `LogCaptureFixture`: `handler`, `records`, `record_tuples`, `messages`, `text`, `get_records(when)`, `set_level(level, logger=None)`, `at_level(level, logger=None)`, `clear()`, `filtering` (verified via introspection) |
| `monkeypatch` | function | `_pytest/monkeypatch.py:36` | `setattr`, `delattr`, `setitem`, `delitem`, `setenv`, `delenv`, `chdir`, `syspath_prepend`, `context()`, `undo()` (verified via introspection); all undone at teardown |
| `recwarn` | function | `_pytest/recwarn.py:37` | `WarningsRecorder`: `list`, `pop(cls)`, `clear()`; `WarningsChecker` (used by `pytest.warns`) adds `matches(...)` |
| `subtests` | function | `_pytest/subtests.py:136` | `with subtests.test(msg=...):` subtest blocks |
| `tmp_path_factory` | session | `_pytest/tmpdir.py:276` | `TempPathFactory`: `mktemp(basename, numbered=True)`, `getbasetemp()`, `from_config(config)` (verified) |
| `tmp_path` | function | `_pytest/tmpdir.py:291` | per-test `pathlib.Path` dir under numbered base temp |

Plugin-provided extras on this install (NOT pytest builtins): `anyio_backend`,
`anyio_backend_name`, `anyio_backend_options`, `free_tcp_port_factory`,
`free_udp_port_factory`, `free_tcp_port`, `free_udp_port` (from
`anyio/pytest_plugin.py`), and `@pytest.mark.anyio` / `@pytest.mark.timeout`
markers. Do not document these as pytest API.

### 1.5 House guidance on fixtures (this project)

- **Lean on `tmp_path`** for ProotSession/service tests: fake rootfs trees,
  fake container dirs (`containers/<name>/{rootfs,manifest.json,shm}`), fake
  `oci_layers/` — never touch the real filesystem.
- **Lean on `monkeypatch`** for the env contract: `proot-distro` reads
  `TERMUX__PREFIX`, `PD_PROOT_BIN`, etc. at import time — `monkeypatch.setenv`
  + `monkeypatch.delitem(sys.modules, "proot_distro...")` gives hermetic
  re-import tests. **This is standard capture/env control, NOT patching
  upstream** (owner rule targets monkeypatching library internals; env setup
  before import is the documented contract).
- **Lean on `caplog`** for stage-line assertions if the service logs install
  stages; use `capsys`/`capfd` if asserting on `redirect_stderr` capture of
  upstream progress output.
- **`pytestconfig`** for asserting house ini (e.g. timeout value) in a
  `test_config_parity.py` guard test — sibling apps use `test_imports_vs_deps.py`
  + `test_version_sync.py`; add config assertions the same way.

---

## 2. Markers system + ALL builtin markers

### 2.1 Mechanics

- Registration: `markers` ini key (linelist, `addinivalue_line`); unknown marks
  with `strict_markers` raise `PytestUnknownMarkWarning` as error
  (`_pytest/warning_types.py:86`).
- `@pytest.mark.NAME` is a `MarkGenerator` (verified: `mark -> MarkGenerator`).
- `-m MARKEXPR` selects; `--markers` lists; `-m "not live"` is the house CI
  split (device tests marked `live` are deselected on desktop CI).

### 2.2 Builtin markers (verified via `pytest --markers` on this install)

| Marker | Signature / form | Source of truth |
|---|---|---|
| `skip(reason=None)` | skip unconditionally | `--markers` output |
| `skipif(condition, ..., *, reason=...)` | skip if any condition true | `--markers` output |
| `xfail(condition, ..., *, reason=..., run=True, raises=None, strict=strict_xfail)` | expected failure; `strict` defaults to `strict_xfail` ini | `--markers` output |
| `parametrize(argnames, argvalues, ...)` | ids, indirect supported (ids/indirect verified by `--markers` long text — full kwargs **unverified** beyond common use) | `--markers` output |
| `usefixtures(name1, name2, ...)` | attach fixtures without params | `--markers` output |
| `filterwarnings(warning)` | per-test warning filter | `--markers` output |
| `tryfirst` | hook-ordering; **DEPRECATED**, use `@pytest.hookimpl(tryfirst=True)` | `--markers` output |
| `trylast` | hook-ordering; **DEPRECATED**, use `@pytest.hookimpl(trylast=True)` | `--markers` output |
| `timeout(...)` | from pytest-timeout plugin, NOT a builtin (see `pytest-timeout.md`) | plugin |
| `anyio` | from anyio plugin, NOT a builtin | plugin |

House `live` marker must be registered in `markers = ["live: ..."]` so
`strict_markers` passes.

---

## 3. `pytest.approx` / `raises` / `warns` / `deprecated_call` / `fail` / `skip` / `importorskip`

All signatures verified by live introspection:

```python
approx(expected, rel=None, abs=None, nan_ok=False) -> ApproxBase
# rel/abs accept float | Decimal | timedelta | None (verified annotation)

raises(expected_exception=None, func=None, *args, **kwargs) -> RaisesExc | ExceptionInfo
# RaisesExc API (verified): .matches(...), .fail_reason

warns(expected_warning=Warning, func=None, *args, **kwargs) -> WarningsChecker | Any
# WarningsChecker API (verified): .list, .pop(cls), .clear(), .matches(...)

deprecated_call(func=None, *args, **kwargs) -> WarningsRecorder | Any

fail(reason='', pytrace=True) -> NoReturn        # raises Failed
skip(reason='', allow_module_level=False) -> NoReturn   # raises Skipped
exit(reason='', returncode=None) -> NoReturn     # raises Exit
xfail(reason='') -> NoReturn                      # raises XFailed

importorskip(modname, minversion=None, reason=None, *, exc_type=None) -> Any
# source: _pytest/outcomes.py:198
```

Outcome exception hierarchy (`_pytest/outcomes.py:13,39,59,65,76`):
`OutcomeException(BaseException)` → `Skipped`, `Failed` → `XFailed(Failed)`;
`Exit(Exception)` is separate. `importorskip` is the house tool for optional
deps in tests (e.g. skip flet-dependent UI tests when packaged minimally).

---

## 4. Hooks — full lifecycle list (inventory level)

All from `.venv/Lib/site-packages/_pytest/hookspec.py` (line numbers = the
`def pytest_*` lines). Firstresult hooks return a single non-`None` result;
all others collect lists. `wrapper=True` hookimpls wrap the call
(see `pluggy.md`).

**Startup / configuration:** `pytest_addhooks` (:54), `pytest_plugin_registered`
(:72), `pytest_addoption` (:97), `pytest_configure` (:138),
`pytest_cmdline_parse` (:162), `pytest_load_initial_conftests` (:185),
`pytest_cmdline_main` (:203), `pytest_sessionstart` (:888),
`pytest_sessionfinish` (:901), `pytest_unconfigure` (:917).

**Collection:** `pytest_collection` (:227), `pytest_collection_modifyitems`
(:268), `pytest_collection_finish` (:290), `pytest_ignore_collect` (:303),
`pytest_collect_directory` (:336), `pytest_collect_file` (:365),
`pytest_collectstart` (:392), `pytest_itemcollected` (:407),
`pytest_collectreport` (:421), `pytest_deselected` (:436),
`pytest_make_collect_report` (:458), `pytest_pycollect_makemodule` (:482),
`pytest_pycollect_makeitem` (:509), `pytest_generate_tests` (:552),
`pytest_make_parametrize_id` (:568).

**Run:** `pytest_runtestloop` (:594), `pytest_runtest_protocol` (:620),
`pytest_runtest_logstart` (:660), `pytest_runtest_logfinish` (:678),
`pytest_runtest_setup` (:698), `pytest_runtest_call` (:717),
`pytest_runtest_teardown` (:733), `pytest_runtest_makereport` (:758),
`pytest_runtest_logreport` (:777), `pytest_pyfunc_call` (:535),
`pytest_fixture_setup` (:834), `pytest_fixture_post_finalizer` (:862).

**Reporting / misc:** `pytest_report_to_serializable` (:792),
`pytest_report_from_serializable` (:811), `pytest_assertrepr_compare` (:934),
`pytest_assertion_pass` (:957, needs `enable_assertion_pass_hook`),
`pytest_report_header` (:1005), `pytest_report_collectionfinish` (:1031),
`pytest_report_teststatus` (:1068), `pytest_terminal_summary` (:1100),
`pytest_warning_recorded` (:1122), `pytest_markeval_namespace` (:1166),
`pytest_internalerror` (:1195), `pytest_keyboard_interrupt` (:1214),
`pytest_exception_interact` (:1228), `pytest_enter_pdb` (:1260),
`pytest_leave_pdb` (:1276).

`@pytest.hookimpl` signature (verified):
`hookimpl(function=None, hookwrapper=False, optionalhook=False, tryfirst=False, trylast=False, specname=None, wrapper=False)`.
`hookwrapper` is the legacy name; `wrapper=True` is the new-style wrapper impl
(**unverified** whether `hookwrapper=` still accepted at runtime in 9.1.1 —
the parameter exists on the marker; prefer `wrapper=True`).
`@pytest.hookspec` signature (verified):
`hookspec(function=None, firstresult=False, historic=False, warn_on_impl=None, warn_on_impl_args=None)`.

---

## 5. Config options — EVERY ini key relevant to the house config

Complete ini-key inventory extracted by scanning `addini(` across
`.venv/Lib/site-packages/_pytest/**/*.py` (41 keys). House-relevant first:

| Key | Type / value shape | House use |
|---|---|---|
| `pythonpath` | paths | `["src"]` — house style |
| `strict_config` | bool | fail on unknown config; house ON |
| `strict_markers` | bool | fail on unknown marks; house ON |
| `strict` | bool (sets both above) | alternative single switch |
| `filterwarnings` | linelist | own-module warnings as errors, e.g. `error::Warning::proot_service` style entries |
| `markers` | linelist | register `live` + any project marks |
| `testpaths` | args | point at `tests` |
| `addopts` | args | e.g. `-m "not live"` for default CI run |
| `python_files/classes/functions` | args | default `test_*.py` / `Test*` / `test*` |
| `usefixtures` | args | project-wide autouse list |
| `minversion` | string | floor the pytest version (packaging-backed, `_pytest/config/__init__.py:1455`) |
| `required_plugins` | args | packaging-requirement strings enforced at startup (`config/__init__.py:1472-1474`) |
| `norecursedirs` | args | collection excludes |
| `consider_namespace_packages` | bool | src-layout namespace support |
| `collect_imported_tests` | bool | **unverified** semantics — listed, not studied |
| `console_output_style` | string | `classic`/`progress` |
| `truncation_limit_lines/chars` | int | assertion output truncation |
| `log_cli` (+ `log_cli_level/format/date_format`) | bool/string | live log capture config (**sub-key names unverified** — listed family only) |
| `junit_*` (`junitxml` is a CLI flag; ini: `junit_family/duration_report/log_passing_tests/logging/suite_name`) | mixed | CI XML reports |
| `cache_dir` | string | relocate `.pytest_cache` |
| `faulthandler_timeout/exit_on_timeout` | float/bool | hang diagnostics |
| `max_warnings` | int | warning-count gate |
| `tmp_path_retention_count/policy` | int/string | numbered-temp retention |
| `doctest_optionflags/encoding` | args/string | doctest runs |
| `assertion_text_diff_style` | string | **unverified** values |
| `enable_assertion_pass_hook` | bool | enables `pytest_assertion_pass` |
| `strict_xfail` | bool | default for xfail `strict=` |
| `strict_parametrization_ids` | bool | id validation |
| `import-mode` equivalent | CLI only (`--import-mode`) | `prepend`/`append`/`importlib` |
| `pytester_example_dir` | string | pytester-internal |
| `disable_test_id_escaping_and_forfeit_all_rights_to_community_support` | bool | exotic; listed only |
| `timeout/timeout_method/timeout_func_only/session_timeout` | plugin keys | see `pytest-timeout.md` |

Config file mode rule (verified in D4 study + `_pytest/config/__init__.py`):
`[tool.pytest.ini_options]` (string-INI compat) and `[tool.pytest]` (native TOML)
are mutually exclusive — both present = hard `UsageError`. House uses
`[tool.pytest.ini_options]`.

---

## 6. CLI flags enumeration (practical set, verified from `pytest --help`)

- **Selection:** `file_or_dir` positionals, `-k EXPRESSION`, `-m MARKEXPR`,
  `--markers`, `--fixtures/--fixtures-per-test`, `--collect-only/--co`,
  `--ignore/--ignore-glob`, `--deselect`, `--confcutdir`, `--pyargs`,
  `--import-mode={prepend,append,importlib}`, `--continue-on-collection-errors`.
- **Rerun/state:** `-x/--exitfirst`, `--maxfail=num`, `--lf/--last-failed`,
  `--ff/--failed-first`, `--nf/--new-first`, `--sw/--stepwise` (+ `--sw-skip`,
  `--sw-reset`), `--lfnf/--last-failed-no-failures={all,none}`,
  `--cache-show/--cache-clear`, `--stepwise` family backed by `cache` fixture.
- **Output:** `-v/-q`, `--tb={auto,long,short,line,native,no}`,
  `-r chars` (default `fE`), `-l/--showlocals`, `--no-showlocals`,
  `--show-capture={no,stdout,stderr,log,all}`, `--full-trace`,
  `--durations=N`, `--durations-min=N`, `--disable-warnings`,
  `-W/--pythonwarnings`, `--max-warnings`, `--junitxml/--junit-xml`,
  `--junitprefix/--junit-prefix`, `--no-header/--no-summary/--no-fold-skipped`.
- **Execution:** `-s` (= `--capture=no`), `--capture={fd,sys,no,tee-sys}`,
  `--pdb/--pdbcls/--trace`, `--runxfail`,
  `--doctest-modules/--doctest-report`, `--strict-config/--strict-markers/--strict`.
- **Timeout (plugin):** `--timeout`, `--timeout-method`,
  `--timeout_method` (deprecated alias), `--session-timeout` + `timeout`
  marker — see `pytest-timeout.md`.

---

## 7. Plugin system + entry points

- Entry-point group **`pytest11`** (verified `_pytest/config/__init__.py:907,1364,1583`):
  `load_setuptools_entrypoints("pytest11")` autoloads installed plugins;
  disable with `-p no:NAME` or `PYTEST_DISABLE_PLUGIN_AUTOLOAD`.
- `PytestPluginManager` (in `_pytest/config/__init__.py`) subclasses pluggy's
  `PluginManager`; `pytest_addhooks` lets a plugin register additional
  `pyproject`-level hookspecs. Conftest files are local plugins loaded at
  collection (`pytest_load_initial_conftests`, `confcutdir`-scoped).
- `required_plugins` ini enforces presence via `packaging.requirements.Requirement`
  (verified `config/__init__.py:1472-1474`); `minversion` via
  `packaging.version.Version` (`:1455`).

## 8. `_pytest` internals worth knowing

- **`_pytest.stash.Stash`**: type-safe heterogeneous map on `Config`
  (`config.stash`). Verified API: `StashKey()` (no-arg construction),
  `stash[key]`, `stash.get(key, default)`, `stash.setdefault(key, default)`.
  pytest-timeout stores its session deadline here.
- **`_pytest.config.Config`**: `config.getini(name)`, `config.getoption(name)`,
  `config.addinivalue_line(name, line)`, `config.getvalue(name)` (optpass-style).
- **`_pytest.fixtures.FixtureManager`**: resolves scope ordering, params, autouse.
- **Warning types** (`_pytest/warning_types.py`): `PytestWarning`,
  `PytestAssertRewriteWarning`, `PytestCacheWarning`, `PytestConfigWarning`,
  `PytestCollectionWarning`, `PytestDeprecationWarning`,
  `PytestRemovedIn10Warning`, `PytestExperimentalApiWarning`,
  `PytestReturnNotNoneWarning`, `PytestUnknownMarkWarning`,
  `PytestUnraisableExceptionWarning`, `PytestUnhandledThreadExceptionWarning`,
  `PytestFDWarning` — target `filterwarnings` at these for the house
  warnings-as-errors policy.
- **Assertion rewriting** import hook (`_pytest/assertion/`): the source of the
  rich `assert` introspection; `ImportError`-sensitive in exotic loaders
  (**unverified** edge details).
- **Python 3.14 specifics in 9.x:** `Requires-Python >=3.10`; the venv here runs
  CPython 3.14.7 with pytest 9.1.1 green. Per-version 3.14 behavioral notes
  (free-threading, new warning classes) are **unverified** — no 3.14-specific
  code paths were found in the surveyed modules.

---

## 9. How this dependency makes our app significantly better than Termux's proot-distro

Termux's proot-distro ships shell scripts with no automated test story: every
change is validated by hand on a device. Our pytest suite is the structural
advantage:

1. **Contract tests pin the upstream surface.** `test_imports_vs_deps.py`-style
   guards plus tests over `parse_reference`, `derive_alias`,
   `iter_cached_images`, `paths.*`, `progress.fmt_size` fail loudly on a bump
   that renames anything — Termux discovers that breakage from user bug
   reports; we discover it in CI before release.
2. **Fake-transport ProotSession tests.** `tmp_path` fake rootfs +
   `monkeypatch` env control lets us test install/list/remove/login-argv logic
   fully offline on Windows/Linux CI — no phone, no root, no network. Termux
   has no equivalent; their logic is only exercisable inside Termux.
3. **Release quality gating.** `pytest -m "not live"` + warnings-as-errors +
   `--timeout=60` in the quality job means no release artifact builds while a
   regression or hang exists. Termux releases are cut by hand; ours are gated
   by machine.
4. **Doctest-able pure helpers.** `fmt_size`, alias derivation, and error
   translation get doctests/examples that double as documentation — the
   project's onboarding story Termux lacks.

## 10. Verification refs

- Versions/licenses: `pytest-9.1.1.dist-info/METADATA`, `entry_points.txt`.
- Markers/fixtures: `pytest --markers`, `pytest --fixtures` (anyio + timeout
  entries are plugin-provided, excluded from builtin tables).
- Hooks: `_pytest/hookspec.py` def lines listed in §4.
- Ini keys: `addini(` scan over `_pytest/**/*.py` (§5).
- Signatures: live `inspect.signature` (§1.1, §3, hookimpl/hookspec).
- `ScopeName`: `_pytest/scope.py:18`; scopes validation `:63-83`.
- Stash/MonkeyPatch/caplog/capsys/TempPathFactory/WarningsChecker/RaisesExc:
  live `dir()` introspection.
- Outcomes: `_pytest/outcomes.py:13,39,59,65,76,198`.
- Warning types: `_pytest/warning_types.py` class lines.
- Entry-point group: `_pytest/config/__init__.py:907,1364,1583`;
  packaging use `:1455,1472-1474`; `outcomes.py:279`; `unittest.py:565`.
- House style: `docs/roadmap.md` §1b, `docs/reference/dep-test-and-lint-stack.md`.
