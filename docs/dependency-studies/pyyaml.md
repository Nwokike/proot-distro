# pyyaml 6.0.3 — YAML parser and emitter

Identity: PyYAML 6.0.3, MIT (`METADATA` License: MIT), Python with optional compiled
`_yaml`/`CSafeLoader` bindings (verified: `yaml` has `CSafeLoader`, `CBaseLoader`;
this venv imports the `yaml` package backed by `_yaml`). The only serialization
format in this stack — cookiecutter config, flet-cli pubspec patching, and our own
manifests all flow through it.

## Complete public API

Top-level functions (`yaml/__init__.py`, names introspected):
- `safe_load(stream) -> object` — load YAML with `SafeLoader` (no arbitrary objects).
- `safe_load_all(stream) -> generator` — multi-document stream, safe.
- `load(stream, Loader) -> object` — explicit-Loader load (never omit Loader).
- `load_all(stream, Loader) -> generator` — multi-document variant.
- `safe_dump(data, stream=None, **kwds) -> str|None` — emit with `SafeDumper`.
- `dump(data, stream=None, Dumper=..., **kwds)` / `dump_all(documents, ...)` — full emit.
- `safe_dump_all` / `dump_all` — multi-document emit (unverified exact kwarg list —
  mirrors `dump`, labeled unverified beyond name existence).
- `add_representer / add_constructor / add_implicit_resolver / add_path_resolver` —
  type hooks (names verified on module; per-call signatures unverified, use `help()`).

Loader/Dumper classes (all present as attributes, verified):
- `SafeLoader`, `CSafeLoader` (C, fastest — preferred), `BaseLoader` (all scalars →
  strings), `FullLoader` (full YAML without arbitrary code), `UnsafeLoader`
  (full object construction — never on untrusted input), `Loader` (= FullLoader alias,
  unverified alias claim — check `yaml.Loader` before relying).
- `SafeDumper`, `CDumper`/`CSafeDumper` (names follow Loader pattern; C variant
  presence unverified on this host beyond `CSafeLoader`/`CBaseLoader`), `Dumper`.
- `YAMLError` (+ `MarkedYAMLError`, scanner/parser/composer/reader error subclasses) —
  catch `yaml.YAMLError` around every load.
- `YAMLObject`, `YAMLObjectMetaclass` — declarative serializable classes.
- `serialize / serialize_all / emit / parse / compose / scan` — event/token-level
  pipeline (names verified; reach for these only for custom tooling).

## Example

```python
import yaml
manifest = yaml.safe_load(open("container-manifest.json.yaml", encoding="utf-8"))
manifest["image_ref"] = "alpine:3.21"
with open("container-manifest.yaml", "w", encoding="utf-8") as f:
    yaml.safe_dump(manifest, f, sort_keys=True, allow_unicode=True)
try:
    doc = yaml.safe_load(untrusted_text)
except yaml.YAMLError:
    doc = {}
```

## How cookiecutter/flet uses it

- cookiecutter: `cookiecutter/config.py:11` (`import yaml`);
  `config.py:70` (`yaml_dict = yaml.safe_load(file_handle) or {}`),
  `config.py:71` (`except yaml.YAMLError as e:`) — user config load with merge
  against `DEFAULT_CONFIG` (`config.py:78`).
- flet-cli: `flet_cli/commands/build_base.py:13` (`import yaml`);
  `build_base.py:3615` (`def load_yaml(self, path):`),
  `:3627` (`return yaml.safe_load(f)`), `:3639` (`yaml.dump(doc, f)`);
  `pubspec.yaml` is read as YAML while still unrendered (`:1588-1591`,
  `pubspec_description` escaping) and patched post-render at `:1917,1932,1955,1968,2054`
  (`pubspec = self.load_yaml(self.pubspec_path)`) to apply
  `[tool.flet.flutter.pubspec.*]` overrides (dep-cookiecutter-stack.md).

## Our-project utilization — first-class (M3/M5 manifests)

PyYAML is our manifest layer: container `manifest.json` companions, distro catalog
entries (certified map: `ubuntu:24.04`, `debian:bookworm`, `alpine:3.21`), per-image
metadata (`oci_manifests/` mirrors), and build/CI config. Rules: always `safe_load`
+ `except yaml.YAMLError`; `sort_keys=True, allow_unicode=True` on every dump so
diffs are stable; `CSafeLoader`-equivalent default (`safe_load` picks C when present)
for the M5 Android compile-proof step that reads lock/manifest trees. M3
`proot_service.py` reads upstream's on-disk `manifest.json` files (JSON) but OUR
catalog/manifest sidecar format is YAML via this package.

## Better than Termux's proot-distro?

Operational edge: human-readable, hand-editable distro/manifest catalogs with strict
safe-load semantics — power users can add custom OCI refs as YAML instead of opaque
CLI flags, and malformed files produce a clean error, not a traceback.

## Verification refs

- Live introspection: `yaml.__version__` (unverified print — version from dist-info);
  `safe_load/safe_dump/load/dump/safe_load_all` signatures; `CSafeLoader/CBaseLoader/
  FullLoader/UnsafeLoader` attribute check
- `.../cookiecutter/config.py:11,70-78`
- `.../flet_cli/commands/build_base.py:13,930,1588-1591,1917,3615,3627,3639`
- `pyyaml-6.0.3.dist-info/METADATA` (MIT); `docs/reference/dep-cookiecutter-stack.md`
  (pyyaml notes + pubspec override mechanics); `docs/roadmap.md` §M3/M5
