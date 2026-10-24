# pytest-timeout 2.4.0 — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/pytest-timeout.md`; `docs/reference/dep-test-and-lint-stack.md`; `docs/decisions.md:13` (D-003); `pyproject.toml`; `.github/workflows/app.yml`; `tests/` (all 11 `.py` files); `src/services/session_service.py`; `src/core/proot_probe.py`; `.venv/Lib/site-packages/pytest_timeout.py` (559 lines, read in full); `.venv/Lib/site-packages/pytest_timeout-2.4.0.dist-info/METADATA`; `.venv/Lib/site-packages/_pytest/` (`config/__init__.py`, `main.py`, `runner.py`); `docs/swarm/dependency-utilization/pluggy.md` (sibling, overlap noted in F1) · **Date:** 2026-10-20

## What it does / how the app uses it

**pytest-timeout is the repo's only runaway-test guard. It is installed, auto-loaded and configured — but it is configured to exactly one of its two settings, and the one it is missing is the one that decides what a hung test does to the whole run.**

- **Declared dev-group dependency**: `pyproject.toml:82` `"pytest-timeout>=2.4.0"`, installed 2.4.0 (`docs/swarm/dependency-tree/installed.json`, `uv.lock` dev group). It is dev-only and cannot reach the APK (`pyproject.toml:9-15` runtime deps exclude it).
- **The whole configuration surface is two lines**: `pyproject.toml:89` `timeout = 60`. There is **no** `timeout_method`, **no** `timeout_func_only`, **no** `session_timeout`, **no** `timeout_disable_debugger_detection` (`grep -n "timeout" pyproject.toml` → only `:82` and `:89`).
- **Effective policy, as the plugin itself reports it** (session header, live run):
  ```
  plugins: anyio-4.15.1, flet-1.0.4, timeout-2.4.0
  timeout: 60.0s
  timeout method: thread
  timeout func_only: False
  ```
  (`pytest_report_header`, `pytest_timeout.py:219-238`.)
- **The method is chosen by the platform, not by the repo.** `pytest_timeout.py:26-30`:
  ```python
  HAVE_SIGALRM = hasattr(signal, "SIGALRM")
  if HAVE_SIGALRM:
      DEFAULT_METHOD = "signal"
  else:
      DEFAULT_METHOD = "thread"
  ```
  Measured on this machine: `HAVE_SIGALRM: False` → `DEFAULT_METHOD: thread` (Windows). CI runs `ubuntu-latest` (`.github/workflows/app.yml:41`) → `signal`. **The two environments take different code paths, and the paths differ in how violently they fail** (F1).
- **What each path does on a hung test** — `signal` → `timeout_sigalrm` (`pytest_timeout.py:485-503`) dumps the stacks of every thread and calls `pytest.fail(...)` (`:502`) → **one test fails, the run continues, a normal summary is printed**. `thread` → `timeout_timer` (`pytest_timeout.py:505-542`) dumps the stacks, then calls **`os._exit(1)`** (`:542`) → **the entire pytest process dies on the spot**: no summary, no remaining tests, no fixture teardown, exit code 1 (indistinguishable from an ordinary test failure by exit code alone).
- **CI uses it exactly once**: `.github/workflows/app.yml:108` `uv run pytest -q -m "not live"`. The `quality` job has **no** job-level `timeout-minutes` (`grep -rn "timeout-minutes" .github/` → no output), and the plugin's own `session_timeout` is unset — so the 60 s per-test guard is the *only* bound on the whole quality job (F2).
- **The suite itself is timeout-safe today**: no test spawns a thread, a subprocess or a PTY (see *Verified-good list* and F6).

## Findings

### F1 · P2 · `timeout_method` is unpinned: the same hung test **hard-kills the whole Windows run** but only **fails one test on Linux CI** — and `signal` cannot be the fix

- **Where:** `pyproject.toml:86-97` — `[tool.pytest.ini_options]` sets `timeout = 60` (`:89`) and **no** `timeout_method`; `.github/workflows/app.yml:41` (`runs-on: ubuntu-latest` for the `quality` job), `:108` (`uv run pytest -q -m "not live"`); `.venv/Lib/site-packages/pytest_timeout.py:26-30` (platform switch), `:306-311` (`signal` → `thread` fallback off the main thread), `:313-325` (signal arming), `:326-335` (thread arming), `:485-503` (`timeout_sigalrm` → `pytest.fail` at `:502`), `:505-542` (`timeout_timer` → `os._exit(1)` at `:542`).
- **What:** the repo's dev environment is Windows and its CI is Linux-only, and the unpinned method splits the failure semantics of the *one* guard the house has:
  - **Windows (laptop, `thread`)** → `os._exit(1)` (`:542`) → the whole pytest process is killed: the remaining tests never run, no `N passed / M failed` summary is printed, no fixture teardown executes, exit code 1 — the same code a normal test failure produces.
  - **Linux CI (`signal`)** → `pytest.fail(...)` (`:502`) → exactly one test fails, the remaining ~54 still run, the summary is printed.
  The house's own reference doc already prescribes the fix and the repo has not applied it: `docs/reference/dep-test-and-lint-stack.md:13` — *"**Method default is platform-dependent**: `signal` where SIGALRM exists (Linux/CI), `thread` on Windows. For a Windows+Linux CI matrix, pin **`timeout_method = "thread"`** for uniform behavior (house style uses `timeout = 60`)."* The dependency study's house policy (§5) says the same. So this is **doc-vs-pyproject drift, not a new proposal**.
  **New constraint established by this audit:** `signal` is **not** an available pin value. On Windows `signal.SIGALRM` does not exist, so the `signal` branch raises inside the timer hook and pytest dies with an INTERNALERROR (exit code 3). `thread` is the only value that works on both platforms — the choice is binary, not a preference.
- **Evidence:**
  ```
  $ grep -n "timeout" pyproject.toml
  82:    "pytest-timeout>=2.4.0",
  89:timeout = 60
  ```
  ```
  $ .venv/Scripts/python.exe -c "import pytest_timeout; print(pytest_timeout.HAVE_SIGALRM, pytest_timeout.DEFAULT_METHOD)"
  False thread
  ```
  Windows, `thread` method — a 60 s sleep under `--timeout=3` (throwaway file outside the repo, repo untouched):
  ```
  $ pytest -o addopts="" --timeout=3 --timeout-method=thread -v test_hang.py ; echo EXIT=$?
  test_hang.py::test_a_hangs +++++++++++++++++++++++++++++++++++ Timeout +++++++++++++++++++++++++++++++++++
  ~~~~~~~~~~~~~~~~~~~~~~~~~ Stack of MainThread (21372) ~~~~~~~~~~~~~~~~~~~~~~~~~
  ...
  +++++++++++++++++++++++++++++++++++ Timeout +++++++++++++++++++++++++++++++++++
  EXIT=1
  $ grep -c "MARKER_TEST_B_RAN" out_thread.txt
  0                       # the SECOND test never ran
  $ grep -Eo "[0-9]+ (passed|failed)" out_thread.txt
  (no output)             # pytest never produced a summary
  ```
  Windows, `signal` method — **not usable**:
  ```
  $ pytest -o addopts="" --timeout=3 --timeout-method=signal -v test_hang.py ; echo EXIT=$?
  INTERNALERROR>     signal.signal(signal.SIGALRM, handler)
  INTERNALERROR> AttributeError: module 'signal' has no attribute 'SIGALRM'. Did you mean: 'SIGABRT'?
  EXIT=3
  ```
  (raised from `pytest_timeout.py:324`, `signal.signal(signal.SIGALRM, handler)` — the module-level `signal.SIGALRM` attribute does not exist on Windows).
  Linux CI path, from the installed source (not executed here — see *Unverified*):
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  485:def timeout_sigalrm(item, settings):
  ...
  499:    dump_stacks(terminal)
  ...
  502:    pytest.fail(PYTEST_FAILURE_MESSAGE % settings.timeout)
  ```
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  505:def timeout_timer(item, settings):
  506:    """Dump stack of threads and call os._exit().
  ...
  542:        os._exit(1)
  ```
- **Fix / opportunity — the minimal config fix (one line, `pyproject.toml`):**
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["src"]
  addopts = ["-ra", "-q"]
  timeout = 60
  timeout_method = "thread"     # <-- add immediately after pyproject.toml:89
  strict_markers = true
  ```
  `thread` is the only cross-platform-safe value (proved above), it matches `docs/reference/dep-test-and-lint-stack.md:13` and `docs/dependency-studies/pytest-timeout.md:180-184`, and it removes the platform branch from the house's only timeout policy: the Windows laptop and the Linux CI runner then take the *same* code path. **Do not pin `signal`** — it is an INTERNALERROR on Windows.
  Trade-off to accept explicitly when applying it: after the pin, a hang on **Linux CI** also hard-kills the run (`os._exit(1)`) instead of failing one test. That is the point of the pin (one deterministic policy instead of two), but it makes the CI backstop in F2 mandatory rather than optional. The alternative — leaving the default and passing `--timeout-method=signal` explicitly on the Linux CI step (`.github/workflows/app.yml:108`) — preserves CI's graceful single-failure behaviour but keeps the hard-kill as the permanent Windows default and formalises the local/CI divergence. **Recommended: pin `thread` + F2.**
- **Risk if ignored:** a single hanging test on the owner's Windows machine destroys the entire local run's output — the resulting signal ("pytest crashed, no summary") is materially worse than CI's ("1 failed, 54 passed, here is the stack"), and it hides the culprit behind dozens of never-run tests. A marginal overrun is enough: with `--timeout=1` and a test that sleeps exactly 1.0 s, the watchdog fired **mid-sleep in 2 of 3 runs** and killed the whole session (exit 1, second test never ran, no summary) — the 60 s budget includes fixture setup, so the effective body budget is slightly under 60 s.
- **Overlap note for the synthesis:** the same gap is filed by the sibling audits — `docs/swarm/dependency-utilization/pluggy.md` F1 (P2, "the owner hard-kills, CI fails one test") and `docs/swarm/dependency-utilization/iniconfig.md` *Verified-good list* (`:195`, which judged pinning "optional, not a defect" because the CI matrix is Linux-only). **This report owns the fix** (it is pytest-timeout's configuration) and adds the missing half of the argument: the divergence is **local-vs-CI**, not CI-vs-CI, and the house doc's prescribed pin is `thread` — which is the *only* value that runs on Windows at all. Please do not re-open it as three findings.

### F2 · P2 · Nothing bounds the CI job except the per-test guard: no `timeout-minutes`, no `session_timeout` — and after F1's pin a hung test takes the whole CI run with it

- **Where:** `.github/workflows/app.yml:40-41` (`quality:` job, `runs-on: ubuntu-latest` — no `timeout-minutes`), `:107-108` (the single `pytest` step), `:48-49` (`uv sync --frozen --group dev`), `:54-58` (the Flet API guard loop — one `python` process per `src/**.py` file); `.venv/Lib/site-packages/pytest_timeout.py:108` (`parser.addini("session_timeout", ...)`), `:164-175` (the `session_timeout` resolution), `:195-199` (the between-tests expiry check), `:49-53` (`SESSION_TIMEOUT_DESC`: *"Timeout is checked between tests, and will not interrupt a test in progress"*).
- **What:** the `quality` job inherits the GitHub Actions platform default job timeout — nothing in the workflow caps it. Two consequences: (a) a hang **outside** a test (the `uv sync` step, the per-file Flet API guard loop at `:54-58`, or the `ruff` step) is not covered by pytest-timeout at all and burns the platform default; (b) after F1's pin, a hang **inside** a test kills the entire pytest process on Linux CI too, so the job loses every other test's result instead of reporting one failure. The plugin ships the exact backstop for (b) — `session_timeout` — and the repo does not set it (`grep -n "timeout" pyproject.toml` → `:82`, `:89` only; the header prints no "session timeout" line).
- **Evidence:**
  ```
  $ grep -rn "timeout-minutes\|timeout_minutes" .github/
  (no output)
  $ grep -n "timeout" pyproject.toml
  82:    "pytest-timeout>=2.4.0",
  89:timeout = 60
  ```
  Session header of a live run — no session bound is in effect:
  ```
  timeout: 60.0s
  timeout method: thread
  timeout func_only: False
  ```
  (a "session timeout" line would be printed by `pytest_timeout.py:234-236` when `session_timeout` is set — it is absent.)
- **Fix / opportunity:** two optional one-liners, both inside the same policy surface:
  1. `.github/workflows/app.yml:40-41` — add `timeout-minutes: 15` to the `quality` job. The suite takes ~33 s locally (55 tests, live run: `2 failed, 53 passed in 32.85s` — the two failures are the pre-existing `LICENSES/` worktree deletions, see *Unverified*), so 15 minutes is generous and still bounds a wedged job at a fraction of the platform default.
  2. `pyproject.toml` — optionally `session_timeout = 900` next to `timeout = 60`, bounding the whole suite independently of the CI platform. Note it is checked **between** tests (`:195-199`), so it is a backstop for a pathological suite, not a substitute for the per-test guard. One caveat measured while testing this: an **ini-set** `session_timeout` is honoured by the plugin's logic (`:164-168` reads `config.getini("session_timeout")`) but is **not printed in the session header**, because the header reads only the CLI option (`:234-236`) — see F4. The CI log will therefore not advertise the session bound unless `--session-timeout` is also passed.
- **Risk if ignored:** a wedged CI job consumes the platform default before a human notices, and a single hanging test can erase the entire quality signal for the run. The house's stated purpose for this dependency (`docs/dependency-studies/pytest-timeout.md:206-209` — *"Session backstop protects release CI"*) is unmet.

### F3 · P2 · `pytest_enter_pdb` permanently disables the 60 s guard for the rest of the session — the guard vanishes exactly when a contributor is diagnosing a hang

- **Where:** `.venv/Lib/site-packages/pytest_timeout.py:248-259` (`pytest_enter_pdb` sets the module global `SUPPRESS_TIMEOUT = True`), `:278-280` (`is_debugging()` returns `True` when that global is set), `:300` (`SUPPRESS_TIMEOUT = False` — the only other assignment, at import time), `:492` and `:511` (both watchdog callbacks bail out when `is_debugging()` is true).
- **What:** once a contributor steps into `pdb` in a session (pytest's `--pdb`, or a `breakpoint()`/`pdb.set_trace()` in a test), `SUPPRESS_TIMEOUT` is set to `True` and **nothing ever resets it**. From that moment on the watchdog fires, sees `is_debugging() == True`, and returns without failing — so the 60 s guard is silently inert for the rest of that pytest session. The house's most likely use of `pdb` is exactly the scenario the dependency study calls out (`docs/dependency-studies/pytest-timeout.md:176-178`: *"**Debugger interplay.** `breakpoint()` under a running timer fires the timeout unless detection is on (default) or the marker disables it — document for contributors debugging ProotSession tests locally."*) — i.e. debugging a hang — and that is precisely when the guard stops working.
- **Evidence:** (throwaway `conftest.py` outside the repo that reproduces what `pytest_enter_pdb` does, vs. a control without it; `--timeout=2`, the test sleeps 5 s)
  ```
  # conftest.py
  import pytest_timeout
  pytest_timeout.pytest_enter_pdb()

  $ pytest -o addopts="" --timeout=2 --timeout-method=thread -q test_pdb.py ; echo EXIT=$?
  ..                                                                       [100%]
  2 passed in 5.38s
  EXIT=0
  ```
  The 5 s sleep blew the 2 s budget and **passed**; the second test ran (session intact). Control, same file, no `conftest.py`:
  ```
  $ pytest -o addopts="" --timeout=2 --timeout-method=thread -q test_pdb.py ; echo EXIT=$?
  ... File "test_pdb.py", line 4, in test_a_hangs_5s
      time.sleep(5)
  +++++++++++++++++++++++++++++++++++ Timeout +++++++++++++++++++++++++++++++++++
  EXIT=1
  summary: (none)      # second test never ran
  ```
  The only difference between the two runs is the `SUPPRESS_TIMEOUT` global.
- **Fix / opportunity:** no config change can restore the guard mid-session — it is a plugin-side sticky global. Two cheap mitigations, in order of value:
  1. **Document it** in `docs/reference/dep-test-and-lint-stack.md` next to the existing pytest-timeout note: *"after stepping into `pdb` in a session, the 60 s timeout is disabled for the rest of that session — restart pytest to get it back."*
  2. **Use the one working escape hatch** when you want the guard to survive a debugger session: `--timeout-disable-debugger-detection` (`:84-89`). Note the **ini key of the same name is dead** — see F4 — so it must be passed on the command line.
- **Risk if ignored:** a contributor debugging a suspected hang with `pdb` concludes "pytest-timeout is not working" (or worse, trusts that the 60 s bound is still protecting the suite while it is not). CI is unaffected — CI never enters `pdb` — so this is a local-debug-loop defect, not a CI one.

### F4 · P3 · The `timeout_disable_debugger_detection` **ini key is dead code** in 2.4.0 — and the `session_timeout` ini key is honoured but invisible in the header: the house cannot express either policy in `pyproject.toml`

- **Where:** `.venv/Lib/site-packages/pytest_timeout.py:84-89` (`--timeout-disable-debugger-detection` registered with `action="store_true"` → its default is `False`, **not** `None`), `:102-107` (`parser.addini("timeout_disable_debugger_detection", ..., type="bool", default=False)` — the ini key exists and is registered), `:377-383` (`get_env_settings`: `disable_debugger_detection = config.getvalue("timeout_disable_debugger_detection")`; the ini is consulted **only** `if disable_debugger_detection is None:`); the milder second instance at `:234-236` (`pytest_report_header` reports `config.getoption("session_timeout")` only — never the ini value) versus `:164-168` (the plugin's *logic* does read `config.getini("session_timeout")`).
- **What:** `action="store_true"` gives the option a default of `False`, so `config.getvalue(...)` is never `None` → the `if ... is None:` guard at `:378` is never true → **the ini value is never read**. The key is registered and accepted by pytest (`--help` lists it as `timeout_disable_debugger_detection (bool):`), but setting it in `pyproject.toml` has no effect. This is the only one of the five ini keys whose *value* is dead: `timeout` (`:357`, option default `None`), `timeout_method` (`:367`, both options default `None`), `session_timeout` (`:164`, explicit `default=None`) and `timeout_func_only` (`:375`, no CLI option at all) all fall through to the ini correctly. The **same `getoption`-vs-`getini` split** makes `session_timeout` milder-dead: an ini-set value *is* honoured by the plugin's logic (`:164-168`) but the session header never prints it (`:234-236` reads the CLI option only) — so a policy written in `pyproject.toml` is invisible in the CI log, contradicting the study's claim that *"CI logs self-describe their timeout policy"* (`docs/dependency-studies/pytest-timeout.md:144-146`).
- **Evidence:**
  ```
  # conftest.py
  def pytest_configure(config):
      print("GETVALUE:", repr(config.getvalue("timeout_disable_debugger_detection")))
      print("GETINI:", repr(config.getini("timeout_disable_debugger_detection")))

  $ pytest -q -s test_x.py
  GETVALUE: False      # <- never None, so the ini branch at :378 is dead
  GETINI: False

  $ pytest -o timeout_disable_debugger_detection=true -q -s test_x.py
  GETVALUE: False      # still False
  GETINI: True         # the ini value is set ... and ignored

  $ pytest --timeout-disable-debugger-detection -q -s test_x.py
  GETVALUE: True       # only the CLI flag works
  GETINI: False
  ```
  Behavioural confirmation: with the pdb simulation of F3 active, `-o timeout_disable_debugger_detection=true` did **not** restore enforcement (`2 passed in 5.38s`, exit 0) — exactly as the code path predicts; the CLI flag does.
  The milder second instance — an ini-set `session_timeout` is honoured but not reported:
  ```
  $ pytest -o addopts="" -o session_timeout=900 --collect-only | head -8
  plugins: anyio-4.15.1, flet-1.0.4, timeout-2.4.0
  collected 1 item                       # <- no "session timeout:" line

  $ pytest -o addopts="" --session-timeout=900 --collect-only | head -8
  plugins: anyio-4.15.1, flet-1.0.4, timeout-2.4.0
  session timeout: 900.0s                # <- CLI only
  ```
- **Fix / opportunity:** if the house ever wants "the timeout always fires, even inside `pdb`", it must be passed as the CLI flag, e.g. `.github/workflows/app.yml:108` → `uv run pytest -q -m "not live" --timeout-disable-debugger-detection`. Do **not** put it in `pyproject.toml` — it would be silently ignored (and `strict_config = true` would not catch it, because the key *is* registered).
- **Risk if ignored:** a policy written into `pyproject.toml` as `timeout_disable_debugger_detection = true` reads as enforced in review and in the config file, but is inert at runtime — a silent no-op in the one place the house believes it has a safety setting.

### F5 · P3 · The dependency study's kill-semantics claim is wrong in the one place that matters — and one of its API claims does not exist

- **Where:** `docs/dependency-studies/pytest-timeout.md:104-109` (*"**exact kill semantics unverified** beyond timer + dump + fail — the plugin reports the timeout; it does not `SIGKILL` the test"*), `:164-165` (*"but the underlying thread may linger until the process exits"*), `:161-166` (caveat 2, *"No preemption of native blocks"*), `:30` (the CLI-flag table lists *"--timeout-func-only / ini `timeout_func_only`"* with the exact spelling marked unverified); against `.venv/Lib/site-packages/pytest_timeout.py:505-542` (`timeout_timer`), `:326-335` (thread arming), `:485-503` (`timeout_sigalrm`), `:64-98` (the real option list).
- **What:** the study hedged the single most consequential fact about this plugin and hedged it wrongly. In the **thread** method the plugin does not "report the timeout" — it **kills the whole process** with `os._exit(1)` (`:542`), which is strictly stronger than `SIGKILL`ing the test and is not recoverable by any `finally`/teardown. The "thread may linger until the process exits" caveat describes the *signal* method, not the thread method — and the "no preemption of native blocks" caveat is inverted for the thread method: the watchdog is an independent `threading.Timer` thread (`:327`), so it fires on schedule even while the main thread is blocked inside a C call. Two smaller corrections: **there is no `--timeout-func-only` CLI flag in 2.4.0** (the ini key `timeout_func_only` exists at `:101`; there is no CLI counterpart — the real option list is `--timeout`, `--timeout_method` (deprecated), `--timeout-method`, `--timeout-disable-debugger-detection`, `--session-timeout`), and the study's open item "type/default **unverified**" for `disable_debugger_detection` is now resolved: `type="bool", default=False` (`:102-107`).
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -m pytest -o addopts="" --help | grep -i timeout
  --timeout=TIMEOUT
  --timeout_method={signal,thread}      Deprecated, use --timeout-method
  --timeout-method={signal,thread}
  --timeout-disable-debugger-detection
  --session-timeout=SECONDS
  ```
  (no `--timeout-func-only` in the output.)
  ```
  $ .venv/Scripts/python.exe -m pytest -o addopts="" --help | grep -E "^  (timeout|session_timeout)"
  timeout (string):
  timeout_method (string):
  timeout_func_only (bool):
  timeout_disable_debugger_detection (bool):
  session_timeout (string):
  ```
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  101:    parser.addini("timeout_func_only", FUNC_ONLY_DESC, type="bool", default=False)
  102:    parser.addini(
  103:        "timeout_disable_debugger_detection",
  ...
  107:    )
  ```
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  326:    elif timeout_method == "thread":
  327:        timer = threading.Timer(settings.timeout, timeout_timer, (item, settings))
  ...
  542:        os._exit(1)
  ```
- **Fix / opportunity:** correct `docs/dependency-studies/pytest-timeout.md` §2.2 (replace "it does not `SIGKILL` the test" with "in the `thread` method it terminates the whole pytest process via `os._exit(1)` — no teardown, no summary, exit code 1"), §4 caveat 2 (move "no preemption of native blocks" to the `signal` column — the `thread` watchdog fires independently of the main thread), and §1.2 (drop `--timeout-func-only`; the ini key exists, the flag does not). Add the resolved `disable_debugger_detection` type/default. The study is the artifact the owner consults before touching the dependency set, and its §2.2 currently understates the blast radius of a hang.
- **Risk if ignored:** the next agent (or the owner) reads "the plugin reports the timeout; it does not kill the test", assumes a hang costs one test, and ships a CI setup where a hang silently costs the whole run.

### F6 · P3 · The first test that opens a real PTY will inherit the hard-kill cleanup gap: `os._exit(1)` skips the teardown that reaps the guest shell

- **Where:** `src/services/session_service.py:95-134` (`ProotSession.start()`: `pty.openpty()` at `:100`, `subprocess.Popen(...)` at `:101-109`, a daemon reader thread at `:133-134`), `:152-165` (`stop()` → `process.terminate()` + `process.wait(timeout=2)`), `:167-172` (`__enter__`/`__exit__` → `stop()`); `.venv/Lib/site-packages/pytest_timeout.py:542` (`os._exit(1)`), `:326-335` (thread watchdog); `tests/test_sessions.py:101-112` (the only `ProotSession` tests — a session that is **never started**).
- **What:** today no test opens a PTY (`grep -rn "\.start()\|ProotSession(" tests/` → only the constructor at `tests/test_sessions.py:103` and `:110`; `start()` is never called), so the gap is latent. The moment a test calls `ProotSession.start()`, the child process (`/bin/bash -l` under proot, `src/services/session_service.py:101-109`) plus the PTY master fd become resources that only `stop()` reaps — and `stop()` runs from teardown / `__exit__`. With the `thread` method (the Windows default today, and the value F1 proposes pinning) a timeout calls `os._exit(1)`, which **skips every teardown in the process**: the guest shell is never terminated, the PTY master fd is closed by the OS rather than by `stop()`, and the pytest run dies mid-test. With the `signal` method the exception unwinds normally, `__exit__` runs, and the child is reaped — so the *method choice* silently changes the cleanup semantics of any future PTY test.
- **Evidence:**
  ```
  $ grep -rn "\.start()\|ProotSession(" tests/
  tests/test_sessions.py:103:    session = session_service.ProotSession(["/bin/true"], {}, received.append)
  tests/test_sessions.py:110:    session = session_service.ProotSession(["/bin/true"], {}, lambda _b: None)
  ```
  ```
  src/services/session_service.py
  100:        master_fd, slave_fd = pty.openpty()
  101:        self._process = subprocess.Popen(
  ...
  133:        self._reader = threading.Thread(target=_read_loop, daemon=True)
  152:    def stop(self) -> None:
  ...
  162:                process.terminate()
  164:                process.wait(timeout=2)
  ```
  ```
  .venv/Lib/site-packages/pytest_timeout.py
  542:        os._exit(1)     # <- no teardown, no atexit, no fixture finalizers
  ```
  The teardown-skip is observable in the F1 experiment: the killed run produced **no summary line at all**, i.e. pytest never reached its teardown phase.
- **Fix / opportunity:** when the first PTY test lands, it must reap the child itself — wrap the session in `try/finally` (or `with ProotSession(...)`, whose `__exit__` calls `stop()`, `src/services/session_service.py:171-172`) **inside the test body**, so the cleanup does not depend on pytest teardown that a hard-kill can skip. Do not rely on a fixture finalizer for a child process. This is a note for the future PTY test, not a change to today's suite.
- **Risk if ignored:** a hung PTY test leaves an orphaned guest shell (proot + `/bin/bash`) on the developer machine or the CI runner, invisible because the run was killed before any report.

## Missed capabilities (dependency audits only)

- **`session_timeout` — a whole-suite bound that is switched off** (`pytest_timeout.py:108` ini key; resolved at `:164-175`; checked between tests at `:195-199`; semantics note at `:49-53`: *"Timeout is checked between tests, and will not interrupt a test in progress"*). *Integration point:* one line in `[tool.pytest.ini_options]` next to `timeout = 60` (`pyproject.toml:89`) — e.g. `session_timeout = 900`. *Value vs cost:* it bounds a pathological suite (55 tests × 60 s = 55 min of hanging) independently of the CI platform's job default, which F2 shows is unbounded today; it is the only pytest-timeout capability that survives a per-test guard that cannot interrupt a running test. *Cost:* one ini line; *risk:* it must not be confused with an interrupt — it never kills a running test, and an ini-set value is not echoed in the session header (F4), so pass `--session-timeout` too if the CI log must show it.
- **`timeout_func_only` — defer the budget to the test body** (`pytest_timeout.py:101` ini key, `type="bool", default=False`; per-marker keyword `func_only=True` at `:145-151`; the arming split at `:189`/`:192` vs `:212`/`:215`). *Integration point:* a `@pytest.mark.timeout(300, func_only=True)` on the future **live**/device tests — the house already anticipated this (`docs/dependency-studies/pytest-timeout.md:188-191`: *"`live` (device) tests: allow per-test `@pytest.mark.timeout(300, func_only=True)` for on-device install flows"*). *Value vs cost:* high when the first device test lands (a distro image install is a slow *fixture*, not a slow assertion, and would otherwise eat the 60 s body budget); zero cost today (no test carries the marker: `grep -rn "pytest.mark" tests/` → no output).
- **The per-item `timeout` marker** (`pytest_timeout.py:141-156`; parsing at `:412-446`; per-item override precedence at `:388-409`). *Integration point:* per-test budget overrides — e.g. a slow-but-legitimate test gets `@pytest.mark.timeout(120)` while everything else stays at 60 s. *Value vs cost:* low today (55 fast, offline tests), but it is the mechanism the house needs to give a legitimately slow test more room **without** raising the global budget that catches real hangs. Note the marker keyword is `timeout`/`method`/`func_only` only — `disable_debugger_detection` is accepted by the *registration text* (`:145-151`) but `_parse_marker` raises `TypeError` for it (`:428-429`) — **UNVERIFIED-by-execution**, source-proven.
- **`--timeout-disable-debugger-detection` — the only working knob for the sticky debugger suppression** (`pytest_timeout.py:84-89`; the ini twin is dead, F4). *Integration point:* the CI pytest step (`.github/workflows/app.yml:108`) or a local alias; plus a sentence in `docs/reference/dep-test-and-lint-stack.md` about F3. *Value vs cost:* small but real — it is the difference between "the 60 s guard is still on" and "the guard vanished when I opened pdb".
- **pytest's own free watchdogs — `faulthandler_timeout` and `faulthandler_exit_on_timeout`** (shipped by pytest itself, visible in `pytest --help`; not a new dependency). *Integration point:* optional `--faulthandler-timeout` alongside the pytest-timeout settings. *Value vs cost:* low — it dumps all thread tracebacks to stderr and (with `faulthandler_exit_on_timeout`) exits the process, but it does **not** fail the test, so pytest-timeout remains the reporting mechanism; it is a cheap second pair of eyes for native-level hangs, not a replacement. Listed for completeness so the synthesis does not mistake it for an unused dependency.

## Verified-good list

- **Every API and line reference in `docs/dependency-studies/pytest-timeout.md` was spot-checked against the installed 2.4.0 and is accurate**, except the three items corrected in F5: `HAVE_SIGALRM`/`DEFAULT_METHOD` at `:26-30`; `parser.addini` block at `:99-108`; CLI options at `:64-98` (the study's table has one flag that does not exist); the marker registration at `:141-156`; `pytest_runtest_protocol` at `:178-199` (`:189`/`:192` gate on `func_only is False`); `pytest_runtest_call` at `:202-216` (`:212`/`:215` gate on `func_only is True`); `pytest_report_header` at `:219-238`; `is_debugging` at `:262-297`; the `signal` arming at `:313-325`; the `thread` arming at `:326-335`; the `signal`→`thread` fallback off the main thread at `:306-311`; `get_env_settings` precedence (env > ini > default) at `:352-385`; `_get_item_settings` at `:388-409`; `_parse_marker` at `:412-446`; `dump_stacks` at `:545-558`.
- **The study's §1.4 precedence claim is confirmed by the installed code**: env > config file > default for the timeout (`:357-365`) and for the method (`:367-373`), and `PYTEST_TIMEOUT` is validated by `_validate_timeout` (`:359-361`, `:449-455`). No `PYTEST_TIMEOUT` is set in the repo or in CI (`env | grep -i pytest` → not set; `.github/workflows/app.yml:29-37` defines no such variable), so the ini value is what is in force.
- **`timeout = 60` is honoured**: the live header prints `timeout: 60.0s` (`pytest_report_header`, `:219-238`). The value flows `pyproject.toml:89` → `getini("timeout")` (`:363`) → `config._env_timeout` (`:159`) → `_get_item_settings` fallback (`:401-402`) → armed in `pytest_runtest_protocol` (`:188-190`).
- **The plugin is auto-loaded and its keys are real**: the header lists `timeout-2.4.0` among the plugins; `pytest --help` lists all five ini keys (`timeout`, `timeout_method`, `timeout_func_only`, `timeout_disable_debugger_detection`, `session_timeout`) and all five CLI options. `strict_config = true` (`pyproject.toml:91`) means a missing plugin would fail the session loudly rather than silently disable the guard (`ERROR: Unknown config option: timeout`) — the guard is not optional-by-accident.
- **The timeout covers setup + call + teardown** (`func_only = False`, header-confirmed): the watchdog is armed in `pytest_runtest_protocol` (`:189-190`) and cancelled in the same hook's teardown (`:192-193`), so a hang in a fixture is caught too, and the timer is always disarmed on a clean exit (`:330-332` `timer.cancel(); timer.join()` — no timer thread outlives its test).
- **The test suite is entirely timeout-safe today — it spawns nothing.** `grep -rn "sleep(\|input(\|urlopen\|httpx\|requests\.\|socket\.\|while True\|Popen\|check_output\|os.system\|multiprocessing\|Thread" tests/` returns only four `asyncio.run(...)` calls (`tests/test_ads.py:27`, `:36`, `:45`, `:56`), each of which creates and closes its own event loop. No test opens a PTY (`ProotSession.start()` is never called — F6). The app's only real subprocess (`src/core/proot_probe.py:116`, `subprocess.run([PD_PROOT_BIN, "--version"], ..., timeout=30)`) is **unreachable from the suite**: `bootstrap_env` returns early at `src/core/proot_probe.py:72-74` when `_native_library_dir()` is `None` (`:26-35`), which is the case on a desktop without `ANDROID_NATIVE_LIBRARY_DIR` — and the test that calls `bootstrap_env` deletes that variable first (`tests/test_core.py:82`, `:87`). The inner `timeout=30` (`src/core/proot_probe.py:119`) is in any case below the 60 s budget.
- **A full live run of the suite completes in ~33 s** — two orders of magnitude under the 60 s per-test budget, so the guard never fires spuriously (`pytest -m "not live"` → `2 failed, 53 passed in 32.85s`; the two failures are the pre-existing `LICENSES/` worktree deletions — see *Unverified*).
- **The stack dump on timeout is the diagnostic the house wants**: `dump_stacks` (`:545-558`) prints every thread's stack with its name and ident, and on the `thread` path the captured run shows the hung test's frame (`time.sleep(60)` at the bottom of `Stack of MainThread`), because the watchdog runs in its own thread and therefore skips only itself (`:547-550`).
- **The `live` marker pair is already declared and deselected in CI** (`pyproject.toml:92-94`, `.github/workflows/app.yml:108`) — but no test carries it (`grep -rn "pytest.mark" tests/` → no output), so the deselection guards nothing today. Already reported by the sibling `docs/swarm/dependency-utilization/iniconfig.md` F7; listed here only so the synthesis does not re-open it as a pytest-timeout finding.

## Unverified

- **The Linux / `signal` path was not executed in this environment** — the only runtimes available are Windows (`platform win32`, Python 3.14.7); `wsl -l -v` reports *"The Windows Subsystem for Linux is not installed"* and `docker` is not on PATH. The claim *"one test fails, the run continues, a summary is printed"* on Linux CI is derived from the installed source (`timeout_sigalrm` → `pytest.fail(...)`, `pytest_timeout.py:502`; the `Failed` exception is raised inside the test call, so pytest reports one failure and continues) and from the header/ini plumbing, not from an observed Linux run.
- **Whether the SIGALRM Python handler is deferred when the main thread is blocked in a C call that does not return EINTR** (e.g. a wedged `socket.recv` or a native extension). Source-level reasoning only: the Python-level handler runs at the next interpreter checkpoint, so the `signal` method may report a timeout later (or not at all) than the `thread` watchdog, which fires from an independent thread (`:327`). Not executed here.
- **Whether the guest shell spawned by `ProotSession.start()` survives the death of its parent pytest process** (F6). The *teardown-skip* half is proven from `os._exit` semantics and from the observed absence of a pytest summary in the killed runs; whether the orphaned `proot`/`bash` child is reaped by the kernel when the PTY master closes (SIGHUP to the session leader) could not be tested here — no PTY/proot on this host.
- **GitHub Actions' default job timeout (360 minutes)** is an external platform fact, not observed here; the verified claim is only that the workflow sets no `timeout-minutes` (F2).
- **The two pre-existing failures in `tests/test_ui_reactive.py`** (`test_license_texts_are_present_and_shipped` at `:175`, `test_licenses_view_carries_real_text` at `:200`) are caused by `src/LICENSES/` and `LICENSES/` being **deleted in the working tree** (`git status --porcelain` → ` D LICENSES/*.txt`, ` D src/LICENSES/*.txt`, plus other pre-existing deletions and `?? docs/swarm/`). That deletion predates this audit (it was present before this session's first command) and is **not** caused by anything pytest-timeout does. Not diagnosed and not restored (BRIEF rule 1: read-only apart from this report) — it is a worktree-coordination question for the orchestrator.
- **The `disable_debugger_detection` marker keyword** — the marker registration text advertises it (`pytest_timeout.py:145-151`) but `_parse_marker` raises `TypeError` for any keyword outside `timeout`/`method`/`func_only` (`:428-429`). Source-proven, not executed.
