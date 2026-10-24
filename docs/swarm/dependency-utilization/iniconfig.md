# iniconfig 2.3.1 — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/iniconfig.md`; `docs/reference/dep-test-and-lint-stack.md`; `docs/reference/app-sherlock.md`; `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `tests/conftest.py`; `tests/` (all 11 files); `src/` (all 30 `.py` files); `.venv/Lib/site-packages/iniconfig/` (all 5 modules); `.venv/Lib/site-packages/iniconfig-2.3.1.dist-info/`; `.venv/Lib/site-packages/_pytest/config/findpaths.py`; `.venv/Lib/site-packages/_pytest/config/__init__.py`; `.venv/Lib/site-packages/_pytest/main.py`; `.venv/Lib/site-packages/_pytest/warnings.py`; `.venv/Lib/site-packages/_pytest/terminal.py`; `.venv/Lib/site-packages/pytest_timeout.py`; `.venv/Lib/site-packages/flet/pytest_plugin.py`; `docs/swarm/dependency-tree/uv-tree.txt`; `docs/swarm/dependency-tree/uv-tree-inverted.txt` · **Date:** 2026-10-20

## What it does / how the app uses it

**Plainly: the app does not use iniconfig, and no app use of iniconfig is appropriate.**

- **iniconfig is dev-only and transitive.** It is required by exactly one package, **pytest** (`uv.lock:636`, inside the `pytest` block at `uv.lock:631`; the same edge in `docs/swarm/dependency-tree/uv-tree.txt:59-61` and `uv-tree-inverted.txt:45-46`: `iniconfig v2.3.1 └── pytest v9.1.1`). pytest itself is in the **dev** dependency group only (`pyproject.toml:77-84`, `pytest>=9.1.1` at `pyproject.toml:81`); `[project].dependencies` (`pyproject.toml:9-15`) does not contain pytest or iniconfig, so iniconfig is not in the Android resolve and cannot reach the APK.
- **Nothing in the repo imports it.** `grep -rn "iniconfig" src/ tests/ .github/ build_flet_proot_wheel.py pyproject.toml` → **no output** (only `uv.lock`, `docs/dependency-studies/`, `docs/reference/` and this report mention the name).
- **pytest never even parses our config with it.** Our config file is `pyproject.toml`, and pytest reads that path with **`tomllib`**, not iniconfig (`.venv/Lib/site-packages/_pytest/config/findpaths.py:96-153` — `import tomllib` at `:97-100`, `tomllib.loads` at `:104`, the `[tool.pytest.ini_options]` branch at `:144-153`). iniconfig is used **only** for `.ini`/`.cfg` files (`findpaths.py:46-55`, `:66-91`). The repo has **no** `pytest.ini`, `tox.ini`, `setup.cfg`, `pytest.toml` or `.pytest.toml` at the root (`ls pytest.ini tox.ini setup.cfg pytest.toml .pytest.toml` → *No such file or directory*), so iniconfig's parser is dead code in this project. Proven at runtime, not inferred:
  ```
  $ PYTHONPATH=… .venv/Scripts/python.exe -m pytest -p inicheck_plugin --collect-only -q
  INICONFIG-IniConfig-INIT-CALLS: NONE
  ```
  (the plugin wraps `iniconfig.IniConfig.__init__`; it is never called during a full collection of this repo).
- **The installed API matches the dependency study exactly.** Every entry in `docs/dependency-studies/iniconfig.md` §2 spot-checks clean against `.venv/Lib/site-packages/iniconfig/` (details in *Verified-good list*). The two items the study left as **unverified** are now **verified**: `__version__ == "2.3.1"` (`iniconfig/_version.py:21`) and the exception name `ParseError` (`iniconfig/exceptions.py:4`, re-exported at `iniconfig/__init__.py:13,18`), whose instances carry `path`/`lineno`/`msg` (`exceptions.py:9-13`).
- **What is actually wrong is the house study's explanation of the value, and three pieces of the pytest config that iniconfig has nothing to do with but that the audit was asked to check** (see F1–F7).

### Proof chain (reproducible)

1. **Single dependent, dev group only** — `uv.lock:322-328` is the `iniconfig` block (`name` at `:323`, `version = "2.3.1"` at `:324`, one pure-Python `py3-none-any` wheel at `:328`); `uv.lock:634-636` lists `{ name = "iniconfig" }` among pytest's dependencies.
2. **Installed version is 2.3.1** — `.venv/Lib/site-packages/iniconfig/_version.py:21` (`__version__ = version = '2.3.1'`), matching `iniconfig-2.3.1.dist-info/`.
3. **pytest's only iniconfig call site is the legacy constructor** — `.venv/Lib/site-packages/_pytest/config/findpaths.py:53` `return iniconfig.IniConfig(str(path))`, wrapped by `:54-55` (`except iniconfig.ParseError as exc: raise UsageError(str(exc))`). `IniConfig.__init__` parses with `strip_inline_comments=False` (`iniconfig/__init__.py:117-119`) — i.e. pytest 9.1.1 does **not** use the new 2.3.x `parse()` default (`iniconfig/__init__.py:132`).
4. **Our config path never touches iniconfig** — `findpaths.py:96-153` is pure `tomllib`; the runtime probe above shows `IniConfig.__init__` is never called.
5. **pytest's strict-config failure carries no line number, on either path** —
   ```
   $ printf '[tool.pytest.ini_options]\nstrict_config = true\nbogus_key = 1\n' > pyproject.toml && pytest --collect-only
   ERROR: Unknown config option: bogus_key
   $ printf '[pytest]\nstrict_config = true\nbogus_key = 1\n' > pytest.ini && pytest --collect-only
   ERROR: Unknown config option: bogus_key
   ```
   (`_pytest/config/__init__.py:1462-1464` builds the message, `:1499-1506` raises it as `UsageError`.) No file, no line — see F1.
6. **TOML, by contrast, *does* point at the line** —
   ```
   $ printf '[tool.pytest.ini_options]\naddopts = "-x"\nbroken = \n' > pyproject.toml && pytest --collect-only
   ERROR: …\pyproject.toml: Invalid value (at line 3, column 10)
   ```
   (`tomllib.TOMLDecodeError` caught at `findpaths.py:103-106`.) The "fail fast with line numbers" capability the study attributes to iniconfig is in fact already provided — by `tomllib`.
7. **`lineof()` is dead code from pytest's perspective** — `grep -rn "lineof" .venv/Lib/site-packages/_pytest/` → **no output**. pytest never calls iniconfig's line-mapping API.

## Findings

### F1 · P2 · The study's headline benefit — "config errors fail fast with line numbers" via iniconfig's `lineof()` — is false for this repo and false for pytest 9.1.1 in general

- **Where:** `docs/dependency-studies/iniconfig.md:78-82` (*"**Config errors fail fast with line numbers.** `strict_config` + iniconfig's `lineof()` means a typo'd pytest key errors at startup naming the file and line"*) and `:71` (*"the cause is usually INI grammar … and `lineof()` pinpoints the source line"*); `.venv/Lib/site-packages/iniconfig/__init__.py:180-182` (`lineof`); `.venv/Lib/site-packages/_pytest/config/findpaths.py:46-55`, `:96-153`; `.venv/Lib/site-packages/_pytest/config/__init__.py:1462-1464`, `:1499-1506`.
- **What:** pytest 9.1.1 **never calls `lineof`** (grep over the whole installed `_pytest/` tree → no hits). The `strict_config` failure message is the bare string `Unknown config option: <key>` — no file name and no line number — and that is true on **both** config paths: the TOML path (`pyproject.toml`, ours) and the iniconfig path (`pytest.ini`). Our repo additionally never reaches the iniconfig path at all (proof-chain step 4), so the capability the study advertises is not merely misattributed — it is absent. The line number we *do* get for a broken config comes from `tomllib` (proof-chain step 6).
- **Evidence:**
  ```
  $ grep -rn "lineof" .venv/Lib/site-packages/_pytest/
  (no output)
  ```
  ```
  .venv/Lib/site-packages/_pytest/config/__init__.py:1462-1464
      def _validate_config_options(self) -> None:
          for key in sorted(self._get_unknown_ini_keys()):
              self._warn_or_fail_if_strict(f"Unknown config option: {key}\n")
  ```
  ```
  .venv/Lib/site-packages/_pytest/config/__init__.py:1499-1506
      def _warn_or_fail_if_strict(self, message: str) -> None:
          strict_config = self.getini("strict_config")
          if strict_config is None:
              strict_config = self.getini("strict")
          if strict_config:
              raise UsageError(message)
          self.issue_config_time_warning(PytestConfigWarning(message), stacklevel=3)
  ```
  Runtime: `ERROR: Unknown config option: bogus_key` for both a `pyproject.toml` and a `pytest.ini` (proof-chain step 5).
- **Fix / opportunity:** documentation only — correct `docs/dependency-studies/iniconfig.md:78-82` and `:71` to state that (a) pytest's `strict_config` reports the *key*, not a location, on either path; (b) the line-numbering we actually get comes from `tomllib`'s `TOMLDecodeError` (`findpaths.py:103-106`), which is why `[tool.pytest.ini_options]` is the right config format for this repo; (c) `lineof()` is an iniconfig API that pytest does not use. Optionally re-attribute the benefit in `docs/reference/dep-test-and-lint-stack.md:27` (which currently says only *"pytest internals + Windows ANSI"* — correct but vague) to `tomllib`. **No code change, no dependency change.**
- **Risk if ignored:** a synthesis agent or contributor reads the study and concludes our config is "validated with line numbers by iniconfig", then adds a `pytest.ini` (thinking that is the "portable" format) — which would *silently* downgrade the config to the legacy INI grammar *and* lose `tomllib`'s line reporting, for a benefit that does not exist. `docs/dependency-studies/iniconfig.md:87-91` already gestures at this ("the same parser semantics apply"), which makes the trap more likely, not less.

### F2 · P2 · The `filterwarnings` module regex in `pyproject.toml` does not match what it claims: the `tests` branch is dead, `hooks` does not exist, and the three top-level app modules are uncovered

- **Where:** `pyproject.toml:95-97` (`filterwarnings = ["error::Warning:^(services|screens|components|core|state|hooks|tests)(\.|$)"]`); `.venv/Lib/site-packages/_pytest/config/__init__.py:2122-2182` (`parse_warning_filter`; the module field is used **verbatim** for ini-sourced filters because `escape=False` — `:2177-2180`, `:2230-2232`), `:2224-2246` (`apply_warning_filters`); `.venv/Lib/site-packages/_pytest/warnings.py:36-47`; CPython `warnings.filterwarnings` (a `str` module is compiled as-is) and `warn_explicit`'s filter test (`mod.match(module)`, where `module` is the `__name__` of the frame that called `warnings.warn`).
- **What:** the rule is meant to escalate *our own* warnings to errors. It matches on module names, and three of its seven alternatives are wrong:
  - `tests` — **never matches**. pytest imports test files as **top-level** modules (`test_ads`, `test_core`, …), not `tests.test_ads`, because `tests/` has no `__init__.py` and pytest's default `prepend` import mode inserts `tests/` on `sys.path`. A warning raised inside a test module is therefore *not* escalated.
  - `hooks` — **no such package**. `ls src/hooks` → *No such file or directory*. The name comes from the sherlock-app layout the repo was ported from (`docs/reference/app-sherlock.md:34`: `src layout {main.py, app_shell.py, core/, state/, services/, components/, screens/, hooks/}`).
  - `app_controller`, `app_shell`, `main` — **not covered**. These are top-level modules under `src/` (`src/app_controller.py`, `src/app_shell.py`, `src/main.py`), so their `__name__` is the bare module name, which the regex (anchored `^` + `(\.|$)`) does not match.
- **Evidence:**
  ```
  $ PYTHONPATH=… .venv/Scripts/python.exe -m pytest -p modnames_plugin --collect-only -q
  MODULE-NAMES:
    tests/test_ads.py           ->  __name__='test_ads'
    tests/test_core.py          ->  __name__='test_core'
    tests/test_flet_api_guard.py->  __name__='test_flet_api_guard'
    … (9 files, all top-level `test_*`)
  ```
  ```
  regex: ^(services|screens|components|core|state|hooks|tests)(\.|$)
    match('core.constants')   -> True
    match('components.ui')    -> True
    match('screens.views')    -> True
    match('services.ad_service') -> True
    match('state.controller_ctx') -> True
    match('app_controller')   -> False
    match('app_shell')        -> False
    match('main')             -> False
    match('test_ads')         -> False
    match('test_core')        -> False
    match('conftest')         -> False
  ```
  The escalation itself works (same script, using `warnings.warn_explicit`): a warning attributed to `core.constants` becomes a `UserWarning` error; one attributed to `test_ads` does not.
  ```
  $ grep -rn "pytest.mark" tests/ --include="*.py"   # no marker usage anywhere
  $ grep -rn "import warnings\|warnings\.warn" src/ tests/ --include="*.py"   # no output
  ```
- **Fix / opportunity:** replace the module field with one that names the modules that actually exist — e.g. `error::Warning:^(app_controller|app_shell|main|components|core|screens|services|state)(\.|$)` — and, if test-module warnings should also be errors, add the pytest module names (`^test_`) or drop the module field entirely and use `error::Warning` with a per-test `@pytest.mark.filterwarnings` opt-out. If the sherlock-style `hooks/` package is ever ported in, add it then. Keep `strict_markers = true` (`pyproject.toml:90`) as-is.
- **Risk if ignored:** the guard silently under-covers. A `DeprecationWarning` raised by our own `app_controller`/`app_shell`/`main`, or by any test module, passes CI unnoticed while the config file reads as if it would be caught. Low severity today (F3: nothing emits such warnings yet), but the guard is false comfort rather than a safety net.

### F3 · P3 · The warning-as-error rule cannot see the app's actual warnings, because the app uses `logging`, not the `warnings` module

- **Where:** `pyproject.toml:95-97`; `src/services/ad_service.py:87`, `:89`, `:93`, `:98`, `:103`, `:117`; `src/services/proot_service.py:411`; `src/components/banner_ad.py:67`, `:70`; `src/components/ui.py:26`; `.venv/Lib/site-packages/_pytest/config/__init__.py:2122-2182`.
- **What:** every "warning" in `src/` is a `logger.warning(...)` call, i.e. a **logging** record. `filterwarnings` only governs the stdlib `warnings` framework (`warnings.warn`, `DeprecationWarning`, `PendingDeprecationWarning`, …). `grep -rn "import warnings\|warnings\.warn" src/ tests/` → **no output**: the app never calls `warnings.warn` anywhere, and `logger.warning` is not affected by any `filterwarnings` rule. Combined with F2, the whole `filterwarnings` line is a **no-op today** — it cannot fail a test, because there is nothing for it to catch.
- **Evidence:** refs above; `src/components/ui.py:26` is only a docstring (*"A warning strip for a failed probe."*); the `logger.warning` call sites are all inside `except` blocks.
- **Fix / opportunity:** decide what the rule is *for*, then make it true. Two coherent options, both config-only:
  1. Keep the stdlib-warnings rule for the rare `DeprecationWarning` class of problem (fix the module regex per F2 and it becomes meaningful the day someone adds a `warnings.warn`), **or**
  2. If the intent was "our own error paths must not be silent", that is a **logging** concern and the right tool is a `caplog`-based test assertion, not `filterwarnings`. Note that `logging` escalation via `-W`/`filterwarnings` is not possible, and pytest's `caplog` fixture would need a new test rather than a config key.
  Either way, **do not** add `logging.captureWarnings`-style plumbing to production code to satisfy a config key.
- **Risk if ignored:** a contributor reads `filterwarnings` as "our warnings fail the build" and assumes the app's failure paths are covered by CI. They are not — and neither the rule nor any test covers them.

### F4 · P3 · CI's pytest invocation doubles `-q`, which silently suppresses the run summary line

- **Where:** `.github/workflows/app.yml:107-108` (`- name: Tests` / `run: uv run pytest -q -m "not live"`); `pyproject.toml:88` (`addopts = ["-ra", "-q"]`); `.venv/Lib/site-packages/_pytest/terminal.py:80-114` (`MoreQuietAction` decrements the verbosity counter on **every** occurrence), `:441-442` (`showheader` → `self.verbosity >= 0`), `:1252-1254` (`summary_stats` returns early `if self.verbosity < -1`).
- **What:** `addopts` already contributes one `-q`, and the CI command adds a second. `-q` is a counting action (`MoreQuietAction.__call__`, `terminal.py:104-114`), so the effective verbosity is **-2**, and at verbosity `< -1` pytest's `summary_stats()` returns immediately — the final `N failed, M passed in Xs` line is never printed. The `-ra` short summary still prints, and the exit code is still correct (1 on failure), so CI still fails properly; only the human-readable tally is lost. (The header was already suppressed by the single `-q` in `addopts`.)
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -m pytest -q -m "not live" 2>&1 | grep -c "passed"
  0                                  # CI-style: verbosity -2, no summary line
  $ .venv/Scripts/python.exe -m pytest -m "not live" 2>&1 | grep -c "passed"
  1                                  # addopts' single -q: verbosity -1, summary line present
  ```
  ```
  $ .venv/Scripts/python.exe -m pytest -q -m "not live" 2>&1 | tail -3
  =========================== short test summary info ============================
  FAILED tests/test_ui_reactive.py::test_license_texts_are_present_and_shipped
  FAILED tests/test_ui_reactive.py::test_licenses_view_carries_real_text - Asse...
  ```
- **Fix / opportunity:** drop the redundant `-q` from the CI step — `uv run pytest -m "not live"` — and let `addopts` own the verbosity. (Or, if CI wants the summary line to be prominent, keep `-q` in CI and remove it from `addopts`; do not keep both.)
- **Risk if ignored:** low. A CI log for a red build shows the failing node IDs but no `N failed, M passed` tally, and a green build's log ends with the last dot — which is exactly the information a reviewer scanning the job summary wants.

### F5 · P3 · `tests/conftest.py` is entirely dead code: `FakePage` and both fixtures are referenced by no test

- **Where:** `tests/conftest.py:10-48` (`class FakePage`), `:51-53` (`fake_page` fixture), `:56-59` (`platform_windows` fixture); `.venv/Lib/site-packages/flet/pytest_plugin.py:1-17` (flet's own pytest plugin, entry point `flet-1.0.4.dist-info/entry_points.txt:4-5`); `docs/reference/app-sherlock.md:34`.
- **What:** the whole conftest is a leftover from the sherlock-app port. `grep -rn "FakePage\|fake_page\|platform_windows" --include="*.py" --include="*.md" .` (excluding `.venv/`) hits **only the definitions themselves** — no test requests either fixture, and nothing instantiates `FakePage`. The house layout note (`docs/reference/app-sherlock.md:34`) describes `tests/{conftest.py(FakePage), flet_tree.py}` and a `hooks/` src package; neither `tests/flet_tree.py` nor `src/hooks/` exists here, so the copied harness was never needed. The `FakePage.run_task` shim (`conftest.py:36-39`) calls `handler(*args, **kwargs)` and returns the result — for an async handler that would create a never-awaited coroutine and emit a `RuntimeWarning`, which (per F2) the `filterwarnings` rule would not catch; moot only because nothing uses it.
- **Evidence:** the grep above; `tests/test_terminal_wiring.py:17-20` shows the house's actual fixture style (a local `MagicMock`-based fixture defined in the test module itself).
- **Fix / opportunity:** delete `tests/conftest.py` (it can be an empty file or removed entirely) **or** start using it. If the intent is a shared page double, note that flet already ships a pytest plugin that auto-loads in every session and provides `flet_app` / `flet_app_function` fixtures (`.venv/Lib/site-packages/flet/pytest_plugin.py:1-17`) — that is the flet audit's call to assess, flagged here only as a pointer so the next agent does not "rebuild" a harness on top of the dead `FakePage`. Do not delete `conftest.py` without checking that no future test wants a shared fixture, and do not keep a 59-line scaffold that nothing uses.
- **Risk if ignored:** low, but it misleads: a new contributor reads `tests/conftest.py`, concludes "the house harness is `FakePage`", and writes tests against a page double that no other test uses and that does not model `ft.Page` (no `add`, no `session`, no `update` semantics, `show_dialog`/`pop_dialog` invented for this repo).

### F6 · P3 · `strict_config` + `strict_markers` should be the single umbrella `strict = true`; the split form leaves two strictness options off

- **Where:** `pyproject.toml:90-91` (`strict_markers = true`, `strict_config = true`); `.venv/Lib/site-packages/_pytest/main.py:97-119` (`strict_config` ini at `:97-104`, `strict_markers` ini at `:105-112`, umbrella `strict` ini at `:113-119`: *"Enables all strictness options, currently: strict_config, strict_markers, strict_xfail, strict_parametrization_ids"*), `.venv/Lib/site-packages/_pytest/config/__init__.py:1499-1504` (`strict_config` falls back to `strict` when unset).
- **What:** pytest 9.1.1 ships a consolidated `strict` ini that enables `strict_config`, `strict_markers`, `strict_xfail` **and** `strict_parametrization_ids`. The repo sets the first two individually, which is the pre-8.1 spelling of the same intent — valid, but it silently omits the other two, and it is the spelling pytest will eventually retire (the per-key inis exist for back-compat, each defaulting to `None` → "fallback to `strict`", `main.py:99-104`, `:109-112`).
- **Evidence:** refs above; both current keys are valid and behave as intended today (`strict_config` is proven live below).
- **Fix / opportunity:** replace `pyproject.toml:90-91` with a single `strict = true`. Zero behaviour change for the current suite (no `xfail` and no strict parametrize-id usage exists), one key instead of two, and it picks up `strict_xfail`/`strict_parametrization_ids` for free.
- **Risk if ignored:** very low. It is a drift risk, not a bug: a future `xfail_strict`-style expectation in a test would not be enforced, and the config would keep using the deprecated spelling.

### F7 · P3 · The `live` marker and CI's `-m "not live"` deselection guard nothing — no test in the repo carries any marker

- **Where:** `pyproject.toml:92-94` (`markers = ["live: hits the real device or network (deselected on desktop CI)"]`); `.github/workflows/app.yml:108` (`-m "not live"`); `.venv/Lib/site-packages/_pytest/mark/__init__.py:126` (`parser.addini("markers", …, "linelist")`).
- **What:** the marker is registered and CI deselects it, but **zero** tests use any marker: `grep -rn "pytest.mark\|mark(" tests/ --include="*.py"` → no output. The deselection therefore filters an empty set, and the "live tests are excluded from desktop CI" safety net exists only as a convention. (Note that `strict_markers = true` does mean that a *future* test using `live` will work, because the marker is registered — so the wiring is correct; only the subject matter is missing.)
- **Evidence:** the greps above; the suite's 55 collected items contain no marker selection (`pytest -v --collect-only` header: `collected 55 items`).
- **Fix / opportunity:** either (a) keep the marker and use it the day a device/network-touching test exists — the registration and the CI filter are already correct and cost nothing, or (b) if the "live" concept is not planned for this repo, drop both `markers` (`pyproject.toml:92-94`) and `-m "not live"` (`app.yml:108`) so the config does not advertise a protection that nothing uses. Do not weaken `strict_markers` to make this simpler.
- **Risk if ignored:** low, but the failure mode is the expensive one: a contributor writes a test that touches the device or the network, forgets the `live` marker, and CI runs it on the runner.

## Missed capabilities (dependency audits only)

**No app use of iniconfig is appropriate** — and this is a conclusion, not a gap. iniconfig is a pytest internal with no runtime role, and the app has no INI-shaped configuration of its own (its only config file is `pyproject.toml`, TOML, read by `tomllib`). For completeness, the capabilities the app does **not** use, with the reason each was declined:

- **`IniConfig.parse(path, …, strip_inline_comments=True, strip_section_whitespace=False)`** · API: `iniconfig/__init__.py:125-178` · Integration point: none · Value: correct 2.3.x comment stripping and Unicode-whitespace-safe section names · Cost: irrelevant — the app parses no INI. **Declined**, and note the trap: **pytest itself does not use this path** — it calls the legacy constructor (`_pytest/config/findpaths.py:53` → `iniconfig/__init__.py:117-119`, `strip_inline_comments=False`), so a `pytest.ini` value such as `addopts = -x  # note` keeps its trailing comment under pytest while `IniConfig.parse()` would strip it. Verified:
  ```
  constructor value: '-x  # trailing comment'
  parse()     value: '-x'
  ```
- **`IniConfig.lineof(section, name)` / `SectionWrapper.lineof(name)`** · API: `iniconfig/__init__.py:180-182` (returns the 1-based source line; verified `2` for a key on line 2), `:32-33` · Integration point: none · Value: "which line did this key come from" for a host-side config linter · Cost: a host tool we do not have. **Declined** — and note it is **not** a pytest feature (no `_pytest/` caller), so it cannot be bought by adding a config key.
- **`ParseError(path, lineno, msg)`** · API: `iniconfig/exceptions.py:4-16` (instance attributes `path`/`lineno`/`msg` set at `:9-13`; `str()` renders `path:lineno: msg` at `:15-16`) · Integration point: a host-side INI validator · Value: precise parse-failure locations · Cost: a tool that does not exist. **Declined** — the equivalent capability for our actual config format is already provided by `tomllib` (`tomllib.TOMLDecodeError` → `findpaths.py:103-106`, which reports `at line 3, column 10`).
- **`SectionWrapper.get(key, default, convert)` typed conversion** · API: `iniconfig/__init__.py:35-71` (overloads `:35-62`, implementation `:65-71`), `IniConfig.get` `:184-237` · Integration point: none · Value: turning raw INI strings into typed values (the mechanism behind pytest's `getini`) · Cost: irrelevant in TOML, where the types are native. **Declined.**
- **`IniConfig.sections` / `__iter__` / `__contains__`** · API: `iniconfig/__init__.py:91`, `:244-246`, `:248-249` · Value: bulk section walking · **Declined** — no INI file to walk.

The one thing this audit *does* recommend taking from the study's idea is already taken, by a different library: **config errors that name the file and line**. Our config format provides that today (`tomllib`), so there is nothing to add.

## Verified-good list

- **The dependency study's API inventory is accurate — every claim spot-checks clean against the installed 2.3.1.** `IniConfig.parse` signature and body (`iniconfig/__init__.py:125-178`), `IniConfig.__init__` (`:94-123`), `IniConfig.get` overloads (`:184-237`), `IniConfig.lineof` (`:180-182`), `IniConfig.__getitem__`/`__iter__`/`__contains__` (`:239-249`), `SectionWrapper` (`:24-86`: `lineof` `:32-33`, `get` overloads `:35-71`, `__getitem__` `:73-74`, `__iter__` `:76-82`, `items` `:84-86`), `ParsedLine` fields (`_parse.py:11-15`: `lineno, section, name, value`), `parse_ini_data` (`:18-65`), `parse_lines` (`:68-96`), `_parseline` (`:99-155`), `iscommentline` (`:158-160`), `COMMENTCHARS = "#;"` (`:7`). The study's `__init__.py:126` / `:180` / `:185-222` / `:239` / `:244` / `:248` and `_parse.py:11,18,68,99,158` line anchors are all correct.
- **The study's two "unverified" items are now verified:** `__version__ == "2.3.1"` (`iniconfig/_version.py:21`) and the exception name `ParseError` (`iniconfig/exceptions.py:4`; exported at `iniconfig/__init__.py:13,18`). The study's `__all__` surface matches: `["COMMENTCHARS", "IniConfig", "ParseError", "iscommentline"]` (`iniconfig/__init__.py:13`).
- **The study's statement that `[tool.pytest.ini_options]` is read natively as TOML is correct** (`_pytest/config/findpaths.py:96-153`), and so is its statement that the `[tool.pytest]` vs `[tool.pytest.ini_options]` mutual-exclusion rule lives in pytest (`findpaths.py:129-135`) — **not** in iniconfig. Our repo uses only the `ini_options` form, so no `UsageError` is possible.
- **The study's statement that iniconfig has no options surface of its own is correct** — nothing in `iniconfig/` reads an environment variable or a config file; the only inputs are `path`, `data`, `encoding` (`iniconfig/__init__.py:94-102`, `:126-134`).
- **The study's "typed ini access without hand-rolled parsing" point is sound but inapplicable here** — the app parses no INI (see *Missed capabilities*).
- **iniconfig is genuinely dev-only and cannot reach the APK.** Its only dependent is pytest (`uv.lock:636`), pytest is dev-group only (`pyproject.toml:77-84`), `[project].dependencies` (`pyproject.toml:9-15`) contains neither, and the app's in-app license list (`src/screens/views.py:26-42`) correctly omits it.
- **The APK/AAB prune guard cannot miss iniconfig, even though its regex does not name it.** The regex is `pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/` (`.github/workflows/app.yml:168`, `:282`) and does **not** match `iniconfig/` — but iniconfig is only reachable through pytest, and the regex's `pytest/` substring matches pytest's `_pytest/` package directory. Verified: `echo "_pytest/" | grep -qE 'pytest/'` → match; `echo "iniconfig/" | grep -qE '…'` → no match. So a bundled pytest is caught, and iniconfig cannot exist without it.
- **`[tool.pytest.ini_options]` is valid for the installed pytest 9.1.1** — every key resolves: `pythonpath` (`_pytest/config/__init__.py:1550`, *paths* type; inserted at `sys.path[0]` at `:1373-1378`), `addopts` (`:1547`, *args* type), `timeout` / `timeout_method` / `timeout_func_only` (`pytest_timeout.py:99-101`), `strict_markers` (`_pytest/main.py:105-112`), `strict_config` (`:97-104`), `markers` (`_pytest/mark/__init__.py:126`, *linelist*), `filterwarnings` (`_pytest/main.py:137-143`, *linelist*). No unknown-key error is raised, and the run header confirms the effective config: `rootdir: …\proot-distro-flet`, `configfile: pyproject.toml`, `plugins: anyio-4.15.1, flet-1.0.4, timeout-2.4.0`, `timeout: 60.0s`.
- **`strict_config = true` is doing real work.** It is what makes a missing plugin fail loudly instead of silently: with pytest-timeout disabled, the `timeout` key becomes unknown and the session dies with `ERROR: Unknown config option: timeout` (verified with `pytest -p no:timeout --collect-only`). That is the intended behaviour for a key owned by a plugin.
- **`timeout = 60` is honoured** — the header prints `timeout: 60.0s`. Note the method is platform-dependent by design: `DEFAULT_METHOD = "signal"` where `SIGALRM` exists, else `"thread"` (`pytest_timeout.py:26-30`), so the Windows laptop runs `thread` and the Linux CI runs `signal`. The house note (`docs/reference/dep-test-and-lint-stack.md:13`) recommends pinning `timeout_method = "thread"` "for a Windows+Linux CI matrix" — that matrix does not exist here (all four CI jobs are `ubuntu-latest`, `.github/workflows/app.yml:41`, `:112`, `:131`, `:185`), so the recommendation's premise is unmet; pinning is optional, not a defect. Recorded here so the synthesis does not re-open it.
- **`pythonpath = ["src"]` is the mechanism that makes the app importable in tests** — e.g. `from services.session_manager import SessionEntry` (`tests/test_terminal_wiring.py:14`) and `from core.constants import …` (`app.yml:67`). Verified working: the suite imports `core.*`, `services.*`, `screens.*` successfully.
- **The `test_imports_vs_deps.py` guard needs no change for iniconfig** — it scans `src/` only (`tests/test_imports_vs_deps.py:52`) and `src/` imports nothing from iniconfig (grep → no output).
- **Plugin autoload is on and the plugin set is small and benign** — `anyio`, `flet`, `pytest-timeout` (header line above). `flet`'s plugin (`.venv/Lib/site-packages/flet/pytest_plugin.py:1-17`) is deliberately lightweight and degrades to a no-op without `pytest_asyncio`.

## Unverified

- **The real APK/AAB was not built in this audit** (no Flutter/Android SDK run). The "iniconfig never reaches the APK" conclusion is a resolver-level proof (iniconfig's only dependent is dev-group pytest, and `[project].dependencies` is the Android resolve's input — same mechanism the msgpack audit proved for `flet_cli/commands/build_base.py:2563-2619`), not an on-device `unzip -l` observation.
- **The two failing tests in this checkout are a working-tree artifact, not a defect under audit.** `tests/test_ui_reactive.py:175` (`test_license_texts_are_present_and_shipped`) and `:200` (`test_licenses_view_carries_real_text`) fail because `LICENSES/` and `src/LICENSES/` are **deleted from the working tree** in this checkout (`git status --short` → ` D LICENSES/…`, ` D src/LICENSES/…`) while present in git HEAD. This is the same harness artifact the msgpack and colorama audits recorded. Out of scope here (not an iniconfig or pytest-config matter), and no CI claim should be drawn from the local run.
- **`src/LICENSES/`, `LICENSES/`, `docs/roadmap.md`, `docs/testing-findings.md`, `generate_third_party_sources.py` and `check_elf_alignment.py`** are deleted from the worktree in this checkout but present in git HEAD; I did not read them (they are outside this assignment) and made no claim about their contents.
- **The Linux CI behaviour was not executed here** — the timeout-method difference (`signal` vs `thread`) and the `-q`-doubling effect were derived from the installed pytest/pytest-timeout source and reproduced on Windows; the CI runner is `ubuntu-latest` (`app.yml:41`).
- **Whether the `hooks/` package is planned** (per `docs/reference/app-sherlock.md:34`) is UNVERIFIED — it does not exist in `src/` today, and `docs/roadmap.md` (git HEAD, not read here) was not consulted.
- **flet's own `flet_app` / `flet_app_function` fixtures** (`.venv/Lib/site-packages/flet/pytest_plugin.py`) were noted but **not** assessed for suitability — that belongs to the flet audit, and F5 deliberately does not recommend adopting or deleting them.
