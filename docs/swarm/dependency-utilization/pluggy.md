# pluggy 1.7.0 — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/pluggy.md`; `docs/dependency-studies/INDEX.md:45`; `docs/reference/dep-test-and-lint-stack.md`; `docs/decisions.md:12-14` (D-003), `:49` (D-015); `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `tests/conftest.py`; `tests/` (all 10 `.py` files); `src/` (all 30 `.py` files); `.venv/Lib/site-packages/pluggy/` (all 12 modules); `.venv/Lib/site-packages/pluggy-1.7.0.dist-info/METADATA`; `.venv/Lib/site-packages/_pytest/config/__init__.py`; `.venv/Lib/site-packages/_pytest/hookspec.py`; `.venv/Lib/site-packages/_pytest/main.py`; `.venv/Lib/site-packages/_pytest/runner.py`; `.venv/Lib/site-packages/pytest_timeout.py`; `.venv/Lib/site-packages/flet/pytest_plugin.py`; `docs/swarm/dependency-utilization/iniconfig.md` (sibling, overlap noted in F1) · **Date:** 2026-10-20

## What it does / how the app uses it

**The app does not use pluggy, and no app use of pluggy is appropriate. The study's headline verdict — "don't adopt directly" — is CORRECT and survives contact with the current codebase.**

- **pluggy is dev-only, transitive, and provably cannot reach the APK.** It is required by exactly one package, **pytest** (`uv.lock:638` `{ name = "pluggy" }` inside the `pytest` dependency list at `uv.lock:634-640`; the `pluggy` block itself is `uv.lock:565-571`). pytest is a **dev-group** dependency only (`pyproject.toml:77-84`, `pytest>=9.1.1` at `pyproject.toml:81`; `uv.lock:612-619` `[package.metadata.requires-dev]`). The runtime resolve — `uv.lock:603-610` `[package.metadata] requires-dist` — lists only `flet`, `flet-ads`, `flet-terminal`, `httpx`, `proot-distro`; **no pytest, no pluggy**. `flet build` resolves only `requires-dist`, and the house's own guard enforces that boundary for imports (`tests/test_imports_vs_deps.py:46-59`).
- **Nothing in the repo imports it.** `grep -rn "pluggy" src/ tests/ pyproject.toml .github/` → **no output**. The only mentions in the repo are `docs/dependency-studies/pluggy.md`, `docs/dependency-studies/pytest.md:172,293`, `docs/reference/dep-test-and-lint-stack.md:27-28`, `docs/dependency-studies/INDEX.md:45` and this report.
- **The repo needs no plugin/hook architecture, and has none.** `tests/conftest.py` is 59 lines: a `FakePage` stand-in (`:10-48`) plus two plain fixtures (`fake_page` `:51-53`, `platform_windows` `:56-59`) — no `@pytest.hookimpl`, no `@pytest.hookspec`, no `pytest_addoption`, no `pytest_configure`, no `pytest_collection_modifyitems` anywhere (`grep -rn "hookimpl\|hookspec\|pytest_addoption\|pytest_configure\|pytest_collection_modifyitems" src/ tests/` → no output). There is **no `pytest11` entry point** in `pyproject.toml` (no `[project.entry-points]` section) and **no second `conftest.py`** in the tree (`find . -name conftest.py -not -path "./.venv/*"` → `./tests/conftest.py` only). The app's own composition is explicit, not a registry: `src/state/controller_ctx.py:23-58` is a fixed dataclass of `Callable`s and `src/core/shared_services.py:23-29` is a fixed tuple of service specs — pluggy is not a candidate for either.
- **But pluggy is very much alive at test time**, and it is the machinery under every test the house runs: **38 distinct pluggy hooks are dispatched in a single `pytest` run** of this repo (measured, see F3 evidence), and pytest's own manager is a pluggy `PluginManager` subclass (`.venv/Lib/site-packages/_pytest/config/__init__.py:42-46` imports `HookimplMarker`, `HookimplOpts`, `HookspecMarker`, `HookspecOpts`, `PluginManager`; `:460` `class PytestPluginManager(PluginManager)`).
- **Every API claim in the dependency study spot-checks clean against the installed source** (full table in *Verified-good list*). The two items the study left **unverified** are now **resolved** — one in the study's favour, one against it (F2, F3).
- **The study's §7 framing is wrong in kind** (F4): it argues pluggy "makes our app significantly better than Termux's proot-distro", but pluggy is a test-time library that cannot enter the shipped artifact at all. The comparison belongs to the *test suite*, not the *app*.

### Proof chain (reproducible)

1. **Installed identity** — `.venv/Lib/site-packages/pluggy-1.7.0.dist-info/METADATA:2-3` (`Name: pluggy` / `Version: 1.7.0`); `pluggy.__version__ == "1.7.0"` (live) via the lazy `__getattr__` at `pluggy/__init__.py:32-36`.
2. **Single dependent, dev group only** — `uv.lock:638`; `uv.lock:603-610` vs `uv.lock:612-619`.
3. **No app/test import** — grep over `src/`, `tests/`, `pyproject.toml`, `.github/` → no output.
4. **No plugin surface** — `tests/conftest.py` (59 lines, fixtures only); no `pytest11` entry point; no `hookimpl`/`hookspec` in the repo.
5. **Legacy old-style hookwrapper is LIVE in pluggy 1.7.0** — dispatched at `pluggy/_execution.py:121-127`, implemented at `pluggy/_execution.py:27-64`. Measured **138 legacy-wrapper invocations in one `pytest -q` run** of this repo (probe below). The house's only timeout guard rides on it.
6. **`check_pending`'s raise type** — the study left it unverified; it is `PluginValidationError` (`pluggy/_manager.py:494-497`), and pytest calls it at `_pytest/main.py:871`.

## Findings

### F1 · P2 · `timeout_method` is unpinned, so a hung test hard-kills the owner's entire local pytest process while CI fails exactly one test and continues

- **Where:** `pyproject.toml:86-97` — `[tool.pytest.ini_options]` sets `timeout = 60` (`:89`) and **no** `timeout_method`; `.github/workflows/app.yml:41,112,131,185` — every job is `runs-on: ubuntu-latest`; `.venv/Lib/site-packages/pytest_timeout.py:26-30` (`HAVE_SIGALRM = hasattr(signal, "SIGALRM")` → `DEFAULT_METHOD = "signal"` on Linux, `"thread"` elsewhere), `:26-30` is the platform switch; `:306-311` (`signal` → `thread` fallback), `:485-503` (`timeout_sigalrm` → `pytest.fail(...)`), `:505-542` (`timeout_timer` → `os._exit(1)` at `:542`). House doc already prescribes the fix: `docs/reference/dep-test-and-lint-stack.md:13` — *"**Method default is platform-dependent** … For a Windows+Linux CI matrix, pin **`timeout_method = "thread"`** for uniform behavior (house style uses `timeout = 60`)."*
- **What:** The repo's dev environment is Windows (BRIEF: `.venv/Lib/site-packages/`, Python 3.14.7) and CI is Linux-only. With `timeout_method` unset, the **same hung test behaves differently in the two places**:
  - **CI (Linux, `signal`):** `timeout_sigalrm` dumps stacks and calls `pytest.fail(...)` (`pytest_timeout.py:485-503`) → **one test fails, the rest of the suite still runs**, and the run produces a normal summary.
  - **Local Windows (`thread`):** `timeout_timer` dumps stacks and calls **`os._exit(1)`** (`pytest_timeout.py:505-542`) → **the whole pytest process is killed instantly**: no failure summary, no remaining tests executed, no coverage, exit code indistinguishable from a crash.
  The house doc's "Windows+Linux CI matrix" premise does not hold today (Linux-only CI), so the divergence is **local-vs-CI**, not CI-vs-CI — but the local side is the owner's, and the local side is the one that hard-kills.
- **Evidence:**
  ```
  $ grep -n "timeout" pyproject.toml
  89:timeout = 60          # <-- no timeout_method
  $ grep -n "runs-on" .github/workflows/app.yml
  41:    runs-on: ubuntu-latest
  112:    runs-on: ubuntu-latest
  131:    runs-on: ubuntu-latest
  185:    runs-on: ubuntu-latest
  ```
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  26:HAVE_SIGALRM = hasattr(signal, "SIGALRM")
  27:if HAVE_SIGALRM:
  28:    DEFAULT_METHOD = "signal"
  30:    DEFAULT_METHOD = "thread"
  ...
  505:def timeout_timer(item, settings):
  506:    """Dump stack of threads and call os._exit().
  ...
  542:        os._exit(1)
  ```
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  485:def timeout_sigalrm(item, settings):
  ...
  503:    pytest.fail(PYTEST_FAILURE_MESSAGE % settings.timeout)
  ```
- **Fix / opportunity:** add `timeout_method = "thread"` to `[tool.pytest.ini_options]` (`pyproject.toml:86-97`), exactly as `docs/reference/dep-test-and-lint-stack.md:13` already prescribes. `thread` is the only method that behaves identically on Windows and Linux, so one pinned value removes the platform branch entirely. (Note for the synthesis: the *option* is pytest-timeout's; the audit that owns that package should carry the fix. It is surfaced here because the enforcement path runs through pluggy's hook dispatch — see F2 — and because the house's own reference doc already prescribes it, so this is a doc-vs-pyproject drift, not a new proposal.)
- **Risk if ignored:** on the owner's Windows machine a single hanging test destroys the entire test run's output; the resulting signal ("pytest crashed, no summary") is materially worse than CI's ("one test failed, here is the stack"), and it can mask the real culprit behind dozens of never-run tests.

### F2 · P3 · The study's "legacy `hookwrapper` … unverified — do not rely on it" is disproved: pluggy 1.7.0 still executes it, and the house already depends on it transitively for its only timeout guard

- **Where:** `docs/dependency-studies/pluggy.md:100-103` (*"`hookwrapper=False` — **legacy** wrapper impl (old `yield`-dict protocol). Still present as a parameter on `pytest.hookimpl` in 9.1.1 … Whether the legacy protocol still executes in pluggy 1.7.0 is **unverified** — do not rely on it."*); `.venv/Lib/site-packages/pluggy/_execution.py:121-127` (dispatch), `:27-64` (`run_old_style_hookwrapper`), `:77-86` (`_warn_teardown_exception` → `warnings.warn(PluggyTeardownRaisedWarning(msg), stacklevel=6)`); `.venv/Lib/site-packages/pytest_timeout.py:178-179` (`@pytest.hookimpl(hookwrapper=True)` on `pytest_runtest_protocol`), `:202-203` (same on `pytest_runtest_call`), `:135-137` (`pytest_addhooks` → `pluginmanager.add_hookspecs(TimeoutHooks)`), `:111-131` (`TimeoutHooks` with two `firstresult=True` hookspecs at `:114` and `:124`).
- **What:** The legacy old-style wrapper protocol **is fully executed in pluggy 1.7.0** — the branch is live in `_multicall`, the generator is driven to its second `send`, and the teardown-exception path even emits the documented `PluggyTeardownRaisedWarning`. The house's **only** timeout enforcement (`timeout = 60`, `pyproject.toml:89`) is implemented by pytest-timeout as two **legacy** hookwrapper impls, so the 60 s guard is itself riding on the protocol the study says not to rely on. Nothing in the repo tests that the guard still fires.
- **Evidence:** runtime probe (throwaway plugin outside the repo, `PYTHONPATH`/`PYTEST_PLUGINS`, repo untouched):
  ```
  PROBE_OLD_STYLE_HOOKWRAPPER_CALLS= 138
  ```
  (a `run_old_style_hookwrapper` wrapper counted **138** invocations during one `pytest -q` run of this repo — i.e. pytest-timeout's two legacy impls, once per test, plus pytest's own legacy impls.)
  ```
  $ PYTHONPATH=/tmp/pluggyprobe PYTEST_PLUGINS=teardown_raise_plugin \
      .venv/Scripts/python.exe -m pytest -q tests/test_core.py
  ...
  _pytest/runner.py:250: PluggyTeardownRaisedWarning: A plugin raised an exception during an old-style hookwrapper teardown.
  Plugin: teardown_raise_plugin, Hook: pytest_runtest_call
  RuntimeError: boom in legacy hookwrapper teardown
  ...
  FAILED tests/test_core.py::test_grp_shim_shapes - RuntimeError: bo...
  ```
  The warning is emitted **and** the exception propagates — both legacy behaviours are live.
- **Fix / opportunity:** replace the study's *"unverified — do not rely on it"* with the verified statement: *legacy `hookwrapper=True` still executes in pluggy 1.7.0 (`_execution.py:121-127`), and pytest-timeout 2.4.0 — the house's only timeout guard — depends on it.* Then close the actual exposure the study was gesturing at: add **one** test that asserts a deliberately-hanging test is killed by the timeout (or asserts `pluginmanager.hook.pytest_timeout_set_timer` resolves), so a future pluggy that drops legacy support fails loudly instead of silently losing the 60 s guard. Keep it a plain pytest test — no `PluginManager` instantiation.
- **Risk if ignored:** the house's only runaway-test guard is an unasserted, deprecated-by-the-study dependency on a legacy protocol; if it ever stops working, every CI run could hang indefinitely with no test noticing.

### F3 · P3 · `pytest --debug` is the house's free pluggy hook tracer, but it drops a 7 743-line `pytestdebug.log` into the repo root and `.gitignore` does not cover it

- **Where:** `.venv/Lib/site-packages/_pytest/config/__init__.py:514` (`self.enable_tracing()` on the debug path) → `.venv/Lib/site-packages/pluggy/_manager.py:607-630` (`PluginManager.enable_tracing()` → `add_hookcall_monitoring(before, after)`, `:570-605`); `.venv/Lib/site-packages/_pytest/helpconfig.py:141` (same call for `--debug`); repo `.gitignore` (no `pytestdebug.log` entry).
- **What:** pluggy's tracing capability is fully reachable **through pytest, with no new dependency and no code change** — `pytest --debug` writes a complete hook-dispatch transcript. It is the answer to "why did my fixture/plugin/conftest not run", which is exactly the class of bug the study's §7.2 advertises. The cost is an untracked 7 743-line file written into the **current working directory** (the repo root), which `.gitignore` does not exclude → it shows up as `?? pytestdebug.log` in `git status` and can be committed by accident.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -m pytest --debug
  writing pytest debug information to pytestdebug.log
  ...
  wrote pytest debug information to pytestdebug.log
  $ wc -l pytestdebug.log
  7743 pytestdebug.log
  $ grep -oE "^ *[a-z_]+ \[hook\]" pytestdebug.log | sed 's/\[hook\]//' | tr -d ' ' | sort -u | wc -l
  38
  ```
  The 38 distinct hooks dispatched in one run include `pytest_collection`, `pytest_collection_modifyitems`, `pytest_fixture_setup`, `pytest_fixture_post_finalizer`, `pytest_runtest_call`, `pytest_runtest_logfinish`, `pytest_report_teststatus`, `pytest_plugin_registered` — i.e. the whole lifecycle the study describes in §5.
  ```
  $ git status --porcelain
  ?? pytestdebug.log
  ```
- **Fix / opportunity:** add `pytestdebug.log` to `.gitignore` (one line, same block as `.pytest_cache`/`.ruff_cache` hygiene), and note `pytest --debug` in the house test-and-lint reference (`docs/reference/dep-test-and-lint-stack.md`) as the hook-dispatch diagnostic. No pluggy adoption involved — pytest already exposes it.
- **Risk if ignored:** a 7 743-line diagnostic dump is one `git add .` away from being committed to a public repo (D-007: *"Repository is PUBLIC"*).

### F4 · P3 · The study's §7 claim that pluggy "makes our app significantly better than Termux's proot-distro" is a category error: pluggy is a test-time library that provably cannot enter the shipped app

- **Where:** `docs/dependency-studies/pluggy.md:206-224` (esp. `:208` *"pluggy is indirect (via pytest) but its properties shape our quality story"*, `:214-215` *"Our CI gains capabilities by **installing a package**"*, `:220` *"Termux failures are debugged by reading someone's shell history"*); `uv.lock:603-610` (`requires-dist` — no pluggy); `uv.lock:612-619` (`requires-dev` — pytest); `pyproject.toml:9-15` (runtime deps); `tests/test_imports_vs_deps.py:46-59` (the guard that keeps undeclared imports out of the APK).
- **What:** Every one of §7's three claims is about the **test/CI pipeline**, not the app. §7.1 ("plugin composition without forks") is a property of *pytest's* plugin ecosystem, not of this app — pluggy contributes nothing to the APK, the proot container, the Flet UI, or the update path. §7.3 ("contract for shared test tooling") describes a *hypothetical future house plugin* that does not exist (no `pytest11` entry point, no `conftest.py` hooks). The claim as written ("**our app** significantly better") overstates by one full layer, and the Termux comparison is unfair on its face: Termux's shell tooling was never a pytest peer.
- **Evidence:**
  ```
  $ grep -n -A 8 "^\[package.metadata\]" uv.lock
  603:[package.metadata]
  604-requires-dist = [
  605-    { name = "flet", specifier = ">=1.0.4" },
  606-    { name = "flet-ads", specifier = ">=1.0.4" },
  607-    { name = "flet-terminal", specifier = ">=0.4.0" },
  608-    { name = "httpx", specifier = ">=0.28.1" },
  609-    { name = "proot-distro", specifier = ">=5.10.0" },
  610-]
  ```
  ```
  $ grep -rn "pluggy" src/ tests/ pyproject.toml .github/
  (no output)
  ```
- **Fix / opportunity:** re-title §7 to *"What this dependency contributes to our test pipeline"* and re-scope all three points to CI/test concerns; drop the Termux comparison or restate it as "our CI is extensible by installing a package, unlike a shell-script toolchain". Also add one line the study omits: pluggy **cannot** reach the APK, because `requires-dist` (the set `flet build` resolves) excludes it and `tests/test_imports_vs_deps.py:46-59` fails the build on any undeclared `src/` import.
- **Risk if ignored:** the study is the artifact future agents and the owner consult before touching the dependency set. A claim that a dev-only library "makes the app significantly better" invites exactly the kind of expansion D-003 (`docs/decisions.md:12-14`) exists to prevent.

## Missed capabilities (dependency audits only)

- **Hook-dispatch tracing via pytest — `pytest --debug` → `PluginManager.enable_tracing()`** (`pluggy/_manager.py:607-630`, reached at `_pytest/config/__init__.py:514` and `_pytest/helpconfig.py:141`). *Integration point:* a line in `docs/reference/dep-test-and-lint-stack.md` next to the existing pytest/pytest-timeout notes, plus `pytestdebug.log` in `.gitignore` (F3). *Value vs cost:* medium value (it is the only way to see which plugin actually ran a hook — the exact class of confusion F2 warns about), near-zero cost (no code, no dependency). Measured output: 38 distinct hooks, 7 743 lines, one run.
- **`PluginManager.check_pending()` — spec/impl contract enforcement** (`pluggy/_manager.py:481-497`; raises `PluginValidationError` at `:494-497`; pytest calls it at `_pytest/main.py:871`). *Integration point:* nothing to build — it is already on. *Value vs cost:* this is the mechanism behind the study's §7.3 claim; it is worth a sentence in the study saying **"already active for free"** rather than describing it as a future benefit. *Value vs cost:* zero cost, zero value today (no plugins registered) — document, do not build.
- **`pytest_collection_modifyitems` hookimpl — enforcing the house's inert `live` marker** (hookspec at `_pytest/hookspec.py:268`). *Integration point:* `tests/conftest.py` (the natural home; the house already keeps all shared fixtures there). *Value vs cost:* this is the **mechanism** for the sibling finding in `docs/swarm/dependency-utilization/iniconfig.md` F7 (`:160-165`) — the `live` marker is declared (`pyproject.toml:92-94`) and CI deselects it (`app.yml:108`), but **no test in the repo carries any marker** (`grep -rn "pytest.mark" tests/` → no output), so the deselection guards nothing today. A ~10-line `pytest_collection_modifyitems` hookimpl in `conftest.py` could fail the run when a network/device-touching test is *not* marked `live`. *Value vs cost:* medium value **when** the first live test lands (today: none); low cost; and it must be consumed **through pytest** (a plain hookimpl in `conftest.py`) — never by instantiating `PluginManager`, per the study's §6 and BRIEF rule 4. **Overlap warning for the synthesis:** the *gap* is already reported by the iniconfig audit; this entry only supplies the pluggy-backed enforcement option.
- **Explicitly NOT worth adopting** (the study's §6 conclusion, re-verified against the current app): `HookspecMarker`/`HookimplMarker`/`PluginManager` for app or test code. `tests/conftest.py` (59 lines, `FakePage` + 2 fixtures) already covers every house need; `src/state/controller_ctx.py:23-58` and `src/core/shared_services.py:23-29` are explicit, not registries; and D-003 (`docs/decisions.md:12-14`) freezes the dependency set — pluggy is not even a *declared* dependency, it is a transitive one, so "adopting" it would mean promoting a test-time transitive into a direct dependency for no gain.

## Verified-good list

- **Every line number in the study's §2 `PluginManager` table is exact** for the installed 1.7.0: `__init__` `:158`, `_hookexec` `:174`, `register` `:185`, `parse_hookimpl_opts` `:258`, `unregister` `:281`, `set_blocked` `:325`, `is_blocked` `:330`, `unblock` `:334`, `add_hookspecs` `:344`, `parse_hookspec_opts` `:370`, `get_plugins` `:396`, `is_registered` `:400`, `get_canonical_name` `:404`, `get_plugin` `:415`, `has_plugin` `:419`, `get_name` `:423`, `_verify_hook` `:431`, `check_pending` `:481`, `load_setuptools_entrypoints` `:497`, `list_plugin_distinfo` `:527`, `list_plugin_distributions` `:541`, `list_name_plugin` `:551`, `get_hookcallers` `:555`, `add_hookcall_monitoring` `:570`, `traced_hookexec` `:587`, `undo` `:602`, `enable_tracing` `:607`, `subset_hook_caller` `:632` — all confirmed by `grep -n` over `pluggy/_manager.py` (652 lines).
- **`PluginValidationError` is at `pluggy/_manager.py:128` with `(plugin, message)` at `:135-140`** — the study's §2/§4.4 claim is exact.
- **`pluggy/__init__.py:1-16` `__all__` matches the study §1 verbatim**; `__version__` is a lazy `__getattr__` at `:32-36` (`importlib.metadata.version("pluggy")`), so the study's "no static attribute" note is correct.
- **`HookspecOpts` / `HookimplOpts` are exactly as documented** at `pluggy/_config.py:11-24` and `:27-45` (`firstresult`, `historic`, `warn_on_impl`, `warn_on_impl_args`; `wrapper`, `hookwrapper`, `optionalhook`, `tryfirst`, `trylast`, `specname`).
- **`Result` methods match the study §4.3** at `pluggy/_result.py`: `get_result` `:91-103`, `force_result` `:67-78`, `force_exception` `:80-89`, `from_call` `:56-65`, `exception` property `:51-54`, `excinfo` property `:42-49`; `HookCallError` at `:20-21`. (One nit: the study lists `excinfo` among "internals"; it is a **public** property, same class as `exception`.)
- **`HookCaller` surface matches the study §4.1** at `pluggy/_caller.py`: `has_spec` `:94`, `set_specification` `:98`, `is_historic` `:112`, `get_hookimpls` `:123`, `__call__` `:181`, `call_historic` `:201`, `call_extra` `:229`; `HookRelay` at `:33-54`; `HookImpl` at `pluggy/_impl.py:26`.
- **The study's §3.3 pytest aliases are exact** — live `inspect.signature`: `pytest.hookimpl(function=None, hookwrapper=False, optionalhook=False, tryfirst=False, trylast=False, specname=None, wrapper=False)`, `pytest.hookspec(function=None, firstresult=False, historic=False, warn_on_impl=None, warn_on_impl_args=None)`; `isinstance(pytest.hookimpl, pluggy.HookimplMarker)` → `True`; `isinstance(pytest.hookspec, pluggy.HookspecMarker)` → `True`.
- **The study's §8 pytest-integration refs are exact**: `_pytest/config/__init__.py:907` (`self.load_setuptools_entrypoints("pytest11", name=modname)`), `:1364` (`ep.group == "pytest11"` scan), `:1583` (`self.pluginmanager.load_setuptools_entrypoints("pytest11")`).
- **`_verify_hook` enforces the arg-subset contract as the study claims** (`pluggy/_manager.py:444-454`, `PluginValidationError` at `:448`).
- **The study's "don't adopt pluggy for app/test code" verdict (§6) is correct** and confirmed against the current app: `tests/conftest.py` is 59 lines of plain fixtures; the repo has no `pytest11` entry point, no `hookimpl`/`hookspec`, and no second `conftest.py`; the app's service composition (`src/core/shared_services.py:23-29`, `src/state/controller_ctx.py:23-58`) is explicit, not a registry.
- **The house's `filterwarnings` escalation cannot be accidentally tripped by pluggy.** `pyproject.toml:96` filters `error::Warning:^(services|screens|components|core|state|hooks|tests)(\.|$)`; pluggy's own teardown warning is issued with `stacklevel=6` (`pluggy/_execution.py:86`) and pytest attributes it to `_pytest/runner.py:250` (see F2 evidence) — outside the house's module prefixes, so it is reported as a warning, not escalated. Conversely the house's app-module warnings are unaffected by pluggy. (Note: the `hooks` prefix in that regex matches **no** module in `src/` — the repo has no `src/hooks/`; "hooks" here means Flet `on_change` callbacks, e.g. `src/app_shell.py:47`, `src/screens/views.py:89`.)
- **pluggy cannot reach the APK, and the repo enforces that**: `uv.lock:603-610` (`requires-dist` excludes pytest/pluggy) plus the guard `tests/test_imports_vs_deps.py:46-59`, which fails the build on any `src/` import that is not a declared runtime dependency.
- **The house's `live` marker / CI deselection pair is currently inert** — `pyproject.toml:92-94` declares the marker, `.github/workflows/app.yml:108` runs `uv run pytest -q -m "not live"`, but no test carries any marker. **Already reported** as `iniconfig.md` F7 (`:160-165`); listed here only to record the pluggy-side enforcement mechanism, not as a new finding.

## Unverified

- **The pre-existing test-suite failures are not pluggy-related and were not diagnosed** (out of scope). `pytest -q` currently fails 2 tests in `tests/test_ui_reactive.py` — `test_license_texts_are_present_and_shipped` (`:182`, asserts `src/LICENSES` exists) and `test_licenses_view_carries_real_text` (`:206`) — because `src/LICENSES/` and `LICENSES/` are **deleted in the working tree** (`git status --porcelain` shows ` D src/LICENSES/*.txt`, ` D LICENSES/*.txt`, ` D docs/compliance/…`, ` D docs/testing-findings.md`, ` D check_elf_alignment.py`). That deletion predates this audit (it was already present before the first command of this session) and is **not** caused by anything pluggy does. I did not restore or diagnose it (rule 1: read-only apart from this report). Whether the swarm should treat it as a broken worktree is a coordination question for the orchestrator.
- **`pluggy.PluginManager.list_plugin_distributions` signature** — the study (§2) marks it unverified; it exists at `pluggy/_manager.py:541` but I did not re-derive its exact parameter list, and nothing in this repo calls it. Irrelevant to the verdict.
- **`Hookimpl.hookwrapper` / `wrapper` deprecation timeline** — pluggy 1.7.0 still executes both protocols (verified), but *when* upstream removes the legacy one is upstream's roadmap, not this repo's concern; I did not check pluggy's changelog.
- **Whether the house will ever ship a reusable pytest plugin across repos** (the study §6 "one legitimate use") — no such artifact exists in this repo today (`grep -rn "entry-points\|pytest11" pyproject.toml` → no output), and the decision is the owner's; the audit can only state that the mechanism would be pluggy-through-pytest, never a direct `PluginManager`.
- **`pytest --debug`'s output path on non-Windows** — the file is written into `cwd` via `_pytest/helpconfig.py:135-148`; I only observed the Windows behaviour.
