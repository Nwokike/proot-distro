# text-unidecode 1.3 — ASCII transliteration tables

Identity: text-unidecode 1.3, Artistic License (`METADATA` Summary: "The most basic
Text::Unidecode port"), pure Python, data-heavy (~3 MB transliteration table — the
reason `slugify._transliterate` skips backend import for pure-ASCII input,
`slugify.py:52`). One of three selectable slugify backends (`Backend` literal).

## Complete public API

One function (`text_unidecode/__init__.py:8`, signature introspected):
- `unidecode(txt) -> str` — maps every codepoint through the table to an ASCII
  approximation; unknown/unmappable codepoints become `?`-style fallbacks per the
  table data (exact fallback char unverified — spot-check with `help()`/REPL for
  your target scripts).

That is the entire module surface (introspected `dir()` shows only `unidecode` plus
dunders).

## Example

```python
from text_unidecode import unidecode
print(unidecode("Übuntu Débian 中文"))  # ASCII approximation, e.g. 'Ubuntu Debian ...'
from slugify import slugify
print(slugify("Übuntu Débian", backend="text-unidecode"))  # explicit backend pin
```

## How cookiecutter/flet uses it

Transitively: the `slugify` Jinja filter defaults to `backend='auto'`, which imports
`text_unidecode` when the standalone `unidecode` package is absent
(`slugify.py:55-63`) — the path cookiecutter template rendering takes in our venv
(no `unidecode` distribution installed; verified by `ls site-packages`). So every
`|slugify` call on non-ASCII input in template rendering runs through this table.

## Our-project utilization (M3 naming, with a size caveat)

Same container/profile naming pipeline as python-slugify — this is its engine. Caveat
for M2/M5: the ~3 MB table ships wherever slugify's non-ASCII path ships. Fine on the
build host; if slug-based naming ever moves on-device, measure the APK delta first or
restrict to `allow_unicode`/ASCII-only slugs. Keep it as a locked transitive dep, not
a direct import — always call it through `slugify(..., backend=...)`.

## Better than Termux's proot-distro?

Same naming-robustness story as slugify (its engine): non-Latin distro/profile names
transliterate instead of erroring. Invisible infrastructure, correctly boring.

## Verification refs

- `.../text_unidecode/__init__.py:8` (`def unidecode(txt)`); module `dir()` (single public name)
- `.../slugify/slugify.py:25,51-65` (Backend literal + auto-fallback chain)
- `text_unidecode-1.3.dist-info/METADATA`; venv listing (no standalone `unidecode` installed)
