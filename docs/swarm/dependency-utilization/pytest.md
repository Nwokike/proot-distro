# pytest 9.1.1 — utilization & test-suite audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `pyproject.toml` `[tool.pytest.ini_options]` · `tests/conftest.py` · `tests/test_ads.py` · `tests/test_core.py` · `tests/test_flet_api_guard.py` · `tests/test_imports_vs_deps.py` · `tests/test_proot_surfaces.py` · `tests/test_sessions.py` · `tests/test_terminal_wiring.py` · `tests/test_ui_reactive.py` · `tests/test_version_sync.py` · `tests/check_flet_api.py` · `.github/workflows/app.yml` · all 30 modules under `src/` · `.venv/Lib/site-packages/_pytest/**` · `.venv/Lib/site-packages/pytest_timeout.py` · `.venv/Lib/site-packages/flet/pytest_plugin.py` · `.venv/Lib/site-packages/flet/testing/tester.py` · `.venv/Lib/site-packages/flet_terminal/mobile_terminal.py` · **Date:** 2026-10-20

## What it does / how the app uses it

pytest is the app's **only** release gate for logic (`docs/decisions.md` D-005, D-015, D-017 all lean on it; D-003 freezes it as one of seven dev dependencies). The house config lives in `pyproject.toml:86-97`; the suite is 9 files / 55 tests; CI runs it at `.github/workflows/app.yml:107-108` (`uv run pytest -q -m "not live"`).

The **configuration is sound** — every key used is real, correctly typed, and does what the house reference says. The **suite is not**: three of the guards the decision log names as safety nets are void, and 7 of 10 behavioural mutations of `src/` are invisible to the run. Measured `src/` line coverage: **867 / 2875 = 30.2 %**.

---

## Findings

### F1 · P0 · The "frozen controls cannot be updated" guard never renders a view body — the D-015 release gate is void

- **Where:** `tests/test_ui_reactive.py:43-45` (`_render`), `:48-55`, `:99-118`; `src/screens/views.py:73-74`; `.venv/Lib/site-packages/flet/components/component.py:476-522` (`Renderer.render_component` → returns a `Component` wrapper, body **not** executed), `:170-205` (`Component.before_update` → `:194` `b = Renderer(self).render(self.fn, …)` is what actually runs the body).
- **What:** `docs/decisions.md` D-015 ruling 1 states: *"the components are constructed + re-rendered inside a renderer context in tests, so the bug class cannot silently return."* They are **not**. `Renderer.render_component()` only allocates a wrapper; the component body — the code that reads `core.state.state` and builds the control tree — is never invoked. `_render()` therefore returns an object whose `_b` (built body) is `None`, and `assert _render(...) is not None` is satisfied by the wrapper alone.
- **Evidence (probe, run against the installed flet 1.0.4):**
  ```
  probe: body executed? False | returned: Component
  DistroView -> Component | _b (built body): None
  DistroView .controls: n/a
  DistroView .build(): None
  ```
  Mutation test (pristine `git archive HEAD` tree in a temp dir, baseline = 0 failures):
  ```
  *** NOT CAUGHT ***  L views.py: DistroView raises the owner's 'Frozen controls cannot be updated' RuntimeError
  ```
  A view that raises **the owner's exact crash** at render time passes the whole suite. `test_state_changes_rerender_without_frozen_errors` (`tests/test_ui_reactive.py:99-118`) sets `state.containers`, `state.installing`, `state.install_stage`… and then never renders anything that reads them.
- **Fix / opportunity:** one line in the helper. `Component.before_update()` renders the body offline (verified: with a fake page bound to `flet.controls.context._context_page`, `dv.before_update()` completes and populates `_b`). Change `tests/test_ui_reactive.py:43-45` to bind a page + call `before_update()`, and assert on the **built tree** (control count, text values), not on the wrapper. No new dependency: `flet` is already a runtime dep.
- **Risk if ignored:** the app's own reported crash class ("Frozen controls cannot be updated", an APK that died on the owner's phone) can silently return and will only be discovered on a device, after an APK is handed over. The decision log currently claims a guarantee the suite does not provide.

### F2 · P1 · `test_both_input_paths_are_wired` is vacuous — it mocks the very thing that is broken

- **Where:** `tests/test_terminal_wiring.py:17-22` (`entry` fixture sets `item.mt = MagicMock()`), `:25-32` (`_handlers`), `:35-39` (the test); the real wiring is `src/screens/terminal_view.py:105-111` (`mt.set_on_bytes(...)`, `mt.on_data = ...`, `mt.on_resize`, `mt.on_mount`, `mt.on_title_change`).
- **What:** the test asserts `callable(handlers["on_bytes"])` and `callable(handlers["on_data"])`. Both operands are `MagicMock` attributes, which are **always** callable. The test never opens `src/screens/terminal_view.py`, never constructs a `MobileTerminal`, never checks that either handler is actually assigned.
- **Evidence (mutation test):** replacing the entire `src/screens/terminal_view.py` in a pristine copy with a stub that wires *nothing*:
  ```
  .....F                                                    [100%]
  FAILED tests/test_terminal_wiring.py::test_terminal_view_is_built_inside_the_component_tree
  ```
  The behaviour test named after the behaviour **passes**; only the source-text grep fails.
- **Fix / opportunity:** assert on the real widget, not a mock. `flet_terminal.MobileTerminal` is installed (`_pytest` sibling `.venv/Lib/site-packages/flet_terminal/mobile_terminal.py:22`) and every member the app uses exists there: `set_on_bytes` `:337`, `on_data` `:343`, `on_resize` `:352`, `on_title_change` `:361`, `on_mount` `:394`, `set_theme` `:156`, `send_bytes` `:245`, `clear_pending` `:415`. Construct a `MobileTerminal()` in the test, run the app's wiring block against it, and assert `mt.on_data is not None` / `mt._terminal.on_data` is the app's lambda — a real contract test, and the flet-terminal study's 0.3.9 → **0.4.0** drift (BRIEF rule 5) finally gets covered.
- **Risk if ignored:** D-017 ruling 4 records the exact field failure: *"Missing the second path is why characters silently vanish on a phone while delete still works."* The one test named for that regression cannot fail.

### F3 · P1 · The source-level imperative-mutation guard checks 1 of 4 screen files

- **Where:** `tests/test_ui_reactive.py:152-162`; `src/screens/` contains `__init__.py`, `onboarding_view.py`, `terminal_view.py`, `views.py`.
- **What:** the loop body assigns `src = path.read_text(...)` on every iteration, so after the loop `src` holds only the **last** file. The four `assert not re.search(pattern, src)` checks therefore inspect `src/screens/views.py` and nothing else. D-015 ruling 1 says the guard *"fails the build if imperative mutation returns to `screens.py`"* — it does not fail for `terminal_view.py` or `onboarding_view.py`.
- **Evidence (loop replication):**
  ```
  files visited by the loop:  __init__.py  onboarding_view.py  terminal_view.py  views.py
  => the assert only ever sees: views.py
  ```
  Mutation test:
  ```
  *** NOT CAUGHT ***  M terminal_view.py: imperative mutation (entry.mt.controls.append) in a screen
  *** NOT CAUGHT ***  N onboarding_view.py: imperative mutation (progress.value = ...)
  ```
  Both mutations match the guard's own regexes and are invisible to the suite.
- **Fix / opportunity:** accumulate instead of rebind — `srcs = {p: p.read_text() for p in ...}` then `for p, src in srcs.items(): assert not re.search(pattern, src), f"{p}: {pattern}"`. Two lines, no new dependency. (Same shape of bug appears in `tests/test_ui_reactive.py:154-155` only; the sibling guard `tests/test_proot_surfaces.py:45-51` gets it right — assert inside the loop.)
- **Risk if ignored:** the frozen-controls class is unguarded in 3 of 4 screens, and the guard actively reports "green" for those files.

### F4 · P1 · 7 of 10 behavioural mutations of `src/` are invisible to the suite

- **Where:** suite-wide; see the matrix below. The mutations target `src/main.py:29`, `src/services/update_service.py:34-37`, `src/app_controller.py:252`, `src/core/proot_probe.py:105`, `src/services/session_manager.py:80`, `src/services/ad_service.py:185`.
- **What:** a mutation-style harness (pristine `git archive HEAD` tree per mutant, baseline = **0 failures**) shows the suite has almost no power over app behaviour.
- **Evidence:**
  ```
  BASELINE failures: []

  *** NOT CAUGHT ***  A main.py: disconnect kills the shells (regression of commit 0fbe769)
  *** NOT CAUGHT ***  B update_service: is_allowed_launch_url accepts http://evil
  *** NOT CAUGHT ***  C update_service: is_allowed_launch_url accepts any host
  *** NOT CAUGHT ***  D app_controller: PD_DOCKER_AUTH never exported (private images break)
  *** NOT CAUGHT ***  E proot_probe: PD_PROOT_BIN never exported (proot can never exec)
  *** NOT CAUGHT ***  F session_manager.open: entry never marked ready (terminal stuck on 'starting')
  *** NOT CAUGHT ***  G ad_service: show_interstitial never shows (ads silently dead)
  CAUGHT   H storage_paths: XDG_DATA_HOME points at the Termux default
           tests/test_proot_surfaces.py::test_env_contract_is_import_safe
  CAUGHT   I session_service: host essentials not merged (proot cannot find libproot)
           tests/test_sessions.py::test_session_argv_merges_the_host_essentials
  CAUGHT   J proot_service: is_pull_limit always False (rate-limit msg lost)
           tests/test_proot_surfaces.py::test_pull_limit_is_reported_as_policy
  *** NOT CAUGHT ***  K app_controller: install_distro never clears state.installing (app wedged)
  ```
  Note **A**: it is a verbatim regression of the owner's own fix (commit `0fbe769` "sessions: a disconnect is not a shutdown", which changed `src/main.py:29` to `page.on_disconnect = lambda _e=None: None`) — the suite cannot see it come back. **B/C** are a security regression in the update-dialog launch allowlist (`src/services/update_service.py:26-37`).
- **Fix / opportunity:** close the gaps listed in the priority table below; each is one or two tests using only `monkeypatch` + `asyncio.run` (already in the suite's vocabulary).
- **Risk if ignored:** the "green CI" signal does not correspond to working software. A re-introduced disconnect-kills-shells or an allowlist bypass ships to the device unchallenged.

### F5 · P1 · `src/app_controller.py` has 0 % coverage and no test at all — the app's whole action layer is unverified

- **Where:** `src/app_controller.py` (327 executable lines, **0 covered**), `src/main.py` (0/24), `src/services/update_service.py` (0/66), `src/components/update_dialog.py` (0/112). `tests/conftest.py:1` — *"Shared fixtures — a minimal page stand-in for controller-branch tests"* — but there are **no** controller-branch tests.
- **What:** `AppController` owns install/remove/reset/search/cache-clear/token/theme/probe/session actions (`src/app_controller.py:141-418`). Not one is executed by the suite. The `FakePage` stand-in (`tests/conftest.py:10-48`) even carries `on_disconnect`/`on_close` attributes (`:19-20`) — the fingerprint of a planned `main.main()` test that was never written.
- **Evidence (stdlib `trace` line coverage of `src/`, 55-test run):**
  ```
  TOTAL executable lines in src/: 2875 covered: 867 (30.2%)
       0/ 327  src/app_controller.py
       0/ 112  src/components/update_dialog.py
       0/  66  src/services/update_service.py
       0/  24  src/main.py
     100/ 465  src/screens/views.py
      21/ 228  src/screens/terminal_view.py
      85/ 274  src/services/proot_service.py
      65/ 199  src/services/ad_service.py
      67/ 125  src/services/session_service.py
      44/ 108  src/core/proot_probe.py
  ```
  (`coverage`/`pytest-cov` are **not** installed — `.venv/Lib/site-packages/` has no `coverage`; the numbers above come from the stdlib `trace` module, so the gap is currently invisible to CI as well.)
- **Fix / opportunity:** the `FakePage` fixture already exists — wire `AppController(FakePage())` and drive the async methods with `asyncio.run`. `AppController.__init__` (`src/app_controller.py:39-43`) needs only `page.services`, `page.render`, `page.run_task`, `page.loop` — all present on the stand-in.
- **Risk if ignored:** every user-visible action (install, remove, search, backup, restore, token, theme, probe gate) is released with zero automated evidence.

### F6 · P2 · The suite is order-dependent: the `pwd`/`grp` shim leaks out of `test_proot_surfaces.py` into `test_core.py`

- **Where:** `src/core/posixdb.py:96-107` (`ensure()` writes `sys.modules[name] = factory()`), `src/services/proot_service.py:39` (`bootstrap()` calls `posixdb.ensure()`), `tests/test_proot_surfaces.py:106-117` (calls `proot_service.bootstrap()`), `tests/test_core.py:12-21` (the cleanup fixture `_restore_db_modules` is **module-local**, not in `tests/conftest.py`).
- **What:** on any interpreter without native `pwd`/`grp` (i.e. **Windows**, the house dev platform — `docs/dependency-studies/pytest.md:6` "Windows, Python 3.14.7"), `bootstrap()` installs both shims into `sys.modules` and nothing removes them. The only cleanup fixture lives in `test_core.py`, so it cannot protect the other module. `test_core.py:27-37` then asserts `probe == {"pwd": False, "grp": False}` and sees `True`.
- **Evidence (same suite, two orders):**
  ```
  === normal (alphabetical) order ===
  ................                                          [100%]
  === REVERSED order ===
  .........F......                                          [100%]
  E  AssertionError: assert {'pwd': True, 'grp': True} == {'pwd': False, 'grp': False}
  tests\test_core.py:34: AssertionError
  ```
  The suite is green today only because pytest collects files alphabetically (`test_core.py` < `test_proot_surfaces.py`). `--ff`/`--lf` reordering, a `-k` filter that changes the set, or `pytest-xdist` distribution changes the result.
- **Fix / opportunity:** move `_restore_db_modules` (`tests/test_core.py:12-21`) verbatim into `tests/conftest.py` as a session-wide `autouse` fixture. No behaviour change, one file move.
- **Risk if ignored:** the local (Windows) test loop can go red for a reason unrelated to the change under test, and the shim leak can silently change behaviour of any later test that imports `pwd`/`grp`.

### F7 · P2 · The warnings-as-errors policy has two dead regex alternatives and is narrower than the house doc claims

- **Where:** `pyproject.toml:95-97` — `"error::Warning:^(services|screens|components|core|state|hooks|tests)(\\.|$)"`; filter parsing `.venv/Lib/site-packages/_pytest/config/__init__.py:2122-2199` (`parse_warning_filter`, `escape=False` → the module field is a raw regex), applied at `:2225-2246`; per-item scope at `.venv/Lib/site-packages/_pytest/warnings.py:36-54`.
- **What:** the module field is matched against the `__name__` of the frame that *raised* the warning. Two alternatives can never match: `hooks` — no such module exists in `src/`; `tests` — `tests/` has no `__init__.py`, so test modules are imported as `test_core`, `test_ads`, … never `tests.test_core`. Verified by experiment: a `UserWarning` raised inside a module named `services.noisy` **is** turned into an error, and a `DeprecationWarning` is too (the `always` filters that pytest prepends for deprecations at `_pytest/warnings.py:41-42` do not shadow the config filter, because `warnings.filterwarnings` prepends and `apply_warning_filters` runs after them).
- **Evidence (isolated repro, house filter verbatim):**
  ```
  FAILED test_probe.py::test_user_warning_becomes_error  - UserWarning: user warning from our module
  FAILED test_probe2.py::test_deprecation_warning_becomes_error - DeprecationWarning: deprecation from our module
  2 failed
  ```
  One real hole remains: the attribution follows the **stacklevel**. A warning raised with `stacklevel=2` from `services/x.py` is attributed to the *caller* and escapes the filter (verified: with `stacklevel=2` the same warning was only reported, not raised). The app raises no warnings today (`grep warnings.warn src/` → 0 hits), so this is latent.
- **Fix / opportunity:** drop the `hooks` and `tests` alternatives from `pyproject.toml:96`; add `^tests?\.` only if `tests/` ever becomes a package. Document the stacklevel caveat next to the key.
- **Risk if ignored:** the policy reads stronger than it is; a future warning raised with an explicit `stacklevel` from a dependency's helper inside our module will be reported, not fatal.

### F8 · P2 · `timeout_method` is not pinned, so the timeout behaves differently on CI (Linux) and on the house dev box (Windows)

- **Where:** `pyproject.toml:89` sets `timeout = 60` but **no** `timeout_method`; `.venv/Lib/site-packages/pytest_timeout.py:26-30` (`HAVE_SIGALRM` → `DEFAULT_METHOD = "signal"` on Linux, `"thread"` on Windows), `:99-108` (the ini keys), `:362-373` (resolution order: CLI → ini → default), `:303-336` (the two implementations). `docs/reference/dep-test-and-lint-stack.md:13` explicitly says: *"For a Windows+Linux CI matrix, pin **`timeout_method = "thread"`** for uniform behavior (house style uses `timeout = 60`)."*
- **What:** the house reference and the house config disagree. The dev loop runs on Windows (`thread` → a `threading.Timer` fires, the hung thread keeps running); CI runs on `ubuntu-latest` (`.github/workflows/app.yml:41`) → `signal`/SIGALRM, which kills the process hard. A test that hangs in CI is killed; the same hang on the dev box leaves a live thread.
- **Evidence:** `pytest --co -v` header on this box: `plugins: anyio-4.15.1, flet-1.0.4, timeout-2.4.0` / `timeout: 60.0s` — no method shown (the method is only printed with `--timeout-method` set).
- **Fix / opportunity:** add `timeout_method = "thread"` to `pyproject.toml` (one line) — or amend `docs/reference/dep-test-and-lint-stack.md:13` if the house prefers the platform default. Pick one; today the doc and the file disagree.
- **Risk if ignored:** "the test passes locally" and "CI killed the hung test" are two different failure modes; a hang on the dev box is not reproducible in CI and vice versa.

### F9 · P2 · The `live` marker is registered but never used — CI's `-m "not live"` is a no-op

- **Where:** `pyproject.toml:92-94` registers `live`; `.github/workflows/app.yml:108` runs `uv run pytest -q -m "not live"`. `markers` is a `linelist` (`.venv/Lib/site-packages/_pytest/mark/__init__.py:126`); `strict_markers` is honoured at `.venv/Lib/site-packages/_pytest/mark/structures.py:620-634`.
- **What:** **no** test in `tests/` carries any `@pytest.mark.*` (census: `pytest.mark` → 0 hits in `tests/**/*.py`). The desktop/device split the house doc describes does not exist.
- **Evidence:** `pytest -m "live" --collect-only -q` → **0 tests collected**; `pytest --markers` lists `@pytest.mark.live: hits the real device or network (deselected on desktop CI)` — registered, unused.
- **Fix / opportunity:** either mark the device-dependent tests when they exist (the D-005 tier-3 device gate is currently a manual step), or drop the marker and the `-m` flag until there is something to deselect — a registered-but-unused marker plus a CI flag that does nothing is misleading documentation.
- **Risk if ignored:** the first device test added without the marker will run on desktop CI and fail there (or, worse, run against a real device and mutate state).

### F10 · P3 · Dead fixtures and dead test helpers

- **Where:** `tests/conftest.py:51-53` (`fake_page` — **never referenced** by any test), `tests/conftest.py:56-59` (`platform_windows` — **never referenced**; the one test that needs it, `tests/test_core.py:79`, does the `monkeypatch.delenv` inline at `:82`), `tests/test_sessions.py:85-98` (`_FakeProcess` — **defined, never instantiated**), `tests/test_sessions.py:115` (`monkeypatch` parameter declared and never used), `tests/test_terminal_wiring.py:55-65` (two tests that exercise only the stdlib `json` module: `json.dumps` → `json.loads` → compare, and `pytest.raises(ValueError)` around `json.loads("not-json")`).
- **What:** `tests/test_sessions.py:4-5` claims *"the PTY is exercised against a fake process"* — the fake process is never used. `tests/test_terminal_wiring.py:63-65` is named "…**is ignored**" but asserts the opposite (that it *raises*).
- **Evidence:** `grep -rn "fake_page\|platform_windows\|_FakeProcess" tests/ --include=*.py` → only the definitions.
- **Fix / opportunity:** delete `fake_page`/`platform_windows`/`_FakeProcess`, drop the unused `monkeypatch` parameter, and either delete the two stdlib-only `json` tests or convert them into real assertions on `src/screens/terminal_view.py:83-94` (the `_on_resize` handler that parses the payload) — that is the behaviour they were written for.
- **Risk if ignored:** dead fixtures read as coverage. A future agent sees `fake_page` and assumes the controller is tested; the docstring at `tests/test_sessions.py:4-5` is actively false.

### F11 · P3 · The flet API guard runs twice over the same files (CI shell loop + pytest)

- **Where:** `.github/workflows/app.yml:54-58` (a `for f in $(find src -name "*.py"); do uv run --no-sync python tests/check_flet_api.py "$f" || exit 1; done`) and `tests/test_flet_api_guard.py:34-45` (runs the same `guard.main()` over the same `_src_files()` set, `tests/test_flet_api_guard.py:26-27`).
- **What:** identical work, twice. The pytest version is the more complete one — it also asserts the file set is non-empty (`tests/test_flet_api_guard.py:30-31`) and reports all failures at once.
- **Evidence:** `pytest --durations=12` → `4.84s call tests/test_flet_api_guard.py::test_every_source_file_passes_the_api_guard`.
- **Fix / opportunity:** drop the CI shell step and keep the pytest test (or vice-versa). No behavioural change to the gate.
- **Risk if ignored:** ~5 s of CI per run and two places to keep in sync.

### F12 · P3 · The suite uses almost none of pytest's feature surface, and ignores the pytest plugin that flet itself ships

- **Where:** census over `tests/**/*.py`: `parametrize` **0**, `tmp_path` **0**, `tmpdir` **0**, `capsys` **0**, `capfd` **0**, `caplog` **0**, `recwarn` **0**, `subtests` **0**, `approx` **0**, `xfail` **0**, `skipif` **0**, `pytest.mark.*` **0**, `pytestconfig` **0**; used: `monkeypatch` 27, `pytest.raises` 6, `pytest.fixture` 5, `pytest.importorskip` 4, `pytest.skip` 1. The installed flet registers its own plugin: `.venv/Lib/site-packages/flet-1.0.4.dist-info/entry_points.txt:4-5` → `[pytest11] flet = flet.pytest_plugin`, providing `flet_app` / `flet_app_function` (`.venv/Lib/site-packages/flet/pytest_plugin.py`) and `flet.testing.Tester` (`.venv/Lib/site-packages/flet/testing/tester.py:15`, with `pump` `:20`, `pump_and_settle` `:29`, `find_by_text` `:48`). `anyio` 4.15.1 is also autoloaded (plugins header) and unused.
- **What:** the house pytest study explicitly prescribes `tmp_path` for fake rootfs trees (`docs/dependency-studies/pytest.md:85-88`); the suite uses `tempfile.TemporaryDirectory()` instead (`tests/test_core.py:92,96`). The ads tests hand-roll `asyncio.run(...)` five times (`tests/test_ads.py:26,36,44,56`) although the `anyio` plugin is already installed and loaded. `pytest_asyncio` is **not** installed, so flet's plugin currently degrades to a no-op (`.venv/Lib/site-packages/flet/pytest_plugin.py:16-21`).
- **Fix / opportunity:** (a) `tmp_path` for the `ProotSession`/storage fakes (house-prescribed, zero new deps); (b) `@pytest.mark.parametrize` over the `proot_service._ns_*` namespace builders and the `theme_mode` matrix — the same coverage, fewer duplicated test bodies; (c) `caplog` for the `state.data_note` / stage-line assertions the app already logs (`src/services/proot_service.py:411`, `src/services/ad_service.py:82-91`); (d) `pytestconfig` to assert the house ini values — the study names a `test_config_parity.py` guard (`docs/dependency-studies/pytest.md:98-100`); (e) `pytest.raises` + `match=` for the existing bare `pytest.raises(RuntimeError)` calls (`tests/test_sessions.py:75,81,133`) so the *reason* is asserted, not just the type.
- **Risk if ignored:** the suite is 55 hand-written, largely-duplicated test bodies where a parametrized table would be shorter; and it drifts from the house's own documented pytest usage.

### F13 · P3 · Configuration hardening the house reference offers but the config does not take

- **Where:** `docs/reference/dep-test-and-lint-stack.md:9` — *"Optional hardening available: `minversion`, `required_plugins` (packaging-backed)."* Neither is set in `pyproject.toml:86-97`. Also unset: `testpaths` (`.venv/Lib/site-packages/_pytest/main.py:241-247`), `strict_xfail` (`.venv/Lib/site-packages/_pytest/skipping.py:39-47`, default `None` → falls back to `strict`, which is off — the house sets `strict_config`/`strict_markers` separately, `pyproject.toml:90-91`), `session_timeout` (`.venv/Lib/site-packages/pytest_timeout.py:108`), `faulthandler_timeout` (`.venv/Lib/site-packages/_pytest/faulthandler.py:27-30`).
- **What:** `minversion` is packaging-backed and enforced at `_pytest/config/__init__.py:1452-1460`; `required_plugins` at `:1552-1557` and `:1466-1497`. Without `minversion`, a pytest 10 bump is not gated at startup — `PytestRemovedIn10Warning` handling is commented out at `_pytest/warnings.py:44-45` and is meant to become an error in 10.0. Without `faulthandler_timeout`/`session_timeout`, a hang during **collection/import** (e.g. `import flet` blocking) is not interrupted by the 60 s per-test timer, which only starts at test setup.
- **Fix / opportunity:** `minversion = "9.1"` and `required_plugins = ["pytest-timeout>=2.4"]` in `pyproject.toml` (two lines, zero new packages). `strict_xfail` is moot until someone uses `xfail`; `faulthandler_timeout = 120` is the cheap insurance against import-time hangs.
- **Risk if ignored:** a dependency bump can turn into a red CI with an obscure error instead of a clear "pytest too old" message, and an import-time hang wedges the job with no stack dump.

---

## Prioritized test-suite gaps

Ordered by (user-visible risk × likelihood of silent regression) ÷ cost to close. Every item uses only capabilities already in the venv — no new packages (D-003).

| # | Gap | Why it is first | Minimal fix | Cost |
|---|---|---|---|---|
| 1 | **The frozen-controls render guard is void** (F1) | The owner's shipped crash class has no live guard; a view raising the exact `RuntimeError` passes CI. | Change `tests/test_ui_reactive.py:43-45` to bind a fake page (`flet.controls.context._context_page`) and call `Component.before_update()`; assert on the built tree. | ~15 LOC |
| 2 | **Terminal input paths are mocked, not tested** (F2) | D-017.4's field failure ("characters silently vanish on a phone") has a test that cannot fail. | Build a real `MobileTerminal` and assert `set_on_bytes` / `on_data` / `on_resize` / `on_mount` are the app's handlers (`src/screens/terminal_view.py:105-111`). | ~25 LOC |
| 3 | **`AppController` is 0 % covered** (F5) | Every user action — install, remove, search, backup, restore, token, theme, probe — is released with no automated evidence. | Use the existing `FakePage` (`tests/conftest.py:10-48`) + `asyncio.run` to drive `install_distro` / `remove_container` / `set_docker_token` / `cycle_theme_mode`. | ~60 LOC, 8 tests |
| 4 | **The update-dialog launch allowlist is untested** (F4, mutation B/C) | A security boundary (`src/services/update_service.py:26-37`) with zero coverage: `http://evil` and any host are both accepted by the mutants. | 3 `pytest.raises`/`is False` cases over `is_allowed_launch_url` + `is_newer` (both pure functions, no I/O). | ~20 LOC |
| 5 | **The `main.py` disconnect/close wiring is untested** (F4, mutation A) | A verbatim regression of the owner's own fix (commit `0fbe769`) is invisible. | Assert `page.on_disconnect` is a no-op and `page.on_close` closes sessions, using the `FakePage.on_disconnect`/`on_close` slots that already exist (`tests/conftest.py:19-20`). | ~15 LOC |
| 6 | **The payload probe's env contract is untested** (F4, mutation E) | `PD_PROOT_BIN` / `PROOT_LOADER` / `LD_LIBRARY_PATH` / `PROOT_TMP_DIR` are set at `src/core/proot_probe.py:104-107`; the app cannot exec proot without them, and nothing checks. | `monkeypatch.setenv("ANDROID_NATIVE_LIBRARY_DIR", str(tmp_path))` + `bootstrap_env(runtime_root=tmp_path)`; assert the four env vars and that `res.staged`/`res.problems` behave. | ~30 LOC |
| 7 | **`SessionManager.open()` / `close()` are untested** (F4, mutation F) | The "open a shell" path — the product's core feature — is only covered at the `entry()` bookkeeping level (`tests/test_sessions.py:115-134`). | `monkeypatch` `session_service.session_argv` + `ProotSession`, then assert `entry.ready`, `entry.session`, and that `close()` stops it. | ~30 LOC |
| 8 | **The ad-show path is untested** (F4, mutation G) | `show_interstitial` (`src/services/ad_service.py:166-227`) — the money path — is only covered for its two *skip* branches. | Cover the show branch with a fake `InterstitialAd` **and** assert the real `flet_ads` unit id matches `pyproject.toml:75`; the 30 s interval guard is already covered. | ~30 LOC |
| 9 | **The screens source-guard checks 1 of 4 files** (F3) | Imperative mutation in `terminal_view.py` / `onboarding_view.py` is unguarded *and* the guard reports green. | Accumulate the sources instead of rebinding `src` (`tests/test_ui_reactive.py:154-155`). | 2 LOC |
| 10 | **The suite is order-dependent** (F6) | The local Windows loop can go red for an unrelated reason; `--ff`/`xdist` change the answer. | Move `_restore_db_modules` (`tests/test_core.py:12-21`) into `tests/conftest.py` as a session-wide autouse fixture. | file move |
| 11 | **`_fmt_size` / `_fmt_count` are untested** (F5) | Pure helpers with real formatting rules (`src/screens/views.py:54-67`) that a `parametrize` table covers in six lines — and the house pytest study names `fmt_size` as a doctest-able helper (`docs/dependency-studies/pytest.md:346-349`). | `@pytest.mark.parametrize("n,expected", [...])`. | ~10 LOC |
| 12 | **The `proot_service._ns_*` namespaces are only half-pinned** (F5) | `tests/test_proot_surfaces.py:57-83` pins install/remove/reset against upstream's parser but not rename/backup/restore/copy/kill (`src/services/proot_service.py:137-170`) — the namespaces that break on an upstream bump. | Extend the existing "subset of upstream's namespace" assertion to the remaining five. | ~25 LOC |
| 13 | **The `proot_probe` staging + f2fs verdict paths are untested** | `src/core/proot_probe.py:80-113` is the device gate; only the "no native dir" early-return is covered (`tests/test_core.py:79-88`). | Same fixture as #6. | ~20 LOC |
| 14 | **No test asserts the house ini config itself** | A typo'd/renamed ini key would be caught by `strict_config` only at the *next* pytest release that adds the key; the house study names a `test_config_parity.py` guard (`docs/dependency-studies/pytest.md:98-100`). | `pytestconfig.getini("timeout") == "60"`, `getini("pythonpath")`, `getini("markers")`. | ~15 LOC |
| 15 | **The `flet` pytest plugin + `flet.testing.Tester` are unused** | Flet 1.0.4 ships `flet_app` / `flet_app_function` and a real `Tester`; the suite hand-rolls a `FakePage` instead. Note `pytest_asyncio` is not installed, so the plugin is currently a no-op — adopting it would need `pytest-asyncio` (**new package → owner sign-off under D-003**). | Defer; do not add the package unilaterally. | blocked by D-003 |

---

## Missed capabilities (dependency audits only)

| Capability | Where it lives | Current use | Proposed integration point | Value vs cost |
|---|---|---|---|---|
| `pytest.mark.parametrize` | `_pytest/mark/structures.py` | **0 uses** | `tests/test_proot_surfaces.py` (the five unpinned namespaces), `tests/test_ui_reactive.py:135-149` (theme matrix), `tests/test_sessions.py` (host-essential merge) | Replaces 6 near-duplicate test bodies with 3 tables. Zero cost. |
| `tmp_path` | `_pytest/tmpdir.py:291` | **0 uses** (the house study prescribes it, `docs/dependency-studies/pytest.md:85-88`) | fake rootfs / `containers/<name>/` / `oci_layers/` for `ProotSession` + `proot_service.storage_bytes` | Enables the "no real filesystem" tests the house doc asks for; replaces `tempfile.TemporaryDirectory()` (`tests/test_core.py:92,96`). Zero cost. |
| `caplog` | `_pytest/logging.py:611` | **0 uses** | assert `state.data_note` / install stage lines / ad-skip reasons (`src/services/proot_service.py:411`, `src/services/ad_service.py:82-91`) | Turns "no swallowed bugs" (D-017.9) into an assertion instead of a comment. Zero cost. |
| `pytestconfig` | `_pytest/fixtures.py:1564` | **0 uses** | a `test_config_parity.py` guard, exactly as the house study prescribes (`docs/dependency-studies/pytest.md:98-100`) | Pins `timeout`, `pythonpath`, `markers` against the installed pytest. Zero cost. |
| `pytest.raises(..., match=…)` | `_pytest/raises.py:74` | 6 uses, none with `match=` | `tests/test_sessions.py:75,81,133` | Asserts *why* the RuntimeError fired, not just its type. Zero cost. |
| `xfail` / `skipif` | `_pytest/skipping.py` | **0 uses** | the known-broken `apt upgrade-over-existing` path (D-016.2) — currently absent from the suite entirely | Marks the one open upstream bug as a *tracked* failure instead of silence. Zero cost. |
| `pytest.approx` | `_pytest/python_api.py:646` | **0 uses** | size/percentage assertions | Low value here (the app formats sizes as strings). Skip. |
| `subtests` | `_pytest/subtests.py:136` | **0 uses** | the five unpinned upstream namespaces — one test, five subtests | Nice-to-have; `parametrize` is a better fit. |
| `flet.testing.Tester` + `flet_app` fixtures | `.venv/Lib/site-packages/flet/testing/tester.py:15`, `.venv/Lib/site-packages/flet/pytest_plugin.py` | **0 uses** | real UI assertions instead of `FakePage` | High value (would close gap #3 for real), but the plugin is a no-op without `pytest_asyncio`, which is **not installed** → a new package → needs owner sign-off under D-003. Flag, do not install. |
| `anyio` pytest plugin | autoloaded (`anyio-4.15.1` in the plugins header) | **0 uses**; the suite hand-rolls `asyncio.run` 5× (`tests/test_ads.py:26,36,44,56`) | replace `asyncio.run(...)` with `@pytest.mark.anyio` + the `anyio_backend` fixture | Already installed; removes the repeated `import asyncio` inside test bodies. Zero cost. |
| `minversion` / `required_plugins` | `_pytest/config/__init__.py:1548`, `:1552-1557` | unset | `pyproject.toml:86-97` | Fails fast on a pytest/pytest-timeout downgrade. Zero cost (no new package). |
| `faulthandler_timeout` / `session_timeout` | `_pytest/faulthandler.py:27-30`, `pytest_timeout.py:108` | unset | `pyproject.toml` | Dumps stacks on an import-time hang, which the 60 s per-test timer cannot catch. Zero cost. |

---

## Verified-good list

Checked and correct — do not re-open:

- **The ini mode is right.** `[tool.pytest.ini_options]` (`pyproject.toml:86`) is the string-INI compat mode; no `[tool.pytest]` native-TOML block exists, so there is no mutually-exclusive-mode `UsageError`. `configfile: pyproject.toml` confirmed in the pytest header; `rootdir` = repo root.
- **Every key used is real and correctly typed.** `pythonpath` (`_pytest/config/__init__.py:1549-1551`, type `paths`), `addopts` (`:1547`, type `args`), `strict_markers` (`_pytest/main.py:105-112`, type bool), `strict_config` (`_pytest/main.py:97-104`, type bool), `markers` (`_pytest/mark/__init__.py:126`, type `linelist`), `filterwarnings` (`_pytest/main.py:137-143`, type `linelist`), `timeout` (`pytest_timeout.py:99`).
- **`strict_config` really fails.** Unknown ini keys raise `UsageError` through `_warn_or_fail_if_strict` (`_pytest/config/__init__.py:1499-1506`, called from `:1462-1464`).
- **`strict_markers` really fails.** An unregistered mark hard-fails via `fail(...)` at `_pytest/mark/structures.py:620-626`.
- **`pythonpath = ["src"]` is rootdir-relative, not CWD-relative.** The `paths` ini type resolves against `self.inipath.parent` (`_pytest/config/__init__.py:1786-1793`) and is prepended to `sys.path` at `:1371-1375`, with a matching cleanup at `:1377-1381`. Running pytest from any directory resolves `src` correctly.
- **The warnings-as-errors filter works for warnings raised inside our own modules.** Verified end-to-end: a `UserWarning` and a `DeprecationWarning` raised from a module named `services.noisy` both become test errors under the house filter. pytest's prepended `always` deprecation filters (`_pytest/warnings.py:39-42`) do **not** shadow the config filter, because `apply_warning_filters` runs after them and `warnings.filterwarnings` prepends (`_pytest/config/__init__.py:2225-2246`).
- **The `timeout = 60` ini is honoured.** The pytest header prints `timeout: 60.0s`; resolution order is CLI → ini → default (`pytest_timeout.py:362-373`).
- **The sole-importer rule is genuinely enforced.** `tests/test_proot_surfaces.py:34-42` AST-walks all of `src/` and asserts `src/services/proot_service.py` is the only importer; `:45-51` does the same for `screens/` + `app_controller.py` with the assert *inside* the loop (this is the correct shape that `tests/test_ui_reactive.py:154-162` gets wrong).
- **The dev-only-tree guard is real.** `tests/test_proot_surfaces.py:133-148` proves `src/` never imports `pytest`, `ruff`, `flet_cli`, `flet_desktop`, `cookiecutter`, `jinja2`, `requests`, `chardet`, `binaryornot`.
- **The import-vs-deps guard is real.** `tests/test_imports_vs_deps.py:46-59` resolves every `src/` import against `pyproject.toml` + the installed dist metadata, with a `sys.stdlib_module_names` carve-out. It also parses the `tool.flet.<platform>.dependencies` tables (`:24-25`).
- **The upstream argv contract is genuinely pinned.** `tests/test_sessions.py:17-37` holds a captured `--get-proot-cmd` line *and* its backslash-newline-wrapped form; `:148-159` covers the wrapped form, `:71-83` the two rejection paths, `:59-68` the host-essential merge. This is the D-017.1 guarantee and it holds.
- **`is_pull_limit` is covered** (`tests/test_proot_surfaces.py:151-156`) — mutation J confirms it.
- **The `env_contract` is covered** (`tests/test_proot_surfaces.py:88-103`) — mutation H confirms it.
- **The `posixdb` shim *shapes* are covered** (`tests/test_core.py:48-73`) on the factories directly, which is the D-015.7(c)-correct approach (Linux runners have a real `grp`).
- **`theme_mode` resolution is covered** (`tests/test_ui_reactive.py:135-149`), including the "no page → terminal-native dark" default (`src/core/theme.py:60-61`).
- **The `BUILTIN_THEMES` names the app uses exist in the installed flet-terminal 0.4.0.** `BUILTIN_THEMES.get("Collab Light")` and `.get("JetBrains Dark")` (`src/screens/terminal_view.py:34,75`) resolve — runtime check: `['Colab Light', 'Dracula', 'JetBrains Dark', 'Matrix Green']` (`.venv/Lib/site-packages/flet_terminal/themes.py:9`).
- **Every `ft.*` chain in `src/` exists in the installed flet.** `tests/test_flet_api_guard.py:34-45` runs `tests/check_flet_api.py` over all 30 `src/` files; the suite is green. The guard's `RuntimeError` branch (`tests/check_flet_api.py:74-79`) correctly accepts runtime-context chains such as `ft.context.page`.
- **The version-drift guard is real.** `tests/test_version_sync.py:23-46` pins `pyproject.toml` ↔ `core/constants.py` ↔ `CHANGELOG` ↔ `version.json` ↔ the workflow defaults, and skips cleanly when `version.json` is absent (`:36-37`).
- **The license-text guard caught a real problem.** `tests/test_ui_reactive.py:175-197` compares `src/LICENSES/` against the repo `LICENSES/` byte-for-byte; in this working tree it fails because `src/LICENSES/` has been deleted (uncommitted) — see *Unverified*.
- **`pytest.importorskip` is used correctly** for the optional/host-dependent paths (`tests/test_proot_surfaces.py:58,77,107`, `tests/test_ui_reactive.py:16`).
- **The `tests/` tree is not collected as a package** (`python_files` default `test_*.py` / `*_test.py`, `_pytest/python.py:87-92`), so `tests/check_flet_api.py` is a CLI script, not a test module — as intended (`pyproject.toml:111`).

---

## Unverified

- **The current working tree has 24 uncommitted file deletions** (`git diff --stat`: `src/LICENSES/*.txt`, `LICENSES/*.txt`, `check_elf_alignment.py`, `generate_third_party_sources.py`, `docs/*`). Consequently `pytest -q -m "not live"` currently reports **2 failed, 53 passed** — `tests/test_ui_reactive.py::test_license_texts_are_present_and_shipped` and `::test_licenses_view_carries_real_text` (the licenses view renders `"(text missing)"` because `src/LICENSES/` is gone, `src/screens/views.py:628`). This is a worktree state, not a suite defect; the committed tree (`git archive HEAD`) is **0 failures**, which is the baseline used for every mutation result above. Whether the deletions are intentional is outside my scope.
- **Whether `proot_distro` is importable on Windows CI is not exercised** — CI is `ubuntu-latest` only (`.github/workflows/app.yml:41`), and the suite's `importorskip` guards make the Windows path untested. The `pythonpath`/`src` layout is proven here on Windows.
- **The `timeout = 60` ceiling has never been hit**, so the timeout's *behaviour* on timeout (stack dump, thread kill) is unproven in this repo.
- **`flet.testing.Tester` / `flet_app` are unproven in this environment**: `pytest_asyncio` is not installed, so `.venv/Lib/site-packages/flet/pytest_plugin.py` degrades to a no-op and its fixtures are never registered. Whether they work under `flet test` on this repo is UNVERIFIED.
- **The `live` marker has never been exercised** — no test uses it, so the desktop/device split described in `docs/reference/dep-test-and-lint-stack.md` and `docs/dependency-studies/pytest.md:113` is aspirational.
- **Line-coverage numbers are from the stdlib `trace` module** (`trace._find_executable_linenos`), not `coverage.py` — branch coverage is not measured, and `trace` counts only lines executed under the traced run. Treat 30.2 % as a floor.
- **The mutation matrix is a sample (13 mutations), not a full mutation score.** It demonstrates the *shape* of the gap; it does not bound it.
- **No `xfail` exists, so the one open upstream defect named in D-016.2** (`apt upgrade-over-existing`) is not tracked by the suite at all — its absence from the suite is a fact; whether it is reachable through any current code path is UNVERIFIED.
- **CI was not executed** — the workflow was read, not run. All CI claims are static-analysis based plus local runs of the same commands.
