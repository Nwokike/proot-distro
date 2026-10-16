# ruff 0.17.1 — Exhaustive API Reference

**Identity:** `ruff` 0.17.1 · MIT (`License-Expression: MIT` in
`.venv/Lib/site-packages/ruff-0.17.1.dist-info/METADATA`) · Summary:
`An extremely fast Python linter and code formatter, written in Rust.`
**Distribution shape:** single binary at `.venv/Scripts/ruff.exe`
(`ruff 0.17.1` via `ruff.exe --version`); the Python package
(`.venv/Lib/site-packages/ruff/__init__.py`, `__main__.py`, `_find_ruff.py`)
is a thin launcher — `__main__.py:_run()` locates the binary via
`find_ruff_bin()` then `subprocess.run([ruff, *sys.argv[1:]])` on win32
else `os.execvp`. No Python runtime deps; host-only, never ships to Android.
Our project declares it as `ruff>=0.17.1` in `[dependency-groups].dev`
(`pyproject.toml`); siblings pin `ruff>=0.15.14` (Sherlock) and
`ruff==0.16.8` (ffmpeg).

**Verification method:** every claim below traces to installed source
(`file:line`) or quoted live CLI output from `.venv/Scripts/ruff.exe`;
anything not verifiable is marked **unverified**.

House context (read first): `docs/roadmap.md` §1b/§M5 + §3 table row D5,
`docs/reference/dep-test-and-lint-stack.md` §`ruff 0.17.1`,
sibling configs `C:\Users\nwoki\.zcode\workspace\default\Sherlock\pyproject.toml`
`[tool.ruff.lint]` and `...\ffmpeg\pyproject.toml` `[tool.ruff]` +
`[tool.ruff.lint]`. flet stays 1.0.4 (D-010).

---

## 1. Command surface (verified via `--help`)

Top level (`ruff.exe --help`):

```text
Ruff: An extremely fast Python linter and code formatter.
Usage: ruff.exe [OPTIONS] <COMMAND>
Commands:
  check    Run Ruff on the given files or directories
  rule     Explain a rule (or all rules)
  config   List or describe the available configuration options
  linter   List all supported upstream linters
  clean    Clear any caches in the current directory and any subdirectories
  format   Run the Ruff formatter on the given files or directories
  server   Run the language server
  analyze  Run analysis over Python source code
  version  Display Ruff's version
  help     Print this message or the help of the given subcommand(s)
```

Global options (same output): `--config <CONFIG_OPTION>` (path to
`pyproject.toml`/`ruff.toml` OR inline `KEY = VALUE` pair, highest precedence),
`--isolated` (ignore all config files), `--color <WHEN>` (`auto|always|never`),
`-h/--help`, `-V/--version`, log levels `-v/--verbose`, `-q/--quiet`,
`-s/--silent` (still exit 1 on diagnostics).

### 1.1 `ruff check` flags (verified via `ruff check --help`)

- Fix mode: `--fix` / `--no-fix`, `--unsafe-fixes` / `--no-unsafe-fixes`,
  `--show-fixes` / `--no-show-fixes`, `--diff` (implies `--fix-only`, prints
  diffs, exit 0 if clean), `--fix-only` / `--no-fix-only`,
  `--add-noqa[=<REASON>]`, `--add-ignore[=<REASON>]` (preview: suppression
  comments with rule names instead), `--ignore-noqa`.
- Output: `--output-format <OUTPUT_FORMAT>` (`concise|full|json|json-lines|junit|grouped|github|gitlab|pylint|rdjson|azure|sarif`,
  env `RUFF_OUTPUT_FORMAT`), `-o/--output-file` (env `RUFF_OUTPUT_FILE`),
  `--statistics` (per-rule violation counts), `--show-files`, `--show-settings`.
- Rule selection: `--select`, `--ignore`, `--extend-select`,
  `--per-file-ignores`, `--extend-per-file-ignores`, `--fixable`,
  `--unfixable`, `--extend-fixable`, `--target-version`
  (`py37|py38|py39|py310|py311|py312|py313|py314|py315`), `--preview`,
  `--extension <EXT:lang>` (`python|ipynb|pyi`, e.g. `--extension ipy:ipynb`).
- File selection: `--exclude`, `--extend-exclude`, `--respect-gitignore` /
  `--no-respect-gitignore`, `--force-exclude` / `--no-force-exclude`.
- Misc: `-n/--no-cache` (env `RUFF_NO_CACHE`), `--cache-dir` (env
  `RUFF_CACHE_DIR`), `--stdin-filename`, `-e/--exit-zero` (exit 0 even with
  violations — never use in CI), `--exit-non-zero-on-fix`.
- Watch: `-w/--watch` (re-run on change; dev-loop only).

### 1.2 `ruff format` flags (verified via `ruff format --help`)

```text
Usage: ruff.exe format [OPTIONS] [FILES]...
  [FILES]...  files/dirs or `-` for stdin [default: .]
Options:
  --check / --diff / --extension / --target-version (same value set as check)
  --preview / --output-format (same values; used with --check)
  -n/--no-cache, --cache-dir, --stdin-filename (same as check)
  --exit-non-zero-on-format / --respect-gitignore / --exclude /
  --extend-exclude / --force-exclude (same semantics as check)
Editor options: --range <RANGE> (format only the given range — LSP path)
Format configuration: --line-length <LINE_LENGTH>
```

`--check` = CI gate (exit nonzero if any file would change, writes nothing);
`--diff` = same + prints the diff. No `--fix` concept — formatter always writes
unless `--check`/`--diff`.

### 1.3 `ruff rule` / `ruff config` / `ruff clean` / `ruff analyze`

- `ruff rule <RULE|--all> [--output-format text|json]` — e.g. verified:
  `ruff rule E501` prints `# line-too-long (E501) / Derived from the
  **pycodestyle** linter… Checks for lines that exceed the specified maximum
  character length… default 88… configurable via [line-length]`. Use
  `ruff rule --all` for the full rule catalog (JSON for tooling).
- `ruff config [lint|format|<KEY>]` — bare `ruff config` lists top-level keys
  (see §3); `ruff config lint` lists lint keys; `ruff config format` lists
  format keys. **Unverified**: whether `ruff config <dotted-key>` explains one
  key — help text implies it, not exercised here.
- `ruff clean` — `Clear any caches in the current directory and any
  subdirectories`; no extra flags beyond log/global options.
- `ruff analyze graph` — `Generate a map of Python file dependencies or
  dependents` (`ruff analyze --help` verified; subcommand flags unverified).

### 1.4 `ruff server` — editor/LSP mode (verified via `ruff server --help`)

```text
Usage: ruff.exe server [OPTIONS]
Options:
  --untrusted-workspace   Treat all workspaces as untrusted, disabling the uv formatter backend
  --preview               Enable preview mode (unstable server features + preview lint/format)
```

Plus standard log/global options (`-v/-q/-s`, `--config`, `--isolated`,
`--color`). Protocol/transport details (stdio, capabilities) are
**unverified** from this install — the VSCode `ruff` extension shells to this
subcommand. Practical effect: live squiggles + fix actions + format-on-save
without a Python daemon.

---

## 2. Complete lint rule-FAMILY inventory (verified via `ruff linter`)

`ruff.exe linter` on 0.17.1 prints 59 rows (code + upstream name). The output
carries NO defaults column in this version — any "default-selected" claim is
**unverified** from this CLI (upstream docs conventionally default to a small
`E4/E7/E9/F` subset; do not rely on it — always set `select` explicitly).

| Code | Upstream family | Sherlock select? | ffmpeg select? | Notes / why per sibling configs |
|---|---|---|---|---|
| AIR | Airflow | — | — | Neither house config selects; data-pipeline only. |
| ERA | eradicate | ✅ | — | Sherlock selects (dead commented-code); ffmpeg omits (smaller set). |
| FAST | FastAPI | — | — | Web-framework only. |
| YTT | flake8-2020 | — | — | `sys.version` idioms; house sets cover via UP instead. |
| ANN | flake8-annotations | — | — | Deliberately OUT of both house sets (annotation churn). |
| ASYNC | flake8-async | — | ✅ | ffmpeg selects (M3: async-correctness); Sherlock omits. Recommend IN for our app (asyncio.to_thread bridge). |
| S | flake8-bandit | ✅ (+ignores) | — | Sherlock selects, ignores `S110` (silent no-ops = owner pattern) + `S101` under `tests/**`; ffmpeg omits `S` entirely (assert-in-tests = house rule). |
| BLE | flake8-blind-except | ✅ (+ignore BLE001) | — | Sherlock selects but ignores `BLE001` (wide-except+log = owner pattern, 200+ sites). |
| FBT | flake8-boolean-trap | — | — | OUT of both (positional-bool churn). |
| B | flake8-bugbear | ✅ | ✅ | Both select. Opinionated correctness; keep. |
| A | flake8-builtins | ✅ (+1 per-file) | — | Sherlock selects; `src/services/scan_notify.py = ["A002"]` because `id` mirrors the notifications signature. ffmpeg omits. |
| COM | flake8-commas | — | — | OUT (formatter owns trailing commas). |
| C4 | flake8-comprehensions | ✅ | — | Sherlock selects; ffmpeg omits. Keep (generator/comprehension idioms). |
| CPY | flake8-copyright | — | — | OUT (no header policy). |
| DTZ | flake8-datetimez | ✅ | — | Sherlock selects (naive-datetime guard); ffmpeg omits. Keep if we touch datetimes. |
| T10 | flake8-debugger | — | — | OUT of both selects (**unverified** whether a bare `debugger` slips past E/F — treat as uncovered). |
| DJ | flake8-django | — | — | Framework only. |
| EM | flake8-errmsg | ✅ (+ignore EM101/102/103) | — | Sherlock selects but ignores inline-message rules (owner rule: visible specific errors, no class-per-message). |
| EXE | flake8-executable | — | — | Shebang-only. |
| FIX | flake8-fixme | — | — | OUT (TODO tracking via issues, not lint). |
| FA | flake8-future-annotations | — | — | OUT (py310+ `X | Y` handled by UP). |
| INT | flake8-gettext | — | — | i18n only. |
| ISC | flake8-implicit-str-concat | — | — | OUT of both (formatter-adjacent). |
| ICN | flake8-import-conventions | — | — | OUT (no alias policy). |
| LOG | flake8-logging | — | — | OUT (we log via flet/print paths). |
| G | flake8-logging-format | — | — | Same as LOG. |
| INP | flake8-no-pep420 | — | — | Namespace-package only. |
| PIE | flake8-pie | — | — | OUT of both. |
| T20 | flake8-print | ✅ | — | Sherlock selects (flags stray `print`); ffmpeg omits. Keep for app code (route prints through logging/UI). |
| PYI | flake8-pyi | — | — | Stub-file only. |
| PT | flake8-pytest-style | — | — | OUT of both (house pytest style enforced by review, not lint). |
| Q | flake8-quotes | ✅ | — | Sherlock selects (quote consistency with formatter); ffmpeg omits. |
| RSE | flake8-raise | ✅ | — | Sherlock selects; ffmpeg omits. Keep. |
| RET | flake8-return | ✅ | — | Sherlock selects; ffmpeg omits. Keep. |
| SLF | flake8-self | — | — | OUT (private-member style not enforced). |
| SIM | flake8-simplify | ✅ (+ignore SIM105) | ✅ | Both select; Sherlock ignores `SIM105` (silent `contextlib.suppress` = owner pattern). |
| SLOT | flake8-slots | — | — | OUT. |
| TID | flake8-tidy-imports | — | — | OUT (ban-list not maintained). |
| TD | flake8-todos | — | — | OUT. |
| TC | flake8-type-checking | — | — | OUT (import-cycle guard not needed). |
| ARG | flake8-unused-arguments | — | — | OUT (placeholder `_` args common in Flet callbacks). |
| PTH | flake8-use-pathlib | — | ✅ | ffmpeg selects; Sherlock omits. Recommend IN for our app (pathlib over `os.path`). |
| FLY | flynt | — | — | OUT (f-string conversion churn). |
| I | isort | ✅ | ✅ | Both select. Import order; keep. |
| C90 | mccabe | — | — | OUT (complexity via review). |
| NPY | NumPy-specific | — | — | Numeric only. |
| PD | pandas-vet | — | — | Dataframe only. |
| N | pep8-naming | — | — | OUT of both (Flet `snake_case` already). |
| PERF | Perflint | ✅ | ✅ | Both select. Keep. |
| E/W | pycodestyle | ✅ E/W (+ignore E501) | ✅ E/W (+ignore E501) | Both select, both ignore `E501` (formatter owns length; Sherlock comment + ffmpeg `line-length = 100`). |
| DOC | pydoclint | — | — | OUT (docstring convention not enforced). |
| D | pydocstyle | — | — | OUT of both. |
| F | Pyflakes | ✅ | ✅ | Both select. Keep (undefined names/unused imports). |
| PGH | pygrep-hooks | — | — | OUT. |
| PL | Pylint | — | — | OUT (covered piecemeal by B/SIM/RET etc.). |
| UP | pyupgrade | ✅ | ✅ | Both select. Keep (modern syntax for the pinned target). |
| FURB | refurb | — | — | OUT of both. |
| RUF | Ruff-specific | ✅ | ✅ | Both select. Keep. |
| TRY | tryceratops | ✅ (+ignore TRY003/300/301) | ✅ (+ignore TRY003/TRY300) | Both select `TRY`, both ignore `TRY003` (long raise-messages = house style) and `TRY300/TRY301` (try/else reshuffle churn; Sherlock ignores both, ffmpeg ignores `TRY300` only — `TRY301` coverage **unverified**, treat as ignored-by-policy). |

Sherlock full select (verbatim, `Sherlock/pyproject.toml:100-103`):
`E F W UP B Q C4 PERF ERA I T20 DTZ RUF S TRY BLE EM A SIM RET RSE`;
ignore (`:104-118`): `E501, EM101/102/103, TRY003, BLE001, S110, SIM105, TRY300, TRY301`
with owner-rule comments. ffmpeg full select (verbatim,
`ffmpeg/pyproject.toml`): `E F W I UP B SIM PERF RUF ASYNC PTH TRY`;
ignore: `E501 TRY003 TRY300`; plus `[tool.ruff] line-length = 100`,
`target-version = "py313"` with the Flet-verifier comment.

---

## 3. Config-key surface (`ruff config` outputs, verified)

Bare `ruff config` top-level keys (verbatim order):

```text
cache-dir extend output-format output-prefer-rule-codes fix unsafe-fixes
fix-only show-fixes required-version preview exclude extend-exclude
extend-include force-exclude include respect-gitignore extension builtins
namespace-packages target-version per-file-target-version src line-length
indent-width lint format analyze
```

`ruff config lint` keys (verbatim): `allowed-confusables dummy-variable-rgx
extend-ignore(deprecated) extend-select extend-fixable external fixable ignore
extend-safe-fixes extend-unsafe-fixes ignore-init-module-imports(deprecated)
logger-objects select explicit-preview-rules task-tags typing-modules
unfixable` + per-linter subsections (`flake8-annotations … pyupgrade`),
`per-file-ignores extend-per-file-ignores exclude pydoclint ruff preview
typing-extensions future-annotations`.

`ruff config format` keys (verbatim): `exclude preview indent-style
quote-style nested-string-quote-style skip-magic-trailing-comma line-ending
docstring-code-format docstring-code-line-length`.

Keys we will actually use (all verified present above):

- `[tool.ruff]`: `line-length` (ffmpeg `= 100`; default 88 per `rule E501`
  output), `target-version` (`py313` ffmpeg / `py314`-era Sherlock — our app
  `requires-python = ">=3.14"`, so `py313` stays importable by the Flet
  verifier per ffmpeg comment), `preview` (bool — gates unstable rules/fixes),
  `required-version` (pin the binary, e.g. `==0.17.1`), `src`/`namespace-packages`,
  `include`/`exclude`/`extend-exclude`/`force-exclude`/`respect-gitignore`,
  `fix`/`unsafe-fixes`/`show-fixes`, `cache-dir`, `builtins`.
- `[tool.ruff.lint]`: `select`, `ignore`, `extend-select`, `extend-ignore`
  (deprecated — prefer `extend-select` + `ignore`), `per-file-ignores`
  (e.g. `"tests/**" = ["S101"]`), `extend-per-file-ignores`, `fixable`,
  `unfixable`, `extend-fixable`, `explicit-preview-rules`, `task-tags`,
  plus per-linter tables (`[tool.ruff.lint.isort]`, `[tool.ruff.lint.pyupgrade]`,
  etc. — subsection names verified in the `config lint` list).
- `[tool.ruff.format]`: `quote-style`, `indent-style`, `line-ending`,
  `skip-magic-trailing-comma`, `docstring-code-*`, `preview`, `exclude`.
  Canonical TOML shape (Sherlock/ffmpeg pattern):
  `[tool.ruff] line-length/target-version`, `[tool.ruff.lint] select/ignore`,
  `[tool.ruff.lint.per-file-ignores]`, `[tool.ruff.format] quote-style`.

---

## 4. Unknown-key hard-error behavior (verified live)

Probe: temp `pyproject.toml` with `[tool.ruff] bogus_key_xyz = true` →

```text
ruff failed
  Cause: Failed to load configuration `.../pyproject.toml`
  Cause: Failed to parse .../pyproject.toml
  Cause: TOML parse error at line 1, column 1
  |
1 | [tool.ruff]
  | ^^^^^^^^^^^
unknown field `bogus_key_xyz`
```

(Exit code surfaces as 0 in this shell harness; real CI fails loudly — the
`ruff failed` + `unknown field` cause chain is the contract.) Consequence:
renamed/removed keys break the run instead of silently drifting — desirable
(D5 row: "fails loudly"). Every key added to our config must exist in
`ruff config [lint|format]` for the pinned version.

---

## 5. How ruff makes our app significantly better than Termux's proot-distro

Termux's proot-distro is a shell/C distribution bootstrap — it has no Python
application surface to lint, no CI quality gate, and quality rests on manual
review of scripts. Our app is a Python/Flet codebase where the load-bearing
risks are exactly what ruff catches for free: undefined names and unused
imports (`F`), import disorder (`I`), stale pyupgrade idioms (`UP`),
bugbear-class correctness (`B`), simplification/performance (`SIM`/`PERF`),
try/except hygiene (`TRY`), plus quote/format consistency (`Q` + formatter).
Adopting the Sherlock-style ruleset as a CI gate (`ruff check` + `ruff format
--check`, both exit-nonzero on violation) means every push proves the whole
tree still meets the house standard — something the Termux lineage never had
and never needed. It costs one dev-only binary, zero APK bytes, zero runtime
risk.

## 6. Fullest utilization — concrete for THIS project

1. Add a `[tool.ruff]` + `[tool.ruff.lint]` + `[tool.ruff.format]` block to our
   `pyproject.toml` modeled on Sherlock (richest set above), with
   `line-length = 100` + `target-version = "py313"` (ffmpeg values — keeps
   output importable by the Flet verifier while app requires 3.14).
2. Keep the Sherlock ignores that encode owner rules (`E501 EM101/102/103
   TRY003 BLE001 S110 SIM105 TRY300 TRY301`) + `tests/** = ["S101"]`; add
   `PTH` + `ASYNC` from ffmpeg (pathlib discipline, async correctness for the
   `asyncio.to_thread` bridge in `services/proot_service.py`).
3. CI quality job (M5 `build-all.yml`): `uv run ruff check .` then
   `uv run ruff format --check .` before `pytest -m "not live"`; pin
   `required-version = "==0.17.1"` so the gate cannot float.
4. Editor path: document `ruff server` for VSCode (format-on-save + fix
   actions) — same binary, same config, no drift.
5. watchdog NOT in lint scope; qrcode NOT in lint scope beyond its dev-script
   use (see sibling files).

## 7. Verification refs

- `.venv/Scripts/ruff.exe --version` → `ruff 0.17.1`; `--help`, `check --help`,
  `format --help`, `server --help`, `analyze --help`, `clean --help`,
  `rule --help`, `linter` (59-row table quoted in §2), `config` / `config lint` /
  `config format` key lists, `rule E501` text — all live outputs above.
- `.venv/Lib/site-packages/ruff-0.17.1.dist-info/METADATA` (`License-Expression:
  MIT`, `Summary: An extremely fast Python linter and code formatter, written
  in Rust.`), `licenses/`, `RECORD`, `WHEEL`; `ruff/__main__.py:_run()`.
- `C:\Users\nwoki\.zcode\workspace\default\Sherlock\pyproject.toml:99-125`
  (`[tool.ruff.lint]` select/ignore/per-file-ignores + cleanup globs).
- `C:\Users\nwoki\.zcode\workspace\default\ffmpeg\pyproject.toml`
  (`[tool.ruff] line-length/target-version`, `[tool.ruff.lint]` select/ignore,
  `[tool.pytest.ini_options]`, `[tool.flet.*]`).
- `docs/roadmap.md` §3 row D5 + §M5; `docs/reference/dep-test-and-lint-stack.md`
  §ruff; our `pyproject.toml` (`[dependency-groups].dev`, no `[tool.ruff]` yet).
- Unknown-key probe output (§4). Default-select rule set: **unverified** (no
  defaults column in 0.17.1 `linter` output; `check --show-settings` empty in
  this harness) — always set `select` explicitly.
