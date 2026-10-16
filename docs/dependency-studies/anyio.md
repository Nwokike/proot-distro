# anyio — exhaustive API reference (installed 4.15.1)

Verified 2026-10-16 against `.venv/Lib/site-packages/anyio` (4.15.1) via live introspection
(`.venv/Scripts/python.exe`) + source reads. Context: `docs/roadmap.md`,
`docs/reference/dep-httpx-cluster.md`. Project: Flet Android app (proot-distro wrapper;
flet stays 1.0.4 per D-010). Anti-hallucination rule: every signature below was obtained
by live `inspect.signature` except where explicitly marked **unverified**; file:line refs
point at the installed source.

## 1. Identity

| Fact | Value (verified) |
|---|---|
| Version | **4.15.1** (`anyio-4.15.1.dist-info/METADATA`, `Name: anyio`, `Version: 4.15.1`) |
| License | **MIT** (`License-Expression: MIT` in METADATA) |
| Summary | "High-level concurrency and networking framework on top of asyncio or Trio" (METADATA) |
| Pure-Python | Yes — no compiled extensions in the installed tree (only `.py`, `py.typed`); ships unmodified into the APK |
| Backends | `asyncio` + `trio` (`anyio/_backends/` holds both; `get_all_backends`, `get_available_backends` in `_core/_eventloop.py:136,141`) |
| Live backend here | **asyncio only** — `trio`, `sniffio`, `outcome`, `uvloop` all absent from `.venv/Lib/site-packages` (verified by directory listing); trio is an optional extra (`Requires-Dist: trio>=0.32.0; extra == "trio"`, METADATA:31). `get_available_backends()` returns only what is importable, so here it is `('asyncio',)` |
| Why asyncio | The Flet session loop is asyncio; httpx uses anyio for async IO on the asyncio backend; no trio code can run on-device because trio is not installed |
| Python support | `Requires-Python: >=3.10` (METADATA); our runtime is the Flet-bundled Python 3.14 |
| Deps of anyio itself | `exceptiongroup>=1.0.2` (only py<3.11), `idna>=2.8`, `typing_extensions>=4.16.0` (only py<3.15) — METADATA |
| Typing | Fully typed (`py.typed` present); generic streams/locks carry statistics dataclasses |

## 2. Complete public API (top-level `anyio.*`)

Source of truth: `anyio/__init__.py` (lazy-import table). Every name below is a verified
top-level export. Signatures are live introspection unless marked **unverified**.

### 2.1 Entry point + clock (`_core/_eventloop.py`)

| Export | Signature (verified) | Source |
|---|---|---|
| `run` | `(func: Callable[[Unpack[PosArgsT]], Awaitable[T_Retval]], *args: Unpack[PosArgsT], backend: str = 'asyncio', backend_options: dict[str, Any] \| None = None) -> T_Retval` | `_core/_eventloop.py:38` |
| `sleep` | `(delay: float) -> None` | `_core/_eventloop.py:88` |
| `sleep_forever` | `() -> None` | `_core/_eventloop.py:98` |
| `sleep_until` | `(deadline: float) -> None` | `_core/_eventloop.py:110` |
| `current_time` | `() -> float` | `_core/_eventloop.py:124` |
| `get_all_backends` | `() -> tuple[str, ...]` | `_core/_eventloop.py:136` |
| `get_available_backends` | `() -> tuple[str, ...]` | `_core/_eventloop.py:141` |
| `get_cancelled_exc_class` | `() -> type[BaseException]` | `_core/_eventloop.py:162` |

Notes: `run()` is the sync entry that boots the chosen backend and runs the async main;
`backend='asyncio'` is the default — always pass explicitly in our code for clarity.
`sleep(0)` / `sleep_until` use the event-loop clock (`current_time`), not wall time.

### 2.2 Task groups + cancellation (`_core/_tasks.py`)

| Export | Signature (verified) | Source |
|---|---|---|
| `create_task_group` | `() -> TaskGroup` (use as `async with`) | `_core/_tasks.py:238` |
| `CancelScope` | `(*, deadline: float = inf, shield: bool = False) -> CancelScope` | `_core/_tasks.py:43` |
| `CancelScope.cancel` | `(self, reason: str \| None = None) -> None` | introspected |
| `CancelScope` attrs | `cancel_called`, `cancelled_caught`, `deadline`, `shield` | introspected `dir()` |
| `move_on_after` | `(delay: float \| None, shield: bool = False) -> CancelScope` | `_core/_tasks.py:201` |
| `move_on_at` | `(deadline: float \| None, shield: bool = False) -> CancelScope` | `_core/_tasks.py:182` |
| `fail_after` | `(delay: float \| None, shield: bool = False, reason: str \| None = None) -> Generator[CancelScope, None, None]` | `_core/_tasks.py:159` |
| `fail_at` | `(deadline: float \| None, shield: bool = False, reason: str \| None = None) -> Generator[CancelScope, None, None]` | `_core/_tasks.py:128` |
| `current_effective_deadline` | `() -> float` | `_core/_tasks.py:222` |
| `TASK_STATUS_IGNORED` | sentinel `_IgnoredTaskStatus` instance | `_core/_tasks.py` + `anyio/__init__.py` |
| `TaskHandle` | generic handle returned by `TaskGroup.start_soon` — **unverified** (type only, not introspected) | `anyio/__init__.py` |

`abc.TaskGroup` methods (verified introspection on `anyio.abc.TaskGroup`):

```text
start_soon(self, func: Callable[[Unpack[PosArgsT]], Coroutine[Any, Any, T_co]], *args: Unpack[PosArgsT], name: object = None) -> TaskHandle[T_co]
start(self, func: Callable[..., Coroutine[Any, Any, T_co]], *args: object, name: object = None, return_handle: Literal[False, True] = False) -> Any
cancel(self) / create_task(...) — present (dir-verified; full overloads unverified)
```

Semantics: exiting the `async with create_task_group()` block waits for all children;
any child exception cancels the scope and re-raises (structured concurrency — no orphan
tasks). `start()` waits until the child calls `task_status.started()`; `start_soon()`
fires and forgets inside the group. `move_on_*` swallow timeout cancellation;
`fail_*` raise `TimeoutError` on expiry. `shield=True` protects cleanup from outer cancel.

### 2.3 Concurrency helpers (`_core/_concurrency_utils.py`)

| Export | Signature (verified) | Source |
|---|---|---|
| `gather` | `(*coros: Coroutine[Any, Any, Any]) -> tuple[Any, ...]` | `_concurrency_utils.py:80` |
| `as_completed` | `(*awaitables: Awaitable[R]) -> AsyncGenerator[MemoryObjectReceiveStream[TaskHandle[R]]]` | introspected (overloads at `_concurrency_utils.py:97`) |
| `amap` | `(func: Callable[[T], Coroutine[Any, Any, R]], args: Iterable[T]) -> list[R]` | introspected |

### 2.4 Thread bridging — `anyio.to_thread` / `anyio.from_thread`

`to_thread` (`anyio/to_thread.py`):

```text
run_sync(func: Callable[[Unpack[PosArgsT]], T_Retval], *args: Unpack[PosArgsT], abandon_on_cancel: bool = False, cancellable: bool | None = None, limiter: CapacityLimiter | None = None) -> T_Retval  # to_thread.py:27
current_default_thread_limiter() -> CapacityLimiter  # to_thread.py:70
```

`from_thread` (`anyio/from_thread.py`):

```text
run(func: Callable[[Unpack[PosArgsT]], Coroutine[Any, Any, T_co]], *args: Unpack[PosArgsT], token: EventLoopToken | None = None) -> T_co        # from_thread.py:68
run_sync(func: Callable[[Unpack[PosArgsT]], T_Retval], *args: Unpack[PosArgsT], token: EventLoopToken | None = None) -> T_Retval                  # from_thread.py:96
start_blocking_portal(backend: str = 'asyncio', backend_options: dict[str, Any] | None = None, *, name: str | None = None) -> Generator[BlockingPortal, Any, None]  # from_thread.py:506
BlockingPortal methods (dir-verified): call, sleep_until_stopped, start_task, start_task_soon, stop, wrap_async_context_manager
```

Rule: async→sync-blocking work uses `await to_thread.run_sync(fn)`; sync thread→loop
uses `from_thread.run(coro)` / `run_sync(fn)`. `BlockingPortal` (with
`start_blocking_portal()`) is the long-lived bridge for threads that must submit many
calls (e.g. a reader thread pumping into the loop). Default thread limiter caps at
~40 workers (`current_default_thread_limiter`).

### 2.5 Process / interpreter offload — `anyio.to_process`, `anyio.to_interpreter`

```text
# to_process.py:45,191
to_process.run_sync(func, *args, cancellable: bool = False, limiter: CapacityLimiter | None = None) -> T_Retval
to_process.current_default_process_limiter() -> CapacityLimiter
# to_interpreter.py:174,231
to_interpreter.run_sync(func, *args, limiter: CapacityLimiter | None = None) -> T_Retval
to_interpreter.current_default_interpreter_limiter() -> CapacityLimiter
```

Both modules also export their `BrokenWorkerProcess` / `BrokenWorkerInterpreter`
exceptions. **Not for Android use** — process spawn under serious_python + subinterpreters
are both unverified on-device; document only, do not call from the app (see §5).

### 2.6 Synchronization (`_core/_synchronization.py`)

```text
Event() -> Event                                    # _synchronization.py:88
  .set() -> None / .wait() -> None / .is_set() -> bool
Lock(*, fast_acquire: bool = False) -> Lock         # _synchronization.py:161
  .acquire() / .release() + async-context-manager support
Semaphore(initial_value: int, *, max_value: int | None = None, fast_acquire: bool = False)  # :388
  .acquire() -> None / .release() -> None
CapacityLimiter(total_tokens: float) -> CapacityLimiter  # :534
  .acquire() / .acquire_nowait() / .acquire_on_behalf_of(borrower: object) / .acquire_on_behalf_of_nowait(...)
  .release() / .release_on_behalf_of(...) / .available_tokens / .borrowed_tokens / .total_tokens / .statistics()
Condition(lock: Lock | None = None)                 # :276
  .acquire() / .wait() -> None / .notify(n: int = 1) / .notify_all()
ResourceGuard(action: str = 'using')                # :746
Statistics dataclasses: EventStatistics, LockStatistics, SemaphoreStatistics, CapacityLimiterStatistics, ConditionStatistics
```

`CapacityLimiter` is the concurrency-cap primitive (the CollabShell pattern): share one
limiter across `to_thread.run_sync(..., limiter=...)` calls to bound simultaneous
downloads/extracts. `ResourceGuard` raises `BusyResourceError` on re-entrant use.

### 2.7 Memory object streams (`_core/_streams.py`, `streams/memory.py`)

```text
create_memory_object_stream(max_buffer_size: float = 0, item_type: object = None) -> tuple[MemoryObjectSendStream[T], MemoryObjectReceiveStream[T]]  # verified introspection
MemoryObjectSendStream: send / send_nowait / aclose / close / clone / statistics / extra  (streams/memory.py:199)
MemoryObjectReceiveStream: receive / receive_nowait / aclose / close / clone / statistics / extra  (streams/memory.py:80)
```

`max_buffer_size=0` = rendezvous (send waits for receive); `>0` buffers that many items;
`float('inf')` = unbounded. Cloning either end multiplies producers/consumers.
`receive()` raises `EndOfStream` when all send ends close; `send_nowait` raises
`WouldBlock` when full; `receive_nowait` raises `WouldBlock` when empty.

### 2.8 Subprocesses (`_core/_subprocesses.py`)

```text
run_process(command: StrOrBytesPath | Sequence[StrOrBytesPath], *, input: bytes | None = None, stdin: int | IO[Any] | None = None, stdout: int | IO[Any] | None = -1, stderr: int | IO[Any] | None = -1, check: bool = True, cwd: StrOrBytesPath | None = None, env: Mapping[str, str] | None = None, startupinfo: Any = None, creationflags: int = 0, start_new_session: bool = False, pass_fds: Sequence[int] = (), user/group/extra_groups/umask...) -> CompletedProcess[bytes]  # :16
open_process(command, *, stdin=-1, stdout=-1, stderr=-1, cwd/env/startupinfo/creationflags/start_new_session/pass_fds/user/group/extra_groups/umask...) -> Process  # :122
abc.Process (dir-verified): aclose, kill, pid, returncode, send_signal, stderr, stdin, stdout, terminate, wait
```

`run_process` = one-shot (completed output); `open_process` = interactive (`Process.stdin`
is a byte-send stream, `.stdout`/`.stderr` byte-receive streams). `check=True` raises
`CalledProcessError` on non-zero exit. PTY caveat: neither attaches a PTY — interactive
shells need the flet-terminal view + stdin pump, not a pty on the Python side (M0
resolution: package stays view-only, app owns `ProotSession`).

### 2.9 Sockets / networking (`_core/_sockets.py`)

```text
connect_tcp(remote_host, remote_port, *, local_host=None, local_port=None, tls=False, ssl_context=None, tls_standard_compatible=True, tls_hostname=None, happy_eyeballs_delay=0.25) -> SocketStream | TLSStream  # :145 (overloads :73-135)
create_tcp_listener(*, local_host=None, local_port=0, family=AF_UNSPEC, backlog=65536, reuse_port=False) -> MultiListener[SocketStream]  # :300
connect_unix(path: str | bytes | PathLike[Any]) -> UNIXSocketStream  # :285
create_unix_listener(path, *, mode=None, backlog=65536) -> SocketListener  # :437
create_udp_socket(family=AF_UNSPEC, *, local_host=None, local_port=0, reuse_port=False) -> UDPSocket  # :469
create_connected_udp_socket(remote_host, remote_port, *, family=AF_UNSPEC, local_host=None, local_port=0, reuse_port=False) -> ConnectedUDPSocket
create_unix_datagram_socket(*, local_path=None, local_mode=None) -> UNIXDatagramSocket
create_connected_unix_datagram_socket(remote_path, *, local_path=None, local_mode=None) -> ConnectedUNIXDatagramSocket
getaddrinfo(host, port, *, family=0, type=0, proto=0, flags=0) -> list[...]
getnameinfo(sockaddr, flags=0) -> Awaitable[tuple[str, str]]
wait_readable(obj: FileDescriptorLike) -> Awaitable[None]
wait_writable(obj: FileDescriptorLike) -> Awaitable[None]
as_connectable(remote, /, *, tls=False, ssl_context=None, tls_hostname=None, tls_standard_compatible=True) -> ByteStreamConnectable
notify_closing(obj: FileDescriptorLike) -> None
TCPConnectable / UNIXConnectable — connectable descriptors (export-verified; constructors unverified)
wait_socket_readable / wait_socket_writable — export-verified; signatures unverified
```

`abc` stream/listener types (`SocketStream`, `TLSStream`, `SocketListener`,
`MultiListener`, `UDPSocket`, `ConnectedUDPSocket`, …) are all export-verified under
`anyio.abc` (dir-verified list §2.12).

### 2.10 Lowlevel (`anyio/lowlevel.py`)

```text
checkpoint() -> None                  # lowlevel.py:28  — cancel + schedule point
checkpoint_if_cancelled() -> None     # lowlevel.py:43  — checkpoint only if cancel pending
cancel_shielded_checkpoint() -> None  # lowlevel.py:55  — schedule point, never cancels
RunVar(name: str, default=NO_VALUE_SET)  # lowlevel.py:133 — run-local variable
  RunVar methods (dir-verified): get / set / reset (+ NO_VALUE_SET sentinel)
current_token() / get_async_backend() — present (unverified signatures)
```

Every `await` on an anyio primitive contains a checkpoint; bare `checkpoint()` forces
one where none would otherwise occur (keeps `wait_all_tasks_blocked` honest in tests).

### 2.11 File I/O + tempfile (`_core/_fileio.py`, `_core/_tempfile.py`)

```text
open_file(file: str | PathLike[str] | int, mode='r', buffering=-1, encoding=None, errors=None, newline=None, closefd=True, opener=None, *, limiter=None) -> AsyncFile[Any]  # _fileio.py:175+ (overloads :190,:204)
wrap_file(file: IO[AnyStr], *, limiter=None) -> AsyncFile[AnyStr]  # _fileio.py:244
Path — async wrapper of pathlib.Path (class _fileio.py:280); await read_text/write_text/mkdir/stat/exists/iterdir etc.
aclose_forcefully(resource: AsyncResource) -> None  (verified)
open_signal_receiver(*signals: Signals) -> AbstractContextManager[AsyncIterator[Signals]]  (verified; POSIX-only — unusable on Android, document only)
Tempfile (all async context managers): TemporaryFile(mode='w+b', ...) / NamedTemporaryFile(...) / SpooledTemporaryFile / TemporaryDirectory / mkstemp(...) / mkdtemp(...) / gettempdir() / gettempdirb()
```

`AsyncFile` runs blocking file IO in the thread limiter — correct way to hash/verify
large rootfs tarballs without stalling the loop.

### 2.12 Abstract types (`anyio.abc` — dir-verified)

`AsyncResource`, `TaskGroup`, `TaskStatus`, `Process`, `TestRunner`,
`ByteReceiveStream`, `ByteSendStream`, `ByteStream`, `ByteStreamConnectable`,
`AnyByteReceiveStream`, `AnyByteSendStream`, `AnyByteStream`, `AnyByteStreamConnectable`,
`UnreliableObjectReceiveStream`, `UnreliableObjectSendStream`, `UnreliableObjectStream`,
`AnyUnreliableByteReceiveStream`, `AnyUnreliableByteSendStream`, `AnyUnreliableByteStream`,
`ObjectReceiveStream`, `ObjectSendStream`, `ObjectStream`, `ObjectStreamConnectable`,
`SocketStream`, `SocketListener`, `SocketAttribute`, `Listener`,
`UDPSocket`, `ConnectedUDPSocket`, `UNIXSocketStream`, `UNIXDatagramSocket`,
`ConnectedUNIXDatagramSocket`, `IPAddressType`, `IPSockAddrType`,
`UDPPacketType`, `UNIXDatagramPacketType`.

### 2.13 Testing utilities (`_core/_testing.py`)

```text
get_current_task() -> TaskInfo        # _testing.py:56
get_running_tasks() -> list[TaskInfo] # _testing.py:68
wait_all_tasks_blocked() -> None      # _testing.py:80
TaskInfo — dataclass (class _testing.py:9)
pytest_plugin.py — anyio_backend fixture (export-verified; parametrization unverified)
```

Pattern: `await wait_all_tasks_blocked()` after spawning, then assert on
`get_running_tasks()` — deterministic structured-concurrency tests with zero sleeps.

### 2.14 Typed attributes + context mixins (export-verified, signatures unverified)

`TypedAttributeProvider`, `TypedAttributeSet`, `typed_attribute`,
`AsyncContextManagerMixin`, `ContextManagerMixin`.

### 2.15 Helper submodules (export-verified)

`anyio.functools` (`cache`, `lru_cache`, async variants), `anyio.itertools`
(async `chain`, `islice`, `count`, `cycle`, `zip_longest`, …), `anyio.to_interpreter`
(see §2.5). Full function lists dir-verified; individual signatures unverified.

### 2.16 Exceptions (`_core/_exceptions.py` — ALL, class lines verified)

| Exception | Line | Meaning |
|---|---|---|
| `BrokenResourceError` | :12 | peer vanished mid-stream (connection dropped) |
| `BusyResourceError` | :61 | guarded resource re-entered (`ResourceGuard`) |
| `ClosedResourceError` | :71 | used after `aclose()` |
| `ConnectionFailed` | (module, line unverified) | connect failed |
| `DelimiterNotFound` | :93 | `receive_until` exceeded max bytes without delimiter |
| `EndOfStream` | :106 | clean EOF on a receive stream |
| `IncompleteRead` | :112 | stream ended mid-frame |
| `WouldBlock` | :133 | non-blocking op would block (`send_nowait`/`receive_nowait`) |
| `TaskCancelled` / `TaskFailed` / `TaskNotFinished` | module | task-lifecycle states |
| `FutureCancelled` / `FutureFailed` / `FutureFinished` family (`FutureAlreadyFinished`, `FutureNotFinished`) | module | `anyio.Future` states |
| `BrokenWorkerProcess` / `BrokenWorkerInterpreter` | module | offload worker died |
| `NoEventLoopError` | module | `from_thread` with no running loop |
| `RunFinishedError` | module | portal used after loop end |
| `TypedAttributeLookupError` | module | missing socket extra attribute |

`Future` itself (`_core/_futures.py`) is export-verified; per-method signatures unverified.

## 3. How it serves us (Flet session loop is asyncio; httpx rides anyio)

- **httpx uses anyio for async IO.** Our app makes no direct httpx calls (no OAuth), so
  the cluster is dormant — but anyio is still the correct async dialect for OUR code
  because httpx already drags it into the APK for free.
- **Install-progress streaming into the UI:** `create_memory_object_stream(ItemType)`
  producer/consumer pair. Downloader coroutine `await send_stream.send(Progress(...))`;
  UI coroutine `async for p in receive_stream: page update`. Bounded buffer
  (`max_buffer_size=50`) gives backpressure; `send_nowait` + `WouldBlock` catch lets the
  producer shed load instead of stalling. This replaces `contextlib.redirect_stderr`
  scraping with a typed pipeline the moment M3 wraps installs in coroutines.
- **Cancellation of long installs:** wrap each install in
  `with move_on_after(timeout):` (soft UI timeout) or `with CancelScope()` + explicit
  `.cancel()` wired to the page's Cancel button. `cancelled_caught=True` tells the UI
  "user cancelled" vs real failure. Cleanup (partial rootfs delete, lock release) goes
  in `with CancelScope(shield=True):` so cancelling never leaves a half-extracted
  `containers/<name>/rootfs`. This is strictly beyond what `asyncio.to_thread` alone gives.
- **Thread bridging — `to_thread` vs `asyncio.to_thread`:** prefer
  `await anyio.to_thread.run_sync(sync_install_fn, limiter=install_limiter)` because
  (a) it honors a shared `CapacityLimiter` across all call sites, (b) `abandon_on_cancel`
  / `cancellable` give defined cancel semantics, (c) the code stays backend-agnostic if
  httpx ever needs trio compat. `asyncio.to_thread` (roadmap M3 default) has none of
  these — keep it only for one-liners outside anyio task groups.
- **`CapacityLimiter` for concurrency caps (CollabShell pattern):** one module-level
  `DOWNLOAD_LIMITER = CapacityLimiter(2)` shared by every OCI layer fetch +
  `INSTALL_LIMITER = CapacityLimiter(1)` serializing extractions (UBIFS-style flash
  wear + ANR avoidance). Pass explicitly — never rely on the ambient default limiter.
- **Subprocess spawning (`anyio.open_process` vs raw subprocess):** `open_process` gives
  async stdin/stdout byte streams that plug straight into the `ProotSession` bridge
  (`send_input`/`on_stdout`) without a pump thread. Caveats: no PTY (matches M0 —
  flet-terminal is view-only, app owns the session); job control / `start_new_session`
  semantics on Android are **unverified** — prove in M0 gate 4 before depending on
  signal forwarding; one-shot `pd install`-CLI fallback uses `run_process(check=True)`.

## 4. How this dependency makes our app significantly better than Termux's proot-distro

Termux's proot-distro is a shell experience: `proot-distro install ubuntu` blocks a
terminal, `Ctrl-C` may leave a torn rootfs, parallel installs trample each other, and
progress is stderr lines. anyio lets our app be a managed installer instead of a
terminal wrapper:

1. **Structured concurrency — no orphan installs.** Each install runs in a task group;
   leaving the screen cancels its scope and the group teardown joins every child.
   Termux cannot guarantee this — a killed terminal leaves proot/tar children behind.
2. **Cancellable installs with clean teardown.** Cancel button → `scope.cancel()` →
   shielded cleanup deletes `containers/<name>/{rootfs,manifest.json,shm}` fragments
   and releases `ContainerLock`. Shell `Ctrl-C` gives no such two-phase guarantee.
3. **Responsive UI during long pulls.** Thread-limiter offload keeps the Flet loop at
   60 fps while layers download/extract; memory-stream backpressure turns byte bars
   into smooth determinate progress + stage labels. Termux shows raw tar chatter.
4. **Concurrency caps that protect flash and RAM.** A single `CapacityLimiter(1)` around
   extraction prevents two simultaneous `tar`/`zstd` storms from OOM-killing the app on
   4 GB phones — a shell user gets no guardrails.
5. **One bridge shape for both M4 modes.** The same `open_process` byte streams feed
   the interactive console AND the structured command→outputs mode (CollabShell
   notebook mapping); Termux has only the console.

## 5. Fullest-utilization proposals (tied to M3/M4)

- **P1 — Progress pipeline (M3):** `services/install_pipeline.py`: producer coroutine
  wraps `_run_install` in `to_thread.run_sync` and forwards parsed stage lines into a
  `create_memory_object_stream(ProgressEvent, max_buffer_size=64)`; screen consumes with
  `async for`. Acceptance: cancel mid-download → `EndOfStream` closes the UI iterator,
  no leaked thread.
- **P2 — Cancellable installs (M3):** every install under
  `with CancelScope() as scope:` stored on `AppState`; Cancel button calls
  `scope.cancel()`; `finally: with CancelScope(shield=True): cleanup_partial(name)`.
  Timeout variant: `move_on_after(600)` for 10-min OCI pulls with friendly retry UI.
- **P3 — Session manager (M4):** `services/session_manager.py` owns one task group per
  terminal tab; each session = `open_process(login_argv)` + stdin-pump task +
  stdout-pump task into `MemoryObjectSendStream[bytes]` feeding flet-terminal.
  Tab close cancels that tab's scope only. `CapacityLimiter(4)` caps concurrent sessions.
- **P4 — Probe + prefetch (M3):** `gather(probe_proot(), probe_arch(), probe_storage())`
  in parallel at startup; `wait_all_tasks_blocked()` in widget tests for determinism.
- **Non-goals:** trio backend, `to_process`/`to_interpreter`, `open_signal_receiver`,
  UDP/TCP listeners — no server sockets on-device; document-only.

## 6. Android notes

- **Private import (dep-httpx-cluster §19):** `anyio/_backends/_asyncio.py:21` does
  `from asyncio.base_events import _run_until_complete_cb` with
  `# type: ignore[attr-defined]`, used at `:321` (`cb is _run_until_complete_cb`).
  Only a CPython major bump in the Flet build recipe (3.14 → 3.15) can break it;
  pin-watch the template, do not patch.
- **Trio absence:** trio is not installed and not on pypi.flet.dev; any
  `backend="trio"` call fails at runtime. Hard-require asyncio in every `run()` /
  portal call and assert `get_available_backends() == ("asyncio",)` in a startup probe.
- **Signals:** `open_signal_receiver` is POSIX-only — no SIGCHLD/SIGTERM delivery
  semantics on Android; use task-group cancellation instead of signal handling.
- **Threads:** the default thread limiter (~40) is generous for a phone — always pass
  explicit small limiters (1–2) for disk/network work to avoid ANRs and flash contention.
- **Subprocess:** `open_process`/`run_process` on serious_python need M0-gate-4 proof;
  keep the raw-`subprocess` + `--get-proot-cmd` fallback behind the same interface.

## 7. Verification

- Installed tree: `.venv/Lib/site-packages/anyio/` (`__init__.py` export table,
  `_core/`, `_backends/`, `abc/`, `streams/`, `to_thread.py`, `from_thread.py`,
  `to_process.py`, `to_interpreter.py`, `lowlevel.py`, `pytest_plugin.py`).
- Live introspection: `.venv/Scripts/python.exe -c` with `inspect.signature` /
  `dir()` for every signature above not marked unverified (2026-10-16).
- File:line refs in §2 point at the installed files (e.g. `_core/_tasks.py:43`,
  `_backends/_asyncio.py:21,321`, `_core/_exceptions.py:12,61,71,93,106,112,133`).
- Cross-refs: `docs/roadmap.md` (§1c CollabShell pattern, M3 proot_service/M4 sessions),
  `docs/reference/dep-httpx-cluster.md` (cluster dormancy, certifi, private-import note).
- Absence proofs: `ls site-packages | grep -i trio/sniffio/outcome/uvloop` empty;
  `Provides-Extra: trio` in `anyio-4.15.1.dist-info/METADATA:31`.
