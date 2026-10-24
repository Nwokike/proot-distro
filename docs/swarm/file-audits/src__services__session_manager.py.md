# src/services/session_manager.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/services/session_manager.py` (98 lines) · `src/services/session_service.py` · `src/screens/terminal_view.py` · `src/app_controller.py` · `tests/test_sessions.py` · `docs/decisions.md` (D-016, D-017) · installed `flet==1.0.4`, `flet-terminal==0.4.0` at `.venv/lib/python3.14/site-packages/` · **Date:** 2026-10-24

---

## What it does / how the app uses it

`src/services/session_manager.py` defines `SessionEntry` (`@ft.observable`) and `SessionManager`. One `SessionEntry` per container holds the shell process, a `deque` scrollback (capped at `SCROLLBACK_CHUNKS = 2000`), and readiness/error status. `SessionManager` opens/closes/switches guest shells and caps concurrency at `MAX_CONCURRENT_SESSIONS = 4`.

The data flow: `SessionManager.open()` builds a `ProotSession` (session_service.py:72) whose read thread delivers PTY output to `_on_bytes` → `entry.feed(data)` → `entry.scrollback.append(data)` (session_manager.py:38-39). The terminal view (`terminal_view.py`) mounts a `MobileTerminal` on `entry.mt`, wires both input paths (`set_on_bytes` + `on_data` → `_write` → `entry.session.write` = PTY input), and on mount calls `entry.replay(mt.send_bytes)` to push stored scrollback to the canvas.

Key architecture rulings this file must honor:
- D-017 §3: sessions live on observable entries, not widgets; buffer replays on mount; cap at 4 shells.
- D-017 §4: both input paths wired (`set_on_bytes` binary + `on_data` string).

---

## Findings

### F1 · P0 · Live PTY output never reaches the terminal canvas — `feed()` writes scrollback only, never `send_bytes`

- **Where:** `src/services/session_manager.py:38-39` (`feed` does `self.scrollback.append(data)` only); `:69-70` (`_on_bytes` → `entry.feed(data)`); `:77` (`ProotSession(argv, env, _on_bytes, _on_exit)`); contrast `src/screens/terminal_view.py:96-98` (`on_mount` → `entry.replay(mt.send_bytes)`).
- **What:** PTY output flows `ProotSession._read_loop` (session_service.py:113-131) → `self._on_bytes(data)` → `entry.feed(data)` → `scrollback.append`. `feed()` never calls `send_bytes`, so live output is stored in scrollback but **never pushed to the Dart terminal canvas**. The only canvas write is `replay()` on mount. After the initial replay, the terminal appears frozen/dead even though the shell is running and producing output.
- **Evidence:** `feed()` body is a single `self.scrollback.append(data)` — no `send_bytes` call anywhere in session_manager.py. `send_bytes` is Python→Dart canvas output (`.venv/lib/python3.14/site-packages/flet_terminal/terminal.py:129-130` docstring "Sends raw bytes from Python to Dart (writing to terminal canvas)."; `data_channel.py:65-66` "Send bytes Python → Dart"). `set_on_bytes` is the Dart→Python input direction (terminal.py:123-124 "bytes pushed from Dart to Python"), correctly used in terminal_view.py:105-108 for keyboard input. The live-output direction (`feed` → canvas) is simply missing.
- **Fix / opportunity:** `feed()` must both append to scrollback AND forward live bytes to the canvas: `if self.mt is not None: self.mt.send_bytes(data)` (entry.mt is populated by terminal_view.py:68-78). Gate on `self.mt` so pre-mount output is captured in scrollback for later replay, while post-mount output streams live. Keep `replay()` for the backlog on mount.
- **Risk if ignored:** Terminal feature is broken end-to-end — user sees no live shell output. P0 (user-visible broken behavior).

### F2 · P1 · Cross-thread race on `entries` dict and `entry` fields (no lock)

- **Where:** `src/services/session_manager.py:50` (`self.entries: dict[str, SessionEntry] = {}`); `entry()` `:52-61` (reads/mutates `self.entries`); `open()` `:63-82` (mutates `entry.session`, `entry.ready`, `entry.error`); `close()` `:84-89` (`self.entries.pop`); `close_all()` `:91-93` (iterates `self.entries`). Called via `asyncio.to_thread` from `src/app_controller.py:406` (`open_session`) and `:416` (`close_session`) — i.e. on worker threads. Read on the UI/Flet thread in `src/screens/terminal_view.py:146` (`entry.ready`), `:38` (`entry.session`), `:91` (`entry.session`), `:157` (`entry.ready`).
- **What:** The `entries` dict and `entry.session`/`entry.ready`/`entry.error`/`entry.title` are mutated on worker threads and read on the Flet UI thread with no lock, no `threading.Lock`, and no marshaling. `Observable.__setattr__` (flet/components/observable.py:204-212) notifies listeners but provides no mutual exclusion. A concurrent `open()`/`close()`/`close_all()` can raise `RuntimeError: dictionary changed size during iteration`, and UI reads can observe a torn/stale `entry.session`/`entry.ready`.
- **Fix / opportunity:** Add a `threading.Lock` to `SessionManager` guarding `entries` mutations and entry-field writes; marshal UI-visible reads onto the Flet loop or copy under lock. Keep constructor injection / no monkeypatch (D-016, BRIEF rule 4).
- **Risk if ignored:** Crash from concurrent dict mutation; stale "live"/"idle" indicator; dangling session reference after close.

### F3 · P2 · File-descriptor leak: `open()` replaces a dead session without closing it; natural exit never closes the master fd

- **Where:** `src/services/session_manager.py:52-61` (`entry()` returns an existing entry even when its session is dead); `:77-79` (`open()` creates a new `ProotSession` and assigns `entry.session = session`, dropping the old reference); `src/services/session_service.py:129` (`_on_exit` sets `entry.session = None`, `entry.ready = False` but never closes `master_fd`); `:152-165` (`ProotSession.stop()` closes `master_fd` but is only called by `SessionManager.close()`, not on natural exit). `ProotSession` has no `__del__` (session_service.py:72-172).
- **What:** When a shell exits naturally, the read loop breaks (session_service.py:128) and `_on_exit` nils `entry.session`, but the orphaned `ProotSession` still holds an open PTY master fd that is never closed. On reopen, `open()` installs a fresh session and the old fd leaks. `stop()` (which closes the fd) is never invoked on natural exit.
- **Fix / opportunity:** On natural exit, close the master fd (e.g. in `_on_exit`/read-loop teardown, or have `SessionManager.open()` call `old.stop()` before replacing a dead session — guarded for `None`).
- **Risk if ignored:** File-descriptor exhaustion over repeated open/exit/reopen cycles. P2.

### F4 · P2 · `close()` leaves stale observable state and does not deterministically terminate the reader thread

- **Where:** `src/services/session_manager.py:84-89` (`close` pops the entry and calls `entry.session.stop()`); does not reset `entry.ready`, `entry.session`, or `entry.mt`; `src/services/session_service.py:152-165` (`stop()` terminates + waits ≤2s but does not `join` the daemon reader thread).
- **What:** `close()` pops `entry` from `self.entries`, but any external reference (e.g. `terminal_view` holds `entry` via closure/`entry.mt`) still sees `entry.ready == True` and a `session` object whose `_process` is None. The daemon reader thread may remain blocked on `os.read(master_fd, ...)` until `stop()` closes the fd (causing OSError) — but `stop()` does not `join` the thread, so termination is not deterministic. Since `close()` is invoked via `asyncio.to_thread` (app_controller.py:416), the UI thread can observe `entry.ready == True` for a closed shell.
- **Fix / opportunity:** After `stop()`, set `entry.ready = False`, `entry.session = None` (before popping, or document that popped entries are stale), and join the reader thread with a short timeout.
- **Risk if ignored:** Stale "live" indicator and dangling session reference after close; thread not deterministically terminated.

### F5 · P3 · Cap-of-4 is a check-then-act race (no lock), so the 4-shell cap can be exceeded

- **Where:** `src/services/session_manager.py:20` (`MAX_CONCURRENT_SESSIONS = 4`); `entry()` `:55-58` (`if len(self.entries) >= MAX_CONCURRENT_SESSIONS: raise ...` then `self.entries[container] = entry`).
- **What:** The length check and the insert are not atomic. Two concurrent `entry()` calls (via `asyncio.to_thread`, app_controller.py:406) can both observe `len < 4` and both insert, exceeding the cap. D-017 §3 caps concurrency at 4 shells; this race violates it.
- **Fix / opportunity:** Guard the check-and-insert with the same lock as F2 so the cap is enforced atomically.
- **Risk if ignored:** More than 4 concurrent shells, contradicting D-017; unbounded PTY/process resources.

### F6 · P3 · `feed()` does not notify observers — `scrollback` is a `deque`, not Observable-wrapped

- **Where:** `src/services/session_manager.py:25-31` (`SessionEntry` is `@ft.observable`; `self.scrollback: deque[bytes] = deque(maxlen=SCROLLBACK_CHUNKS)`); `:38-39` (`feed` does `self.scrollback.append(data)`).
- **What:** `Observable._wrap_if_collection` (flet/components/observable.py:184-201) only wraps `list`/`dict` values into `ObservableList`/`ObservableDict`; a `deque` is stored unwrapped. `Observable.__setattr__` (observable.py:204-212) never sees a `scrollback` reassignment because `feed()` mutates the deque in place via `.append()`, so no `_notify` fires. Any observer subscribed to scrollback changes would never fire (currently nothing subscribes — see F1).
- **Fix / opportunity:** Either make `feed()` call `self.notify()` after appending, or switch `scrollback` to an observable list. Primary fix remains F1 (forward live bytes to canvas); this is a secondary observable-correctness issue.
- **Risk if ignored:** Observable contract for scrollback is broken; observers never fire. Low immediate impact since nothing subscribes, but it masks the F1 fix and is a latent correctness defect.

---

## Verified-good list

- Flet APIs used in session_manager.py all exist in 1.0.4: `ft.observable` (flet/components/observable.py:18-49), `@ft.component` (flet/components/component_decorator.py:10). `ft` itself imported at session_manager.py:14.
- `session_service.session_argv(container)` exists and returns `(Env, Argv)` (session_service.py:39-69); used correctly at session_manager.py:67.
- `session_service.ProotSession(argv, env, on_bytes, on_exit)` exists with `start()` (session_service.py:95), `alive` property (session_service.py:91-93), `stop()` (session_service.py:152); used correctly at session_manager.py:77-79.
- API directions confirmed against `.venv`: `set_on_bytes` = Dart→Python input (terminal.py:123-124) — correctly wired for keyboard input in terminal_view.py:105-108. `send_bytes` = Python→Dart canvas output (terminal.py:129-130; data_channel.py:65-66) — correct direction for `replay()` in terminal_view.py:98.
- `replay()` snapshots with `list(self.scrollback)` (session_manager.py:42) — defensive copy against concurrent mutation. Good.
- `close()` pops from `self.entries` (session_manager.py:85) — frees a cap slot on close. Good.
- Cap of 4 is enforced and tested (session_manager.py:55-58; tests/test_sessions.py:127-134).
- `MAX_CONCURRENT_SESSIONS = 4` and `SCROLLBACK_CHUNKS = 2000` match D-017 §3.

---

## Unverified

- Whether `entry.mt.send_bytes(data)` called from the PTY read thread (daemon thread in `ProotSession._read_loop`) is safe against Flet's data-channel locking — `send_bytes` uses `self._lock` (terminal.py:62, 135-136) so likely safe, but not proven by source inspection.
- Whether the cross-thread races (F2/F4) actually manifest on Android under real `asyncio.to_thread` scheduling — requires device/concurrence reproduction.
- Whether `ProotSession` reader thread reliably exits after `stop()` closes `master_fd` within the 2s wait — OSError delivery to blocked `os.read` is platform/PTY dependent. UNVERIFIED on device.
- Whether any caller holds a reference to a `SessionEntry` after `close()` pops it (terminal_view closures) — grep needed beyond the files read.

---

## Report contract notes

- No code, tests, pyproject, or docs were modified (read-only except this report file).
- Every defect cites `file:line` from the app and `file:line` from `.venv` where an API claim is made.
- Nothing is labeled as verified that was not confirmed against installed source; unproven items are in the Unverified section.
