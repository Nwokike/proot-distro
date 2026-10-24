# binaryornot 0.4.4 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/binaryornot.md`; `docs/dependency-studies/chardet.md`; `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `build_flet_proot_wheel.py`; `tests/test_proot_surfaces.py`; `tests/test_ui_reactive.py`; all 23 `src/**/*.py` modules (grepped whole-tree for file-content, backup/restore, import/export, preview paths); `.venv/Lib/site-packages/binaryornot/{check.py,helpers.py}`; `.venv/Lib/site-packages/binaryornot-0.4.4.dist-info/{METADATA,RECORD}`; `.venv/Lib/site-packages/cookiecutter/generate.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/chardet-5.2.0.dist-info/METADATA` · **Date:** 2026-10-20

## What it does / how the app uses it

`binaryornot` 0.4.4 (BSD, pure Python) is a two-module, four-function binary-vs-text probe: `check.is_binary(filename)` and `helpers.get_starting_chunk(filename, length=1024)` / `helpers.is_binary_string(bytes_to_check)` / `helpers.print_as_hex(s)` (`.venv/Lib/site-packages/binaryornot/check.py:12,18`; `helpers.py:18,25,51`).

**The app does not use it. It has no legitimate on-device use, and the app is architecturally forbidden from importing it.**

- It is not a runtime dependency: `pyproject.toml:9-15` lists only `flet`, `flet-ads`, `httpx`, `flet-terminal`, `proot-distro`. It reaches the venv transitively and host-only: `flet-cli` (dev group, `pyproject.toml:77-84`) → `cookiecutter` (`uv.lock:179`) → `binaryornot` (`uv.lock:224`).
- `grep -rn "binaryornot\|is_binary\|is_binary_string\|get_starting_chunk\|print_as_hex" src/` → **zero hits** (exit 1).
- The app's own guard test forbids it: `tests/test_proot_surfaces.py:133-148` puts `"binaryornot"` in the `dev_only` set and asserts no file under `src/` imports it ("The build-host tree must never reach the app (licensing A4)").

Its **one live, legitimate exercise is on the build host**, and it is not ours to invoke directly: CI runs `uv run flet build apk` / `flet build aab` (`.github/workflows/app.yml:149,159` and `:203,213`, after `uv sync --frozen --group dev` at `:49`) → `flet_cli/commands/build_base.py:1893-1895` calls `cookiecutter.main.cookiecutter(...)` → `cookiecutter/generate.py:15` `from binaryornot.check import is_binary`, applied at `generate.py:221` (`if is_binary(infile):` → `shutil.copyfile` + `copymode`, `:222-224`) so binary Flutter-template assets are copied instead of being fed to Jinja2.

**There is no need for a binary-vs-text probe in the app.** Every file-content path is either byte-safe by construction or opaque:

| Path | Site | Binary-safe? |
|---|---|---|
| Brand icon | `src/components/brand_hero.py:28` `candidate.read_bytes()` → `ft.Image(src=bytes)` (`:35-36`) | Yes — bytes never decoded |
| Native `.so` staging | `src/core/proot_probe.py:97` `dst.write_bytes(src.read_bytes())` | Yes — bytes copied |
| Container size | `src/services/proot_service.py:175-181` `os.walk` + `stat().st_size` | Yes — file never opened |
| Backup / restore | `src/app_controller.py:342-368` → `src/services/proot_service.py:357-372` → upstream `proot_distro.commands.backup`/`restore` | Yes — opaque path handed to proot; the app never opens the tar |
| Container install | `src/services/proot_service.py:212-224` (image ref string) | Yes — upstream fetches and unpacks |
| Shell output | `src/services/session_manager.py:31,38-42` (`deque[bytes]`), `src/screens/terminal_view.py:105-108` | Yes — raw bytes into the flet-terminal emulator |
| Update feed | `src/services/update_service.py:5-6` ("nothing is downloaded in-app"), `:73-76` (JSON over https) | Yes — no file written |
| License texts | `src/screens/views.py:626-628` `path.read_text(encoding="utf-8")` | **The app's only text decode** — but the inputs are 7 fixed UTF-8 license files (`views.py:43-51`) |

## Findings

### F1 · P2 · The prior study's on-device plan is dead on arrival and would misfire if revived

- **Where:** `docs/dependency-studies/binaryornot.md:42-51` ("Our-project utilization (M3/M5) … `is_binary(path)` is exactly that gate, no new dependency … for on-device use it is a ~10-line vendored heuristic"); contradicted by `tests/test_proot_surfaces.py:133-148`; `pyproject.toml:9-15`; `uv.lock:224`.
- **What:** the study proposes `is_binary(path)` as the gate for an on-device import/export feature (pull guest files out of a container, then decode-and-show vs offer-a-save). The app has no such feature: the only file the user can move is a whole-container tar, handled by upstream proot (`src/services/proot_service.py:357-372`), and the only in-container file access is the shell terminal (`src/screens/terminal_view.py:104-110`). Worse, the proposal is forbidden: `tests/test_proot_surfaces.py:142` names `"binaryornot"` in the `dev_only` set, so importing it from `src/` fails the test suite. `binaryornot` is also a **transitive** dependency of `flet-cli`/`cookiecutter`, not a declared one (`pyproject.toml:9-15`); relying on it in `src/` would depend on a dev-group package that never ships to the APK.
- **Evidence:** `grep -rn "binaryornot\|is_binary" src/` → 0 hits (exit 1). `pyproject.toml:9-15` has no `binaryornot`; `uv.lock:224` places it under `flet-cli`'s dependency list, `uv.lock:179` under `cookiecutter`'s. `tests/test_proot_surfaces.py:135-145` lists `"binaryornot"` in `dev_only`, and `:146-148` asserts no `src/**/*.py` imports any of them.
- **Fix / opportunity:** correct `docs/dependency-studies/binaryornot.md:42-51` to state the plain truth — **build-host only, transitively via cookiecutter; not an app dependency.** Do not "wire up" an import/export feature on this package. If a future on-device file-preview feature is genuinely specced, the gate must be reimplemented in `src/` (the study's own `chardet` is LGPL and must not be vendored — `chardet-5.2.0.dist-info/METADATA` `License: LGPL`), and it must handle F1 of this report (the chunk boundary) — see F2.
- **Risk if ignored:** the synthesis inherits a phantom integration: an app-side `is_binary()` call that breaks the `dev_only` guard test and adds a runtime dependency that is absent from the shipped dependency set, producing an `ImportError` on device (the app bundle only contains `pyproject.toml:9-15`).

### F2 · P2 · `is_binary` calls valid UTF-8 text "binary" whenever the 1024-byte chunk splits a multi-byte character

- **Where:** `.venv/Lib/site-packages/binaryornot/helpers.py:25` (`get_starting_chunk(filename, length=1024)`), `:33-35` (`f.read(length)` — a hard 1024-byte cut, no alignment), `:71-72` (`nontext_ratio1`), `:83-84` (`nontext_ratio2`), `:87-90` (`is_likely_binary`), `:94` (`chardet.detect`), `:99-103` (decode only if `confidence > 0.9` **and** the *chunk* decodes), `:119-123` (return `True` when `is_likely_binary` and not decodable); `check.py:32-33` (the chunk is what `is_binary` actually judges).
- **What:** the heuristic computes `nontext_ratio1` from bytes outside `_printable_ascii` (`helpers.py:40,47`), so a UTF-8 CJK file has `r1 = 1.0`; and `nontext_ratio2` from bytes outside `_printable_high_ascii` (`helpers.py:44,48`), so `r2 = 0.0`. That satisfies `helpers.py:88` (`r1 > 0.3 and r2 < 0.05`) → `is_likely_binary = True`. The text verdict then depends entirely on the chunk decoding cleanly. Because the chunk is cut at a fixed byte offset, the cut frequently lands **inside** a multi-byte UTF-8 character; the truncated chunk raises `UnicodeDecodeError`, `decodable_as_unicode` stays `False` (`helpers.py:113-115`), and `helpers.py:119-123` returns `True` — "binary" — for a file that is perfectly valid UTF-8 end to end.
- **Evidence:** runnable probe against the installed package (`.venv/Scripts/python.exe`), file = `"这是一段中文文本，用于测试二进制检测。".encode("utf-8") * 40` (2280 bytes, decodes as UTF-8 in full):
  ```
  full file bytes: 2280   chunk bytes: 1024   (chunk ends on byte 0xe3)
  chunk decodes as utf-8? NO -> 'utf-8' codec can't decode byte 0xe3 in position 1023: unexpected end of data
  full  decodes as utf-8? YES
  whole  (2280B): r1=1.000 r2=0.000 likely_binary=True  chardet=utf-8/0.99 decodable=True  => is_binary_string=False
  chunk  (1024B): r1=1.000 r2=0.000 likely_binary=True  chardet=utf-8/0.99 decodable=False => is_binary_string=True
  chunk-1(1023B): r1=1.000 r2=0.000 likely_binary=True  chardet=utf-8/0.99 decodable=True  => is_binary_string=False
  chunk+1(1025B): r1=1.000 r2=0.000 likely_binary=True  chardet=utf-8/0.99 decodable=False => is_binary_string=True
  ```
  The 1023/1024/1025 off-by-one triple isolates the cause to the chunk cut, not to the content. `is_binary()` on the same file returns `True` (binary) — a false positive on real text.
- **Fix / opportunity:** do not use `is_binary` as a text gate anywhere (this is the deciding argument against F1's proposal). If a text-viewing feature is ever specced, either (a) decode with `errors="replace"` and probe for replacement characters, or (b) probe a chunk that is trimmed to a character boundary, or (c) sniff for NUL bytes plus a UTF-8 decode attempt of the whole (bounded) file. The study's own "reimplement the ratio check" hint (`docs/dependency-studies/binaryornot.md:48-49`) is the better path than depending on this package.
- **Risk if ignored:** for a CJK/Japanese/Korean system log or a UTF-8 config inside a container, a text-preview built on `is_binary()` would refuse to show a file the user can plainly read in the terminal — the exact "mojibake / refuse to show" outcome the study claimed the package would prevent.

### F3 · P3 · `is_binary()` accepts `str` only — a `pathlib.Path` argument raises `AttributeError`

- **Where:** `.venv/Lib/site-packages/binaryornot/check.py:28` (`if filename.endswith(ext):`) and `:26` (`binary_extensions = ['.pyc', ]`); `check.py:18` (signature takes `filename`).
- **What:** the extension shortcut calls `str.endswith`, so a `Path` object blows up before the content probe is ever reached. The app's house style is pathlib throughout (`src/screens/views.py:20,627`; `src/core/storage_paths.py:15`; `src/core/proot_probe.py:30,32`; `src/services/proot_service.py:180`), so a naive integration would crash on the first call. Note the extension list is only `.pyc` — every other type (PNG, tar.gz, ELF) is judged purely by content, which is where F2 applies.
- **Evidence:** `is_binary(Path(".../icon.png"))` → `AttributeError: 'WindowsPath' object has no attribute 'endswith'` (installed `.venv` package).
- **Fix / opportunity:** if the tool is ever used, call it with `str(path)` — but per F1/F2 the correct answer is to not use it on-device.
- **Risk if ignored:** an immediate crash on the first invocation of any future text-preview path, in a package whose whole purpose is to prevent crashes.

### F4 · P3 · A missing or unreadable file is silently reported as "text", and the error is `print()`ed to stdout

- **Where:** `.venv/Lib/site-packages/binaryornot/helpers.py:32-37` (`except IOError as e: print(e)` — the function then returns `None` implicitly); `.venv/Lib/site-packages/binaryornot/check.py:32-33` (passes that `None` to `is_binary_string`); `.venv/Lib/site-packages/binaryornot/helpers.py:66-67` (`if not bytes_to_check: return False` → "not binary").
- **What:** the IOError is swallowed and the error text is written to **stdout** rather than raised or logged. The `None` return then flows into `is_binary_string(None)`, which hits the empty-input short-circuit and returns `False`. So `is_binary()` on a nonexistent path, a directory, or an unreadable file returns **`False` = "this is text"**. A caller that uses "is it binary?" to decide "can I decode this?" would then attempt to decode a missing file.
- **Evidence:** installed package, runnable:
  ```
  is_binary(missing) -> False          # after printing "[Errno 2] No such file or directory: ..."
  get_starting_chunk(missing) -> None
  is_binary(dir)     -> False          # after printing "[Errno 13] Permission denied: ..."
  is_binary_string(None) -> False
  ```
- **Fix / opportunity:** none needed on our side (we do not call it). Worth recording so the synthesis does not propose `is_binary()` as a "safe to decode" predicate: it answers "text" for every input it could not actually read.
- **Risk if ignored:** a future caller treats an unreadable guest file as text and surfaces a decode error (or empty content) to the user instead of an honest failure.

### F5 · P3 · The app's only text decode has no encoding fallback — but binaryornot is not the fix

- **Where:** `src/screens/views.py:626-628` (`body = path.read_text(encoding="utf-8")[:6000] if path.is_file() else "(text missing)"`); `views.py:43-51` (`_TEXT_FILES` — 7 fixed `.txt` names); `views.py:422` (`content=licenses_view()` evaluated *before* `page.show_dialog(...)` at `:419`).
- **What:** `read_text(encoding="utf-8")` has no `errors=` fallback, so a non-UTF-8 license file would raise `UnicodeDecodeError` out of `licenses_view()`, and because `:422` is an argument to `page.show_dialog(...)`, the dialog would never open. The `is_file()` guard already covers the missing-file case, and all 7 shipped texts are valid UTF-8, so this is hardening rather than a live defect.
- **Evidence:** all 7 files at `git show HEAD:src/LICENSES/<name>.txt` decode as UTF-8 (Apache-2.0 11357 B, BSD-3-Clause 1529 B, GPL-2.0 19106 B, GPL-3.0 35147 B, MIT 1071 B, MPL-2.0 16726 B, PSF-2.0 13936 B). `views.py:628` is the only `read_text`/`decode` site in `src/` (grep for `open(|.read()|read_text|read_bytes|decode(` across `src/` returns only `brand_hero.py:28` `read_bytes`, `proot_probe.py:97` `read_bytes`, `terminal_view.py:107,126` `.encode("utf-8")`, and this line).
- **Fix / opportunity:** if this path is touched for another reason, use `errors="replace"` (or `read_bytes()` + a lenient decode). Do **not** introduce a binary-vs-text probe here: the inputs are 7 known-UTF-8 license files, and the dominant defect at this site is already reported by the flet-cli audit (the texts are unreachable on device through `Path(__file__)` under the `app.zip` zipimport packaging — see `docs/swarm/dependency-utilization/flet-cli.md` F4).
- **Risk if ignored:** low — a corrupted or re-encoded license file would blank the Licenses dialog instead of showing text.

## Missed capabilities (dependency audits only)

**None — and that is the finding, not an omission.** The capability binaryornot offers (a binary-vs-text decision before decoding a file) has no consumer in this app:

- The app never opens a user-supplied file for display. `ft.FilePicker` is used exactly twice (`src/app_controller.py:342-368`): `save_file` to choose where proot writes a container tar, and `pick_files` to choose a container tar to restore. In both cases the path is handed to upstream proot (`src/services/proot_service.py:357-372`) as an opaque string; the app never inspects the bytes.
- The app never renders guest file content. Guest content reaches the screen only through the PTY (`src/services/session_manager.py:31,38-42` keeps a `deque[bytes]`; `src/screens/terminal_view.py:105-108` forwards bytes to flet-terminal), where the terminal emulator — not Python — decides how bytes render.
- There is no log viewer, no file browser, no editor, no text-preview dialog, and no download manager in `src/`.
- The app's own binary assets never need a probe: `brand_hero.py:28` hands bytes to `ft.Image(src=...)` and `proot_probe.py:97` copies `.so` files byte-for-byte.

Cost of the status quo: zero. Value of adding a probe: zero, and it would import a package the app is forbidden to import (`tests/test_proot_surfaces.py:142`) that is absent from the shipped dependency set (`pyproject.toml:9-15`).

The one place binaryornot does earn its keep is the build host, and it is already earning it: `flet build` → `cookiecutter` → `is_binary(infile)` (`cookiecutter/generate.py:221`) keeps Flutter-template binary assets out of the Jinja2 renderer. That path needs no change from us.

## Verified-good list

- Installed version is exactly **0.4.4** with `License: BSD` and `Requires-Dist: chardet (>=3.0.2)` (`.venv/Lib/site-packages/binaryornot-0.4.4.dist-info/METADATA`), and `chardet` resolves to **5.2.0** (`License: LGPL`, `.venv/Lib/site-packages/chardet-5.2.0.dist-info/METADATA`). The study's identity claims at `docs/dependency-studies/binaryornot.md:3-5` are correct.
- The package is pure Python with no compiled artifacts — `RECORD` lists only `__init__.py`, `check.py`, `helpers.py` plus dist-info files. The study's "no compiled files" claim (`docs/dependency-studies/binaryornot.md:3-4`) holds.
- The documented public surface is complete and accurate: `check.is_binary` (`check.py:18`), `helpers.get_starting_chunk` (`helpers.py:25`), `helpers.is_binary_string` (`helpers.py:51`), `helpers.print_as_hex` (`helpers.py:18`). Nothing else is exported; `binaryornot/__init__.py` adds no API.
- The cookiecutter usage described in the study is confirmed verbatim in the installed source: `cookiecutter/generate.py:15` imports `is_binary`, `:221` applies it, `:222-224` copies with `shutil.copyfile`/`copymode` and returns without rendering.
- The flet-cli → cookiecutter → binaryornot build-host chain is real and exercised by CI: `flet_cli/commands/build_base.py:1893-1895` calls `cookiecutter.main.cookiecutter(...)`, and `app.yml:149,159` / `:203,213` run `uv run flet build apk` / `flet build aab` after `uv sync --frozen --group dev` (`app.yml:49,149,203`).
- The app never imports binaryornot, chardet, cookiecutter, jinja2, requests, flet_cli, flet_desktop, pytest, or ruff — enforced by `tests/test_proot_surfaces.py:133-148` and true in the current tree (grep returns 0 hits in `src/`). The licensing boundary (A4) is intact.
- `binaryornot` does **not** ship to the APK: it is a transitive dependency of the dev-group `flet-cli` (`pyproject.toml:77-84`), not of any `pyproject.toml:9-15` runtime dependency.
- `is_binary_string` correctly classifies the realistic binary cases the app would care about (verified against the installed package): repo PNG asset → `True`; ELF-like header → `True`; gzip magic → `True`; 16-byte and 64-byte random blobs → `True`; ASCII text → `False`; UTF-8-with-BOM text → `False`; empty file → `False` (`helpers.py:66-67`); ASCII log with a single UTF-8 error line → `False`; Latin-1 text → `False`.
- The app's backup/restore and install paths keep tar/archive handling entirely inside upstream proot; `src/services/proot_service.py:357-372` passes file names and archives as opaque arguments, and `src/services/proot_service.py:175-181` measures container size with `stat()` only, never opening a file.
- The app's only text-decode inputs are 7 shipped license `.txt` files, all valid UTF-8 at `HEAD`, all guarded by `is_file()` (`src/screens/views.py:628`).

## Unverified

- **The contents of the flet build template** (`https://github.com/flet-dev/flet/releases/download/v{version}/flet-build-template.zip`, `flet_cli/commands/build_base.py:67-70`) could not be inspected offline — no cached template zip exists on this machine (`~/.flet/cache` holds only `python-build/manifest-20260921.json`). I therefore cannot state whether the template actually contains binary assets that `is_binary()` (`cookiecutter/generate.py:221`) is protecting, only that the guard is invoked for every template file. The sibling flet-cli audit inspected a pinned v1.0.4 template; I did not re-derive that here.
- **The `chardet` confidence threshold interaction in the wild** is characterised only by the three files I probed (Chinese, German, ASCII-with-UTF-8). I did not sweep a corpus of real-world logs or container configs, so the exact rate of F2 false positives across other encodings (UTF-16, UTF-32, Shift-JIS, GBK) is unmeasured. UTF-16LE text was observed to be classified `True` (binary) in the first probe, which is expected but I did not isolate whether that is F2's chunk cut or the ratio thresholds alone.
- **On-device reachability of the license texts** — `docs/swarm/dependency-utilization/flet-cli.md` F4 argues they are unreachable through `Path(__file__)` under the `app.zip` packaging. I confirmed the code shape (`src/screens/views.py:20,626-628`) but did not re-run the zipimport proof, and did not verify whether the shipped build in `build/` has the same layout. This matters only for F5's severity, not for the binaryornot verdict.
- **`src/LICENSES/` and the repo `LICENSES/` directory are currently deleted in the working tree** (`git status --short` shows ` D LICENSES/*.txt` and ` D src/LICENSES/*.txt`; they are tracked in `HEAD`). I did not modify anything. Whether that deletion is intentional (a separate in-flight change) is unknown to me. The consequence is verified, not assumed: `.venv/Scripts/python.exe -m pytest tests/test_ui_reactive.py::test_license_texts_are_present_and_shipped` fails today with `AssertionError: src/LICENSES is missing — the texts would not ship` at `tests/test_ui_reactive.py:182`. That is unrelated to binaryornot, but it is the reason `src/screens/views.py:628` currently falls back to `"(text missing)"` for every license tile in this working tree.
- I did not execute the app on a device or emulator; all runtime behaviour claims above come from reading `src/`, `.venv/`, and running the installed `binaryornot` package directly under `.venv/Scripts/python.exe` (Python 3.14.7).
