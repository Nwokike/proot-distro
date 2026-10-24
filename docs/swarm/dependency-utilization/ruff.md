# ruff 0.17.1 — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `pyproject.toml:79-84,99-117` · `.github/workflows/app.yml:1-58,110-111` · `docs/dependency-studies/ruff.md` · `docs/reference/dep-test-and-lint-stack.md:18-21` · `docs/decisions.md:13` · `.venv/Scripts/ruff.exe` · `.venv/Lib/site-packages/ruff/**` · `.venv/Lib/site-packages/ruff-0.17.1.dist-info/**` · `uv.lock:600-601,618,761-764` · `src/**` (32 modules) · `tests/**` (12 files) · `build_flet_proot_wheel.py` · `docs/requests/mobile-forge-recipe-flet-proot/test.py` · `/home/maikel/.zcode/workspace/default/Sherlock/pyproject.toml:98-124` · **Date:** 2026-10-22

## What it does / how the app uses it

ruff is a **host-only, dev-only** Rust binary that ships zero bytes into the APK.
It is declared once, in the dev group:

```text
$ .venv/Scripts/ruff.exe --version
ruff 0.17.1
```

```text
pyproject.toml:83
    "ruff>=0.17.1",
```

The Python distribution is a thin launcher — the real work is
`../../Scripts/ruff.exe` (`ruff-0.17.1.dist-info/RECORD:1`, 26 MB binary):

```text
.venv/Lib/site-packages/ruff/__init__.py:5
__all__ = ["find_ruff_bin"]
```

```text
.venv/Lib/site-packages/ruff/__main__.py:9-23
def _run() -> None:
    ruff = find_ruff_bin()
    if sys.platform == "win32":
        ...
            completed_process = subprocess.run([ruff, *sys.argv[1:]], check=False)
        ...
        sys.exit(completed_process.returncode)
    else:
        os.execvp(ruff, [ruff, *sys.argv[1:]])
```

```text
.venv/Lib/site-packages/ruff-0.17.1.dist-info/METADATA:3,27
Version: 0.17.1
License-Expression: MIT
```

**What the app actually uses it for:** exactly two commands, in one CI step,
which gates the whole release chain (`prepare-release` needs `quality`,
`app.yml:110-111`):

```text
.github/workflows/app.yml:50-53
      - name: Ruff
        run: |
          uv run ruff check src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
          uv run ruff format --check src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
```

There is **no** local hook, Makefile, tox/nox config or pre-commit config in the
repo (`ls -a` finds none), so ruff runs only in CI. The version is pinned today
by the lock, not by the config:

```text
uv.lock:761-762
name = "ruff"
version = "0.17.1"
```

**The configuration** is a near-verbatim copy of the Sherlock sibling
(`Sherlock/pyproject.toml:98-124`): the same 22-family `select`, the same
10-entry `ignore`, plus five extra `per-file-ignores` for this repo's host-side
CLIs.

```text
pyproject.toml:99-117
[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "W", "UP", "B", "Q", "C4", "PERF", "ERA", "I", "T20", "DTZ", "RUF", "S", "TRY", "BLE", "EM", "A", "SIM", "RET", "RSE"]
ignore = ["E501", "EM101", "EM102", "EM103", "TRY003", "BLE001", "S110", "SIM105", "TRY300", "TRY301"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]
"tests/check_flet_api.py" = ["T201"]
"tests/test_flet_api_guard.py" = ["S603"]
"build_flet_proot_wheel.py" = ["T201", "S310"]
"check_elf_alignment.py" = ["T201"]
"generate_third_party_sources.py" = ["T201", "E402"]
```

**Current compliance: clean.** Run against the committed tree
(`git archive HEAD` into a scratch dir, so the working tree was not touched):

```text
$ ruff check src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
All checks passed!
CHECK_EXIT=0
$ ruff format --check src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
46 files already formatted
FORMAT_EXIT=0
```

Against the working tree as it stands right now the same command **fails**,
because two of the five paths do not exist on disk (see F4).

---

## Findings

### F1 · P2 · `required-version` is never pinned — the lint gate can float on a ruff upgrade

- **Where:** `pyproject.toml:99-101` (`[tool.ruff]`), `pyproject.toml:83` (`ruff>=0.17.1`), `.github/workflows/app.yml:49,52-53`.
- **What:** `required-version` is a valid `[tool.ruff]` key in the installed 0.17.1 but is **not set**. The CI step runs `uv run ruff` (no `--frozen`, no `--no-sync`), and the dependency spec is an open `>=0.17.1`. Nothing in the config says "this gate is a 0.17.1 gate".
- **Evidence:**

```text
$ .venv/Scripts/ruff.exe config | head -14
cache-dir
extend
output-format
output-prefer-rule-codes
fix
unsafe-fixes
fix-only
show-fixes
required-version          <-- valid key, absent from pyproject.toml:99-101
preview
exclude
extend-exclude
extend-include
force-exclude
include
respect-gitignore
extension
builtins
namespace-packages
target-version
```

  The dependency study recommended exactly this, and it was not implemented:

```text
docs/dependency-studies/ruff.md §6.3
3. CI quality job (M5 `build-all.yml`): `uv run ruff check .` then
   `uv run ruff format --check .` before `pytest -m "not live"`; pin
   `required-version = "==0.17.1"` so the gate cannot float.
```

  The house reference says the same in prose:

```text
docs/reference/dep-test-and-lint-stack.md:21
- Run via the locked venv (`uv sync` then `ruff check`) so the version can't float.
```

  Today the lock does the pinning (`uv.lock:761-762` → `ruff 0.17.1`;
  `uv run --no-sync ruff --version` → `ruff 0.17.1`), but that is a property of
  the lockfile, not of the lint configuration.
- **Fix / opportunity:** add one line to `pyproject.toml:99-101`:
  `required-version = "==0.17.1"`. Then a ruff bump fails loudly with a version
  message instead of silently reformatting or re-flagging the tree.
- **Risk if ignored:** ruff's formatter output is version-sensitive. A ruff 0.18
  that reflows one construct makes `ruff format --check` fail on code nobody
  touched, and the failure reads as "someone broke the formatting" rather than
  "the linter moved". Equally, a new stable rule can fire on a PR with no
  reviewer-visible cause.

### F2 · P2 · `S110` is globally ignored, and the single silent-swallow in the tree is on the compliance screen

- **Where:** `src/screens/views.py:595-596`, `src/screens/views.py:609-612`, `pyproject.toml:105` (`S110` in `ignore`).
- **What:** `_native_entries()` swallows **every** exception with a bare `pass`
  and no log. That function feeds `licenses_view()` — the in-app compliance
  §3.3 third-party-provenance list. If `import flet_proot` fails, or the
  wheel manifest shape changes, the native-payload rows silently disappear
  from the licenses screen: no error, no log line, nothing.
- **Evidence:** exactly one `S110` exists in the whole linted surface — this one:

```text
$ ruff check --isolated --target-version py314 --select S --statistics src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
 118	S101	assert
   2	S310	suspicious-url-open-usage
   1	S110	try-except-pass
Found 121 errors.
```

```text
src/screens/views.py:578-597
    try:
        import flet_proot  # type: ignore[import-not-found]
        ...
    except Exception:
        pass
    return entries
```

```text
src/screens/views.py:609-612
def licenses_view() -> ft.Control:
    """Licenses screen content (compliance §3.3). ..."""
    entries = _native_entries() + _py_entries()
```

  Contrast with the app's other broad excepts, which all log — this one is the
  outlier:

```text
src/core/shared_services.py:37-41
        try:
            instance = factory()
        except Exception as exc:
            logger.debug("shared service %s unavailable: %s", key, exc)
            continue
```

- **Fix / opportunity:** narrow the except to `except ImportError:` (and/or
  `except AttributeError:` for a manifest-shape change) and `logger.debug(...)`
  it — matching `shared_services.py:39-41`. The global `S110` ignore can stay
  for the other two benign sites (`src/services/ad_service.py:242-243`,
  `src/services/update_service.py:63-64`); if the team prefers the ignore,
  add a targeted `# noqa: S110 - <reason>` at `views.py:595` instead.
- **Risk if ignored:** a broken or absent native payload silently blanks the
  license provenance section of a shipped app — a compliance-visible
  degradation with zero diagnostic trace, which is exactly the class of defect
  `S110` exists to catch.

### F3 · P2 · The CI lint step hardcodes five paths: one missing file fails the gate, and one real source file is outside it

- **Where:** `.github/workflows/app.yml:52-53`.
- **What:** the lint command is a hand-maintained path list rather than
  `ruff check .`. Two consequences, both reproducible:
  1. **Brittle.** `ruff check` on a path that does not exist is a hard error
     (`E902`), exit 1 — the gate fails on a *missing file*, not on a lint
     defect.
  2. **Incomplete.** `docs/requests/mobile-forge-recipe-flet-proot/test.py` is
     not in the list, so a live Python file in the repo is never linted — and
     it has four real violations.
- **Evidence:** the exact CI command, run in the current working tree, where
  `check_elf_alignment.py` and `generate_third_party_sources.py` are absent
  from disk (they are present in git HEAD — see "Unverified"):

```text
$ ruff check src tests build_flet_proot_wheel.py check_elf_alignment.py generate_third_party_sources.py
E902 The system cannot find the file specified. (os error 2)
--> check_elf_alignment.py:1:1

E902 The system cannot find the file specified. (os error 2)
--> generate_third_party_sources.py:1:1

Found 2 errors.
EXIT=1
```

  On the committed tree the same command is green (quoted in "What it does
  above"), so the CI gate itself is sound — the point is that it is *path
  fragile*.

  The uncovered file does have defects:

```text
$ ruff check docs/requests/mobile-forge-recipe-flet-proot/test.py
docs\requests\mobile-forge-recipe-flet-proot\test.py:19:5: S101 Use of `assert` detected
docs\requests\mobile-forge-recipe-flet-proot\test.py:25:5: S101 Use of `assert` detected
docs\requests\mobile-forge-recipe-flet-proot\test.py:29:9: S101 Use of `assert` detected
docs\requests\mobile-forge-recipe-flet-proot\test.py:33:5: T201 `print` found
Found 4 errors.
1 unsafe fix available with `--fix --unsafe-fixes`.
```

  It is also unformatted:

```text
$ ruff format --diff docs/requests/mobile-forge-recipe-flet-proot/test.py
-        assert align and align >= 0x4000, (
-            f"{lib['jni']}: PT_LOAD align {align!r} < 0x4000 (16 KiB)"
-        )
+        assert align and align >= 0x4000, f"{lib['jni']}: PT_LOAD align {align!r} < 0x4000 (16 KiB)"
```

- **Fix / opportunity:** the natural fix (`ruff check .` +
  `ruff format --check .`) is **not** a drop-in here — see F5. The minimal,
  safe fix is to keep the explicit list and add the missing file plus its
  ignores:

```toml
[tool.ruff.lint.per-file-ignores]
"docs/requests/mobile-forge-recipe-flet-proot/test.py" = ["S101", "T201"]
```

  and append that path to `app.yml:52-53`. Longer term, replace the list with
  `ruff check .` **plus** `[tool.ruff] extend-exclude = ["docs/**"]` and
  `[tool.ruff.format] exclude = ["*.md"]`.
- **Risk if ignored:** every future Python file the team adds outside the four
  listed roots is silently unlinted — the recipe test proves it already
  happened once. And a deleted/renamed host tool breaks CI with "file not
  found" instead of a real diagnostic.

### F4 · P3 · `BLE` and `EM` are selected but contribute exactly zero rules

- **Where:** `pyproject.toml:104-105`.
- **What:** the ruff 0.17.1 catalog has exactly **one** BLE rule and exactly
  **three** EM rules. All four are in this repo's `ignore` list. So the
  `select` entries `"BLE"` and `"EM"` buy nothing — they are pure "allow"
  holes wearing the costume of enforcement.
- **Evidence:** full rule catalog, enumerated from the installed binary:

```text
$ ruff rule --all --output-format json | <count by prefix>
BLE    n=  1 ['BLE001']
EM     n=  3 ['EM101', 'EM102', 'EM103']
```

  And what they would have caught if not ignored:

```text
$ ruff check --isolated --target-version py314 --select BLE,EM --statistics src tests build_flet_proot_wheel.py
 41	BLE001	blind-except
 17	EM102	f-string-in-exception
  5	EM101	raw-string-in-exception
```

  All 63 are neutralised by `pyproject.toml:105`. Note this is **not** a
  mistake in the ignores — it is Sherlock's own owner rule, verbatim:

```text
Sherlock/pyproject.toml:105-108
    # Message-string style: this app raises with inline human messages on
    # purpose (owner rule: visible, specific errors); classes-per-message
    # would be churn with no behavioral gain.
    "EM101", "EM102", "EM103", "TRY003",
```

  I checked the 41 BLE001 sites: they are all deliberate best-effort paths that
  log or degrade cleanly (`src/core/shared_services.py:39-47`,
  `src/services/ad_service.py:86-222`, `src/app_controller.py:104-407`,
  `src/screens/views.py:568`). The ignores are justified; the *selection* is
  the redundant part.
- **Fix / opportunity:** either drop `"BLE"`/`"EM"` from `select` and keep the
  ignores as documentation of intent (the ignores alone still work — an ignored
  rule that was never selected is harmless), or keep them and add a comment
  saying they are intentionally fully suppressed. Do **not** un-ignore BLE001
  without narrowing 41 sites first.
- **Risk if ignored:** low direct impact, but the config overstates its own
  coverage. A reviewer who widens `ignore` later has no signal that these two
  families were already switched off.

### F5 · P3 · A bare `ruff format` at the repo root rewrites 29 documentation files

- **Where:** `pyproject.toml:99-101` (no `[tool.ruff.format]` `exclude`), `pyproject.toml:99` (no `extend-exclude`).
- **What:** ruff 0.17.1 formats Python code blocks **inside Markdown files**.
  `ruff format` with no arguments defaults to `.`
  (`ruff format --help`: `[FILES]...  files/dirs or `-` for stdin [default: .]`),
  so a developer running the obvious command in the repo root silently rewrites
  the house dependency studies.
- **Evidence:** on the committed tree, `ruff format --check .` reports 29 files
  it would change — 28 Markdown documents plus the one uncovered `.py`:

```text
$ ruff format --check .
unformatted: File would be reformatted
  --> docs\dependency-studies\arrow.md:33:1
   |
32 | import arrow
33 +
34 | stamp = arrow.now("Africa/Lagos").format("YYYY-MM-DD HH:mm:ssZZ")
   |

... 29 files total:
docs/dependency-studies/{arrow,certifi,chardet,click,colorama,cookiecutter,flet-ads,
  flet-platform-assets,flet-terminal,httpx,idna,jinja2,markdown-it-py,markupsafe,mdurl,
  msgpack,pluggy,pygments,pytest-timeout,python-dateutil,python-slugify,pyyaml,rich,
  text-unidecode,tzdata,urllib3,watchdog}.md
docs/requests/mobile-forge-recipe-flet-proot/test.py
docs/testing-findings.md
```

  The CI path list is what currently shields the docs — which is why F3's
  "just use `ruff check .`" needs the `exclude` to land with it.
- **Fix / opportunity:** add to `pyproject.toml`:

```toml
[tool.ruff.format]
exclude = ["*.md"]
```

  (`exclude` is a valid `[tool.ruff.format]` key — confirmed by
  `ruff config format`, which lists `exclude` among the format keys.) Optionally
  also `[tool.ruff] extend-exclude = ["docs/**"]` to keep `ruff check .` sane.
- **Risk if ignored:** a routine `ruff format` mutates 28 house reference
  documents with no diff review; and the first person to "modernise" the CI
  path list to `.` gets a 29-file CI failure that looks like a lint regression.

### F6 · P3 · `ARG` is the one omitted family with a real hit — a dead parameter in the copy-path dialog

- **Where:** `src/screens/views.py:210`, `src/screens/views.py:175-176`, `src/screens/views.py:222-226`.
- **What:** `_ask_copy(container: str)` receives the container it was opened
  from and never uses it. The user must type `container:/path` by hand into
  the source field, even though the app already knows the container.
- **Evidence:**

```text
$ ruff check --isolated --target-version py314 --select ARG --output-format concise src
src\screens\views.py:210:23: ARG001 Unused function argument: `container`
```

```text
src/screens/views.py:175-176
            def _copy(_e) -> None:
                _ask_copy(container)

src/screens/views.py:210-213
        def _ask_copy(container: str) -> None:
            source = ft.TextField(hint_text="source (container:/path)", text_size=12)
            destination = ft.TextField(hint_text="destination (container:/path)", text_size=12)
```

  The other 10 ARG hits are benign: 3 in `build_flet_proot_wheel.py` (callback
  signatures for a fixed interface) and 7 in `tests/test_sessions.py` (pytest
  lambda/parametrisation placeholders).
- **Fix / opportunity:** prefill the source field with `f"{container}:/"` and
  use the container in the dialog title (mirroring `_ask_rename`, which does
  `value=container` at `views.py:193` and `f"Rename {container}"` at
  `views.py:201`), or drop the parameter. Selecting `ARG` permanently is not
  justified — the family would need 11 ignores to be usable — but this one hit
  is worth acting on directly.
- **Risk if ignored:** small but real UX friction; the app asks the user to
  retype information it already has, on a path (copy a path between
  containers) where a typo produces a confusing proot error.

### F7 · P3 · `"tests/test_flet_api_guard.py" = ["S603"]` is dead configuration

- **Where:** `pyproject.toml:112`.
- **What:** the per-file ignore suppresses `S603` (`subprocess-without-shell-equals-true`)
  for a file that never touches `subprocess`.
- **Evidence:** the whole file (46 lines) imports only `importlib.util`, `sys`
  and `pathlib`; it loads the guard with `importlib.util.spec_from_file_location`
  and calls `guard.main()` in-process:

```text
tests/test_flet_api_guard.py:9-11
import importlib.util
import sys
from pathlib import Path
```

```text
$ grep -rn "subprocess" src tests build_flet_proot_wheel.py
src\core\proot_probe.py:6:import subprocess
src\core\proot_probe.py:116:        proc = subprocess.run(  # noqa: S603 - ...
src\services\session_service.py:21:import subprocess
src\services\session_service.py:101:        self._process = subprocess.Popen(  # noqa: S603 - ...
```

  The two real `S603` sites are in `src/` and are handled with inline
  `# noqa` comments (`src/core/proot_probe.py:116`,
  `src/services/session_service.py:101`) — not by a per-file ignore.
- **Fix / opportunity:** delete `pyproject.toml:112`, or keep it with a
  comment that it is forward-looking for a future subprocess-based guard test.
  Every other per-file-ignore entry is load-bearing — verified by re-running
  each file with `--isolated` and the project's `select` list:
  `check_elf_alignment.py` → 6× T201; `generate_third_party_sources.py` →
  2× E402 + T201; `build_flet_proot_wheel.py` → T201 + 2× S310;
  `tests/check_flet_api.py` → 3× T201.
- **Risk if ignored:** low. It inflates the perceived coverage of the config
  and makes the next reader hunt for the subprocess call that is not there.

### F8 · P3 · `target-version = "py314"` is correct here — but the house reference still says `py313`, and `py313` would break the gate

- **Where:** `pyproject.toml:101`, `docs/reference/dep-test-and-lint-stack.md:20`, `docs/dependency-studies/ruff.md` §6.1.
- **What:** the project uses **PEP 758** syntax (`except A, B:` without
  parentheses), which is new in Python 3.14. The project's `py314` is
  *required*, not a preference — and it deliberately diverges from the house
  reference and from the dependency study, both of which prescribe `py313`.
- **Evidence:**

```text
src/services/update_service.py:60-64
    try:
        if int(remote_build) > APP_BUILD_NUMBER:
            return True
    except TypeError, ValueError:
        pass
```

```text
$ ruff check --isolated --target-version py313 --select E9,F src/services/update_service.py
invalid-syntax: Multiple exception types must be parenthesized on Python 3.13 (syntax was added in Python 3.14)
  --> src\services\update_service.py:63:12
   |
61 |         if int(remote_build) > APP_BUILD_NUMBER:
62 |             return True
63 |     except TypeError, ValueError:
   |            ^^^^^^^^^^^^^^^^^^^^^
Found 1 error.
EXIT=1
```

  With the project's own `py314` setting the file passes
  (`ruff check src/services/update_service.py` → `All checks passed!`).

  The stale prescriptions:

```text
docs/reference/dep-test-and-lint-stack.md:20
- All house keys valid at this version: `target-version = "py313"`, full select list, ...

docs/dependency-studies/ruff.md §6.1
1. Add a `[tool.ruff]` + ... block to our `pyproject.toml` modeled on Sherlock
   (richest set above), with `line-length = 100` + `target-version = "py313"`
```

  The AST verifier is **not** affected — it parses with the running
  interpreter and no `feature_version` pin:

```text
tests/check_flet_api.py:61
    tree = ast.parse(target.read_text(encoding="utf-8"))
```

  and `py_compile` on the file succeeds under 3.14.7 (exit 0).
- **Fix / opportunity:** update `docs/reference/dep-test-and-lint-stack.md:20`
  to `py314` and annotate `docs/dependency-studies/ruff.md` §6.1 with the
  PEP 758 reason. The pyproject itself needs no change.
- **Risk if ignored:** an agent or contributor "restores" `py313` per the
  study/reference and the entire lint gate fails with an "invalid-syntax"
  error that looks like a code corruption rather than a config value.

### F9 · P3 · `preview` is off — and the one preview rule with a hit is a false positive, so this is correctly closed

- **Where:** `pyproject.toml:99-101` (no `preview`), `src/state/controller_ctx.py:19`.
- **What:** 139 of the 971 rules in 0.17.1 are preview, and 87 of them sit
  inside families this repo already selects. Turning `preview` on wholesale
  would be reckless; the question is whether any specific preview rule is worth
  having. The answer for this codebase is no.
- **Evidence:** the highest-value preview rules, run against the whole linted
  surface, produce exactly one hit:

```text
$ ruff check --isolated --preview --target-version py314 \
    --select RUF029,RUF047,RUF050,RUF055,RUF056,RUF069,RUF072,RUF075,RUF052,RUF065,RUF045,RUF038,RUF031,RUF027,UP048,UP052,UP051,RUF039,RUF054 \
    --output-format concise src tests build_flet_proot_wheel.py
src\state\controller_ctx.py:19:11: unused-async: Function `_noop_async` is declared `async`, but doesn't `await` or use `async` features.
Found 1 error.
```

  That hit is a **false positive**: `_noop_async` is the deliberate async
  no-op default for `Callable[..., Awaitable[None]]` fields in the controller
  bridge — it must be awaitable so the real implementation can replace it.

```text
src/state/controller_ctx.py:15-20
def _noop() -> None:
    return None


async def _noop_async(*_args, **_kwargs) -> None:
    return None
```

```text
src/state/controller_ctx.py:26
    refresh_containers: Callable[[], Awaitable[None]] = _noop_async
```

  Two API facts verified for the record, because the dependency study left
  them open:
  - `explicit-preview-rules` is a **boolean**, not a list:

```text
ruff failed
  Cause: TOML parse error at line 3, column 26
explicit-preview-rules = ["RUF055"]
                          ^^^^^^^^^^^
invalid type: sequence, expected a boolean
```

  - it has no effect unless `preview = true` is also set:

```text
$ ruff check .   # preview=false, explicit-preview-rules=true
warning: Selection `RUF055` has no effect because preview is not enabled.
```

- **Fix / opportunity:** none. Keep `preview` off. If a preview rule is ever
  wanted, set `preview = true` **and** `explicit-preview-rules = true` and
  name the rule explicitly.
- **Risk if ignored:** none today. Recorded so the synthesis does not
  re-investigate it.

### F10 · P3 · `N` (pep8-naming) and `PLC0415` must stay omitted — verified

- **Where:** `src/app_shell.py:42`, `src/screens/views.py:74`, `src/screens/terminal_view.py:60`, `src/services/proot_service.py:37`.
- **What:** two omitted families would produce pure noise on this codebase.
  Recording the evidence so the synthesis does not propose them.
- **Evidence:** `N` flags the `@ft.component` classes as non-lowercase:

```text
$ ruff check --isolated --target-version py314 --select N --output-format concise src
src\app_shell.py:42:5: N802 Function name `AppShell` should be lowercase
src\components\app_header.py:98:5: N802 Function name `AppHeader` should be lowercase
src\screens\onboarding_view.py:38:5: N802 Function name `OnboardingView` should be lowercase
src\screens\terminal_view.py:60:5: N802 Function name `TerminalView` should be lowercase
src\screens\terminal_view.py:232:5: N802 Function name `SessionSelectorView` should be lowercase
src\screens\views.py:74:5: N802 Function name `DistroView` should be lowercase
src\screens\views.py:386:5: N802 Function name `SettingsView` should be lowercase
src\services\proot_service.py:21:7: N818 Exception name `ProotUnavailable` should be named with an Error suffix
```

  `PLC0415` fires 69 times — all deferred `import flet as ft` inside component
  functions, a deliberate house pattern (69 hits; `src/` alone: 20):

```text
src\services\proot_service.py:37:5: PLC0415 `import` should be at the top-level of a file
src\screens\views.py:579:9: PLC0415 `import` should be at the top-level of a file
```

  Critically, those deferred imports are **not** masking an import cycle. The
  unused-but-valuable `ruff analyze graph` subcommand proves it:

```text
$ ruff analyze graph src
warning: `ruff analyze graph` is experimental and may change without warning
{ "src\\app_controller.py": [ ... ], ... }
```

  Graph over all 32 `src/` modules, **0 cycles found** — and the graph *does*
  include function-local imports (`src/services/proot_service.py:37` is a
  function-local `from core import posixdb`, and `src/core/posixdb.py` appears
  in its dependency list).
- **Fix / opportunity:** none — do not select `N` or `PL`.
- **Risk if ignored:** a future "enable more rules" proposal that includes `N`
  or `PL` would demand renaming every Flet component class and hoisting 69
  deliberate lazy imports.

---

## Missed capabilities

1. **`required-version = "==0.17.1"`** — valid `[tool.ruff]` key in 0.17.1
   (`ruff config` → `required-version`), recommended verbatim by
   `docs/dependency-studies/ruff.md` §6.3, absent from `pyproject.toml:99-101`.
   Cost: one line. Value: the CI gate cannot drift silently. (F1)
2. **`[tool.ruff.format] exclude = ["*.md"]`** — key verified present via
   `ruff config format`. Prevents ruff 0.17.1's Markdown-code-block formatting
   from rewriting 28 house documents on a bare `ruff format`, and makes
   `ruff format --check .` safe to adopt. Cost: two lines. Value: removes the
   trap that currently forces a hand-maintained path list. (F5)
3. **`ruff check .` + `extend-exclude`** — replaces the five hardcoded paths in
   `app.yml:52-53` with a self-maintaining surface. Requires (2) to be safe
   and the `docs/requests/.../test.py` per-file-ignore to be added. Cost: a
   config edit plus one ignore line. Value: new Python files are linted by
   default. (F3)
4. **`ruff analyze graph`** — a working, already-shipped import-graph
   generator (`ruff analyze graph src` → 32 modules, 0 cycles). Unused by the
   app and by CI. Value: a cheap guard against the cycle that the 69 deferred
   imports could otherwise hide. Cost: one CI step or a manual check.
5. **`ruff server`** — the LSP entry point (`ruff server --help` verified: runs
   the language server, with `--untrusted-workspace` and `--preview` flags).
   The dependency study §6.4 recommended documenting it for the VSCode
   extension; no doc mentions it. Value: format-on-save + fix actions against
   the *same* config as CI, so local and CI cannot drift. Cost: a doc line.
6. **`ruff rule <CODE>` / `ruff config <dotted.key>`** — self-documenting
   introspection. `ruff config lint.select` **does** explain a single dotted
   key (the dependency study marked this "Unverified" — it is now verified):

```text
$ ruff config lint.select
A list of rule codes or prefixes to enable. Prefixes can specify exact
rules (like `F841`), entire groups (like `F`), or anything in
between.
```

   Value: the next agent can answer "why is E501 ignored?" without the docs.
   Cost: none. Low value for the app; worth knowing.

---

## Verified-good list

- **Installed version is exactly 0.17.1** — `.venv/Scripts/ruff.exe --version`
  → `ruff 0.17.1`; `ruff-0.17.1.dist-info/METADATA:3` → `Version: 0.17.1`;
  `RECORD:1` → `../../Scripts/ruff.exe` (the real 26 MB binary). The Python
  package is a launcher only (`ruff/__init__.py:5`, `ruff/__main__.py:9-23`,
  `ruff/_find_ruff.py:11-55`). No runtime dependency, zero APK impact.
- **The CI lint gate is green on the committed tree** — the exact two commands
  from `app.yml:52-53` run against `git archive HEAD` → `All checks passed!`
  (exit 0) and `46 files already formatted` (exit 0).
- **The gate blocks the release chain** — `prepare-release: needs: [quality]`
  (`app.yml:110-111`), and `apk`/`aab` need `prepare-release`
  (`app.yml:130,184`). A lint failure stops the APK/AAB.
- **The version is pinned by the lockfile today** — `uv.lock:761-762` →
  `ruff 0.17.1`; `uv run --no-sync ruff --version` → `ruff 0.17.1`.
- **`target-version = "py314"` is correct and load-bearing** — the app uses
  PEP 758 syntax at `src/services/update_service.py:63`; `--target-version
  py313` makes ruff report `invalid-syntax` on that file (F8). The choice
  matches `requires-python = ">=3.14"` (`pyproject.toml:8`).
- **`line-length = 100` matches the formatter** — `ruff format --check` passes
  at 100 and the repo has 11 lines over 100 chars, all of them comments or
  unsplittable string literals (e.g. `src/components/ui.py:47-49`,
  `src/core/posixdb.py:11`, `build_flet_proot_wheel.py:207,351,384,403`).
  `E501` is ignored, so those are accepted, not hidden defects.
- **Every per-file-ignore is load-bearing except one** — verified by
  re-running each target with `--isolated` + the project's `select`:
  `check_elf_alignment.py` (6× T201), `generate_third_party_sources.py`
  (2× E402 + T201), `build_flet_proot_wheel.py` (T201 + 2× S310),
  `tests/check_flet_api.py` (3× T201). Only `tests/test_flet_api_guard.py`
  `S603` is dead (F7).
- **The three inline `# noqa` directives are all live and all justified** —
  `src/core/posixdb.py:11` (`S105`, a passwd *field-name* string),
  `src/core/proot_probe.py:116` and `src/services/session_service.py:101`
  (`S603`, our own staged payload / upstream's login argv). `RUF100` confirms
  none is stale: with the project's config, `ruff check src` passes; only an
  isolated `--select RUF` run (without `S`) reports them as unused.
- **The app has no `print` in `src/`** — `T20` is selected and `src/` is clean;
  all 26 `T201` hits are in host-side CLIs, all covered by per-file-ignores.
- **No debugger statements** — `grep -rnE "\bbreakpoint\(\)|\bpdb\.set_trace|import pdb"`
  over `src/` and `tests/` → no hits, so the omitted `T10` family costs nothing
  today.
- **The omitted `ASYNC` and `PTH` families would find nothing** — 0 hits each
  across `src`, `tests` and `build_flet_proot_wheel.py` (measured with
  `--isolated --select ASYNC` and `--select PTH`). The dependency study §6.2
  recommended adding both; on this codebase they are no-ops.
- **No import cycles** — `ruff analyze graph src` → 32 modules, 0 cycles
  (the graph includes function-local imports).
- **The rule selection matches Sherlock's byte for byte**
  (`Sherlock/pyproject.toml:99-102` vs `pyproject.toml:104`), and the ignore
  set is Sherlock's (`Sherlock/pyproject.toml:103-117` vs `pyproject.toml:105`)
  plus the five repo-specific per-file-ignores. The house house-style
  rationale is carried over verbatim and still applies.
- **The "no new packages" constraint (D-003) is respected** —
  `docs/decisions.md:13` lists `ruff` among the dev dependencies; every
  opportunity above is a configuration change to an already-shipped binary.

---

## Unverified

- **The working tree is missing `check_elf_alignment.py`,
  `generate_third_party_sources.py`, `LICENSES/*`, `THIRD-PARTY-SOURCES.md`,
  `src/LICENSES/*`, `docs/roadmap.md`, `docs/release-runbook.md`,
  `docs/compliance/*` and `docs/testing-findings.md`** — `git status
  --porcelain` reports them as unstaged deletions (` D ...`), while
  `git ls-files` and `git show HEAD:<path>` confirm they are tracked and
  present in HEAD. I did **not** restore or modify them (BRIEF rule 1). The
  F3 E902 output above was produced against that state; on HEAD the same
  command is green. Whether the deletion is an intentional environment prune
  or an accident is outside this audit's remit.
- **The `ffmpeg` sibling cited by the dependency study no longer exists** —
  `ls /home/maikel/.zcode/workspace/default/ffmpeg` → *No such file or
  directory*. The study's claims about `ffmpeg/pyproject.toml`'s
  `[tool.ruff] line-length = 100` / `target-version = "py313"` (study §2, §3,
  §6.1) could not be re-verified against that file. Our repo's `line-length =
  100` is independently verified above (ruff format passes at 100).
- **The dependency study's claim that `ruff check --show-settings` was empty
  in its harness** did not reproduce here — `ruff check --show-settings
  src/services/update_service.py` prints the full resolved settings
  (`linter.project_root`, `linter.rules.enabled`, `linter.per_file_ignores`,
  `linter.unresolved_target_version = 3.14`, `linter.preview = disabled`,
  `linter.line_length = 100`, `linter.src = [<root>, <root>/src]`). The study's
  "default-select rule set is unverified" note therefore still stands for the
  *defaults*, but the settings dump is now available for inspection.
- **`ruff server`'s transport/protocol details** (stdio, LSP capabilities)
  were not exercised — only `ruff server --help` was run. The study also
  marked these unverified.
- **`ruff analyze graph` is flagged experimental** by the binary itself
  (`warning: ruff analyze graph is experimental and may change without
  warning`); the 0-cycle result is a snapshot of 0.17.1, not a contract.
- **`ruff config <dotted-key>` was verified only for `lint.select`** — the
  dependency study's blanket "Unverified" note is narrowed, not lifted, for
  every other key.
- **Whether the `S110` fix in F2 is the owner's intent** — the Sherlock owner
  rule ("silent best-effort no-ops are the documented owner pattern") argues
  for leaving the global ignore in place. The narrow finding is that
  `src/screens/views.py:595` is the one site in this repo where the silence
  has a user-visible compliance consequence; whether to log it or to leave it
  is an owner call, not a lint call.
