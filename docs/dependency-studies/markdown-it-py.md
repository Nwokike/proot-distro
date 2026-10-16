# markdown-it-py 4.2.0 — exhaustive API reference

Verified 2026-10-16 against `.venv/Lib/site-packages/markdown_it`
(`__init__.py`, `main.py`, `token.py`, `renderer.py`, `ruler.py`,
`parser_block.py`, `parser_core.py`, `parser_inline.py`, `presets/`,
`helpers/`, `rules_*/`). Version via `markdown_it.__version__ == "4.2.0"`.
License: MIT (`markdown_it_py-4.2.0.dist-info/licenses/LICENSE`; port note in
`LICENSE.markdown-it` crediting upstream markdown-it © 2014 Vitaly Puzrin,
Alex Kocharin). Sole runtime dep: `mdurl~=0.1` (verified `Requires-Dist`).
Optional extras (all NOT installed — verified absent): `linkify-it-py`
(`linkify` extra), `mdit-py-plugins` (`plugins`/`rtd` extras),
`markdown-it-pyrs`, benchmarking/compare/profiling packages.

Identity: CommonMark + extensions Markdown parser — a Python port of
markdown-it. Pipeline: `MarkdownIt.parse(src)` → `list[Token]` →
`RendererHTML.render(tokens)` → HTML string.

## 1. `MarkdownIt` — constructor (`main.py`)

```python
MarkdownIt(config="commonmark", options_update=None, *, renderer_cls=RendererHTML)
# config: "commonmark" | "default" | "zero" | PresetType dict
```

There are NO `html/linkify/typographer/highlight` keyword args — passing
`MarkdownIt(linkify=True)` raises `TypeError` (verified). Options are set
after construction via `set()`/`configure()`/`enable()`/`disable()`.

Default options (`MarkdownIt().options`, introspected live):

```python
{"breaks": False, "highlight": None, "html": True, "langPrefix": "language-",
 "linkify": False, "maxNesting": 20, "quotes": "\u201c\u201d\u2018\u2019",
 "typographer": False, "xhtmlOut": True}
# "zero" preset differs only in: html=False, xhtmlOut=False.
```

Meaning of each: `html` = allow raw HTML blocks/inline; `linkify` = autolink
bare URLs (needs the linkify core rule enabled AND `linkify-it-py` installed —
NOT installed here, so enabling the rule alone is a no-op, verified);
`typographer` = enable `replacements`+`smartquotes` core rules (quotes,
`(c)`, `--` → en-dash…); `breaks` = single `\n` → `<br>`; `xhtmlOut` = `<br />`
style; `langPrefix` = fenced-code class prefix; `maxNesting` = nesting guard;
`quotes` = smartquote characters; `highlight` = `fn(str, lang, attrs) -> str`
callback for fenced code (default `None` = escape).

## 2. `MarkdownIt` — every public method (verified `dir` + signatures)

```python
parse(src, env=None) -> list[Token]            # block+inline pipeline
parseInline(src, env=None) -> list[Token]      # inline pipeline only
render(src, env=None) -> str                  # parse + RendererHTML
renderInline(src, env=None) -> str            # parseInline + renderInline
# NOTE: there is NO inline_render (verified absent).

enable(names: str|Iterable[str], ignoreInvalid=False) -> MarkdownIt   # enable rule(s)
disable(names: str|Iterable[str], ignoreInvalid=False) -> MarkdownIt
use(plugin: Callable[..., None], *params, **options) -> MarkdownIt   # plugin hook
add_render_rule(name, function, fmt="html") -> None                  # override renderer
reset_rules() -> Generator[None, None, None]  # context manager restoring rules
get_active_rules() -> dict[str, list[str]]
get_all_rules() -> dict[str, list[str]]
normalizeLink(url) -> str       # mdurl-based normalization
normalizeLinkText(link) -> str
validateLink(url) -> bool       # block javascript:/vbscript:/file: etc.
configure(presets, options_update=None) -> MarkdownIt
set(options: OptionsType) -> None   # bulk-set options dict (typographer via set())
```

Correct usage pattern (verified live):

```python
md = MarkdownIt().enable("linkify").enable("replacements").enable("smartquotes")
md.set({"typographer": True, "breaks": True, "html": False})
md.configure("commonmark", {"linkify": True})
```

## 3. Presets (`presets/commonmark.py:13`, `default.py:6`, `zero.py:9` — `make()`)

- `"commonmark"` (default ctor arg): CommonMark-strict options but allows HTML;
  enables only CommonMark rule components.
- `"default"`: everything on — `components: {core:{}, block:{}, inline:{}}`
  (all rules active), `html=True`.
- `"zero"`: blank slate — all rules disabled, `html=False, xhtmlOut=False`;
  enable exactly what you need (`MarkdownIt("zero").enable(["heading",
  "paragraph", ...])`).

## 4. `Token` — every attribute (`token.py`)

```python
Token(type, tag, nesting: -1|0|1, attrs={}, map=None, level=0,
      children=None, content="", markup="", info="", meta={}, block=False,
      hidden=False)
# attrs: type, tag, nesting, attrs(dict), map([start,end] source lines|None),
#   level, children(list[Token]|None — only inline tokens carry children),
#   content, markup (delimiter chars, e.g. "#" or "*"), info (fence language),
#   meta(dict), block(bool), hidden(bool)
# methods: attrGet/attrIndex/attrItems/attrJoin/attrPush/attrSet,
#          as_dict/from_dict/copy
```

Real token stream (verified `md.parse("# Hi\n\npara *em* [x](https://a.com)\n")`):

```text
heading_open  tag=h1  nesting=+1 map=[0,1] markup="#"
inline        nesting=0 map=[0,1] content="Hi"
  └ child text "Hi"
heading_close tag=h1   nesting=-1 markup="#"
paragraph_open tag=p   nesting=+1 map=[2,3]
inline        content="para *em* [x](https://a.com)"
  ├ text "para " · em_open/em_close (markup="*") · text " "
  └ link_open attrs={"href": "https://a.com"} · text "x" · link_close
paragraph_close
```

Key token types: `heading_open/close`, `paragraph_open/close`,
`blockquote_open/close`, `bullet_list_open/close`, `ordered_list_open/close`,
`list_item_open/close`, `fence` (`info`=language, `content`=code),
`code` (indented), `hr`, `table_open/thead/tbody/tr/th/td_open`,
`html_block`, `inline` (container; real text lives in `children`:
`text code_inline em_open/close strong_open/close s_open/close link_open/close
image autolink html_inline softbreak hardbreak entity`).

## 5. Rule trees — complete enumeration (verified `get_all_rules()`)

Default preset (`"default"` / `MarkdownIt().enable-everything`):

- **core:** `normalize block inline linkify replacements smartquotes text_join`
- **block:** `table code fence blockquote hr list reference html_block heading
  lheading paragraph`
- **inline:** `text linkify newline escape backticks strikethrough emphasis link
  image autolink html_inline entity`
- **inline2:** `balance_pairs strikethrough emphasis fragments_join`

Active by default under `"commonmark"` ctor (verified `get_active_rules()`):
core `normalize block inline text_join` (no linkify/replacements/smartquotes);
block `code fence blockquote hr list reference html_block heading lheading
paragraph` (no table); inline `text newline escape backticks emphasis link image
autolink html_inline entity` (no linkify/strikethrough). Rule dirs:
`rules_core/` `rules_block/` `rules_inline/` (one module per rule name).

Plugin system: `md.use(plugin_fn, *params, **options)`; plugins typically call
`md.add_render_rule(name, fn)`, `md.enable/disable(...)`, or push to
`md.core.ruler / md.block.ruler / md.inline.ruler / md.inline.ruler2`
(`Ruler` in `ruler.py` — ordered rule chains). `mdit_py_plugins` (NOT
installed — verified `ImportError`): would add `footnote deflist tasklists
colon_fence tex dollarmath anchors…`.

## 6. Renderer (`renderer.py`)

`RendererHTML` methods (verified `dir`): `render(tokens, options, env)`,
`renderToken(tokens, idx, options, env)`, `renderInline(tokens, options, env)`,
`renderInlineAsText(tokens, options, env)`, `renderAttrs(token)`,
`code_block code_inline fence hardbreak html_block html_inline image
list_item_open softbreak text`. Default rules dispatch `token.type` →
same-named method; `add_render_rule` overrides per type. Helpers
(`helpers/`): `parseLinkDestination/parseLinkLabel/parseLinkTitle` (+
snake_case aliases) — link-target parsing primitives.

## 7. How rich uses markdown-it (verified `rich/markdown.py`)

`Markdown.__init__` builds its own parser, IGNORING user options:

```python
parser = MarkdownIt().enable("strikethrough").enable("table")  # markdown.py
self.parsed = parser.parse(markup)
```

So in rich: tables + strikethrough work; linkify/replacements/smartquotes do
NOT (parser never enables them). Token → rich style mapping (element classes
in `rich/markdown.py`): `heading_open(h1..h6)` → `Heading` (theme styles
`markdown.h1`… + `markdown.h1.border` rule for h1/h2); `paragraph_open` →
`Paragraph` (justified per `Markdown(justify=...)`); `fence`/`code` →
`CodeBlock` → `Syntax(content, info or "text", theme=code_theme)` (this is the
rich→pygments bridge); `blockquote_open` → `BlockQuote` (`markdown.block_quote`
+ left padding); `hr` → `HorizontalRule` (`markdown.hr`); table tokens →
`TableElement` family → `rich Table(box=box.SQUARE)`; list tokens →
`ListElement/ListItem` (`markdown bullet/number/item` styles); `em_open` →
italic, `strong_open` → bold, `s_open` → strike, `code_inline` →
`markdown.code` (+ optional `inline_code_lexer` Syntax); `link_open href` →
`Link` (style `markdown.link` or `markdown.link_url` when text==URL;
`hyperlinks=False` renders literal); `image` → `ImageItem` (alt text +
`!` marker, `markdown.item`); inline `text/entity/text_join` → plain spans.

## 8. How markdown-it-py makes our app significantly better than Termux's proot-distro

Honest two-track assessment (this is the one package in the cluster that COULD
ship to Android):

**Track A — host/CI-side (no shipping question, usable now).** markdown-it-py
arrives free with rich (hard dep `markdown-it-py>=2.2.0`). Uses: render
`docs/*.md` changelogs/release notes to HTML in CI (`tools/` scripts) with the
same `RendererHTML` the docs were validated against; `parse()`-level lint of
our markdown (broken links via `link_open` href walk, missing fence languages
via `fence.info`); `validateLink` reuse for URL gating in scaffolding scripts.

**Track B — in-app markdown rendering (option, NOT a decision).** Facts:
markdown-it-py is pure-Python (only dep `mdurl`, also pure-Python) so it WOULD
run under Flet's CPython-on-Android and survive the `uv pip compile
--python-platform aarch64-linux-android` gate mechanically; it is fast and
small (~hundreds of KB). BUT: it outputs HTML/token streams, not Flet controls —
shipping it means writing and owning a `Token → ft.Markdown`/`ft.TextSpan`
mapper (heading/list/code/table/image elements), testing it against the
`flet build` tree, and carrying it in the APK forever against the owner's
minimal-deps rule (M3/M4 plan-mode decision). Termux's proot-distro has no
in-app rendering at all (it is a CLI plugin), so even Track A alone is parity
plus; Track B would be a genuine differentiator (offline distro READMEs,
in-app help) at a real maintenance cost. Recommendation: Track A now, Track B
as an explicit M4 plan-mode proposal with a line-count estimate for the mapper.

## 9. Verification refs

- `markdown_it/main.py` (`MarkdownIt`, all method sigs introspected live);
  `markdown_it/token.py` (`Token`); `markdown_it/renderer.py` (method list);
  `markdown_it/presets/{commonmark,default,zero}.py` (`make()` at
  `:13/:6/:9`); `markdown_it/helpers/`; `rules_core/ rules_block/ rules_inline/`.
- `mdurl` linkage: `markdown_it` `Requires-Dist: mdurl~=0.1`; linkify needs
  `linkify-it-py` (absent — `Requires-Dist` extra `linkify`).
- `rich/markdown.py` parser line + element classes `:25-:465` + `Markdown`
  at `:513`; `rich/syntax.py:24-28` for the Syntax bridge.
- Live probes: default/zero options dicts, token-stream dump (§4), rule trees
  (§5), `TypeError` on `MarkdownIt(linkify=True)`, no-op linkify without the
  extra, `typographer` inert via `configure(..., {'typographer': True})`
  (verified rendered output unchanged — actual enable path is the
  `replacements`/`smartquotes` rules).
