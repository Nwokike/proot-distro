# jinja2 3.1.6 — template engine

Identity: Jinja2 3.1.6, BSD (`METADATA` License-File; BSD License classifier), pure
Python. Requires `MarkupSafe>=2.0` (`METADATA Requires-Dist`). Ceiling: Jinja2<4 —
bump with markupsafe (dep-cookiecutter-stack.md).

## Complete public API (grouped; verified by source + introspection)

Core: `Environment`, `BaseEnvironment`, `Template`, `StrictUndefined`, `Undefined`,
`ChainableUndefined`, `DebugUndefined` (`jinja2/__init__.py`, `environment.py`).
Cookiecutter's `StrictEnvironment(ExtensionLoaderMixin, Environment)` sets
`undefined=StrictUndefined` (`environment.py:59-71`) — missing keys fail closed.
Loaders: `FileSystemLoader`, `DictLoader`, `PackageLoader`, `BaseLoader`,
`FunctionLoader`, `PrefixLoader`, `ChoiceLoader`, `ModuleLoader`, `TemplateNotFound`.
(`select_autoescape` lives in `jinja2.utils`, not top-level — the similarly named
top-level import fails; verified.)
Extension authoring: `jinja2.ext.Extension`, `jinja2.nodes.*`, `jinja2.parser.Parser`;
cookiecutter's five built-ins are auto-loaded (`environment.py:36-42`):
`JsonifyExtension` (`jsonify` filter), `RandomStringExtension`
(`random_ascii_string` global), `SlugifyExtension` (`slugify` filter),
`TimeExtension` (`{% now %}` tag), `UUIDExtension` (`uuid4` global).
Filters: ~60 `do_*` built-ins (`jinja2/filters.py`: `do_capitalize/title/upper/lower/
trim/striptags/join/split/sort/unique/sum/map/select/reject/groupby/dictsort/batch/
slice/first/last/random/urlize/urlencode/tojson/wordcount/filesizeformat/pprint/
indent/center/truncate/wordwrap/xmlattr/replace/format/round/int/float/list/attr/
default/items/max/min/format_number` family); globals include `range`, `dict`,
`namespace()`, `cycler()`, `joiner()`, `lipsum()`.
Native output: `jinja2.nativetypes.NativeEnvironment` (renders to Python objects).
Also: `jinja2.sandbox.SandboxedEnvironment`, `jinja2.meta.find_undeclared_variables`,
`jinja2.exceptions.TemplateSyntaxError/UndefinedError/TemplateError`.

## Example

```python
from jinja2 import StrictUndefined, Environment, DictLoader
env = Environment(loader=DictLoader({"p": "distro={{ name }} arch={{ arch|default('aarch64') }}"}),
                  undefined=StrictUndefined)
print(env.get_template("p").render(name="alpine"))  # missing arch -> default, typo'd key -> error
```

## How cookiecutter/flet uses it

Everywhere: `generate.py:16` (`Environment, FileSystemLoader`), `prompt.py`,
`find.py:13` (render path inside template names), `hooks.py`/`utils.py:106`
(`StrictEnvironment(context=..., keep_trailing_newline=True)`), `environment.py:71`
(`undefined=StrictUndefined`). Consequences that matter (dep-cookiecutter-stack.md):
typo'd top-level `extra_context` keys are silently ignored (must exist in
cookiecutter.json); non-serializable context breaks replay; `None`s are stripped.
Post-render, flet-cli applies `[tool.flet.flutter.pubspec.*]` overrides to
`pubspec.yaml` via YAML — not cookiecutter context.

## Our-project utilization — first-class (M3/M5 distro configs + profiles)

Jinja2 renders our distro/profile configs: per-distro install manifests, default shell
profiles, MOTD/login scripts with `{{ arch }}`, `{{ image_ref }}`, `{% now %}` stamps —
always with `StrictUndefined` so a typo fails at generation time, never on-device.
Use `DictLoader` for inline templates in tests, `FileSystemLoader` for a `templates/`
dir, and the cookiecutter extension idioms (`slugify` for container names, `uuid4` for
instance IDs) as the model for our own filter set.

## Better than Termux's proot-distro?

Yes, modestly: distro profiles become declarative templates with fail-fast rendering
instead of hand-edited shell/config blobs — fewer per-device snowflakes, reproducible
`apt`-ready images.

## Verification refs

- `.../cookiecutter/environment.py:36-42,59-71`, `generate.py:16`, `utils.py:81-106`,
  `find.py:13`, `extensions.py` (all five extensions + `{% now %}` tags)
- Introspected: filter list, utils (`select_autoescape`), `nativetypes`, top-level names
- `Jinja2-3.1.6` + `jinja2-3.1.6.dist-info/METADATA` (`Requires-Dist: MarkupSafe>=2.0`)
- `docs/reference/dep-cookiecutter-stack.md` (StrictUndefined/context mechanics)
