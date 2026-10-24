# packaging 26.3 — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/dependency-studies/packaging.md`; `docs/decisions.md` (D-003, D-004, D-010, D-015); `docs/reference/dep-flet-cli.md`; `docs/swarm/dependency-tree/uv-tree.txt`, `uv-tree-inverted.txt`, `installed.json`; `pyproject.toml`; `uv.lock`; `version.json`; `.github/workflows/app.yml`; `src/core/constants.py`; `src/core/changelog.py`; `src/core/proot_probe.py`; `src/services/update_service.py`; `src/components/app_header.py`; `src/components/update_dialog.py`; `src/screens/views.py`; `tests/test_version_sync.py`; `tests/test_imports_vs_deps.py`; `tests/check_flet_api.py`; `build_flet_proot_wheel.py`; `.venv/Lib/site-packages/packaging/` (all 18 modules + `licenses/`); `.venv/Lib/site-packages/packaging-26.3.dist-info/METADATA`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/flet_cli/utils/python_versions.py`; `.venv/Lib/site-packages/flet_cli/commands/flutter_base.py`; `.venv/Lib/site-packages/_pytest/config/__init__.py`; `.venv/Lib/site-packages/_pytest/outcomes.py`; `.venv/Lib/site-packages/_pytest/unittest.py`; `.venv/Lib/site-packages/{pytest,flet_cli}-*.dist-info/METADATA` · **Date:** 2026-10-20

## What it does / how the app uses it

**Plainly: `packaging` 26.3 is installed in the venv and is used correctly by its two consumers — `pytest` and `flet-cli` — but the app, the host tools and the CI gates never touch it. Every version comparison, version-sync check and dependency-name parse in this repository is hand-rolled string/tuple arithmetic, and four of those hand-rolled comparators are wrong in ways that fire the moment the house does what it says it does (a version bump).**

### 1. Identity — verified

- `packaging` 26.3 is installed: `.venv/Lib/site-packages/packaging/__init__.py:9` → `__version__ = "26.3"`; `.venv/Lib/site-packages/packaging-26.3.dist-info/METADATA:3` → `Version: 26.3`, `:5` → `Requires-Python: >=3.9`, `:8` → `License-Expression: Apache-2.0 OR BSD-2-Clause`.
- The tree is 18 modules + `licenses/` (`_elffile.py`, `_manylinux.py`, `_musllinux.py`, `_parser.py`, `_ranges.py`, `_structures.py`, `_tokenizer.py`, `dependency_groups.py`, `direct_url.py`, `errors.py`, `markers.py`, `metadata.py`, `pylock.py`, `ranges.py`, `requirements.py`, `specifiers.py`, `tags.py`, `utils.py`, `version.py`) — 12,715 lines, 960 KB installed.
- The lock agrees: `uv.lock:506-512` (`name = "packaging"`, `version = "26.3"`, one `py3-none-any` wheel, 129,956 bytes).
- The study's inventory is **accurate**; every item it hedged on is now confirmed (see *Verified-good list*).

### 2. It is a **dev-only** dependency — it never reaches the APK

- `packaging` is required by exactly **two** installed distributions, both in the dev group:
  - `flet_cli-1.0.4.dist-info/METADATA:15` → `Requires-Dist: packaging>=25.0` (flet-cli is `[dependency-groups].dev`, `pyproject.toml:79`)
  - `pytest-9.1.1.dist-info/METADATA:36` → `Requires-Dist: packaging>=22` (pytest is `[dependency-groups].dev`, `pyproject.toml:81`)
  - `pillow-12.3.0.dist-info/METADATA:55` → `Requires-Dist: packaging; extra == "tests"` — a test extra nobody installs.
- No **runtime** package requires it. `flet-1.0.4.dist-info/METADATA:12-18` lists only `flet-cli` (under the `cli` extra), `flet-web`, `oauthlib`, `httpx`, `repath`, `msgpack`, `typing-extensions`; `flet_ads-1.0.4.dist-info/METADATA:14` → `flet==1.0.4`; `httpx-0.28.1.dist-info/METADATA:27-30` → `anyio/certifi/httpcore/idna`; `flet_terminal-0.4.0.dist-info/METADATA:23` → `flet`; `proot_distro-5.10.0.dist-info/METADATA:13` → only a `test` extra.
- The lock graph is unambiguous — `docs/swarm/dependency-tree/uv-tree-inverted.txt:71-74`:
  ```
  packaging v26.3
  ├── flet-cli v1.0.4 (*)
  └── pytest v9.1.1 (*)
  ```
  and `uv.lock:229` (inside the `flet-cli` block, header at `uv.lock:220`) + `uv.lock:637` (inside the `pytest` block, header at `uv.lock:631`) — **no marker on either edge**, so `packaging` is installed unconditionally in every dev env, on every platform.
- Resolver-level proof that it is not in the APK — the Android resolve of the runtime set (`pyproject.toml:9-15`) is **15 packages and does not contain packaging**:
  ```
  $ printf 'flet>=1.0.4\nflet-ads>=1.0.4\nhttpx>=0.28.1\nflet-terminal>=0.4.0\nproot-distro>=5.10.0\n' > req-runtime.txt
  $ uv pip compile --python-version 3.14 --python-platform aarch64-linux-android \
      --extra-index-url https://pypi.flet.dev/ req-runtime.txt | grep -E '^[a-z0-9_.-]+==' | sort
  anyio==4.15.1        flet==1.0.4            idna==3.20          oauthlib==2.0.0 -> 4.0.0
  certifi==2026.10.19  flet-ads==1.0.4        msgpack==1.1.2      proot-distro==5.10.0
  flet-terminal==0.4.2 h11==0.16.0            httpx==0.28.1       repath==0.9.0
  httpcore==1.0.9     six==1.17.0            typing-extensions==4.16.0
  (15 packages; `grep -i '^packaging'` → no output)
  ```
  The 15 are exactly the 15 in the app's own shipped-license list, `src/screens/views.py:26-42` — which correctly **omits** packaging.
- **Consequence for this audit:** `src/` code **cannot** import `packaging` without promoting it to `[project].dependencies` (`pyproject.toml:9-15`) — and the house's own import guard would fail the build first: `tests/test_imports_vs_deps.py:46-59` scans `src/**/*.py` and asserts every non-stdlib, non-local import maps to a declared dependency; `packaging` is in neither `project.dependencies` nor `tool.flet.<platform>.dependencies`, so `'packaging' in declared → False` (verified: the declared set is `['flet', 'flet_ads', 'flet_proot', 'flet_terminal', 'httpx', 'proot_distro']`).

### 3. Where the app / host tools / CI hand-roll version handling (the full inventory)

| # | Site | What it does | Correct? |
|---|---|---|---|
| A | `src/services/update_service.py:50-55` `_release_tuple` | splits a version on `[-+]`, requires every dot-component to `.isdigit()`, returns a tuple of ints | **no** (F1) |
| B | `src/services/update_service.py:58-67` `is_newer` | `int(remote_build) > APP_BUILD_NUMBER` **or** `remote_tuple > local_tuple` | **no** (F1) |
| C | `.github/workflows/app.yml:85-86` `def vt(s)` | `tuple(int(x) for x in s.split("."))` — a **second, independent** version comparator | **no** (F2) |
| D | `.github/workflows/app.yml:91` `elif vj_v == py:` | string equality for "the feed is in sync" | **no** (F2) |
| E | `.github/workflows/app.yml:96` `elif vt(vj_v) < vt(py):` | tuple compare for "the feed is behind" | **no** (F2) |
| F | `tests/test_version_sync.py:25` | `proj["project"]["version"] == APP_VERSION` (string equality) | **no** (F3) |
| G | `tests/test_version_sync.py:26` | `int(proj["tool"]["flet"]["build_number"]) == APP_BUILD_NUMBER` | correct |
| H | `tests/test_version_sync.py:30-31` | `APP_VERSION in CHANGELOG` + `notes_for(APP_VERSION)` (dict key lookup) | stringly (F3, F6) |
| I | `tests/test_version_sync.py:39` | `int(feed["build_number"]) <= APP_BUILD_NUMBER` | correct (the feed may legitimately lead) |
| J | `tests/test_version_sync.py:45-46` | `f'default: "{APP_VERSION}"' in workflow` (substring on YAML) | correct-ish, brittle |
| K | `tests/test_imports_vs_deps.py:26-32` | hand-rolled PEP 508 requirement-name parser | **no** (F4) |
| L | `build_flet_proot_wheel.py:388` | hand-built wheel filename `f"{DIST_NAME}-{proot_version}-{build_tag}-{tag}.whl"` | unvalidated (F5) |
| M | `build_flet_proot_wheel.py:395` | hand-built dist-info dir `f"{DIST_NAME}-{proot_version}.dist-info"` | unvalidated (F5) |
| N | `build_flet_proot_wheel.py:399-412` | hand-written `METADATA` (Version, Requires-Python, License, License-File) | unvalidated (F5) |
| O | `build_flet_proot_wheel.py:34-81` `_PINNED_SOURCES` vs `pyproject.toml:52` | two hand-kept copies of the `flet-proot` version | **not cross-checked** (F5) |
| P | `src/core/changelog.py:16-18` `notes_for` | "falling back to the newest one" — returns the **oldest** | **no** (F6) |

Everything else that mentions a version is display-only: `src/components/app_header.py:41` (chip label), `src/components/update_dialog.py:47,56` (dialog text), `src/screens/views.py:570,581,589` (license-screen version strings), `src/core/proot_probe.py:83-87` (payload provenance text), `tests/check_flet_api.py:81` (prints the installed flet version). None of them compares.

## Findings

### F1 · P1 · The runtime update check compares versions with a hand-rolled int-tuple, not PEP 440 — it can offer every user a bogus update and can miss real ones

- **Where:** `src/services/update_service.py:50-55` (`_release_tuple`), `:58-67` (`is_newer`), `:63` (the `except` clause), `:84-86` (the call), `:100-102` (the blanket `except Exception`); `src/core/constants.py:11-12` (`APP_VERSION = "1.0.0"`, `APP_BUILD_NUMBER = 1`); `version.json:2-3`.
  API claims: `.venv/Lib/site-packages/packaging/version.py:110` (`def parse(version: str) -> Version`), `:124` (`class InvalidVersion(ValueError)`), `:340` (`class Version`), `:408` (`Version.__init__`), `:606-745` (the six comparison operators, PEP 440 `_cmpkey` ordering), `:1014` (`is_prerelease`).
- **What:** `_release_tuple` strips a `-`/`+` suffix, splits on `.`, requires every component to satisfy `str.isdigit()`, and returns a tuple of ints. It then compares tuples. That is **not** PEP 440 ordering:
  - **Trailing/extra components are not normalized.** PEP 440 says `1.0`, `1.0.0` and `1.0.0.0` are the *same* version (`packaging.utils.canonicalize_version`, `utils.py:154`, strips trailing zeros: `canonicalize_version('1.0.0')` → `'1'`). The tuple compare says otherwise, in **both** directions.
  - **Prerelease / post / epoch / `v`-prefix forms are not understood at all** — `_release_tuple` returns `None` for them and `is_newer` then gives up.
  - **`str.isdigit()` admits non-decimal digits.** `'²'.isdigit()` is `True` but `int('²')` raises `ValueError`, and the `try/except` at `:60-64` wraps **only** the build-number branch, so the `ValueError` escapes `is_newer` and is swallowed by the blanket `except Exception` at `:100` → the whole update check silently returns `None` for the rest of the session.
- **Evidence:** (runnable, against the installed `packaging` 26.3 and the repo's own `src/`)
  ```
  $ .venv/Scripts/python.exe -c "<import services.update_service as us; from packaging.version import Version;
      us.APP_VERSION='1.0'; print(us.is_newer(1,'1.0.0'), Version('1.0.0') > Version('1.0'))"
  True False          <-- same version, app says "update available"
  ```
  Full table (local `APP_VERSION = "1.0.0"`, `remote_build = 1`):
  ```
        remote             rtuple  is_newer  PEP440 newer?
         1.0.0          (1, 0, 0)     False          False
           1.0             (1, 0)     False          False
         1.0.0.0       (1, 0, 0, 0)      True          False   <-- FALSE POSITIVE
         1.1.0          (1, 1, 0)      True           True
         1.0.0rc1               None     False          False
        1!2.0.0               None     False           True   <-- MISSED
          v1.1.0               None     False           True   <-- MISSED
      1.0.0+build7          (1, 0, 0)     False           True   <-- MISSED
       1.0.0.post1               None     False           True   <-- MISSED
  ```
  and the `isdigit` trap:
  ```
  _release_tuple('1.0.²') -> ValueError: invalid literal for int() with base 10: '²'
  '²'.isdigit() = True | int('²') -> ValueError
  ```
- **Fix / opportunity:** (minimal, architecture-respecting) **do not add `packaging` to the runtime dependency set.** The version-string comparison in `is_newer` is *redundant*: the feed's `build_number` is the authoritative signal, and CI already guarantees it is monotonic and in lockstep with the shipped build (`.github/workflows/app.yml:92-93` requires `version.json.build_number == BUILD_NUMBER == tool.flet.build_number` whenever the versions match). **Drop the version-string branch from `is_newer` entirely** and compare on `build_number` only — one integer, zero parsing, zero new dependency, and it cannot be fooled by a version format.
  If the owner wants the version string to remain a second signal, it must be compared with PEP 440 semantics, and `packaging` is **not importable from `src/`** (§2) — so the honest options are (a) promote `packaging` to `[project].dependencies` (cost: 15 modules / 12,715 lines / 960 KB installed in the APK; **needs owner sign-off under D-003**, `docs/decisions.md:12-13`), or (b) keep it dependency-free and at minimum strip trailing zeros and a leading `v` before comparing. Option (a) is the weaker one: the `build_number`-only fix is strictly simpler and already correct.
  Independently of the above, the `except TypeError, ValueError:` at `:63` must be widened to cover the version branch (or the version branch removed), so a malformed feed version cannot kill the whole update check.
- **Risk if ignored:** the next release that changes the version *shape* (e.g. `1.0.0` → `1.1`, or a `1.0.0.post1` rebuild) either pushes a **false "Update available" pill to every user** (header chip, `src/components/app_header.py:41`) or **silently hides a real update**. A malformed feed version disables the update feature for the whole session. This is the house's stated release path (D-004, `docs/decisions.md:15-16`), so the trigger is routine, not exotic.

### F2 · P1 · The CI release-identity gate carries a second, independent version comparator that can block a release on a cosmetic reformat — and crash with a traceback on any non-numeric version

- **Where:** `.github/workflows/app.yml:59-106` (the *Release identity consistency* step), `:85-86` (`def vt(s): return tuple(int(x) for x in s.split("."))`), `:91` (`elif vj_v == py:`), `:96` (`elif vt(vj_v) < vt(py):`), `:99` (the "AHEAD" error), `:101-105` (`sys.exit(1)`); inputs at `:33-34`.
  API claims: `.venv/Lib/site-packages/packaging/version.py:110` (`parse`), `:124` (`InvalidVersion`), `:606-745` (ordering operators).
- **What:** the step compares `version.json`'s version against `pyproject.toml`'s three ways: string equality (`:91`), then a hand-rolled int-tuple (`:96`). Both are wrong:
  - **False "the feed advertises a version that does not exist".** `version.json` says `1.0.0`, `pyproject.toml` says `1.0` — *the same version* under PEP 440 — and `vt("1.0.0") < vt("1.0")` is `False`, so control falls to the `else` at `:99` and the step appends *"version.json 1.0.0 is AHEAD of pyproject 1.0 — the feed advertises a version that does not exist"* and `sys.exit(1)` at `:105` **blocks the release pipeline**. The mirror case (pyproject `1.0.0`, feed `1.0`) is equally wrong.
  - **Traceback instead of a drift message.** `vt()` raises `ValueError` on any component that is not a bare integer, so a prerelease/post/epoch version in `version.json` or `pyproject.toml` kills the step with an unhandled traceback; the intended drift handler at `:101-105` never runs and the operator gets a stack trace instead of the house's "Version drift:" report.
  - **The step is duplicated logic.** The same three numbers are also compared as *strings* in `tests/test_version_sync.py:25,45-46` (F3) and, in the runtime, as a tuple in `src/services/update_service.py:50-55` (F1). Three comparators, one truth.
- **Evidence:** (the CI snippet, reproduced verbatim against the installed `packaging`)
  ```
  py, vj_v = "1.0", "1.0.0"
    vt(vj)= (1, 0, 0)  vt(py)= (1, 0)
    vj_v == py -> False
    vt(vj) < vt(py) -> False
    => CI takes the ELSE branch: 'version.json 1.0.0 is AHEAD of pyproject 1.0' (release blocked)
  ```
  ```
  vt('1.0.0-rc1')  -> ValueError: invalid literal for int() with base 10: '0-rc1'
  vt('1.0.0rc1')   -> ValueError: invalid literal for int() with base 10: '0rc1'
  vt('1.0.0.post1')-> ValueError: invalid literal for int() with base 10: 'post1'
  vt('1!2.0.0')    -> ValueError: invalid literal for int() with base 10: '1!2'
  ```
- **Fix / opportunity:** `packaging` **is** available in this step — the job runs `uv sync --frozen --group dev` (`.github/workflows/app.yml:49`), which installs `pytest` → `packaging>=22` and `flet-cli` → `packaging>=25.0` (both edges unmarked, `uv.lock:229`, `uv.lock:637`). Replace `vt()` with `packaging.version.Version`:
  - "in sync" → `Version(vj_v) == Version(py)` (true for `1.0` vs `1.0.0`),
  - "feed behind" → `Version(vj_v) < Version(py)`,
  - "feed ahead" → `Version(vj_v) > Version(py)`,
  - and wrap the parse in `try/except packaging.version.InvalidVersion` so a malformed version becomes a **drift error** on the house's error list, not a traceback.
  This is a ~6-line change to a CI step, with **no new dependency** and **no APK impact** — the dependency set is untouched (packaging 26.3 is already locked at `uv.lock:506-512`).
- **Risk if ignored:** a release is blocked with a *false* accusation ("the feed advertises a version that does not exist") that sends the operator hunting for a version-sync bug that does not exist — or, in the opposite direction, a genuinely inconsistent feed slips past because `vt()` compares a different axis than the author intended. D-004 makes a version bump a routine, quarterly-ish event; every such event re-runs this gate.

### F3 · P2 · `tests/test_version_sync.py` compares version *strings* for equality, so it fails on a semantically identical version — and never checks a single installed version against a declared floor

- **Where:** `tests/test_version_sync.py:23-26`, `:29-31`, `:34-40`, `:43-46`; `pyproject.toml:5` (`version = "1.0.0"`), `:9-15` (the declared floors), `:26` (`build_number = 1`).
  API claims: `.venv/Lib/site-packages/packaging/version.py:606-745`; `.venv/Lib/site-packages/packaging/utils.py:154` (`canonicalize_version`); `.venv/Lib/site-packages/packaging/requirements.py:82` (`Requirement.__init__`); `.venv/Lib/site-packages/packaging/specifiers.py:794` (`SpecifierSet.__init__`), `:1228` (`SpecifierSet.contains`).
- **What:** the guard asserts `proj["project"]["version"] == APP_VERSION` (`:25`) — **string** equality, not version equality. `1.0` and `1.0.0` are the same version under PEP 440 (`canonicalize_version('1.0.0')` → `'1'`, `utils.py:154`) but the test fails on them, and a legitimate formatting change from `1.0.0` to `1.0` breaks the suite for no reason. Conversely the guard never validates a *version at all*: `pyproject.toml:9-15` declares `flet>=1.0.4`, `flet-ads>=1.0.4`, `httpx>=0.28.1`, `flet-terminal>=0.4.0`, `proot-distro>=5.10.0` and `pyproject.toml:52` declares `flet-proot==5.1.107.98`, but **no test in the repo asserts that the installed distributions satisfy those specifiers**. The installed tree is flet 1.0.4, flet-ads 1.0.4, httpx 0.28.1, flet-terminal 0.4.0, proot-distro 5.10.0 — all currently satisfied, but *nothing enforces it*, so a stale lock or a bad `uv add` can silently install flet 1.0.3 and the whole suite still passes.
  The changelog check (`:29-31`, `APP_VERSION in CHANGELOG`) has the same stringly coupling: the `CHANGELOG` dict key (`src/core/changelog.py:6`) must be a byte-identical copy of `APP_VERSION` (`src/core/constants.py:11`) which must be a byte-identical copy of `pyproject.toml:5` — **three** hand-synced copies, compared as strings.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "from packaging.utils import canonicalize_version as c; from packaging.version import Version
      print(c('1.0.0'), c('1.0'), Version('1.0')==Version('1.0.0'), Version('1.0')==Version('1.0'))"
  1 1 True True
  ```
  The installed-vs-declared state (all currently green, all currently unenforced):
  ```
  'flet>=1.0.4'        -> canonical 'flet'           spec '>=1.0.4'      marker=None
  'flet-ads>=1.0.4'    -> canonical 'flet-ads'       spec '>=1.0.4'      marker=None
  'httpx>=0.28.1'      -> canonical 'httpx'          spec '>=0.28.1'     marker=None
  'flet-terminal>=0.4.0'-> canonical 'flet-terminal' spec '>=0.4.0'      marker=None
  'proot-distro>=5.10.0'-> canonical 'proot-distro'  spec '>=5.10.0'     marker=None
  'flet-proot==5.1.107.98'-> canonical 'flet-proot'  spec '==5.1.107.98' marker=None
  ```
- **Fix / opportunity:** (all inside `tests/`, where `packaging` is installed)
  1. Replace the string compares at `:25` and `:45-46` with `packaging.version.Version` (`Version(proj["project"]["version"]) == Version(APP_VERSION)`), so the guard tests the *version*, not its spelling.
  2. **Add the missing test** — the one the house's own dependency study claims exists (`docs/dependency-studies/packaging.md:125-129`: *"Import-vs-deps guards are exact, not stringly … so the 'bump a version' update path is verified by tests, not by hope"*). It does not. The test is ~10 lines: for each `Requirement` parsed from `pyproject.toml:9-15` + `:52`, read the installed version with `importlib.metadata.version(req.name)` and assert `req.specifier.contains(installed)`, skipping `flet-proot` (a build artifact, not installed in the venv). This turns D-004's "floors in pyproject" into an enforced fact for the first time.
  3. For the changelog, assert the *set* of `CHANGELOG` keys satisfies the version ordering (`Version` sorted), not just that the current version is a key.
- **Risk if ignored:** the house's stated release invariant — "floors in pyproject, exact in `uv.lock`, `uv sync --frozen` in CI" (`docs/decisions.md:16`) — is enforced by the *lockfile*, not by a test. A hand-edited `pyproject.toml` floor, or a `uv add` that moved a floor backwards, is invisible to the suite. A version reformat (`1.0.0` → `1.0`) breaks CI for a spelling reason.

### F4 · P2 · `tests/test_imports_vs_deps.py` re-implements PEP 508 requirement parsing by hand, so the house's dependency guard checks **names only** — never specifiers, never markers, never installed versions

- **Where:** `tests/test_imports_vs_deps.py:18-32` (`_declared()`), `:26-32` (the parse loop), `:35-43` (`_imports()`), `:46-59` (the guard), `:57` (the assertion).
  API claims: `.venv/Lib/site-packages/packaging/requirements.py:27` (`InvalidRequirement`), `:35` (`class Requirement`), `:82` (`__init__` → `.name` / `.specifier` / `.marker` / `.extras` / `.url`); `.venv/Lib/site-packages/packaging/utils.py:82` (`canonicalize_name`), `:127` (`is_normalized_name`); `.venv/Lib/site-packages/packaging/markers.py:402` (`Marker.__init__`), `:504` (`Marker.evaluate`).
- **What:** the manual parser is six chained string splits:
  ```python
  base = dep.split(";")[0].strip()      # strip the marker
  base = base.split("[")[0].strip()      # strip the extras
  base = base.split()[0]                 # first whitespace token
  base = base.split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("~")[0]
  names.add(base.lower().replace("-", "_"))
  ```
  It **never validates** and **throws away the specifier**. Consequences:
  - The guard at `:57` compares *names* only, so the declared floors `>=1.0.4`, `>=0.4.0`, `==5.1.107.98` are checked against **nothing**. A pyproject pin of `flet-proot==5.1.107.96` (the *previous* pin, `docs/decisions.md:57`) would pass this guard unchanged.
  - The name normalization `name.lower().replace("-", "_")` is **not PEP 503** — it does not collapse runs of `-`/`_`/`.` into a single separator. `packaging.utils.canonicalize_name` (`utils.py:82`) does: `canonicalize_name("Flet.Terminal")` → `'flet-terminal'`, `canonicalize_name("flet_terminal")` → `'flet-terminal'`. The manual rule maps `flet--terminal` → `flet--terminal` (double dash survives) and `flet.terminal` → `flet.terminal` (dot survives), so two spellings of one distribution can be treated as two different packages.
  - The order of the hacks is **load-bearing and undocumented**: `split(";")` must run before the operator split (else `python_version<'3.11'` would be chopped), and `split()[0]` must run before the operator split (else `"flet >= 1.0.4"` would become `"flet "`). Neither is documented at `:26-31`.
  - `base.split()[0]` raises **`IndexError`** on an empty dependency string (e.g. a stray empty entry in the TOML array) — the guard dies with a traceback instead of naming the offending entry.
  - The guard scans `src/` only (`:52`) and only `project.dependencies` + `tool.flet.<platform>.dependencies` (`:23-25`); `[dependency-groups].dev` (`pyproject.toml:77-84`) is invisible to it.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "<the manual parser>"
  declared (manual parser): ['flet', 'flet_ads', 'flet_proot', 'flet_terminal', 'httpx', 'proot_distro']
  'packaging' in declared -> False
  ```
  versus the same six strings through `packaging.requirements.Requirement`:
  ```
  'flet>=1.0.4'          name='flet'          canonical='flet'          spec='>=1.0.4'      marker=None
  'flet-ads>=1.0.4'      name='flet-ads'      canonical='flet-ads'      spec='>=1.0.4'      marker=None
  'httpx>=0.28.1'        name='httpx'         canonical='httpx'         spec='>=0.28.1'     marker=None
  'flet-terminal>=0.4.0' name='flet-terminal' canonical='flet-terminal' spec='>=0.4.0'      marker=None
  'proot-distro>=5.10.0' name='proot-distro'  canonical='proot-distro'  spec='>=5.10.0'     marker=None
  'flet-proot==5.1.107.98' name='flet-proot'  canonical='flet-proot'    spec='==5.1.107.98' marker=None
  ```
  and the PEP 503 difference:
  ```
  canonicalize_name('flet_terminal') -> 'flet-terminal'
  canonicalize_name('Flet.Terminal') -> 'flet-terminal'
  ```
- **Fix / opportunity:** (test-only, no new dependency) rewrite `_declared()` as
  `Requirement(dep)` → `.name` (via `canonicalize_name`) + `.specifier` + `.marker`, and let `InvalidRequirement` (`requirements.py:27`) surface a malformed `pyproject.toml` entry as a *named* failure instead of a silent mis-parse. Then extend the guard with the specifier check described in F3 (installed version ∈ declared specifier) and — because `Requirement.marker` is now available — assert that every declared dependency's marker evaluates true for the target platform (`Marker.evaluate`, `markers.py:504`), which is what `tool.flet.<platform>.dependencies` needs.
- **Risk if ignored:** the guard's name is a promise ("Every import in `src/` must be declared in `[project].dependencies`") that it only half keeps: it proves *a name* is declared, never that the declared *version* is one the app can actually run. The house's import guard is cited as the mechanism that keeps the APK installable (`tests/test_imports_vs_deps.py:3-5`); keeping it name-only means the version half of that promise is unverified.

### F5 · P1 · The `flet-proot` payload version lives in two hand-kept copies that nothing cross-checks — a payload bump that updates only one of them **breaks the APK build**; and the wheel the builder writes is never machine-validated

- **Where:** `build_flet_proot_wheel.py:34-81` (`_PINNED_SOURCES`; proot version at `:40`, libtalloc at `:54`, libandroid-shmem at `:68`), `:202-210` (`_fetch_verified` — sha256 enforcement), `:388` (wheel filename), `:395` (dist-info dir), `:399-412` (METADATA), `:413-418` (WHEEL), `:466-498` (`main`); `pyproject.toml:52` (`dependencies = ["flet-proot==5.1.107.98"]`); `.github/workflows/app.yml:141` (build the wheels), `:153` (`PIP_FIND_LINKS: ${{ github.workspace }}/wheels`), `:194-195`, `:207`.
  API claims: `.venv/Lib/site-packages/packaging/utils.py:200` (`parse_wheel_filename`), `:306` (`parse_sdist_filename`), `:54` (`InvalidWheelFilename`); `.venv/Lib/site-packages/packaging/metadata.py:814` (`class Metadata`), `:832` (`from_raw`), `:887` (`from_email`), `:46` (`InvalidMetadata`), `:360` (`parse_email`); `.venv/Lib/site-packages/packaging/version.py:110`/`124`.
- **What:** the builder writes the version `5.1.107.98` into the wheel it produces (`build_flet_proot_wheel.py:40` → `:363` → `:388`/`:395`/`:402`), and `pyproject.toml:52` independently pins `flet-proot==5.1.107.98`. These are **two copies edited by hand** and **nothing compares them**. The APK job builds the wheels from the builder (`.github/workflows/app.yml:141`) and then asks pip to resolve `flet-proot==5.1.107.98` from that directory (`PIP_FIND_LINKS`, `:153`). If the builder is bumped to `5.1.107.99` and `pyproject.toml:52` is not, pip finds no `flet-proot==5.1.107.98` in the find-links directory and the **APK build fails at dependency resolution** — the payload bump is exactly the routine operation the house does (last one: `docs/decisions.md:57`, "proot 5.1.107.98 replaced 5.1.107.96 when Termux dropped the old debs"). The sha256 lock at `:44`/`:48` protects the *bits*; nothing protects the *version agreement*.
  Separately, the wheel's own metadata is written by hand and never validated: the filename at `:388` is not checked against PEP 427, the dist-info directory at `:395` is not checked against the METADATA `Version` at `:402`, and the METADATA block at `:399-412` is never parsed. A mismatch between any of the three is a silent install failure on the device.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "from packaging.utils import parse_wheel_filename
      parse_wheel_filename('flet_proot-5.1.107.98-1-py3-none-android_24_arm64_v8a.whl')"
  name= flet-proot version= 5.1.107.98 build= (1, '') tags= frozenset({<py3-none-android_24_arm64_v8a @ 2193451341952>})
  parse_wheel_filename('flet_proot-5.1.107.98-1-py3-none-android_24_x86_64.whl')  -> OK
  ```
  ```
  $ .venv/Scripts/python.exe -c "from packaging.metadata import Metadata
      Metadata.from_email(<the exact METADATA block from build_flet_proot_wheel.py:399-412>, validate=True)"
  packaging.metadata validate=True: OK
     version       = 5.1.107.98
     requires_py   = >=3.10
     license_files = None
  ```
  and the missing cross-check (grep for the pin across the repo — only the two hand-kept copies and prose):
  ```
  pyproject.toml:52:dependencies = ["flet-proot==5.1.107.98"]
  build_flet_proot_wheel.py:40:            "version": "5.1.107.98",
  build_flet_proot_wheel.py:43:                "file": "proot_5.1.107.98_aarch64.deb",
  ```
  No test, no CI step, no workflow line compares them.
- **Fix / opportunity:** (CI-side; `packaging` is already installed in the build job — `uv sync --frozen --group dev` at `.github/workflows/app.yml:149`)
  1. **Version-agreement gate.** Parse `pyproject.toml:52` with `packaging.requirements.Requirement` → `.name`/`.specifier`, read the builder's version, and assert `req.specifier.contains(builder_version)`. One line, and it turns the APK build break into a clear CI error at the *quality* job instead of a resolver failure in the *apk* job.
  2. **Wheel self-validation.** After `build_flet_proot_wheel.py` runs, validate each produced `.whl` with `parse_wheel_filename` (name/version/build-tag) and parse its `METADATA` with `Metadata.from_email(..., validate=True)`, asserting `metadata.version == parse_wheel_filename(name).version` and that the `dist-info` directory name matches. Both APIs are already verified working on the exact artifacts the builder emits (evidence above).
  Both are host-side/CI-side: **no APK impact, no new dependency** (packaging 26.3 is already locked at `uv.lock:506-512`).
- **Risk if ignored:** the next payload bump that touches only one of the two copies fails the **APK** job (the most expensive job in the pipeline, `.github/workflows/app.yml:129-182`) with a pip resolution error that points at the resolver rather than at the version skew; or, if the METADATA/filename disagree, the app installs a payload whose reported version is not the version that was pinned and sha256-verified.

### F6 · P2 · `src/core/changelog.py` documents "falling back to the newest one" but returns the **oldest** entry

- **Where:** `src/core/changelog.py:5-13` (the `CHANGELOG` dict), `:16-18` (`notes_for`); consumed at `src/components/update_dialog.py:89` (`notes_for(APP_VERSION)`); guarded at `tests/test_version_sync.py:29-31`.
- **What:** `return CHANGELOG.get(version) or next(iter(CHANGELOG.values()), "")` — `next(iter(...))` is the **first** inserted item, i.e. the **oldest** release, not the newest. With the current single-entry changelog (`:5-13`, only `"1.0.0"`) the two coincide, so `tests/test_version_sync.py:29-31` cannot detect the bug. The moment a second version is added (the next release), an app shipped at a version with no exact changelog key shows the **first release's** notes under the "What's New" heading of the update dialog (`src/components/update_dialog.py:89`) — the oldest release notes presented as the newest.
- **Evidence:** the docstring vs the code, side by side:
  ```
  src/core/changelog.py:17:    """The changelog entry for a version, falling back to the newest one."""
  src/core/changelog.py:18:    return CHANGELOG.get(version) or next(iter(CHANGELOG.values()), "")
  ```
  `next(iter(dict.values()))` is the first insertion, not the maximum.
- **Fix / opportunity:** this module is **runtime** (`src/`), so `packaging` is not importable here without a runtime dependency (§2). The cheapest correct fix is to make the fallback honest: since `tests/test_version_sync.py:30` guarantees the shipped version **has** an entry, return `""` (render "no release notes") rather than the wrong notes, and keep `CHANGELOG` in release order so the last item is the newest. The stronger fix — ordering the fallback by PEP 440 — belongs in the **build/CI layer**, where `packaging` *is* available: a CI step that asserts `CHANGELOG`'s keys are strictly increasing `Version`s and that the highest key equals `APP_VERSION` turns a runtime guess into a checked fact. `packaging.version.Version` is the tool for it; `packaging` does not need to reach the APK for that.
- **Risk if ignored:** a user on a version without an exact changelog entry sees the **oldest** release's "What's New" text — a wrong, misleading product statement, in the one dialog where the app talks about its own history.

### F7 · P3 · The dependency study's headline claims are unverified or overstated; the flet-cli call sites it left open are now resolved

- **Where:** `docs/dependency-studies/packaging.md:104-114` (§6, *"flet-cli: packaging is a transitive dependency … exact call sites **unverified** (out of scope …)"*), `:125-129` (§7.2, *"Import-vs-deps guards are exact, not stringly … so the 'bump a version' update path (roadmap §0) is verified by tests, not by hope"*), `:30-34` (the pytest `Version` claim), `:80` (*"method name/signature unverified"*), `:89-95` (§5 inventory), `:25` (*"`from_parts(...)` (classmethod, signature **unverified**)"*).
- **What:** the study's *API inventory* is accurate, but three claims are now wrong or can be promoted:
  1. **flet-cli's call sites are now verified** and are directly relevant to this repo:
     - `flet_cli/commands/build_base.py:30` → `from packaging.requirements import Requirement`, used at `:2583` (`package_name = Requirement(toml_dependencies[i]).name`) — this is exactly where the house's `[tool.flet.android].dependencies = ["flet-proot==5.1.107.98"]` (`pyproject.toml:52`) is parsed.
     - `flet_cli/utils/python_versions.py:23-24` → `from packaging.specifiers import SpecifierSet` / `from packaging.version import Version`, used at `:168`, `:180`, `:183`, `:193`, `:197`, `:202` to select the bundled CPython for the house's `requires-python = ">=3.14"` (`pyproject.toml:8`).
     - `flet_cli/commands/flutter_base.py:9` → `from packaging import version`, used at `:136-137` and `:220-225`.
  2. **§7.2 is false of the current code.** The import guard compares *names* only (`tests/test_imports_vs_deps.py:57`); no test compares an installed version against a declared specifier (see F3, F4). The "verified by tests, not by hope" claim describes what the house *should* have, not what it has.
  3. The unverified hedges can be promoted: `from_parts` → `packaging/version.py:469`; `Marker.evaluate` → `packaging/markers.py:504`; `SpecifierSet.contains` → `packaging/specifiers.py:1228`, `.filter` → `:1317`, `.is_subset` → `:1149`, `.is_superset` → `:1169`, `.is_disjoint` → `:1187`, `.is_unsatisfiable` → `:1054`, `.to_range` → `:1128`; `packaging.utils.canonicalize_name` → `utils.py:82`, `.canonicalize_version` → `:154`, `.parse_wheel_filename` → `:200`, `.parse_sdist_filename` → `:306`, `.is_normalized_name` → `:127`; `packaging.tags.sys_tags` → `tags.py:963`; `packaging.licenses.canonicalize_license_expression` → `licenses/__init__.py:71`; `packaging.ranges.VersionRange` → `ranges.py:903`; `packaging.metadata.Metadata` → `metadata.py:814` / `.from_email` → `:887`; `packaging.dependency_groups.resolve_dependency_groups` → `dependency_groups.py:286`; `packaging.pylock.Pylock` → `pylock.py:670`.
- **Evidence:** the study's own hedges, grepped from the installed tree:
  ```
  $ grep -rn "packaging" .venv/Lib/site-packages/flet_cli/ --include="*.py" | grep -E "^.*(import|from)"
  flet_cli/commands/build_base.py:30:from packaging.requirements import Requirement
  flet_cli/utils/python_versions.py:23:from packaging.specifiers import SpecifierSet
  flet_cli/utils/python_versions.py:24:from packaging.version import Version
  flet_cli/commands/flutter_base.py:9:from packaging import version
  ```
  and the guard that §7.2 describes, showing what it actually compares:
  ```
  tests/test_imports_vs_deps.py:57
              if not (providers & declared) and mod.lower() not in declared:
  ```
  — a set of **names**; no `specifier` and no installed version appears anywhere in the file.
- **Fix / opportunity:** documentation only — the owner may promote the unverified items and correct §7.2. **No code change.** Do not open a new study; the audit above is the update.
- **Risk if ignored:** a future agent reads §7.2 and believes the version-floor discipline is already machine-enforced, and does not add the missing test (F3). Documentation drift, but it is exactly the drift that lets a real gap persist.

### F8 · P3 · `except TypeError, ValueError:` is Python-3.14-only syntax, used consistently in four runtime modules — safe today, but it ties the source to the `requires-python` floor

- **Where:** `src/services/update_service.py:63`, `src/components/update_dialog.py:33`, `src/core/posixdb.py:87`, `src/services/session_service.py:123`; `pyproject.toml:8` (`requires-python = ">=3.14"`).
- **What:** the unparenthesized multi-exception `except` is **PEP 758**, added in **Python 3.14** (peps.python.org/pep-0758 — Status *Final*, Python-Version *3.14*: *"allow 'except' expressions ':' block"*). It parses on the installed 3.14.7 (verified: `ast.parse` succeeds on `src/services/update_service.py`; `sys.version` → `3.14.7`), and the project's floor is `>=3.14`, so it is currently correct. The four occurrences are a consistent house style, not a one-off. The risk is a **coupling**: if the floor is ever lowered (or a device is built with a 3.13 CPython), these four modules become `SyntaxError` at import time. `src/services/update_service.py` is imported by `src/app_controller.py:311` and `src/components/update_dialog.py:151`, so a syntax error there is an **app-start failure**, not a degraded feature.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "import ast; ast.parse(open('src/services/update_service.py',encoding='utf-8').read())"
  AST PARSE OK        (python 3.14.7)
  $ grep -rnE "except [A-Za-z_.]+ *, *[A-Za-z_.]+ *:" src/
  src/components/update_dialog.py:33:    except TypeError, ValueError:
  src/core/posixdb.py:87:    except ValueError, ImportError:
  src/services/session_service.py:123:                except OSError, ValueError:
  src/services/update_service.py:63:    except TypeError, ValueError:
  ```
  Note the ordering: the **build** path already treats this correctly — flet-cli resolves the bundled CPython from `requires-python` with `packaging.specifiers.SpecifierSet` (`flet_cli/utils/python_versions.py:168,180,183`), so the floor is machine-honored at build time; the *source* just has to agree with it.
- **Fix / opportunity:** `except (TypeError, ValueError):` — identical semantics, valid on every Python 3.x, and it removes the source↔floor coupling. Four one-line edits, zero behavior change. (Optional; the current state is correct given `pyproject.toml:8`.)
- **Risk if ignored:** low today. It becomes a P0 (app-start `SyntaxError`) only if the Python floor moves down or a device is built with an older interpreter than the source assumes.

## Missed capabilities (dependency audits only)

`packaging` is installed and available in **every dev/CI environment** (two unconditional dependents: `pytest>=22`, `flet-cli>=25.0`; `uv.lock:229`, `uv.lock:637`). None of the following is used by the house today. Each is listed with its integration point, its value, and its cost.

- **PEP 440 version comparison — `Version` / `parse` / `InvalidVersion`** · API: `packaging/version.py:340`, `:110`, `:124`, ordering at `:606-745` · Integration point: `.github/workflows/app.yml:85-99` (the release-identity gate), `tests/test_version_sync.py:25,45-46`, and — if the owner keeps a version-string signal — `src/services/update_service.py:50-67` · Value: removes three hand-rolled comparators and every false-positive/false-negative they carry (F1, F2, F3) · Cost: **zero** in CI/tests; **non-zero in `src/`** (see §2 — `packaging` would have to become a runtime dep, 960 KB in the APK, owner sign-off under D-003). **Accepted for CI/tests, declined for `src/`** — the runtime fix there is "compare `build_number` only".
- **`Requirement` — parse a declared dependency into name + specifier + marker + extras** · API: `packaging/requirements.py:35`, `:82` · Integration point: `tests/test_imports_vs_deps.py:26-32` (replaces the six chained `split()`s) and a new "installed version satisfies the declared floor" test over `pyproject.toml:9-15` · Value: turns the house's name-only guard into a real dependency guard, and makes the import-vs-deps guard match the study's own claim (`docs/dependency-studies/packaging.md:125-129`) · Cost: zero (already installed).
- **`SpecifierSet.contains` — "is the installed version inside the declared range?"** · API: `packaging/specifiers.py:794`, `:1228` · Integration point: the new guard above; also usable for `is_subset` (`:1149`) to assert the pyproject floor is not looser than the lock's resolution · Value: machine-enforces D-004's "floors in pyproject" · Cost: zero.
- **`canonicalize_name` — PEP 503 name normalization** · API: `packaging/utils.py:82`, plus `is_normalized_name` at `:127` · Integration point: `tests/test_imports_vs_deps.py:31` (replaces `name.lower().replace("-", "_")`) and the `providers` set at `:56` · Value: correct handling of `[-_.]+` runs, and of the `flet-terminal` ↔ `flet_terminal` ↔ `Flet.Terminal` spellings the study called out (`docs/dependency-studies/packaging.md:99-101`) · Cost: zero.
- **`canonicalize_version` — strip trailing zeros** · API: `packaging/utils.py:154` · Integration point: a helper shared by the CI gate and the version-sync test, so "is 1.0 the same as 1.0.0?" has one answer · Value: exactly the normalization the tuple comparators lack (F1, F2) · Cost: zero.
- **`parse_wheel_filename` — validate a wheel's name** · API: `packaging/utils.py:200`, `InvalidWheelFilename` at `:54` · Integration point: a CI step over `wheels/*.whl` right after `build_flet_proot_wheel.py` (`.github/workflows/app.yml:141`) · Value: catches a malformed wheel filename / dist-info mismatch before the APK job, and asserts the wheel's version equals the `pyproject.toml:52` pin (F5) · Cost: zero. **Verified to parse the house's two artifacts exactly** (evidence in F5).
- **`packaging.metadata.Metadata.from_email` — validate a hand-written METADATA** · API: `packaging/metadata.py:887`, `InvalidMetadata` at `:46` · Integration point: the same CI step; parse the `METADATA` block that `build_flet_proot_wheel.py:399-412` writes · Value: catches a malformed `Version` / `Requires-Python` / `License-Expression` before it reaches a device · Cost: zero. **Verified to accept the house's exact block** (evidence in F5).
- **`Marker` / `Marker.evaluate` — PEP 508 environment markers** · API: `packaging/markers.py:402`, `:504` · Integration point: (a) the import guard, to assert every declared dependency's marker is true for the target platform; (b) a CI check that the *bundled Android CPython* satisfies the app's `requires-python` floor — the same `SpecifierSet`/`Version` mechanism flet-cli already uses at `flet_cli/utils/python_versions.py:168-183` · Value: turns "the APK runs a Python the source can parse" (F8) into a checked fact · Cost: zero. **Declined for `src/`** (runtime dep).
- **`packaging.tags.sys_tags` / `cpython_tags` / `compatible_tags`** · API: `packaging/tags.py:963` (+ siblings, verified present) · Integration point: a CI check that the wheel tag flet-cli picks for the Android build is one pip accepts · Value: unclear today — the house ships no Python-source wheel of its own, only the `flet_proot` payload wheel, whose platform tag (`py3-none-android_24_arm64_v8a`) is hand-written at `build_flet_proot_wheel.py:183-185` · Cost: zero, but **no proven need** — see *Unverified*.
- **`packaging.dependency_groups.resolve_dependency_groups` (PEP 735) / `packaging.pylock.Pylock`** · API: `packaging/dependency_groups.py:286`, `packaging/pylock.py:670` · Integration point: none found — the house's lock format is `uv.lock`, not `pylock.toml`, and the house's groups are `uv`-style (`pyproject.toml:77-84`) · Value: would let a `pylock.toml` be validated, if the house ever moves off uv · Cost: n/a. **Declined — no fit.**
- **`packaging.licenses.canonicalize_license_expression`** · API: `packaging/licenses/__init__.py:71` · Integration point: the license screen (`src/screens/views.py:565-606`) and the wheel METADATA · Value: normalizing the house's license strings (`GPL-2.0-or-later`, `GPL-3.0`, `BSD-3-Clause`, `Apache-2.0 OR BSD-2-Clause`) to SPDX form · Cost: zero, but the house's license strings are already SPDX-shaped and the screen is display-only · **Declined — no defect to fix.**

## Verified-good list

- **The installed library matches the study.** `packaging` 26.3 at `.venv/Lib/site-packages/packaging/__init__.py:9`; `packaging-26.3.dist-info/METADATA:3,5,8`; lock `uv.lock:506-512`. The study's §1-§4 API inventory is accurate in every checked item: `Version` (`version.py:340`) and its `__init__` (`:408`), `parse` (`:110`), `InvalidVersion` (`:124`), `VERSION_PATTERN` (`:233`), `normalize_pre` (`:89`); `Specifier` (`specifiers.py:220`, ctor `:355`), `SpecifierSet` (`:766`, ctor `:794`), `InvalidSpecifier` (`:122`); `Requirement` (`requirements.py:35`, ctor `:82`) with `.name`/`.specifier`/`.marker`/`.extras`/`.url` set at `:88-98`, `InvalidRequirement` (`:27`); `Marker` (`markers.py:380`, ctor `:402`), `InvalidMarker` (`:61`), `UndefinedComparison` (`:69`), `UndefinedEnvironmentName` (`:78`).
- **The study's pytest call sites are correct.** `_pytest/config/__init__.py:1455` (`from packaging.version import Version`), `:1472-1474` (`InvalidRequirement`, `Requirement`, `Version`), `_pytest/outcomes.py:279`, `_pytest/unittest.py:565` — all four confirmed by grep in the installed tree.
- **The study's flet-cli call sites, previously "unverified", are confirmed** (see F7): `flet_cli/commands/build_base.py:30`/`:2583`; `flet_cli/utils/python_versions.py:23-24`/`:168,180,183,193,197,202`; `flet_cli/commands/flutter_base.py:9`/`:136-137,220-225`.
- **`packaging` is dev-only, provably.** Two dependents, both dev-group (`pytest-9.1.1.dist-info/METADATA:36`, `flet_cli-1.0.4.dist-info/METADATA:15`); `uv.lock:229`, `uv.lock:637` (no markers); `docs/swarm/dependency-tree/uv-tree-inverted.txt:71-74`; the Android resolve of the runtime set is 15 packages and excludes it (resolver proof in §2).
- **The app's shipped-license list is correct.** `src/screens/views.py:26-42` (`_PY_DISTS`) lists exactly the 15 APK-resident distributions; `packaging` is correctly absent.
- **The APK/AAB prune guards need no `packaging/` entry.** The regexes at `.github/workflows/app.yml:168` and `:282` (`pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/`) can never match a `packaging/` tree, because packaging cannot be in the artifact (resolver proof). Adding it would be noise.
- **The runtime update service's *hardening* is good; only its *version comparison* is weak.** `src/services/update_service.py:26-37` (`is_allowed_launch_url` — https-only, exact-or-subdomain host match), `:40-48` (`_safe_text` / `_safe_url` with length caps and fallbacks), `:100-102` (silent failure). The feed is treated as untrusted everywhere **except** in the version comparison (F1).
- **The feed-vs-shipped-build invariant is correctly tested.** `tests/test_version_sync.py:39` (`int(feed["build_number"]) <= APP_BUILD_NUMBER`) correctly encodes "the feed may lead the shipped build" and the `pytest.skip` at `:37` correctly handles the held-back feed (`docs/decisions.md:57`).
- **The CI release-identity gate's *coverage* is right, only its comparison is wrong.** `.github/workflows/app.yml:76-83` correctly cross-checks the four version numbers (workflow input, `core.constants.APP_VERSION`, `core.constants.APP_BUILD_NUMBER`, `tool.flet.build_number`) and `:88-99` correctly models the three feed states (absent / in-sync / behind) — the failure is the comparator, not the model.
- **The build-number pipeline is already coherent.** `pyproject.toml:26` (`build_number = 1`) ≡ `src/core/constants.py:12` (`APP_BUILD_NUMBER = 1`) ≡ `version.json:2` (`"build_number": 1`) ≡ `.github/workflows/app.yml:34` (`BUILD_NUMBER: ${{ inputs.build_number || '1' }}`) — one number, four copies, all currently equal, and CI checks three of the four pairs.
- **The house's `requires-python = ">=3.14"` (`pyproject.toml:8`) is machine-honored by the build**, not hand-honored: flet-cli resolves the bundled CPython with `packaging.specifiers.SpecifierSet` + `packaging.version.Version` (`flet_cli/utils/python_versions.py:168-183`). This is the one place in the repo where a version floor is genuinely enforced by a version library — and it is in the right layer (the build), which is the model the other checks should follow.
- **The payload's *bits* are strongly protected.** `build_flet_proot_wheel.py:202-210` (`_fetch_verified`) enforces the sha256 pins at `:44`/`:48`/`:60`/`:64`/`:76` before anything is written, and `:131-135` enforces 16 KiB PT_LOAD congruence. The payload's *version string* is the unprotected part (F5).
- **flet-cli's use of packaging on the house's own pin is exact.** `flet_cli/commands/build_base.py:2583` parses `flet-proot==5.1.107.98` (`pyproject.toml:52`) with `Requirement(...).name` — a real PEP 508 parse, not a string hack. The house's `[tool.flet.android].dependencies` entry is already in the one place where a version library is guaranteed to read it correctly.
- **The 3.14-only `except` syntax is consistent and currently safe** (F8): four occurrences, all matching the declared floor `>=3.14`.
- **No `src/` module imports `packaging`** — `grep -rn "packaging" src/ tests/ build_flet_proot_wheel.py pyproject.toml version.json` → only `pyproject.toml:48` (`legacy_packaging = true`, an unrelated flet setting) and a prose mention at `build_flet_proot_wheel.py:88`.

## Unverified

- **No APK/AAB was built in this audit** (no Flutter/Android SDK run). "packaging is not in the APK" is a **resolver-level proof** — the exact `pyproject.toml:9-15` requirement strings resolved for `aarch64-linux-android` against `https://pypi.flet.dev`, yielding the 15 names in `src/screens/views.py:26-42` — not an on-device `unzip -l` observation. The house's own colorama audit made the same class of claim (see `docs/swarm/dependency-utilization/colorama.md:179`).
- **The exact CPython that flet-cli selects for the Android build was not determined.** `flet_cli/utils/python_versions.py:29` pins `PYTHON_BUILD_RELEASE_DATE = "20260921"` and the manifest (`python-build/releases/download/20260921/manifest.json`, `:37-39`) was **not fetched** (network fetch of a GitHub release asset was not performed in this audit). Consequently, the claim in F8 that the 3.14-only `except` syntax is safe **on device** rests on `pyproject.toml:8` + flet-cli's `SpecifierSet` selection, not on an observed device interpreter.
- **Whether `flet build apk` would accept the house's hand-written Android platform tag** `py3-none-android_24_arm64_v8a` was not exercised end-to-end. `packaging.utils.parse_wheel_filename` accepts it (verified, F5) and `packaging.tags` exposes `sys_tags`/`cpython_tags`/`compatible_tags` (verified present, `tags.py:963` and siblings), but no Android tag resolution was run and pip's acceptance of the tag on the device was not tested.
- **`packaging.pylock` (`pylock.py:670`) and `packaging.dependency_groups` (`dependency_groups.py:286`) were inventoried but not exercised.** Their names and signatures were confirmed; no `pylock.toml` or PEP 735 group file exists in the repo, and the house locks with `uv.lock`, so no fit was found — but their behavior was not read beyond the public names.
- **`packaging.licenses.canonicalize_license_expression` (`licenses/__init__.py:71`) was not exercised** against the house's license strings (`GPL-2.0-or-later`, `GPL-3.0`, `BSD-3-Clause`, `Apache-2.0 OR BSD-2-Clause`).
- **The `Marker.evaluate` context parameter** (`markers.py:504`, `context="metadata" | "lock_file" | "requirement"`, added in packaging 25.0) was read from source but not exercised; the "declared dependency's marker is true for the target platform" check proposed in *Missed capabilities* was not run.
- **`docs/reference/dep-*.md` were grepped for "packaging" (no house-policy hit) but not read in full** for a version-handling policy; the reference set contains no doc that governs how versions are compared.
- **Whether the owner's next flet bump (D-010, `docs/decisions.md:33-34`) changes flet-cli's `packaging` floor was not re-checked** — today's floor is `packaging>=25.0` (`flet_cli-1.0.4.dist-info/METADATA:15`), and the installed 26.3 satisfies it.
- **The `is_newer` false-positive/missed-update cases were demonstrated by calling the repo's function with synthetic feed versions** (`src/services/update_service.py:58`), not by observing a real feed. The feed is house-authored (`version.json`, `raw.githubusercontent.com` — `src/core/constants.py:17`), so the trigger is a house version-format change, not an attacker.
