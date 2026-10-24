# src__services__session_service.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/services/session_service.py` (primary) · `src/services/proot_service.py` (`get_proot_cmd`) · `src/services/session_manager.py` (caller) · `tests/test_sessions.py` (monkeypatches the bug away) · `docs/decisions.md` D-016 (contract) · verified against `.venv/lib/python3.14/site-packages/proot_distro 5.10.0` and `flet 1.0.4` · **Date:** 2026-10-24

## What it does / how the app uses it

`session_service.session_argv(container)` asks upstream proot-distro itself for the guest session's `(env, argv)` by running `proot-distro login <c> --get-proot-cmd` in-process (`proot_service.get_proot_cmd`, `src/services/proot_service.py:312`) and parsing the single public `env -i …` line it prints. Nothing about the argv is reimplemented or hardcoded, so an upstream bump flows through (D-017 §1, D-016 §3). `ProotSession` is a PTY port of the flet-terminal example: `pty.openpty()` + `subprocess.Popen` on the slave fd with `start_new_session`, a blocking read thread handing bytes to `on_bytes`, `TIOCSWINSZ` resize, and close-master → terminate (`start()`, `stop()`). `SessionManager` (`src/services/session_manager.py`) keeps one `ProotSession` per container behind observable `SessionEntry` entries, capped at 4 concurrent shells (D-017 §3).

## Findings

### F1 · P0 · `get_proot_cmd` crashes: `sys.stdout` is a `StringIO` but upstream prints via `sys.stdout.buffer` → `AttributeError`; `session_argv` can never return real argv, so sessions cannot open

- **Where:** `src/services/proot_service.py:328` sets `sys.stdout = buffer` where `buffer = io.StringIO()` (line 328), then calls `cli.main()` (line 334). Upstream's `_print_command` (the `--get-proot-cmd` printer) writes via `sys.stdout.buffer.write(data)` / `.flush()` (`.venv/.../proot_distro/commands/login/__init__.py:624-625`). `io.StringIO` has no `.buffer` attribute → `AttributeError: '_io.StringIO' object has no attribute 'buffer'` (verified by executing `.venv` Python 3.14.9: `hasattr(io.StringIO(), 'buffer')` is `False`; accessing `.buffer` raises `AttributeError`).
- **What:** `session_argv` (`src/services/session_service.py:41`) calls `get_proot_cmd(container)`. When a container is actually installed, `command_login` reaches `show_cmd` → `_print_command` (`.venv/.../proot_distro/commands/login/__init__.py`, `show_cmd` path at `login/__init__.py` `if show_cmd:` block → `_print_command`), which raises `AttributeError`. `get_proot_cmd` only catches `SystemExit` (`proot_service.py:335`), not `AttributeError`, so it propagates through `session_argv` to `SessionManager.open` (`src/services/session_manager.py:67-78`) and aborts session start. On this desktop host `pd login --help` errors at `_ensure_proot_available` (no proot binary) before the flag can be exercised end-to-end, but the code path is present and the `--get-proot-cmd` flag is real (`.venv/.../proot_distro/parser.py:267` `p.add_argument("--get-proot-cmd", dest="get_proot_cmd", ...)`).
- **Evidence:** `proot_service.py:327-345`; `_print_command` `.buffer` writes at `proot_distro/commands/login/__init__.py:624-625`; `io.StringIO` has no `.buffer` (verified by execution). The parser flag exists (`parser.py:267`), so `--get-proot-cmd` is a real contract, not a hallucination.
- **Fix / opportunity:** Capture upstream's printed bytes through a capture object that exposes `.buffer` (e.g. redirect the real file descriptor / use `io.BytesIO` for stdout buffer, or capture `sys.stdout.buffer` directly) instead of replacing `sys.stdout` with a text `StringIO`. Minimal, architecture-respecting: keep the in-process `cli.main()` invocation (a subprocess is impossible on Android, M0 G1b) but fix the capture so `_print_command`'s `sys.stdout.buffer.write` succeeds.
- **Risk if ignored:** P0. Terminal/session feature (M4) is completely non-functional on any device with an installed container — `session_argv` raises before any `ProotSession` is created. The test suite does not catch this because every test monkeypatches `proot_service.get_proot_cmd` to return `GOLDEN_CMD` (`tests/test_sessions.py:42-43`, `:61-62`), never exercising the real `get_proot_cmd`.

### F2 · P1 · `start()` leaks the PTY master/slave fds if `subprocess.Popen` raises (no `try/finally`)

- **Where:** `src/services/session_service.py:100-111`. `pty.openpty()` creates `master_fd, slave_fd` (line 100); `subprocess.Popen(...)` (line 101) is not wrapped; if it raises, neither fd is closed, `self._master_fd` is never set (line 111 skipped), and `os.close(slave_fd)` (line 110) is skipped.
- **What:** On a failed spawn (e.g. `env` lacks a needed binary, `EACCES`, `ENOMEM` from `execvpe` — upstream documents these at `proot_distro/commands/login/__init__.py _exec_proot`), both PTY fds leak. Repeated failed session opens exhaust file descriptors.
- **Evidence:** `session_service.py:100-111`; no `try/finally` around `Popen`/`os.close(slave_fd)`.
- **Fix / opportunity:** Wrap the `Popen` call in `try/except` that closes `master_fd` and `slave_fd` on failure, or use a context manager/finally. Keep `close_fds=True`, `start_new_session=True`.
- **Risk if ignored:** fd leak → `OSError: too many open files` on repeated failed/open-close cycles; PTY slots exhausted.

### F3 · P1 · `stop()` has no SIGKILL escalation and does not join the reader thread; orphaned proot processes can linger

- **Where:** `src/services/session_service.py:152-165`. `stop()` sets `self._process = None` (line 153), closes `self._master_fd` (line 156), then `process.terminate()` (line 162) and `process.wait(timeout=2)` (line 164). If proot ignores/delays on SIGTERM, `wait` times out after 2s, `process.poll()` may still be `None` (line 165 sets `returncode` to `None`), and the process is left running. It was started with `start_new_session=True` (line 107) → its own process group, so it is not reaped by the parent. The reader thread (`_read_loop`, daemon, line 133) is woken by the master close (os.read raises OSError → break) but is never `join()`ed.
- **What:** A stuck guest shell survives `stop()` as an orphaned proot process holding the PTY/rootfs. Repeated stop/start accumulates zombie-or-live proot processes and PTY master fds (until GC/process exit). The read thread is a daemon so it dies at interpreter exit, but not deterministically at `stop()`.
- **Evidence:** `session_service.py:152-165`, `107` (`start_new_session`), `133` (`daemon=True`, no `join`).
- **Fix / opportunity:** After `wait(timeout=2)` times out, escalate `process.kill()` then `wait()`. `join()` the reader thread (with a short timeout) in `stop()` after closing the master, so `stop()` is synchronous and deterministic. Match the D-016 "close-master → terminate" shape but add the kill escalation it omits.
- **Risk if ignored:** orphaned guest shells accumulate; repeated terminal use leaks proot processes and PTYs; on Android this can exhaust the device's process/fd limits.

### F4 · P2 · `write()` may silently drop bytes: no partial-write handling; check-then-act race on `self._master_fd`

- **Where:** `src/services/session_service.py:136-140`. `write()` returns early if `self._master_fd is None` (line 137), then `os.write(self._master_fd, payload)` (line 140) under `suppress(OSError)`. `os.write` on a PTY master is not guaranteed to write all bytes (short writes are possible), and the fd can be closed by `stop()` between the `None` check and `os.write` (suppressed, but remaining bytes are dropped).
- **What:** Keystrokes/input sent to the guest can be partially or fully lost without any error surfaced. `stop()` closes the master (line 156) while a concurrent `write()` may be in flight.
- **Evidence:** `session_service.py:136-140` (write), `152-157` (stop closes master).
- **Fix / opportunity:** Loop on `os.write` until all bytes are written (handling `EAGAIN`/`EINTR`), or at minimum detect and report short writes. Serialize `write`/`stop` with a lock so the fd cannot be closed mid-write.
- **Risk if ignored:** user-visible input loss in the terminal (characters vanish) — this is the class of bug D-017 §6 warns about for the *other* input path; here it affects the master-write path.

### F5 · P3 · `except OSError, ValueError:` is legacy Python-2 comma syntax (functionally a tuple on 3.14.9, but non-idiomatic and version-fragile)

- **Where:** `src/services/session_service.py:123` `except OSError, ValueError:`.
- **What:** On Python 3.14.9 this behaves as `except (OSError, ValueError)` (verified by execution: `OSError` and `ValueError` are caught, `TypeError` propagates), so it is *not* a coverage bug on the target interpreter. However it is the removed Python-2 `except E, V` binding form; it reads as "catch OSError and bind it to the name ValueError" and is not valid idiomatic Python 3. It is fragile if the interpreter ever changes this legacy acceptance.
- **Evidence:** `session_service.py:123`; execution confirmed both OSError and ValueError caught, TypeError not caught.
- **Fix / opportunity:** Modernize to `except (OSError, ValueError):` for clarity and forward compatibility.
- **Risk if ignored:** Low on 3.14.9 (works), but confusing to maintainers and a latent porting hazard. `requires-python = ">=3.14"` (`pyproject.toml:8`).

### F6 · P2 (contract gap, UNVERIFIED on device) · D-016 lists argv flags that upstream does not emit in the non-Termux path, and `tmp:/dev/shm` / `PROOT_L2S_DIR` do not appear in proot args at all

- **Where:** `docs/decisions.md` D-016 §3 claims session argv uses `--change-id=0:0`, `<rootfs>tmp:/dev/shm`, stdio binds, `--link2symlink`, `-L`, `--sysvipc`, `--kill-on-exit`, `--kernel-release`, `PROOT_L2S_DIR`. Code: `src/services/session_service.py` *parses* whatever upstream prints (no flag injection). Upstream `.venv/.../proot_distro/commands/login/proot_cmd.py:137` `if not IS_TERMUX: return` — so `--kill-on-exit` (line 143), `--link2symlink` (line 146), `--sysvipc` (line 149), `--kernel-release` (line 154), `-L` (line 158) are only added when `IS_TERMUX` is true. `--change-id` is added only for non-termux containers (line 105). There is no `tmp:/dev/shm` bind and no `PROOT_L2S_DIR` argv anywhere in `build_proot_args`/`_add_proot_extensions`/`_add_non_minimal_binds` (`proot_cmd.py:31-215`); `PROOT_L2S_DIR` is set as an *env var* in `login/__init__.py` (not proot argv), and `tmp:/dev/shm` is not referenced at all in the installed proot_distro.
- **What:** `session_argv` is a faithful pass-through parser — no parsing bug. The golden test (`tests/test_sessions.py:17-23`, `GOLDEN_CMD`) correctly omits the Termux-only flags because the test host is not Termux (`IS_TERMUX=False`). But D-016's claimed contract (`tmp:/dev/shm` bind, `PROOT_L2S_DIR` in argv) is not produced by upstream on any path I could verify, so the "golden-string contract" does not cover the D-016 flags on this host; on Android (Termux) they appear only via upstream's `IS_TERMUX` branch, which this code does not control or assert.
- **Evidence:** `session_service.py:39-69` (parse-only, no flag injection); `proot_distro/commands/login/proot_cmd.py:137,143,146,149,154,158,105`; `tests/test_sessions.py:17-23` (GOLDEN_CMD has none of the Termux flags); `proot_distro/commands/login/__init__.py` sets `PROOT_L2S_DIR` as env (not argv), no `tmp:/dev/shm` bind found.
- **Fix / opportunity:** If the product requires `tmp:/dev/shm` / `PROOT_L2S_DIR` in the guest argv, that must be added upstream or via a documented adapter — `session_service` itself cannot inject flags without violating D-017 §1 ("guest argv comes from upstream, never from us"). At minimum, add a test asserting which flags appear under `IS_TERMUX=True` vs False so the contract is pinned, not assumed.
- **Risk if ignored:** P2. Session spawn on Android may not match D-016's intended shape (missing `kill-on-exit`, `link2symlink`, `sysvipc`, `kernel-release`, `tmp:/dev/shm`); behavior drift between the golden test (desktop) and the device (Termux) is untested. Label: **UNVERIFIED** whether a real Android/Termux device emits `tmp:/dev/shm` or `PROOT_L2S_DIR` — no device is available here (offline, D-005 §1).

### F7 · P3 · `resize()` arg order is correct but the parameter naming `(cols, rows)` packed as `(rows, cols)` is a footgun; `suppress(Exception)` swallows genuine `EBADF` after master close

- **Where:** `src/services/session_service.py:142-150`. `resize(cols, rows)` packs `struct.pack("HHHH", rows, cols, 0, 0)` (line 149) — i.e. `ws_row=rows` (2nd param), `ws_col=cols` (1st param). Verified correct against `struct winsize {ws_row, ws_col, …}` and `TIOCSWINSZ` (`.venv` `termios.TIOCSWINSZ` exists, `struct.pack("HHHH",80,24,0,0)` = `b'P\x00\x18\x00\x00\x00\x00\x00'` → row=0x18=24, col=0x50=80). But a caller passing `resize(rows=24, cols=80)` by name would invert the terminal size.
- **What:** Functionally correct as called, but the parameter order is counter-intuitive (most APIs take rows then cols). `suppress(Exception)` (line 145) swallows `OSError`/`EBADF` if the master is already closed — harmless but masks use-after-close.
- **Evidence:** `session_service.py:142-150`; `termios.TIOCSWINSZ`, `struct.pack` verified in `.venv`.
- **Fix / opportunity:** Rename params to `(rows, cols)` or add a comment documenting the `(rows, cols)` pack order; keep `suppress` but narrow to `OSError`.
- **Risk if ignored:** Low (correct today), but easy to misuse during future edits → inverted terminal dimensions.

## Missed capabilities

Not applicable — this is an app-service audit, not a dependency audit.

## Verified-good list

- `session_argv` golden-string contract: folds backslash-newline continuations before `shlex.split` (`session_service.py:45-46`), validates `tokens[0] == "env"` and strips `-i` (lines 47-53), parses `KEY=VALUE` assignments via `_ASSIGNMENT_RE` (lines 56-61), treats the first non-assignment token as argv start (line 57), rejects empty argv (lines 63-64), merges host essentials `LD_LIBRARY_PATH`/`PROOT_LOADER`/`PROOT_TMP_DIR` from `os.environ` (lines 65-68). `_ASSIGNMENT_RE` correctly excludes proot `-flag=val` args (they start with `-`). Tests pass: `tests/test_sessions.py:40-82` (env/command parse), `59-68` (host essentials merge), `71-76` (reject garbage), `79-82` (reject empty command), `148-159` (wrapped output). Verified by execution.
- Proot argv flags verified against installed upstream: `--get-proot-cmd` flag at `parser.py:267`; `--change-id` (`proot_cmd.py:105`); `--kill-on-exit` (`143`), `--link2symlink` (`146`), `--sysvipc` (`149`), `--kernel-release` (`154`), `-L` (`158`) — all gated on `IS_TERMUX` (`137`). `--bind=/dev,/proc,/sys` (`proot_cmd.py` non-minimal binds), `--cwd=` (`build_proot_args`).
- `ProotSession` shape matches D-017 §2 / flet-terminal: `pty.openpty()` (`session_service.py:100`), `Popen` on slave fd with `close_fds=True`, `start_new_session=True` (lines 101-109), `os.close(slave_fd)` (line 110), daemon read thread (line 133), `TIOCSWINSZ` resize (lines 142-150), close-master → terminate (`stop`, lines 152-165).
- `flet` 1.0.4 APIs used by `session_manager` (`ft.observable`, `ft.component`) verified present in `.venv/flet`. `session_manager.S` uses `ft.observable` (`session_manager.py:24`) — exists.
- `.venv` proot_distro APIs all present and signatures match the adapter: `cli.main()` (`.venv/proot_distro/cli.py`), `session.active_sessions()`, `paths.installed_container_names()`, `paths.container_image_origin()`, `locking.busy_locks()`, `docker.search.search_images()`, `cache.iter_cached_images()`, and all `command_*` handlers (`install/remove/reset/backup/restore/copy/kill/rename`) — verified by introspection against installed source.

## Unverified

- End-to-end `get_proot_cmd` with a real installed container: cannot run here (no proot binary, no device, offline per D-005 §1). The `AttributeError` (F1) is proven by code inspection + `io.StringIO` execution, but the full `login --get-proot-cmd → _print_command` path is only reachable with an installed container. Marked P0 because the code path is present and the flag is real.
- Whether a real Android/Termux device emits `tmp:/dev/shm` or `PROOT_L2S_DIR` (D-016 flags). No device available; `IS_TERMUX` branch not exercisable here. Label: **UNVERIFIED**.
- `except OSError, ValueError:` tuple semantics verified on Python 3.14.9 only (the target `requires-python >=3.14`). Forward compatibility on future 3.x not tested.
- `SessionManager.open()` concurrency / thread-safety not tested here (no device, UI-thread assumption).
