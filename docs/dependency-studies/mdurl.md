# mdurl 0.1.2 — exhaustive API reference

Verified 2026-10-16 against `.venv/Lib/site-packages/mdurl`
(`__init__.py`, `_encode.py`, `_decode.py`, `_parse.py`, `_format.py`,
`_url.py`). Version via `mdurl.__version__ == "0.1.2"`.
License: MIT (`METADATA` classifiers include `License :: OSI Approved ::
MIT License`; `Summary: Markdown URL utilities`). Zero runtime dependencies
(no `Requires-Dist` at all — verified). Pure-Python, ~6 tiny modules.

Identity: URL percent-encoding + WHATWG-ish URL splitting, ported from JS
mdurl for markdown-it's link pipeline. It is NOT a general URL library
(no fetching, no joining, no query manipulation) — encode/decode/parse/format
only. Sole consumer in our tree: markdown-it-py (`normalizeLink`,
`normalizeLinkText`, link-href encoding).

## 1. Complete API — five public names (verified `dir(mdurl)`)

```python
encode(string: str, exclude: str = ";/?:@&=+$,-_.!~*'()#",   # _encode.py:45
       *, keep_escaped: bool = True) -> str
decode(string: str, exclude: str = ";/?:@&=+$,#") -> str    # _decode.py:33
parse(url: URL | str, *, slashes_denote_host: bool = False) -> URL  # _parse.py:297
format(url: URL) -> str                                      # _format.py:9 (named format — shadows builtin)
URL  # class, _url.py:6
```

Plus four charset constants:

```python
ENCODE_DEFAULT_CHARS    = ";/?:@&=+$,-_.!~*'()#"  # _encode.py:9
ENCODE_COMPONENT_CHARS  = "-_.!~*'()"             # _encode.py:10
DECODE_DEFAULT_CHARS    = ";/?:@&=+$,#"            # _decode.py:7
DECODE_COMPONENT_CHARS  = ""                       # _decode.py:8
```

## 2. `encode` / `decode` — semantics (verified by live probes)

`encode` percent-encodes every byte outside the unreserved set PLUS every char
in `exclude` left as-is. Default `exclude=ENCODE_DEFAULT_CHARS` keeps
`;/?:@&=+$,-_.!~*'()#` literal — i.e. reserved URL punctuation survives, so
`encode("a b/c?d=e f")` → `"a%20b/c?d=e%20f"` (space encoded, `/ ? =` kept).
`ENCODE_COMPONENT_CHARS="-_.!~*'()"` is the tighter component-level set (use
it when encoding a single query value/path segment where `/ ? & =` must also
be escaped). `keep_escaped=True` (default) leaves existing `%XX` sequences
alone; `False` re-encodes the `%` itself. Cache helper: `get_encode_cache`
(`_encode.py:17`) builds a 256-entry table per `exclude` value.

`decode` reverses `%XX` → char EXCEPT for chars in `exclude` (default
`DECODE_DEFAULT_CHARS`), which stay escaped: `decode("a%20b%2Fc")` →
`"a b%2Fc"` — `%20` decodes (space not excluded) but `%2F` (`/`, excluded)
does NOT. `DECODE_COMPONENT_CHARS=""` = decode everything. Cache helper:
`get_decode_cache` (`_decode.py:13`); worker `repl_func_with_cache` (`:39`).

Round-trip rule: `decode(encode(s)) == s` holds for ordinary strings; it breaks
iff `s` already contains `%XX` AND `keep_escaped=True` (pre-escaped input is
preserved, not double-encoded) — callers normalizing user input should decide
which behavior they want explicitly.

## 3. `URL` object (`_url.py:6` — a `NamedTuple`)

Fields (verified `URL._fields`):

```python
("protocol", "slashes", "auth", "port", "hostname", "hash", "search", "pathname")
```

All eight are plain positional fields (no defaults documented — construct via
`parse`, not by hand). There is NO `.host`, NO `.href`, NO `.origin`, NO
`.username/.password`, NO methods beyond NamedTuple's (`_replace`, `count`,
`index` — `count`/`index` appear in `dir()` from the tuple base). Verified:
`getattr(u, "host")` raises `AttributeError`.

Real parse (verified):

```python
>>> parse("https://user:pass@host.com:8080/p/a/t/h?q=1&r=2#frag")
protocol="https:"  slashes=True  auth="user:pass"  hostname="host.com"
port="8080"  pathname="/p/a/t/h"  search="?q=1&r=2"  hash="#frag"
>>> format(that) == "https://user:pass@host.com:8080/p/a/t/h?q=1&r=2#frag"
```

Internals: `parse` delegates to `url_parse` (`_parse.py:297`); a `MutableURL`
helper class lives at `_parse.py:105` (private — building state only, not part
of the public surface). `slashes_denote_host=False` default mirrors the JS
behavior for protocol-relative inputs.

## 4. How markdown-it-py uses mdurl (the only in-tree consumer)

- `MarkdownIt.normalizeLink(url)` — parses and re-formats to a canonical form
  (encoding unsafe chars in hrefs).
- `MarkdownIt.normalizeLinkText(link)` — same for link display text/URLs.
- `MarkdownIt.validateLink(url)` — scheme allowlist (blocks `javascript:` /
  `vbscript:` / `file:` etc.; pure function, mdurl-independent but adjacent).
- Inline `link`/`image`/`autolink` rules call these when producing
  `link_open.attrs["href"]`.

## 5. How mdurl makes our app significantly better than Termux's proot-distro

Honest scope: mdurl is **transitive plumbing** (markdown-it-py → mdurl), never
a direct app dependency, never shipped to Android on its own. Its contribution
is indirect but real:

- **Correct link handling in Track A tooling** (§8 of markdown-it-py.md): any
  CI script that parses our docs' `link_open` hrefs gets properly
  encoded/normalized URLs for free — no hand-rolled `urllib.parse` quoting
  with its ASCII-default pitfalls.
- **OCI/distro URL hygiene (M3):** if a helper script normalizes custom
  registry refs or tarball URLs, `mdurl.encode(s, ENCODE_COMPONENT_CHARS)`
  is the correct primitive for single-segment encoding (safer default than
  `urllib.parse.quote`'s `/`-preserving default for path segments).
- **No action required:** no bump group owns it alone — it moves with
  `markdown-it-py+mdurl` (D3 bump group); ceiling `mdurl~=0.1` (verified in
  markdown-it-py's `Requires-Dist`).

Termux comparison: Termux's proot-distro does no URL processing at all; mdurl
matters only insofar as our docs/OCI tooling handles URLs without bugs.

## 6. Verification refs

- `mdurl/__init__.py` (five exports + four constants); `mdurl/_encode.py:9-10,
  :17, :45`; `mdurl/_decode.py:7-8, :13, :33, :39`; `mdurl/_parse.py:105, :297`;
  `mdurl/_format.py:9`; `mdurl/_url.py:6`.
- `mdurl-0.1.2.dist-info/METADATA` (name/version/MIT/no Requires-Dist).
- Live probes: `encode("a b/c?d=e f")`, `decode("a%20b%2Fc")`, full-URL
  `parse`/`format` round-trip, `URL._fields`, `AttributeError` on `.host`.
