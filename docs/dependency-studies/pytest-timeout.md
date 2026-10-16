# pytest-timeout 2.4.0 — Exhaustive API Reference

**Identity:** `pytest-timeout` 2.4.0 · MIT · `Requires-Python: >=3.7`
(`pytest_timeout-2.4.0.dist-info/METADATA`). Single-module plugin:
`.venv/Lib/site-packages/pytest_timeout.py` (~450 lines). All line numbers
below refer to that file. Verification: source read + `pytest --markers`
output. Unverifiable items marked **unverified**.

---

## 1. Configuration surface

### 1.1 ini keys (`parser.addini`, :99-108)

| Key | Type / default | Description constant |
|---|---|---|
| `timeout` | float-as-string, no default (none) | `TIMEOUT_DESC`: "Timeout in seconds before dumping the stacks. Default is 0 which means no timeout" (:32) |
| `timeout_method` | string, no default (falls back to `DEFAULT_METHOD`) | `METHOD_DESC` |
| `timeout_func_only` | `type="bool"`, `default=False` | `FUNC_ONLY_DESC` |
| `disable_debugger_detection` | (`addini` line at :102-107; type/default **unverified** — not captured in survey grep) | debugger-detection toggle |
| `session_timeout` | string/float, default None | `SESSION_TIMEOUT_DESC`: "Timeout in seconds for entire session. Default is None which means no timeout" (:50) |

### 1.2 CLI flags (`pytest_addoption`, :64-93)

| Flag | Type | Notes |
|---|---|---|
| `--timeout` | `type=float` | per-test timeout seconds (:70) |
| `--timeout-method` | `dest="timeout_method"` (:78) | `signal` \| `thread`; current canonical flag |
| `--timeout_method` | underscore variant (:72) | **Deprecated**, "use --timeout-method" (:75) |
| `--timeout-func-only` / ini `timeout_func_only` | (**exact CLI spelling unverified** — `FUNC_ONLY_DESC` exists; flag name not captured) | defers timer to test body only |
| `--session-timeout` | `dest="session_timeout"` (:91) | whole-session deadline |

### 1.3 `timeout` marker (registered in `pytest_configure`, :141-151)

```
timeout(timeout, method=None, func_only=False, disable_debugger_detection=False)
```

Verbatim from `:145-151`: "Set a timeout, timeout method and func_only
evaluation on just one test item. The first argument, *timeout*, is the
timeout in seconds while the keyword, *method*, takes the same values as the
`--timeout-method` option. The *func_only* keyword, when set to True, defers
the timeout evaluation to only the test function body, ignoring the time it
takes when evaluating any fixtures used in the test. The
*disable_debugger_detection* keyword, when set to True, disables debugger
detection, allowing `breakpoint()`, `pdb.set_trace()`, etc. to be
interrupted." (Also visible in `pytest --markers` output.)

Marker parsing (`_parse_marker`, :412+): positional `timeout` = first arg,
`method` = second positional if present; keywords `timeout`/`method`/
`func_only` likewise; per-item settings override env/config
(`_get_item_settings`, :388-409).

### 1.4 Environment variable

`PYTEST_TIMEOUT` (read in `get_env_settings`, :359-360): validated via
`_validate_timeout(os.environ.get("PYTEST_TIMEOUT"), "PYTEST_TIMEOUT
environment variable")`. Precedence (verified `:352-385`): **env >
config file > default** for timeout; same lookup shape for method, falling
back to `DEFAULT_METHOD` (:373) when neither env (`config.getvalue`,
:367) nor ini (:369-371) provides one.

### 1.5 `Settings` namedtuple (:59)

```python
Settings = namedtuple("Settings", ["timeout", "method", "func_only",
                                   "disable_debugger_detection"])
```

---

## 2. ALL method semantics — `thread` vs `signal`

Default selection (`:28-30`, verified):

```python
# posix with SIGALRM:
DEFAULT_METHOD = "signal"
# otherwise (Windows):
DEFAULT_METHOD = "thread"
```

Enforced fallback (`pytest_timeout_set_timer`, :304-311): if
`timeout_method == "signal"` **and** running on a non-main thread
(`threading.current_thread() is not threading.main_thread()`), the method
silently degrades to `"thread"`.

### 2.1 `signal` method (:313-324)

- Installs a `SIGALRM`-based handler (`handler(signum, frame)` at :315) for
  `settings.timeout` seconds; `cancel()` (:319) disarms on test end.
- Interrupts even blocked C calls on POSIX — true preemption, but
  process-wide signal state: incompatible with threads other than main and
  with debuggers unless detection disabled.
- House rule: **do NOT use** — platform-dependent (Linux-only), breaks
  Windows/Linux CI parity.

### 2.2 `thread` method (:326+, verified start)

- `timer = threading.Timer(settings.timeout, timeout_timer, (item, settings))`
  (:327): a watchdog thread fires after the deadline and fails the test
  (`timeout_timer` → marks timeout, dumps stacks, fails the item).
- `cancel()` (:330) cancels the timer on clean completion.
- Cooperative: only fires between bytecode steps of the test thread; a test
  stuck inside a non-releasing C call or `threading.Lock` may not die
  promptly (**exact kill semantics unverified** beyond timer + dump + fail —
  the plugin reports the timeout; it does not `SIGKILL` the test).
- Deadlock risk where the timed-out test holds a lock the teardown needs
  (**unverified** — standard `threading.Timer` caveat, noted as caution).

### 2.3 `func_only` semantics

- `False` (default): timer arms in `pytest_runtest_protocol` (:179-199
  region — timer set around setup+call+teardown; verified `:189,192` gate on
  `settings.func_only is False`).
- `True`: timer arms only in `pytest_runtest_call` (:203-215 region; `:212,215`
  gate on `func_only is True`) — slow fixtures (downloading a fixture image,
  building a fake rootfs) don't consume the budget.
- House: default `False` is fine; set per-test `func_only=True` only for tests
  with deliberately slow fixtures.

### 2.4 `session_timeout`

- Read from `--session-timeout` option or `session_timeout` ini, validated by
  `_validate_timeout` (:164-168).
- Stored on `config.stash[SESSION_TIMEOUT_KEY]` / `SESSION_EXPIRE_KEY`;
  checked in `pytest_runtest_protocol` (:195-199): when the deadline passes,
  `item.session.shouldfail = f"session-timeout: {timeout} sec exceeded"`.
- Whole-suite backstop against a hung CI job (complements, not replaces, the
  CI job-level timeout).

---

## 3. Stack-dump behavior

`dump_stacks(terminal)` (verified source): iterates `sys._current_frames()`,
skips the current thread, resolves each ident to a `threading.enumerate()`
name (fallback `"<unknown>"`), and writes
`terminal.sep("~", title="Stack of %s (%s)")` + `traceback.format_stack(frame)`
per thread. Triggered on timeout before failing the item, so CI logs show
*where* every thread was stuck — the primary diagnostic for ProotSession
hangs (which thread is in `wait()`, which in socket read, etc.).

`pytest_report_header` (`:220-236`, verified) prints the effective
`timeout / timeout method / timeout func_only` (+ session timeout when set)
in the test-session header — CI logs self-describe their timeout policy.

`pytest_exception_interact` (`:242`) and `pytest_enter_pdb` (`:249`) hooks
wire debugger interaction; `is_debugging(trace_func=None)` (`:262`) detects
an active debugging session so timers don't fire mid-breakpoint (defeated
per-test by `disable_debugger_detection=True`).

---

## 4. Thread-method caveats on Windows

1. **Default is already `thread` on Windows** (`DEFAULT_METHOD`, :30) — but
   Linux CI would silently use `signal` without the pin. House pins
   `timeout_method = "thread"` so both platforms behave identically
   (verified D4 study + roadmap M5 CI note).
2. **No preemption of native blocks.** A test hung inside a native call that
   never returns to the interpreter (e.g. a wedged subprocess `wait()` —
   directly relevant to future ProotSession spawn tests) will be *reported*
   at the deadline with full stack dumps, but the underlying thread may
   linger until the process exits. Keep `timeout = 60` plus a CI job timeout
   as the real backstop.
3. **`threading.Timer` is itself a thread.** Massively parametrized suites
   create/cancel one timer per test — negligible overhead, but a test that
   spawns non-daemon threads and times out can keep the worker alive past the
   report. Prefer `asyncio.to_thread`-based service code with its own
   cancellation over raw threads in tests.
4. **Debugger interplay.** `breakpoint()` under a running timer fires the
   timeout unless detection is on (default) or the marker disables it —
   document for contributors debugging ProotSession tests locally.

---

## 5. House timeout policy (this project)

```toml
[tool.pytest.ini_options]
timeout = 60
timeout_method = "thread"
```

- `60` matches sibling-app house style; long enough for fake-rootfs builds,
  short enough to fail fast on deadlocks.
- `live` (device) tests: allow per-test
  `@pytest.mark.timeout(300, func_only=True)` for on-device install flows;
  deselected (`-m "not live"`) on desktop CI so they never consume the
  default budget there.
- Never set `timeout = 0`/disable globally to "fix" a hanging test — the
  stack dump is the diagnosis; fix the hang.

---

## 6. How this dependency makes our app significantly better than Termux's proot-distro

1. **Hangs become failing tests with stack dumps, not mystery CI timeouts.**
   ProotSession work (spawn, stdin pump, resize, exec) is exactly the code
   that deadlocks. With `timeout=60/thread`, a deadlock fails in 60 s with
   every thread's stack in the log — Termux contributors debug hangs by
   re-running shell by hand on a phone.
2. **Uniform Windows/Linux behavior.** Contributors run `uv run pytest` on
   Windows laptops while CI runs Linux; the `thread` pin means a timeout that
   passes locally passes in CI. Termux testing is Android-only by
   construction, so they never even get a fast desktop loop.
3. **Session backstop protects release CI.** `session_timeout` bounds the whole
   quality job — a pathological hang can't burn the entire CI budget before
   the build matrix starts. Termux has no equivalent gate between "test" and
   "release".

## 7. Verification refs

- Identity: `pytest_timeout-2.4.0.dist-info/METADATA`.
- All code refs: `.venv/Lib/site-packages/pytest_timeout.py` lines cited
  inline (§1–§4). Marker text: `pytest --markers` + `:141-151`.
- `DEFAULT_METHOD` platform conditional `:28-30`; thread fallback `:304-311`;
  timer creation `:327`; env/config/default precedence `:352-385`;
  per-item override `:388-409`; marker parsing `:412+`.
- House policy: `docs/reference/dep-test-and-lint-stack.md`,
  `docs/roadmap.md` M5.
