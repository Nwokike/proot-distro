# colorama 0.4.6 — audit

**Verdict:** PERFECT
**Confidence:** high
**Scope:** `docs/dependency-studies/colorama.md`; `docs/dependency-studies/qrcode.md`; `docs/reference/dep-test-and-lint-stack.md`; `docs/reference/dep-flet-cli.md`; `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `src/` (all 30 `.py` files); `tests/test_imports_vs_deps.py`; `tests/check_flet_api.py`; `build_flet_proot_wheel.py`; `.venv/Lib/site-packages/colorama/` (all 6 modules); `.venv/Lib/site-packages/colorama-0.4.6.dist-info/METADATA`; `.venv/Lib/site-packages/_pytest/capture.py`; `.venv/Lib/site-packages/_pytest/_io/terminalwriter.py`; `.venv/Lib/site-packages/qrcode/console_scripts.py`; `.venv/Lib/site-packages/qrcode/__init__.py`; `.venv/Lib/site-packages/flet_cli/commands/run.py`; `.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA`; `.venv/Lib/site-packages/pytest-9.1.1.dist-info/METADATA`; `.venv/Lib/site-packages/qrcode-8.2.dist-info/METADATA`; `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA`; `.venv/Lib/site-packages/rich-*.dist-info/METADATA` · **Date:** 2026-10-20

## What it does / how the app uses it

**Plainly: colorama is dormant in this app. It is a Windows-only, dev-only, transitive dependency that never reaches the APK, is never imported by `src/`, and is not even installed in CI.**

- **Nothing in `src/` imports it.** `grep -rn "colorama" src/` → no output. The app's in-app license list (`src/screens/views.py:26-42`, `_PY_DISTS`) enumerates the 15 distributions that actually ship — colorama is correctly absent, and correctly so.
- **It never reaches the APK.** colorama is required by exactly two packages, both with the marker `sys_platform == 'win32'`: `pytest>=0.4` (`pytest-9.1.1.dist-info/METADATA:33`) and `qrcode` (`qrcode-8.2.dist-info/METADATA:29`). `qrcode` is in turn required only by `flet-cli` (`flet_cli-1.0.4.dist-info/METADATA:16`), which lives in the **dev** dependency group (`pyproject.toml:79`) and is a *host* tool, never a runtime dep. The `flet` runtime package itself does not require colorama (`flet-1.0.4.dist-info/METADATA:12-18` — only `flet-cli` under the `cli` extra, plus `oauthlib`/`httpx`/`repath`/`msgpack`). The APK's Python payload is resolved from the `pyproject.toml` runtime set, and the **Android** resolve contains **15 packages, none of them colorama** (proof chain below).
- **CI does not need Windows ANSI handling, because CI is not Windows.** All four jobs run on `ubuntu-latest` (`.github/workflows/app.yml:41`, `:112`, `:131`, `:185`). The `sys_platform == 'win32'` marker is therefore false on the CI runner, and colorama is **not installed in CI at all** — a Linux resolve of the full runtime+dev set contains no colorama (proof chain below).
- **The repo's own host tools emit no ANSI escapes**, so they do not need colorama on the Windows contributor's laptop either. `grep -rnE 'x1b|033|u001b' build_flet_proot_wheel.py tests/ src/` → only two false positives inside a numeric ad-unit id (`src/services/ad_service.py:29-30`, `"…/1033173712"`). `build_flet_proot_wheel.py`, `tests/check_flet_api.py` and (via `git show HEAD:`) `check_elf_alignment.py` / `generate_third_party_sources.py` print plain text.

### Proof chain (reproducible)

1. Only two dependents, both Windows-gated — `uv.lock:635` (inside the `pytest` block, header at `uv.lock:631`) and `uv.lock:713` (inside the `qrcode` block, header at `uv.lock:709`):
   ```
   $ grep -n 'name = "colorama", marker' uv.lock
   635:    { name = "colorama", marker = "sys_platform == 'win32'" },
   713:    { name = "colorama", marker = "sys_platform == 'win32'" },
   ```
   The colorama package block itself is `uv.lock:164-171` (`name = "colorama"` at `:165`, `version = "0.4.6"`, one pure-Python `py2.py3-none-any` wheel).
2. The **Android** resolve of the app's exact runtime requirement set (`pyproject.toml:9-15`) contains **no colorama**:
   ```
   $ printf 'flet>=1.0.4\nflet-ads>=1.0.4\nhttpx>=0.28.1\nflet-terminal>=0.4.0\nproot-distro>=5.10.0\n' > req-runtime.txt
   $ uv pip compile --python-version 3.14 --python-platform aarch64-linux-android \
       --extra-index-url https://pypi.flet.dev/ req-runtime.txt | grep -i 'colorama\|qrcode'
   (no output; 15 packages resolved)
   ```
   The 15 resolved names — `anyio, certifi, flet, flet-ads, flet-terminal, h11, httpcore, httpx, idna, msgpack, oauthlib, proot-distro, repath, six, typing-extensions` — are exactly the 15 in `src/screens/views.py:26-42`, which is the app's own in-app license list. colorama is not among them because it is not among them.
3. The **Linux** resolve of the full runtime **+ dev** set (what CI's `uv sync --frozen --group dev` installs, `.github/workflows/app.yml:49`, `:149`, `:203`) contains **no colorama**:
   ```
   $ uv pip compile --python-version 3.14 --python-platform x86_64-manylinux_2_28 req-dev.txt | grep -in colorama
   (no output)
   ```
   The **Windows** resolve of the same set does:
   ```
   $ uv pip compile --python-version 3.14 --python-platform x86_64-pc-windows-msvc req-dev.txt | grep -in -A2 colorama
   24:colorama==0.4.6
   25-    # via
   26-    #   pytest
   ```
   So colorama exists **only** on a Windows contributor's machine, **only** as a transitive of pytest (and of `qrcode` via `flet-cli`).
4. The **installed API** matches the study exactly (live `inspect.signature` against `.venv/Lib/site-packages/colorama/`):
   ```
   version 0.4.6
   init (autoreset=False, convert=None, strip=None, wrap=True)   # initialise.py:37
   just_fix_windows_console ()                                    # initialise.py:72
   deinit ()                                                      # initialise.py:65
   reinit ()                                                      # initialise.py:104
   colorama_text (*args, **kwargs)                                # initialise.py:96
   wrap_stream (stream, convert, strip, autoreset, wrap)          # initialise.py:111
   AnsiToWin32 (wrapped, convert=None, strip=None, autoreset=False)# ansitowin32.py:81
   exports ['AnsiToWin32','Back','Cursor','Fore','Style','ansi','ansitowin32',
            'colorama_text','deinit','init','initialise','just_fix_windows_console',
            'reinit','win32','winterm']                            # __init__.py:2-6
   ```
   `reset_all` at `initialise.py:32` and `_wipe_internal_state_for_tests` at `initialise.py:9`; `StreamWrapper` at `ansitowin32.py:16`; `AnsiToWin32` class at `ansitowin32.py:72`; `ansi.py` names `AnsiCodes`(`:25`) `AnsiCursor`(`:36`) `AnsiFore`(`:49`) `AnsiBack`(`:71`) `AnsiStyle`(`:93`) with the `Fore`/`Back`/`Style`/`Cursor` instances at `ansi.py:99-102`.

## Findings

### F1 · P3 · The study's pytest call-site claim is wrong: pytest 9.1.1 never calls `just_fix_windows_console()`

- **Where:** `docs/dependency-studies/colorama.md:36-40` (*"pytest's Windows terminal support path uses this shape rather than full `init` (**exact pytest call site unverified**)"*); `.venv/Lib/site-packages/_pytest/_io/terminalwriter.py:78-85`; `.venv/Lib/site-packages/_pytest/capture.py:68-80`, `:160`; `.venv/Lib/site-packages/colorama/initialise.py:72-93`.
- **What:** the study leaves pytest's call site unverified and hints at `just_fix_windows_console()`. The installed pytest 9.1.1 uses a **third** mechanism entirely: it does a bare `import colorama` at session start so colorama binds to the real stdio handles before capture begins, and it wraps the terminal writer's file through `colorama.AnsiToWin32(file).stream` rather than through `init()` or `just_fix_windows_console()`. `just_fix_windows_console()` has **zero callers** anywhere in the installed tree outside colorama's own test module.
- **Evidence:**
  ```
  $ grep -rn "just_fix_windows_console" .venv/Lib/site-packages/ --include="*.py" | grep -v "/colorama/"
  .venv/Lib/site-packages/\colorama\tests\initialise_test.py:11,131,132,162,172,179,183
  (only colorama's own tests; zero callers in pytest, qrcode, flet, flet-cli, click, rich)
  ```
  ```
  .venv/Lib/site-packages/_pytest/capture.py:76-80
      if sys.platform.startswith("win32"):
          try:
              import colorama  # noqa: F401
          except ImportError:
              pass

  .venv/Lib/site-packages/_pytest/_io/terminalwriter.py:78-85
          if hasattr(file, "isatty") and file.isatty() and sys.platform == "win32":
              try:
                  import colorama
              except ImportError:
                  pass
              else:
                  file = colorama.AnsiToWin32(file).stream
  ```
  Both are win32-gated, which is why CI (Linux) never touches colorama at all. `AnsiToWin32.__init__` (`ansitowin32.py:81-119`) is what actually enables Windows VT processing — `enable_vt_processing(fd)` (`ansitowin32.py:101`, defined at `winterm.py:178`) and `winapi_test()` (`ansitowin32.py:96`, defined at `win32.py:114`).
- **Fix / opportunity:** documentation only — the owner may correct `docs/dependency-studies/colorama.md:36-40` to name the two real pytest call sites, and `docs/reference/dep-test-and-lint-stack.md:27-28` (which says only *"pytest internals + Windows ANSI"*, already correct but vague). **No code change.** Nothing in this repo should ever call `just_fix_windows_console()` — it would be a monkeypatch of a third-party terminal setup, which the house architecture forbids (BRIEF rule 4).
- **Risk if ignored:** low. A future agent reading the study might "helpfully" add `colorama.just_fix_windows_console()` to a host tool, adding a `sys.stdout` mutation with no ANSI output to justify it. Documentation drift only; no user-visible impact.

### F2 · P3 · The study over-attributes colorama to `flet run`; the `flet run` QR path never touches it

- **Where:** `docs/dependency-studies/colorama.md:6-7` and `:69-71` (*"flet-cli `flet run` output. The device-connect QR + log output path formats through colorama-backed streams"*); `.venv/Lib/site-packages/flet_cli/commands/run.py:16`, `:671-677`; `.venv/Lib/site-packages/qrcode/__init__.py:1-11`; `.venv/Lib/site-packages/qrcode/console_scripts.py:19-23`; `.venv/Lib/site-packages/qrcode-8.2.dist-info/entry_points.txt:1-2`.
- **What:** the study says the colorama presence is explained by "`flet run` device-connect extras". That is **not** what happens. flet-cli's device-connect QR path uses the `qrcode` **library** API (`qrcode.QRCode()`), and `qrcode/__init__.py` imports only `qrcode.main` / `qrcode.constants` / `qrcode.image` — it never imports `console_scripts`, and never imports colorama. The **only** colorama call in the whole qrcode package is inside the standalone `qr` console script's module-level Windows guard, and the only entry point that reaches it is the `qr` executable. The repo never invokes `qr`.
- **Evidence:**
  ```
  .venv/Lib/site-packages/flet_cli/commands/run.py:16
  import qrcode
  .venv/Lib/site-packages/flet_cli/commands/run.py:671-677
          # print(qr_url)
          qr = qrcode.QRCode()
          qr.add_data(qr_url)
          qr.print_ascii(invert=True)
          # qr.print_tty()
          print("")
          print("Scan QR code above with Camera app.")
  ```
  ```
  .venv/Lib/site-packages/qrcode/console_scripts.py:19-23
  # The next block is added to get the terminal to display properly on MS platforms
  if sys.platform.startswith(("win", "cygwin")):  # pragma: no cover
      import colorama  # type: ignore

      colorama.init()
  ```
  ```
  .venv/Lib/site-packages/qrcode-8.2.dist-info/entry_points.txt:1-2
  [console_scripts]
  qr=qrcode.console_scripts:main
  ```
  ```
  $ grep -rn "\"qr\"\|'qr'\|qr\.exe\|console_scripts" .venv/Lib/site-packages/flet_cli/ --include="*.py"
  (no output — flet-cli never spawns the `qr` script)
  ```
- **Fix / opportunity:** documentation only — `docs/dependency-studies/colorama.md:6-7` and `:69-71` should attribute colorama to the **pytest** path and the **`qr` console script** path, and note that the `flet run` QR path is colorama-free. No code change; this is strictly a tightening of the "why is this in our lockfile" record.
- **Risk if ignored:** low. A reader who believes "`flet run` needs colorama" may treat colorama as a runtime concern and protect it in the APK-prune step, adding a false positive to the CI artifact checks.

### F3 · P3 · The study recommends a `test_imports_vs_deps.py` allow-list entry for colorama; the guard provably does not need one

- **Where:** `docs/dependency-studies/colorama.md:74-75` (*"The house `test_imports_vs_deps.py` guard should list it as an allowed transitive (pytest/flet-cli support) rather than a direct import"*); `tests/test_imports_vs_deps.py:46-59`; `src/screens/views.py:26-42`.
- **What:** the guard only fires on **imports found in `src/`**. It walks `src/**/*.py`, collects top-level module names via `ast` (`tests/test_imports_vs_deps.py:35-43`), skips stdlib and local packages, and asserts each remaining import maps to a declared dependency (`:52-59`). colorama is never imported from `src/` (grep: no output), so the guard never sees it and never needs an allow-list. The `providers` fallback at `:56` (`importlib.metadata.packages_distributions()`) would in any case map `colorama` to `pytest`/`qrcode`, neither of which is declared — but that path is only reached if `src/` imported colorama, which it does not.
- **Evidence:**
  ```
  $ grep -rn "colorama" src/ tests/ .github/ build_flet_proot_wheel.py pyproject.toml
  (no output)
  ```
  The guard's own module set (`tests/test_imports_vs_deps.py:52`) is `sorted((ROOT / "src").rglob("*.py"))` — `tests/` is out of scope for the import scan.
- **Fix / opportunity:** none in code. The owner may drop the recommendation at `docs/dependency-studies/colorama.md:74-75` or restate it as "no guard change is required — colorama is never imported from `src/`". **Do not** add colorama to `[project.dependencies]`: that would pull a Windows-only package into the Android resolve and violate D-003's frozen dependency set.
- **Risk if ignored:** very low. The only realistic harm is a contributor adding colorama to `pyproject.toml` to "satisfy the study" — which would put a package in the APK that is currently a zero-byte dev-only transitive.

### F4 · P3 · The APK/AAB prune check does not (and need not) list `colorama/` — but the reason is worth recording

- **Where:** `.github/workflows/app.yml:163-172` (APK prune check, regex `pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/` at `:168`); `.github/workflows/app.yml:275-288` (AAB prune check, same regex at `:282`); `pyproject.toml:62-63` (`[tool.flet.cleanup] package_files = ["oauthlib/**"]`).
- **What:** the two artifact guards look for dev-only trees inside the built APK/AAB. `colorama/` is not on the list — correctly, because the Android resolve (proof chain step 2) contains 15 packages and colorama is not one of them, so `colorama/` can never appear. Adding it to the regex would be harmless but misleading: it would imply colorama is a known APK-resident risk. The only thing `[tool.flet.cleanup]` prunes is `oauthlib/**` (`pyproject.toml:62-63`), which is correct — colorama is not in the payload, so there is nothing to prune.
- **Evidence:** the `unzip -l` prune regexes at `.github/workflows/app.yml:168` and `:282`; the Android resolve output in the proof chain; `src/screens/views.py:26-42` lists the 15 shipped dists and no colorama.
- **Fix / opportunity:** none. Record the reason in the release notes or the dependency study so a future contributor does not "harden" the prune regex with a package that cannot be there. If the owner prefers belt-and-braces, `colorama/` may be appended to both regexes at zero cost — but it is not a fix for anything.
- **Risk if ignored:** negligible.

## Missed capabilities (dependency audits only)

**None worth taking.** colorama is a terminal-cosmetics library, and every capability it offers is either (a) irrelevant to the artifact, or (b) already covered by a better-suited dependency that the app already ships:

- **`just_fix_windows_console()`** · API: `colorama/initialise.py:72-93` (enables Windows VT processing on `sys.stdout`/`sys.stderr` without touching autoreset/strip state) · Integration point: a host-side CLI (`build_flet_proot_wheel.py`, `check_elf_alignment.py`) · Value: renders ANSI in a Windows console · Cost: a `sys.stdout` mutation for output that does not exist (the repo's tools print plain text — grep evidence above) · **Declined.** This repo is an Android app; Windows is only a contributor's dev box, and the tools' output is ANSI-free.
- **`init()` / `colorama_text()` / `Fore`/`Back`/`Style`/`Cursor`** · API: `initialise.py:37`, `:96`; `ansi.py:99-102` · Value: colorized terminal text · Cost: an import + a global stdout wrapper · **Declined.** The app's own terminal is a Flet widget (flet-terminal), not a console; the in-app terminal renders ANSI through flet-terminal, not through a Python `print`. Nothing in `src/` prints to a console.
- **`AnsiToWin32` / `wrap_stream`** · API: `ansitowin32.py:72`, `:81`; `initialise.py:111` · Value: strip/convert ANSI on a legacy Windows console · **Declined** — same reason, plus the house ban on monkeypatching third-party terminal state.
- The correct owner for Windows console color in this stack is **`rich`**, not colorama: `flet-cli` already depends on it (`flet_cli-1.0.4.dist-info/METADATA:21`, `Requires-Dist: rich>=13.0.0`), and `rich` has **no** colorama dependency of its own (`rich-*.dist-info/METADATA:27-29`; `grep -rn "colorama" .venv/Lib/site-packages/rich/` → no output) — it handles the Windows console natively. CI additionally forces plain output with `FLET_CLI_NO_RICH_OUTPUT: "1"` (`.github/workflows/app.yml:31`).

## Verified-good list

- **colorama is not in the APK.** Android resolve of the runtime set = 15 packages, no colorama; the 15 match `src/screens/views.py:26-42` exactly. Its only two dependents are `sys_platform == 'win32'`-gated (`uv.lock:635`, `:713`) and `qrcode` is reached only through the dev-group `flet-cli` (`pyproject.toml:79`).
- **colorama is not installed in CI.** All four jobs are `ubuntu-latest` (`.github/workflows/app.yml:41`, `:112`, `:131`, `:185`); the Linux resolve of the full runtime+dev set contains no colorama.
- **`src/` has zero colorama references** — `grep -rn "colorama" src/ tests/ .github/ build_flet_proot_wheel.py pyproject.toml` → no output.
- **The in-app license list is correct.** `src/screens/views.py:26-42` lists exactly the 15 shipped dists; colorama is correctly absent, and `src/LICENSES/` needs no colorama entry (BSD-3-Clause, and it does not ship).
- **The third-party sources bundle is correct.** `generate_third_party_sources.py` (git HEAD) lists `proot-distro`, `flet`, `flet-ads`, `flet-terminal`, `httpx`, `httpcore`, `h11`, `anyio`, … — no colorama, matching the APK payload.
- **No `import colorama` in `click`** — `click/utils.py:297` is a docstring line ("Support colors on Windows if colorama is installed"), not code; click's `Requires-Dist` has no colorama.
- **No `import colorama` in `rich`** — verified by grep; rich is self-sufficient on Windows.
- **The study's API inventory is accurate.** Every signature it lists is present at the stated line in the installed 0.4.6: `init` (`initialise.py:37`), `deinit` (`:65`), `reinit` (`:104`), `just_fix_windows_console` (`:72`), `colorama_text` (`:96`), `wrap_stream` (`:111`), `reset_all` (`:32`), `_wipe_internal_state_for_tests` (`:9`), `StreamWrapper` (`ansitowin32.py:16`), `AnsiToWin32` (`:72`, ctor `:81`), and the `ansi.py` surface (`AnsiCodes`/`AnsiCursor`/`AnsiFore`/`AnsiBack`/`AnsiStyle` at `:25`/`:36`/`:49`/`:71`/`:93`; `Fore`/`Back`/`Style`/`Cursor` instances at `:99-102`) — confirmed by live `inspect.signature` and `dir()`. The study's "inventory only" hedges on `ansi.py`/`win32.py`/`winterm.py` can be promoted to verified.
- **`init()`'s "no-op passthrough on non-Windows" claim holds.** `AnsiToWin32.__init__` sets `on_windows = os.name == 'nt'` (`ansitowin32.py:91`) and `need_conversion = conversion_supported and not system_has_native_ansi` (`:103`), so `convert` is False off-Windows; `should_wrap()` (`:121-129`) then returns False unless autoreset was requested, and `wrap_stream` (`:111-117`) returns the raw stream. The claim was previously marked unverified in the study; it is now verified from source.
- **The colorama version in the lock matches the installed tree**: `uv.lock:165-166` (`colorama` 0.4.6, one `py2.py3-none-any` wheel) vs `colorama/__init__.py:6` (`__version__ = '0.4.6'`) and `colorama-0.4.6.dist-info/METADATA:2-5`.
- **The lock's colorama block is a pure-Python, platform-agnostic wheel** (`uv.lock:170` — `colorama-0.4.6-py2.py3-none-any.whl`), so it could be installed on Android if anything ever required it without a marker — nothing does, which is the actual protection.
- **The `test_imports_vs_deps.py` guard needs no change** for colorama (see F3): it scans `src/` only (`tests/test_imports_vs_deps.py:52`).

## Unverified

- **The real APK was not built in this audit** (no Flutter/Android SDK run). The "colorama is not in the APK" conclusion is a resolver-level proof (the exact `pyproject.toml` requirement strings resolved for `aarch64-linux-android` against `https://pypi.flet.dev`, matching the 15 names in `src/screens/views.py:26-42`), not an on-device `unzip -l` observation. The `serious_python` pip step's mechanics were taken from the msgpack audit's already-verified chain, not re-verified here.
- **`flet-proot==5.1.107.98`** (`pyproject.toml:52`, the native payload wheel built by `build_flet_proot_wheel.py`) was not dependency-resolved here; it is a local wheel with no Python dependency graph, but its metadata was not re-read in this audit.
- **The Windows contributor experience of pytest's colorama path was not observed** — the call sites are read from source (F1) but no run was done on a Windows console to confirm the rendered output. The mechanism (`AnsiToWin32` + `enable_vt_processing`, `winterm.py:178`) is verified from source only.
- **Whether a future `flet` release adds an unconditional colorama dependency** is out of scope; today's `flet-1.0.4.dist-info/METADATA:12-18` has none, and the flet 1.0.4 → later bump planned in D-010 was not re-checked for colorama.
- **`colorama/tests/`** (shipped inside the installed package) is colorama's own upstream test suite, not this repo's; it was not audited.
- `docs/roadmap.md`, `src/LICENSES/*`, `generate_third_party_sources.py` and `check_elf_alignment.py` are **deleted from the working tree** in this checkout (`git status --short` shows them as ` D`) but present in git HEAD; they were read with `git show HEAD:<path>` (read-only). If that deletion is not a harness artifact, a separate audit should cover it — it is not part of the colorama verdict.
