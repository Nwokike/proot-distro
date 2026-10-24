# src/services/proot_service.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/services/proot_service.py` · `src/app_controller.py` · `src/services/session_service.py` · `src/services/session_manager.py` · `src/core/storage_paths.py` · `src/core/proot_probe.py` · `src/core/posixdb.py` · `tests/test_proot_surfaces.py` · installed `proot-distro==5.10.0` at `.venv/lib/python3.14/site-packages/proot_distro/` · **Date:** 2026-10-24

---

## What it does / how the app uses it

`src/services/proot_service.py` is the **sole module allowed to import `proot_distro`** (module docstring, `:1`). It is a lazy in-process facade: `bootstrap()` (`:32-41`) installs `pwd`/`grp` shims via `posixdb.ensure()` and applies the env contract from `storage_paths.env_contract()` *before* any `proot_distro` import; the import itself is deferred to `importlib.import_module` inside `available()` (`:46-47`), `_run_command` (`:83`), and `get_proot_cmd` (`:322`). `_run_command` (`:73-102`) invokes one upstream `command_*` handler on a `SimpleNamespace`, captures stdout/stderr via `contextlib.redirect_*`, and translates `SystemExit`/exceptions into an `Outcome`. Public ops: `list_containers`, `install`, `remove_container`, `reset_container`, `remove_cached_image`, `search_images`, `cached_images`, `storage_bytes`, `busy_locks`, `get_proot_cmd`, `rename_container`, `backup_container`, `restore_container`, `copy_path`, `kill_session`, `active_sessions`, plus `friendly_job_error`/`is_pull_limit` for UI error translation. `get_proot_cmd` (`:312-345`) runs `cli.main()` in-process with `sys.argv` = `["proot-distro", "login", <container>, "--get-proot-cmd"]` to obtain the upstream session argv line, consumed by `session_service.session_argv` (`session_service.py:41`).

Upstream API contract verified against the installed `proot-distro 5.10.0` source:
- `cli.main()` (`.venv/.../cli.py:246`) installs a `SIGQUIT → KeyboardInterrupt` handler (`.venv/.../cli.py:258`), calls `_ensure_proot_available` (`.venv/.../cli.py:265`), parses args, and dispatches `handler(args)` (`.venv/.../cli.py:340-344`) with **no try/except around the handler**. Error paths call `crit_error` + `sys.exit(1)` (`.venv/.../cli.py:292,318,326,343`); help/usage exits `sys.exit(0)` (`.venv/.../cli.py:271,275,301`).
- `command_install` reads `image_ref`, `custom_container_name`, `override_arch`, `allow_insecure` (`.venv/.../commands/install.py:140-188`).
- `command_remove` reads `target`/`image`/`override_arch`/`verbose` (`.venv/.../commands/remove.py:108-130`); `_remove_image` reads `target`/`verbose`/`override_arch` (`.venv/.../commands/remove.py:174-179`).
- `command_reset` reads `container_name` (`.venv/.../commands/reset.py:46`); calls `command_install` internally (`.venv/.../commands/reset.py:98`).
- `command_rename` reads `orig_name`/`new_name` (`.venv/.../commands/rename.py:52-53`).
- `command_backup` reads `container_name`/`output`/`compression`/`verbose` (`.venv/.../commands/backup.py:453-456`).
- `command_restore` reads `archive`/`verbose` (`.venv/.../commands/restore.py:458-459`).
- `command_copy` reads `source`/`destination`/`verbose`/`move`/`recursive` (`.venv/.../commands/copy.py:65-69`).
- `command_kill` reads `target`/`all`/`signal` (`.venv/.../commands/kill.py:90-94`).
- `paths.installed_container_names()` (`.venv/.../paths.py:257`), `paths.container_image_origin()` (`.venv/.../paths.py:380`).
- `helpers/docker/cache.iter_cached_images()` returns records with keys `path`, `name`, `key`, `image_ref`, `repo`, `arch`, `image_id`, `layers`, `size`, `missing`, `created`, `cached_at` (`.venv/.../helpers/docker/cache.py:698-714`).
- `helpers/docker/search.search_images(query, limit)` returns `(results, total)` (`.venv/.../helpers/docker/search.py:191,254`).
- `locking.busy_locks()` → `list[(path, hint)]` (`.venv/.../locking.py:346-348`).
- `session.active_sessions()` → records with `pid`/`container`/`kind`/`command`/`user`/`start_time` (`.venv/.../session.py:210-253`, record fields at `:149-154`).
- `constants.py` import-time reads `TERMUX_APP__PACKAGE_NAME` (`:47`), `TERMUX__HOME` (`:48`), `TERMUX__PREFIX` (`:51`), `XDG_DATA_HOME` (`:79`), `XDG_CACHE_HOME` (`:82`); `message.py` honors `PD_FORCE_NO_COLORS` (`:108`); `progress.progress_active()` = stderr-is-tty and not quiet (`.venv/.../progress.py:80-82`).
- `helpers/rootfs.py` imports `grp`/`pwd` (`.venv/.../helpers/rootfs.py:42-44`) — POSIX-only, absent on Windows per PEP 738; `posixdb.ensure()` shims them into `sys.modules` (`.venv/.../src/core/posixdb.py:96-107`... actually `src/core/posixdb.py:96-107`).

App-side wiring:
- `app_controller.AppController.open_session` → `session_manager.open` (in `asyncio.to_thread`, `app_controller.py:406`) → `session_service.session_argv` → `proot_service.get_proot_cmd` (`session_service.py:41`).
- `app_controller.install_distro` → `self.proot.install(image, name, on_line=_on_line)` in `asyncio.to_thread` (`app_controller.py:179-184`); `_on_line` marshals to the loop via `loop.call_soon_threadsafe` (`app_controller.py:177`).
- `app_controller.remove_container`/`reset_container`/`backup_container`/`restore_container`/`copy_path`/`kill_session` all call the proot_service op in `asyncio.to_thread` (`app_controller.py:205,212,351,366,378,396`).
- `tests/test_proot_surfaces.py:34-42` asserts the sole-importer rule; `:57-73` assert namespace fields match `parser.build_parser()`.

---

## Findings

### F1 · P1 · `get_proot_cmd` calls `cli.main()` from a worker thread — `cli.main()` installs a `SIGQUIT` signal handler (main-thread-only) → `ValueError` uncaught

- **Where:** `src/services/proot_service.py:312-345` (`get_proot_cmd` calls `cli.main()` at `:334` after mutating `sys.argv`/stdout/stderr at `:324-332`); `.venv/lib/python3.14/site-packages/proot_distro/cli.py:258` (`signal.signal(signal.SIGQUIT, _sigquit_to_keyboard_interrupt)` inside `cli.main()`, `:246`). Called from `src/services/session_service.py:41` (`line = proot_service.get_proot_cmd(container)`), which is called from `src/services/session_manager.py:67` (`env, argv = session_service.session_argv(container)`), which is called from `src/app_controller.py:406` via `await asyncio.to_thread(self.session_manager.open, container)` — i.e. on a **worker thread**.
- **What:** Python's `signal.signal()` can only be called from the main thread; from any other thread it raises `ValueError: signal only works in main thread`. `get_proot_cmd` only catches `SystemExit` (`:335-340`), so a `ValueError` propagates uncaught through `session_argv` → `session_manager.open` → `app_controller.open_session` (caught there by `except Exception` at `app_controller.py:407`, so the app degrades to `state.session_error` rather than crashing, but `get_proot_cmd` fails to return the session argv and opening a session fails). This is the "cli.main signal bug (get_proot_cmd in worker thread)" named in the brief.
- **Evidence:** `cli.py:246` (`def main()`) → `:258` `signal.signal(signal.SIGQUIT, ...)`; `signal.signal` documentation: "Only the main thread is allowed to set signal handlers" (stdlib). `get_proot_cmd` runs under `asyncio.to_thread` transitively (app_controller.py:406 → session_manager.py:67 → session_service.py:41 → proot_service.py:334). No `try/except ValueError` around `cli.main()` in proot_service.py:330-344.
- **Fix / opportunity:** Run `cli.main()` on the main thread (e.g. via `loop.run_in_executor` is wrong — must be *main* thread; better: restructure so `get_proot_cmd` is invoked on the main thread, or capture `--get-proot-cmd` output without calling `cli.main()`/`signal.signal`, e.g. call `login.__init__`'s argv assembly directly). At minimum wrap `cli.main()` in `try/except (SystemExit, Exception)` so `ValueError` becomes a failed `Outcome`-style result instead of propagating. Do **not** mutate global `sys.argv`/`sys.stdout`/`sys.stderr` from a worker thread (see F2).
- **Risk if ignored:** Opening any guest session fails on Android/dev builds where `open_session` runs off the main thread — the login/console feature is non-functional.

### F2 · P2 · `get_proot_cmd` mutates global `sys.argv`/`sys.stdout`/`sys.stderr` — not thread-safe; concurrent session opens clobber each other

- **Where:** `src/services/proot_service.py:324-333` (`argv_backup = sys.argv[:]`; `stdout_backup = sys.stdout`; `stderr_backup = sys.stderr`; `sys.argv = [...]`; `sys.stdout = buffer`; `sys.stderr = errors`); restored in `finally` at `:341-344`. Called concurrently from `session_service.session_argv` (`session_service.py:41`) → multiple `session_manager.open` calls via `asyncio.to_thread` (`app_controller.py:406`).
- **What:** `sys.argv`, `sys.stdout`, and `sys.stderr` are process-global. Two concurrent `get_proot_cmd` calls (e.g. opening two sessions back-to-back) interleave: call A saves backups, call B overwrites `sys.argv`, call A's `finally` restores call B's backups (or vice-versa), leaving one call with the wrong argv and/or a closed/wrong stream. `cli.main()` parses `sys.argv`, so the wrong command/container can be dispatched, or output lands on the wrong stream. No lock serializes these calls.
- **Evidence:** proot_service.py:324-344 reads/writes globals with no `threading.Lock`. `session_service.session_argv` (`session_service.py:39-41`) has no locking either. `app_controller.open_session` (`app_controller.py:403-410`) invokes `session_manager.open` in `asyncio.to_thread`, so concurrent opens are real (user taps two containers quickly).
- **Fix / opportunity:** Serialize `get_proot_cmd` with a module-level `threading.Lock`, and/or avoid mutating globals by invoking the login `--get-proot-cmd` path without `cli.main()` (call `proot_distro.commands.login` internals directly with a namespace). Prefer constructor injection / no global state (BRIEF rule 4).
- **Risk if ignored:** Wrong session argv returned, or output written to the wrong buffer; sessions opened with the wrong command/env; intermittent failures under concurrency.

### F3 · P2 · `_run_command` does not catch `KeyboardInterrupt` — `cli.main()` installs `SIGQUIT → KeyboardInterrupt`, so a `SIGQUIT` during an install crashes the worker thread uncaught

- **Where:** `src/services/proot_service.py:88-102` (`_run_command` `try/except SystemExit` at `:96` and `except Exception` at `:101`); `.venv/lib/python3.14/site-packages/proot_distro/cli.py:252-258` (`cli.main` installs `SIGQUIT → KeyboardInterrupt` handler).
- **What:** `KeyboardInterrupt` is a `BaseException`, **not** an `Exception`, so neither `except SystemExit` nor `except Exception` catches it. If `SIGQUIT` (Ctrl-\) arrives during an in-process `command_install`/`command_backup`/etc., the handler converts it to `KeyboardInterrupt`, which propagates out of `_run_command` and crashes the `asyncio.to_thread` worker. The app's install/backup flows (`app_controller.py:184`, `:205`, `:351`, etc.) do not catch it at the service boundary.
- **Evidence:** proot_service.py:89 `with contextlib.redirect_stderr(buf), ...: fn(namespace)` — `fn` is the upstream handler; cli.main's SIGQUIT handler (`.venv/.../cli.py:258`) raises `KeyboardInterrupt`; proot_service.py:101 `except Exception` does not match `KeyboardInterrupt`. No `except (KeyboardInterrupt, SystemExit)` or `except BaseException`.
- **Fix / opportunity:** Change `except Exception` to `except (Exception, KeyboardInterrupt)` (or `except BaseException` with careful handling) in `_run_command`, mapping `KeyboardInterrupt` to `Outcome(False, "interrupted", buf.getvalue())`. This matches upstream's own intent (cli.py:252-256 docstring: route SIGQUIT through KeyboardInterrupt so `except KeyboardInterrupt` blocks handle it).
- **Risk if ignored:** `SIGQUIT` mid-install/backup crashes the worker thread; partial state may be left; user sees an abrupt failure rather than a clean "interrupted" report.

### F4 · P2 · `_run_command` with `on_line` loses live stderr lines from `outcome.output` — error fallback reads a truncated/wrong buffer

- **Where:** `src/services/proot_service.py:88-95` (outer `redirect_stderr(buf)` then inner `redirect_stderr(_LineTee(on_line))` at `:91`; `_LineTee.write` at `:62-67` calls `on_line` but **never writes to `buf`**); `:95` `return Outcome(True, "completed", buf.getvalue())`.
- **What:** When `on_line` is set (install progress), the inner `redirect_stderr(_LineTee(on_line))` shadows the outer `redirect_stderr(buf)`. `_LineTee.write` forwards each line to `on_line` (the UI progress sink) and returns `len(data)`, but discards the text — it never writes to `buf`. So `buf.getvalue()` (`outcome.output`) contains **stdout only**, not the live-forwarded stderr stage lines. `friendly_job_error` (`:415-423`) falls back to `outcome.output.strip().splitlines()[-3:]` when `detail` is empty — that tail may be empty or incomplete because the real diagnostic lines went to `on_line`, not `buf`.
- **Evidence:** proot_service.py:53-70 `_LineTee.write` — no write to any buffer; `:88-94` nested redirects; `:420-421` fallback reads `outcome.output`. `install_distro` in `app_controller.py:188-193` calls `friendly_job_error(outcome)` when `not outcome.ok`, relying on `outcome.output` for the tail.
- **Fix / opportunity:** Make `_LineTee` also forward to an underlying buffer (tee behavior), or capture `on_line` lines into a list stored on the namespace/`_run_command` and append them to `buf.getvalue()` in the returned `Outcome`. Minimal: give `_LineTee` a reference to `buf` and `buf.write(line + "\n")` after `on_line(line)`.
- **Risk if ignored:** `friendly_job_error` reports "unknown error" or a stale tail when the real diagnostic was streamed live; install failures surface without the actual error message.

### F5 · P3 · `available()` can return `True` on a desktop/Windows interpreter even though proot cannot execute — the "no grp shim" claim in the `ProotUnavailable` docstring is stale

- **Where:** `src/services/proot_service.py:21-23` (`ProotUnavailable` docstring: "proot-distro cannot run on this interpreter (desktop Windows, no grp shim)"); `:44-50` (`available()` only tests `importlib.import_module("proot_distro")`); `.venv/lib/python3.14/site-packages/proot_distro/__init__.py:1-25` (package doc only, no exports; does **not** import `helpers/rootfs`); `.venv/lib/python3.14/site-packages/proot_distro/helpers/rootfs.py:42-44` (`import grp`, `import pwd` — imported lazily, not at package `__init__`).
- **What:** `import proot_distro` succeeds on Windows because `__init__.py` does not import `helpers/rootfs` (the `grp`/`pwd` module). So `available()` returns `True` even on an interpreter where proot cannot actually run. The `ProotUnavailable` docstring's rationale ("no grp shim on Windows") is only true once `helpers/rootfs` is imported, which `available()` never triggers. `posixdb.ensure()` (shims `pwd`/`grp` into `sys.modules`, `src/core/posixdb.py:96-107`) runs in `bootstrap()` before import, so on Windows `import grp` inside proot_distro would get the shim — but `available()` doesn't exercise that path.
- **Evidence:** proot_service.py:21-23 docstring; `:46-47` the only import probe; `__init__.py` has no `import rootfs`; `helpers/rootfs.py:42-44` the real `grp`/`pwd` import site.
- **Fix / opportunity:** Either update the `ProotUnavailable` docstring to reflect that `available()` is an import probe only (not an exec probe), or make `available()` attempt a lightweight proot execution (e.g. `get_proot_bin` validation) — but that risks side effects. At minimum label the docstring accurately: "import succeeds (grp shimmed by posixdb) but proot may not be executable." UNVERIFIED whether any caller treats `available() == True` as "proot executable."
- **Risk if ignored:** Code paths that gate on `available()` may proceed on an interpreter where proot-distro cannot actually execute, leading to later `SystemExit`/errors at command time rather than a clean up-front "unavailable" report.

---

## Verified-good list (no defect found — included so synthesis does not re-open)

| Item | Evidence |
|------|----------|
| Sole-importer rule | `src/services/proot_service.py:1` docstring; `tests/test_proot_surfaces.py:34-42` asserts only `src/services/proot_service.py` imports `proot_distro`; `src/app_controller.py` and `src/screens/*` do not import it (`tests/test_proot_surfaces.py:45-51`). |
| Env contract ordering | `bootstrap()` (`:32-41`): `posixdb.ensure()` (shims `pwd`/`grp` into `sys.modules`, `src/core/posixdb.py:96-107`) → `os.environ.update(storage_paths.env_contract())` → lazy `proot_distro` import in `available()`/`_run_command`/`get_proot_cmd`. `env_contract()` (`src/core/storage_paths.py:36-53`) sets all import-time vars upstream reads (`constants.py:47-86`): `TERMUX_APP__PACKAGE_NAME`, `TERMUX__PREFIX`, `TERMUX__HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `PROOT_TMP_DIR`, `PD_FORCE_NO_COLORS`. `proot_probe.bootstrap_env` additionally sets `PD_PROOT_BIN`/`PROOT_LOADER` (`src/core/proot_probe.py:105-106`) before first import. Ordering is correct: env is set before `proot_distro.constants` is imported. |
| Namespace field parity | Verified against installed parser/handlers: `_ns_install` (`:108-114` vs `commands/install.py:140-188`); `_ns_remove` (`:117-125` vs `commands/remove.py:108-130`); `_ns_remove_image` (`:242-251` vs `commands/remove.py:174-179`); `_ns_reset` (`:128-134` vs `commands/reset.py:46`); `_ns_rename` (`:137-138` vs `commands/rename.py:52-53`); `_ns_backup` (`:141-148` vs `commands/backup.py:453-456`); `_ns_restore` (`:151-152` vs `commands/restore.py:458-459`); `_ns_copy` (`:155-165` vs `commands/copy.py:65-69`); `_ns_kill` (`:168-169` vs `commands/kill.py:90-94`). All fields upstream reads are present on the namespace (superset is fine — upstream uses `getattr(args, x, default)` for optional fields). `tests/test_proot_surfaces.py:57-73` spot-checks install/remove/reset. |
| `SystemExit` translation in `_run_command` | `:96-102`: code 0 → `Outcome(True, "no-op")`; non-zero → `Outcome(False, ...)`. Upstream handlers exit via `sys.exit(1)` on error (`.venv/.../cli.py:292,318,326,343`) and `sys.exit(0)` for help (`.venv/.../cli.py:271,275,301`). |
| `is_pull_limit` | `:441-444` matches markers against `detail + output`; `tests/test_proot_surfaces.py:151-156` passes. |
| `friendly_job_error` | `:415-423` safe against empty output/detail (guarded by `.strip()` and `if tail`). |
| `search_images` returns plain dicts | `:263-269` filters `isinstance(r, dict)`; upstream `search_images` returns `(results, total)` (`.venv/.../helpers/docker/search.py:191,254`). |
| `cached_images` record keys | `:278-291` reads `image.get("image_ref") or image.get("id")`, `image.get("arch")`, `image.get("full_path") or image.get("path")`; upstream `iter_cached_images` records carry `image_ref`, `arch`, `path` (`.venv/.../helpers/docker/cache.py:698-707`). |
| `busy_locks` | `:301-309` wraps `locking.busy_locks()` (`.venv/.../locking.py:346`) in try/except → `[]` on failure. |
| `active_sessions` record shape | `:393-412` maps `pid`/`container`/`kind`/`user`/`command`/`start_time`; upstream records have exactly those fields (`.venv/.../session.py:149-154`). |

---

## Unverified

- Whether any caller gates executable-runtime capability on `available()` returning `True` on Windows/desktop (F5 impact). UNVERIFIED — no app-side caller of `available()` was found in the files read, but the full codebase was not searched.
- Whether two sessions are ever opened concurrently in practice (F2 likelihood). UNVERIFIED — `app_controller.open_session` is invoked from the UI; user tap timing is not deterministic.
- Whether `SIGQUIT` is ever delivered to the worker thread in practice (F3 likelihood). UNVERIFIED — Android/desktop signal delivery to `asyncio.to_thread` workers is not exercised by the tests read.
- Whether `outcome.output` fallback in `friendly_job_error` is actually reached with empty output in a real failure (F4 impact). UNVERIFIED — depends on which failure paths write to stderr vs stdout.
- The exact line numbers of per-`getattr` reads inside `_login_with_rootfs` (the `--get-proot-cmd` path) — cited as a region in the dependency study (`login/__init__.py:460-670`). The `sys.exit(0)` after printing is at `.venv/.../commands/login/__init__.py:551-552`; confirmed `get_proot_cmd` receives exit code 0 → `Outcome(True)` at proot_service.py:98.

---

## Missed capabilities

Not applicable — this is a service-facade audit, not a dependency audit. The `docs/dependency-studies/proot-distro-api.md` study already maps unused upstream APIs (`command_backup`/`restore`, `command_sync`, `command_kill`, `command_search`, `command_rename`, `command_reset`, session registry, `arch.*`, `guestfile.*`, etc.) to milestones; `proot_service.py` already wires `backup`/`restore`/`copy`/`kill`/`rename`/`reset`/`search_images`/`cached_images`/`busy_locks`/`active_sessions`.

---

No code was modified. This report is the single deliverable at `docs/swarm/file-audits/src__services__proot_service.py.md`.
