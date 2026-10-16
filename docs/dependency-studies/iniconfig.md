# iniconfig 2.3.1 — Exhaustive API Reference

**Identity:** `iniconfig` 2.3.1 · MIT · "brain-dead simple config-ini parsing"
(`iniconfig-2.3.1.dist-info/METADATA`). Role: pytest's INI parser — reads
`pytest.ini` / `setup.cfg` / `tox.ini` style config and backs
`config.getini()` for `[tool.pytest.ini_options]`-equivalent string values.
Verification: installed source (`iniconfig/__init__.py`, `iniconfig/_parse.py`)
+ live `inspect.signature`. Unverifiable items marked **unverified**.

---

## 1. Parsing model

- Grammar: sections `[name]`, `key: value` or `key = value` lines, `#`-comments
  (verified: `iscommentline` at `_parse.py:158`, `_parseline` at `:99`,
  `parse_lines` at `:68`, `parse_ini_data` at `:18`). Comment-stripping is
  configurable at parse time (see `strip_inline_comments` below).
- `IniConfig.parse(path, data=None, encoding='utf-8', *,
  strip_inline_comments=True, strip_section_whitespace=False) -> IniConfig`
  (verified signature) — classmethod-style constructor (`__init__.py:126`).
- Constructor verified: `IniConfig(path, data=None, encoding='utf-8', *,
  _sections=None, _sources=None)`. `_sections`/`_sources` are private
  injection points (tests/tools); normal code uses `parse()`.
- `ParsedLine` NamedTuple (`_parse.py:11`): the intermediate line record
  (fields **unverified** — internal).
- Exceptions live in `iniconfig/exceptions.py` (module verified present;
  individual exception names **unverified**).
- `__version__` location **unverified** (`iniconfig/_version.py` exists;
  content not read).

## 2. Complete API with signatures

```python
# Construction
IniConfig.parse(path, data=None, encoding='utf-8', *,
                strip_inline_comments=True,
                strip_section_whitespace=False) -> IniConfig
IniConfig(path, data=None, encoding='utf-8', *, _sections=None, _sources=None)

# Section access
config[name] -> SectionWrapper          # __getitem__, :239
config.get(section, name=None, ...)      # overloaded :185-222 (see below)
section in config / iter(config)         # __contains__ :248, __iter__ :244
config.lineof(section, name=None) -> int | None   # :180 — source line for errors

# SectionWrapper (config["pytest"])
section[key] -> str                      # __getitem__, :73
section.get(key) -> str | None           # overloads :36-65:
section.get(key, default) -> str | default
section.get(key, default, convert=None)  # with converter applied when present
iter(section) -> Iterator[str]           # key names, :76
section.items() -> Iterator[tuple[str, str]]  # :84
section.lineof(name) -> int | None       # :32 (plus overload at :79)
```

`get` overloads (verified lines `:185-222` for `IniConfig`, `:36-65` for
`SectionWrapper`): the `convert` callable variant lets callers parse
`linelist`/`args`/`bool` shapes from raw strings — this is exactly how
pytest's `getini` turns INI text into typed config values.

## 3. How pytest uses it

pytest's cofig reader delegates INI-file parsing to `IniConfig` for
`pytest.ini`/`setup.cfg`/`tox.ini` discovery; `pyproject.toml`'s
`[tool.pytest.ini_options]` is read natively as TOML (string values kept
INI-compatible). The mutual-exclusion rule (`[tool.pytest]` vs
`[tool.pytest.ini_options]` → `UsageError`) lives in pytest, not iniconfig.

Nothing to configure: iniconfig has no options surface of its own. Relevance
to us is diagnostic — when `getini` returns an unexpected value, the cause is
usually INI grammar (indentation, comment stripping, section naming), and
`lineof()` pinpoints the source line.

---

## 4. How this dependency makes our app significantly better than Termux's proot-distro

1. **Config errors fail fast with line numbers.** `strict_config` +
   iniconfig's `lineof()` means a typo'd pytest key errors at startup naming
   the file and line. Termux's shell config (`proot-distro.sh` variables)
   fails silently or mid-install on a typo — discovered on-device, not at
   config-parse time.
2. **Typed ini access without hand-rolled parsing.** `get(key, default,
   convert)` gives the house `timeout`/`filterwarnings`/`markers` values
   validated types; Termux parses shell by convention with no validation
   layer at all.
3. **Portable across pytest's config files.** Whether CI passes config via
   `pyproject.toml` or a contributor uses `pytest.ini`, the same parser
   semantics apply — Termux has exactly one execution environment, so config
   portability was never a consideration for them; for us it keeps Windows
   laptops and Linux CI in agreement.

## 5. Verification refs

- Identity: `iniconfig-2.3.1.dist-info/METADATA`.
- `SectionWrapper`: `iniconfig/__init__.py:24-84` (methods/lines in §2 table).
- `IniConfig`: `__init__.py:89-248`; `__init__` + `parse` signatures live;
  `get` overloads `:185-222`; `lineof` `:180`.
- Parse layer: `_parse.py:11,18,68,99,158`; `exceptions.py` + `_version.py`
  existence only.
