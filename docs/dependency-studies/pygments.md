# pygments 2.21.0 — exhaustive API reference (practical level)

Verified 2026-10-16 against `.venv/Lib/site-packages/pygments`
(`__init__.py`, `lexer.py`, `formatter.py`, `token.py`, `style.py`,
`lexers/`, `formatters/`, `styles/`, `filter.py`, `cmdline.py`, `console.py`).
Version via `pygments.__version__ == "2.21.0"`. License: BSD-2-Clause
(`pygments-2.21.0.dist-info/METADATA` → `License-Expression: BSD-2-Clause`).
Runtime deps: NONE, except `colorama>=0.4.6` on the `windows-terminal` extra
(verified `Requires-Dist`). Pure-Python (regex-based lexers). Scale: **602**
lexers (verified `len(list(get_all_lexers()))`), 18 formatters, 51 styles.

Identity: syntax-highlighting engine. Pipeline: source text → `Lexer`
(`get_tokens` yields `(TokenType, str)` pairs) → `Formatter` (`format`
consumes the stream) → output (HTML/terminal/LaTeX/SVG/…). Filters
(`filter.py`) transform token streams mid-pipeline.

## 1. Top-level functions (`pygments/__init__.py`)

```python
lex(code, lexer) -> Iterable[tuple[TokenType, str]]        # :35 — raw token stream
format(tokens, formatter, outfile=None) -> None|str        # :52 (builtin shadow;
                                                           #   returns str when outfile=None — unverified, labeled unverified)
highlight(code, lexer, formatter, outfile=None)            # :77 — lex + format in one
```

## 2. Lexer lookup (`pygments/lexers/`)

```python
get_lexer_by_name(_alias, **options) -> Lexer          # e.g. "python", "py", "docker"
get_lexer_for_filename(_fn, code=None, **options) -> Lexer
guess_lexer(_text, **options) -> Lexer                # content-based analysis
guess_lexer_for_filename(_fn, _text, **options) -> Lexer
find_lexer_class_for_filename(_fn, code=None) -> type[Lexer]|None
get_all_lexers() -> Iterable[(name, aliases, file_patterns, mimetypes)]
```

`get_all_lexers` entry shape (verified sample):
`('ABAP', ('abap',), ('*.abap', '*.ABAP'), ('text/x-abap',))`.
Enumeration strategy (how to list at runtime):

```python
from pygments.lexers import get_all_lexers
names   = sorted(name for name, _, _, _ in get_all_lexers())        # 602 display names
by_alias = {a: name for name, aliases, _, _ in get_all_lexers() for a in aliases}
by_glob  = [(pat, name) for name, _, pats, _ in get_all_lexers() for pat in pats]
```

## 3. `Lexer` base (`lexer.py`) — the practical surface

Class attrs: `name`, `aliases`, `filenames`, `alias_filenames`, `mimetypes`,
`url`, `priority`, `version_added`. Methods (verified `dir`):
`get_tokens(text)`, `get_tokens_unprocessed(text)` (adds `(index, ttype, value)`
offsets), `add_filter(filter)`, `analyse_text(text)` (static scoring used by
`guess_lexer`). Writing a custom lexer (unverified beyond class shape —
labeled unverified): subclass `RegexLexer`, define `tokens = {root: [...]}`;
NOT needed for our project.

## 4. Formatters — all 18 (`pygments/formatters/`, verified `FORMATTERS` keys)

```python
HtmlFormatter  TerminalFormatter  Terminal256Formatter  TerminalTrueColorFormatter
SvgFormatter  LatexFormatter  RtfFormatter  BBCodeFormatter  IRCFormatter
NullFormatter  RawTokenFormatter  TestcaseFormatter  GroffFormatter
PangoMarkupFormatter  BmpImageFormatter  GifImageFormatter  JpgImageFormatter
ImageFormatter
```

Lookup: `get_formatter_by_name(alias, **options)`,
`get_all_formatters()`, `get_formatter_for_filename(fn, **options)`.
`Formatter.__init__(self, **options)`; methods (verified): `format`,
`get_style_defs`, plus `name/aliases/filenames/unicodeoutput` attrs.
Key `HtmlFormatter` options (verified accepted as `**options`; constructor
itself takes only `**options`): `noclasses=False`, `style="default"`,
`linenos`, `cssclass`, `hl_lines`, `nowrap`, `full` (verified live:
`HtmlFormatter().noclasses is False`,
`.style is DefaultStyle`). Terminal family: `TerminalFormatter` (16 colors),
`Terminal256Formatter` (256-color escapes), `TerminalTrueColorFormatter`
(24-bit) — the ones rich's terminal output is modeled on.

## 5. Token types (`pygments/token.py`)

Hierarchy (verified names): root `Token` with children `Text Whitespace Escape
Error Other Keyword Name Literal String Number Operator Punctuation Comment
Generic` (+ `STANDARD_TYPES` mapping to CSS-ish names). Helpers:
`is_token_subtype(ttype, parent)`, `string_to_tokentype(s)`. Token values are
tuples used as dict keys — styles map `Token.Keyword` → `"bold #008000"` etc.

## 6. Styles — all 51 exist (verified `get_all_styles()`)

```text
abap algol algol_nu arduino autumn borland bw coffee colorful default dracula
emacs friendly friendly_grayscale fruity github-dark gruvbox-dark gruvbox-light
igor inkpot lightbulb lilypond lovelace manni material monokai murphy native
night-owl nord nord-darker one-dark paraiso-dark paraiso-light pastie perldoc
rainbow_dash rrt sas solarized-dark solarized-light staroffice stata-dark
stata-light tango trac vim vs xcode zenburn
```

API: `get_style_by_name(name) -> type[Style]`, `get_all_styles()`.
`Style` classvars (verified): `background_color`, `styles` (token→def dict),
`aliases`, `highlight_color`, `line_number_*`, `web_style_gallery_exclude`.
Verified: `get_style_by_name("monokai").background_color == "#272822"`.
Custom style (unverified pattern, standard documented usage — labeled
unverified): subclass `Style`, set `background_color` + `styles = {...}`.

## 7. Filters + CLI extras

`Filter` (`filter.py`): single method `filter(lexer, stream)`; built-ins in
`pygments/filters/` (codedoc, keywordcase, whitespace, gobble, tokenmerge… —
directory verified, individual behaviors unverified). `pygments/cmdline.py` =
`pygmentize` entry point; `pygments/console.py` = its own tiny ansiformat
helper (unrelated to rich). `pygments/sphinxext.py`, `modeline.py`,
`plugin.py` (entry-point lexer/formatter discovery), `unistring.py`,
`regexopt.py`, `scanner.py` — infrastructure, not needed here.

## 8. Usage in rich (verified `rich/syntax.py:24-28, :141-154`)

```python
from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name, guess_lexer_for_filename
from pygments.style import Style as PygmentsStyle
from pygments.styles import get_style_by_name
```

Flow: `Syntax(code, "python")` → `get_lexer_by_name("python")`;
`Syntax.from_path(p)` → `guess_lexer_for_filename(path, code)`; theme string
→ `PygmentsSyntaxTheme(get_style_by_name(theme))`, unknown names fall back to
`"default"` (`:148-150`). Rich then converts each `(ttype, word)` pair via
`get_style_for_token` into its own `Style` objects — pygments' formatters are
NEVER involved in terminal rendering (only `HtmlFormatter` matters for
`Console.export_html` code blocks — unverified exact wiring, labeled
unverified).

## 9. How pygments makes our app significantly better than Termux's proot-distro

Honest scope — two tracks, both host-side unless a future feature says otherwise:

**Track A — today (free, via rich).** Every `Syntax(...)` block in our
dev-script output, every fenced code block in `rich.Markdown` build reports,
and every `traceback.install()` frame is pygments-highlighted across 602
languages. Termux's proot-distro output is unhighlighted shell text. Cost: zero
— pygments ships as rich's hard dep (`pygments>=2.13.0,<3.0.0`; ceiling
`pygments<3` in the D3 bump group).

**Track B — future feature: syntax-highlighted file previews (M4 option).**
A "view guest file" screen (e.g. preview `/etc/apt/sources.list` or a build
log) could highlight server-side-of-the-UI: run pygments in the short-lived
helper (host scripts now; on-device Python later) and map its token stream to
`ft.TextSpan`s. The Android-shipping question is REAL and must be decided in
M4 plan mode: pygments is pure-Python (no native code) so it mechanically
passes the Android compile gate, but it is LARGE (602 lexer modules ≈ MBs of
APK weight against the ~30 MB rootfs budget discussion) — the honest options
are (a) ship it whole, (b) strip to ~10 needed lexers via `[tool.flet.cleanup]`
globs (fragile — lexer autoload uses dynamic imports), or (c) highlight on the
host/CI side only and ship pre-rendered spans. Termux has no such feature;
even option (c) (highlighted build-log artifacts) is a differentiator.

Recommendation: Track A now (already working); Track B as an M4 plan-mode
proposal with an APK-size measurement (`uv pip compile --python-platform
aarch64-linux-android` + trial `flet build apk` size delta) before committing.

## 10. Verification refs

- `pygments/__init__.py:35/:52/:77`; `pygments/lexer.py` + `formatter.py`
  (`Formatter.__init__(**options)`); `pygments/token.py`; `pygments/style.py`
  (`STYLE_MAP` at `:18`); `pygments/styles/__init__.py`; `pygments/filter.py`.
- `pygments-2.21.0.dist-info/METADATA` (BSD-2-Clause, no hard deps).
- Live counts: 602 lexers, 18 formatter names, 51 style names; `monokai`
  background `#272822`; `HtmlFormatter` defaults.
- `rich/syntax.py:24-28` (imports), `:62` (terminal-style comment),
  `:123` (`RICH_SYNTAX_THEMES`), `:141-154` (`PygmentsSyntaxTheme`),
  `rich/markdown.py` `CodeBlock` → `Syntax` path.
- Labeled unverified: `format()` return value, custom Lexer/Style authoring
  details, per-filter behaviors, `export_html`↔`HtmlFormatter` wiring.
