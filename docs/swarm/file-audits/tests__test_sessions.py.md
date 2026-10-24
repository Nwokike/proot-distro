# tests/test_sessions.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_sessions.py · src/services/session_service.py · src/services/session_manager.py · src/services/proot_service.py · .venv/lib/python3.14/site-packages/proot_distro/commands/login/__init__.py · .venv/lib/python3.14/site-packages/proot_distro/cli.py · pytest 9.1.1 / Python 3.14.9 · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/test_sessions.py` is the session-layer unit test file: 10 tests, all passing (`pytest tests/test_sessions.py` → `10 passed in 0.13s`). It exercises two units:

1. `session_service.session_argv(container)` (session_service.py:39-69) — parses upstream's `--get-proot-cmd` line into `(env, argv)`. Five tests (`:40-56`, `:59-68`, `:71-76`, `:79-82`, `:148-159`) each monkeypatch `session_service.proot_service.get_proot_cmd` to return a captured golden line (plain or backslash-newline wrapped), then assert env entries and argv shape.

2. `session_service.ProotSession` (session_service.py:72-172) — the PTY port (openpty + Popen + blocking read thread + TIOCSWINSZ resize). Three tests (`:101-106`, `:109-112`) construct a `ProotSession` without calling `start()` and assert write/resize/stop are safe no-ops when there is no master fd.

Plus `SessionManager`/`SessionEntry` (session_manager.py): two tests (`:115-120`, `:127-134`) on entry uniqueness and the 4-shell cap, and one test (`:137-145`) on `SessionEntry.replay` order.

The file imports `from services import session_service` (:12) and `from services import session_manager as sm` (:116, :128, :138), resolving under pyproject.toml `pythonpath=["src"]`.

## Findings

### F1 · P1 · Golden-string argv tests mock `proot_service.get_proot_cmd`, so they hide the real signal-handler and `stdout.buffer` bugs

- **Where:** `tests/test_sessions.py:40-56` (mocks `get_proot_cmd` at `:42`), `:59-68` (`:62`), `:148-159` (`:151`); `src/services/proot_service.py:312-345` (`get_proot_cmd` mutates globals `:324-333`, sets `sys.stdout = buffer` `:331`, calls `cli.main()` `:334`, catches only `SystemExit` `:335-340`); `.venv/lib/python3.14/site-packages/proot_distro/cli.py:258` (`signal.signal(signal.SIGQUIT, ...)` — main-thread-only); `.venv/lib/python3.14/site-packages/proot_distro/commands/login/__init__.py:624-625` (`_print_command` writes `sys.stdout.buffer.write(data)` / `.flush()`).
- **What:** All five argv tests replace `get_proot_cmd` with a constant golden string, so `session_argv`'s parser is unit-tested in isolation but `proot_service.get_proot_cmd` itself is never executed. Two real bugs in `get_proot_cmd` are therefore invisible to this suite:
  (a) `cli.main()` installs a `SIGQUIT → KeyboardInterrupt` signal handler (`cli.py:258`); `signal.signal` works only from the main thread, but `get_proot_cmd` is reached via `session_manager.open` → `app_controller.open_session` under `asyncio.to_thread` (app_controller.py:406 → session_manager.py:67 → session_service.py:41 → proot_service.py:334), so it raises `ValueError: signal only works in main thread` uncaught (`get_proot_cmd` catches only `SystemExit`, `:335-340`).
  (b) `get_proot_cmd` redirects `sys.stdout` to a `StringIO` (`:331`), but upstream `_print_command` writes to `sys.stdout.buffer` (login/__init__.py:624-625). A `StringIO` has no `.buffer` attribute (verified: `hasattr(io.StringIO(), 'buffer')` → False on Python 3.14.9), so `_print_command` raises `AttributeError`, which also escapes `get_proot_cmd` (only `SystemExit` is caught). Either way the returned `buffer.getvalue()` is empty/wrong and session open fails.
- **Evidence:** tests/test_sessions.py `:42,:62,:151` (the only `get_proot_cmd` mocks, in every argv test); proot_service.py `:331,:334,:335-340`; cli.py:258; login/__init__.py:624-625; StringIO `.buffer` absence confirmed by running `python -c "import io; print(hasattr(io.StringIO(), 'buffer'))"` → `False`. Sibling proot_service audit F1/F2 documents the same signal/global-state bugs at source.
- **Fix / opportunity:** Keep the golden parser tests (they are good unit tests for `session_argv`), but add an integration-style test that drives `proot_service.get_proot_cmd` with `proot_distro.cli.main` monkeypatched (or a fake `cli.main`) to assert: `ValueError` from `signal.signal` is translated into a clean failure rather than propagating, and `sys.stdout.buffer` writes are captured into the returned buffer (e.g. patch `sys.stdout` to an object exposing a `.buffer` that tees into the same capture). Do not mutate real globals without a lock (see proot_service audit F2).
- **Risk if ignored:** The golden suite passes while the real session-open path crashes on worker threads (signal) or returns an empty command line (`stdout.buffer` bypass) — users cannot open a guest shell, and tests give false confidence.

### F2 · P2 · `ProotSession.start()`, the read thread, `_on_exit`, and `alive` transitions are never tested; write/resize only cover the dead (no-master-fd) no-op path

- **Where:** `tests/test_sessions.py:101-106` (constructs `ProotSession` without `start()`, so `_master_fd is None`; write/resize are no-ops; asserts `received == []`); `:109-112` (stop with no process); `src/services/session_service.py:95-134` (`start` opens PTY via `pty.openpty` `:100`, spawns `Popen` with `stdin=stdout=stderr=slave_fd` `:101-106`, closes slave_fd `:110`, starts reader thread `:133-134`); `:113-131` (`_read_loop` reads `os.read` `:122`, delivers to `self._on_bytes` `:126`, on EOF/OSError sets `returncode` `:129` and calls `self._on_exit` `:130-131`); `:91-93` (`alive` = `poll() is None`).
- **What:** No test calls `session.start()`, so the PTY open, `Popen` spawn, slave-fd close, reader-thread launch, byte delivery to `on_bytes`, EOF break, `returncode` setting, and `_on_exit` invocation are all unexercised. `alive` (True when `poll() is None`, False after exit) is asserted only in the trivial no-process stop test (`:112`). `write`/`resize` are only tested when `_master_fd is None` — the live-fd path (`os.write`, `fcntl.ioctl` `TIOCSWINSZ`, the `cols <= 0 or rows <= 0` guard at session_service.py:143) is untested, as is whether `os.write`'s `OSError` is correctly suppressed (`:139-140`).
- **Fix / opportunity:** Monkeypatch `pty.openpty`, `subprocess.Popen`, `os.read`, `os.write`, `fcntl.ioctl`, `termios`; assert `start()` wires PTY/process/thread, feed fake bytes via `os.read` side-effect and assert `on_bytes` called, assert `_on_exit` called with the polled returncode, assert `write` passes bytes to `os.write` on a live fd and `resize` packs `struct.pack("HHHH", rows, cols, 0, 0)` into `TIOCSWINSZ`.
- **Risk if ignored:** Regressions in PTY setup (slave-fd leak), read-thread byte delivery, or resize go undetected until device runtime.

### F3 · P2 · No test for `stop()` escalation (terminate → wait → timeout), master-fd close, or reader-thread join

- **Where:** `tests/test_sessions.py:109-112` (only the `process is None` early return); `src/services/session_service.py:152-165` (`stop` swaps `self._process`, closes `master_fd` `:154-157`, `process.terminate()` `:162`, `process.wait(timeout=2)` `:164`); `TimeoutExpired` is a subclass of `Exception` (verified on Python 3.14.9), so the `contextlib.suppress(Exception)` at `:161-164` swallows timeouts — but that suppression is untested.
- **What:** `test_session_stop_is_safe_without_a_process` never touches `terminate()`, `wait(timeout=2)`, `os.close(master_fd)`, or the reader thread. The sibling session_manager audit F3/F4 flags that `stop()` never `join`s the daemon reader thread and that natural exit never closes the master fd — no test pins any of this.
- **Fix / opportunity:** Monkeypatch a fake `Popen` whose `poll()` returns `None` then a code, record `terminate()`/`wait(timeout=2)` calls, and fake `os.close` to assert `master_fd` is closed. Assert `stop()` calls `terminate()` then `wait(timeout=2)`, and that a second `stop()` is idempotent.
- **Risk if ignored:** `stop()` may hang (reader thread not joined), fds leak on repeated stop/reopen, and `TimeoutExpired` swallowing masks a genuinely stuck process.

### F4 · P2 · No coverage of `SessionManager.close()`/`close_all()`, `open()` dead-session replacement, or the concurrency-cap race

- **Where:** `tests/test_sessions.py:115-134` (tests `entry()` uniqueness and the cap raise only); `src/services/session_manager.py:63-82` (`open` creates a new `ProotSession` and assigns `entry.session`, dropping a dead old reference without calling `stop()`); `:84-89` (`close` pops entry and calls `entry.session.stop()` but does not reset `ready`/`session`/`mt`); `:91-93` (`close_all`); `:52-61` (`entry` cap check-then-act is not atomic).
- **What:** No test verifies `close()` actually calls `session.stop()`, frees a cap slot, or that `close_all()` stops every entry. `open()` on a container whose entry holds a dead/exited session installs a fresh session and leaks the old one's master fd (no `old.stop()`). The cap-of-4 check-and-insert (`:55-58`) races under concurrent `entry()` calls (session_manager audit F5).
- **Fix / opportunity:** Add tests: `close()` asserts `session.stop()` called and entry removed from `manager.entries`; `close_all()` stops all entries; `open()` re-opening after natural exit calls the old session's `stop()`; concurrent `entry()` calls (monkeypatched `threading`) assert the cap is not exceeded.
- **Risk if ignored:** File-descriptor exhaustion on open/exit/reopen cycles (session_manager audit F3), cap exceeded under concurrency (F5), stale "live" indicators after close (F4).

### F5 · P3 · Weak assertions: `RuntimeError` without `match`, and a fragile negative assertion `"n" not in argv`

- **Where:** `tests/test_sessions.py:71-76` (`pytest.raises(RuntimeError)` no `match=`), `:79-82` (same), `:157` (`assert "n" not in argv`); `src/services/session_service.py:47-48,63-64` (the `RuntimeError` raise sites).
- **What:** `test_session_argv_rejects_garbage`/`:test_session_argv_rejects_empty_command` assert only the exception type, so they would pass even if raised for the wrong reason (e.g. a `RuntimeError` from an unrelated parse failure). `:157`'s `"n" not in argv` is a negative assertion that only proves the backslash-newline didn't become a literal `"n"` token; it adds nothing beyond the positive `argv[0]`/`argv[-2:]` checks already in `:158-159`.
- **Fix / opportunity:** Add `match=` to both `pytest.raises(RuntimeError, match=...)` assertions pinning the exact message (`session_service.py:48` / `:64`). Replace or supplement `"n" not in argv` with a positive equivalence check: wrapped golden parses to an `argv` identical to the unwrapped golden's `argv` (and no `"n"` token anywhere).
- **Risk if ignored:** Parser regressions (wrong error, spurious tokens) slip through; the wrapped-format handling is only negatively asserted.

### F6 · P3 · Over-mocking in one direction / under-mocking in another, plus dead `_FakeProcess` code

- **Where:** `tests/test_sessions.py:40-43,:61-63,:150-152` (monkeypatch `session_service.proot_service.get_proot_cmd` — mocks at the `proot_service` boundary, so the real `get_proot_cmd`/cli path is never tested); `:85-99` (`_FakeProcess` class defined but **never instantiated or called** in any test — dead code); `src/services/session_service.py:98-108,136-150` (`start` uses `pty.openpty`/`subprocess.Popen`; `write` uses `os.write`; `resize` uses `fcntl`/`termios` — none of these are faked anywhere in the file).
- **What:** The argv tests over-mock the integration boundary (`get_proot_cmd`), hiding the real `cli.main`/signal/`stdout.buffer` bugs (F1). Meanwhile nothing fakes `pty`, `os.read`/`os.write`, `subprocess.Popen`, `fcntl.ioctl`, or `termios`, so `ProotSession`'s actual OS interactions are never deterministically unit-tested. `_FakeProcess` (`:85-99`) looks intended to simulate a process but is unused — the two ProotSession tests (`:101-106`, `:109-112`) construct `ProotSession` directly with no fd/process at all.
- **Fix / opportunity:** Remove `_FakeProcess` or use it (e.g. pass a fake process into `stop`/write tests). Add monkeypatch-based tests for `ProotSession.start/write/resize/stop` with faked `os`/`pty`/`subprocess`/`fcntl`/`termios` so the PTY logic is covered without a real PTY.
- **Risk if ignored:** Dead test code rots; PTY/write/resize/stop regressions invisible; suite keeps passing while the real `get_proot_cmd` path is broken (F1).

## Missed capabilities

N/A — this is a first-party file audit, not a dependency audit. (Skipped per BRIEF report contract.)

## Verified-good list

- `pytest tests/test_sessions.py` → `10 passed in 0.13s` on CPython 3.14.9 / pytest 9.1.1 (ground truth); `services.session_service` and `services.session_manager` imports resolve under `pythonpath=["src"]`.
- `session_argv` correctly folds backslash-newline continuations before `shlex.split` (session_service.py:45) — the wrapped golden test passes (`:148-159`) and `argv[0]` ends in `libproot.so`, `argv[-2:] == ["/bin/bash", "-l"]`.
- `_HOST_ESSENTIALS` merge tested both directions: cleared (`:46-47`, `:153-154`) and set via `monkeypatch.setenv` (`:64-65`), asserting `env["LD_LIBRARY_PATH"]`/`env["PROOT_LOADER"]` (`:67-68`).
- `SessionEntry.replay` snapshots with `list(self.scrollback)` (session_manager.py:42) — defensive copy; replay order asserted at tests/test_sessions.py:145.
- `except OSError, ValueError:` at session_service.py:123 is **functional** on Python 3.14.9 — empirically verified it catches both `OSError` and `ValueError` subclasses (it is not a dropped `ValueError`); non-idiomatic (should be `except (OSError, ValueError)`) but not a defect.
- `TimeoutExpired` is a subclass of `Exception` (verified), so `stop()`'s `suppress(Exception)` at session_service.py:161-164 does swallow wait timeouts — behavior is correct, just untested (F3).
- `ProotSession.write`/`resize` short-circuit when `_master_fd is None` (session_service.py:137-138, :143) — covered by `:101-106`.

## Unverified

- Whether `get_proot_cmd` actually raises `AttributeError` (`sys.stdout.buffer` on a `StringIO`, proot_service.py:331 vs login/__init__.py:624) and/or `ValueError` (`signal.signal` off main thread, cli.py:258) in an integrated run — source chain is proven by reading, but the full bootstrap (`posixdb.ensure`, env contract, `proot_distro.cli` import) was not executed end-to-end for `--get-proot-cmd`; marked UNVERIFIED at integration level.
- Whether `open_session`/`get_proot_cmd` is ever invoked off the main thread in practice (depends on UI tap timing; proot_service audit F2).
- Whether `ProotSession.stop()` reliably unblocks a reader thread stuck in `os.read(master_fd, ...)` via `os.close(master_fd)` within the 2s `wait` (PTY/OS-dependent; session_manager audit Unverified :85).
- Whether two sessions are opened concurrently in practice (cap race likelihood; session_manager audit F2/F5).
- Device/Android behavior (pty, flet-terminal canvas, `send_bytes` from a daemon thread) — D-005 gate; not runnable here.

No application code, tests, pyproject, or docs were modified; this is a read-only audit producing one report file at `docs/swarm/file-audits/tests__test_sessions.py.md`.
