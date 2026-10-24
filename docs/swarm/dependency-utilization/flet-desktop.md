# flet-desktop 1.0.4 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/flet-desktop.md`; `docs/reference/dep-flet-build-host.md`; `docs/decisions.md`; `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `.gitignore`; `src/main.py`; `src/components/banner_ad.py:45-62`; `src/services/ad_service.py:48-56`; `src/services/proot_service.py:21-22`; `src/screens/terminal_view.py:12`; `.venv/Lib/site-packages/flet_desktop/{__init__.py,version.py,win_taskbar.py}`; `.venv/Lib/site-packages/flet_cli/commands/run.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2556-2612`; `.venv/Lib/site-packages/flet/{app.py,version.py,utils/pip.py}`; `flet`/`flet_ads`/`flet_desktop` dist-info METADATA; `~/.flet/client/flet-desktop-full-1.0.3/`, `~/.flet/client/flet-desktop-full-1.0.4/`; `git show HEAD:docs/roadmap.md`, `git show HEAD:docs/testing-findings.md` (both are **deleted in the working tree** — uncommitted deletions, see F6) · **Date:** 2026-10-20

## What it does / how the app uses it

`flet-desktop` is the host-only provider of the **prebuilt Flutter desktop client** that `flet run` launches. It contains no binaries of its own (the bundle dir `<site-packages>/flet_desktop/app` does not exist on this host), so on every fresh machine it downloads `flet-windows.zip` from the flet GitHub release, unpacks it into `~/.flet/client/flet-desktop-{flavor}-{version}/`, and starts `flet.exe` against the app's socket URL. It also owns the Windows taskbar-identity stamping used by packed apps.

It is a **dev-only** dependency (`pyproject.toml:80`, group `dev`) and **never ships into the APK**: the packaged set is `project.dependencies` + `tool.flet.<platform>.dependencies` only (`flet_cli/commands/build_base.py:2566-2576`), and `flet build apk` contains zero `flet_desktop` references (grep over `flet_cli/` finds it only in `commands/run.py`, `commands/pack.py`, `__pyinstaller/`).

**The three questions this audit was asked to answer:**

1. **Is it needed for `flet run`? — Yes, and it is the only thing that makes `flet run` open a window.** `flet_cli/commands/run.py:227-232` picks `ensure_flet_desktop_package_installed()` for the desktop branch (`--web/--ios/--android` take the `flet-web` branch instead) and `run.py:611-614` calls `open_flet_view(...)` to start the client. The in-process path needs it too: `src/main.py:40` calls `ft.run(main, …)`, whose default view is `AppView.FLET_APP` (`flet/app.py:74,156`), and `flet/app.py:299-306` then calls `ensure_flet_desktop_package_installed()` + `open_flet_view_async(...)` whenever the app is not embedded and `FLET_DISPLAY_URL_PREFIX` is unset (i.e. `python src/main.py` run by hand). Under `flet run` the CLI sets that prefix (`run.py:493`), so the CLI process owns the window and the app subprocess does not open a second one.
2. **Does a local desktop workflow exist in this repo? — Yes, it is the documented second layer of the three-layer test loop.** `docs/decisions.md:19` (D-005) lists `uv run flet run` as step 2; `git show HEAD:docs/roadmap.md:46,48` repeats it and records the owner's desktop run as clean at M3 and M4 (`roadmap.md:89,108`); `git show HEAD:docs/testing-findings.md:6,40` makes it a hard gate ("Local `uv run flet run` smoke passed … The owner may also run it"). Machine evidence agrees: this host's `~/.flet/client/` holds `flet-desktop-full-1.0.3/` and `flet-desktop-full-1.0.4/` (97 MB extracted, `flet.exe` + `flutter_windows.dll` + the Flutter plugin DLLs), and the 1.0.4 `.last-used` marker was touched today. I also ran the loop end-to-end for this audit: `flet run src` booted the app (`Starting up TCP server on localhost:13056` → `App session started` → `AdService: non-mobile platform — consent flow skipped`) and the client started as `…\flet.exe tcp://localhost:2576 <pidfile> …\src\assets` — exactly the argv built at `flet_desktop/__init__.py:648` + `:719-720`.
3. **Does the owner's no-local-build rule make it dead weight? — No.** The rule forbids `flet build` (`docs/decisions.md:19`; `roadmap.md:13`; `testing-findings.md:45`), a *build* that compiles a client. `flet run` compiles nothing and uses the prebuilt client, so it is fully compliant with the rule and is the only way to iterate on the non-extension UI. The rule that would have made `flet-desktop` dead weight is the one that bans the *desktop build* (O-9), not the one that bans desktop *runs*.

## Findings

### F1 · P1 · `close_flet_view()` cannot terminate the desktop client on Windows — every `flet run` leaves an orphan window and process

- **Where:** `.venv/Lib/site-packages/flet_desktop/__init__.py:576` (`os.kill(fvp_pid, signal.SIGKILL)`), `:577-578` (bare `except Exception: pass`), `:579-580` (`finally: os.remove(pid_file)`); the only caller on the `flet run` path: `.venv/Lib/site-packages/flet_cli/commands/run.py:396-399`; the in-process path: `.venv/Lib/site-packages/flet/app.py:306,318`.
- **What:** `signal.SIGKILL` **does not exist on Windows** (CPython defines only `SIGABRT SIGBREAK SIGFPE SIGILL SIGINT SIGSEGV SIGTERM`). Line 576 therefore raises `AttributeError` *before* `os.kill` is ever called; the bare `except` at `:577` swallows it and the `finally` at `:579-580` deletes the pid file — the only handle anyone has on the client process. The client is never killed. `run.py` has no other reaping path (grep: the only `kill` is `self.p.kill()` on the *app* subprocess at `run.py:621`; no `taskkill`), so the `flet.exe` window survives the CLI.
- **Evidence:**
  ```text
  $ .venv/Scripts/python.exe -c "import signal; print(hasattr(signal,'SIGKILL'))"
  False
  $ .venv/Scripts/python.exe -c "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"
  AttributeError: module 'signal' has no attribute 'SIGKILL'. Did you mean: 'SIGILL'?
  ```
  Stand-in target process (the exact function flet-cli calls):
  ```text
  spawned stand-in pid 10764
  poll after close_flet_view -> None (None means STILL RUNNING)
  RESULT: client process still alive after close_flet_view(): True
  pid file still present: False
  ```
  Real client started by `flet run src` (pid file written by the client itself):
  ```text
  client pid: 12580
  client cmd: …\flet-desktop-full-1.0.4\flet\flet.exe tcp://localhost:2576 /home/maikel/AppData/Local/Temp/RqF3Dh23IILWXRjwXJqT …\src\assets
  pid file content: '12580'
  client alive after flet_desktop.close_flet_view(): True
  ```
  And in a separate run the client (pid 1400) was still running after the CLI process was killed outright.
- **Fix / opportunity:** upstream only — `flet-dev/flet`. `os.kill(pid, signal.SIGTERM)` works on Windows (TerminateProcess) and is the portable form; alternatively guard the signal with `getattr(signal, "SIGKILL", signal.SIGTERM)`. This repo must not patch upstream (D-001, `roadmap.md:13` "no patching of upstream"), so the actionable item is **file the issue with the repro above** and, until it is fixed, close the dev window manually (or `taskkill /IM flet.exe`) after a `flet run` session. 1.0.4 is the newest release on PyPI (checked 2026-10-20), so there is no fixed version to move to.
- **Risk if ignored:** every dev cycle on the owner's Windows machine leaks a GUI process; the pid file is destroyed, so nothing can reap it later and the process count grows with the number of `flet run` invocations. A stale client also keeps the socket/port and the 97 MB cache dir busy.

### F2 · P2 · HALLUCINATION in the prior study: the `win_taskbar.py` line references point past the end of the file

- **Where:** `docs/dependency-studies/flet-desktop.md:141-160` (`WT:65-783`, `WT:89-795`, `WT:98-815`, `WT:90-841`, `WT:187-948`, `WT:220-980`, `WT:984-996`, `WT:997-999`, `WT:1001-1009`, `WT:1010-1012`, `WT:1020-1048`) and its summary at `:264,266`; the installed file is `.venv/Lib/site-packages/flet_desktop/win_taskbar.py` = **317 lines**.
- **What:** every reference above `:317` is out of range. The real locations are `GUID` `win_taskbar.py:34-52`, `PROPERTYKEY` `:58-64`, `PROPVARIANT` `:67-83`, `_propvariant_from_string` `:90-110`, `IPropertyStoreVtbl` `:123-141`, `_IID_IPropertyStore` `:152`, the PKEY/PID constants `:155-159`, `_FLUTTER_WINDOW_CLASS` `:184`, `_find_top_window` `:187-217`, `_set_props` `:220-249`, `apply_relaunch_props_async` `:252-317` (env contract `:266-281`, props list `:283-287`, worker thread `:289-317`). The `__init__.py` references also drift by one line from `__get_desktop_flavor` downwards: `open_flet_view` is `:490-511` (not `FD:491-512`), `open_flet_view_async` `:514-535`, `__apply_taskbar_props` `:538-555`, `close_flet_view` `:558-580`, `__locate_and_unpack_flet_view` `:583-725`.
- **Evidence:**
  ```text
  $ wc -l .venv/Lib/site-packages/flet_desktop/*.py
    725 .venv/Lib/site-packages/flet_desktop/__init__.py
      1 .venv/Lib/site-packages/flet_desktop/version.py
    317 .venv/Lib/site-packages/flet_desktop/win_taskbar.py
  ```
  `grep -n "^def \|^class " .venv/Lib/site-packages/flet_desktop/win_taskbar.py` → `34: class GUID`, `58: class PROPERTYKEY`, `67: class PROPVARIANT`, `90: def _propvariant_from_string`, `123: class IPropertyStoreVtbl`, `144: class IPropertyStore`, `187: def _find_top_window`, `220: def _set_props`, `252: def apply_relaunch_props_async`.
- **Fix / opportunity:** correct §2.9 and §7 of `docs/dependency-studies/flet-desktop.md` to the line numbers above (the *semantics* the study describes are correct — the env contract, the polling worker, the path-traversal-safe extraction, the fingerprint scheme all check out; only the line anchors are wrong). This report is read-only, so the edit belongs to whoever owns the study.
- **Risk if ignored:** the synthesis re-opens or mis-attributes settled facts, and any later agent that greps `WT:1020` finds nothing and concludes the behavior was invented.

### F3 · P2 · The dev-group specifier is a floor, so the next lock refresh can trip the lockstep auto-reinstall and mutate `.venv` outside `uv.lock`

- **Where:** `pyproject.toml:80` (`"flet-desktop>=1.0.4"`); `uv.lock:240-250` (resolved `1.0.4`), `:597,615` (dev-group membership); `.venv/Lib/site-packages/flet/utils/pip.py:88-105` (the lockstep check), `:52-85` (`install_flet_package`), `:66` (`package_spec = f"{name}=={flet.version.flet_version}"`), `:20-21` (no `pip` in the venv → return 1), `:74-75` (fallback to `uv pip install`); `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:22,26` (upstream's own extra pins `flet-desktop==1.0.4` exactly).
- **What:** the check compares `flet_desktop.version.version` with `flet.version.flet_version` and, on any mismatch, installs `flet-desktop==<flet version>` **into the live venv** — with `pip` absent from this uv venv, that is `uv pip install` (pip.py:47), which does not touch `uv.lock`. Today the check passes (`flet_desktop/version.py:1` = `flet/version.py:19` = `1.0.4`), but `>=1.0.4` lets a `uv lock --upgrade` resolve flet-desktop to a newer release than the flet family while flet stays at 1.0.4. The next `flet run` would then silently rewrite the venv; the next `uv sync --frozen` would restore the locked version; the cycle repeats and the environment stops being reproducible from the lock — which is the ground truth the whole swarm depends on.
- **Evidence:** `importlib.util.find_spec('pip')` → `None`; `uv --version` → `uv 0.12.17`; `pip.py:66` builds `flet-desktop==1.0.4`; `flet-1.0.4.dist-info/METADATA:26` → `Requires-Dist: flet-desktop==1.0.4; extra == "desktop"`. Today: `flet_desktop/version.py:1` `version = "1.0.4"` == `flet/version.py:19` `flet_version = "1.0.4"`.
- **Fix / opportunity:** pin the dev group exactly — `flet-desktop==1.0.4` — matching upstream's own extra and the house "floor in pyproject, exact in uv.lock" reading of D-004 (`docs/decisions.md:15`). This is a dev-set change, so under D-003 (`docs/decisions.md:12`) it needs owner sign-off; the flet-cli report already proposes pinning the whole family exactly, and this is the flet-desktop half of that proposal.
- **Risk if ignored:** a routine `uv lock --upgrade` can leave the developer's venv silently diverging from the lock, and the divergence is invisible to `uv sync --frozen` (which repairs it) and to CI (which never runs `flet run`).

### F4 · P3 · CI installs `flet-desktop` on every job and never uses it

- **Where:** `.github/workflows/app.yml:49` (quality), `:149` (apk), `:203` (aab) — all `uv sync --frozen --group dev`; `uv.lock:597,615`; `flet_cli/commands/build_base.py:2566-2576` (the shipped set is `project.dependencies` + `tool.flet.<platform>.dependencies` — the dev group is never consulted).
- **What:** the three CI jobs pull a 13.5 KB wheel plus three modules that nothing in the workflow calls; `flet build apk/aab` does not touch the desktop client (grep over `flet_cli/` finds `flet_desktop` only in `commands/run.py`, `commands/pack.py`, `__pyinstaller/`), and no CI job runs `flet run`.
- **Evidence:** `uv.lock:249` — the wheel is 13,519 bytes; its deps (`flet`, `rich`) are already in the lock via `flet-cli`; `grep -rn "flet_desktop" .venv/Lib/site-packages/flet_cli/` → `commands/pack.py:220,393,395,611`, `commands/run.py:223,232,397,611`, `__pyinstaller/utils.py:8`, `__pyinstaller/hook-flet.py:17`, `__pyinstaller/rthooks/pyi_rth_localhost_fletd.py:14,15,31` — no `build_base.py` hit.
- **Fix / opportunity:** optional and low-value — `uv sync --frozen --group dev --no-install-package flet-desktop` in the three CI steps. **Do not** move `flet-desktop` out of the dev group: the desktop dev loop needs it. The honest cost of leaving it is ~13 KB.
- **Risk if ignored:** negligible. The one real hazard it would create is the F3 auto-reinstall firing in CI, which it cannot (CI never runs `flet run`).

### F5 · P3 · The client download carries no integrity check, and the only app-side lever cannot add one

- **Where:** `.venv/Lib/site-packages/flet_desktop/__init__.py:309-331` (`__download_flet_client`: `:324-325` builds `https://github.com/flet-dev/flet/releases/download/v{ver}/{file}`, `:326` allows `FLET_CLIENT_URL` to replace it wholesale, `:329` stages it in the temp dir), `:296-306` (`__download_with_progress` → `urllib.request.urlopen`, 8 KiB chunks, no hash), `:204-242` (the SHA-256 fingerprint exists but applies **only to bundled archives**, i.e. `flet pack` output).
- **What:** the binary that executes on the developer's host is fetched over TLS from a GitHub release with no checksum; a replaced release asset runs unverified. The package exposes no checksum hook — `FLET_CLIENT_URL` can only point somewhere else, not pin a hash.
- **Evidence:** `hashlib` is imported at `__init__.py:6` but used only inside `__get_archive_fingerprint` (`:235-239`), which is reached only for a bundled archive (`:351-353`). The network path at `:362-363` goes straight to the download.
- **Fix / opportunity:** no app-side fix is available in 1.0.4; upstream is the only place to add one (a published `<artifact>.sha256` verified the way the bundle path already does). Until then this is an accepted upstream risk — but it should be an *accepted* one, recorded next to the dev-loop decision.
- **Risk if ignored:** a compromised or moved release asset executes on the dev host; the blast radius is the developer's machine, not a shipped APK.

### F6 · P3 · The documentation of the local desktop workflow is missing from the working tree (uncommitted deletions)

- **Where:** `git status --short` → ` D docs/roadmap.md`, ` D docs/testing-findings.md`, ` D docs/release-runbook.md`, ` D docs/roadmap-synthesis.md`, ` D docs/compliance/*`, ` D LICENSES/*`, ` D src/LICENSES/*`, ` D THIRD-PARTY-SOURCES.md`, ` D check_elf_alignment.py`, ` D generate_third_party_sources.py` — all present in HEAD (`git ls-tree -r HEAD --name-only` lists them), all deleted from the working tree.
- **What:** the two documents that define the local desktop workflow — the dev loop (`testing-findings.md:6,32,40`) and the owner constraint (`roadmap.md:13,46,48`) — exist only in HEAD, not on disk. `README.md:12,15` still links to both, so the links are currently dead in the working tree. This audit cites them via `git show HEAD:…` for that reason.
- **Evidence:** `git status --short` output above; `git ls-tree -r HEAD --name-only | grep -E "roadmap|testing-findings"` → `docs/roadmap-synthesis.md`, `docs/roadmap.md`, `docs/testing-findings.md`.
- **Fix / opportunity:** not this report's to fix (read-only). Whoever owns the working tree should restore or intentionally re-land these files — the dev-loop decision that makes `flet-desktop` necessary lives in exactly these documents.
- **Risk if ignored:** the next agent (or the owner) reads the working tree, finds no documented dev loop, and may conclude that `flet-desktop` is unused and drop it from the dev group — which would break the only local UI loop the project has.

## Missed capabilities (dependency audits only)

- **Windows taskbar identity for the dev window** — `flet_desktop/__init__.py:538-555` (`__apply_taskbar_props`, called from `open_flet_view` at `:510`) → `win_taskbar.py:252-317` (`apply_relaunch_props_async`). It no-ops unless `FLET_APP_USER_MODEL_ID` is set (`__init__.py:548`), and `win_taskbar.py:279-281` bails out unless a relaunch command is derivable — so the ID alone is not enough unless it is an existing file path. **Integration point:** two env vars before `uv run flet run` (`FLET_APP_USER_MODEL_ID=ng.kiri.prootdistro` plus `FLET_APP_RELAUNCH_COMMAND="<path to flet.exe>"`). **Value:** the dev window shows "Proot Distro" with its own icon instead of "Flet" (the reason the module exists). **Cost:** two env vars, zero code. Low value, but it is the one branding lever flet-desktop offers.
- **`FLET_VIEW_PATH`** — `__init__.py:629-641` (Windows), `:657-668` (macOS), `:695-709` (Linux): point the dev loop at a locally built client instead of the cached one. This is precisely the O-9 lever ("the only way to see extension panes locally"). **Value:** would unlock the flet-terminal/flet-ads panes locally. **Cost:** requires a local `flet build`, which the owner forbids (`roadmap.md:13,148`), so it is off the table today. Recorded so the owner knows the exact one-liner if O-9 ever flips.
- **`FLET_CLIENT_URL`** — `__init__.py:326`: the only lever over the client source. **Value:** could point at an internal mirror. **Cost:** it cannot add integrity (F5), so it trades one risk for another.
- **`open_flet_view_async`** — `__init__.py:514-535`: already exercised by the in-process path (`flet/app.py:306`) when `src/main.py` is run directly. Nothing to adopt.
- **Not a capability — do not "optimize" with it:** `desktop_flavor` / `FLET_DESKTOP_FLAVOR` (`__init__.py:61-96`) is **inert on Windows and macOS**. The artifact name is fixed per OS (`:156-159` returns `flet-windows.zip` / `flet-macos.tar.gz`); the flavor only enters the *Linux* file name (`:161-166`) and the cache-directory name (`:186-190`). Verified live: `get_artifact_filename()` returns `flet-windows.zip` with and without `FLET_DESKTOP_FLAVOR=light`. Setting `[tool.flet].desktop_flavor = "light"` would therefore **not** shrink the 97 MB Windows download — it would only create a second, duplicate cache directory that re-downloads the same archive.

## Verified-good list

- **The dependency is really installed and importable:** `.venv/Lib/site-packages/flet_desktop/{__init__.py,version.py,win_taskbar.py}` (725 / 1 / 317 lines) + `flet_desktop-1.0.4.dist-info/`; `import flet_desktop` succeeds and `flet_desktop.version.version` = `1.0.4`.
- **The flet family is in lockstep today:** `flet 1.0.4`, `flet-ads 1.0.4`, `flet-cli 1.0.4`, `flet-desktop 1.0.4`, `flet-platform-assets 1.0.4`, `flet-terminal 0.4.0` (`uv.lock:220-262`; `docs/swarm/dependency-tree/installed.json`). `flet_desktop/version.py:1` == `flet/version.py:19` == `1.0.4`, so `ensure_flet_desktop_package_installed()` (`flet/utils/pip.py:88-105`) passes and no auto-reinstall fires. `flet-ads` also pins `flet==1.0.4` exactly (`flet_ads-1.0.4.dist-info/METADATA:14`), and `flet-desktop` pins `flet==1.0.4` (`flet_desktop-1.0.4.dist-info/METADATA:12`).
- **flet-desktop never ships into the APK:** dev group only (`pyproject.toml:77-84`); the packaged set is `project.dependencies` + `tool.flet.<platform>.dependencies` (`build_base.py:2566-2576`); `flet build apk` has no `flet_desktop` reference. On device the desktop branch is skipped anyway (`flet/app.py:302` requires `not is_embedded()`; `is_embedded()` = `FLET_PLATFORM is not None`, `flet/utils/platform_utils.py:70-77`).
- **The desktop client resolution and argv match the installed source:** live run produced `…\flet.exe tcp://localhost:<port> <pidfile> <assets_dir>` — `__init__.py:648` (Windows argv) plus `:719-720` (assets dir appended). The pid file is written by the client with its own PID (observed: `12580`).
- **The extension boundary holds in the app:** ads are gated to mobile (`src/components/banner_ad.py:50-57`, `src/services/ad_service.py:51-55`), so the desktop preview renders a zero-size placeholder instead of raising (live log: "AdService: non-mobile platform — consent flow skipped"); proot is explicitly unavailable off-device (`src/services/proot_service.py:21-22`).
- **The cache/extraction mechanics are sound:** the bundle dir does not exist on this host (`:48-58` → the download path is always taken); the fingerprint scheme is for bundled archives only (`:204-242`); extraction uses `flet.utils.safe_zip_extractall` / `safe_tar_extractall` (`:375-380`, path-traversal safe); the cache is installed by atomic rename with a lost-race fallback (`:382-390`); stale *fingerprinted* siblings are GC'd after 30 days (`:245-293`).
- **The stale-client warning exists:** `__init__.py:424-440`, called at `:627` / `:655` / `:693` — if a `build/windows` client ever shadows the cached one (only possible if the owner runs a local `flet build`, which the rule forbids), `flet run` says so loudly.
- **CI never needs the desktop client:** `app.yml` only runs `flet build apk/aab`; the desktop client path is not reachable from `build_base.py`.
- **No `[tool.flet].desktop_flavor` key** — correct, it would be inert on Windows/macOS (see Missed capabilities).

## Unverified

- **Whether the orphaned client window self-exits when the app server dies.** The function-level failure is proven (F1) and the client demonstrably outlives a killed CLI, but my harness could not deliver a real console Ctrl+C to the CLI (the probe process had no attached console, so `CTRL_C_EVENT` was never delivered and the CLI had to be force-killed). The user-visible "the window stays open" is therefore inferred from the proven code path, not observed through an interactive Ctrl+C.
- **Whether the upstream project has already fixed the SIGKILL bug.** PyPI JSON (checked 2026-10-20) shows 1.0.4 as the latest release; I did not inspect the flet-dev/flet issue tracker.
- **The macOS and Linux branches** of `__locate_and_unpack_flet_view` (`__init__.py:650-715`), the Linux identity args (`:443-487`) and the `win_taskbar` ctypes calls were read but not executed on this Windows host.
- **The `flet pack` path** (the other flet-desktop consumer) is not exercised by this repo; `flet_cli/commands/pack.py:220,393-395,611` was read only.
- **That the prebuilt client contains no third-party extension Dart** was not re-verified by inspecting the binary; the evidence used is the repo's own documents (`testing-findings.md:30-36`) plus the file listing of the cached client (no flet-terminal/flet-ads plugin DLLs).
- **The `.flet/storage/{data,cache,temp}` directories** created by my probe run are git-ignored (`.gitignore:13`, `.flet/.gitignore` = `*`) and were already present before this audit.
