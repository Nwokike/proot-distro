# colorama 0.4.6 — Exhaustive API Reference

**Identity:** `colorama` 0.4.6 · "Cross-platform colored terminal text"
(`colorama-0.4.6.dist-info/METADATA`). Role in our stack: transitive
dependency — pytest uses it for Windows ANSI terminal output; flet-cli pulls
it via `qrcode`/CLI output paths (D1 study: "qrcode/colorama = `flet run`
device-connect extras, zero build relevance"). Pure-Python, ships nothing to
the APK. Verification: source grep + live `inspect.signature`. Unverifiable
items marked **unverified**.

---

## 1. Complete API with signatures

Module layout verified: `colorama/__init__.py`, `initialise.py`, `ansi.py`,
`ansitowin32.py`, `win32.py`, `winterm.py`, `tests/`.

### 1.1 `initialise.py` (verified def lines)

```python
init(autoreset=False, convert=None, strip=None, wrap=True)   # :37
deinit()                                                      # :65
reinit()                                                      # :104
just_fix_windows_console()                                    # :72
colorama_text(*args, **kwargs)                                # :96
wrap_stream(stream, convert, strip, autoreset, wrap)           # :111
reset_all()                                                   # :32
_wipe_internal_state_for_tests()                              # :9 (test helper)
```

- `init(autoreset=False, convert=None, strip=None, wrap=True)` — wrap
  `sys.stdout`/`sys.stderr` in `AnsiToWin32` so ANSI escape sequences render
  on Windows consoles; on non-Windows it is effectively a no-op passthrough
  (platform-branch details **unverified** — behavior described from API
  shape, not traced per-branch).
- `just_fix_windows_console()` — no-arg (signature verified `()`); enables
  Windows VT processing / wrapping without touching autoreset/strip state.
  This is the modern minimal call — pytest's Windows terminal support path
  uses this shape rather than full `init` (**exact pytest call site
  unverified**).
- `deinit()` / `reinit()` — unwrap / re-wrap the streams.
- `colorama_text(*args, **kwargs)` — context manager form (args **unverified**).
- `wrap_stream(...)` — wrap an arbitrary stream (signature above; per-arg
  semantics **unverified**).
- `reset_all()` — emit reset sequences.

### 1.2 `ansitowin32.py` (verified class lines)

- `StreamWrapper(object)` (`:16`) — delegates attributes to the wrapped
  stream (exact delegation surface **unverified**).
- `AnsiToWin32(object)` (`:72`) — converts ANSI sequences to Win32 console
  calls; `convert`/`strip`/`autoreset` behavior flags (constructor signature
  **unverified**).

### 1.3 `ansi.py` / `win32.py` / `winterm.py` (inventory only)

- `ansi.py`: `Fore`/`Back`/`Style` color constants + `Cursor` positioning
  (**names unverified** — conventional colorama surface, not read in this
  survey).
- `win32.py` / `winterm.py`: Win32 API bindings and terminal-state helpers
  (**details unverified** — Windows-only internals, irrelevant to our usage).

## 2. Why present in our stack

1. **pytest terminal colors on Windows.** Contributors run `uv run pytest` on
   Windows; colorama makes `-v` output, failure highlighting, and the
   timeout-report header readable there. No config needed — autoloaded with
   pytest's terminal reporter.
2. **flet-cli `flet run` output.** The device-connect QR + log output path
   formats through colorama-backed streams (D1). Zero build relevance, zero
   APK content.
3. **Nothing to configure, nothing to gate.** No ini keys, no markers, no
   version floors needed. It appears in the lockfile only as a transitive
   dep. The house `test_imports_vs_deps.py` guard should list it as an
   allowed transitive (pytest/flet-cli support) rather than a direct import.

---

## 3. How this dependency makes our app significantly better than Termux's proot-distro

Honestly: colorama itself confers no app advantage — it is terminal
cosmetics for the dev loop. Its *presence* is still a marker of the deeper
gap:

1. **Readable Windows test output keeps desktop CI contributors.** Colored
   pass/fail/skip reporting + the timeout header's stack dumps are legible on
   a contributor's Windows laptop without WSL. Termux development happens
   exclusively inside Termux on-device with monochrome shell echo — the
   contributor funnel is everyone willing to type on a phone.
2. **Zero-cost transitive hygiene.** Because colorama is pure-Python and
   build-inert, it costs the APK nothing while improving every local test
   run. Termux's toolchain has no "dev-only, ships-nothing" category — what
   runs on the build host and what ships on device are the same scripts.
3. **Legible failure logs in CI artifacts.** When the quality job fails, the
   log a reviewer reads (dumps, durations, warning summaries) is formatted
   for humans. Termux failure diagnosis is "run it again on the phone and
   watch".

## 4. Verification refs

- Identity: `colorama-0.4.6.dist-info/METADATA`.
- `initialise.py` def lines `:9,32,37,65,72,96,104,111` (grep-verified);
  `init` + `just_fix_windows_console` signatures live.
- `ansitowin32.py` class lines `:16,:72` (grep-verified).
- `ansi.py`/`win32.py`/`winterm.py` contents: inventory only, unverified.
- Stack role: `docs/reference/dep-test-and-lint-stack.md` (D4/D5) +
  `docs/roadmap.md` dep table (D1 row).
