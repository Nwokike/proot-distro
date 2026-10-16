# watchdog 6.0.0 — Exhaustive API Reference

**Identity:** `watchdog` 6.0.0 · Apache-2.0 (`License: Apache-2.0` in
`.venv/Lib/site-packages/watchdog-6.0.0.dist-info/METADATA`, `Summary:
Filesystem events monitoring`) · version source
`.venv/Lib/site-packages/watchdog/version.py`: `VERSION_MAJOR = 6`,
`VERSION_MINOR = 0`, `VERSION_BUILD = 0`, `VERSION_STRING = "6.0.0"`.
Pure-Python with per-OS backends + `py.typed`; declared only transitively
(`Requires-Dist: watchdog>=4.0.0` in
`.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA:14`) for
`flet run` hot-reload. Dev-loop only: zero effect in `flet build`/CI, never
ships to Android (roadmap §3 row D5; dep-test-and-lint-stack §watchdog).

**Verification method:** every claim traces to installed source (`file:line`)
or quoted live CLI output (`watchmedo --help`); unverifiable items are marked
**unverified**.

---

## 1. `Observer` — platform dispatch + every method

`Observer` is NOT a class but the result of `_get_observer_cls()` in
`.venv/Lib/site-packages/watchdog/observers/__init__.py` (`__all__ =
["Observer"]`). Selection logic (same file, verified read):

- Linux → `watchdog.observers.inotify.InotifyObserver` (guarded by
  `contextlib.suppress(UnsupportedLibcError)`), else fall through to polling.
- macOS → `fsevents.FSEventsObserver`, fallback `kqueue.KqueueObserver` with
  `warnings.warn("Failed to import fsevents…")`, else polling with warn.
- Windows → `read_directory_changes.WindowsApiObserver`, fallback polling.
- BSD → `kqueue.KqueueObserver`; anything else → `polling.PollingObserver`.

The doc-table in the same file names the five backends:
`inotify.InotifyObserver` (Linux 2.6.13+, `inotify(7)`),
`fsevents.FSEventsObserver` (macOS), `kqueue.KqueueObserver` (macOS/BSD,
`kqueue(2)`), `read_directory_changes.WindowsApiObserver` (Windows),
`polling.PollingObserver` (any — fallback). `ObserverType` Protocol:
`__call__(*, timeout: float = ...) -> BaseObserver`.

### 1.1 `BaseObserver` / `EventDispatcher` / `EventEmitter` / `ObservedWatch`

All in `.venv/Lib/site-packages/watchdog/observers/api.py` (line refs from
`grep -n "^class \|^    def "`):

- `ObservedWatch(:40)`: `__init__(path: str | Path, *, recursive: bool,
  event_filter: list[type[FileSystemEvent]] | None = None)`; props
  `path(:46)`, `is_recursive(:51)`, `event_filter(:56)`, `key(:61)`,
  `__eq__/:64 __ne__/:69 __hash__/:74 __repr__/:77`.
- `EventEmitter(BaseThread)(:87)`: `__init__(:109)`, `timeout(:124)`,
  `watch(:129)`, `queue_event(:133)`, `queue_events(timeout: float)(:145)`,
  `run(:156)`. Subclassed per backend (e.g. `InotifyEmitter(:85)` +
  `InotifyFullEmitter(:236)` in `inotify.py`; `FSEventsEmitter(:42)` in
  `fsevents.py` / `(:182)` in `fsevents2.py`; `KqueueEmitter(:352)` in
  `kqueue.py`; `PollingEmitter(:46)` in `polling.py`).
- `EventDispatcher(BaseThread)(:161)`: `__init__(*, timeout: float =
  DEFAULT_OBSERVER_TIMEOUT)(:175)`, `timeout(:181)`, `stop(:185)`,
  `event_queue(:191)`, `dispatch_events(event_queue)(:198)`, `run(:210)`.
- `BaseObserver(EventDispatcher)(:218)`: `__init__(emitter_class:
  type[EventEmitter], *, timeout: float)(:221)`, `_add_emitter(:230)`,
  `_remove_emitter(:234)`, `_clear_emitters(:241)`,
  `_add_handler_for_watch(:250)`, `_remove_handlers_for_watch(:253)`,
  `emitters(:257)`, `start(:261)`, `schedule(:270)`, `add_handler_for_watch(:317)`,
  `remove_handler_for_watch(:335)`, `unschedule(:353)`, `unschedule_all(:368)`,
  `on_thread_stop(:375)`, `dispatch_events(:378)`.

`schedule` full signature (`api.py:270-276`, docstring `:277-300`):

```python
def schedule(self, event_handler: FileSystemEventHandler, path: str, *,
             recursive: bool = False,
             event_filter: list[type[FileSystemEvent]] | None = None) -> ObservedWatch
```

`stop()` + `join()` are the shutdown pair (flet-cli calls both;
`join` inherited from the thread base — **unverified** line, behavior verified
by use). Typical lifecycle: `Observer()` → `schedule(handler, dir,
recursive=…)` → `start()` → … → `stop()` → `join()`.

### 1.2 Platform-specific observer classes (verified class names)

- Linux: `InotifyObserver(BaseObserver)` (`inotify.py:245`); emitters
  `InotifyEmitter(:85)`, `InotifyFullEmitter(:236)`; helpers `inotify_buffer.py`,
  `inotify_c.py`. flet-cli's Linux hint references inotify limits (see §4).
- macOS: `FSEventsObserver(BaseObserver)` (`fsevents.py:322`) with
  `FSEventsEmitter(:42)`; alternate `FSEventsObserver2(:251)` +
  `FSEventsEmitter(:182)`, `FSEventsQueue`, `NativeEvent` in `fsevents2.py`.
- BSD/macOS: `KqueueObserver(BaseObserver)` (`kqueue.py:649`), emitter
  `KqueueEmitter(:352)`, descriptor machinery `KeventDescriptorSet(:143)`,
  `KeventDescriptor(:275)`.
- Windows: file `read_directory_changes.py` + `winapi.py` present; class name
  `WindowsApiObserver` per `observers/__init__.py` doc-table —
  exact `class` line **unverified** in this pass (grep output truncated).
- Fallback: `PollingObserver(BaseObserver)` (`polling.py:117`,
  `__init__(*, timeout: float)`), `PollingEmitter(:46)`,
  `PollingObserverVFS(:126)` (VFS-stat variant — ctor args **unverified**).
  Selection priority is native-first, polling-last (§1 top).

`utils/` helpers (present, names verified via `ls`): `bricks.py`,
`delayed_queue.py`, `dirsnapshot.py` (polling diff core), `echo.py`,
`event_debouncer.py`, `patterns.py`, `platform.py` (`is_linux/is_darwin/
is_windows/is_bsd` used by the dispatch), `process_watcher.py`.
`tricks/` package verified present (`__init__.py` only — contents unverified).

---

## 2. `FileSystemEventHandler` — every `on_*` + `dispatch`

`.venv/Lib/site-packages/watchdog/events.py` (line refs from grep + read
`205-292`):

```python
class FileSystemEventHandler:
    def dispatch(self, event: FileSystemEvent) -> None  # :208
    def on_any_event(self, event) -> None                # :219 catch-all, always first
    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None      # :228
    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None # :237
    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent) -> None # :246
    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None # :255
    def on_closed(self, event: FileClosedEvent) -> None                   # :264
    def on_closed_no_write(self, event: FileClosedNoWriteEvent) -> None   # :273
    def on_opened(self, event: FileOpenedEvent) -> None                   # :282
```

`dispatch` body (`:217`): `self.on_any_event(event)` then
`getattr(self, f"on_{event.event_type}")(event)` — so `event_type` strings
(`moved|created|deleted|modified|closed|closed_no_write|opened`) map to the
`on_*` above; override any subset. Subclasses in the same file:
`PatternMatchingEventHandler(:292)` (glob `patterns/case_sensitive`,
`dispatch(:342)` filters `ignore_directories`, matches `dest_path+src_path`),
`RegexMatchingEventHandler(:368)` (`dispatch(:427)`), `LoggingEventHandler(:451)`
with the same `on_moved/created/deleted/modified/closed/closed_no_write/opened`
set (`:458-492`). Generators: `generate_sub_moved_events(:498)`,
`generate_sub_created_events(:525)`.

---

## 3. `FileSystemEvent` tree — every class + attrs

Base (`events.py:105-123`):

```python
class FileSystemEvent:
    src_path: bytes | str          # :113
    dest_path: bytes | str = ""    # :114 (move events only)
    event_type: str = field(default="", init=False)   # :115
    is_directory: bool = field(default=False, init=False)  # :116
    is_synthetic: bool = field(default=False)         # :123
```

`event_type` constants + classes (grep-verified lines):

| Class | Line | `event_type` | `is_directory` |
|---|---|---|---|
| `FileSystemMovedEvent(FileSystemEvent)` | :126 | `moved` (:129) | — |
| `FileDeletedEvent` | :135 | `deleted` (:138) | False |
| `FileModifiedEvent` | :141 | `modified` (:144) | False |
| `FileCreatedEvent` | :147 | `created` (:150) | False |
| `FileMovedEvent(FileSystemMovedEvent)` | :153 | inherited `moved` | False |
| `FileClosedEvent` | :157 | `closed` (:160) | False |
| `FileClosedNoWriteEvent` | :163 | `closed_no_write` (:166) | False |
| `FileOpenedEvent` | :169 | `opened` (:172) | False |
| `DirDeletedEvent` | :178 | `deleted` (:181) | True (:182) |
| `DirModifiedEvent` | :185 | `modified` (:188) | True (:189) |
| `DirCreatedEvent` | :192 | `created` (:195) | True (:196) |
| `DirMovedEvent(FileSystemMovedEvent)` | :199 | inherited `moved` | True (:202) |

Move events carry both `src_path` + `dest_path`; `is_synthetic` marks
generated (non-kernel) events. `EVENT_TYPE_*` constant names **unverified**
verbatim (values verified via the `event_type = …` assignments above).

---

## 4. `PollingObserver` + `watchmedo` CLI

`PollingObserver` = `BaseObserver` with `PollingEmitter` (snapshot-diff via
`dirsnapshot.py`); ctor `__init__(*, timeout: float =
DEFAULT_OBSERVER_TIMEOUT)` (`polling.py:122`); `PollingObserverVFS(:126)`
variant for virtual filesystems. Use when native backends unavailable or in
containers without inotify — slower, higher CPU (interval `timeout`).

`watchmedo` entry: `.venv/Scripts/watchmedo.exe --help` ≡
`python -m watchdog.watchmedo --help` (verified identical header):

```text
usage: python.exe -m watchdog.watchmedo [-h] [--version]
  {tricks-from,tricks,tricks-generate-yaml,generate-tricks-yaml,log,shell-command,auto-restart} ...
```

Every subcommand (help outputs verified for `log`, `auto-restart`,
`shell-command`, `tricks-from`; remaining `tricks*` flags partially
**unverified**):

- `log [directories…]` — print events; `-q/-v`, `-p/--pattern/--patterns`,
  `-i/--ignore-patterns`, `-D`, `-R`, `--interval TIMEOUT`,
  `--debug-force-{polling,kqueue,winapi,fsevents,inotify}`.
- `shell-command [directories…]` — `-c/--command COMMAND`, same `-p/-i/-D/-R/
  --interval`, plus `-w/-W` (wait flags — exact semantics unverified).
- `auto-restart [-d DIRECTORY] [-p/-i/-D/-R/--interval] [--signal SIGNAL]
  [--kill-after KILL_AFTER] [--debounce-interval DEBOUNCE_INTERVAL]
  [--no-restart-on-command-exit] command [arg …]` (use `--` before command args).
- `tricks-from [--python-path] [--interval] [--recursive]
  [--debug-force-*] [files …]`; `tricks`, `tricks-generate-yaml`,
  `generate-tricks-yaml` (YAML trick pipelines — details unverified).

---

## 5. How flet-cli's `flet run` hot-reload uses it (quote sites)

`.venv/Lib/site-packages/flet_cli/commands/run.py`:

- Imports (`:17-18`): `from watchdog.events import FileSystemEventHandler`,
  `from watchdog.observers import Observer`.
- CLI surface (`:144-149`, `:193`): `--recursive` (`dest="recursive"`,
  "sub-directories recursively") and `--ignore-dirs` (`dest="ignore_dirs"`).
- Wire-up (`:368-371`): `my_observer = Observer()`;
  `my_observer.schedule(my_event_handler, script_dir, recursive=options.recursive)`;
  `try: my_observer.start() except OSError as e:` → `Warning: file watching is
  unavailable (…), so the app won't reload on changes.` + Linux inotify-limits
  hint (`:372-383`); `my_observer = None` fallback.
- Loop (`:385-403`): `my_event_handler.start_process()`; `while True:
  if my_event_handler.terminate.wait(1): break`; `KeyboardInterrupt: pass`;
  finally `my_observer.stop(); my_observer.join()` (`:401-403`).
- `Handler(FileSystemEventHandler)` (`:406-459`): stores `watch_directory,
  script_path, ignore_dirs, terminate = threading.Event(), last_time,
  is_running, …`; `on_any_event(:535)`: skips events under `ignore_dirs`
  (`commonpath` check), reacts only when `watch_directory or
  event.src_path == script_path` and `event.event_type in ["modified",
  "deleted", "created", "moved"]`, debounced `> 0.5 s`, spawning
  `threading.Thread(target=self.restart_program, daemon=True)`; `restart_program`
  SIGTERMs + `wait()`s then `start_process()` (`:629-636`).

So: watchdog watches the script dir, any create/modify/delete/move restarts the
app process — desktop hot-reload only. Nothing here touches `flet build`, CI, or
the APK.

## 6. How watchdog makes our app significantly better than Termux's proot-distro

Honestly: it does NOT make the app itself better — it is dev-loop only (stated
per roadmap D5). The Termux comparison is about workflow, not product: Termux
proot-distro development is edit → manually re-run shell steps on-device;
our Flet loop is `flet run` → save → watchdog restarts the desktop app in
<1 s with a 0.5 s debounce and ignore-dirs filtering. That tightens UI
iteration for screens/services/terminal-bridge code that never needs a device.
It contributes zero APK bytes, zero runtime behavior, zero CI signal — and
must stay that way (no in-app file-watching; Android has no use for it and the
polling fallback would burn battery).

## 7. Fullest utilization — concrete for THIS project

watchdog: use as-is via `flet run [--recursive] [--ignore-dirs]` during M3/M4
UI work; no config, no wrapper, no dependency to declare (transitive via
flet-cli). Do NOT add it to our `dependencies`, do NOT write handlers, do NOT
gate tests on it. The one operational note: on Linux CI/dev-hosts hitting
`ENOSPC/EMFILE`, raise inotify limits per the flet-cli warning link — host
tuning, not app code.

## 8. Verification refs

- `watchdog/version.py` (`VERSION_*`); `watchdog-6.0.0.dist-info/METADATA:1-11`.
- `watchdog/observers/__init__.py` (dispatch + table + `__all__`);
  `observers/api.py:20-378` (method inventory + `schedule:270` docstring);
  `observers/{inotify.py:85,236,245, kqueue.py:143,275,352,649,
  fsevents.py:42,322, fsevents2.py:72,143,182,251, polling.py:46,117,126}`;
  `utils/` + `tricks/` listings; `watchmedo.py` + `watchmedo.exe --help`,
  `watchmedo {log,shell-command,auto-restart,tricks-from} --help`.
- `watchdog/events.py:105-202` (event tree), `:205-292` (`Handler` +
  `dispatch` body), `:292-492` (pattern/regex/logging handlers),
  `:498,525` (generators).
- `flet_cli/commands/run.py:16-18,144-149,193,274-279,350-403,406-460,535-560,607-636`
  (imports, flags, schedule/start/stop/join, `Handler`, debounce restart).
- `flet_cli-1.0.4.dist-info/METADATA:14,16` (`watchdog>=4.0.0`,
  `qrcode>=7.4.2` floors); `docs/roadmap.md` §3 D5 + §1b; house study
  `docs/reference/dep-test-and-lint-stack.md` §watchdog.
- **Unverified**: `WindowsApiObserver` exact class line; `PollingObserverVFS`
  ctor; `EVENT_TYPE_*` constant identifiers; `tricks*` YAML subcommand flags;
  `shell-command -w/-W` semantics.
