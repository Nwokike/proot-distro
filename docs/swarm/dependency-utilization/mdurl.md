# mdurl 0.1.2 — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `.venv/Lib/site-packages/mdurl/{__init__,_encode,_decode,_parse,_format,_url}.py`, `mdurl-0.1.2.dist-info/METADATA`, `markdown_it_py-4.2.0.dist-info/METADATA`, `uv.lock`, `pyproject.toml`, `docs/dependency-studies/mdurl.md`, `docs/swarm/dependency-tree/*`, `src/services/update_service.py`, `src/components/update_dialog.py`, `src/core/shared_services.py`, `src/core/constants.py`, `src/screens/views.py`, `tests/` · **Date:** 2026-10-20

> **Plain statement on mdurl itself: it is dormant.** The app never imports it, it is not in the runtime dependency set, it cannot be imported from `src/` without breaking the repo's own import guard, and there is no URL-parsing/normalization/encoding work in the app that would need it. No action is required on mdurl, and mdurl must **not** be used to "fix" the URL allow-list (see F1: mdurl's parser has the same host-extraction divergence as `urllib.parse`).
> The one real defect found while auditing mdurl's subject area is in the app's own URL surface: `is_allowed_launch_url` computes the host with an RFC-3986 parser but the platform browser parses the launched string with WHATWG rules (F1).

## What it does / how the app uses it

**mdurl** is a pure-Python percent-encoding + legacy-Node-style URL splitter, ported from JS, with the single purpose of serving markdown-it's link pipeline. Public surface (all verified against the installed copy):

- `encode(string, exclude=ENCODE_DEFAULT_CHARS, *, keep_escaped=True)` — `.venv/Lib/site-packages/mdurl/_encode.py:45-47`; defaults at `_encode.py:9-10`; cache helper `_encode.py:17`.
- `decode(string, exclude=DECODE_DEFAULT_CHARS)` — `.venv/Lib/site-packages/mdurl/_decode.py:33`; defaults `_decode.py:7-8`.
- `parse(url, *, slashes_denote_host=False)` — `.venv/Lib/site-packages/mdurl/_parse.py:297-304` (delegates to `MutableURL.parse`, `_parse.py:105`, `:116`).
- `format(url)` — `.venv/Lib/site-packages/mdurl/_format.py:9-27`.
- `URL` — a 8-field `NamedTuple` — `.venv/Lib/site-packages/mdurl/_url.py:6-14` (fields: `protocol, slashes, auth, port, hostname, hash, search, pathname`).
- Exports + `__version__ = "0.1.2"` — `.venv/Lib/site-packages/mdurl/__init__.py:1-18`.

Spot-check of the prior study (live probe, `.venv/Scripts/python.exe`):

```
version: 0.1.2
dir: ['DECODE_COMPONENT_CHARS', 'DECODE_DEFAULT_CHARS', 'ENCODE_COMPONENT_CHARS',
      'ENCODE_DEFAULT_CHARS', 'URL', '_decode', '_encode', '_format', '_parse',
      '_url', 'decode', 'encode', 'format', 'parse']
encode: 'a%20b/c?d=e%20f'      encode component: 'a%20b%2Fc'      decode: 'a b%2Fc'
parsed: URL(protocol='https:', slashes=True, auth='user:pass', port='8080',
            hostname='host.com', hash='#frag', search='?q=1&r=2', pathname='/p/a/t/h')
format: https://user:pass@host.com:8080/p/a/t/h?q=1&r=2#frag
has .host: False
```

`docs/dependency-studies/mdurl.md` is accurate on every point I re-checked; the only nuance it does not spell out is that mdurl is **not** a WHATWG parser: `_parse.py:28-29` states verbatim *"Backslashes are not replaced with slashes, so `http:\\example.org\` is treated like a relative path"* (this is Node's legacy `url.parse`, not the WHATWG URL Standard).

**How the app uses it: it does not.** The only in-tree consumer is `markdown-it-py` (`.venv/Lib/site-packages/markdown_it_py-4.2.0.dist-info/METADATA:23` — `Requires-Dist: mdurl~=0.1`; the sole runtime dep of that package), and `markdown-it-py` is itself only reachable through the dev group. `grep -rn "markdown_it\|import markdown" src/ tests/` returns nothing; `grep -rn "import rich\|from rich" src/` returns nothing. The app renders markdown with Flet's own control (`src/components/update_dialog.py:67-72`, `:88-94` → `ft.Markdown`), whose Python side is a dumb value holder (`.venv/Lib/site-packages/flet/controls/core/markdown.py:940-943`) — parsing happens in the Dart client, so no Python markdown stack, and therefore no mdurl, is involved in rendering the app's release notes.

**mdurl is dev-only — proven, not inferred:**

- `uv.lock:582-592` — the project's **runtime** `dependencies` are `flet`, `flet-ads`, `flet-terminal`, `httpx`, `proot-distro`. No path to mdurl.
- `uv.lock:594-601` — the **dev** group is `flet-cli`, `flet-desktop`, `pytest`, `pytest-timeout`, `ruff`.
- The only edges into mdurl: `flet-cli → rich` (`uv.lock:223-233`), `flet-desktop → rich` (`uv.lock:243-246`), `rich → markdown-it-py` (`uv.lock:747-755`), `markdown-it-py → mdurl` (`uv.lock:344-350`), `mdurl` itself has a `dependencies` block of none (`uv.lock:433-440`). Same shape in `docs/swarm/dependency-tree/uv-tree-inverted.txt:53-59` and `uv-tree.txt:45-46` (the mdurl edge sits inside the `flet-cli v1.0.4 (group: dev)` branch, `uv-tree.txt:23`; `flet-desktop v1.0.4 (group: dev)` is the other parent, `uv-tree.txt:56`).
- `pyproject.toml:9-14` (runtime) vs `pyproject.toml:77-83` (dev) — same split; `docs/decisions.md:12-13` (D-003) freezes the set.
- `tests/test_imports_vs_deps.py:1-6, 46-59` enforces it: any `import mdurl` under `src/` fails the guard (mdurl is neither a local module nor a declared dependency) — so a stray import would break CI rather than ship and crash on device.

**Does the app need URL parsing / normalization / encoding beyond `urllib.parse`? No.**

- Every URL the app owns is a constant: `src/core/constants.py:16-20`.
- The only remote-supplied URLs are two feed fields, and they are gated, not parsed: `src/services/update_service.py:97-98` → `_safe_url` (`:44-47`).
- The only URL *parse* in the whole app is `urlsplit` inside the allow-list: `src/services/update_service.py:28-37`.
- There is no percent-encoding anywhere in `src/` — `grep -rn "quote\|unquote\|urlencode" src/` returns nothing.
- The user-typed Docker image ref is forwarded verbatim to the upstream `proot-distro` package, which owns registry-URL resolution: `src/services/proot_service.py:212-221`; the app never touches the URL.

## Findings

### F1 · P1 · The launch allow-list checks a different host than the browser will visit (RFC-3986 vs WHATWG backslash divergence)

- **Where:** `src/services/update_service.py:26-37` (the check), `src/services/update_service.py:44-47` + `:97-98` (the feed fields it gates), `src/components/update_dialog.py:23-26` (the launch), `src/core/shared_services.py:58-66` (raw string handed to the launcher), `.venv/Lib/site-packages/flet/controls/services/url_launcher.py:72-100` (`launch_url` forwards the string verbatim to the client).
- **What:** `is_allowed_launch_url` derives the host with `urllib.parse.urlsplit`, which treats `\` as an ordinary netloc character. The engine that actually opens the link (Chrome — the same Blink engine the Android system browser uses; verified below on Chrome) parses the same string with WHATWG rules, where `\` is a path/authority separator. The two disagree, so a URL whose *real* host is outside the allow-list passes the check and is launched. Verified with `https://evil.com\@github.com/`:
  - Python side: `urlsplit(...).hostname == 'github.com'` → `is_allowed_launch_url(...) is True`, and `_safe_url(crafted, GITHUB_RELEASES_URL)` returns the crafted URL, **not** the safe default.
  - Browser side (headless Chrome, `new URL(...)`): `host=evil.com`, `href=https://evil.com/@github.com/` → the user is sent to **evil.com**.
- **Evidence:**

  App-level probe (`.venv/Scripts/python.exe`, `sys.path` = `src`):

  ```
  crafted                       : https://evil.com\@github.com/
  is_allowed_launch_url         : True
  _safe_url(crafted, default)    : https://evil.com\@github.com/
    -> default returned?        : False
  ```

  Browser-side probe (`chrome --headless=new --dump-dom` on a local page running `new URL(...)`):

  ```
  https://evil.com\@github.com/   ->   host=evil.com  hostname=evil.com  href=https://evil.com/@github.com/
  https://github.com\@evil.com/   ->   host=github.com  hostname=github.com  href=https://github.com/evil.com/
  https://github.com@evil.com/    ->   host=evil.com  hostname=evil.com
  https://github.com.evil.com/    ->   host=github.com.evil.com
  ```

  Python's view of the same three inputs (`urllib.parse.urlsplit`): `'github.com'`, `'github.com\\evil.com'`, `'evil.com'`.

  **mdurl would not have fixed this.** `mdurl.parse("https://evil.com\\@github.com/")` → `hostname='github.com'`, `auth='evil.com\\'` (probe output) — the same RFC-3986-ish reading as `urlsplit`, and the same divergence from the browser. The reason is documented in the package itself: `.venv/Lib/site-packages/mdurl/_parse.py:28-29`. So "switch the allow-list to mdurl" is **not** a fix, and mdurl is not available at runtime anyway (see above).
- **Fix / opportunity:** align the check with the browser before splitting — one line, stdlib only, no new dependency (D-003 stays intact):

  ```python
  parts = urlsplit(url.replace("\\", "/"))   # WHATWG: "\" is a path separator for http(s)
  ```

  Probe of that change (current vs patched, same battery):

  ```
  current=True  patched=True  'https://github.com/Nwokike/proot-distro/releases/latest'
  current=True  patched=True  'https://raw.githubusercontent.com/Nwokike/proot-distro/main/version.json'
  current=True  patched=True  'https://play.google.com/store/apps/details?id=ng.kiri.prootdistro'
  current=True  patched=False 'https://evil.com\\@github.com/'      <-- hole closed
  current=False patched=True  'https://github.com\\evil.com/'      <-- now matches the browser (host=github.com)
  current=False patched=False 'https://github.com@evil.com/'
  current=False patched=False 'https://github.com.evil.com/'
  current=False patched=False 'http://github.com/x'
  current=True  patched=True  'https://x.github.com/x'
  ```

  Belt-and-braces alternative (also stdlib): reject any URL containing `\`, or require the URL to match a strict `https://<allowed-host>[/...]` regex before parsing. A belt-and-braces variant is preferable because `urlsplit` is not a WHATWG parser in general.
- **Risk if ignored:** the app's stated guarantee — *"Only https links into the project's own domains may launch"* (`src/services/update_service.py:27`) — does not hold. A crafted link in the remote release feed (`github_url` in `version.json`) or in the remote release-notes markdown passes the allow-list and opens an attacker-controlled site in the user's browser, i.e. a phishing primitive delivered by the app's own update dialog. Exploitation requires control of the feed/release notes (the project's own `raw.githubusercontent.com/version.json`, `src/core/constants.py:17`), so this is a bypass of the app's only link control, not a remote-0-click.

### F2 · P2 · The launch allow-list has no test coverage at all

- **Where:** `tests/` — `grep -rn "update_service\|is_allowed_launch_url\|launch_url\|update_dialog" tests/` returns **no matches**; the test modules in the tree are `test_ads.py`, `test_core.py`, `test_flet_api_guard.py`, `test_imports_vs_deps.py`, `test_proot_surfaces.py`, `test_sessions.py`, `test_terminal_wiring.py`, `test_ui_reactive.py`, `test_version_sync.py` (plus `check_flet_api.py` and `conftest.py`).
- **What:** `is_allowed_launch_url` (`src/services/update_service.py:26-37`) is the app's only outbound-URL control and it is completely unguarded. The repo already ships a guard for a comparable invariant (`tests/test_imports_vs_deps.py`), so the pattern exists.
- **Evidence:** the grep above; `src/services/update_service.py` and `src/components/update_dialog.py` are not imported by any test.
- **Fix / opportunity:** add a table-driven unit test for `is_allowed_launch_url` covering at least: the three allowed hosts, `http://` (deny), `https://github.com.evil.com` (deny), `https://github.com@evil.com` (deny), `https://evil.com\@github.com` (deny — the F1 case), `https://github.com.` (deny), `javascript:` (deny), and the empty string. Pure-stdlib, no fixtures, no network.
- **Risk if ignored:** any refactor of the allow-list (or a "make it stricter" / "make it friendlier" edit) can silently re-open the F1 hole, and nothing in CI would notice. The control is one line away from being decorative.

### F3 · P3 · Blocked and failed launches are silent — the user gets no feedback

- **Where:** `src/components/update_dialog.py:23-26` (returns silently when the URL is not allowed), `src/core/shared_services.py:58-66` (returns `False`, logs at `debug` only, when the launcher is missing or raises).
- **What:** tapping a link in the release notes whose host is not allow-listed does nothing visible; a failed `launch_url` (no browser installed, client-side rejection) also does nothing visible. Both paths are silent by construction.
- **Evidence:** `src/components/update_dialog.py:24-25` — `if not is_allowed_launch_url(url): return` (no message); `src/core/shared_services.py:64-66` — `except Exception as exc: logger.debug(...)` then `return False`, and the return value is discarded at `src/components/update_dialog.py:26` (`page.run_task(launch_url, url, page)` ignores the future).
- **Fix / opportunity:** show a `ft.SnackBar` ("That link is not from a project domain") on the deny path and on a failed launch. The dialog already uses `ft.SnackBar` at `src/components/update_dialog.py:161`, so the pattern is established.
- **Risk if ignored:** the app looks broken rather than safe: the user believes a link opened and instead nothing happens, with no way to tell a blocked link from a broken button.

### F4 · P3 · The allow-list ignores the port, so `https://github.com:<any-port>/` is allowed

- **Where:** `src/services/update_service.py:36-37` — the check uses `parts.hostname` only; `parts.port` is never inspected.
- **What:** `https://github.com:8443/` is treated as an allowed "project domain" URL even though it is not a GitHub-operated service on the default port. Not exploitable against GitHub itself (an attacker cannot bind a port on github.com), but it weakens the "our own domains" claim and lets a feed point at an unexpected service.
- **Evidence:** probe output — `is_allowed_launch_url("https://github.com:8443/")` → `True`; the same probe shows `https://github.com.evil.com/` → `False` and `https://x.github.com/x` → `True` (subdomain rule, `src/services/update_service.py:37`).
- **Fix / opportunity:** if the feed ever carries a port, either pin the allowed ports to `{None, 443}` or restrict the rule to the exact hosts (`host == domain` plus an explicit list of the subdomains actually used, e.g. `gist.github.com`). Keep it stdlib.
- **Risk if ignored:** low; the allow-list's intent is "our own domains", and a non-standard port is outside it.

## Missed capabilities (dependency audits only)

**None worth acting on.** mdurl exposes exactly five public names (`__init__.py:1-11`) and the app uses none of them. The two that could matter are considered and rejected:

| Capability | API location | Would it help? | Cost |
|---|---|---|---|
| `encode()` — percent-encodes unsafe chars, incl. `\` → `%5C` | `.venv/Lib/site-packages/mdurl/_encode.py:45-47` | **This is the primitive that neutralizes F1** — probe: `mdurl.encode("https://evil.com\\@github.com/")` → `"https://evil.com%5C@github.com/"`, which the browser resolves to host `github.com`. But it cannot be used: mdurl is dev-only (not in `pyproject.toml:9-14`, blocked by `tests/test_imports_vs_deps.py:46-59`, frozen by `docs/decisions.md:12-13`), and the identical effect is one stdlib call away (`urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=")`) or one stdlib line (`url.replace("\\", "/")`). | Runtime dependency addition (D-003 sign-off) for no gain over stdlib. |
| `parse()` / `format()` — split a URL into 8 fields | `.venv/Lib/site-packages/mdurl/_parse.py:297-304`, `_format.py:9` | **No.** It is the legacy-Node parser, not WHATWG (`_parse.py:28-29`), and it reproduces the F1 divergence verbatim (`hostname='github.com'` for the crafted URL). It also has no `.host`/`.href`/`.origin` (probe: `hasattr(u, "host")` → `False`). The app needs a *host-allow-list decision*, not a URL splitter. | Same D-003 cost, negative value. |
| `decode()` | `.venv/Lib/site-packages/mdurl/_decode.py:33` | No. The app never decodes percent-escapes: no `quote`/`unquote`/`urlencode` appears anywhere in `src/`, and the feed's URL fields are opaque strings that are only gated, never re-assembled. | — |

The genuinely useful observation is the inverse: **mdurl's `encode` is what markdown-it-py uses to neutralize backslashes in hrefs** (`normalizeLink` → `mdurl.encode`), which is why the *markdown-it* pipeline is not vulnerable to F1. The app's renderer is Flet's Dart-side `ft.Markdown`, which is not in this repository, so the app has neither markdown-it-py's normalization nor an equivalent. The fix belongs in `is_allowed_launch_url`, in stdlib.

## Verified-good list

- **The prior study is accurate.** Every API in `docs/dependency-studies/mdurl.md` re-verified against the installed copy: `encode`/`decode`/`parse`/`format`/`URL` at `_encode.py:45`, `_decode.py:33`, `_parse.py:297`, `_format.py:9`, `_url.py:6`; the four charset constants at `_encode.py:9-10`, `_decode.py:7-8`; `URL._fields` = `('protocol','slashes','auth','port','hostname','hash','search','pathname')`; `format(parse(x)) == x` round-trip; no `.host` attribute. No drift from the 2026-10-16 study.
- **mdurl 0.1.2 is installed and is the locked version.** `mdurl.__version__ == "0.1.2"` (`.venv/Lib/site-packages/mdurl/__init__.py:12`); `mdurl-0.1.2.dist-info/METADATA:2-3`; `uv.lock:434-435`; `docs/swarm/dependency-tree/installed.json` (mdurl 0.1.2). MIT (`METADATA:9`).
- **mdurl has no dependencies of its own** — `mdurl-0.1.2.dist-info/METADATA` contains no `Requires-Dist`, and `uv.lock:433-440` has no `dependencies` block. It cannot drag anything into the app.
- **The app correctly does NOT import mdurl** — `grep -rn "mdurl" src/` → no hits; and `tests/test_imports_vs_deps.py:46-59` would fail the build if it did. The dev-only boundary is machine-enforced, not just conventional.
- **The allow-list already defeats the classic host-confusion attacks** (probe output, `is_allowed_launch_url`): `https://github.com.evil.com/` → `False`; `https://github.com@evil.com/` → `False`; `https://user:pass@evil.com/` → `False`; `http://github.com/x` → `False`; `javascript:alert(1)` → `False`; `//github.com/x` → `False`; `https:/github.com/x` → `False`; `https://xn--github-2of.com/x` → `False`; `https://gıthub.com/x` (Unicode dotless ı) → `False`; `https://github.com%2eevil.com/` → `False`; `https://raw.githubusercontent.com.evil.com/` → `False`; `https://play.google.com.evil.com/` → `False`; `https://github.com\x00.evil.com/` → `False`; `https://github.com\n.evil.com/` → `False` (Python strips `\n` and the remainder is a different host). Only the backslash form (F1) leaks.
- **Trailing-dot and case handling fail closed**: `https://github.com./x` → `False`; `HTTPS://GITHUB.COM/x` → `True` (correctly, `urlsplit` lowercases the scheme and `hostname`).
- **The allow-list is applied twice** — at fetch time (`src/services/update_service.py:97-98` → `_safe_url` `:44-47`) and again at tap time (`src/components/update_dialog.py:24`). Defense in depth: a value that bypasses the fetch-time check is still checked before launch.
- **Deny paths fail closed to safe constants**: `github_url` falls back to `GITHUB_RELEASES_URL` (`src/services/update_service.py:97`), `playstore_url` to `None` (`:98`) — and the Play button is only rendered when the URL is non-empty (`src/components/update_dialog.py:129`).
- **Remote content is bounded**: `_safe_text` truncates version/title/notes to 50/500/10000 chars (`src/services/update_service.py:40-41`, used at `:91-95`).
- **Remote markdown cannot auto-open links**: `ft.Markdown.auto_follow_links` defaults to `False` (`.venv/Lib/site-packages/flet/controls/core/markdown.py:963-967`) and the app never sets it, so taps only fire `on_tap_link` (`markdown.py:1031-1036`) → the app's allow-list is the sole gate for the release notes. The bundled offline notes (`src/core/changelog.py`) are local text, not remote.
- **Flet API usage is correct** — `ft.UrlLauncher` is a service mounted once (`src/core/shared_services.py:27`, `:43-49`) and `launch_url(url)` is awaited with the raw string (`.venv/Lib/site-packages/flet/controls/services/url_launcher.py:72-100`); `Page.run_task` requires a coroutine function (`.venv/Lib/site-packages/flet/controls/page.py:929-941`) and `launch_url` is `async def` (`src/core/shared_services.py:58`) → no `TypeError`.
- **Python 3.14-only syntax is intentional and correct**: the un-parenthesized `except TypeError, ValueError:` at `src/services/update_service.py:63` and `src/components/update_dialog.py:33` is PEP 758 (valid from 3.14); `pyproject.toml:8` pins `requires-python = ">=3.14"`, and the file parses under the installed 3.14.7 (`ast.parse` → OK).
- **No URL is ever displayed in a spoofable way**: the launch buttons are labelled "Release page" / "Google Play" (`src/components/update_dialog.py:132`, `:139`); the only URL text in the UI is the native-wheel provenance `source` string (`src/screens/views.py:591`), which comes from the on-device `flet_proot` manifest, not from the network.

## Unverified

- **Whether the Dart-side markdown renderer leaves a literal `\` in a link href.** Flet's `ft.Markdown` parses in the Flutter client (the Dart `markdown` package); that code is not in this repository, so the exact href the *release-notes* path produces for a crafted destination is not proven here. The CommonMark reference implementation available in the venv (markdown-it-py 4.2.0) percent-encodes it — probe: `[x](https://evil.com\\@github.com/)` → `href='https://evil.com%5C@github.com/'` — i.e. CommonMark-based renderers tend to neutralize the trick. F1 does **not** depend on this: the `github_url` / `playstore_url` JSON fields of the feed reach the same check with no markdown involved (proved above).
- **Whether the Android system browser and the Flet client parse the launched URL with WHATWG rules.** The Flet Dart `url_launcher` plugin is not in this repository. The behaviour was verified in headless **Chrome** on this machine (`host=evil.com` for the crafted URL) — the same Blink engine that ships on Android; the Flet client's own handling is not inspectable here.
- **That the built APK actually omits mdurl.** No build was run. The omission is proven indirectly but strongly: no runtime edge exists in `uv.lock:582-592` / `pyproject.toml:9-14`, and `tests/test_imports_vs_deps.py:46-59` blocks the only way `src/` could import it.
- **Whether the feed host itself (`raw.githubusercontent.com`) is considered trusted by the project.** The F1 risk statement assumes the feed is attacker-reachable only by someone who can already write to the repository; the docs do not state a threat model for the update feed.
