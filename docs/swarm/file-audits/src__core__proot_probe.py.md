# src/core/proot_probe.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/core/proot_probe.py` (136 lines) · `src/app_controller.py` (`check_probe` at :276-286) · `src/services/proot_service.py` (`bootstrap` at :32-42) · `src/core/storage_paths.py` · `tests/test_core.py` (:79-98) · installed Python 3.14.9 stdlib · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/proot_probe.py` is the pre-UI gate: `bootstrap_env()` (called from `AppController.check_probe` via `asyncio.to_thread`) discovers the APK's native lib dir (`ANDROID_NATIVE_LIBRARY_DIR`), stages the `flet_proot` payloads (soname != jni) into a runtime dir, sets the `LD_LIBRARY_PATH`/`PD_PROOT_BIN`/`PROOT_LOADER`/`PROOT_TMP_DIR` env contract, runs proot's f2fs-bug probe, execs `proot --version`, and checks the containers root is writable. Returns a `ProbeResult` whose `problems` list drives `state.probe_passed`/`probe_summary`. `bootstrap_env` is the only path that sets the payload env vars; `proot_service.bootstrap()` later layers `storage_paths.env_contract()` on top.

---

## Findings

### F1 · P2 · `_f2fs_probe` does not catch write failures, so a non-writable probe base crashes the whole probe
- **Where:** `src/core/proot_probe.py:45-52` (`(d / "aa").write_bytes(b"x")` etc.) and `:38-43` (only `mkdtemp` is guarded); caller `src/app_controller.py:276-286` does not catch.
- **What:** The outer `try` at :40-43 covers only `tempfile.mkdtemp`. If the temp dir is created but the subsequent `write_bytes` raises `OSError`/`PermissionError` (or `base_dir` is a file), the exception escapes `_f2fs_probe` and `bootstrap_env`, and `asyncio.to_thread` re-raises into `check_probe`, which has no `except`. App init (which `await`s `check_probe`) then fails instead of reporting a problem.
- **Evidence:** `src/core/proot_probe.py:38-62` shows the second `try` has no `except` (only `finally` cleanup); `app_controller.py:276-286` has only `finally: state.probe_running = False`.
- **Fix / opportunity:** Wrap the write/existence block in `except OSError as exc: return f"probe failed: {exc!r}"`, mirroring the `mkdtemp` guard.
- **Risk if ignored:** A single unwritable tmp dir aborts startup instead of a probe verdict.

### F2 · P2 · `bootstrap_env` has no top-level guard; several operations can raise and abort startup
- **Where:** `src/core/proot_probe.py:76` (`runtime.mkdir(parents=True, exist_ok=True)`), `:96` (`dst.write_bytes(src.read_bytes())`), `:98` (`dst.chmod(0o755)`), `:127-130` (`croot.mkdir(...)` is guarded, but `:76` and `:96-98` are not), `:109-113`.
- **What:** `runtime.mkdir` raises `FileExistsError` if `runtime` exists as a file; `dst.write_bytes`/`chmod` raise on read-only or full filesystems. These occur outside any `try`, so they propagate through `check_probe` and crash init. The per-lib staging loop's `try` at :80-101 would catch them, but only if reached; `runtime.mkdir` at :76 precedes it.
- **Evidence:** lines above.
- **Fix / opportunity:** Move `runtime.mkdir` into a `try/except` appending `f"runtime not creatable: {exc!r}"` and returning; wrap per-lib `write_bytes`/`chmod` in their own `try` so one bad lib does not abort the rest of staging.
- **Risk if ignored:** Partial/corrupt staging or a stray file at the runtime path bricks startup.

### F3 · P3 · `PROOT_TMP_DIR` is never created; f2fs probe and proot both depend on it
- **Where:** `src/core/proot_probe.py:107` sets `os.environ["PROOT_TMP_DIR"] = str(storage_paths.support_root() / "tmp")`; `src/core/storage_paths.py:51` same; `_f2fs_probe` falls back to `runtime` when tmp is not a dir (`proot_probe.py:109-113`).
- **What:** Nothing in `src/` calls `mkdir` on `support_root()/tmp`. If proot requires the directory to exist (it reads `PROOT_TMP_DIR` at startup), execs may fail with a confusing error; the f2fs probe silently uses `runtime` instead, so its verdict does not reflect the real tmp fs.
- **Evidence:** `grep -rn "mkdir" src/` shows only `runtime` and `containers_dir`/`support_root` parents; no `tmp` mkdir.
- **Fix / opportunity:** Add `(storage_paths.support_root() / "tmp").mkdir(parents=True, exist_ok=True)` before setting the env var (guarded), so the probe and proot use the real directory.
- **Risk if ignored:** f2fs verdict measured on the wrong filesystem; possible proot startup failure.

### F4 · P3 · `LD_LIBRARY_PATH` is overwritten, discarding any pre-existing entries
- **Where:** `src/core/proot_probe.py:103-104` (`ld = [str(p) for p in (native, runtime) if p]`; `os.environ["LD_LIBRARY_PATH"] = ":".join(ld)`).
- **What:** Any `LD_LIBRARY_PATH` already present (e.g. from the host/serious_python) is replaced rather than merged. `if p` is always true for `Path`, so the guard is dead. On Android the native dir is usually already present, but on unusual hosts (emulator with extra lib dirs) those paths vanish.
- **Evidence:** lines 103-104.
- **Fix / opportunity:** Merge: `existing = os.environ.get("LD_LIBRARY_PATH", "")`; build `ld` from `[native, runtime]` plus existing entries not already included.
- **Risk if ignored:** Missing shared libs on non-standard hosts. Low probability on target.

### F5 · P3 · Dev fallback glob pattern is unverified against the real `/data/app` layout
- **Where:** `src/core/proot_probe.py:31-34` (`Path("/data/app").glob("*/ng.kiri.prootdistro-*/lib/*")`).
- **What:** The pattern assumes an extra directory level under `/data/app` before the package dir. Real Android installs often place the package dir directly at `/data/app/<pkg>-<hash>/...` (no `*/` prefix) or under `/data/app/~~...`. If the pattern never matches, `_native_library_dir()` returns `None` even on a device where `ANDROID_NATIVE_LIBRARY_DIR` is unset, producing a false "no nativeLibraryDir" failure.
- **Evidence:** pattern at :32; cannot verify layout without a device.
- **Fix / opportunity:** Broaden to `Path("/data/app").rglob("ng.kiri.prootdistro-*/lib/*")` (or also try `Path("/data/app").glob("ng.kiri.prootdistro-*/lib/*")`), keeping the first directory hit. Label UNVERIFIED on device.
- **Risk if ignored:** Dev/emulator fallback unusable; UNVERIFIED.

### F6 · P3 · No architecture check against the staged payload
- **Where:** `src/core/proot_probe.py:81-99` reads `flet_proot.LIBS`/`SOURCES` but never `getattr(flet_proot, "ARCH", ...)` (manifest writes `ARCH` at `build_flet_proot_wheel.py:382`); no `platform`/`os.uname` use.
- **What:** A wrong-ABI wheel would stage and pass `proot --version` only if the binary happens to run; the probe cannot detect an arch mismatch early. `flet_proot.ARCH` is available but unused.
- **Evidence:** `build_flet_proot_wheel.py:378-385` writes `ARCH = {arch!r}`; `proot_probe.py:81-87` reads VERSION/SOURCES/LIBS only.
- **Fix / opportunity:** Compare `getattr(flet_proot, "ARCH", None)` with `platform.machine()` (aarch64/x86_64) and append a problem on mismatch. Value vs cost: small; useful for mis-packaged builds.
- **Risk if ignored:** Wrong-arch payload discovered only at runtime.

### F7 · P3 · Subprocess failure detail (stdout/stderr) is discarded
- **Where:** `src/core/proot_probe.py:115-125` (`proc = subprocess.run(..., capture_output=True, ...)`; on nonzero rc only `f"proot --version rc={proc.returncode}"` is recorded).
- **What:** `proc.stdout`/`proc.stderr` are captured but never surfaced, so a failing `proot --version` gives no diagnostic. `TimeoutExpired` is caught generically.
- **Evidence:** :122-125.
- **Fix / opportunity:** Append a truncated stderr/stdout tail to the problem string (e.g. `...: {proc.stderr.decode(errors='replace')[:200]}`).
- **Risk if ignored:** Harder field debugging; low.

### F8 · P3 · Concurrent `bootstrap_env` calls can race on the runtime dir and staged files
- **Where:** `src/core/proot_probe.py:65-136` (no lock); `src/app_controller.py:276-286` allows repeated `check_probe` invocations.
- **What:** Two concurrent probes can both `write_bytes`/`chmod` the same `dst`, and `runtime.mkdir` races. `Path.write_bytes` is not atomic; a reader (proot) could see a half-written lib. No observed failure, but no guard exists.
- **Evidence:** lines 96-98 and app_controller `check_probe` (no guard against re-entry; `state.probe_running` is set but not checked).
- **Fix / opportunity:** Guard re-entry in `check_probe` (return if `state.probe_running`) and/or use atomic write (temp file + `replace`) in staging.
- **Risk if ignored:** Rare torn-write on repeated probe. UNVERIFIED on device.

---

## Missed capabilities (dependency audits only)

Not applicable (app file, not a dependency). Note: `flet_proot.ARCH` and `flet_proot.WHEEL_BUILD_TAG` (manifest fields at `build_flet_proot_wheel.py:379-382`) are available but unused by the probe.

---

## Verified-good list

- `ProbeResult` dataclass with `field(default_factory=...)` is valid Python 3.14 (`dataclasses`); `ok` property logic correct.
- `os.environ.get`, `Path.is_dir`, `Path.glob`, `tempfile.mkdtemp(dir=...)`, `Path.write_bytes`, `Path.stat().st_size`, `Path.chmod`, `subprocess.run(capture_output=..., timeout=..., env=...)` all exist in Python 3.14.9 stdlib (verified via `python -c`).
- `native`/`runtime` list comprehension and `":".join` are fine; `os.environ` assignment is standard.
- Env contract ordering is correct in the happy path: `check_probe` (probe sets `PD_PROOT_BIN`/`PROOT_LOADER`/`LD_LIBRARY_PATH`/`PROOT_TMP_DIR`) runs before `proot_service.bootstrap()` (which calls `posixdb.ensure()` then `os.environ.update(storage_paths.env_contract())`); `env_contract()` does not clobber the payload vars, and `PROOT_TMP_DIR` agrees (`storage_paths.py:51`).
- Containers-root writability check (`proot_probe.py:127-134`) is guarded and appends a problem instead of raising.
- `flet_proot` import is guarded (`:80-101`) and degrades to `payload_provenance = "unavailable"`-style staging note on desktop.
- Sole-importer rule intact: `proot_probe.py` does not import `proot_distro` (only `flet_proot`), so `tests/test_proot_surfaces.py` still passes.
- `bootstrap_env(runtime_root=...)` override is honored (`:76`), matching `tests/test_core.py:87`.

---

## Unverified

- Real `/data/app` directory layout for the dev fallback glob (F5) — requires a device/emulator.
- Whether `proot` itself creates `PROOT_TMP_DIR` if absent (F3) — requires device run.
- Whether `LD_LIBRARY_PATH` overwrite breaks anything on target (F4) — requires device run.
- Concurrency/torn-write risk (F8) — not observed; plausible only.
- Whether `flet_proot.ARCH` matches `platform.machine()` naming on the target (F6) — wheel manifest uses `aarch64`/`x86_64` (`build_flet_proot_wheel.py:182-183`), while `platform.machine()` returns `aarch64`/`x86_64` on Linux; naming likely matches but unverified on Android CPython.