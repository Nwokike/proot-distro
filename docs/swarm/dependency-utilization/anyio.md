# anyio 4.15.1 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/dependency-studies/anyio.md`; `src/services/proot_service.py`; `src/services/session_service.py`; `src/services/session_manager.py`; `src/services/update_service.py`; `src/services/ad_service.py`; `src/app_controller.py`; consumers `src/main.py`, `src/screens/views.py`, `src/screens/terminal_view.py`, `src/core/state.py`, `src/core/proot_probe.py`; `.venv/Lib/site-packages/anyio/` (4.15.1); `.venv/Lib/site-packages/flet/`; `.venv/Lib/site-packages/flet_terminal/`; `tests/test_imports_vs_deps.py`; `docs/reference/app-sherlock.md`; `docs/reference/app-data-formulator.md` · **Date:** 2026-10-20

## What it does / how the app uses it

anyio **4.15.1** is installed (`anyio-4.15.1.dist-info/METADATA`), pure Python, **asyncio backend only**: `anyio.get_available_backends() == ('asyncio',)`, `get_all_backends() == ('asyncio', 'trio')` with no trio/sniffio/outcome/uvloop in site-packages. It reaches the APK only as a hard dependency of httpx.

**The app does not import anyio at all.** A grep over `src/` finds the string only in the third-party license list (`src/screens/views.py:32`). Every blocking call is dispatched with the stdlib `asyncio.to_thread` — 19 call sites, all in `AppController` (`src/app_controller.py:144,149,154,164,184,205,212,219,236,240,279,336,351,366,378,386,396,406,416`). The split is otherwise clean:

- `proot_service.py` — synchronous, owns the only `proot_distro` import; called only from worker threads.
- `session_service.py` / `session_manager.py` — synchronous PTY wrapper plus one daemon reader thread per shell; called from `to_thread`.
- `update_service.py` — fully async httpx, no threading.
- `ad_service.py` — async platform-service calls only, no threads.
- `app_controller.py` — all UI-thread async orchestration; progress lines are bridged with `loop.call_soon_threadsafe` (`:171-177`).

So the audit question is not "is anyio used" (it is not) but whether the hand-rolled stdlib threading/loop bridging has real defects that anyio's shipped primitives would prevent. It does: one P1 (live terminal output is never delivered) and a cluster of P2 concurrency defects. The study's P1/P2 proposals (§3, §5) are materially beyond what the code does today; P2 cancellation remains owner-parked in D-015 item 9.

## Findings

### F1 · P1 · Live PTY output never reaches the terminal

- **Where:** `src/services/session_service.py:113-134` (reader thread, `self._on_bytes(data)` at `:126`); `src/services/session_manager.py:38-39` (`feed` appends to a `deque`); `src/screens/terminal_view.py:96-98` (the only `send_bytes` call is the mount replay); `.venv/Lib/site-packages/flet/components/observable.py:197-201` (only `list`/`dict` are wrapped for change notification).
- **What:** Every byte read from the PTY is appended to `entry.scrollback`; nothing forwards it to `MobileTerminal.send_bytes`. `send_bytes` is called once per mount by `_on_mount`, which replays the *existing* buffer. Output produced after mount — the prompt itself, command output, everything — is stored but never rendered. `@ft.observable` does not help: a `deque` is not wrapped by `_wrap_if_collection`, so `feed` emits no notification either.
- **Evidence:** `grep -rn "send_bytes" src/` returns only `src/screens/terminal_view.py:98` (`entry.replay(mt.send_bytes)`), and `session_manager.py:41-43` shows `replay` iterating the buffer. Runnable proof that `feed` is silent:
  ```
  after feed (deque append): []
  ```
  (`SessionEntry("debian")`, a strong-ref listener, `entry.feed(b"x")` — no callback). The flet-terminal contract confirms `send_bytes` is the Python→screen write path (`flet_terminal/terminal.py:126-141`, `mobile_terminal.py:245-246`) and `set_on_bytes` is the screen→Python path.
- **Fix / opportunity:** keep `feed` for scrollback, add a loop-side delivery hook: `SessionManager` receives the page loop (constructor injection from `AppController`) and the reader thread does `loop.call_soon_threadsafe(entry.deliver, data)`, where `deliver` appends and calls the registered `mt.send_bytes`. An `anyio` memory stream consumed by a task is the structured version of the same fix. Do not call `send_bytes` directly from the reader thread.
- **Risk if ignored:** the terminal looks frozen after mount; users type commands and see nothing. This is the product's core M4 interaction.

### F2 · P2 · Observable state is mutated from worker/reader threads

- **Where:** `src/services/session_manager.py:69-75` (callbacks execute on the reader thread) and `:79-81` (executed inside `asyncio.to_thread`, `src/app_controller.py:406`); `.venv/Lib/site-packages/flet/components/observable.py:204-213` → `:165-181`; `.venv/Lib/site-packages/flet/components/component.py:214-220`; `.venv/Lib/site-packages/flet/messaging/session.py:61-62,673-674`; `.venv/Lib/site-packages/flet/controls/context.py:62-67`.
- **What:** `entry.ready` / `entry.session` / `entry.error` assignments call `_notify` synchronously on the calling thread. From the plain reader thread, `context.page` raises `RuntimeError` because a `threading.Thread` does not inherit the contextvar — so `_on_exit` aborts at `session_manager.py:73` and **never executes `entry.session = None` (`:74`) or `entry.error = ...` (`:75`)**. From the `to_thread` worker (context is copied by `asyncio.to_thread`), `_schedule_update` reaches `Session.schedule_update`, which does `self.__pending_updates.add(control)` and `self.__updates_ready.set()` — an `asyncio.Event` mutated from a foreign thread.
- **Evidence:** runnable proofs:
  ```
  ft.context.page in a plain thread -> RuntimeError: The context is not associated with any page.
  listener fired from thread: ('ready', 'reader-thread')
  asyncio.Event.set() from a foreign thread (PYTHONASYNCIODEBUG=1)
    -> RuntimeError: Non-thread-safe operation invoked on an event loop other than the current one
       waiter_done=False
  ```
  The subscription is real: `TerminalView(entry)` at `src/app_shell.py:55` passes the observable as a component argument, and Flet subscribes observable args at `flet/components/component.py:243-245`. Flet's own cross-thread helpers use `run_coroutine_threadsafe` / `call_soon_threadsafe` (`flet/controls/page.py:939,1005`), confirming the framework expects the app to marshal.
- **What it means:** when the user is watching the terminal, a shell exit prints an unhandled traceback in the reader thread, the entry keeps `session` set, and the UI keeps showing "live". The scheduler wakeup may also be dropped, delaying unrelated state updates.
- **Fix / opportunity:** one loop-side mutation point. Inject the loop into `SessionManager`; have `_on_bytes`/`_on_exit` call `loop.call_soon_threadsafe(...)`. In `open()`, return the started session from the worker and assign `entry.session/ready/error` in the coroutine after `await`, not inside the worker.
- **Risk if ignored:** stale "live" status, missing exit/error text, sporadic lost re-renders, thread tracebacks.

### F3 · P2 · Install stderr is discarded from the final Outcome

- **Where:** `src/services/proot_service.py:53-70` (`_LineTee`), `:89-95`; `src/app_controller.py:179-192`.
- **What:** `_run_command` redirects stderr to `_LineTee` when `on_line` is supplied, but `_LineTee.write` only forwards to the hook and returns `len(data)`; it never writes to the capture buffer. `Outcome.output` is `buf.getvalue()` (`:95`), so it contains stdout only. The docstring at `:78-80` claims the lines are forwarded "as well as captured for the final report" — false. `install()` is always called with `on_line` from the controller (`:179-180`), so every install loses all stderr from its Outcome.
- **Evidence:** `_LineTee` has no buffer field (`:59-67`); comparison of `:89` vs `:95`; `is_pull_limit` (`:441-444`) and `friendly_job_error` (`:415-423`) both read `outcome.output`.
- **Fix / opportunity:** `_LineTee(on_line, capture=buf)` and `self._capture.write(data)` in `write`; or wrap the hook as `lambda line: (on_line(line), buf.write(line + "\n"))`. Keep the capture lossless.
- **Risk if ignored:** a failed pull shows a generic line instead of upstream's real error, and Docker Hub 429 text is not seen, so `PULL_LIMIT_COPY` (`:426-430`) is never selected.

### F4 · P2 · Process-global stdio redirection races across threads

- **Where:** `src/services/proot_service.py:89-94` (`redirect_stdout`/`redirect_stderr`) and `:327-344` (`sys.argv`/`sys.stdout`/`sys.stderr` swap in `get_proot_cmd`); concurrent entry points `src/app_controller.py:184,205,212,219,240,336,351,366,378,396,406`.
- **What:** `sys.stdout`/`sys.stderr` are process globals, not thread-local. Two `_run_command` calls in different worker threads install nested redirects; whichever exits first restores the original stream, so the other thread's subsequent output goes to the real stdout instead of its buffer. `get_proot_cmd` (session open) additionally swaps `sys.argv`, `sys.stdout`, and `sys.stderr` manually. Realistic overlap: an install continues when the user leaves the Distros screen (by design), then the user opens a shell or clears the cache.
- **Evidence:** two-thread reproduction of the exact pattern:
  ```
  A captured: ''
  B captured: 'payload-A\n'
  ```
  A's output was captured into B's buffer; A's buffer is empty. The suppress-free `sys.stdout = buffer` block is at `proot_service.py:331-343`.
- **Fix / opportunity:** a module-level `threading.RLock` inside `proot_service` around the whole redirect+call section (and around `get_proot_cmd`'s swap). This is the minimal fix because the code is synchronous. If the call sites are converted to `anyio.to_thread.run_sync`, a single-slot `anyio.CapacityLimiter(1)` passed as `limiter=` serializes them at the dispatch layer.
- **Risk if ignored:** lost or misattributed command output, wrong error messages, and `--get-proot-cmd` output captured by a concurrent install, which makes `session_argv` fail with "unexpected --get-proot-cmd output".

### F5 · P2 · Install guard is a TOCTOU; two installs can start

- **Where:** `src/app_controller.py:162-167`, `:198-200`.
- **What:** `if state.installing: return` is separated from `state.installing = name or image` by `await asyncio.to_thread(self.proot.busy_locks)` at `:164`. Two tasks scheduled by `page.run_task` (`src/screens/views.py:100`) can both pass the check before either sets the flag. The `finally` block then clears the flag unconditionally, so the first finisher also unlocks the second.
- **Evidence:** code order above; `busy_locks()` only reports locks held by *other processes* (`proot_service.py:301-309`), not in-process claims.
- **Fix / opportunity:** claim the guard synchronously before the first await, with rollback on exception; or use `anyio.Lock` in the controller (which is async code). Make `finally` clear only if this task still owns the claim.
- **Risk if ignored:** two upstream installs write the same image cache/container tree concurrently — partial layers and a corrupted install.

### F6 · P2 · Cache clear / remove / reset can run during an install

- **Where:** `src/app_controller.py:231-246` (`clear_cache`), `:204-214` (`remove_container`, `reset_container`), versus `:161-202`.
- **What:** Only `install_distro` consults `state.installing`. `clear_cache` deletes cached image layers (`:236-240`) and remove/reset mutate container trees with no guard. Installs intentionally survive screen navigation, so the user can start a pull on Distros, switch to Settings, and delete the layers the pull is using.
- **Evidence:** `grep -n "state.installing" src/app_controller.py` shows references only at `:162,167,186,198,199`; none in the other mutating methods. `remove_cached_image` runs the same upstream `command_remove` as a normal remove (`proot_service.py:254-260`).
- **Fix / opportunity:** serialize all mutating proot operations behind the same lock/limiter as the install (see F4), and refuse with a snack while `state.installing` is set.
- **Risk if ignored:** a running pull loses its layers mid-extract; containers partially removed under a reset/remove racing an install.

### F7 · P2 · Double "Open shell" races and leaks a PTY + reader thread

- **Where:** `src/app_controller.py:403-410`; `src/services/session_manager.py:63-82`.
- **What:** `open_session` offloads `SessionManager.open` to a worker. Two tasks (double tap; the selector calls `page.run_task` at `terminal_view.py:247,289`) can both observe `entry.session is None` at `session_manager.py:65`, both run `session_argv` (also hitting F4), both `Popen` a PTY, and the second assignment at `:79` overwrites the first. The first `ProotSession` — its child process, master fd, and daemon reader thread — is orphaned. There is also a smaller race where `_on_exit` fires before `:79-81`, resurrecting a dead session as ready.
- **Evidence:** no in-flight flag or lock in `open`; `entry()` only caps the number of entries (`:52-61`).
- **Fix / opportunity:** set an `entry.opening` flag on the loop before offloading, clear it in `finally`; or per-container lock. Assign the session fields on the loop after the `await`.
- **Risk if ignored:** leaked subprocesses, file descriptors, and threads; two live shells for one container; the UI shows only one.

### F8 · P2 · `page.on_close` blocks the event loop while stopping shells

- **Where:** `src/main.py:24-31`; `src/services/session_service.py:152-165` (`process.wait(timeout=2)` at `:164`).
- **What:** `close_all()` runs synchronously inside the `on_close` handler, which Flet dispatches as a task on the session loop (`flet/messaging/session.py:219-234`). Each `stop()` can block the loop for the full 2 s wait; `MAX_CONCURRENT_SESSIONS = 4` (`session_manager.py:20`) means up to 8 s. The `atexit` registration at `main.py:31` is fine; the `on_close` path is not.
- **Evidence:** code refs above; `stop()` has no async/offload wrapper and swallows `TimeoutExpired` (`:160-164`).
- **Fix / opportunity:** `page.on_close = lambda _e: page.run_task(_close_all_async)` and `async def _close_all_async(): await asyncio.to_thread(manager.close_all)`. Keep `atexit` for process exit.
- **Risk if ignored:** app close can freeze for seconds and risk an Android ANR.

### F9 · P2 · PTY writes are blocking calls on the event loop

- **Where:** `src/services/session_service.py:136-140`; callers `src/screens/terminal_view.py:37-39,105-108,124-127`.
- **What:** `os.write(self._master_fd, payload)` is synchronous. It can block when the PTY input buffer is full — a large paste, or a guest process that stopped reading input. The write path is a synchronous Flet event handler, so it cannot await. `resize` (`:142-150`) is a cheap ioctl and not a concern.
- **Evidence:** `write()` is called directly by the `on_data`/`set_on_bytes`/quick-command handlers (`terminal_view.py:38,106,126`); no queue or worker exists.
- **Fix / opportunity:** a single bounded writer queue drained by a worker thread (drop/coalesce on overflow), or schedule `await asyncio.to_thread(os.write, fd, payload)` from the handler. An `anyio` memory stream plus a writer task is the structured version.
- **Risk if ignored:** typing latency spikes and multi-second UI freezes during paste or when a shell floods its input buffer.

### F10 · P2 · Progress updates are uncoalesced; one re-render per stderr line

- **Where:** `src/app_controller.py:173-177`; `src/services/proot_service.py:62-67`; `src/screens/views.py:355-357`; house standard `docs/reference/app-sherlock.md:19`.
- **What:** `_LineTee.write` splits on every line boundary and calls `on_line` per line; `_apply_line` sets `state.install_stage` each time. Because `str.splitlines()` also splits on `\r`, carriage-return progress ticks become individual state mutations. Flet deduplicates pending updates per component but drains the set as fast as signals arrive (`flet/messaging/session.py:712-720`), so a verbose pull drives hundreds of full `DistroView` re-renders per second. The house standard explicitly requires "~2 Hz flush + 500 ms progress coalescing — Flet has zero batching; without it long progress streams freeze the app."
- **Evidence:** `proot_service.py:64-66` loop; `app_controller.py:174` (`state.install_stage = line.strip()`); `views.py:356` renders the value; `app-sherlock.md:19`.
- **Fix / opportunity:** store the latest line in a controller field and flush it to state on a 500 ms timer task; or consume an `anyio` memory stream with a batching reader. Keep the final state write immediate.
- **Risk if ignored:** install-time jank, battery drain, and repeated rebuilds of the banner/ad/container tree.

### F11 · P2 · `ProotSession.stop()` has no SIGKILL escalation

- **Where:** `src/services/session_service.py:158-165`; contrast upstream's escalation in `src/services/proot_service.py:384-390`.
- **What:** `stop()` sends `terminate()` and waits 2 s. On timeout, `contextlib.suppress(Exception)` swallows `TimeoutExpired` and returns. The child keeps running, the master fd was already closed, the entry was already popped from `entries`, and the reader thread may remain blocked in `os.read` (a `close()` from another thread does not invalidate an in-flight `read` on Linux). The app no longer holds a handle to the live shell.
- **Evidence:** `:161-164` — `process.terminate()` then `process.wait(timeout=2)` inside a blanket suppress; no `kill()`. Upstream `kill_session` does "SIGTERM, then SIGKILL escalation" (`:385` docstring).
- **Fix / opportunity:** on timeout, call `process.kill()` and wait; optionally call `proot_service.kill_session(container)` as a fallback. Join `self._reader` with a short timeout.
- **Risk if ignored:** a "closed" shell keeps running and consuming memory; each occurrence leaks a process, a PTY fd, and a daemon thread.

### F12 · P3 · `call_soon_threadsafe` on a torn-down loop aborts the install

- **Where:** `src/app_controller.py:171-177`; `src/services/proot_service.py:101-102`.
- **What:** `_on_line` runs in the install worker and calls `loop.call_soon_threadsafe`. After the session loop closes, that call raises `RuntimeError`. The exception propagates out of `_LineTee.write` into upstream's print call and is caught by `_run_command`'s blanket `except Exception`, which converts it into a failed `Outcome` and stops the install.
- **Evidence:** runnable:
  ```
  closed-loop call_soon_threadsafe -> RuntimeError Event loop is closed
  ```
  `_run_command` catches it at `:101`. Whether upstream catches exceptions around its own printing is **UNVERIFIED**; if it does, the install continues but every later line is dropped.
- **Fix / opportunity:** guard the callback: `if loop.is_closed(): return` plus `try/except RuntimeError`, and attach a generation token so callbacks from a previous session are ignored. A queue owned by the page lifetime makes this structural.
- **Risk if ignored:** backgrounding/reconnect during an install can abort the pull mid-extraction, leaving a partial container.

### F13 · P3 · Refresh does three sequential full tree walks in three thread hops

- **Where:** `src/app_controller.py:141-159`; `src/services/proot_service.py:175-203,272-291,294-298`.
- **What:** `list_containers` walks every container (`_tree_bytes`), `storage_bytes` walks the entire `proot-distro` directory (containers again), and `cached_images` walks every cached image. They run one after another, each in a separate executor hop, and the UI has no "refreshing" state. On multi-GB containers this is seconds of flash I/O with no feedback.
- **Evidence:** `refresh_containers` awaits the three calls sequentially; `_tree_bytes` is `os.walk` + `stat` per file (`:175-181`).
- **Fix / opportunity:** one worker function that gathers all three in a single pass (sharing the container walk), and a `state.refreshing` flag. `anyio.gather` would parallelize the walks but they are disk-bound; a single pass is the real win.
- **Risk if ignored:** multi-second stale UI after every install/remove and redundant flash wear.

## Missed capabilities

**Prerequisite — declaring anyio.** Any direct `import anyio` in `src/` fails the repo's own guard: `tests/test_imports_vs_deps.py:46-59` requires every imported distribution to be in `[project].dependencies`, and the verified declared set is `flet, flet_ads, flet_proot, flet_terminal, httpx, proot_distro` — `anyio` is not in it (it is only a transitive dependency of httpx). The house rule is explicit: "declare every directly-imported transitive in pyproject (DDGS's test guards it)" (`docs/reference/app-data-formulator.md:22`), and the Sherlock study already uses `anyio.CapacityLimiter(12)` with `asyncio.to_thread` (`docs/reference/app-sherlock.md:16`). Declaring `anyio>=4.15.1` adds **zero APK bytes** (already installed as httpx's dependency, pure Python) but is a D-003 dependency-set decision requiring owner sign-off. If the owner declines, F2/F4/F6/F9 still have stdlib-only fixes (`threading.RLock`, `loop.call_soon_threadsafe`, a writer queue); the anyio forms below are the cleaner versions.

| Capability | Installed API | Proposed integration point | Value vs cost |
|---|---|---|---|
| `CapacityLimiter` + `to_thread.run_sync(limiter=...)` | `anyio/_core/_synchronization.py:534`; `anyio/to_thread.py:27-34`; module-level `CapacityLimiter` works before a loop via `CapacityLimiterAdapter` (`_synchronization.py:652-681`) | One `PROOT_LIMITER = CapacityLimiter(1)` created at import; replace the 19 `asyncio.to_thread` calls in `app_controller.py` with `await anyio.to_thread.run_sync(fn, *args, limiter=PROOT_LIMITER)` (wrap multi-arg calls with `functools.partial`) | Fixes F4/F5/F6/F7 at the dispatch layer in one refactor; low cost, high value. |
| `CancelScope` / `move_on_after` | `anyio/_core/_tasks.py:43,201`; `to_thread.py:30` (`abandon_on_cancel`) | Wrap `install_distro`'s await in `with anyio.move_on_after(600):`; set `state.installing=None` on expiry and tell the user to check the container. True cancellation of the upstream in-process call is only possible by raising from `_LineTee`'s hook; `abandon_on_cancel=True` leaves the worker thread and pull running. | Medium value, medium cost; **owner-parked** by D-015 item 9. It does solve the "install never finishes, `state.installing` blocks all future installs" failure, which has no current recovery except app restart. |
| Memory object streams + `from_thread.run` | `anyio/_core/_streams.py:16`; `streams/memory.py:80,199`; `from_thread.py:68` | Reader thread sends chunks into `create_memory_object_stream(bytes, max_buffer_size=64)`; a task drains it into `mt.send_bytes`. Bounded buffer gives PTY backpressure and closes the stream on teardown. | Fixes F1 and gives F10 a batching seam; medium cost. A `loop.call_soon_threadsafe` + `deque` bridge is cheaper and sufficient for F1; the stream is worth it only if backpressure/coalescing is wanted. |
| `create_task_group` | `anyio/_core/_tasks.py:238` | One task group per session owning the reader task and writer task; tab close cancels the group. Requires moving the PTY read/write from raw threads to `run_sync(..., abandon_on_cancel=True)` tasks. | Medium value, high cost (thread-to-task rewrite). The current daemon-thread model works once F1/F2/F11 are fixed; treat as a later cleanup, not a defect fix. |
| `anyio.gather` | `anyio/_core/_concurrency_utils.py:80` | `gather(proot.list_containers, proot.storage_bytes, proot.cached_images)` in `refresh_containers`. | Low value: all three are flash-bound and would contend. Prefer the single-pass fix in F13. |

**Not a fit (do not propose):**
- `anyio.open_process` — no PTY allocation; the session needs `pty.openpty` + `TIOCSWINSZ` (`session_service.py:98-111,142-150`). The dependency study's §5 P3 suggestion is not usable as written.
- `anyio.to_process` / `to_interpreter` — process spawn/subinterpreters are unverified under serious_python on Android (study §2.5, §6).
- Sockets/listeners/signals/`AsyncFile` — the app has no server sockets, no signal use (POSIX-only), and upstream already does its own file I/O in-process.

## Verified-good list

- Version and backend: `anyio-4.15.1.dist-info/METADATA` says 4.15.1, MIT; `get_available_backends() == ('asyncio',)`; no trio/sniffio/outcome/uvloop installed. The study's identity section is accurate.
- **All blocking proot work is off the loop** — every `proot_service`/`session_service`/`session_manager` entry point is reached through `asyncio.to_thread` (`app_controller.py:144,149,154,164,184,205,212,219,236,240,279,336,351,366,378,386,396,406,416`). Startup probe (`:279`) and session open/close are offloaded too.
- Progress bridging uses the correct thread-safe primitive: `loop.call_soon_threadsafe(_apply_line, line)` (`app_controller.py:171-177`); `page.loop` and `page.run_task` are real Flet APIs (`flet/controls/page.py:1334-1338`, `:929-945`), and `run_task` is cross-thread safe via `run_coroutine_threadsafe`.
- `page.on_close` / `page.on_disconnect` exist (`flet/controls/page.py:670,676`); the no-op disconnect handler (`main.py:29`) is deliberate and matches the "shells survive backgrounding" design.
- `update_service.check_for_update` is genuinely async (`httpx.AsyncClient`, 4 s timeout, silent failure) with no blocking calls on the loop; `_safe_text`/`_safe_url` caps are applied after parsing (`update_service.py:40-48,88-99`).
- `ad_service` has no threads and no blocking calls; the interstitial minimum-interval guard is set before the first await (`ad_service.py:170-179`), so concurrent show calls cannot double-show.
- Scrollback is bounded: `deque(maxlen=2000)` (`session_manager.py:21,31`) — roughly 8 MB per 4 KB chunk, capped at 4 entries (`:20,55-58`).
- `_tree_bytes` suppresses per-file `OSError` (`proot_service.py:179-180`), and `refresh_containers` converts each failure into an honest `data_note` instead of swallowing it (`app_controller.py:145-159`).
- `ProotSession` closes the slave fd and marks the reader daemon (`session_service.py:110,133`); `stop()` is safe without a process and `write`/`resize` are no-ops before start (covered by `tests/test_sessions.py:83-100`).
- `except OSError, ValueError:` (`session_service.py:123`) and `except TypeError, ValueError:` (`update_service.py:63`) are **valid on Python 3.14** (PEP 758, parenthesized-less except tuples); `ast.parse` succeeds, `py_compile` exits 0, `requires-python = ">=3.14"` (`pyproject.toml:8`), and ruff targets `py314` (`pyproject.toml:101`). Not a bug. They would be SyntaxErrors below 3.14, so do not back-port them.
- No Flet API hallucinations found: `page.services`, `page.show_dialog`, `page.pop_dialog`, `ft.context.page`, `MobileTerminal.send_bytes/set_on_bytes/on_data`, and `@ft.observable` all exist with the semantics the app assumes.

## Unverified

- Whether closing the PTY master fd from `stop()` actually wakes a reader blocked in `os.read` on Android/Linux. If it does not, F11's timeout path leaks a blocked daemon thread until process exit; I could not run the Android/Linux kernel path here.
- Whether upstream `command_install` catches exceptions raised by its own progress printing. This determines whether F12 aborts the pull or merely drops subsequent lines.
- Whether upstream commands ever exit via `sys.exit(None)`; `_run_command` treats a non-int `SystemExit.code` as exit code 1 (`proot_service.py:97-100`), so a bare `sys.exit()` would be reported as a failure. No upstream call path was inspected to prove this occurs.
- Flet's Android session-restart behavior across backgrounding (whether the event loop is closed and recreated while `state.installing` survives in the module), which decides how often F12's closed-loop path is reachable.
- The exact executor size on-device: `asyncio.to_thread` uses the loop's default executor (`loop.run_in_executor(None, ...)`, stdlib `asyncio/threads.py`), which is `min(32, cpu_count+4)`; Flet's own `connection.executor` is a separate, unused `ThreadPoolExecutor` (`flet/app.py:413,521`; no `set_default_executor` call). I did not measure `os.cpu_count()` under the APK.
