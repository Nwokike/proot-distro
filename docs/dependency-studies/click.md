# click 8.5.0 — composable CLI toolkit

Identity: click 8.5.0, BSD-3-Clause (`METADATA` License-Expression), pure Python.
74 public names (introspected). Note: `click.__version__` is deprecated (warns, removal
in 9.1) — use `importlib.metadata.version("click")`. Ceiling to respect: `click<9`
(dep-cookiecutter-stack.md bump notes).

## Complete public API (grouped; full name list verified by introspection)

Decorators / construction: `command`, `group`, `argument`, `option`, `pass_context`,
`pass_obj`, `make_pass_decorator`, `get_current_context`, `help_option`,
`version_option`, `confirmation_option`, `password_option`, `custom_version_option`.
Core classes: `Command`, `Group`, `CommandCollection`, `Context`, `Argument`, `Option`,
`Parameter`, `ParameterSource`, `HelpFormatter`.
Types: `STRING`, `INT`, `FLOAT`, `BOOL`, `UUID`, `UNPROCESSED`, `DateTime`, `Tuple`,
`Choice`, `File`, `Path`, `IntRange`, `FloatRange`.
Errors: `ClickException`, `UsageError`, `BadParameter`, `BadOptionUsage`,
`BadArgumentUsage`, `MissingParameter`, `NoSuchOption`, `NoSuchCommand`, `Abort`,
`FileError`.
I/O and UX: `echo`, `secho`, `style`, `unstyle`, `format_filename`, `wrap_text`, `clear`,
`confirm`, `prompt`, `pause`, `progressbar`, `edit`, `launch`, `getchar`,
`echo_via_pager`, `open_file`, `get_app_dir`, `get_pager_file`.
Submodules: `core`, `decorators`, `types`, `exceptions`, `formatting`, `parser`,
`termui`, `utils`, `globals`, `annotations`.

## Example

```python
import click

@click.group()
def tools(): ...

@tools.command()
@click.argument("ref", default="ubuntu:24.04")
@click.option("--dest", type=click.Path(file_okay=False), required=True)
@click.confirmation_option(prompt="Write image manifest?")
def fetch(ref, dest):
    click.secho(f"fetching {ref} -> {dest}", fg="green")
```

## How cookiecutter/flet uses it

`cookiecutter/cli.py:18` (`import click`); `@click.command` + `@click.version_option`
+ `@click.argument('template')/('extra_context', nargs=-1)` + ~13 `@click.option`s
(`cli.py:87-163`) define cookiecutter's entire CLI. flet-cli itself is a separate
click-based CLI (D1 study) — same idioms, not this package instance.

## Our-project utilization — first-class (M0/M5 tooling CLIs)

Click is the house pattern for every repo-side CLI we own: M0's `tools/build_proot_wheel.py`
and `tools/check_apk_alignment.py` style helpers, M5 CI scripts, any manifest-lint or
image-prep tool. Use `@click.group` + subcommands, `click.Path(exists=True)` for file
args, `secho` for colored gates output, `confirmation_option` for destructive ops
(wiping a test container dir). Fullest use: one `tools/` entry-point group per repo so
`--help` documents the whole device-test/CI ritual.

## Better than Termux's proot-distro?

Contributor-experience win only: consistent, self-documenting tooling CLIs (`--help`,
validation, paging) versus ad-hoc `sys.argv` scripts. Users never see click.

## Verification refs

- Live introspection: 74 public names listed; `__version__` deprecation warning observed
- `.../cookiecutter/cli.py:15,18,87-163`
- `click-8.5.0.dist-info/METADATA` (BSD-3-Clause); `docs/reference/dep-cookiecutter-stack.md`
  (click in bump-group/ceiling notes); `docs/roadmap.md` §M0/M5 (`tools/`, CI ritual)
