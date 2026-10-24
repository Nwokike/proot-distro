# src/core/storage_paths.py — audit

**Verdict:** MIXED
**Confidence:** medium
**Scope:** `src/core/storage_paths.py` (53 lines) · `src/main.py` · `src/core/shared_services.py` · `src/core/proot_probe.py` (136 lines) · `src/services/proot_service.py` (`bootstrap` :32-42, `available` :44-50) · `src/app_controller.py` (`check_probe` :276-286, `init` :47-49) · `docs/decisions.md` (D-001, D-015, O-8) · `docs/dependency-studies/proot-distro-api.md` §constants · `docs/reference/dep-proot-distro.md` · `.venv/lib/python3.14/site-packages/proot_distro/constants.py:47-99` · `.venv/lib/python3.14/site-packages/flet/controls/services/storage_paths.py:27,72,188` · tests `test_proot_surfaces.py:85-117`, `test_core.py:79-98` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/storage_paths.py` is the single owner of where proot-distro state lives inside the app. `support_root()` resolves the Flet app storage dir (`FLET_APP_STORAGE_DATA`, then `FLET_APP_STORAGE_TEMP`, then a `cwd/.proot-local/data` dev fallback). `xdg_data_home()`/`xdg_cache_home()` nest `.local/share` and `.local/cache` under it; `containers_dir()` is `.../proot-distro/containers`. `env_contract()` returns the import-time env dict (`TERMUX_APP__PACKAGE_NAME`, `TERMUX__PREFIX`, `TERMUX__HOME`, `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `PROOT_TMP_DIR`, `PD_FORCE_NO_COLORS`) that `proot_service.bootstrap()` applies via `os.environ.update(...)` before the first `proot_distro` import. `proot_probe.bootstrap_env()` runs earlier in `AppController.init` and sets the payload vars (`PD_PROOT_BIN`, `PROOT_LOADER`, `LD_LIBRARY_PATH`) directly, so the two modules split the contract: storage_paths owns the Termux/XDG half, proot_probe owns the payload half.

---

## Findings

### F1 · P1 · `support_root()` depends on env vars whose presence before `main()` is unverified, with a cwd-relative silent fallback
- **Where:** `src/core/storage_paths.py:11-18` (`os.environ.get("FLET_APP_STORAGE_DATA") or os.environ.get("FLET_APP_STORAGE_TEMP")`; fallback `Path.cwd() / ".proot-local" / "data"`); `.venv/.../flet/controls/services/storage_paths.py:72,188` (documents these env vars as set "in a running Flet app").
- **What:** The native Flet host is what sets `FLET_APP_STORAGE_DATA`/`_TEMP`. Nothing in the Python tree (`.venv` or `src/`) proves they are populated before `ft.run(main)` invokes `main(page)`. If they are absent (desktop `flet run`, a future Flet build, or a host that sets them later), `support_root()` silently lands all containers/state under the launch cwd's `.proot-local/data`, which is not persisted across runs and may be read-only. The env-var names themselves are correct; only their timing is unproven.
- **Evidence:** `grep -rln "FLET_APP_STORAGE_DATA" .venv/` returns no matches (the vars are set by the native host, not the Python package); `storage_paths.py:13` reads them with no assertion or fallback-to-error.
- **Fix / opportunity:** Add a startup assertion in `AppController.init`/`check_probe` that `FLET_APP_STORAGE_DATA` is present (or surface a `probe` problem when absent), and document the dev fallback as dev-only. Do not silently persist to cwd on a device build.
- **Risk if ignored:** On a packaged build where the host env is missing/renamed, the app appears to work but stores containers in a throwaway cwd and loses them on restart.
- **Label:** timing claim is UNVERIFIED (native host).

### F2 · P2 · Split env contract creates an import-order race between `proot_service` and `proot_probe`
- **Where:** `src/services/proot_service.py:32-42` (`bootstrap()` calls `posixdb.ensure()` then `os.environ.update(storage_paths.env_contract())`, then sets `_BOOTSTRAPPED=True`); `src/core/proot_probe.py:65-136` (`bootstrap_env()` sets `PD_PROOT_BIN`/`PROOT_LOADER`/`LD_LIBRARY_PATH`/`PROOT_TMP_DIR` directly and is the only setter of the payload vars); `src/app_controller.py:47-49` (`init` awaits `check_probe()` first).
- **What:** `proot_service.bootstrap()` applies the Termux/XDG half but not `PD_PROOT_BIN`/`PROOT_LOADER`/`LD_LIBRARY_PATH`. Those come only from `proot_probe.bootstrap_env()`. The happy path is safe because `init` calls `check_probe()` first. But `proot_service.available()` (and every public method) calls `bootstrap()` itself and is callable from any thread/task before `check_probe` completes (or in tests). If that happens, `proot_distro` gets imported with `PD_PROOT_BIN` unset, so `arch.get_proot_bin()` (`arch.py:221-253`) falls back to `shutil.which("proot")`, which is absent on Android → startup failure instead of a probe problem. `_BOOTSTRAPPED` then latches `True`, so a later `bootstrap_env()` cannot repair the missing payload vars through `bootstrap()` (it only adds keys, but `bootstrap()` is a no-op once latched).
- **Evidence:** `proot_service.py:18-19,32-42` (latched flag); `proot_probe.py:103-107` (payload setters); `arch.py:221-253` (fallback to `shutil.which`).
- **Fix / opportunity:** Either move the payload setters into `storage_paths.env_contract()` (so one function is the whole contract, as D-001 implies), or make `proot_service.bootstrap()` call/await `proot_probe.bootstrap_env()` first, or add a `storage_paths.payload_env(native, runtime)` helper that `bootstrap()` consumes. Also reset/repair `_BOOTSTRAPPED` when payload vars are missing.
- **Risk if ignored:** Any code path that touches proot before the probe finishes (or a test ordering) imports proot_distro without its binary path and fails on device.

### F3 · P2 · `env_contract()` claims to mirror upstream "exactly" but omits two import-time inputs and the package-name guard is only partial
- **Where:** `src/core/storage_paths.py:36-43` (docstring "Mirrors upstream `constants.py:47-99` (import-time reads) exactly"); `.venv/.../proot_distro/constants.py:47-68` (`TERMUX_APP__PACKAGE`, `TERMUX_HOME`, `TERMUX_PREFIX`, `_detect_termux` checks `TERMUX_APP__APP_VERSION_NAME`/`TERMUX_VERSION` and prefix accessibility).
- **What:** Upstream computes `IS_TERMUX` from three checks, two of which depend on `TERMUX_APP__APP_VERSION_NAME`/`TERMUX_VERSION` and prefix accessibility. `env_contract()` sets neither `TERMUX_VERSION` nor `TERMUX_APP__APP_VERSION_NAME`. That is deliberate (keeping `IS_TERMUX=False` so the XDG branch is taken — see O-8), but the docstring's "exactly" is inaccurate and could mislead a future edit into adding them and accidentally flipping `IS_TERMUX=True`, which would make upstream ignore `XDG_DATA_HOME`/`XDG_CACHE_HOME` entirely (`constants.py:78-88` takes the Termux branch and uses `TERMUX_PREFIX/var/lib/...`). The omission is load-bearing and undocumented.
- **Evidence:** `constants.py:55-68,78-88`; `storage_paths.py:39-43`.
- **Fix / opportunity:** Rewrite the docstring to state explicitly that `TERMUX_VERSION`/`TERMUX_APP__APP_VERSION_NAME` are intentionally unset to force generic (XDG) mode, and that setting them would switch storage to `TERMUX_PREFIX` and bypass `XDG_*`.
- **Risk if ignored:** A well-meaning "completeness" edit sets the masquerade vars and silently relocates all state under `/data/data/.../files/usr/var/lib/proot-distro`, breaking the XDG relocation.

### F4 · P3 · `env_contract()` does not create the directories it advertises; only `proot_probe` creates `runtime`/`containers_dir`
- **Where:** `src/core/storage_paths.py:45-53` (returns paths only); `src/core/proot_probe.py:76-77,127-129` (`runtime.mkdir`, `croot.mkdir`).
- **What:** `XDG_DATA_HOME`, `XDG_CACHE_HOME`, `PROOT_TMP_DIR` are returned as strings but no `mkdir` is performed by storage_paths. `PROOT_TMP_DIR` (`support_root()/tmp`) is never created anywhere in `src/` (confirmed by `grep -rn "mkdir" src/` — only `runtime` and `containers_dir`). `proot_probe._f2fs_probe` falls back to `runtime` when tmp is absent, so its verdict is measured on the wrong filesystem, and proot itself may expect the dir to exist.
- **Evidence:** `storage_paths.py:51`; `proot_probe.py:107-113`; `grep -rn "mkdir" src/`.
- **Fix / opportunity:** Create `support_root()/tmp` (guarded) in `proot_probe.bootstrap_env` before setting `PROOT_TMP_DIR`, and have storage_paths document which paths are guaranteed to exist.
- **Risk if ignored:** f2fs verdict on the wrong fs; possible proot startup failure. (Already flagged as F3 in the proot_probe audit.)

### F5 · P3 · Dev fallback uses `Path.cwd()`, so the storage root moves with the launch directory
- **Where:** `src/core/storage_paths.py:16-18`.
- **What:** When neither Flet env var is set (desktop dev), `support_root()` returns `Path.cwd() / ".proot-local" / "data"`. `Path.cwd()` depends on where `flet run`/pytest is invoked, so storage is not stable across invocations from different directories, and a read-only cwd makes every path fail. Dev-only, but it makes the service "not testable on a laptop" in practice from arbitrary directories.
- **Evidence:** line 18.
- **Fix / opportunity:** Anchor the fallback to a stable user location (e.g. `Path.home() / ".proot-local" / "data"`) or to the module file's parent, and document it. UNVERIFIED whether tests rely on cwd.
- **Risk if ignored:** Flaky dev/test storage; confusing "where did my container go" on laptop.

### F6 · P3 · `TERMUX__PREFIX`/`TERMUX__HOME` are hardcoded to the package's `/data/data/...` paths with no validation
- **Where:** `src/core/storage_paths.py:47-48`.
- **What:** The paths assume the app's data directory is `/data/data/ng.kiri.prootdistro/files/...`. On devices with work profiles, multiple users, or an unusual install location these may not match the actual app-private dir. There is no cross-check against `ANDROID_NATIVE_LIBRARY_DIR` or the Flet storage env. UNVERIFIED on device.
- **Evidence:** lines 47-48; `proot_probe._native_library_dir()` reads `ANDROID_NATIVE_LIBRARY_DIR` separately.
- **Fix / opportunity:** Cross-check against the Flet support root's parent (`support_root()` is `.../files/data`-ish; its parent's `usr`/`home` siblings) and prefer those when present, falling back to the hardcoded paths. Requires device verification.
- **Risk if ignored:** Wrong prefix on non-standard installs; proot fails to find libs. UNVERIFIED.

### F7 · P3 · `env_contract()` omits `PD_DOCKER_AUTH` (correct, but undocumented) and is not thread-safe
- **Where:** `src/core/storage_paths.py:36-53`; `src/app_controller.py:127,249-254` (sets `os.environ["PD_DOCKER_AUTH"]` directly at runtime).
- **What:** `PD_DOCKER_AUTH` is read by upstream at call time (`helpers/docker/transport.py:355,369,411`), not import time, so it is correctly excluded from the import-time contract and set later by the controller. That split is right but is not explained in storage_paths, so a future audit could flag it as "missing". Separately, `env_contract()` reads `support_root()`/`os.environ` with no lock; concurrent callers (bootstrap + check_probe) can interleave. `_BOOTSTRAPPED` is a plain module global with no synchronization (`proot_service.py:18`).
- **Evidence:** lines above.
- **Fix / opportunity:** Document the `PD_DOCKER_AUTH` split in the docstring; guard `_BOOTSTRAPPED` with a lock if concurrent bootstrap becomes possible.
- **Risk if ignored:** Documentation drift; latent race under concurrency. UNVERIFIED whether concurrency occurs.

---

## Missed capabilities (dependency audits only)

Not applicable (app file, not a dependency). Note: upstream `constants.py` also honors `TERMUX_APP__APP_VERSION_NAME` (used for `_detect_termux`); the app deliberately leaves it unset (see F3).

---

## Verified-good list

- Env var names match upstream exactly: `TERMUX_APP__PACKAGE_NAME` (`constants.py:47`), `TERMUX__HOME` (`:48`), `TERMUX__PREFIX` (`:51`), `XDG_DATA_HOME`/`XDG_CACHE_HOME` (`:80-88` non-Termux branch). Confirmed by `grep` and `test_env_contract_is_import_safe`.
- Path layout matches upstream non-Termux branch: `RUNTIME_DIR = XDG_DATA_HOME/proot-distro`, `BASE_CACHE_DIR = XDG_CACHE_HOME/proot-distro`, `CONTAINERS_DIR = RUNTIME_DIR/containers` (`constants.py:80-99`); `storage_paths.containers_dir()` equals `xdg_data_home()/proot-distro/containers`.
- `PD_FORCE_NO_COLORS` is a real upstream flag (`message.py:108`: `if sys.stderr.isatty() and not os.environ.get("PD_FORCE_NO_COLORS")`).
- Flet env var names are correct per installed source: `FLET_APP_STORAGE_DATA` (`flet/.../storage_paths.py:72`) and `FLET_APP_STORAGE_TEMP` (`:188`), both documented as set "in a running Flet app".
- `os.environ.get`, `Path`, `os` usage is standard Python 3.14 stdlib; no Flet API is used in this file, so there is no Flet hallucination to flag.
- `env_contract()` uses `os.environ.update`-compatible `dict[str, str]` and does not clobber payload vars (`PD_PROOT_BIN`/`PROOT_LOADER`/`LD_LIBRARY_PATH`) because it only sets keys it contains; `PROOT_TMP_DIR` agrees between both modules (`storage_paths.py:51`, `proot_probe.py:107`).
- `support_root()` prefers data over temp, matching Flet's documented semantics (data = persistent support dir; temp = disposable).
- Sole-importer rule is respected: storage_paths does not import `proot_distro`.

---

## Unverified

- Whether the native Flet host populates `FLET_APP_STORAGE_DATA`/`_TEMP` before `main(page)` runs (F1) — cannot be proven from `.venv` or `src/`; needs a device run or host source.
- Real `/data/data/<pkg>/files` layout on target devices (work profiles, multi-user) (F6).
- Whether `Path.cwd()` is writable in the CI/test invocation context (F5).
- Whether concurrent `bootstrap()` calls occur in practice (F7).
- Whether `proot` itself creates `PROOT_TMP_DIR` if absent (F4) — needs device run.