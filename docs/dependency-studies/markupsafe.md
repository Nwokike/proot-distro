# markupsafe 3.0.4 — safe markup strings

Identity: MarkupSafe 3.0.4, BSD-3-Clause (`METADATA` License-Expression), Python +
optional C speedups (`markupsafe/_speedups.c` ships with a compiled
`_speedups.cp314-win_amd64.pyd` in this venv — pure-Python `_native.py` fallback is
used where no wheel ships, e.g. Android). Jinja2's escaping engine (`Requires-Dist:
MarkupSafe>=2.0`).

## Complete public API (introspected)

- `class Markup(str)` — HTML-safe string: `escape`, `unescape`, `striptags`, `format`,
  `join`, `split`, `rsplit`, `partition`, `rpartition`, `strip`, `rstrip`, `lstrip`,
  `removeprefix`, `removesuffix`, `replace`, `upper`, `lower`, `title`, `capitalize`,
  `casefold`, `zfill`, `encode` — all preserve/return `Markup`.
- `escape(s) -> Markup` — escape `&<>"'`; passes `Markup`/`__html__` through untouched.
- `escape_silent(s)` — like `escape` but maps `None` to `""`.
- `soft_str(s)` — `str()` that preserves `Markup` (verified re-exported through
  `jinja2.filters`: `filters.py:13-15` imports `escape, Markup, soft_str` from it).
- `EscapeFormatter` — `str.format`-compatible formatter that escapes substitutions.

## Example

```python
from markupsafe import Markup, escape
user = "<img src=x onerror=alert(1)>"
print(Markup("<b>{}</b>").format(user))  # <b>&lt;img src=x ...&gt;</b> -- structure kept, input escaped
print(escape(None.__class__.__name__))   # plain names pass through safely
```

## How cookiecutter/flet uses it

Transitively only: Jinja2 autoescaping calls `markupsafe.escape`/`Markup` on every
`{{ }}` substitution (`jinja2/filters.py:13-15,139,316`). Cookiecutter's own rendering
targets config/source files (autoescape off), so markupsafe is load-bearing only when
templates render HTML — and must bump in lock-step with jinja2 (bump group).

## Our-project utilization (M3/M4 defense in depth)

Any HTML we render — error dialogs with guest output, report pages, log viewers —
goes through Jinja2 `{{ }}` or explicit `escape()` so a malicious guest filename or
process listing cannot inject markup into the UI. Rule: never `Markup(untrusted)`;
build pages from `Markup` structure + escaped data (the example above is the pattern).

## Better than Termux's proot-distro?

Security-hygiene win: guest-controlled strings (filenames, package output) are escaped
by construction wherever we render rich text — a class of display-spoofing bugs Termux
output views do not systematically guard against.

## Verification refs

- Live introspection: members, `Markup.format`/`escape` signatures, `EscapeFormatter`
- `ls markupsafe/` (`_native.py`, `_speedups.c`, compiled `.pyd` present on this host)
- `.../jinja2/filters.py:13-15,139,316`; `Jinja2-3.1.6.dist-info/METADATA`
- `markupsafe-3.0.4.dist-info/METADATA` (BSD-3-Clause)
