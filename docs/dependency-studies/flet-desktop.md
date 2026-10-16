# flet-desktop 1.0.4 — exhaustive API reference

> Companion to `docs/reference/dep-flet-build-host.md` (summary) and `docs/roadmap.md` (M5 packaging context).
> Every claim cites the installed source (`.venv/Lib/site-packages/flet_desktop/...`)
> or live introspection; anything not established there is labeled **unverified**.
> flet stays 1.0.4 per D-010. Verified 2026-10-16.

## 0. How to read this file

* `FD:` = `flet_desktop/__init__.py`; `VER:` = `flet_desktop/version.py`; `WT:` = `flet_desktop/win_taskbar.py`.
* `RUN:` = `flet_cli/commands/run.py`; `PACK:` = `flet_cli/commands/pack.py`; `PIPU:` = `flet/utils/pip.py`.
* "Private" (`__name`) helpers are documented because they ARE the download/cache/config mechanics — there is no other spec.

---

## 1. Identity

| Item | Value | Source |
|---|---|---|
| Package / version | `flet-desktop 1.0.4` | `VER:1` (`version = "1.0.4"`); `flet_desktop-1.0.4.dist-info/METADATA:2-3` |
| Summary | `Flet Desktop client in Flutter` | `METADATA:4` |
| License | `Apache-2.0` | `METADATA:6` (`License-Expression: Apache-2.0`) |
| Requires-Python | `>=3.10` | `METADATA:10` |
| Runtime deps | `flet==1.0.4`, `rich>=13.0.0` | `METADATA:12-13` |
| Module layout | `__init__.py` (client cache + launcher), `version.py`, `win_taskbar.py` (taskbar identity) | directory listing of installed `flet_desktop` |
| Role | Prebuilt desktop viewer client used by `flet run`; bundled/pached client host for `flet pack` | `FD:335-400`, `RUN:602-625`, `PACK:385-625` |
| APK relevance | **None ships into the APK.** `flet build apk` does not need it; only `run.py` + `pack.py` touch it | `RUN:`, `PACK:` grep; roadmap §1b |

Live introspection (2026-10-16):

```text
flet_desktop C:\...\site-packages\flet_desktop\__init__.py
version version = "1.0.4"
```

---

## 2. Every public API

### 2.1 `get_package_bin_dir()` — `FD:48-59`

```python
def get_package_bin_dir():
```

Returns `str(Path(__file__).parent.joinpath("app"))` — the directory holding bundled desktop runtime artifacts (platform executables or compressed archives used to provision the client at runtime). When the package is installed without bundled binaries the directory is empty and the download path is used instead (docstring `FD:49-57`).

Consumers: `ensure_client_cached()` checks `os.path.join(get_package_bin_dir(), artifact)` for a bundled archive before downloading (`FD:348`); `flet_cli/__pyinstaller/hook-flet.py:17` appends `(bin_path, "flet_desktop/app")` datas so a PyInstaller bundle carries its client with it.

### 2.2 `get_artifact_filename()` — `FD:148-167`

```python
def get_artifact_filename():
```

Returns the release artifact filename for the current platform (docstring `FD:149-155`):

* Windows: `flet-windows.zip`
* macOS: `flet-macos.tar.gz`
* Linux: `flet-linux-{distro}[-light]-{arch}.tar.gz`

Linux branch resolves `{distro}` via `__get_linux_distro_id()` and `{arch}` via `flet.utils.get_arch()` (imported `FD:25-32`), appends `-light` only when flavor is `"light"` (`FD:163-167`). Used by `ensure_client_cached()` (`FD:347`) and by `flet pack` on Linux to name the recompressed client dir (`PACK:611` `from flet_desktop import get_artifact_filename`).

### 2.3 `ensure_client_cached()` — `FD:335-400`

```python
def ensure_client_cached():
```

Ensures the desktop client is extracted in the local cache directory. If the cache dir does not exist, looks for a bundled archive in the package (PyInstaller/legacy wheel) and falls back to downloading from GitHub Releases. Returns `Path` to the cache dir containing the unpacked client (docstring `FD:336-345`).

Exact steps (`FD:347-400`):

1. `artifact = get_artifact_filename()`.
2. `bundled = os.path.join(get_package_bin_dir(), artifact)`; `archive_path = bundled if exists else None`.
3. `fingerprint = __get_archive_fingerprint(archive_path) if archive_path else None`.
4. `cache_dir = __get_client_storage_dir(fingerprint)`; if it exists, touch `.last-used` and return it (`FD:357-361`).
5. Else `archive_path = __download_flet_client(artifact)` when no bundle.
6. Extract to `temp_extract = cache_dir.parent / f"{cache_dir.name}.{random_string(8)}"`, `mkdir(parents=True)` (`FD:369-370`).
7. Format chosen by **artifact name**, not the (random-suffixed) download path: `.zip` → `zipfile` + `safe_zip_extractall`, else `tarfile.open(archive_path, "r:gz")` + `safe_tar_extractall` (`FD:376-381`). The `safe_*` helpers come from `flet.utils` (`FD:25-32`) — path-traversal-safe extraction.
8. Atomic `temp_extract.rename(cache_dir)`; on `OSError` (lost race with a concurrent extraction) reuse winner's dir if it now exists, else re-raise (`FD:383-391`). Any other exception removes `temp_extract` and re-raises (`FD:392-394`).
9. Touch `.last-used`; if fingerprinted, run `__gc_stale_client_dirs(cache_dir)` (`FD:397-399`).

Callers: `__locate_and_unpack_flet_view()` on all three OS branches (`FD:646,673,713`); `flet_cli/__pyinstaller/utils.py:8,30` (`from flet_desktop import ensure_client_cached; cache_dir = ensure_client_cached()`).

### 2.4 `find_macos_app_bundle(directory)` — `FD:403-422`

```python
def find_macos_app_bundle(directory) -> Path | None:
```

Returns the first `.app` bundle directly inside `directory` (sorted listing), or `None` when the directory is missing or holds no `.app` — letting the caller fall through to the next client source instead of raising (docstring `FD:404-414`). Implementation: `Path(directory)`, `is_dir()` guard (`FD:415-417`), `sorted(os.listdir)`, `name.endswith(".app")` (`FD:419-422`).

### 2.5 `open_flet_view(page_url, assets_dir, hidden)` — `FD:491-512`

```python
def open_flet_view(page_url, assets_dir, hidden):
```

Starts a desktop view process. Args (docstring `FD:493-504`):

| Param | Meaning |
|---|---|
| `page_url` | Page endpoint the desktop client should open |
| `assets_dir` | Optional assets directory passed to the client process (appended to argv when truthy, `FD:720-721`) |
| `hidden` | Whether the window should start hidden (sets `FLET_HIDE_WINDOW_ON_START=true` in child env, `FD:723-724`) |

Returns `(subprocess.Popen, str pid_file_path)`; the PID file is consumed by `close_flet_view()`. Body (`FD:506-512`): `args, flet_env, pid_file = __locate_and_unpack_flet_view(...)`, then `__linux_identity_args(args)`, `subprocess.Popen(args, env=flet_env, **extra)`, `__apply_taskbar_props(p.pid)`.

`flet run` calls it as `open_flet_view(self.page_url, self.assets_dir, self.hidden)` (`RUN:611-614`) inside `open_flet_view_and_wait()` (`RUN:602`), then `self.fvp.wait()` and SIGTERMs the app server when the viewer exits (`RUN:615-620`).

### 2.6 `open_flet_view_async(page_url, assets_dir, hidden)` — `FD:515-536`

```python
async def open_flet_view_async(page_url, assets_dir, hidden):
```

Async twin. Same args/returns except the process is `asyncio.subprocess.Process` via `await asyncio.create_subprocess_exec(args[0], *args[1:], env=flet_env, **extra)` (`FD:534`), with the same Linux-identity + taskbar stamping (`FD:533,535`). No in-tree caller at 1.0.4 — **unverified** whether external code uses it; it is public API regardless.

### 2.7 `close_flet_view(pid_file)` — `FD:559-581`

```python
def close_flet_view(pid_file):
```

Terminates a running desktop view using its PID file: reads int PID, `os.kill(pid, SIGKILL)`, removes the file. Termination failures are intentionally ignored, but the PID file is removed when possible (docstring `FD:560-566`). Guards `pid_file is not None and os.path.exists(pid_file)` (`FD:572`); `open(pid_file, encoding="utf-8")`, `int(f.read())` (`FD:574-575`); bare-`except: pass` with `finally: os.remove(pid_file)` (`FD:578-581`). `flet run` imports it at shutdown (`RUN:397` `from flet_desktop import close_flet_view`).

### 2.8 Version surface — `VER:1`

```python
version = "1.0.4"
```

Single-assignment module. Compared against `flet.version.flet_version` by `ensure_flet_desktop_package_installed()` (`PIPU:97-105`): missing or version-skewed → `raise RuntimeError("flet-desktop version mismatch")` → `install_flet_package("flet-desktop")`. This is the lock-step auto-reinstall mechanism (roadmap §3/R1).

### 2.9 `win_taskbar` surface — `WT`

Windows-only module (imports `ctypes.OleDLL/WINDLL`, `WT:29-31`). Public entry:

```python
def apply_relaunch_props_async(pid: int) -> None:  # WT:252-1048
```

Stamps AppUserModel window properties on the Flet client window. Waits on a daemon thread for the client to create its top-level window, then sets AppUserModelID + relaunch command/name/icon from env (`WT:984-996` docstring+body):

* `FLET_APP_USER_MODEL_ID` (required; no-op when unset or `os.name != "nt"`, `WT:997-999`)
* `FLET_APP_RELAUNCH_COMMAND` (else derived `"{aumid}"` when the ID is an existing file path)
* `FLET_APP_RELAUNCH_DISPLAY_NAME` (else basename-without-ext of that path)
* `FLET_APP_RELAUNCH_ICON` (else `"{aumid},0"`)

No derivable relaunch command → debug-log and return (`WT:1010-1012`). Worker holds a `SYNCHRONIZE` handle to the client (detects exit, blocks PID recycling), polls `_find_top_window(pid)` every 0.2 s, stamps via `_set_props`, exits when the client exits first (`WT:1020-1048`).

Supporting public-in-module (underscore-prefixed, but load-bearing) symbols:

* `GUID` (`WT:65-783`), `PROPERTYKEY` (`WT:89-795`), `PROPVARIANT` (`WT:98-815`) — ctypes COM mappings.
* `_PKEY_FMTID = "{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}"` (`WT:155`); `_PID_RELAUNCH_COMMAND = 2`, `_PID_RELAUNCH_ICON = 3`, `_PID_RELAUNCH_DISPLAY_NAME = 4`, `_PID_AUMID = 5` (`WT:156-159`) — `System.AppUserModel.*` keys per propkey.h.
* `_FLUTTER_WINDOW_CLASS = "FLUTTER_RUNNER_WIN32_WINDOW"` (`WT:184`) — matched by `_find_top_window()` (`WT:187-948`).
* `_find_top_window(pid)` (`WT:187`), `_set_props(hwnd, props)` (`WT:220-980`), `_propvariant_from_string(value)` (`WT:90-841`).

Invoked from `__apply_taskbar_props(pid)` (`FD:539-556`), which no-ops unless Windows + `FLET_APP_USER_MODEL_ID` set (`FD:549`), importing `apply_relaunch_props_async` lazily and warning (not raising) on failure (`FD:551-556`). The env values themselves are set by the flet-cli PyInstaller runtime hook (`flet_cli/__pyinstaller/rthooks/pyi_rth_localhost_fletd.py:14-15,31`).

---

## 3. Client-cache / download logic

### 3.1 Paths

* Package bundle dir: `<site-packages>/flet_desktop/app/` (`FD:59`).
* User cache root: `~/.flet/client/`; per-client dir `flet-desktop-{flavor}-{version}[-{fingerprint}]` (`FD:187-191`).
* Fingerprint suffix only when the client came from a bundled archive (keeps `flet pack`-patched clients from shadowing each other or the vanilla client, `FD:173-178`).
* Temp download: `tempfile.gettempdir()/f"{file_name}.{random_string(10)}"` (`FD:330`).
* Temp extract: sibling `{cache_dir.name}.{random_string(8)}` then atomic rename (`FD:369-384`).
* Markers: `.last-used` in each live dir (`FD:360,397`); `<archive>.sha256` sidecar holding `<hash> <size>` (`FD:222-243`); `.trash-{rand8}` during GC (`FD:290-293`).
* PID file: `tempfile.gettempdir()/random_string(20)` (`FD:617`).

### 3.2 URL pattern

```python
ver = flet_desktop.version.version  # FD:325
flet_url = f"https://github.com/flet-dev/flet/releases/download/v{ver}/{file_name}"  # FD:326
flet_url = os.environ.get("FLET_CLIENT_URL", flet_url)  # FD:327 — full override
```

Log + one-time console notice (`FD:328-329`), then `__download_with_progress()` — `urllib.request.urlopen`, `rich.progress.Progress(transient=True)`, `Content-Length` total when present, 8 KiB chunks (`FD:297-307`).

### 3.3 Integrity

No checksum on the network download — **verified**: `__download_flet_client()` (`FD:310-332`) performs no hash verification; transport trust is HTTPS to github.com plus (for bundles) the fingerprint scheme below. Integrity that DOES exist:

* Fingerprint: first 12 hex of SHA-256 of the bundled archive (`FD:204-243`). Prefers `<archive>.sha256` sidecar (`<hash> <size>`) only when size still matches AND hash is 64-char lowercase hex (`FD:226-233`); else streams the file in 1 MiB chunks, writes the sidecar best-effort (`FD:236-243`).
* Hex validation `__is_hex()` (`FD:194-202`); GC only recognizes 12-hex suffixes (`FD:271-280`).
* Extraction uses `safe_zip_extractall` / `safe_tar_extractall` from `flet.utils` (`FD:377-381`).
* Atomic rename prevents half-extracted caches being treated as valid (`FD:366-368`); concurrent-race reuse (`FD:386-391`); stale fingerprinted siblings unused for 30 days are rename-then-delete GC'd (Windows-safe: in-use rename fails and is left alone), plus `.trash-*` sweep (`FD:246-294`).

Roadmap D3's "template zip has no checksum" note is about the cookiecutter template, NOT this client — do not conflate the two.

### 3.4 Linux distro / flavor resolution

* `_GLIBC_DISTRO_TABLE` (`FD:40-46`): `(2,28)→debian10`, `(2,31)→ubuntu20.04`, `(2,35)→ubuntu22.04`, `(2,36)→debian12`, `(2,39)→ubuntu24.04`.
* `__get_system_glibc_version()` via `ctypes.util.find_library("c")` + `gnu_get_libc_version`, fallback `(0,0)` (`FD:100-118`).
* `__get_linux_distro_id()`: `FLET_LINUX_DISTRO` override wins; else highest table entry ≤ system glibc; undetectable → oldest (`debian10`) + warning (`FD:121-145`).
* `__get_desktop_flavor()`: `FLET_DESKTOP_FLAVOR` env → `[tool.flet].desktop_flavor` in CWD `pyproject.toml` (tomllib ≥3.11, tomli below) → default `"light"` on Linux, `"full"` elsewhere (`FD:62-97`).
* `__linux_identity_args()`: when Linux + valid `FLET_APP_ID`, launch argv[0] as the app id with `executable=` pointing at the real binary, so GLib/GTK derive WM_CLASS/Wayland app_id per-app instead of grouping everything as "flet" (`FD:444-488`).

---

## 4. How `flet run` / `flet pack` use it

### 4.1 `flet run` (`RUN:`)

* Startup: `--web/--ios/--android` → `ensure_flet_web_package_installed()`; otherwise `ensure_flet_desktop_package_installed()` (`RUN:223-235`). So desktop runs need the package; mobile/web preview runs do NOT open a native window.
* Serve loop spawns `open_flet_view_and_wait()` on a daemon thread (`RUN:596`); that calls `open_flet_view(page_url, assets_dir, hidden)` (`RUN:611-614`), blocks on `fvp.wait()`, then SIGTERMs the app server (`RUN:615-620`).
* Shutdown imports `close_flet_view` (`RUN:397`).
* Client resolution order inside `__locate_and_unpack_flet_view()` (`FD:587-593`): (1) `flet build` output in CWD (`build/windows/*.exe`, macOS `.app`, Linux executable bit, each logged as warning via `__log_build_client()` `FD:425-441` because a stale built client lacks newly-added extensions); (2) `FLET_VIEW_PATH` dev override; (3) cached/downloaded client.
* Per-OS argv: Windows `[flet_path, page_url, pid_file]` (`FD:649`); macOS `["open", app, "-n", "-W", "--args", page_url, pid_file]` (`FD:682`); Linux `[app, page_url, pid_file]` (`FD:716`). `assets_dir` appended positionally (`FD:720-721`); `hidden` → env `FLET_HIDE_WINDOW_ON_START=true` (`FD:723-724`); full `os.environ` copy otherwise (`FD:718`).
* Roadmap consequence (§1b): the desktop viewer is prebuilt — third-party extension Dart (flet-terminal/flet-ads) never renders under `flet run`; extension panes need placeholders locally and CI APKs for device truth.

### 4.2 `flet pack` (`PACK:`)

* Entry calls `ensure_flet_desktop_package_installed()` (`PACK:393-395`).
* Windows (`PACK:530-614`): patches version info into the client, recompresses `flet/` dir → `flet-windows.zip` via `compress_flet_client_dir()` so `ensure_client_cached()` finds it at runtime (`PACK:541`).
* macOS: unpacks/patches the `.app` (icon via `update_flet_view_icon`, version via `update_flet_view_version_info`), reassembles → `flet-macos.tar.gz`, writes `.sha256` fingerprint sidecar (`PACK:595-614`, `write_archive_fingerprint` at `PACK:220` context).
* Linux: recompresses via `get_artifact_filename()` (`PACK:611`) so the runtime lookup hits the patched bundle.
* The `.sha256` sidecar written at pack time is exactly what `__get_archive_fingerprint()` prefers at runtime (`FD:222-233`).

### 4.3 `flet build` (APK etc.)

Does NOT use flet-desktop. Icon/splash generation for builds lives in `flet-platform-assets` (see `flet-platform-assets.md`), invoked from `build_base.py`. Stating again because it is load-bearing for M5: building the APK needs no desktop client download.

---

## 5. Config knobs

| Knob | Where | Effect |
|---|---|---|
| `[tool.flet].desktop_flavor` | `pyproject.toml` (CWD at `flet run` time) | `"full"` / `"light"` client; env wins; default light-on-Linux else full (`FD:62-97`) |
| `FLET_DESKTOP_FLAVOR` | env | Overrides the above (`FD:72-75`) |
| `FLET_LINUX_DISTRO` | env | Pins Linux artifact distro id, bypasses glibc probe (`FD:129-132`) |
| `FLET_CLIENT_URL` | env | Replaces the whole GitHub Release download URL (`FD:327`) |
| `FLET_VIEW_PATH` | env (dev) | Directory containing `flet.exe` / `.app` / `flet` to launch instead of cache (`FD:631-642,659-669,697-710`) |
| `FLET_APP_ID` | env | Linux argv[0] identity (taskbar grouping/label) (`FD:466-488`) |
| `FLET_APP_USER_MODEL_ID` | env (set by PyInstaller runtime hook for packed apps) | Enables Win taskbar stamping (`FD:549`) |
| `FLET_APP_RELAUNCH_COMMAND` / `FLET_APP_RELAUNCH_DISPLAY_NAME` / `FLET_APP_RELAUNCH_ICON` | env | Taskbar relaunch/name/icon values (`WT:1001-1009`) |
| `FLET_HIDE_WINDOW_ON_START` | child env (set from `hidden`) | Client starts hidden (`FD:723-724`) |
| Rich progress | `rich>=13.0.0` dep | Download bar; `transient=True` so it vanishes after (`FD:299`) |

---

## 6. How flet-desktop makes our app significantly better than Termux's proot-distro

Termux's proot-distro is a shell-plugin ecosystem: install/run/list happen inside someone else's terminal, with zero owned UI, zero brand, and a dev loop gated on pushing to a device. flet-desktop changes the shape of the project, not just its tooling:

1. **Instant local dev loop for everything except the terminal view.** `flet run` opens the prebuilt viewer in one step (cache in `~/.flet/client/`, download once per version). All non-extension UI — distro list, install flow, container actions, settings, ads placeholders, probe-gating screens (M3) — iterates on desktop in seconds, while Termux-side work needs a device or emulator every cycle.
2. **Honest extension boundary.** Because the viewer is prebuilt and never contains third-party Dart, flet-terminal/flet-ads *cannot* render under `flet run` — the failure is architectural, not flaky. That forces the correct pattern early (platform-availability placeholders, ads mobile-gating) instead of discovering it at release.
3. **Packed-desktop path for free.** `flet pack` reuses the same client cache + fingerprinting to produce branded Windows/macOS/Linux artifacts from the same codebase — a Termux plugin can never become a desktop app. The fingerprint/GC design means per-app patched clients coexist safely.
4. **Taskbar/window identity without rebuilding the client.** `FLET_APP_ID` (Linux) and the `win_taskbar` AppUserModel stamping (Windows) give the packed app its own name/icon/pin from env + argv alone — branding leverage with zero native code from us.

It does NOT improve the on-device proot mechanics (exec, loader, seccomp) — those are proven in M0 on real hardware. It compresses everything around them.

---

## 7. Verification

* `flet_desktop/__init__.py:40-46` glibc table; `:48-59` bundle dir; `:62-97` flavor; `:100-145` glibc/distro; `:148-167` artifact names; `:170-243` storage dir + fingerprint; `:246-307` GC + download; `:310-332` release URL; `:335-400` ensure_cached; `:403-441` macOS bundle + build-client warning; `:444-488` Linux identity; `:491-536` open (+async); `:539-556` taskbar hook; `:559-581` close; `:584-726` resolver + per-OS argv.
* `flet_desktop/version.py:1` version.
* `flet_desktop/win_taskbar.py:65-815` COM structs; `:155-159` PKEY/PIDs; `:184` Flutter window class; `:187-980` find/set; `:252-1048` async applier + env contract.
* `flet/utils/pip.py:88-105` lock-step reinstall.
* `flet_cli/commands/run.py:223-235,397,596-625` run integration; `flet_cli/commands/pack.py:220,393-395,530-625` pack integration; `flet_cli/__pyinstaller/utils.py:8,30`, `hook-flet.py:17`, `rthooks/pyi_rth_localhost_fletd.py:14-31` PyInstaller integration.
* `flet_desktop-1.0.4.dist-info/METADATA:2-13` identity/deps.
* Live: `python -c "import flet_desktop, flet_platform_assets, PIL"` import paths + `Pillow 12.3.0` (2026-10-16).
