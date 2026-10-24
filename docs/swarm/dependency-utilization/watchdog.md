# watchdog 6.0.0 — utilization audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/watchdog.md`; `docs/reference/dep-test-and-lint-stack.md:23-25`; `docs/decisions.md:13,19`; `pyproject.toml:9-15,20-31,62-63,77-84`; `uv.lock:220-232,582-604,831-834`; `.github/workflows/app.yml:39-303`; `build_flet_proot_wheel.py:1-503`; `src/main.py:1-40`; `src/core/storage_paths.py:1-59`; `src/core/proot_probe.py:65-97`; `src/core/brand_hero.py:17-29`; `src/services/session_service.py:95-134`; `src/services/session_manager.py:38-43`; `src/services/proot_service.py:53-105`; `src/screens/terminal_view.py:59-122`; `src/screens/views.py:20,626-628`; `.venv/Lib/site-packages/watchdog/{version.py,observers/__init__.py,observers/api.py,observers/polling.py,observers/inotify.py,observers/inotify_c.py,observers/read_directory_changes.py,observers/winapi.py,events.py,watchmedo.py,tricks/__init__.py}`; `.venv/Lib/site-packages/flet_cli/commands/run.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/flet_cli/utils/{project_dependencies.py,pyproject_toml.py}`; `.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA`; `.venv/Lib/site-packages/watchdog-6.0.0.dist-info/METADATA`; live probes against the repo's own `src/` tree · **Date:** 2026-10-22

## What it does / how the app uses it

**watchdog is a transitive, host-only, dev-loop dependency. The app uses it not at all.**

It is not declared by this repo: `pyproject.toml:9-15` (runtime) and `:77-84` (dev) contain no `watchdog` entry; `uv.lock:831-834` records `watchdog 6.0.0` with the single importer `flet-cli` (`uv.lock:220-232`, `uv.lock:232` `{ name = "watchdog" }` under `flet-cli`). The only `Requires-Dist: watchdog>=4.0.0` in the whole environment is `flet_cli-1.0.4.dist-info/METADATA:14`.

Its one consumer in the entire installed tree is `flet run`'s hot-reload loop:

```text
$ grep -rn "watchdog\|Observer\|FileSystemEvent" .venv/Lib/site-packages/flet_cli/ --include="*.py"
.venv/Lib/site-packages/flet_cli/commands/run.py:17:from watchdog.events import FileSystemEventHandler
.venv/Lib/site-packages/flet_cli/commands/run.py:18:from watchdog.observers import Observer
.venv/Lib/site-packages/flet_cli/commands/run.py:368:        my_observer = Observer()
.venv/Lib/site-packages/flet_cli/commands/run.py:406:class Handler(FileSystemEventHandler):
```

(zero hits in `flet/`, `flet_desktop/`, `flet_ads/`, `flet_terminal/`, `proot_distro/`, and in `flet_cli/commands/build_base.py` / `flutter_base.py`).

**It is dormant/inert for the shipped product.** `flet build` resolves the shipped Python set from `project.dependencies` + `tool.flet.<platform>.dependencies` only (`build_base.py:2566-2574`, `:2592-2596`, `:2606`), so the runtime closure never contains watchdog:

```text
$ .venv/Scripts/python.exe -c "…get_project_dependencies(pp['project']['dependencies'])…"
project.dependencies      -> ['flet >=1.0.4', 'flet-ads >=1.0.4', 'flet-terminal >=0.4.0', 'httpx >=0.28.1', 'proot-distro >=5.10.0']
tool.flet.android.deps    -> ['flet-proot==5.1.107.98']
watchdog in the shipped set? False
```

Runtime closure of `[project].dependencies` (extras excluded): `anyio, certifi, flet, flet-ads, flet-terminal, h11, httpcore, httpx, idna, msgpack, oauthlib, proot-distro, repath, six, typing_extensions` — **watchdog is not in it**. Zero APK/AAB bytes, zero runtime behavior, zero CI signal.

**Is it dev-only? Yes — and its only live effect is on the `flet run` desktop hot-reload.** `run.py:368-383` creates the observer, `run.py:369` schedules the app's script directory, `run.py:385-403` runs the restart loop and stops/joins the observer, and `run.py:535-560` (`on_any_event`) decides when to restart. `flet build` and CI never touch it.

**Does the app or any host tool need filesystem watching? No.** There is no log tailing, no build-output watch, and no live asset reload anywhere:

- **No log tailing.** The app's only "log" is the guest shell's PTY stream, which is a live fd read, not a file: `src/services/session_service.py:113-134` (`os.read(master_fd, 4096)` on a thread), `src/services/session_manager.py:38-43` (in-memory `deque` scrollback), `src/screens/terminal_view.py:105-112` (bytes pushed into the terminal widget). Upstream command output is captured in memory via `io.StringIO` + a `_LineTee` stdlib redirect (`src/services/proot_service.py:53-105`). `logging.basicConfig` (`src/main.py:12-16`) writes to the console, not to a file — no `FileHandler` anywhere in `src/`.
- **No live asset reload.** The brand SVG is read once, synchronously, at render time from three candidate paths (`src/components/brand_hero.py:21-29`); license texts are read once (`src/screens/views.py:626-628`). No watcher, no cache invalidation.
- **No build-output watch in CI.** `.github/workflows/app.yml` is a linear step chain: `uv sync` → `ruff` → AST guard → version check → `pytest` (`:48-108`); wheel build → sign → `flet build apk` → size/prune → ELF alignment → upload (`:140-181`); the AAB mirror (`:194-303`). Nothing waits on a file appearing; every step is a foreground command that exits with a status code.
- **No filesystem watching in the wheel builder.** `build_flet_proot_wheel.py` is stdlib-only and fully synchronous: `urllib.request.urlopen` fetches (`:196-210`), `tarfile`/`zipfile` parse in memory (`:233-245`, `:431-433`), `Path.mkdir`/`Path.write_bytes` (`:387`, `:431`). It polls nothing and watches nothing. It is invoked exactly once per Android job as a foreground step (`app.yml:141`, `app.yml:195`).

So: **dormant and inert** in the product; **live but under-exercised** in the dev loop.

## Findings

### F1 · P2 · `flet run` without `-r` cannot hot-reload any module except `src/main.py` — the dev loop reloads nothing on a real edit

- **Where:** `.venv/Lib/site-packages/flet_cli/commands/run.py:369` (`my_observer.schedule(my_event_handler, script_dir, recursive=options.recursive)`), `:144-149` (`--recursive`, default `False`), `:350` (`watch_directory=options.directory or options.recursive`), `:553-555` (the reload predicate); `pyproject.toml:30-31` (`[tool.flet.app] path = "src"`); `run.py:253-258` (`script_dir` re-rooted by `tool.flet.app.path`).
- **What:** the observer watches `src/` non-recursively by default. Every real module of this app lives one level down (`src/core/state.py`, `src/services/proot_service.py`, `src/screens/terminal_view.py`). A non-recursive watch reports nothing for those files, and the reload predicate requires either `watch_directory` truthy or `event.src_path == self.script_path` — so the edit is dropped. Measured against this repo's own `src/` tree with the installed `WindowsApiObserver`:
  - `MODIFY src/core/state.py` → raw events `[]` → **no reload**
  - `CREATE src/core/_audit_tmp.py` → raw events `[]` → **no reload**
  - `MODIFY src/main.py` → raw events `[('modified', 'src\main.py') ×4]` → reload fires (the `src_path == script_path` branch)
  With `recursive=True` the same edit yields `[('modified', 'src\core\state.py')]` → reload fires.
- **Evidence:** live probe (Windows, `WindowsApiObserver`, resolved from `.venv/Lib/site-packages/watchdog/observers/__init__.py:73-78`):
  ```text
  MODIFY src/core/state.py      recursive=False raw=[]                       -> RELOAD=False
  CREATE src/core/_audit_tmp.py recursive=False raw=[]                       -> RELOAD=False
  MODIFY src/main.py            recursive=False raw=[('modified','src\main.py') x4] -> RELOAD=True
  MODIFY src/core/state.py      recursive=True  raw=[('modified','src\core\state.py')] -> RELOAD=True
  ```
  The predicate is `run.py:553-555`: `if (self.watch_directory or event.src_path == self.script_path) and event.event_type in ["modified","deleted","created","moved"]:` — a sub-directory event has a different `src_path`, and `watch_directory` is `options.directory or options.recursive` (`run.py:350`), false by default. The non-recursive behaviour is by design in watchdog itself: inotify "monitoring of directories is not recursive" (`watchdog/observers/inotify.py:39-43`, `inotify_c.py:405-412` adds sub-dir watches only when `recursive`), and Windows passes the flag straight to `ReadDirectoryChangesW` (`watchdog/observers/winapi.py:326-331`, `read_directory_changes.py:67`).
- **Fix / opportunity:** make the documented dev command recursive — `uv run flet run src -r` (`run.py:142-150`) — and record it in `docs/decisions.md:19` (D-005 step 2) and `docs/reference/dep-test-and-lint-stack.md:23-25`, which currently say "used only by `flet run` hot-reload" without noting the flag. Optionally add `--ignore-dirs .flet` (see F2). No code change needed; the fix is in the documented invocation.
- **Risk if ignored:** the owner's second-layer test loop (`docs/decisions.md:19`) silently does not reload. A developer edits `src/screens/terminal_view.py`, sees no rebuild, and either restarts manually (slow, defeats the purpose of the dev dependency) or — worse — believes the change did not work and edits something else. This is the only place watchdog has any effect on this project, and the effect is currently off.

### F2 · P2 · `flet run src` puts the app's own storage tree *inside* the watched directory — under `-r` the app can restart itself in a loop

- **Where:** `.venv/Lib/site-packages/flet_cli/commands/run.py:248` (`project_dir = Path(script_dir)`), `:287-291` (`flet_storage_dir = project_dir / ".flet" / "storage"`), `:497-499` (`FLET_APP_STORAGE_DATA/CACHE/TEMP` exported to the child), `:526` (`cwd=self.flet_app_data_dir`); `src/core/storage_paths.py:12-19` (`support_root()` reads `FLET_APP_STORAGE_DATA`), `:21-33` (`xdg_data_home` → `containers_dir`); `run.py:544-549` (the `ignore_dirs` `commonpath` filter).
- **What:** `flet run src` sets `project_dir = <repo>/src`, so flet-cli's storage lands at `src/.flet/storage/{data,cache,temp}` — **inside the watched tree**. `src/core/storage_paths.py:12-19` then resolves the app's container root to `src/.flet/storage/data/.local/share/proot-distro/containers`, so every container pull/backup/reset writes into the observed directory. Under `-r` (the fix for F1) those writes are observed and the reload predicate matches, so the app restarts itself in response to its own container I/O. The `ignore_dirs` escape hatch exists and works, but it is not used: the repo documents no `--ignore-dirs`, and `run.py:274-279` resolves ignore entries relative to `script_dir`, so the correct value is `.flet`.
- **Evidence:** directory resolution for this repo (replaying `run.py:241-258` + `flet_cli/utils/pyproject_toml.py:11-50`):
  ```text
  flet run 'src':      watched dir = <repo>\src      .flet storage project_dir = <repo>\src
  flet run 'src/main.py': watched dir = <repo>\src   .flet storage project_dir = <repo>\src
  flet run '.':        watched dir = <repo>\src      .flet storage project_dir = <repo>
  ```
  The machine state confirms both variants were used: `src/.flet/storage/{data,cache,temp}` and `<repo>/.flet/storage/{data,cache,temp}` both exist (`stat`: `src/.flet` 2026-10-20 16:58, `<repo>/.flet` 2026-10-19 12:01).
  Container-path resolution under `flet run src` (`FLET_APP_STORAGE_DATA=<repo>/src/.flet/storage/data`):
  ```text
  containers_dir = <repo>\src\.flet\storage\data\.local\share\proot-distro\containers
  => INSIDE the watched tree? True
  ```
  Live probe — writing a container file while watching `src/` recursively:
  ```text
  events: ('modified', 'src\.flet\storage\data\.local\share\proot-distro\containers\alpine'),
          ('modified', 'src\.flet\storage\data\.local\share\proot-distro\containers\alpine\rootfs.bin') …
  would flet-cli RELOAD the app? True
  ```
  And the ignore path works, so the fix is one flag — `run.py:544-549` compares `os.path.commonpath([directory])` with `os.path.commonpath([directory, child])`; for `directory = <repo>\src\.flet` and a storage child the two are equal → the event is skipped (verified: `ignored? True`).
- **Fix / opportunity:** document the dev command as `uv run flet run src -r --ignore-dirs .flet` (`run.py:192-198` defines `--ignore-dirs` as a comma-separated list of directory names relative to the script dir). Alternatively use the bare `uv run flet run` form, which keeps `.flet/` at the repo root, outside the watched `src/` tree — but that still needs `-r` for F1.
- **Risk if ignored:** with `-r` in place, a container operation (pull, backup, restore) writes into `src/.flet/…`, is observed, and restarts the app mid-operation. The restart kills the PTY session (`run.py:625-637` SIGTERM + `wait()` + `start_process()`), so the user's shell dies; the container operation may then be interrupted mid-write. Note the flet-cli debounce is only 0.5 s (`run.py:556`), so a burst of container writes can produce several restarts.

### F3 · P3 · The prior study's "unverified" API items are now verified; the study's blanket claim that watchdog is "inert in our context" understates its one real role

- **Where:** `docs/dependency-studies/watchdog.md:274-276` (the "Unverified" list) and `:210-234` (§5, the flet-cli quote sites); `docs/reference/dep-test-and-lint-stack.md:25` ("inert in our context").
- **What:** the study marked four items unverified. All four are now confirmed against the installed source, and the study's §5 line numbers are accurate. One phrasing needs tightening: watchdog is *not* inert in the dev loop — it is the mechanism behind `flet run` hot reload, which the repo lists as its second-layer test gate (`docs/decisions.md:19`). "Inert" is correct only for the shipped product and for CI.
- **Evidence:** `WindowsApiObserver` is at `.venv/Lib/site-packages/watchdog/observers/read_directory_changes.py:103` (study said "unverified"); `PollingObserverVFS.__init__` at `watchdog/observers/polling.py:126-140` takes `(stat, listdir, *, polling_interval: int = 1)`; the `EVENT_TYPE_*` constants exist verbatim at `watchdog/events.py:95-101` (`MOVED, DELETED, CREATED, MODIFIED, CLOSED, CLOSED_NO_WRITE, OPENED`); `watchmedo shell-command -w/--wait` → `dest="wait_for_process"` and `-W/--drop` → `dest="drop_during_process"` (`watchdog/watchmedo.py:567-580`), consumed by `ShellCommandTrick.__init__(..., wait_for_process=..., drop_during_process=...)` (`watchdog/tricks/__init__.py:79-96`).
- **Fix / opportunity:** update `docs/dependency-studies/watchdog.md:274-276` to drop the four unverified markers (the study is prior knowledge and should not be re-opened by the synthesis), and reword `docs/reference/dep-test-and-lint-stack.md:25` to "inert in the shipped product and in CI; live only as the `flet run` hot-reload mechanism".
- **Risk if ignored:** the synthesis may re-open four already-settled API questions, and a reader may conclude watchdog is entirely unused and propose removing it.

### F4 · P3 · `flet build` never resolves the dev group, so "watchdog is dev-only" is enforced by the build path, not by convention

- **Where:** `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2574` (dependency sources), `:2592-2596` (`-r <raw specifier>` per dependency), `:2606` (the `flet==<version>` fallback only when the list is empty), `:2578-2600` (`dev_packages` only re-points *declared* dependencies to local paths — it never adds one); `pyproject.toml:77-84` (the dev group); `uv.lock:595-604` (`[package.dev-dependencies]`).
- **What:** flet-cli's package step reads `project.dependencies` and `tool.flet.<platform>.dependencies` and nothing else. `[dependency-groups].dev` is never consulted, so `flet-cli` (and through it `watchdog`) is structurally unable to reach the APK. `tool.flet.cleanup.package_files = ["oauthlib/**"]` (`pyproject.toml:62-63`) is the only pruning the build performs, and it is unnecessary for watchdog: watchdog is never installed into the bundle in the first place.
- **Evidence:** `grep -rn "watchdog" .venv/Lib/site-packages/flet_cli/commands/build_base.py` → zero hits; the resolved shipped list is `['flet >=1.0.4', 'flet-ads >=1.0.4', 'flet-terminal >=0.4.0', 'httpx >=0.28.1', 'proot-distro >=5.10.0'] + ['flet-proot==5.1.107.98']` with watchdog absent.
- **Fix / opportunity:** none required. Do **not** add `watchdog/**` to `cleanup.package_files` — it would be a false positive, protecting a package that is never bundled.
- **Risk if ignored:** low. The only risk is a well-meaning "prune the dev deps" change that adds a no-op glob and starts failing a build for the wrong reason.

### F5 · P3 · `watchmedo` is installed and offers capabilities the repo does not use — but every one of them is host-side

- **Where:** `.venv/Lib/site-packages/watchdog/watchmedo.py`; `.venv/Lib/site-packages/watchdog-6.0.0.dist-info/entry_points.txt`; `watchdog/tricks/__init__.py:76-96`.
- **What:** the `watchmedo` console script is installed in `.venv/Scripts/` with subcommands `tricks-from, tricks, tricks-generate-yaml, generate-tricks-yaml, log, shell-command, auto-restart`. `shell-command` runs a shell command on matching events with `${watch_src_path}` / `${watch_dest_path}` / `${watch_event_type}` / `${watch_object}` interpolation, plus `-w` (wait for the process) and `-W` (drop events while the command runs) — exactly the primitives a "rebuild on change" loop needs.
- **Evidence:** `python -m watchdog.watchmedo --help` prints the subcommand list above; `shell-command --help` documents the interpolation variables and the `-w`/`-W` flags; the flags map to `wait_for_process` / `drop_during_process` (`watchmedo.py:567-580`, `tricks/__init__.py:79-96`).
- **Fix / opportunity:** do **not** adopt it. `flet run` already provides the one loop the repo needs (restart the app), and `watchmedo` would be a second, competing watcher. Keep the capability documented as available for host-side experiments only.
- **Risk if ignored:** none. Recording it here prevents a future agent from "discovering" `watchmedo` and wiring it into the build.

## Missed capabilities (dependency audits only)

- **`PatternMatchingEventHandler` / `RegexMatchingEventHandler`** · `watchdog/events.py:292-366` and `:368-449` (glob and regex matching with `ignore_directories`, `case_sensitive`) · integration point: nowhere in the app — but the *host* could use them if `flet run`'s single `--ignore-dirs` list were insufficient · value: low; flet-cli already ships `--ignore-dirs` (`run.py:192-198`) · cost: zero (no code), negative value (a second watcher). **Recommendation: do not use.**
- **`PollingObserver` / `PollingObserverVFS`** · `watchdog/observers/polling.py:117-124` and `:126-140` · integration point: nowhere · value: none on desktop (the native `WindowsApiObserver`/`InotifyObserver` is selected first, `watchdog/observers/__init__.py:54-88`) · cost: higher CPU, higher latency. **Recommendation: do not use.**
- **`EventEmitter.queue_events` / `BaseObserver.add_handler_for_watch`** · `watchdog/observers/api.py:145-156`, `:317-334` · integration point: nowhere · value: these enable *multi-watcher* designs (one observer, many handlers) that the app has no use for — the app has exactly one log stream and it is a PTY, not a file. **Recommendation: do not use.**
- **`watchdog.utils.echo` / `patterns`** · present under `watchdog/utils/` · integration point: nowhere · value: negligible. **Recommendation: do not use.**
- **`watchmedo shell-command`** · `watchdog/watchmedo.py:567-580`, `tricks/__init__.py:76-96` · integration point: a *host-side* "rebuild on change" loop, if one were ever wanted outside `flet run` · value: would duplicate `flet run`; the repo's rule forbids local `flet build` anyway (`docs/decisions.md:19`) · cost: a competing watcher in the same tree. **Recommendation: do not use.**
- **The one capability the repo *should* use** is not a watchdog API but a watchdog *flag*: `flet run -r` (`run.py:142-150`). See F1.

## Verified-good list

- **watchdog is genuinely dev-only.** It is required only by `flet_cli` (`flet_cli-1.0.4.dist-info/METADATA:14`), declared nowhere in `pyproject.toml` (runtime `:9-15`, dev `:77-84`), and pinned in `uv.lock` as `watchdog 6.0.0` with the single importer `flet-cli` (`uv.lock:232`, `:831-834`). It is absent from the runtime dependency closure and therefore from the APK/AAB.
- **Its single consumer is `flet run`.** `grep -rn "watchdog\|Observer\|FileSystemEvent" .venv/Lib/site-packages/flet_cli/ --include="*.py"` returns only `commands/run.py:17,18,368,406`. `flet/`, `flet_desktop/`, `flet_ads/`, `flet_terminal/`, `proot_distro/`, `build_base.py` and `flutter_base.py` have zero hits. Importing `flet` alone does not pull it in (`import flet` → `watchdog` not in `sys.modules`).
- **The installed version is 6.0.0**, matching the study: `watchdog/version.py` → `VERSION_MAJOR = 6`, `VERSION_MINOR = 0`, `VERSION_BUILD = 0`; `watchdog-6.0.0.dist-info/METADATA` → `Name: watchdog`, `Version: 6.0.0`, Apache-2.0.
- **`Observer` platform dispatch is native-first, polling-last** (`watchdog/observers/__init__.py:54-88`): Linux → `InotifyObserver` (`:56-60`), macOS → `FSEventsObserver` → `KqueueObserver` → polling (`:61-72`), Windows → `WindowsApiObserver` → polling (`:73-78`), BSD → `KqueueObserver` (`:79-82`), else `PollingObserver` (`:84-88`); `Observer = _get_observer_cls()` (`:90`). On this host it resolves to `watchdog.observers.read_directory_changes.WindowsApiObserver` (verified at runtime).
- **`schedule()` has the signature the study claims** — `watchdog/observers/api.py:270-276`: `(self, event_handler, path, *, recursive: bool = False, event_filter: list[type[FileSystemEvent]] | None = None) -> ObservedWatch` (verified at runtime via `inspect.signature`).
- **The event tree and `dispatch` are as documented** — `watchdog/events.py:105-202` (event classes and `event_type` assignments), `:205-292` (`FileSystemEventHandler.dispatch` calls `on_any_event` then `on_{event.event_type}`), `:292-449` (pattern/regex handlers), `:451-492` (`LoggingEventHandler`).
- **The flet-cli integration points cited by the study are accurate**: imports (`run.py:17-18`), `--recursive` (`:144-149`), `--ignore-dirs` (`:192-198`), observer creation/schedule/start with the inotify-limit fallback warning (`:368-383`), the run loop and `stop()`/`join()` (`:385-403`), `Handler(FileSystemEventHandler)` (`:406`), `on_any_event` with the `ignore_dirs` `commonpath` filter and the 0.5 s debounce (`:535-560`), `restart_program` SIGTERM+`wait()`+`start_process()` (`:625-637`).
- **The app has no filesystem-watching need of its own.** No `Observer`/`FileSystemEvent`/`watchdog` import in any of the 32 modules under `src/` (grep: zero hits). Log display is a live PTY fd read (`src/services/session_service.py:113-134`) plus an in-memory deque (`src/services/session_manager.py:38-43`); upstream output is captured in memory (`src/services/proot_service.py:53-105`); `logging.basicConfig` writes to console only (`src/main.py:12-16`, no `FileHandler` in `src/`); assets and licenses are read once (`src/components/brand_hero.py:21-29`, `src/screens/views.py:626-628`).
- **CI needs no watcher.** `app.yml` is a linear foreground-step chain in all three jobs (`quality` `:48-108`, `apk` `:140-181`, `aab` `:194-303`); every step's completion is a process exit status. No step waits on a filesystem event.
- **`build_flet_proot_wheel.py` needs no watcher.** Stdlib-only and fully synchronous: `urllib.request.urlopen` (`:196-210`), in-memory `tarfile`/`zipfile` (`:233-245`, `:431-433`), `Path.mkdir`/`write_bytes` (`:387`, `:431`); it polls nothing and is a foreground CI step (`app.yml:141`, `:195`).
- **The `ignore_dirs` mechanism is sound** and is the right escape hatch for F2: `run.py:274-279` resolves entries relative to `script_dir`; `run.py:544-549` skips any event whose `commonpath` equals the ignored directory's. Verified for `src/.flet` vs a `src/.flet/storage/data/x` child → ignored.
- **`flet build` structurally cannot ship watchdog**: `build_base.py:2566-2574` + `:2592-2596` read only `project.dependencies` and `tool.flet.<platform>.dependencies`; the dev group is never consulted; `cleanup.package_files` is not needed for watchdog.

## Unverified

- **Linux/macOS hot-reload parity.** All live probes in this audit ran on Windows with `WindowsApiObserver`. The non-recursive sub-directory gap (F1) is *documented* for inotify (`watchdog/observers/inotify.py:39-43`, `inotify_c.py:405-412` adds sub-dir watches only when `recursive`) and for kqueue/fsevents by analogy, but I did not run a Linux or macOS observer here. That the gap is **at least as bad** on Linux is highly likely (the inotify emitter explicitly does not add sub-directory watches in non-recursive mode), but the exact event set is **UNVERIFIED**.
- **`watchmedo tricks*` subcommand flags** remain unverified beyond the top-level `--help` (the `tricks`, `tricks-generate-yaml`, `generate-tricks-yaml` flag sets were not dumped). Not material: the recommendation is not to use `watchmedo`.
- **Whether a container operation actually writes into `src/.flet/…` during a live `flet run src` on this host.** The path resolution and the watch behavior are both proven separately (F2), but proot-distro is unavailable on desktop Windows (`src/core/proot_probe.py:70-73`: no `nativeLibraryDir` → `ProotUnavailable`), so I could not observe a real container pull writing into the watched tree. The write path is inferred from `src/core/storage_paths.py:21-33` + `src/core/proot_probe.py:76-82`, both of which are proven by inspection. The *consequence* (reload) is proven by the live probe; the *trigger* is inferred. **UNVERIFIED** as an end-to-end run.
- **`flet run` on this host was not executed end-to-end** (no local `flet run` was run for this audit). The `src/.flet/` and `<repo>/.flet/` directory timestamps prove the CLI ran at some point in both modes, but the exact flags used then are **UNVERIFIED**; the resolution logic replayed in F1/F2 is faithful to `run.py:241-258` + `flet_cli/utils/pyproject_toml.py:11-50` and was executed directly, but not against a live `flet run` process.
- **CI was not executed.** No GitHub Actions run was performed for this audit; the CI conclusions are read from `app.yml` plus the installed flet-cli source, not from a build log.
- **Working-tree deletions.** This workspace has many files deleted relative to `HEAD` (`check_elf_alignment.py`, `generate_third_party_sources.py`, `LICENSES/*`, `docs/roadmap.md`, `docs/testing-findings.md`, `docs/release-runbook.md`, `docs/compliance/*`). Where the audit needed those files I read them from `HEAD` via `git show` (notably `docs/testing-findings.md:6,35,40-41` for the documented `flet run` invocation). The deletions themselves are not assessed here.
