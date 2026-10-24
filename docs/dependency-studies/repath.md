# repath — exhaustive API reference (installed 0.9.0)

Verified 2026-10-16 against `.venv/Lib/site-packages/repath.py` (0.9.0, single
file, 296 lines) via full source read + live `inspect.signature`. Context:
`docs/roadmap.md`, `docs/reference/dep-flet-runtime-utils.md`, D-010
(`docs/decisions.md:33-34` — flet stays 1.0.4). Anti-hallucination rule: every
signature below is live-introspected; every behavior claim cites a file:line in
the installed source; anything not read is marked **unverified**.

## 1. Identity

| Fact | Value (verified) |
|---|---|
| Version | **0.9.0** (`repath-0.9.0.dist-info/METADATA` `Name:`/`Version:`). Note: the module itself carries NO `__version__` attr (verified: `hasattr(repath,'__version__')` → `False`) |
| License | **MIT** (METADATA `License:`) |
| Summary | "Generate regular expressions form ExpressJS path patterns" —sic, typo in the original (METADATA) |
| Requires | `six (>=1.9.0)` (METADATA `Requires-Dist`, line 20) — its only dependency, used for `six.string_types` / `six.text_type` and `six.moves.urllib.parse.quote` |
| Requires-Python | none declared (no `Requires-Python` in METADATA — verified absent) |
| Size | **8,205 bytes, 296 lines, one file** (`repath.py`) — the smallest non-trivial dep in the tree |
| Pure-Python | Yes — `import re` + `import six` only; no extensions, no data files |
| flet's floor | `Requires-Dist: repath>=0.9.0` with NO environment marker (`flet-1.0.4.dist-info/METADATA:16`) — unlike oauthlib/httpx, flet demands repath on every platform including Emscripten |
| What it is | ExpressJS-style route-template → regex compiler. `/:userId/books/:id?` in, `^/(?P<userId>[^/]+?)/books(?:/...)` out. Port of the JS `path-to-regexp` idiom to Python |

## 2. Complete API — every public function (live signatures)

Module constants first (`repath.py:1-61`, verified read): `REGEXP_TYPE =
type(re.compile('')) (:6)` (used by `pattern()` to pass compiled regexes
through); `PATH_REGEXP (:21)` — the master tokenizer (verbose regex with named
groups `escaped, prefix, name, capture, group, suffix, asterisk;` the comment
table at `:9-19` documents the match shapes); `PATTERNS (:57)` — three segment
templates `REPEAT='(?:{prefix}{capture})*'`, `OPTIONAL='(?:{prefix}({name}{capture}))?'`,
`REQUIRED='{prefix}({name}{capture})'`.

| Function | Live signature | Source | Role |
|---|---|---|---|
| `escape_string` | `(string)` | `:64` | escapes URL regex specials (`([.+*?=^!:${}()[\]\|])`) in literal segments |
| `escape_group` | `(group)` | `:72` | escapes `([=!:$()])` inside capture groups |
| `parse` | `(string)` | `:76` | tokenizes an Express-style path into a `str | dict` token list (dicts carry `name, prefix, delimiter, optional, repeat, pattern`) |
| `tokens_to_template` | `(tokens)` | `:134` | returns a `template_function(obj)` closure that renders a path from a params dict (raises `KeyError`/`TypeError`/`ValueError` on missing/non-repeat/empty/mismatched values; URL-quotes via `urllib.quote`) |
| `tokens_to_pattern` | `(tokens, end=True, strict=False)` | `:197` | renders the token list into a `^...$` regex string; named tokens become `(?P<name>...)` groups when the name contains `[a-zA-Z]`; non-strict appends `(?:/(?=$))?` trailing-slash tolerance |
| `compile` | `(path, flags=0, **options)` | `:239` | `re.compile(pattern(path, **options), flags)` — note the upstream docstring typos ("comiled regular expresion", verified `:241`) |
| `match` | `(path, string, flags=0, **options)` | `:252` | `compile(path, flags=0, **options).match(string)` — returns `re.Match` or `None`; note it hardcodes `flags=0`, ignoring its own `flags` arg (verified `:265`; latent upstream quirk, harmless because no flet caller passes flags) |
| `pattern` | `(path, **options)` | `:266` | the dispatcher: compiled-regex input → `.pattern` passthrough; `list` input → `(?:a|b|...)` alternation; `str` → `tokens_to_pattern(parse(path))`. `options` are `end` (default `True`) and `strict` (default `False`) |
| `template` | `(path)` | `:288` | `tokens_to_template(parse(path))` — compile once, render many |

Explicit non-existence (owner brief asked about these; verified):
`hasattr(repath,'Match')` → `False`, `hasattr(repath,'MatchResult')` → `False`,
`repath.__all__` → `None`. There are no `Match`/`MatchResult` classes in 0.9.0 —
matching returns stdlib `re.Match` objects. The "compile flags" surface is just
the `flags` int forwarded to `re.compile` (default `0`) plus the `end`/`strict`
options on `pattern()`.

Template syntax supported (from `PATH_REGEXP` + `parse`, verified read):
`:name` params, `:name(regex)` custom captures, `(group)` anonymous groups, `*`
wildcards, `?`/`+`/`*` suffixes (optional/repeat), `prefix` of `/` or `.`,
`\`-escapes. `tokens_to_pattern` details worth knowing: numeric auto-names get no
`(?P<...>)` group (only names matching `[a-zA-Z]` do, `:215`); `repeat` wraps the
capture in the `REPEAT` template (`:220`); optional vs required picks the
`OPTIONAL`/`REQUIRED` segment template (`:222-224`).

## 3. How flet's Router/TemplateRoute consume it (quote sites)

Exactly two consumer files in flet (verified `grep -rln "repath" flet/`):

**`flet/components/router.py:16`** — `import repath` (module top-level, so the
*new* declarative `Router()` API loads repath at import; the import itself is
`import flet`-deferred — eager test shows `repath` absent from `sys.modules`
after `import flet` because `flet/__init__.py` re-exports `Router` lazily). Five
call sites, all `repath.pattern(...)` + stdlib `re.match` (verified lines):

```text
router.py:191:        pattern = repath.pattern(full_path)              # index-route exact match
router.py:228:        prefix_pattern = repath.pattern(full_path, end=False)   # child-prefix match
router.py:265:            prefix_pattern = repath.pattern(full_path, end=False)  # nested prefix re-check
router.py:287:            exact_pattern = repath.pattern(full_path)    # component exact match
router.py:302:    leaf_pattern = repath.pattern(full_path)             # leaf-route exact match
```

Context (verified `sed` reads): `_try_match(route, pathname, parent_path)`
compiles per attempt, then `m.groupdict()` feeds `_RouteMatch(route, params,
full_path, resolved_path)` — i.e. repath named groups ARE the route params
(`use_route_params()` returns them). `end=False` at `:228/:265` is the prefix
form that lets parent routes consume only their segment.

**`flet/controls/template_route.py`** — the legacy matcher, in full (verified
`cat`, 53 lines):

```python
import re
import repath
...
    def match(self, route_template: str) -> bool:
        ...
        pattern = repath.pattern(route_template)
        match = re.match(pattern, self.route)
```

`TemplateRoute.match()` compiles the template with `repath.pattern()`,
`re.match`es the concrete route, stores `match.groupdict()` as attributes, and
clears stale params (`None`) before each attempt. Both consumers use ONLY
`repath.pattern()` — `compile`, `match`, `template`, `parse` are never called by
flet (verified: no other `repath.` attribute access in `flet/`).

Also re-exported for app code: `flet/__init__.py` lazily exposes
`Router, Route, LocationInfo, is_route_active, use_route_location,
use_route_params (via use_route_*), use_route_outlet, ...` (`:39-45`,
`"Route": "flet.components.router"` at `:1642`, `"Router"` at `:1645`,
`"TemplateRoute": "flet.controls.template_route"` at `:1721`); the router is
imported by `flet/__init__.py` (`grep -l` hit) so user code reaches repath
indirectly the moment it builds routes.

## 4. When our app needs it (routing) vs not

- **Needed the moment we declare routes.** M3 scaffolds screens (distro list,
  install flow, container actions, settings — roadmap §M3). If navigation uses
  `Router(routes=[...])` or `TemplateRoute` matching (the house pattern in
  Sherlock/DDGS/CollabShell studies), every navigation event compiles through
  `repath.pattern()`. There is no alternative matcher inside flet — removing
  repath breaks `flet.components.router` and `flet.controls.template_route` at
  import (`ModuleNotFoundError` on `import repath`, lines `router.py:16`,
  `template_route.py:3`), not lazily.
- **Not needed before that.** A single-screen M0 spike or a手-rolled
  `page.go()` string switch never imports the router modules, so repath sits
  idle (~8 KB — pruning it saves nothing worth the resolver fight; and flet's
  unconditional `repath>=0.9.0` floor means pip/uv installs it regardless — a
  cleanup glob would be the only removal path, gaining 8 KB while risking every
  future route).
- **Verdict: keep, unconditionally.** Smallest keep-cost in the tree, zero config,
  load-bearing for the M3 navigation the roadmap already commits to. Never add
  to `cleanup.package_files`; the Sherlock "only `oauthlib/**`" guidance
  (§oauthlib study §4) already implies exactly this.

## 5. How repath makes our app significantly better than Termux's proot-distro

Termux's proot-distro is a shell CLI: navigation is `ls`/`cd` and script names —
there is no in-app routing concept at all. repath (via flet's Router) buys our
app the thing that turns a script collection into a real mobile app:

- **Deep-linkable distro screens.** `/distro/alpine/terminal`,
  `/distro/:name/install`, `/settings/storage` — parameterized routes with
  `use_route_params()` mean one screen component serves every container, instead
  of N hand-wired views. Termux users memorize flags; our users get back-button,
  URL, and state-restore semantics for free from the `Router()` component.
- **Guard rails for destructive flows.** Prefix matching (`end=False`, `:228`)
  lets a parent `/distro/:name` layout wrap children (terminal, logs, remove
  confirmation) with shared guards — e.g. refuse navigation while an install is
  running — a structure Bash CLIs cannot express.
- **Honest limits:** repath is 8 KB of regex compilation. It contributes zero
  runtime features beyond matching; animated transitions, scrollback, and session
  lifetime all live in flet proper. Its value is architectural (declarative
  navigation exists at all), not computational.

## 6. Verification refs

- Source: `.venv/Lib/site-packages/repath.py` (296 lines — read in full);
  METADATA `repath-0.9.0.dist-info` (`Requires-Dist: six (>=1.9.0)`, line 20);
  flet floor `flet-1.0.4.dist-info/METADATA:16` (no marker).
- Signatures: live `inspect.signature` on all nine functions; `Match`/
  `MatchResult`/`__all__` absence live-checked; `match()` flags-quirk at `:265`.
- flet sites: `grep -rln "repath" flet/` → exactly `components/router.py:16`
  (+5 `repath.pattern` lines `:191/:228/:265/:287/:302`) and
  `controls/template_route.py:3` (+1 at `:44`); `flet/__init__.py`
  re-exports (`:39-45, :1642-1812`); eager-import test (`import flet` →
  `repath`/`six`/`oauthlib` all absent from `sys.modules`).
- Repo-zero-usage: `grep -rn "repath\|oauthlib" src/ tests/` → no hits.
- **Unverified**: none — the module is 296 lines and was read end-to-end.
