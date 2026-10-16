# packaging 26.3 — Exhaustive API Reference

**Identity:** `packaging` 26.3 · `Apache-2.0 OR BSD-2-Clause` ·
`Requires-Python: >=3.9` (`packaging-26.3.dist-info/METADATA`). The canonical
PEP-implementing library for versions, specifiers, requirements, markers,
tags, and wheel/sdist filenames. Role in our stack: vendored-adjacent
dependency of pytest (version/requirement checks) and flet-cli (dependency
resolution/build metadata). Verification: live `inspect.signature` +
introspection + source grep. Unverifiable items marked **unverified**.

---

## 1. `version` — `Version` + `parse`

Signatures verified live:

```python
Version(version: str) -> None   # constructor validates; raises InvalidVersion
parse(version: str) -> Version  # packaging.version.parse (verified present)
```

Attributes verified via `dir()`: `epoch`, `release`, `pre`, `post`, `dev`,
`local`, `public`, `base_version`, `major`, `minor`, `micro`,
`is_prerelease()`, `is_postrelease()`, `is_devrelease()`,
`from_parts(...)` (classmethod, signature **unverified**),
`normalize_pre` (helper, verified present), `VERSION_PATTERN` (regex,
verified present). Rich comparison across `Version` objects; `InvalidVersion`
on garbage input (name verified via `dir()` listing).

**pytest uses it** (`_pytest/config/__init__.py:1455`):
`from packaging.version import Version` for `minversion` enforcement.
**flet-cli uses it** for version comparisons in build/publish paths
(specific call sites **unverified** — module-level usage confirmed by
dependency edge only).

## 2. `specifiers` — `SpecifierSet` + `Specifier`

```python
SpecifierSet(specifiers: str | Iterable[Specifier] = '',
             prereleases: bool | None = None)
Specifier(spec: str = '', prereleases: bool | None = None)
```

Methods verified via `dir(SpecifierSet)`: `contains(item, prereleases=None)`,
`filter(iterable, prereleases=None)`, `is_subset(other)`,
`is_superset(other)`, `is_disjoint(other)`, `is_unsatisfiable()`,
`to_range()`, `prereleases` property. Supported operators (standard set —
**operator list unverified against this source tree**, conventional
`==, !=, <=, >=, <, >, ~=, ===`): pin semantics for house pins
(`flet==1.0.4`, `pytest>=x`).

## 3. `requirements` — `Requirement`

```python
Requirement(requirement_string: str)
```

Live parse demo (verified output):
`Requirement('flet>=1.0.4; python_version>="3.10"')` →
`.name == 'flet'`, `.specifier == >=1.0.4`, `.marker == python_version >= "3.10"`,
`.extras == set()`, `.url is None`. Attributes: `name`, `specifier`,
`marker`, `extras`, `url`. Raises `InvalidRequirement` on malformed input
(verified import path used by pytest at
`_pytest/config/__init__.py:1472-1473`).

**pytest uses it** (`:1472-1474`): `required_plugins` entries are parsed as
`Requirement`s and checked against installed dists via `Version` comparison —
the mechanism that lets the house config declare
`required_plugins = ["pytest-timeout>=2.4"]` style floors. **flet-cli uses it**
for parsing dependency declarations (call sites **unverified**).

## 4. `markers` — `Marker`

```python
Marker(marker: str)
```

Evaluates PEP 508 environment markers (`python_version`, `sys_platform`,
`os_name`, `platform_machine`, `extra`, ...). API shape
(`evaluate()` method — **method name/signature unverified** in this survey;
module + constructor verified). Directly relevant to Android CI: markers like
`sys_platform == "linux"` gate platform-specific test deps, and flet-cli
build logic branches on equivalent markers.

## 5. Remaining submodules (inventory; signatures unverified)

| Module | Purpose |
|---|---|
| `packaging.utils` | `canonicalize_name`, `canonicalize_version`, `parse_wheel_filename`, `parse_sdist_filename`, `is_normalized_name`, `BuildTag`, `InvalidName`, `InvalidWheelFilename`, `InvalidSdistFilename`, `NormalizedName` (all names verified via `dir()`) |
| `packaging.tags` | interpreter/ABI/platform tags (`sys_tags()` — name **unverified**) |
| `packaging.metadata` | `Metadata` parsing from wheel METADATA (**details unverified**) |
| `packaging.direct_url` | PEP 610 direct-URL records (**details unverified**) |
| `packaging.licenses` | license-expression handling, new in recent packaging (**details unverified**) |
| `packaging.ranges` | version-range algebra backing `to_range()` (**details unverified**) |
| `packaging.pylock`, `dependency_groups` | lockfile/dependency-group support (**details unverified**) |
| `packaging._elffile/_manylinux/_musllinux/_parser/_structures/_tokenizer` | private implementation |
| `packaging.errors` | error base types (**names unverified**) |

House-relevant: `canonicalize_name` for the `test_imports_vs_deps.py` guard
(normalize `flet-terminal` vs `flet_terminal` before comparing to lockfile
names); `parse_wheel_filename` for asserting M2 wheel ABI tags if a native
wheel ever lands in CI artifacts.

## 6. The ones pytest / flet-cli use (summary)

- pytest: `Version` (`minversion`), `Requirement` + `InvalidRequirement` +
  `Version` (`required_plugins`) — all three import sites verified with file:
  line in `pytest.md` §10.
- pytest also imports `packaging.version` in `_pytest/unittest.py:565`
  (unittest-integration version check) and `_pytest/outcomes.py:279`
  (`importorskip` minversion comparison) — verified by grep.
- flet-cli: packaging is a transitive dependency used in dependency/build
  metadata handling; exact call sites **unverified** (out of scope for the
  test-stack study; see the flet-cli study for its declared dependency edge).

---

## 7. How this dependency makes our app significantly better than Termux's proot-distro

1. **Machine-checked version floors.** `minversion` + `required_plugins` turn
   "works on my machine" into CI-enforced facts: the suite refuses to run
   against a pytest/plugin combo it wasn't validated for. Termux has no
   version discipline — scripts run against whatever `pkg` installed that
   week, and skew shows up as on-device breakage.
2. **Import-vs-deps guards are exact, not stringly.** `canonicalize_name` +
   `Requirement` parsing let `test_imports_vs_deps.py` compare normalized
   names and real specifiers instead of substring hacks — so the "bump a
   version" update path (roadmap §0) is verified by tests, not by hope.
   Termux's update path is "edit the script and push".
3. **Marker-aware test selection.** PEP 508 markers + pytest `-m` let the
   same suite express "desktop-only", "device-only (`live`)", and
   "python-version-gated" tests declaratively. Termux encodes all of that as
   `if [ ... ]` branches inside scripts that only run in one environment.

## 8. Verification refs

- Identity: `packaging-26.3.dist-info/METADATA`.
- `Version/SpecifierSet/Specifier/Requirement/Marker` constructor signatures:
  live `inspect.signature`; `utils` names: live `dir()`.
- `SpecifierSet` methods + `Version` attrs: live `dir()`.
- `Requirement` attribute demo: live parse run.
- pytest call sites: `_pytest/config/__init__.py:1455,1472-1474`,
  `_pytest/outcomes.py:279`, `_pytest/unittest.py:565` (grep-verified).
- flet-cli call sites: **unverified** (dependency edge only).
- §5 submodule details: inventory only, explicitly unverified.
