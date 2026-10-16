# cookiecutter 2.7.1 — Exhaustive API Reference (flet-cli build-template companion)

> Companion to `docs/reference/dep-cookiecutter-stack.md` (mechanics summary).
> This file is the **exhaustive API** companion. flet stays **1.0.4** (D-010);
> flet-cli is therefore 1.0.4 here. Anti-hallucination rule: every claim below
> cites the installed source as `cookiecutter/<file>.py:<line>` (or an
> installed flet-cli path). Anything not found in the installed tree is
> explicitly labeled **unverified**.

Installed source: `.venv/Lib/site-packages/cookiecutter` (2.7.1).
Interpreter used for checks: `.venv/Scripts/python.exe -c`.
Context read first: `docs/roadmap.md` + `docs/reference/dep-cookiecutter-stack.md`.

---

## 1. Identity — version, license, module layout

- **Version:** 2.7.1 — `cookiecutter-2.7.1.dist-info/METADATA` (`Name: cookiecutter`,
  `Version: 2.7.1`); runtime `cookiecutter.__version__` comes from
  `importlib.metadata.version("cookiecutter")` (`cookiecutter/__init__.py:1-5`).
- **License:** BSD. `dist-info/METADATA` declares `License-File: LICENSE`
  (plus `AUTHORS.md`); `dist-info/licenses/LICENSE` header reads
  `Copyright (c) 2013-2026, Audrey M. Roy Greenfeld … Redistribution and use
  in source and binary forms … are permitted` (BSD 3-clause text, verified
  head lines 1–30). PyPI summary line (METADATA `Summary:`):
  `A command-line utility that creates projects from project templates…`.
- **Module layout** (verified `ls`, 17 `.py` files):
  `__init__.py`, `__main__.py`, `cli.py` (258 lines), `config.py` (140),
  `environment.py` (71), `exceptions.py` (180), `extensions.py` (175),
  `find.py` (38), `generate.py` (466), `hooks.py` (201), `log.py` (56),
  `main.py` (212), `prompt.py` (438), `replay.py` (51), `repository.py` (139),
  `utils.py` (106), `vcs.py` (139), `zipfile.py` (125).
  Entry point file: `cookiecutter-2.7.1.dist-info/entry_points.txt`
  (console script; exact target **unverified** — not opened).
- **Runtime role in this repo:** build-host only. None of it ships into the APK
  (see reference doc §Trust boundary). flet-cli imports it lazily inside the
  build path (`flet_cli/commands/build_base.py:1893`
  `from cookiecutter.main import cookiecutter`).

---

## 2. Complete public API

Line anchors below are `def`/`class`/constant lines from `grep -n` on the
installed tree.

### 2.1 `cookiecutter.main.cookiecutter` — full signature (main.py:29)

```python
def cookiecutter(                      # cookiecutter/main.py:29
    template: str,
    checkout: str | None = None,       # main.py:30-43 region
    no_input: bool = False,
    extra_context: dict[str, Any] | None = None,
    replay: bool | str | None = None,
    overwrite_if_exists: bool = False,
    output_dir: str = '.',
    config_file: str | None = None,
    default_config: bool = False,
    password: str | None = None,
    directory: str | None = None,
    skip_if_file_exists: bool = False,
    accept_hooks: bool = True,
    keep_project_on_failure: bool = False,
) -> str:
```

Parameter semantics (all verified against `main.py:29-201` body + docstring
`main.py:44-68`):

| Param | Semantics (installed behavior) |
|---|---|
| `template` | Local dir, cached-template path, git/hg URL, or `.zip` (URL or file). Passed to `determine_repo_dir` (`repository.py:70`) with `abbreviations`, `clone_to_dir`, `checkout`, `no_input`, `password`, `directory` (`main.py:55-63`). |
| `checkout` | Branch/tag/commit checked out after `git clone` (`vcs.py:63-121`; hg gets `--` guard at `vcs.py:115-116`). For flet builds this is the template ref (= flet version). |
| `no_input` | Never prompt; use `cookiecutter.json` + user config + `extra_context`. Also forces refresh of cached VCS/zips: `prompt_and_delete(path, no_input)` returns delete=True without asking (`prompt.py:406-429`), and `vcs.clone` / `zipfile.unzip` both honor it (`vcs.py:100-103`, `zipfile.py:47-50`). Mutually exclusive with `replay`/`extra_context` — raises `InvalidModeException` (`main.py:67-74`). |
| `extra_context` | Override dict applied over file + default context via `apply_overwrites_to_context` (`main.py:113-118`, `generate.py:59-124`). Must be JSON-serializable in practice because the merged context is `replay.dump`ed (`main.py:164`, `replay.py:26-37` `json.dump`). Top-level unknown keys are **silently ignored** (see §2.2). |
| `replay` | `True` = load `<replay_dir>/<template>.json`; `str` = load that file path (`main.py:82-89`, `replay.py:40-51`). Replays prior answers; new keys added since the replay file still prompt (`main.py:92-111`). Cannot combine with `no_input`/`extra_context`. |
| `overwrite_if_exists` | Overwrite the rendered project dir if it exists; else `OutputDirExistsException` (`generate.py:263-293`). flet builds pass `True` (placeholder assets re-render; reference doc). |
| `output_dir` | Parent dir the `<project_slug>/` dir is created in (default `'.'`). Recorded into context as `cookiecutter._output_dir = abspath(output_dir)` (`main.py:152`). |
| `config_file` | Custom YAML user-config path (else `~/.cookiecutterrc` or `$COOKIECUTTER_CONFIG`; `config.py:89-140`). |
| `default_config` | Library-level: `True` = ignore all config files and use `DEFAULT_CONFIG`; `dict` = merge with defaults (`config.py:111-118`). Note CLI flag is `is_flag` bool (`cli.py:143-147`); dict form is **library-only**. |
| `password` | Zip password for protected template zips (`zipfile.py:17-36`, `93-119`). CLI sources it from `$COOKIECUTTER_REPO_PASSWORD` (`cli.py:219-232`). flet never passes it. |
| `directory` | Subdir inside the repo that actually holds `cookiecutter.json` (`repository.py:126-129`). flet passes its template subdir (see §3). |
| `skip_if_file_exists` | Per-file skip (passed to `generate_file`, `generate.py:175-260`); dir-level still governed by `overwrite_if_exists`. flet leaves default `False`. |
| `accept_hooks` | `True` = run `pre_prompt` + `pre/post_gen_project` hooks; `False` = skip all (`main.py:65`, `76`, `generate.py:327-466`). CLI exposes `yes/ask/no` (`cli.py:157-162`). flet leaves default `True` — template hooks **execute** (trust boundary). |
| `keep_project_on_failure` | `True` = keep partial output on failure; default deletes a newly-created project dir on hook/render failure (`generate.py:353-466`). |

Return value: absolute project-dir path string (`generate_files … return project_dir`, `generate.py:464-466`; `main.py:167-201` returns it). Cleanup: temp repo dirs removed via `rmtree` when `determine_repo_dir`/`run_pre_prompt_hook` created them (`main.py:193-199`).

Internals worth knowing (`main.py:76-164`):

1. `run_pre_prompt_hook(base_repo_dir)` may **copy** the repo to a temp dir (`hooks.py:180-201`, `utils.py:92-99`); `cleanup = repo_dir != base_repo_dir`.
2. `_patch_import_path_for_repo` (`main.py:203-212`) appends `repo_dir` to `sys.path` during replay-load, prompting, and generation — template `_extensions` resolve from there.
3. Nested-template dispatch: if context keys contain `template` or `templates`, `choose_nested_template` runs and `cookiecutter()` **recurses** (`main.py:120-139`).
4. `context['_cookiecutter']` snapshot (non-`_` keys) + `_template`, `_output_dir`, `_repo_dir`, `_checkout` injections (`main.py:113-162`); then unconditional `replay.dump` (`main.py:164`).
5. On nested-template return path the function returns the recursive call directly (dump/generate of the outer frame are skipped — `main.py:124-139`).

**`cookiecutter_cli` note (owner addendum compliance):** there is **no**
`cookiecutter.main.cookiecutter_cli` symbol in installed 2.7.1
(`grep -rn cookiecutter_cli cookiecutter/` = no hits). The CLI entry is
`cookiecutter.cli.main` (click command, `cli.py:171`) invoked via
`cookiecutter.__main__` (`__main__.py:1-6` `from cookiecutter.cli import main`).
Any `cookiecutter_cli` reference in third-party docs is **unverified** against
this install — use `cookiecutter.main.cookiecutter` as the library entry.

### 2.2 `generate.py` — context, files, overwrite semantics

- `is_copy_only_path(path, context)` (`generate.py:39-56`): True iff `path`
  fnmatches a pattern in `cookiecutter._copy_without_render`. Matched files/dirs
  are copied with `shutil.copyfile/copymode/copytree` **without rendering**
  (`generate.py:395-436`).
- `apply_overwrites_to_context(context, overwrite_context, *, in_dictionary_variable=False)`
  (`generate.py:59-124`). Exact semantics (quote-structure, verified):
  - Top-level unknown key → **ignored** (`if variable not in context: … continue`
    unless recursing into a dict; `generate.py:68-74`). This is the silent-typo
    trap: every flet `template_data` key must already exist in the template's
    `cookiecutter.json`; nested dicts *can* gain keys (`generate.py:86-91`).
  - `list` context value + `list` overwrite (non-nested) = **multichoice**: must
    be subset or `ValueError` (`generate.py:77-88`). `list` + scalar = **choice**:
    must be a member; it is moved to index 0 (new default) or `ValueError`
    (`generate.py:89-104`).
  - `dict`+`dict` = recursive partial merge (`generate.py:105-111`).
  - `bool` context + `str` overwrite = parsed via `YesNoPrompt().process_response`
    (`1/true/t/yes/y/on` → True; `0/false/f/no/n/off` → False; else `ValueError`;
    `generate.py:112-122`, `prompt.py:45-58`).
  - Else scalar replace (`generate.py:123-124`).
  - `default_context` (user config) failures only `warnings.warn`
    (`generate.py:140-146`); `extra_context` failures raise.
- `generate_context(context_file='cookiecutter.json', default_context=None, extra_context=None)`
  (`generate.py:126-173`): `json.load(…OrderedDict)`; `ValueError` → wrapped as
  `ContextDecodingException` with absolute path (`generate.py:133-146`); context
  key = file stem (`cookiecutter.json` → `context['cookiecutter']`);
  default-then-extra overwrites applied in that order.
- `generate_file(project_dir, infile, context, env, skip_if_file_exists=False)`
  (`generate.py:175-260`): renders the *output path* through Jinja first
  (`env.from_string(infile)`); empty rendered name → silently skipped
  (`generate.py:187-192`); binary (binaryornot) → copy without render
  (`generate.py:199-205`); text → `env.get_template`, `TemplateSyntaxError`
  re-raised with `translated=False` (`generate.py:211-218`); newline handling:
  explicit `cookiecutter._new_lines` wins, else detected from first line
  (`generate.py:220-235`); permissions preserved via `shutil.copymode`
  (`generate.py:259`).
- `render_and_create_dir(dirname, context, output_dir, environment, overwrite_if_exists=False)`
  (`generate.py:263-297`): renders dir name; empty → `EmptyDirNameException`;
  exists + no overwrite → `OutputDirExistsException`; returns `(path, created?)`.
- `_run_hook_from_repo_dir` (`generate.py:300-325`) is **deprecated** — emits
  `DeprecationWarning` and delegates to `hooks.run_hook_from_repo_dir`.
- `generate_files(repo_dir, context=None, output_dir='.', overwrite_if_exists=False, skip_if_file_exists=False, accept_hooks=True, keep_project_on_failure=False)`
  (`generate.py:327-466`): builds `StrictEnvironment` via `create_env_with_context`
  (`generate.py:333`); locates the one `{{cookiecutter…}}` child dir via
  `find_template` (`generate.py:335` + `find.py:18-38`); `pre_gen_project` hook,
  walk with `FileSystemLoader(['.', '../templates'])`, copy-only split,
  per-file/dir render with `UndefinedError` → `UndefinedVariableInTemplate`
  (and `rmtree` unless kept), `post_gen_project` hook; returns abspath string.

### 2.3 `prompt.py` — every prompt function + `prompt_for_config` no_input semantics

Def lines: `read_user_variable:25`, `YesNoPrompt:45`, `read_user_yes_no:61`,
`read_repo_password:83`, `read_user_choice:91`, `process_json:141`,
`JsonPrompt:161`, `read_user_dict:174`, `render_variable:199`,
`_prompts_from_options:239`, `prompt_choice_for_template:250`,
`prompt_choice_for_config:262`, `prompt_for_config:284`,
`choose_nested_template:366`, `prompt_and_delete:406`.

- `read_user_variable(var_name, default_value, prompts=None, prefix="")`
  (`:25`): rich `Prompt.ask` with default; honors `__prompts__` mapping.
- `YesNoPrompt(Confirm)` (`:45-58`): true-set / false-set listed above; else
  `InvalidResponse`.
- `read_user_yes_no` (`:61`): `YesNoPrompt.ask` wrapper.
- `read_repo_password(question)` (`:83`): password prompt (used for zip retry).
- `read_user_choice(var_name, options, prompts=None, prefix="")` (`:91-138`):
  numbered menu, default = option 1; `[]` → bare `ValueError`; supports
  `__prompt__` + per-option labels.
- `process_json` (`:141`) / `JsonPrompt` (`:161`) / `read_user_dict` (`:174`):
  JSON-dict prompt; non-dict JSON or decode failure → `InvalidResponse`;
  non-dict default → `TypeError`.
- `render_variable(env, raw, cookiecutter_dict)` (`:199-236`): `None`/`bool`
  pass through; dict keys+values and list items render recursively; other
  non-str coerced with `str()`; strings rendered as Jinja with
  `cookiecutter=<answered-so-far>` (later defaults can reference earlier keys).
- `prompt_choice_for_template(key, options, no_input)` (`:250-260`):
  `no_input` → `opts[0]`, no render.
- `prompt_choice_for_config(cookiecutter_dict, env, key, options, no_input, …)`
  (`:262-281`): renders each option, `no_input` → first rendered (empty → `ValueError`).
- `prompt_for_config(context, no_input=False)` (`:284-363`) — the two-pass core:
  pops `__prompts__`; pass 1 iterates raw items in file order — `_*` (single
  underscore) copied verbatim, `__*` (double) Jinja-rendered without prompting,
  `list` → choice, `bool` → yes/no (**`no_input` → keep raw bool via
  `render_variable`**), scalar → render then prompt unless `no_input`
  (`:300-342`); pass 2 renders `dict` values (prompting for JSON unless
  `no_input` or `__*`; single-`_`-private dicts skipped at `:370-372` logic →
  actually `:345-347`); any `UndefinedError` → `UndefinedVariableInTemplate`.
  `no_input=True` therefore means: defaults + `extra_context`, first choices,
  raw bools, rendered dicts — **zero interactive reads**.
- `choose_nested_template(context, repo_dir, no_input=False)` (`:366-403`):
  new-style `templates: {opt: {path, title, description}}` menu (labels via
  `_prompts_from_options`, `:239-247`) or old-style `template` regex
  `\((.+)\)` path extraction; non-relative/absolute → `ValueError("Illegal template path")`.
- `prompt_and_delete(path, no_input=False)` (`:406-429`): `no_input` → delete
  (dir → `rmtree`, file → `os.remove`) and return `True`; else ask, falling back
  to reuse-or-`sys.exit()`.

### 2.4 `hooks.py` — execution model (hooks.py:27-201)

- Hook names: `_HOOKS = ['pre_prompt', 'pre_gen_project', 'post_gen_project']`
  (`:27-31`); `EXIT_SUCCESS = 0` (`:32`).
- `valid_hook(hook_file, hook_name)` (`:35-49`): basename == hook name, in
  `_HOOKS`, not `*~` backup. Extension is irrelevant — a `.py` hook and a shell
  hook with the same basename **both** match and both run.
- `find_hook(hook_name, hooks_dir='hooks')` (`:51-78`): CWD-relative lookup;
  returns abspath list or `None` (no dir / no matches). Callers run it under
  `work_in(repo_dir)` / `work_in(template_dir)` so resolution is repo-relative.
- `run_script(script_path, cwd='.')` (`:80-105`): **dispatch** — `*.py` →
  `[sys.executable, script]`; anything else → `[script]` executed directly
  (shebang/`chmod +x` via `make_executable`, `utils.py:71-77`); Windows runs
  through shell (`shell=True` iff `sys.platform.startswith('win')`); non-zero
  exit → `FailedHookException`; `ENOEXEC` → `FailedHookException(might be an
  empty file or missing a shebang)`.
- `run_script_with_context(script_path, cwd, context)` (`:108-127`):
  **from_string render** — hook file read as UTF-8, rendered with
  `create_env_with_context(context)` (`env.from_string(contents).render(**context)`),
  written to a `NamedTemporaryFile(delete=False, suffix=<orig ext>)`, then
  `run_script(temp.name, cwd)`. (Temp file is not deleted by this function —
  OS temp cleanup owns it.)
- `run_hook(hook_name, project_dir, context)` (`:130-144`): find + run each
  script with `cwd=project_dir` (the *generated* project, not the repo).
- `run_hook_from_repo_dir(repo_dir, hook_name, project_dir, context, delete_project_on_failure)`
  (`:147-177`): `work_in(repo_dir)` wrapper; on `FailedHookException` /
  `UndefinedError` optionally `rmtree(project_dir)`, logs, re-raises.
- `run_pre_prompt_hook(repo_dir)` (`:180-201`): runs `pre_prompt` (no context —
  runs from a **temp copy** via `create_tmp_repo_dir`, returns the copy path);
  failure → `FailedHookException('Pre-Prompt Hook script failed')`.

### 2.5 `environment.py` — StrictEnvironment / StrictUndefined

- `ExtensionLoaderMixin.__init__(*, context=None, **kwargs)` (`:12-57`):
  always loads 5 defaults — `JsonifyExtension`, `RandomStringExtension`,
  `SlugifyExtension`, `TimeExtension`, `UUIDExtension` — plus dotted paths from
  `cookiecutter._extensions` (`_read_extensions`, `:59-71` region … actually
  `:44-57`); unimportable → `UnknownExtension`.
- `StrictEnvironment(ExtensionLoaderMixin, Environment)` (`:59-71`): sets
  `undefined=StrictUndefined`. Effect: any missing key in a filename, dir name,
  file body, hook script, or prompt default raises `UndefinedError`, which the
  generate/prompt layers convert to `UndefinedVariableInTemplate`. This is why
  flet strips `None` values from `extra_context` (a `None` *present* renders as
  `None`, a *missing* key hard-fails — flet chose defined-and-None-free).
- `create_env_with_context(context)` (`utils.py:102-106`): honors
  `cookiecutter._jinja2_env_vars` (e.g. custom delimiters) + always
  `keep_trailing_newline=True`.

### 2.6 `extensions.py` — every Jinja extension

Def lines: `JsonifyExtension:24`, `RandomStringExtension:37`,
`SlugifyExtension:54`, `UUIDExtension:96`, `TimeExtension:110`.

| Extension | Surface | Notes |
|---|---|---|
| `JsonifyExtension` | filter `jsonify(obj, indent=4)` → `json.dumps(obj, sort_keys=True, indent=indent)` | deterministic key order. |
| `RandomStringExtension` | global `random_ascii_string(length, punctuation=False)` | `secrets.choice` over `ascii_letters` (+ `string.punctuation` iff true). |
| `SlugifyExtension` | filter `slugify(value, entities=True, decimal=True, hexadecimal=True, max_length=0, word_boundary=False, separator=DEFAULT_SEPARATOR, save_order=False, stopwords=(), regex_pattern=None, lowercase=True, replacements=(), allow_unicode=False)` | passthrough to `python-slugify`; flet uses sibling `slugify` in Python (not this filter) for `project_name_slug`. |
| `UUIDExtension` | global `uuid4()` → `str(uuid.uuid4())` | |
| `TimeExtension` | tag `{% now 'timezone' [, 'format'] %}` + shifting `{% now 'tz' + 'days=1,hours=2' %}` | default format `%Y-%m-%d` (`environment.extend(datetime_format=…)`); offset grammar `interval=value` comma list, `arrow` shift; `parse()` at `extensions.py:139-175`. Date deps (arrow/dateutil/tzdata) exist for this tag. |

Custom `_extensions` from a template resolve via `sys.path` patch (§2.1) —
another arbitrary-code vector alongside hooks (see §4).

### 2.7 `replay.py` — dump / load + JSON-serializability

- `get_file_name(replay_dir, template_name)` (`:19-23`): appends `.json` unless
  present; `os.path.join(replay_dir, …)`.
- `dump(replay_dir, template_name, context)` (`:26-37`): `make_sure_path_exists`,
  requires `cookiecutter` key else `ValueError`, `json.dump(context, indent=2)`.
- `load(replay_dir, template_name)` (`:40-51`): `json.load`, same key guard.
- **Constraint:** context must survive a `json.dump`/`json.load` round-trip.
  Non-serializable `extra_context` (datetime, Path, set, custom objects) fails
  at dump time — *after* prompting but *before* generation. Keep values to
  str/bool/int/float/list/dict/None (and flet strips `None`s for StrictUndefined
  reasons). Default replay/config dirs: `~/.cookiecutter_replay/`,
  `~/.cookiecutters/` (`config.py:28-33`).

### 2.8 `config.py`, `find.py`, `utils.py` (all public helpers)

- `config.py`: `USER_CONFIG_PATH = ~/.cookiecutterrc` (`:20`);
  `BUILTIN_ABBREVIATIONS = {gh, gl, bb}` (`:22-26`);
  `DEFAULT_CONFIG = {cookiecutters_dir, replay_dir, default_context: OrderedDict(), abbreviations}` (`:28-33`);
  `_expand_path` (`:36-39`, envvars + `~`); `merge_configs` (`:42-58`,
  recursive dict merge preserving sibling keys); `get_config` (`:61-86`,
  missing → `ConfigDoesNotExistException`, bad YAML/non-dict →
  `InvalidConfiguration`, expands both dirs);
  `get_user_config(config_file=None, default_config=False)` (`:89-140`):
  dict → merge-and-return; truthy non-dict → shallow-copy defaults (config
  ignored); explicit path (identity-compared against `USER_CONFIG_PATH`) →
  `get_config`; else `$COOKIECUTTER_CONFIG` (missing file **raises**) else
  `~/.cookiecutterrc` if present else defaults.
- `find.py:18-38` `find_template(repo_dir, env)`: first child whose name contains
  `cookiecutter` **and** the env's `variable_start_string`/`variable_end_string`
  (default `{{`/`}}` unless `_jinja2_env_vars` overrides — **unverified**
  delimiter-override interplay, flag as such); else
  `NonTemplatedInputDirException`. Multiple candidates → first `os.listdir`
  hit wins (order-dependent; templates must contain exactly one).
- `utils.py`: `force_delete` (`:25-32`, `rm -rf` onerror handler);
  `rmtree` (`:35-40`); `make_sure_path_exists` (`:43-53`);
  `work_in` (`:56-68`, chdir context manager, restores CWD);
  `make_executable` (`:71-77`, adds `S_IEXEC`);
  `simple_filter` (`:80-89`, decorator turning a function into a Jinja filter
  extension); `create_tmp_repo_dir` (`:92-99`, recursive copy to
  `mkdtemp(prefix='cookiecutter')`); `create_env_with_context` (`:102-106`).

### 2.9 `exceptions.py` — every exception (exceptions.py:1-180)

Base `CookiecutterException(Exception)` (`:11-16`). All subclasses carry only
docstrings except `UndefinedVariableInTemplate(message, error, context)`
(`:125-147`, attrs `.message/.error/.context`, `__str__` interpolates
`error.message`):

`NonTemplatedInputDirException` (`:19`), `UnknownTemplateDirException` (`:28`,
unused locally), `MissingProjectDir` (`:39`, unused locally),
`ConfigDoesNotExistException` (`:50`), `InvalidConfiguration` (`:59`),
`UnknownRepoType` (`:68`), `VCSNotInstalled` (`:76`),
`ContextDecodingException` (`:84`), `OutputDirExistsException` (`:92`),
`EmptyDirNameException` (`:100`), `InvalidModeException` (`:108`),
`FailedHookException` (`:117`), `UndefinedVariableInTemplate` (`:125`),
`UnknownExtension` (`:150`), `RepositoryNotFound` (`:158`),
`RepositoryCloneFailed` (`:166`), `InvalidZipRepository` (`:174`).
CLI catches the operational subset and exits 1 (`cli.py:234-258`).

### 2.10 `zipfile.py` + repository/vcs + requests path

- `unzip(zip_uri, is_url, clone_to_dir='.', no_input=False, password=None)`
  (`zipfile.py:17-125`): URL zips cached by last-path-segment into
  `clone_to_dir` with `prompt_and_delete` re-download gating (`:41-58`);
  **download via `requests.get(zip_uri, stream=True, timeout=100)`**,
  1 KiB chunks (`:54-58` — no checksum, no auth, plain TLS via certifi);
  local zips used as-is (`:59-61`); validation: empty namelist or missing
  top-level dir → `InvalidZipRepository` (`:70-80`); **`extractall`** into
  `tempfile.mkdtemp()` (`:84-89`) — no per-entry sanitization in this function
  (trust the source); password-protected: `password` arg → one retry else
  `InvalidZipRepository`; `no_input` + locked → `InvalidZipRepository`;
  interactive → up to 3 `read_repo_password` retries (`:90-119`);
  `BadZipFile` → `InvalidZipRepository` (`:121-123`).
- `repository.py`: `REPO_REGEX` (`:16-25`, git/hg/ssh/file/https/user@);
  `is_repo_url` (`:28-30`), `is_zip_file` (`:33-35`, lowercase `.zip` suffix);
  `expand_abbreviations` (`:38-53`); `repository_has_cookiecutter_json`
  (`:56-67`); `determine_repo_dir` (`:70-139`): zip → `unzip` (cleanup=True);
  URL → `clone` (cleanup=False); else local candidates
  `[template, clone_to_dir/template]` (+ `directory` suffix); first dir
  containing `cookiecutter.json` wins else `RepositoryNotFound`.
- `vcs.py`: `identify_repo` (`:33-51`, `git+`/`hg+` prefix, `git`-in-URL →
  git, `bitbucket` → hg, else `UnknownRepoType`); `is_vcs_installed` (`:54-60`,
  `shutil.which`); `clone(repo_url, checkout=None, clone_to_dir='.', no_input=False)`
  (`:63-139`): `git clone` + optional `checkout` via subprocess (hg checkout
  gets `--` injection guard, `:115-116`); cached-dir → `prompt_and_delete`;
  `not found` → `RepositoryNotFound`; pathspec/unknown-revision
  (`BRANCH_ERRORS`, `:27-30`) → `RepositoryCloneFailed`.
- `cli.py` surface (for completeness): `version_msg:38`,
  `validate_extra_context:45` (CLI `KEY=VAL` pairs), `list_installed_templates:62`,
  `main:171` click command with `--no-input/-c/--directory/--replay(-file)/
  -f/-s/-o/--config-file/--default-config/--debug-file/--accept-hooks{yes,ask,no}/
  -l/--keep-project-on-failure` (verified `cli.py:87-170`); password from
  `$COOKIECUTTER_REPO_PASSWORD`; `log.py:22 configure_logger`
  (`LOG_LEVELS` `:8-14`, formats `:16-19`).

---

## 3. How flet-cli uses it exactly

### 3.1 Build path — the app-shell stamp (`flet_cli/commands/build_base.py:1892-1908`, flet-cli 1.0.4)

```python
try:
    from cookiecutter.main import cookiecutter      # build_base.py:1893

    cookiecutter(                                    # build_base.py:1895
        template=template_url,                       # local cached zip path (see below)
        checkout=checkout,                           # template_ref, default = flet version
        directory=template_dir,                      # template subdir option/pyproject
        output_dir=str(self.flutter_dir.parent),     # <project>/build/<platform>/flutter
        no_input=True,                               # never prompt during builds
        overwrite_if_exists=True,                    # re-render placeholder assets
        extra_context={
            k: v for k, v in self.template_data.items() if v is not None
        },                                           # None-stripping for StrictUndefined
    )
except Exception as e:
    rmtree(self.flutter_dir)
    self.cleanup(1, f"{e}")
```

Params used: `template`, `checkout`, `directory`, `output_dir`, `no_input`,
`overwrite_if_exists`, `extra_context`. **Not** passed (defaults apply):
`replay`, `config_file`, `default_config`, `password`, `skip_if_file_exists`,
`accept_hooks=True` (hooks run), `keep_project_on_failure=False`.

Template resolution just above (`build_base.py:1830-1871`):

- `template_url = options.template or pyproject[tool.flet.template]`;
- `template_ref = options.template_ref or pyproject[…] or flet.version.flet_version`
  (`:1834-1838`) — default pin = the flet version;
- default source `DEFAULT_TEMPLATE_URL =
  "https://github.com/flet-dev/flet/releases/download/v{version}/flet-build-template.zip"`
  (`build_base.py:67-71`);
- `template_url = str(get_cached_template_zip(template_source, template_ref))`
  (`:1858-1860`); `checkout = template_ref` when using the default URL;
  status line `Creating app shell from {template_source}[ with ref "…"]`
  (`:1886-1890`).

### 3.2 Template cache (flet-side, stdlib — NOT cookiecutter's downloader)

`flet_cli/utils/template_cache.py:21-48` `get_cached_template_zip(url, version)`:
cache path `<FLET_CACHE_DIR|~/.flet/cache>/build-template/v<version>/flet-build-template.zip`
(`:27-29`, root via `get_cache_root()` `:7-18` honoring `$FLET_CACHE_DIR`);
**"use if present, else download once" — no revalidation, no checksum/signature**
(`:24-25` docstring + `:31-32` size->0 short-circuit); download via
`urllib.request.urlopen` → `.tmp` + `fsync` + `os.replace` (`:37-42`).
Because `template` arrives as a **local path**, cookiecutter's `requests` zip
path (§2.10) is bypassed for builds — cookiecutter only unzips locally.

### 3.3 What the context carries (`setup_template_data`, `build_base.py:1021-1660`)

`self.template_data` is assigned at `:1521`. Verified keys (all must exist in the
template's `cookiecutter.json` or be silently dropped per §2.2 — the reference
doc's typo warning): `out_dir`, `sep`, `python_module_name`,
`route_url_strategy`, `web_renderer`, `pwa_background_color`, `pwa_theme_color`,
`pwa_short_name`, `no_wasm`, `no_cdn`, `pyodide_version`, `base_url`,
`no_cdn_js`, `canvas_kit_base_url_js`, `pyodide_url_js`,
`font_fallback_base_url_js` (via `_resolve_web_runtime_js`, `:1670+`),
`split_per_abi`, `test_mode`, `project_name`, `project_name_slug`,
`artifact_name`, `product_name`, `project_description`, `pubspec_description`,
`linux_desktop_exec`, `linux_categories`, `org_name`, `bundle_id`,
`company_name`, `copyright`, `ios_export_method`, `ios_provisioning_profile`,
`ios_signing_certificate`, `ios_export_options`, `ios_team_id`,
`options{package_platform, config_platform, python_version, target_arch,
android_excluded_abis, info_plist, macos_entitlements, android_permissions,
android_features, android_meta_data, android_gradle_properties,
android_proguard_rules, android_providers, deep_linking{scheme,host},
android_signing, android_legacy_packaging}`, `flutter{dependencies}`,
`boot_screen`, `splash`, `adaptive_icon_background`, `pyproject` (whole TOML).
`[tool.flet.flutter.pubspec.*]` overrides are applied **post-render** to
`pubspec.yaml` via YAML (not cookiecutter) — reference doc, **unverified**
against this install's flet-cli lines (not re-read here).

The sibling `create` path (`flet_cli/commands/create.py:134-142`) stamps new
projects with the same `no_input=True, overwrite_if_exists=True` shape
(positional template + `checkout/directory/output_dir/extra_context`).

---

## 4. Fullest utilization & safety

### 4.1 Writing OUR OWN templates (when it pays)

Cookiecutter is a generic deterministic renderer — nothing stops us from using
it outside `flet build`. Legitimate future uses (all build-host/dev-host, never
on-device):

- **Per-distro script templates:** a `cookiecutter.json` with
  `{distro_alias, image_ref, arch, packages[]}` rendering `install.sh`,
  `manifest.json`, probe lists — one reviewed template instead of N hand-copied
  shell files. Choice variables enforce the certified catalog
  (`["ubuntu:24.04","debian:bookworm","alpine:3.21"]`); first item = default
  under `no_input` (§2.3).
- **CI matrix / scaffold stamping:** app-scaffold, screen, service templates
  with `_copy_without_render` for binary fixtures and `_extensions` pinned to
  the 5 built-ins (no custom extension code → no extra code-exec vector).
- Template-authoring rules that follow from §2: single `{{cookiecutter…}}`
  top dir (`find.py`); `_jinja2_env_vars` only if delimiters must change;
  `_new_lines` for CRLF-sensitive guests; `__prompts__` for friendly CLI text;
  `__`-prefixed keys for computed-only values (never prompted).

### 4.2 The JSON-serializability constraint (hard)

`extra_context` + merged context must survive `json.dump` (`replay.dump`,
`replay.py:36-37`) on **every** run — even `no_input` (flet path dumps too,
`main.py:164`). Pass only str/bool/int/float/list/dict/None; convert
`Path`→`str`, `datetime`→ISO, `set`→sorted list, enums→values at the call site.
Non-serializable input fails *after* repo resolution but *before* any file is
written — loud, but late. flet's own `template_data` complies (plain scalars +
  nested dicts/lists; `None`s stripped for StrictUndefined, §2.1).

### 4.3 Hook safety (hooks execute — treat templates as code)

`accept_hooks` defaults True and flet does not override it: `pre_prompt`,
`pre_gen_project`, `post_gen_project` from the template run with the
build user's privileges; hook bodies are Jinja-rendered with the full context
(`run_script_with_context`, `hooks.py:108-127`) and `.py` hooks run under the
build interpreter (`:80-105`). Policy: only first-party template refs
(`template_ref == flet version`); never `--template`/`--template-dir` at
untrusted URLs/paths in CI; review hook diffs on every flet bump; run builds in
ephemeral CI runners; `pre_prompt` can additionally redirect the whole repo to
a temp copy (`hooks.py:180-201`) — do not assume the source tree is untouched.

### 4.4 The cached-template checksum gap + what to do in CI

Gap (verified): `get_cached_template_zip` performs **no hash/signature check**
and never revalidates (`template_cache.py:21-32`); cookiecutter's own zip path
likewise has no checksum (`zipfile.py:52-58`). A poisoned
`~/.flet/cache/build-template/v*/flet-build-template.zip` (or MITM at first
fetch) persists silently across builds, and its hooks execute (§4.3).
Mitigations (concrete, CI-ready):

1. Pin `template_ref = flet_version` (the default); forbid custom
   `--template/--template-ref/--template-dir` in release workflows (lint the
   workflow call).
2. Pre-seed + verify: in CI, download the release zip, check `sha256` against
   a checked-in `build-template.sha256` (maintained at each flet bump),
   place it at the exact `v<version>/` cache path with `FLET_CACHE_DIR` set —
   cache-hit path then skips the network entirely.
3. Log `template_source + ref` (already in build status, `build_base.py:1886`)
   into build artifacts; fail closed if the cache file is absent-but-expected.
4. Prefer ephemeral runners so a poisoned cache cannot persist; where runners
   persist, key the cache dir per-branch/commit or wipe `build-template/` nightly.
5. Upstream ask (unverified — no upstream contact made): publish
   `flet-build-template.zip.sha256` / Sigstore attestation alongside releases.

---

## 5. How this dependency makes our app significantly better than Termux's proot-distro

Termux's proot-distro story is **manual packaging**: shell install scripts,
hand-maintained package metadata, and per-device `proot`/`bsu` behavior that
drifts between Termux repos and user installs. Cookiecutter (via flet-cli)
gives our app the opposite foundation — a **deterministic, config-driven build
shell**:

- **One config → one shell, reproducibly.** `setup_template_data`
  (`build_base.py:1021-1660`) derives the entire Flutter host (bundle id,
  permissions, gradle props, splash/icon resources, pubspec deps) from
  `pyproject.toml` + CLI flags, and cookiecutter stamps it with
  `no_input=True, overwrite_if_exists=True` (`:1895-1905`). Re-running the same
  commit re-renders byte-equivalent scaffolding; Termux-style manual edits to
  generated projects have no equivalent — drift is structurally impossible
  (unknown keys fail safe-silent, §2.2, so CI should diff `template_data`
  keys against the template's `cookiecutter.json` — exact key list **unverified**
  for the remote zip, flagged for the flet-bump checklist).
- **Version-locked template ref.** Default `checkout = flet_version`
  (`:1834-1838`) with `DEFAULT_TEMPLATE_URL` (`:67-71`) ties the native shell
  to the exact flet release under test — the analogue of our
  `proot-distro==5.10.0` floor. Termux users routinely mix package vintages;
  our CI matrix (M5 `build-all.yml`) tests one known-good pair.
- **Strict rendering fails closed.** `StrictUndefined` (§2.5) + stripped
  `None`s mean a misconfigured `pyproject` key errors at stamp time instead of
  shipping a half-rendered `AndroidManifest.xml` — contrast silent Termux
  packaging breakage discovered on-device.
- **Caveats (trust boundary, from the reference doc, restated):** the zip cache
  has no checksum and template hooks execute at build time — the determinism
  above holds only while the template source is trusted (first-party release
  zip, §4.4). On-device, none of this code runs: cookiecutter, Jinja2,
  requests, and hooks are build-host-only; the APK carries only the *rendered*
  shell plus our `proot-distro` payload.

---

## 6. Verification

- Installed tree read in full: `main.py` (212 lines), `generate.py` (466),
  `prompt.py` (438), `hooks.py` (201), `environment.py` (71),
  `extensions.py` (175), `replay.py` (51), `config.py` (140), `find.py` (38),
  `utils.py` (106), `exceptions.py` (180), `zipfile.py` (125),
  `repository.py` (139), `vcs.py` (139), `cli.py` (258), `log.py` (56),
  `__main__.py` (6), `__init__.py` (5). Def/constant lines cited inline.
- `cookiecutter.__version__ == 2.7.1` via
  `.venv/Scripts/python.exe -c "import cookiecutter; …"`.
- flet-cli 1.0.4 call sites quoted: `flet_cli/commands/build_base.py:1892-1908`
  (+ resolution `:1830-1871`, URL `:67-71`, `template_data:1521+`),
  `flet_cli/commands/create.py:134-142`,
  `flet_cli/utils/template_cache.py:1-48`.
- Reference companion: `docs/reference/dep-cookiecutter-stack.md` (mechanics,
  trust boundary, bump groups); milestones: `docs/roadmap.md` (M5 build ritual,
  D3 row).
- **Unverified** (explicit): remote `flet-build-template.zip`'s
  `cookiecutter.json` key list and hook contents; `entry_points.txt` target;
  `_jinja2_env_vars` delimiter-override interplay with `find_template`;
  post-render pubspec-patch code path (carried over from the reference doc).
