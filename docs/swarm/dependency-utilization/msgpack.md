# msgpack (transitive, 1.2.3 in the lock / 1.1.2 on Android) — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `docs/dependency-studies/msgpack.md`; `docs/reference/dep-flet-runtime-utils.md`; `docs/decisions.md` (D-004); `docs/roadmap.md` (git HEAD — deleted from the worktree, read via `git show`); `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `src/screens/views.py`; `src/core/posixdb.py`; `src/app_controller.py`; `src/screens/terminal_view.py`; `.venv/Lib/site-packages/flet/messaging/`; `.venv/Lib/site-packages/flet/utils/pip.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/msgpack/`; `.venv/Lib/site-packages/msgpack-1.2.3.dist-info/`; `serious_python` 5.0.0 (pinned by the flet build template `pubspec.yaml:14`) · **Date:** 2026-10-20

## What it does / how the app uses it

msgpack is **not** a dependency of this app. It is transitive: `flet` requires it (`Requires-Dist: msgpack>=1.1.0` — `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:17`) and `pyproject.toml:9-15` declares no msgpack line at all. The lock resolves it to **1.2.3** (`uv.lock:443-445`), and the installed tree is 1.2.3 with the C extension (`msgpack/_cmsgpack.cp314-win_amd64.pyd`; live check `msgpack.Packer.__module__ == 'msgpack._cmsgpack'`, `msgpack.version == (1, 2, 3)`).

The app itself never imports msgpack. `grep -rn "import msgpack\|from msgpack\|MSGPACK_PUREPYTHON" src/ tests/ build_flet_proot_wheel.py` → **no output**. The single occurrence in app code is a *name in the third-party license list*: `"msgpack",` at `src/screens/views.py:31`, consumed by `_py_entries()` at `src/screens/views.py:600-606` (runtime `importlib.metadata` lookup). Flet uses msgpack for the whole Python↔Dart control protocol (`.venv/Lib/site-packages/flet/messaging/flet_dart_bridge_server.py:129-131` and `:229-233`; `flet_socket_server.py:287` and `:438-442`; `pyodide_connection.py:92` and `:206-210`; encoder `messaging/protocol.py:26-215`, ext decoder `:218-228`).

### Answer to the assignment question: **the lock is NOT a build break. It is not P0.**

The Android build **never reads `uv.lock`**. The APK's Python site-packages are produced by `serious_python`'s `package` step, which runs `pip install --target …` against the **requirement strings in `pyproject.toml`**, with `--only-binary :all:` and `--extra-index-url https://pypi.flet.dev`. The Android resolution therefore picks **msgpack 1.1.2** independently of the desktop lock's 1.2.3 — exactly the split `docs/dependency-studies/msgpack.md` §1.2 rule 2 predicts. The "resolves 1.1.x separately" hypothesis is **CONFIRMED**; the "fails" hypothesis is **REFUTED**.

Proof chain (all commands reproducible):

1. `flet_cli` contains **zero** references to a lockfile or to uv — the build tool cannot be consulting `uv.lock`:
   ```
   $ grep -rn "uv\.lock\|uv sync\|uv pip\|astral" .venv/Lib/site-packages/flet_cli/ --include=*.py
   (no output)
   ```
2. `flet build apk` hands `serious_python` the pyproject requirements, not a lock (`flet_cli/commands/build_base.py:2563-2619`): `toml_dependencies` comes from `get_project_dependencies(self.get_pyproject("project.dependencies"))` (`:2566-2570`) plus `tool.flet.android.dependencies` (`:2572-2576`), and each is passed as `-r <requirement>` (`:2605-2606`). The command itself is `serious_python:main package` (`:2537-2546`).
3. `serious_python` 5.0.0 resolves those requirements with pip, per ABI, against PyPI **plus** the Forge index: `bin/package_command.dart:18` (`const mobilePyPiUrl = "https://pypi.flet.dev"`), `:288` (`extraPyPiIndexes = [mobilePyPiUrl]`), `:459` (`--only-binary :all:`), `:469-471` (`--extra-index-url`), `:473-482` (`python -m pip install --upgrade … --target sitePackagesDir … requirements`). The Android wheel tag is injected by `bin/sitecustomize.dart:44-63` (`platform.system()` → `Android`, `sysconfig.get_platform()` → `android-24-arm64_v8a`, `platform.android_ver()` → api_level 24), with the ABI map at `bin/package_command.dart:69-71`.
4. `uv.lock` is only used for the **host** environment: CI runs `uv sync --frozen --group dev` (`.github/workflows/app.yml:149`) and then `uv run flet build apk` (`:159-161`). The host venv is never copied into the APK — `flet_cli` copies the Flutter project and assets (`build_base.py:3275`, `:3292`), and the Python payload comes from `SERIOUS_PYTHON_SITE_PACKAGES`/`SERIOUS_PYTHON_APP` (`build_base.py:2621-2629`).
5. Empirically, the Android resolve of **the project's full runtime dependency set** lands on 1.1.2:
   ```
   $ printf 'flet>=1.0.4\nflet-ads>=1.0.4\nhttpx>=0.28.1\nflet-terminal>=0.4.0\nproot-distro>=5.10.0\n' > req-full.txt
   $ uv pip compile --python-version 3.14 --python-platform aarch64-linux-android \
       --extra-index-url https://pypi.flet.dev/ req-full.txt
   ...
   msgpack==1.1.2
       # via flet
   ```
   The same command **without** the Android platform/extra-index resolves `msgpack==1.2.3` (desktop). The split is exactly as documented.
6. Real pip (the resolver `serious_python` actually invokes) with the same flags `serious_python` uses:
   ```
   $ pip download --only-binary :all: --platform android_24_arm64_v8a --python-version 3.14 \
       --implementation cp --abi cp314 --extra-index-url https://pypi.flet.dev/ msgpack
   Downloading msgpack-1.1.2-1-cp314-cp314-android_24_arm64_v8a.whl (72 kB)
   $ … --platform android_24_x86_64 …
   Downloading msgpack-1.1.2-1-cp314-cp314-android_24_x86_64.whl (77 kB)
   ```
   Both ABIs the app targets (`pyproject.toml:49` — `target_arch = ["arm64-v8a", "x86_64"]`) resolve. The downloaded wheels contain the compiled extension (`msgpack/_cmsgpack.cpython-314-aarch64-linux-android.so`, 156 552 B; `…-x86_64-linux-android.so`, 158 936 B), so the on-device path is the C extension, not the pure-Python fallback.
7. Wheel availability confirms the study's claim, now against the live index: `https://pypi.flet.dev/msgpack/` lists **only 1.1.0 and 1.1.2** (37 files) — no 1.2.x at all. For cp314 it ships `android_24_arm64_v8a`, `android_24_armeabi_v7a`, `android_24_x86_64` at 1.1.2. PyPI's own 1.1.2 release has no Android wheels either; the Forge rebuild is the only source of them.

## Findings

### F1 · P2 · No CI step proves the Android resolution; one stray pin breaks the APK build with an opaque error

- **Where:** `.github/workflows/app.yml:40-108` (the `quality` job — no Android resolve step); `pyproject.toml:9-15`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2563-2619`; `serious_python` 5.0.0 `bin/package_command.dart:448-482`.
- **What:** the "never pin msgpack ≥1.2.0" rule is currently enforced only by convention — no test, no CI job, no pre-commit hook. The roadmap explicitly asks for the guard and it is not there: `docs/roadmap.md` (git HEAD) `:94` — *"CI gains the **Android compile proof** (`uv pip compile --python-platform aarch64-linux-android --extra-index-url https://pypi.flet.dev/`)"* — and the M5 quality-job contents list (`:112`) repeats *"Android compile proof"* as required content. The `quality` job in `app.yml:40-108` runs ruff, the Flet API guard, the version-identity script and pytest — **no Android resolve**. If anyone later adds `msgpack>=1.2.0` to `pyproject.toml` (or bumps `flet` to a release that raises its msgpack floor), the failure surfaces *inside* `flet build apk`, in `serious_python`'s pip step, long after the cheap `uv sync` — and the error text does not name the Android ceiling.
- **Evidence:** counterfactual, both resolvers:
  ```
  $ printf 'flet>=1.0.4\nmsgpack>=1.2.0\n' > req-pinned.txt
  $ uv pip compile --python-version 3.14 --python-platform aarch64-linux-android \
      --extra-index-url https://pypi.flet.dev/ req-pinned.txt
  error: No solution found when resolving dependencies
    cause: Because only msgpack<=1.1.2 is available and you require msgpack>=1.2.0,
           we can conclude that your requirements are unsatisfiable.
  exit=1

  $ pip download --only-binary :all: --platform android_24_arm64_v8a --python-version 3.14 \
      --implementation cp --abi cp314 --extra-index-url https://pypi.flet.dev/ "msgpack>=1.2.0"
  ERROR: Could not find a version that satisfies the requirement msgpack>=1.2.0 (from versions: 1.1.2)
  exit=1
  ```
  Today, without the pin, the same command exits 0 with `msgpack==1.1.2` (see the proof chain above).
- **Fix / opportunity (minimal):** add one step to the `quality` job in `.github/workflows/app.yml` (before `uv sync`, or as its own step) that fails the build if the Android resolution changes:
  ```yaml
  - name: Android compile proof (msgpack must stay on the Forge 1.1.x wheel)
    run: |
      uv pip compile --quiet --python-version 3.14 \
        --python-platform aarch64-linux-android \
        --extra-index-url https://pypi.flet.dev/ \
        pyproject.toml --output-file android-req.txt
      grep -q '^msgpack==1\.1\.' android-req.txt
  ```
  This exact invocation was run against this repo's `pyproject.toml` during the audit and exits 0 with `flet==1.0.4` and `msgpack==1.1.2` in the output — `uv pip compile` reads `[project.dependencies]` straight from the TOML. Repeat with `--python-platform aarch64-linux-android` plus the x86_64 ABI if `target_arch` ever grows.
- **Risk if ignored:** the only thing standing between a routine dependency bump and a broken release build is a convention recorded in three markdown files. The failure mode is a release-blocking APK build error attributed to `serious_python`, not to the pin that caused it.
- **Explicitly NOT the fix:** do **not** add `msgpack` to `pyproject.toml`, do **not** edit `uv.lock`, and do **not** pin `msgpack<1.2` anywhere. A floor or ceiling in `pyproject.toml` would itself break the Android resolve (F1 evidence) and would put msgpack into our direct dependency set, which D-003 freezes.

### F2 · P3 · The `uv.lock` entry must stay "wrong" — the lock is a desktop lock, and it is not the Android contract

- **Where:** `uv.lock:443-445` (`version = "1.2.3"`, `source = { registry = "https://pypi.org/simple" }`); `uv.lock:447-493` (wheels: macOS/Linux/Windows/Emscripten only — no Android); `docs/decisions.md:16` (D-004: *"floors in pyproject, exact in `uv.lock`, `uv sync --frozen` in CI"*); `docs/dependency-studies/msgpack.md:55-59` (rule 2: keep it floating so the desktop resolver takes 1.2.3 while the Android resolver settles on 1.1.2).
- **What:** `uv.lock` holds a single, marker-free msgpack version for every platform (`grep -c "resolution-markers" uv.lock` → `0`), and it is a desktop-platform artifact. A reviewer (or an agent) reading `uv.lock` alone sees "msgpack 1.2.3" and the Android wheel table in the same file shows no Android wheel — which looks like a contradiction and invites a wrong "fix" (pin msgpack down in the lock, or add an `android` marker fork that `uv` would then have to honour, which the Android build ignores anyway). The lock is **not** wrong; it is out of scope for the APK. `uv.lock` also demonstrably does not describe the APK: the Android resolve picks `flet-terminal==0.4.2` while the lock and the installed tree carry `0.4.0` (`uv.lock:265`, `.venv/Lib/site-packages/flet_terminal-0.4.0.dist-info/METADATA:3`).
- **Evidence:** refs above; the msgpack 1.2.3 wheel list (`uv.lock:447-494`) contains only `macosx_*`, `manylinux*`, `musllinux*`, `win*` and `pyemscripten*` wheels — **no `android_*` tag for msgpack**. (The lock does contain Android wheels for other packages — `charset_normalizer` at `uv.lock:67-68`, `markupsafe` at `:361-362` and `:396-397` — so "Android wheels exist" is package-specific, not a property of the lock format. msgpack is one of the packages where PyPI ships none, and the Forge rebuild at `pypi.flet.dev` is the only source of its Android wheels: PyPI's own msgpack 1.1.2 release lists only `macosx_*`/`manylinux*`/`musllinux*`/`win*` files.)
- **Fix / opportunity:** no change to the lock. Record the reasoning where a future reader will look — the natural home is the `msgpack` study's §1.2 (which already predicts the split correctly) plus the CI step from F1, which turns the convention into a checked invariant. Optionally, add one sentence to `docs/decisions.md` D-004 stating that the lock is the **host/desktop** contract and the APK's Python payload is resolved by `serious_python`'s pip step — so future readers do not "fix" the lock.
- **Risk if ignored:** a well-intentioned pin of `msgpack<1.2` (or `==1.2.3`) in `pyproject.toml`/`uv.lock` turns a non-issue into a real APK build break — the counterfactual in F1.

### F3 · P3 · The app should **not** use msgpack directly — the study's §5 recommendation is declined, with three independent reasons

- **Where:** `docs/dependency-studies/msgpack.md:259-287` (§5 "Fullest utilization — should OUR app use msgpack directly?"); `src/screens/views.py:31` (the only app mention); `src/core/posixdb.py` (no persistence); `src/app_controller.py:100`, `:115-129`, `:248-258` (settings via flet's mounted `prefs` service); `src/screens/terminal_view.py:85` (`json.loads(e.data)` — flet-terminal's own payload); `docs/decisions.md:7` (D-001: wrap upstream `proot-distro`, never fork); `docs/decisions.md:9` (D-003: frozen dependency set).
- **What:** the study argues for msgpack as a local record codec. There is no app-owned record store for it to serve: the container metadata format is owned by upstream `proot-distro` (JSON manifests under the proot-distro home — consuming it as-is is D-001; re-encoding it would fork the upstream contract), the terminal payloads are flet-terminal's own JSON events (`src/screens/terminal_view.py:85`), and the app's own persisted state is flet's key-value `prefs` service (`src/app_controller.py:100` — `mounted.get("prefs")`), not a file we format. Adopting msgpack directly would also (a) add a package to a dependency set frozen by D-003, and (b) make our own code depend on a package that resolves to **two different versions** across our own build targets (1.1.2 on Android, 1.2.3 on desktop) — a version-skew obligation we would be taking on for zero measured benefit.
- **Evidence:** refs above; `grep -rn "import msgpack\|from msgpack" src/ tests/` → no output. Flet itself never touches msgpack's datetime support either — datetimes cross the wire as ext code 1 ISO strings (`flet/messaging/protocol.py:206`), not msgpack `Timestamp`, so there is no app-side format to align with.
- **Fix / opportunity:** none — keep msgpack purely transitive. If the owner later wants binary local records, the correct shape (per the study §5.3) is one `core/codec.py` facade behind `services/proot_service.py`, using only the API surface proven identical across 1.1.2 and 1.2.3 (F5), with a leading format-version byte and atomic file replace. That is a future milestone's call, not this audit's.
- **Risk if ignored:** low today, but a "let's use msgpack for our records" impulse would add a package to a frozen dependency set and a two-version compatibility obligation to a codebase that currently has neither.

### F4 · P3 · The shipped APK's in-app license list will say msgpack 1.1.2, while the repo's dependency docs say 1.2.3

- **Where:** `src/screens/views.py:31`, `:565-573` (`_dist_license`), `:600-606` (`_py_entries`); `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2563-2619`; `serious_python` 5.0.0 `bin/package_command.dart:91-110` (cleanup globs).
- **What:** the licenses screen reads the version from the **installed** distribution metadata at runtime. On a device build that metadata says 1.1.2 (the Forge wheel), while `docs/swarm/dependency-tree/uv-tree.txt:13` and `uv.lock:444` say 1.2.3. That is honest reporting of what actually ships, not a bug — but it is a visible difference between the artifact and the repo's own inventory, and a reviewer comparing the two would flag it. The `.dist-info` directory survives the APK cleanup pass (`serious_python` junk globs are `**.c`, `**.h`, `**.cpp`, `**.hpp`, `**.typed`, `**.pyi`, `**.pxd`, `**.pyx`, `**.a`, `**.pdb`, `__pycache__`, `**.exe`, `**.dll`, `bin` — `package_command.dart:91-110`), so the lookup succeeds on device and the wheel's own `msgpack-1.1.2.dist-info/METADATA` (verified present inside the downloaded Android wheel) is what gets read.
- **Evidence:** the downloaded Android wheel contains `msgpack-1.1.2.dist-info/METADATA` and `licenses/COPYING`; the cleanup glob list excludes `*.dist-info`.
- **Fix / opportunity:** none required for correctness. If the owner wants the repo and the artifact to agree, the cheap option is to note the Android/desktop msgpack split once in the release notes rather than freezing the lock (which F1 shows would break the build). `generate_third_party_sources.py` (git HEAD) already lists `msgpack` with license and upstream URL but **no version**, so `THIRD-PARTY-SOURCES.md` is unaffected.
- **Risk if ignored:** cosmetic inconsistency; a reviewer may re-open the "is 1.2.3 shipping?" question every release.

### F5 · P3 · msgpack 1.1.2 ↔ 1.2.3 API parity is now verified for the whole study "safe subset" (closes the study's open UNVERIFIED)

- **Where:** `.venv/Lib/site-packages/msgpack/fallback.py` (1.2.3, installed) vs the msgpack 1.1.2 sdist from PyPI (`https://files.pythonhosted.org/packages/4d/f2/bfb55a6236ed8725a96b0aa3acbd0ec17588e6a2c3b62a93eb513ed8783f/msgpack-1.1.2.tar.gz`); `docs/dependency-studies/msgpack.md:60`, `:277`, `:322` (the study marks 1.1.x parity as unverified).
- **What:** the study's §5.3 "safe subset" is safe in fact, not by assumption. AST comparison of the two `fallback.py` sources: `Packer.__init__` has **identical** argument names and identical defaults in 1.1.2 and 1.2.3 (`default`, `use_single_float=False`, `autoreset=True`, `use_bin_type=True`, `strict_types=False`, `datetime=False`, `unicode_errors=None`, `buf_size=None`); `Unpacker.__init__` likewise (`file_like`, `read_size=0`, `use_list=True`, `raw=False`, `timestamp=0`, `strict_map_key=True`, `object_hook`, `object_pairs_hook`, `list_hook`, `unicode_errors`, `max_buffer_size=100*1024*1024`, `ext_hook=ExtType`, `max_str_len/max_bin_len/max_array_len/max_map_len/max_ext_len=-1`). `exceptions.py` is byte-identical between the two versions (1 081 B each). `ext.py` differs only in size (5 726 B vs 6 428 B); the **public API is identical** — `ExtType.__new__` plus `Timestamp`'s 13 methods (`__init__`, `__repr__`, `__eq__`, `__ne__`, `__hash__`, `from_bytes`, `to_bytes`, `from_unix`, `to_unix`, `from_unix_nano`, `to_unix_nano`, `to_datetime`, `from_datetime`). `__init__.py` differs only in `version`/`__version__`; `pack/packb/unpack/unpackb` and the four aliases are character-for-character the same, including the `MSGPACK_PUREPYTHON` / `_cmsgpack` / `fallback` selection block.
- **Evidence:** AST extraction run over both files (argument lists and default values printed and compared: `SAME ARGS: True`, `SAME DEFAULTS: True` for both `Packer` and `Unpacker`); `exceptions.py identical: True`; `ext.py` class/method sets compared per class.
- **Fix / opportunity:** none required. The study's §5.3 rule 1 may be relaxed from "unverified parity" to "verified parity" for the listed subset — a documentation improvement the owner can make at leisure.
- **Risk if ignored:** only that the study stays more conservative than the evidence requires. (Note: this parity is between the *fallback* implementations; whether the two C extensions behave identically remains unverified — the C sources are not shipped in the wheels.)

## Missed capabilities (dependency audits only)

The app uses **none** of msgpack's API directly, and F3 argues that is the right call. For completeness, here is what is available if the owner ever reverses that decision, with the cost of each — all of it verified against the installed 1.2.3 source:

- **`packb` / `unpackb` with `default=` / `object_hook=`** · API: `msgpack/__init__.py:20-55` (one-shot wrappers), `fallback.py:673-694` (Packer options), `fallback.py:237-328` (Unpacker options) · Integration point: a new `core/codec.py` facade called only from `services/proot_service.py` · Value: compact binary records for container metadata / install-stage checkpoints · Cost: ~1 file, plus the 1.1.2↔1.2.3 parity obligation (F5 says the subset is identical) and the D-003 dependency-set question. **Currently declined** (F3) — no app-owned store to serve.
- **`Unpacker` streaming with `feed()` / iteration** · API: `fallback.py:329-622` (`feed`, `__next__`, `read_array_header`, `read_map_header`, `skip`, `tell`) · Value: multi-record files without the one-shot `ExtraData` failure · Cost: more code than the one-shot form for no current workload.
- **`max_buffer_size` / `max_map_len` caps on untrusted input** · API: `fallback.py:283-294`, `:193-210` · Value: bounds memory on hostile input · Cost: one keyword. **Not applicable today**: the only msgpack consumer is flet's own socket/dart-bridge transport, whose peer is the Dart client we ship (`flet/messaging/flet_dart_bridge_server.py:129-137` catches broad `Exception` and drops malformed frames rather than crashing).
- **`ExtType` with an app-owned code registry** · API: `msgpack/ext.py:8-18` (code 0–127, `bytes` payload) · Value: typed binary envelopes · Cost: a registry to maintain, and the study's §5.3 rule 5 warns against colliding with flet's ext codes 1–4. **Declined.**
- **`Timestamp` / `Packer(datetime=True)`** · API: `msgpack/ext.py:21-184`, `fallback.py:806-817` · Value: compact datetime encoding · Cost: flet's protocol deliberately does *not* use it (it sends ISO strings as ext code 1 — `flet/messaging/protocol.py:206`), so using it in our own records would create a second, divergent convention. **Declined.**
- **`MSGPACK_PUREPYTHON` as a diagnostics lever** · API: `msgpack/__init__.py:11-17` · Value: proves whether the C extension loaded on device · Cost: zero. **Worth keeping as a dev-only probe** — the on-device fallback is silent (`__init__.py:11-17` catches `ImportError` and falls back with no log line), so a sluggish session has no other explanation; `msgpack.Packer.__module__` is the one-line check.

## Verified-good list

- **The lock is not the Android contract, and the Android build does not fail.** Proven end-to-end above (flet_cli has no uv/lock references; `serious_python` resolves from pyproject requirements; Android resolve → `msgpack==1.1.2`; real pip → `msgpack-1.1.2-1-cp314-cp314-android_24_arm64_v8a.whl`). Nothing in `pyproject.toml` pins msgpack, so no change is needed and no P0 applies.
- The **desktop** resolve is also unchanged: `uv pip compile --python-version 3.14 req.txt` → `msgpack==1.2.3`; the installed tree matches the lock (`msgpack/__init__.py:7-8`; `msgpack-1.2.3.dist-info/METADATA:3`).
- `pyproject.toml` contains **no** msgpack line and no msgpack constraint of any kind (`grep -n "msgpack" pyproject.toml` → no output) — the study's rule 1 holds.
- The **live Forge index** matches the study: `https://pypi.flet.dev/msgpack/` serves only 1.1.0 and 1.1.2; cp314 Android wheels exist for `arm64_v8a`, `armeabi_v7a` and `x86_64` — i.e. both ABIs this app targets (`pyproject.toml:49`).
- The Android wheels ship the **compiled extension** (`_cmsgpack.cpython-314-aarch64-linux-android.so` / `…-x86_64-linux-android.so`), so on-device packing runs the C path, not the pure-Python fallback (study §6 confirmed, not assumed).
- flet's msgpack floor is `>=1.1.0` with no upper cap (`flet-1.0.4.dist-info/METADATA:17`), and the latest flet on PyPI is still **1.0.4** with the same floor; the 1.1.0 dev pre-releases (`1.1.0.dev0`, `1.1.0.dev1`) also keep `msgpack>=1.1.0` — so the flet bump planned in D-010 does not raise the Android ceiling.
- `flet-ads` pins `flet==1.0.4` (`flet_ads-1.0.4.dist-info/METADATA:14`), which is what holds flet (and therefore the msgpack floor) stable in the Android resolve.
- **flet never re-installs msgpack at runtime.** The only auto-install path is `flet/utils/pip.py:52` (`install_flet_package`), whose callers are `pip.py:105` (`flet-desktop`), `:125` (`flet-web`) and `:145` (`flet-cli`) — msgpack is never a target. No runtime package mutation on device.
- The **app does not import msgpack** and does not manipulate it: `grep -rn "import msgpack\|from msgpack\|MSGPACK_PUREPYTHON" src/ tests/ build_flet_proot_wheel.py` → no output. The only app reference is the license-list name at `src/screens/views.py:31`.
- **msgpack is correctly NOT pruned** by `[tool.flet.cleanup]` — the only prune glob is `oauthlib/**` (`pyproject.toml:62-63`), matching the study's §6 note that msgpack must survive (it is load-bearing for every session).
- The study's core API claims spot-check clean against the installed source: version tuple (`msgpack/__init__.py:7-8`), C-extension/fallback selection block (`__init__.py:11-17`), one-shot functions and aliases (`__init__.py:20-55`), flet's send/receive call sites and framing (`flet/messaging/flet_dart_bridge_server.py:129-131`, `:225-233`; `flet_socket_server.py:287`, `:429-442`; `protocol.py:26-48`, `:190-215`, `:218-228`), and the drop-not-crash inbound error handling (`flet_dart_bridge_server.py:129-137`).
- The flet wire protocol is identical on both targets: flet ships as a pure-Python wheel (`flet-1.0.4-py3-none-any.whl`, `uv.lock:204`), so the *same* `packb([action, body], default=…)` code runs in the APK and on the desktop; only the msgpack wheel differs.

## Unverified

- **serious_python 6.0.0** (current pub.dev latest) was not audited — the flet build template pins `serious_python: 5.0.0` (`pubspec.yaml:14`), and 5.0.0 is what I read. If the template is ever bumped to 6.x, the pip-install mechanics must be re-checked. The template itself was downloaded from the release URL that `flet_cli` defaults to (`build_base.py:67-69`, `https://github.com/flet-dev/flet/releases/download/v1.0.4/flet-build-template.zip`).
- The **real APK was not built** in this audit (no Flutter/Android SDK run): the Android resolution is proven at the resolver level (uv + real pip + the actual requirement strings), and the wheel contents were inspected directly, but the assembled APK's site-packages were not listed. The claim "the APK contains msgpack 1.1.2" is therefore a resolver-level conclusion, not an on-device observation.
- Whether **any** other package in the Android resolve has an Android-wheel ceiling that is currently violated was out of scope (only msgpack was audited). The full resolve output above (`out-full-android.txt`) is the starting point for that sweep.
- The C-extension internals of msgpack (nesting limits, key interning, error-message parity with the fallback) remain unverified — no C source is installed in either wheel; only `unpackb`'s keyword list was introspected.
- `docs/roadmap.md`, `src/LICENSES/*`, `generate_third_party_sources.py` and `check_elf_alignment.py` are **deleted from the working tree** in this checkout (`git status --short` shows them as ` D`) but present in git HEAD; I read them with `git show HEAD:<path>` (read-only). If that deletion is not a harness artifact, those files are genuinely missing from the checkout and a separate audit should cover it — it is **not** part of the msgpack verdict.
- Behavior of the **Dart client** side of the wire protocol (msgpack-dart `^1.0.1` in the template's `pubspec.yaml:15`) was not audited; only the Python end was.
