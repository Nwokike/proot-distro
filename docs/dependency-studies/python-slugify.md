# python-slugify 9.1.3 — Unicode-aware slug generator

Identity: python-slugify 9.1.3, MIT (`METADATA` License-Expression), pure Python
(`slugify/slugify.py`; transliteration delegated to the `text-unidecode` backend).
`slugify/__init__.py` exports only `slugify` (verified: no `slugify_unicode` —
that import fails; there is no such name in 9.x).

## Complete public API (signatures introspected from source)

- `slugify(text, entities=True, decimal=True, hexadecimal=True, max_length=0,
  word_boundary=False, separator='-', save_order=False, stopwords=(),
  regex_pattern=None, lowercase=True, replacements=(), allow_unicode=False, *,
  replacement_stage='both', backend='auto', algorithm='legacy') -> str` —
  full signature verified live. Transliterates, strips entities, drops
  disallowed chars (`DISALLOWED_CHARS_PATTERN = r'[^-a-zA-Z0-9]+'`,
  `DISALLOWED_UNICODE_CHARS_PATTERN = r'[\W_]+'`, `DEFAULT_SEPARATOR = '-'`
  — `slugify.py:15-23`), truncates (`max_length`/`word_boundary`/`save_order`).
- `smart_truncate(string, max_length=0, word_boundary=False, separator='-',
  save_order=False)` (in `__all__`; exact defaults from source — verify with
  `help()` before relying on parameter order).
- `Backend = Literal['auto','text-unidecode','unidecode','anyascii']`
  (`slugify.py:25`); `ReplacementStage`, `Algorithm` literals (in `__all__`,
  semantics unverified — read source before using non-defaults).
- Backend resolution (`slugify.py:51-65`): `'auto'` tries `unidecode` first, falls
  back to `text_unidecode`; 7-bit ASCII skips backends entirely (note: text-unidecode's
  table is ~3 MB, hence the skip).

## Example

```python
from slugify import slugify
print(slugify("Debian Bookworm (OCI) — 2026!"))  # debian-bookworm-oci-2026
print(slugify("Übuntu image", allow_unicode=True))  # ubuntu-image (unicode path keeps word chars)
```

## How cookiecutter/flet uses it

`cookiecutter/extensions.py:15-16` (`from slugify import slugify as pyslugify`,
`from slugify.slugify import DEFAULT_SEPARATOR`); `SlugifyExtension` registers the
`slugify` Jinja filter with the full parameter mirror (`extensions.py:55-93`).
Template authors write `{{ cookiecutter.project_name|slugify }}` for safe directory/
identifier derivation. (`allow_unicode`/`backend`/`algorithm` kwargs exist in the
filter signature but are passed straight through — behavior pinned to the installed
python-slugify, not cookiecutter.)

## Our-project utilization (M3 container/distro naming)

Every user-typed name becomes a filesystem/OCI-safe identifier through `slugify`:
custom container names, imported-profile names, export filenames. Use
`separator="-"`, `lowercase=True` defaults; `allow_unicode=True` only where the
consumer (ext4 filename, OCI tag rules) provably accepts it. Backend: leave
`'auto'` (matches cookiecutter); pin text-unidecode in the lock so the fallback is
always present.

## Better than Termux's proot-distro?

Small UX win: friendly names ("My Debian Dev") map deterministically to safe
identifiers (`my-debian-dev`) with no illegal-character failures at install time —
Termux users hit raw `mkdir`/proot errors for bad names instead.

## Verification refs

- Live: full `slugify` signature; `slugify_unicode` ImportError (no such name);
  `__all__ = ['slugify','smart_truncate','Backend','ReplacementStage','Algorithm']`
- `.../slugify/slugify.py:15-25,51-65,122-151`; `.../cookiecutter/extensions.py:15-16,55-93`
- `python_slugify-9.1.3.dist-info/METADATA` (MIT)
