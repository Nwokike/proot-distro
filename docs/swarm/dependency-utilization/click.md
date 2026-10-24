# click 8.5.0 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/dependency-studies/click.md`; `docs/reference/dep-cookiecutter-stack.md`; `docs/decisions.md` (D-003); `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `build_flet_proot_wheel.py`; `check_elf_alignment.py` (git HEAD); `generate_third_party_sources.py` (git HEAD); `tests/test_imports_vs_deps.py`; `.venv/Lib/site-packages/click/` (18 files); `.venv/Lib/site-packages/cookiecutter/`; `.venv/Lib/site-packages/flet_cli/` · **Date:** 2026-10-20

## What it does / how the app uses it

**The app does not use click at all, and neither does anything the repo actually executes.** Click 8.5.0 is installed in `.venv` as a *transitive, dev-only* package:

`pyproject.toml:78-84` (dev group) → `flet-cli>=1.0.4` → `flet_cli-1.0.4.dist-info/METADATA:18` (`Requires-Dist: cookiecutter>=2.6.0`) → `cookiecutter-2.7.1.dist-info/METADATA:32` (`Requires-Dist: click<9.0.0,>=7.0`) → `uv.lock:156-162` (click 8.5.0), `uv.lock:180` (cookiecutter's dependency edge), `uv.lock:226` (flet-cli's edge), `uv.lock:594-601` (the project's dev group). The **runtime** dependency closure (`uv.lock:586-592`, `pyproject.toml:9-15`) contains no click, and no runtime package declares it: `flet-1.0.4.dist-info/METADATA:12-18`, `flet_ads-1.0.4.dist-info/METADATA:14`, `flet_terminal-0.4.0.dist-info/METADATA:23` and `proot_distro-5.10.0.dist-info/METADATA:13` list no `click`.

**Click is provably never imported by this repo's toolchain.** The only module in the environment that imports click is `cookiecutter/cli.py:18` (`import click`), reached solely through the `cookiecutter` console script (`cookiecutter-2.7.1.dist-info/entry_points.txt` → `cookiecutter.__main__:main` → `cookiecutter/__main__.py:3` → `from cookiecutter.cli import main`). But flet-cli uses cookiecutter as a **library**, never as a CLI: `flet_cli/commands/create.py:90` and `flet_cli/commands/build_base.py:1893` both do `from cookiecutter.main import cookiecutter`, and `cookiecutter/main.py:17-24` never imports `cookiecutter.cli`. Runtime proof:

```
$ .venv/Scripts/python.exe -c "import cookiecutter.main, flet_cli.cli, sys; print('click' in sys.modules)"
False
```

`grep -rnw click .venv/Lib/site-packages/flet_cli/` returns **zero** hits (the only match anywhere in `flet_cli/` is the English phrase "double-click" at `flet_cli/commands/build.py:324`). `flet_cli` is an `argparse` program throughout (`flet_cli/cli.py:1,44,117,123,193`; `flet_cli/commands/build.py:1,51,54,87`).

**Click is not shipped to Android.** `flet_cli/commands/build_base.py:2566-2576` collects *only* `project.dependencies` + `tool.flet.<platform>.dependencies` and passes them to the packager (`package_args`); the dev group is never consulted. This matches the repo's own guard (`tests/test_imports_vs_deps.py:1-6,22-32`).

**Where click could matter:** the repo's three host-side CLIs, which live at the **repository root** (not `tools/`) and are the only repo-owned CLIs: `build_flet_proot_wheel.py` (argparse, `:10,467-482`), `check_elf_alignment.py` (hand-rolled `sys.argv`, `:60`), `generate_third_party_sources.py` (no CLI at all). All three run in CI: `.github/workflows/app.yml` — `uv run python build_flet_proot_wheel.py --out wheels` (apk + aab jobs), `uv run python check_elf_alignment.py build/apk/*.apk` and `... build/aab/*.aab`, `uv run python generate_third_party_sources.py`.

## Findings

### F1 · P2 · HALLUCINATION in the prior study: flet-cli is not a click CLI

- **Where:** `docs/dependency-studies/click.md:46-47` — "flet-cli itself is a separate click-based CLI (D1 study) — same idioms, not this package instance." vs `.venv/Lib/site-packages/flet_cli/cli.py:1` (`import argparse`), `flet_cli/cli.py:44` (`class _PositionalsFixArgumentParser(argparse.ArgumentParser)`), `flet_cli/cli.py:117,123,193`; `.venv/Lib/site-packages/flet_cli/commands/build.py:1,51,54,87`.
- **What:** flet-cli 1.0.4 contains **no** click usage at all — it is an argparse program, like the repo's own tools. The study's statement is factually wrong, and it is the premise for the study's headline claim that "Click is the house pattern for every repo-side CLI we own" (`click.md:50-56`).
- **Evidence:** `grep -rnw click .venv/Lib/site-packages/flet_cli/` → 0 hits; `grep -rn "import argparse" .venv/Lib/site-packages/flet_cli/` → 11 hits across `cli.py` and `commands/`. The `flet-cli` study (`docs/dependency-studies/flet-cli.md`) contains **no** mention of click at all.
- **Fix / opportunity:** correct `docs/dependency-studies/click.md:46-47` to state that flet-cli is argparse-based and that click's only importer in the tree is `cookiecutter/cli.py` (an entry point this repo never runs). The house-pattern claim must be re-grounded on the repo's own three scripts, not on flet-cli.
- **Risk if ignored:** a synthesis that trusts the study concludes "click is already the house pattern for our tooling CLIs" and proposes a convention the build host does not follow — and the corroborating claim is checkable in one grep, so it will not survive review.

### F2 · P2 · `check_elf_alignment.py` short-circuits: artifacts after the first failure are never inspected

- **Where:** `check_elf_alignment.py:68` — `ok = all(check_artifact(artifact) for artifact in artifacts)`.
- **What:** `all()` stops at the first `False`, so when the first artifact fails, every later artifact is silently skipped and never reported. CI invokes this as `check_elf_alignment.py build/apk/*.apk` with `split_per_abi = true` (`pyproject.toml:48`), i.e. **two** APKs (arm64 + x86_64), and the AAB job likewise.
- **Evidence:** runtime test against the installed tool (fixtures: one artifact with a non-ELF `.so`, one with a valid 0x4000-aligned ELF64):

```
$ python check_elf_alignment.py bad.apk good.apk
FAIL bad.apk: lib/arm64-v8a/libbad.so: lib/arm64-v8a/libbad.so: not an ELF file
FAILED
exit=1                       # <- good.apk was never opened; no "ok good.apk" line

$ python check_elf_alignment.py good.apk bad.apk
ok   good.apk: lib/arm64-v8a/libgood.so p_align=0x4000
FAIL bad.apk: lib/arm64-v8a/libbad.so: lib/arm64-v8a/libbad.so: not an ELF file
FAILED
exit=1                       # <- order-dependent diagnostics
```

  The exit code is still 1 either way, so the CI gate does not fail open — but the report is order-dependent and a misaligned x86_64 payload is invisible when the arm64 APK fails first.
- **Fix / opportunity:** evaluate every artifact and aggregate: `results = [check_artifact(a) for a in artifacts]; ok = all(results)` (list comprehension, not a generator), or `ok = all([check_artifact(a) for a in artifacts])`.
- **Risk if ignored:** a contributor fixing a 16 KB alignment failure is shown only the first artifact's diagnosis and may "fix" an APK that was never inspected, then re-run CI and hit the same wall on the second.

### F3 · P2 · A corrupt artifact produces a raw `zipfile.BadZipFile` traceback instead of a FAIL line

- **Where:** `check_elf_alignment.py:28` — `with zipfile.ZipFile(artifact) as archive:` (no `try`).
- **What:** a truncated or non-zip artifact raises `zipfile.BadZipFile` out of `main()`. The tool is a CI gate, so its most likely input failure (partial download, wrong path, a text file) produces a Python traceback instead of the tool's own `FAIL:` vocabulary.
- **Evidence:** runtime test:

```
$ python check_elf_alignment.py corrupt.apk
Traceback (most recent call last):
  ...
  File ".../check_elf_alignment.py", line 28, in check_artifact
    with zipfile.ZipFile(artifact) as archive:
  ...
zipfile.BadZipFile: File is not a zip file
exit=1
```

  (The exit code is 1 only because an unhandled exception happens to exit non-zero; the message contract is broken.)
- **Fix / opportunity:** wrap the open in `try/except zipfile.BadZipFile` and print `FAIL {artifact.name}: not a valid APK/AAB zip` and return `False`. `click.FileError` (`click/exceptions.py:342`) is the click-native equivalent, and `click.ClickException` (`click/exceptions.py:35-39`) would give the same `Error: ...` + exit 1 shape.
- **Risk if ignored:** a confusing 15-line stack trace in the CI log for what is a one-line user error, and no consistent FAIL/OK vocabulary for the release gate.

### F4 · P2 · The vendored-license check runs *after* the entire download + sha256 verification pass

- **Where:** `build_flet_proot_wheel.py:330-334` (`_license_text` → `raise SystemExit(f"missing vendored license text: {path}")`), called only from `build_flet_proot_wheel.py:396-398` inside `build_wheel`; `build_wheel` is called at `build_flet_proot_wheel.py:495`, **after** `downloaded = download_sources(lock, arch)` at `:494`.
- **What:** if `LICENSES/GPL-2.0.txt` (or `GPL-3.0.txt` / `BSD-3-Clause.txt`) is missing or renamed, the builder downloads and sha256-verifies **every pinned .deb** and then dies — a minutes-long network round trip for a local file-existence error. The check is free and should be a pre-flight.
- **Evidence:** runtime proof with the network stubbed and `LICENSE_DIR` pointed at a directory without `LICENSES/`:

```
call order: ['download_sources', 'collect_payloads',
             'SystemExit: missing vendored license text: .../LICENSES/GPL-2.0.txt']
```

  (This is not hypothetical for this tree — see the "Unverified" note about the current working-tree deletions.)
- **Fix / opportunity:** call `_license_text` for all three files at the top of `main()` (before the arch loop) — a ~3-line hoist, no new dependency. A `--preflight` flag is unnecessary; the check should simply run first.
- **Risk if ignored:** CI burns a full download cycle (and rate-limits the Termux pool) before failing on something a 3-line pre-flight would catch in milliseconds.

### F5 · P3 · `ElfError` subclasses `SystemExit`, and a second file catches it via `except SystemExit`

- **Where:** `build_flet_proot_wheel.py:104-105` — `class ElfError(SystemExit)`; raised at `:116,118,132-135`; re-wrapped at `:277` — `except ElfError as e: raise SystemExit(str(e)) from e`. Consumed in `check_elf_alignment.py:41` — `except SystemExit as exc:`.
- **What:** an *exception* class inheriting from the *exit* class. Consequences: (a) `except Exception` will never catch it — it is a `BaseException`; (b) `check_elf_alignment.py` can only trap it by catching `SystemExit`, which is an implicit, undocumented cross-file contract between two scripts; (c) the `ElfError → SystemExit` re-wrap at `:277` is pure ceremony, because `ElfError` already *is* a `SystemExit` with the right message.
- **Evidence:** `ElfError.__mro__` = `(ElfError, SystemExit, BaseException, Exception, BaseException)`; `build_flet_proot_wheel.py:104` and the consumer at `check_elf_alignment.py:41`.
- **Fix / opportunity:** make `ElfError` a plain `Exception` subclass and let the CLI layer map it to an exit. Click's taxonomy already does this: `click.ClickException` (`click/exceptions.py:35`, `exit_code = 1` at `:39`, `show()` prints `Error: <msg>` to stderr at `:57-65`) vs `click.UsageError` (`click/exceptions.py:68`, `exit_code = 2` at `:77`).
- **Risk if ignored:** a latent trap for the next editor — changing `ElfError` to inherit from `Exception` (the natural refactor) makes `check_elf_alignment.py` crash with an unhandled `ElfError` instead of printing `FAIL`.

### F6 · P3 · Exit codes are inconsistent across the three host tools, and within one of them

- **Where:** `build_flet_proot_wheel.py:487` — `raise SystemExit("--tag requires exactly one --arch")` (exit **1**); argparse's own usage error exits **2**; `check_elf_alignment.py:62-63` (no args → **2**), `:66-67` (missing file → **1**), `:70` (fail → **1**); `generate_third_party_sources.py:109-113` (always **0**).
- **What:** the *same* class of error (bad usage) exits 1 in `build_flet_proot_wheel.py` and 2 in `check_elf_alignment.py`; the *same* tool reports its own usage error with two different codes. The `--tag` misuse also prints a bare sentence with no usage line, so the user is not told what the valid invocation is.
- **Evidence:** runtime:

```
$ python build_flet_proot_wheel.py --tag py3-none-any
--tag requires exactly one --arch
exit=1

$ python build_flet_proot_wheel.py --arch mips
usage: build_flet_proot_wheel.py [-h] [--out OUT] [--arch {aarch64,x86_64}] [--tag TAG]
build_flet_proot_wheel.py: error: argument --arch: invalid choice: 'mips' (choose from 'aarch64', 'x86_64')
exit=2

$ python check_elf_alignment.py
<docstring>
exit=2
```

- **Fix / opportunity:** adopt one convention — 0 = ok, 1 = failure, 2 = usage — which is exactly click's default taxonomy (`click/exceptions.py:39` and `:77`; `click.UsageError` prints the usage line and the `Try '... --help' for help.` hint, `click/exceptions.py:87-111`). With click, `raise click.UsageError("--tag requires exactly one --arch")` yields exit 2 + usage + hint, matching argparse's own behaviour in the same tool.
- **Risk if ignored:** CI and humans cannot tell a *bad invocation* from a *real failure* by exit code alone, and a `set -e` wrapper that treats 1 and 2 alike will not distinguish "the build broke" from "someone typed the command wrong".

### F7 · P3 · `generate_third_party_sources.py` has no CLI: no `--output`, no `--check`, and it silently overwrites the committed file

- **Where:** `generate_third_party_sources.py:21` — `OUTPUT_FILE = REPO_ROOT / "THIRD-PARTY-SOURCES.md"` (hard-coded); `:109-113` — `main()` writes the file unconditionally and prints `Wrote <path>`; there is no `argparse`/`sys.argv` anywhere in the file (only `sys.path.insert` at `:10`).
- **What:** (a) the output path cannot be redirected, so the script cannot be used to regenerate into a temp dir for a drift check; (b) there is no `--check` mode, so CI cannot assert that the committed `THIRD-PARTY-SOURCES.md` matches the generator — the CI job simply regenerates and uploads (`app.yml`, "Write third-party sources bundle"), which means the committed copy and the released copy can diverge without any signal; (c) the script also writes with the platform default newline, so on Windows it emits **CRLF** while the committed file is **LF**.
- **Evidence:** running the HEAD version of the script against a copy of `src/` produced a file whose content is byte-identical to `git show HEAD:THIRD-PARTY-SOURCES.md` after normalizing line endings (`diff` of `tr -d '\r'` versions: identical), but the raw file reports `with CRLF line terminators` vs the committed `UTF-8 text` (LF). `OUTPUT_FILE` is a module constant, so the destination cannot be varied at all.
- **Fix / opportunity:** add `--output PATH` (default `REPO_ROOT/THIRD-PARTY-SOURCES.md`) and a `--check` flag that writes to a temp file, compares, and exits 1 on drift — `click.Path(path_type=Path, writable=True)` and `click.echo` make this ~10 lines. Write with `newline="\n"` to keep the file LF on every host. Note this is a *CI-tool* improvement only; it must not touch `src/`.
- **Risk if ignored:** the legal "source offer" document that ships with the release is regenerated rather than verified, so a stale committed copy and a fresh release copy can coexist with no error; the CRLF/LF split also produces a noisy diff on Windows contributors' machines.

### F8 · P3 · Prior-study file names do not exist: the house "tools/" convention was never adopted

- **Where:** `docs/dependency-studies/click.md:51-52` — "M0's `tools/build_proot_wheel.py` and `tools/check_apk_alignment.py` style helpers"; `docs/roadmap.md:73` (git HEAD) — "`tools/build_flet_proot_wheel.py`" and "`tools/check_apk_alignment.py`".
- **What:** the actual scripts are `build_flet_proot_wheel.py` and `check_elf_alignment.py`, at the **repository root** — there is no `tools/` directory (`git ls-files` shows no `tools/**`; `ls tools/` → *No such file or directory*). The click study's "house pattern" therefore describes a directory layout that does not exist, and its central example is a script that is not click-based either.
- **Evidence:** `git ls-files` output (no `tools/` entry); `.github/workflows/app.yml` invokes the scripts at the root (`uv run python build_flet_proot_wheel.py --out wheels`; `uv run python check_elf_alignment.py build/apk/*.apk`; `uv run python generate_third_party_sources.py`); `pyproject.toml:115-117` lints them at the root.
- **Fix / opportunity:** correct the two study/roadmap references to the real paths, and re-ground the "click is our house pattern" claim on the three root-level scripts. If a `tools/` group is wanted, that is a separate, owner-ruling decision (it touches CI paths) — not a click question.
- **Risk if ignored:** the synthesis recommends "follow the `tools/` pattern" for work that has no precedent in the tree, and a reviewer who greps for `tools/` finds nothing.

## Missed capabilities (dependency audits only)

- **Uniform, self-documenting CLI surface** · API: `@click.command` / `@click.group` (`click/__init__.py:19,22` → `click/decorators.py:168,293`), `@click.option` (`click/decorators.py:352`), `@click.argument` (`click/decorators.py:324`), `@click.version_option` (`click/decorators.py:421`), `@click.help_option` (`click/decorators.py:603`) · Integration: replace the argparse block at `build_flet_proot_wheel.py:467-482` and the `sys.argv` slice at `check_elf_alignment.py:60` · Value: one `--help` that documents the whole device-test/CI ritual; per-subcommand help instead of one argparse parser; `--version` for the two scripts that lack it. Cost: ~40 lines across the two scripts, no behavior change to the CI invocations.
- **Typed file/path arguments with existence checks** · API: `click.Path(exists=True, dir_okay=False, path_type=Path)` (`click/types.py:1048`, signature at `:1093-1104`), `click.File` (`click/types.py:904`) · Integration: `check_elf_alignment.py:60-67` — replace the hand-rolled `missing = [str(a) for a in artifacts if not a.exists()]` + `FAIL:` print with `type=click.Path(exists=True, dir_okay=False, path_type=Path)` on the argument · Value: the tool's own `FAIL: no such artifact(s): [...]` path becomes a standard usage error (exit 2) with the usage line, and the check happens *before* the first zip is opened instead of after. Verified at runtime with the installed 8.5.0: `Error: Invalid value for '[ARTIFACTS]...': File 'nope.apk' does not exist.` / exit 2. Cost: ~3 lines; the `FAIL:` wording changes, so the CI log string must be updated if it is ever grepped (it is not, in `app.yml`).
- **Enumerated choices** · API: `click.Choice(choices, case_sensitive=True)` (`click/types.py:331`, `__init__` at `:364-368`) · Integration: `build_flet_proot_wheel.py:474` `choices=sorted(ARCH_TAGS)` → `type=click.Choice(sorted(ARCH_TAGS))`; `multiple=True` (`click/core.py:2961`) replaces `action="append"` · Value: identical validation, but the error message becomes click's `'mips' is not one of 'aarch64', 'x86_64'` with a usage line and exit 2, consistent with the tool's own argparse behaviour. Cost: ~2 lines.
- **Correct error taxonomy for gates** · API: `click.ClickException` (`click/exceptions.py:35`, `exit_code = 1` at `:39`, `show()` at `:57-65`), `click.UsageError` (`click/exceptions.py:68`, `exit_code = 2` at `:77`, usage+hint at `:87-111`), `click.BadParameter` (`:114`), `click.Abort` (`:362`) · Integration: `build_flet_proot_wheel.py:104` (`ElfError`), `:206-209` (sha256 mismatch), `:277` (re-wrap), `:487` (the `--tag` usage error); `check_elf_alignment.py:31,45,50,66` (FAIL lines) · Value: fixes F5 and F6 in one move — errors go to **stderr** with an `Error:` prefix, and the exit codes become 1/2 as the tools already half-intend. Verified at runtime: `ClickException` → `Error: alignment 0x1000 < 16 KB` / exit 1; `UsageError` → usage + `Try 'bad --help' for help.` + `Error: --tag requires exactly one --arch` / exit 2. Cost: ~15 lines; the CI invocations and their exit-code contract are unchanged.
- **Hermetic CLI tests** · API: `click.testing.CliRunner` (`click/testing.py:317`; note it is *not* re-exported from the `click` namespace — import it as `from click.testing import CliRunner`) · Integration: new `tests/test_host_tools_cli.py`, driving `check_elf_alignment.py` and `build_flet_proot_wheel.py` with `CliRunner.invoke(...)` and asserting `result.exit_code` / `result.output` · Value: the F2 short-circuit and the F3 traceback become *regression tests* instead of a manual observation; today's `tests/` has **no** test for any host tool (`git ls-files tests/` → only app-level tests plus `check_flet_api.py`). Verified at runtime that `CliRunner` is importable and that `invoke()` returns `exit_code` and `output`. Cost: ~60 lines of new test code, zero new runtime dependency.
- **Progress and colored gate output** · API: `click.progressbar` (`click/termui.py:403`), `click.secho` (`click/termui.py:780`), `click.style` (`:641`), `click.echo(..., err=True)` (`click/utils.py:252`, `err` parameter at `:256`) · Integration: the per-package download loop at `build_flet_proot_wheel.py:449-462` (currently `print(..., end=" ", flush=True)` at `:454`) and the FAIL/ok lines in `check_elf_alignment.py:31-55` · Value: a progress bar over the three deb downloads and stderr-vs-stdout separation so CI logs keep PASS/FAIL lines greppable. Cost: ~10 lines. Lower value than the items above — `rich` (already in the tree via `flet-cli`) could do this too, but rich is *also* only a transitive dev dependency, so click is the safer of the two.
- **Shell completion** · API: `click.shell_complete` (`click/shell_completion.py:19`), `ShellComplete` (`:278`), `add_completion_class` (`:565`) · Integration: a single `tools` group with one entry point per script would give `flet-<tab>` completion for the whole CI ritual · Value: nice, but only material if the three scripts are merged into one group — a larger change than this audit recommends. Cost: high relative to value today; defer.
- **Destructive-op confirmation** · API: `@click.confirmation_option` (`click/decorators.py:380`), `click.confirm` (`click/termui.py:289`) · Integration: none of the three scripts is destructive today (the builder only writes into `--out`; the checker only reads) · Value: **none currently** — recorded so the synthesis does not propose it. It would matter if a future tool wipes a build dir or drops a release tag.

## Recommendation (value vs cost)

**Do not ship click, and do not add it to the runtime dependency set.** It is dev-only by construction (`pyproject.toml:9-15` vs `:78-84`) and is never imported by anything this repo runs (F1 evidence above). It must never appear in `[project].dependencies`, or it would be pulled into the Android bundle — which the packager would do automatically, since it installs `project.dependencies` verbatim (`flet_cli/commands/build_base.py:2566-2576`).

**Recommended split:**

1. **Ship-now, zero dependency (do this regardless of the click decision).** Fix F2 (list comprehension, 1 line), F3 (`except zipfile.BadZipFile`, 3 lines), F4 (hoist the license pre-flight above the download loop, 3 lines), F5/F6 (make `ElfError` an `Exception`; use exit 2 for usage errors, 1 for failures). These are real defects in CI gates, they are framework-independent, and they are ~10 lines total. **Value: high. Cost: ~10 lines, no new dependency, no D-003 sign-off needed.**
2. **Adopt click for the host-side CLI layer, but only with a D-003 sign-off.** Click is already in `uv.lock` at 8.5.0 and already installed in the CI environment (every job runs `uv sync --frozen --group dev`, `app.yml`), so adopting it costs **no new download**; but using a *transitive* dependency directly is fragile — a flet-cli bump that drops cookiecutter, or a cookiecutter bump that drops click, silently breaks the repo's own scripts. The correct form is one line in `[dependency-groups] dev` (`click>=8.5.0,<9`) plus a `uv lock` refresh; that **is** a change to the frozen dev set and therefore needs owner sign-off under D-003 (`docs/decisions.md:12`: "Dev: `flet-cli`, `flet-desktop`, `pytest`, `pytest-timeout`, `ruff`. Any addition needs owner sign-off."). The `click<9` ceiling is already the house rule (`docs/reference/dep-cookiecutter-stack.md`, cookiecutter's own pin `click<9.0.0,>=7.0` at `cookiecutter-2.7.1.dist-info/METADATA:32`).
3. **What click buys, quantified.** For the two CLI-shaped scripts: one consistent `--help`, one error taxonomy that matches the exit codes the tools already half-use (0/1/2), one place where path validation happens before the first byte is read, and — the largest single win — `CliRunner` (`click/testing.py:317`), which turns F2 and F3 from one-time observations into regression tests. For the third script (`generate_third_party_sources.py`), it buys `--output`/`--check` (F7), which is what closes the committed-vs-released drift hole.
4. **Cost of the click path, honestly.** ~40 lines rewritten in `build_flet_proot_wheel.py` and `check_elf_alignment.py`, ~15 lines in `generate_third_party_sources.py`, ~60 lines of new `CliRunner` tests, 1 line in `pyproject.toml`, 1 `uv lock`. Every CI invocation line in `app.yml` keeps working unchanged (the same flags, the same exit codes). The risk to manage is *not* click — it is the exit-code contract: `check_elf_alignment.py` is a release gate (`app.yml`, "Verify 16 KB page alignment"), so any change to its 0/1/2 semantics must be re-verified against a real APK.
5. **Do not do.** Do not merge the three scripts into one click group (that is a repo-layout decision, not a click decision, and it touches CI paths). Do not add shell completion. Do not use `click.confirm` on a non-destructive tool. Do not move click into `[project].dependencies`.

**Net:** the dependency itself is fine where it is (dev-only, inert, zero runtime cost, and a correct BSD-3-Clause, dependency-free wheel: `click-8.5.0.dist-info/METADATA` has no `Requires-Dist` and `License-Expression: BSD-3-Clause`). The actionable work is in the **repo's own three CLIs**, and roughly 80% of that work needs no new dependency at all. Click is the right answer for the remaining 20% *if and only if* the owner signs off on naming it in the dev group.

## Verified-good list

- Installed click is **8.5.0** (`importlib.metadata.version("click")` → `8.5.0`; `click-8.5.0.dist-info/METADATA` `Version: 8.5.0`), matching `uv.lock:156-157` and the prior study's title. Pure-Python wheel (`py3-none-any`, `uv.lock:161`).
- click 8.5.0 has **no runtime dependencies of its own** — `click-8.5.0.dist-info/METADATA` declares no `Requires-Dist`; `Requires-Python: >=3.10` only. License `BSD-3-Clause` (`License-Expression`), and the repo already vendors that text at `LICENSES/BSD-3-Clause.txt` (git HEAD).
- The prior study's API inventory is accurate: `dir(click)` yields exactly **74** public names (runtime check), and every name it lists exists in the installed tree — `Argument`/`Command`/`Context`/`Group`/`Option`/`Parameter`/`ParameterSource` (`click/__init__.py:10-17`), `argument`/`command`/`confirmation_option`/`group`/`help_option`/`make_pass_decorator`/`option`/`pass_context`/`pass_obj`/`password_option`/`version_option` (`:18-29`), `Abort`/`BadArgumentUsage`/`BadOptionUsage`/`BadParameter`/`ClickException`/`FileError`/`MissingParameter`/`NoSuchCommand`/`NoSuchOption`/`UsageError` (`:30-39`), `HelpFormatter`/`wrap_text` (`:40-41`), `get_current_context` (`:42`), `clear`/`confirm`/`echo_via_pager`/`edit`/`get_pager_file`/`getchar`/`launch`/`pause`/`progressbar`/`prompt`/`secho`/`style`/`unstyle` (`:43-55`), `BOOL`/`Choice`/`DateTime`/`File`/`FLOAT`/`FloatRange`/`INT`/`IntRange`/`ParamType`/`Path`/`STRING`/`Tuple`/`UNPROCESSED`/`UUID` (`:56-69`), `echo`/`format_filename`/`get_app_dir`/`open_file` (`:70-73`).
- `click.__version__` is deprecated exactly as the study says: `click/__init__.py:112-122` emits `DeprecationWarning` and returns `importlib.metadata.version("click")`; removal is announced for Click 9.1. Runtime check reproduced the warning.
- The `click<9` ceiling is the correct house rule — it is cookiecutter's own pin (`cookiecutter-2.7.1.dist-info/METADATA:32`, `click<9.0.0,>=7.0`) and is already recorded in `docs/reference/dep-cookiecutter-stack.md`.
- Every click capability proposed in "Missed capabilities" was **executed** against the installed 8.5.0 and behaved as claimed: `Path(exists=True)` → exit 2 + `Error: Invalid value for '[ARTIFACTS]...': File 'nope.apk' does not exist.`; `Choice` → exit 2 + `'mips' is not one of 'aarch64', 'x86_64'`; `ClickException` → exit 1 + `Error: ...`; `UsageError` → exit 2 + usage + `Try '... --help' for help.`; `--help` renders usage/options/defaults and exits 0; `CliRunner().invoke()` returns `exit_code` and `output`.
- The `all()` short-circuit (F2), the `BadZipFile` traceback (F3) and the download-before-license ordering (F4) were all **reproduced at runtime**, not inferred from reading.
- `build_flet_proot_wheel.py`'s argparse layer is otherwise sound: `--arch` is validated against `sorted(ARCH_TAGS)` and errors with exit 2; `--out` defaults to `dist`; the module docstring is surfaced as the parser description via `RawDescriptionHelpFormatter` (`:467-469`); `main()` returns 0 and `raise SystemExit(main())` (`:501-502`).
- The elf reader is sound for the job it does: `elf_info` (`:113-167`) checks the ELF magic, rejects non-ELF64, verifies PT_LOAD congruence, computes the minimum `p_align`, and extracts `DT_NEEDED`/`DT_SONAME`; `unmet_needed` (`:170-178`) correctly excludes `libc.*`/`libdl.*`/`libm.*` plus `SYSTEM_SONAMES` (`:94-101`).
- The sha256 pin discipline is correct: `_fetch_verified` (`:202-210`) compares the digest and refuses to proceed on mismatch with an actionable message; the pin set is a single literal (`:34-81`).
- `generate_third_party_sources.py` produces **byte-identical content** to the committed `THIRD-PARTY-SOURCES.md` (modulo CRLF/LF) when run against the current `src/` — the hard-coded Python-dependency table is *not* stale: it lists exactly the runtime closure of `uv.lock:586-592` minus `oauthlib`, which is deliberately stripped from the bundle by `[tool.flet.cleanup] package_files = ["oauthlib/**"]` (`pyproject.toml:62-63`), and it correctly omits the dev-only `flet-cli`/`flet-desktop`.
- Nothing in `src/` imports click (grep over `src/`, `tests/` and the three root scripts: no `import click`; the only `click` tokens in `src/` are Flet's `on_click=` handler kwargs, e.g. `src/components/app_header.py:31`).
- click 8.5.0 is **not** a runtime dependency of any packaged app: `flet_cli/commands/build_base.py:2566-2576` restricts the bundle to `project.dependencies` + `tool.flet.<platform>.dependencies`.

## Unverified

- **Working-tree deletions (pre-existing, not caused by this audit).** `git status` shows unstaged deletions of `check_elf_alignment.py`, `generate_third_party_sources.py`, `LICENSES/*.txt`, `src/LICENSES/*.txt`, `THIRD-PARTY-SOURCES.md`, and several `docs/` files (`git status --short` → 25 entries, all ` D` / `?? docs/swarm/`). HEAD is `9027359` and there is no stash. Those two scripts were therefore audited from `git show HEAD:<path>` (their content is identical to what the CI workflow invokes) and were **executed** from copies written to a temp directory. F4's real-world trigger is currently live in this tree (no `LICENSES/` → the builder would download every deb and then fail), but the deletions look like an environment artifact of this workspace rather than a committed state — **UNVERIFIED** whether they are intentional.
- I did not run `flet build apk`/`aab`, so the claim that click is absent from the shipped APK rests on the packager's requirement collection (`flet_cli/commands/build_base.py:2566-2576`) and the repo's own guard, not on an APK inspection. The CI "prune check" (`app.yml`, `unzip -l … grep -qE 'pytest/|ruff/|…'`) does not grep for `click/`.
- The exact size click contributes to the CI venv (wheel is 125 251 bytes, `uv.lock:161`) is not a shipped-app cost; no APK size delta was measured.
- I did not verify how `uv` resolves the `dev` group in every invocation form (`uv run` vs `uv sync --frozen --group dev`) on the CI runner; the claim that click is present in CI rests on `app.yml` running `uv sync --frozen --group dev` in the `quality`, `apk` and `aab` jobs.
- No upstream click changelog was consulted; the `click<9` ceiling is taken from cookiecutter's pin and the repo's own reference doc, not from click's release policy.
- Whether the repo *should* get a `tools/` directory is an owner decision, not a technical finding — **UNVERIFIED** and out of scope.
