# six — audit

**Verdict:** PERFECT
**Confidence:** high
**Scope:** `.venv/Lib/site-packages/six.py:1-1003` · `.venv/Lib/site-packages/six-1.17.0.dist-info/METADATA` · `.venv/Lib/site-packages/repath.py:1-296` · `.venv/Lib/site-packages/repath-0.9.0.dist-info/METADATA:20` · `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:16` · `.venv/Lib/site-packages/flet/__init__.py:9,39-49,622,1280,1645,1721,1821-1834` · `.venv/Lib/site-packages/flet/components/router.py:16` · `.venv/Lib/site-packages/flet/controls/template_route.py:3` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:1893-1895,2605-2606,2770-2790` · `.venv/Lib/site-packages/cookiecutter/{environment.py:30-43,extensions.py:12,generate.py:351,utils.py:102-106}` · `.venv/Lib/site-packages/arrow/arrow.py:33-34` · `.venv/Lib/site-packages/dateutil/{parser/_parser.py:42-43,tz/tz.py:19-21,tz/win.py:13-14,tz/_common.py:1,tz/_factories.py:5,relativedelta.py:8,rrule.py:18,20,parser/isoparser.py:17}` · `pyproject.toml:8-15,52,62-63` · `uv.lock:200,659-664,721-726,786-790` · `src/screens/views.py:26-42,565-572,600-606` · `src/` (all 32 files) · `tests/test_imports_vs_deps.py:35-43,46-59,62-68` · `build_flet_proot_wheel.py:10-21` · `.github/workflows/app.yml:49,149,159,203,213` · `docs/dependency-studies/six.md` (study, prior knowledge) · `docs/swarm/dependency-tree/uv-tree-inverted.txt:88-93` · `docs/decisions.md:12-13` (D-003) · **Date:** 2026-10-22

## What it does / how the app uses it

six 1.17.0 is the Python-2/3 compatibility shim: **one file, 1003 lines, 34,703 bytes**, stdlib-only
(`six.py:23,25-29` — `from __future__ import absolute_import`; `functools, itertools, operator, sys,
types`), zero dependencies of its own (`six-1.17.0.dist-info/METADATA` has **no** `Requires-Dist`;
`grep -c "Requires-Dist"` → `0`). Version at `six.py:32` (`__version__ = "1.17.0"`), MIT per METADATA
`License:`.

**The app never imports six.** Zero hits for `import six`, `from six`, `import repath`, `from repath`,
`six.` or `repath.` across `src/`, `tests/`, `build_flet_proot_wheel.py` and `pyproject.toml`. The only
`six` token in `src/` is the **licence-list entry** at `src/screens/views.py:41` (`"six"` inside
`_PY_DISTS`, `src/screens/views.py:26-42`), rendered by `_py_entries()`
(`src/screens/views.py:600-606`) as `six 1.17.0 (MIT)` — verified live from
`importlib.metadata.metadata("six")` → `version=1.17.0`, `license='MIT'`. Correct disclosure of a
dist that really does ship in the APK.

**six stays in the runtime set purely as `repath`'s import.** The chain is one-directional and
declared:

```text
$ grep -n "Requires-Dist" .venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA
16:Requires-Dist: repath>=0.9.0
$ grep -n "Requires-Dist" .venv/Lib/site-packages/repath-0.9.0.dist-info/METADATA
20:Requires-Dist: six (>=1.9.0)
```

`flet-1.0.4.dist-info/METADATA:16` carries **no environment marker** (contrast `:14-15`, where
oauthlib/httpx are `platform_system != "Emscripten"`), so repath is a hard install-time requirement of
flet on every platform, and six is repath's only requirement. `repath.py:3-4` hard-imports it at
module top:

```python
3: import six
4: from six.moves.urllib import parse as urllib
```

flet reaches repath through exactly two modules, both top-level imports:
`flet/components/router.py:16` (`import repath`) and `flet/controls/template_route.py:3`
(`import repath`). Both are **lazily** re-exported by flet (`flet/__init__.py:9` `if TYPE_CHECKING:`;
`:39-49` and `:622` are inside that block; the live table is `_LAZY = {` at `flet/__init__.py:1280`
with `"Router": "flet.components.router"` at `:1645` and `"TemplateRoute":
"flet.controls.template_route"` at `:1721`, resolved by `__getattr__` at `flet/__init__.py:1821-1834`).

Runtime proof of the laziness and of six's non-participation in app startup:

```text
$ .venv/Scripts/python.exe -c "import flet, sys; print('six' in sys.modules, 'repath' in sys.modules)"
False False
$ .venv/Scripts/python.exe -c "import flet as ft, sys; _=ft.Router; print('six' in sys.modules, 'repath' in sys.modules)"
True True
```

Full app import-graph probe (`src/` on `sys.path`, all 32 modules imported):

```text
total .py files: 32
modules attempted: 32
failures: []
six in sys.modules: False
repath in sys.modules: False
dateutil in sys.modules: False
```

**The wheel builder does not use six either.** `build_flet_proot_wheel.py:10-21` imports stdlib only
(`argparse, base64, hashlib, io, re, struct, sys, tarfile, urllib.error, urllib.request, zipfile,
pathlib`); `grep -c six` → `0`, `grep -c repath` → `0`. Notably it uses stdlib `urllib.request` /
`urllib.error` directly (`build_flet_proot_wheel.py:18-19`) rather than `six.moves.urllib.parse`, so
six is not even a convenience there.

**The answer to "prune with repath or must it stay": it must stay**, for two independent reasons
proved below — the app-runtime chain and the CI build-host chain.

## Findings

### F1 · P3 · six must stay: it is load-bearing on the app-runtime chain, and pruning it turns a future routing import into a device crash
- **Where:** `.venv/Lib/site-packages/flet-1.0.4.dist-info/METADATA:16` · `.venv/Lib/site-packages/repath-0.9.0.dist-info/METADATA:20` · `.venv/Lib/site-packages/repath.py:3-4` · `.venv/Lib/site-packages/flet/components/router.py:16` · `.venv/Lib/site-packages/flet/controls/template_route.py:3` · `.venv/Lib/site-packages/flet/__init__.py:1645,1721,1821-1834` · `pyproject.toml:62-63` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2770-2790`
- **What:** `six` is not an optional extra of the runtime set — it is the transitive leaf of an
  *unconditional* flet requirement (`flet-1.0.4.dist-info/METADATA:16` has no marker, so pip installs
  repath → six on every platform including Emscripten). Because `repath.py:3` is a top-level hard
  import, removing six makes `import repath` raise, which makes both flet routing modules raise at
  *their* import. The current cleanup glob (`[tool.flet.cleanup].package_files = ["oauthlib/**"]`,
  `pyproject.toml:63`) correctly excludes both `repath/**` and `six/**`; flet-cli forwards each glob to
  serious_python as `--cleanup-package-files` (`build_base.py:2770-2783`), which deletes files from the
  **packaged** site-packages only.
- **Evidence:** with `six` blocked by a `sys.meta_path` finder:
  ```text
  repath                           -> ModuleNotFoundError: No module named 'six'
  flet.components.router           -> ModuleNotFoundError: No module named 'six'
  flet.controls.template_route     -> ModuleNotFoundError: No module named 'six'
  flet (plain import)              -> OK 1.0.4
  ft.Router                        -> ModuleNotFoundError: No module named 'six'
  ```
  Note the error names **six**, not repath — six is the actual missing leaf.
  Additionally, `flet build` resolves the closure at packaging time: flet-cli passes
  `pyproject.toml [project].dependencies` to serious_python as pip requirements
  (`build_base.py:2605-2606`), so repath and six are installed into the APK's site-packages as
  transitive requirements of `flet`. You cannot keep them out of the APK without violating flet's own
  declared dependency.
- **Fix / opportunity:** none — keep six exactly as it is. Concretely: **never** add `six/**` (or
  `repath/**`) to `[tool.flet.cleanup].package_files`; keep both out of `pyproject.toml:8-15`
  (adding either would make `tests/test_imports_vs_deps.py:46-59` treat it as a direct app dependency,
  and they are transitive).
- **Risk if ignored:** a "trim the APK" pass that adds `six/**` would ship an app that *appears* fine
  (six is never imported — the probe above proves `six` is absent from `sys.modules` after all 32 app
  modules load) until the first `ft.Router` or `ft.TemplateRoute` access, which then dies with
  `ModuleNotFoundError: No module named 'six'` **on device**, with an error that names a package the
  APK still contains in spirit but not in fact. The upside is 34,703 bytes against a Flutter APK —
  negligible; the downside is a crash class that only reproduces after a feature lands.

### F2 · P3 · six is ALSO load-bearing on the CI build host, through a chain no report has identified yet (flet-cli → cookiecutter → arrow → python-dateutil → six)
- **Where:** `.github/workflows/app.yml:49,149,159,203,213` · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:1893-1895` · `.venv/Lib/site-packages/cookiecutter/generate.py:351` · `.venv/Lib/site-packages/cookiecutter/utils.py:102-106` · `.venv/Lib/site-packages/cookiecutter/environment.py:30-43` · `.venv/Lib/site-packages/cookiecutter/extensions.py:12` · `.venv/Lib/site-packages/arrow/arrow.py:33-34` · `.venv/Lib/site-packages/dateutil/tz/tz.py:19` · `uv.lock:659-664`
- **What:** the **dev** side of the tree carries a second, independent reverse dependency on six that
  `docs/dependency-studies/six.md` §2 dismissed as "not in our dependency closure". It *is* in the
  lock (`uv.lock:659-664` — `python-dateutil 2.9.0.post0`, `dependencies = [{ name = "six" }]`) and it
  is on the **`flet build` critical path**: flet-cli bootstraps the Flutter shell with cookiecutter
  (`build_base.py:1893-1895`), cookiecutter renders the template through a Jinja environment
  (`generate.py:351` → `utils.py:102-106` → `StrictEnvironment`), `StrictEnvironment` eagerly loads
  `cookiecutter.extensions.*` as **default extensions** (`environment.py:30-43`), and
  `cookiecutter/extensions.py:12` does `import arrow` → `arrow/arrow.py:33-34` imports `dateutil` →
  `dateutil/tz/tz.py:19` does `import six`. This path runs on every CI build, because
  `uv sync --frozen --group dev` (workflow lines 149 and 203) installs flet-cli → cookiecutter, and
  `flet build apk` / `flet build aab` (lines 159 and 213) start from a clean checkout where
  flet-cli's template hash has never been computed (`build_base.py:1880-1882`), so the cookiecutter
  bootstrap at `:1882-1895` always executes.
- **Evidence:** with `six` blocked:
  ```text
  create_env_with_context({}) -> UnknownExtension Unable to load extension: No module named 'six'
  ```
  with the full import traceback:
  ```text
  File "...\cookiecutter\extensions.py", line 12, in <module>
      import arrow
  File "...\arrow\__init__.py", line 2, in <module>
  File "...\arrow\api.py", line 12, in <module>
      from arrow.arrow import TZ_EXPR, Arrow
  File "...\arrow\arrow.py", line 33, in <module>
      from dateutil import tz as dateutil_tz
  File "...\dateutil\__init__.py", line 16, in __getattr__
  File "...\dateutil\tz\__init__.py", line 2, in <module>
  File "...\dateutil\tz\tz.py", line 19, in <module>
      import six
  ModuleNotFoundError: No module named 'six'
  ```
  The failure surfaces as `UnknownExtension`, not `ModuleNotFoundError` — `cookiecutter/environment.py:41-43`
  catches the `ImportError` and re-raises it as `UnknownExtension`, which is a much more confusing
  diagnostic than the underlying cause.
- **Fix / opportunity:** none for the code. This is a **corrective finding for the study**: the
  conclusion "six must stay" is right, but the study reached it on the runtime chain alone and
  explicitly claimed the dateutil chain was out of scope ("dateutil is NOT in our dependency closure
  (it arrived as a transitive env extra)"). It is in the closure (`uv.lock:659-664`) and it is on the
  build path. Any future "drop the py2 shim" proposal must clear **both** chains.
- **Risk if ignored:** a lockfile cleanup that drops `python-dateutil`/`arrow`/`cookiecutter` from the
  dev group — or a `uv sync` without `--group dev` in CI — would surface as
  `UnknownExtension: Unable to load extension: No module named 'six'` inside the cookiecutter template
  render, i.e. a confusing build failure that looks like a cookiecutter/Jinja problem, not a missing
  package. Note this chain is **invisible to `[tool.flet.cleanup].package_files`** — that glob only
  edits the packaged app, never the host environment — so the two chains must be reasoned about
  separately.

### F3 · P3 · The study's importer census is wrong on two counts (dateutil closure, and the number of importers)
- **Where:** `docs/dependency-studies/six.md` §2 · `uv.lock:659-664` · `docs/swarm/dependency-tree/uv-tree-inverted.txt:88-93` · `.venv/Lib/site-packages/dateutil/parser/_parser.py:42-43` · `.venv/Lib/site-packages/dateutil/parser/isoparser.py:17` · `.venv/Lib/site-packages/dateutil/relativedelta.py:8` · `.venv/Lib/site-packages/dateutil/rrule.py:18,20` · `.venv/Lib/site-packages/dateutil/tz/_common.py:1` · `.venv/Lib/site-packages/dateutil/tz/_factories.py:5` · `.venv/Lib/site-packages/dateutil/tz/tz.py:19-21` · `.venv/Lib/site-packages/dateutil/tz/win.py:13-14` · `.venv/Lib/site-packages/repath.py:3-4`
- **What:** two claims in the prior study do not survive re-verification:
  1. *"dateutil is NOT in our dependency closure (it arrived as a transitive env extra)"* — **false**.
     `python-dateutil 2.9.0.post0` is pinned in `uv.lock:658-668` with `six` as a declared dependency
     (`uv.lock:663`), reached as `flet-cli → cookiecutter → arrow → python-dateutil` (visible in
     `docs/swarm/dependency-tree/uv-tree-inverted.txt:88-93`, which shows six with **two** parents:
     `python-dateutil` and `repath`). The study's *conclusion* — that the runtime reverse-dependency
     set is exactly `{repath}` — still holds; its *reason* does not.
  2. *"grep -rln "^import six\|^from six" site-packages/ finds ten importers total, but nine are
     dateutil"* — **off by one file and off by four statements**. The actual census is **9 files /
     13 import statements**: 8 dateutil files (listed at `:42-43`, `:17`, `:8`, `:18,20`, `:1`, `:5`,
     `:19-21`, `:13-14`) plus `repath.py:3-4`.
- **Evidence:** `grep -rn "import six\|from six\|six\.moves" .venv/Lib/site-packages/ --include="*.py"`,
  excluding `six.py` itself → exactly the nine files above; `uv.lock` confirms the dateutil edge; the
  inverted tree confirms both parents of six.
- **Fix / opportunity:** none in code. `docs/dependency-studies/six.md` §2 should be corrected to say
  *"dateutil is in the **lock** closure but only on the **dev** chain (flet-cli → cookiecutter → arrow
  → python-dateutil); the **runtime** reverse-dependency set is exactly `{repath}`"*, and the importer
  count corrected to *9 files / 13 statements*. **Not applied here** — this audit is read-only apart
  from this report (BRIEF rule 1).
- **Risk if ignored:** low. But the study is the prior-knowledge base for the synthesis, and its
  "dateutil is out of the closure" sentence is the sentence that made the build-host chain (F2)
  invisible. A synthesis that trusts it would under-constrain any "drop six" proposal.

### F4 · P3 · Zero direct app usage of six is correct, and it is structurally enforced rather than accidental
- **Where:** `src/` (all 32 files) · `tests/test_imports_vs_deps.py:35-43,46-59,62-68` · `pyproject.toml:8-15` · `src/screens/views.py:41,600-606`
- **What:** the app's own dependency guard would fail the build if `src/` ever imported `six` or
  `repath`: `tests/test_imports_vs_deps.py` walks every `src/**/*.py` AST for imports
  (`:35-43`), maps a module to its provider via `importlib.metadata.packages_distributions()`
  (`:62-68`), and asserts every provider is declared in `pyproject.toml [project].dependencies`
  (`:46-59`). Live check: `packages_distributions()` maps `six → ['six']` and `repath → ['repath']`,
  and neither name appears in `pyproject.toml:9-15` — so an `import six` in `src/` would be flagged
  as an undeclared import. The zero-usage property therefore cannot regress silently.
- **Evidence:** the import-graph probe above (32/32 modules, `six`/`repath`/`dateutil` all absent from
  `sys.modules`) plus the live `packages_distributions()` mapping.
- **Fix / opportunity:** none — this is the desired end state. It also means the app has **no** way to
  reach six's API directly without a deliberate `pyproject.toml` change, which is exactly the
  friction a frozen dependency set (D-003, `docs/decisions.md:12-13`) wants.
- **Risk if ignored:** none. Recorded so the synthesis does not re-open "the app should use six for
  something" — there is nothing to use it for (see *Missed capabilities*).

### F5 · P3 · Shipped cost is 34,703 bytes, roughly half of it unreachable py2 code, with no compliant way to trim it
- **Where:** `.venv/Lib/site-packages/six.py:1-1003` (34,703 bytes) · `.venv/Lib/site-packages/six.py:48-53` (py2 alias block) · `.venv/Lib/site-packages/six.py:40-47` (live py3 aliases) · `.venv/Lib/site-packages/six.py:750-759` (`raise_from` py2/py3 split) · `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2770-2790`
- **What:** on Python 3.14 every `if PY2:` branch is dead. The live py3 aliases are one-liners —
  `string_types = str,` (`six.py:41`), `integer_types = int,` (`:42`), `class_types = type,` (`:43`),
  `text_type = str` (`:44`), `binary_type = bytes` (`:45`), `MAXSIZE = sys.maxsize` (`:47`) — while the
  py2 mirror block sits at `:48-53` and the py2 `raise_from` at `:758-759`. Runtime confirmation:
  `six.PY2 is False`, `six.PY3 is True`, `six.PY34 is True`, `six.string_types == (str,)`,
  `six.text_type is str`. Six's contribution to the runtime is **behaviourally zero**: every surface
  repath uses is the identity function on py3.
  - `repath.py:144,204,207` — `isinstance(token, six.string_types)` → `isinstance(token, str)`
  - `repath.py:174,185` — `six.text_type(val)` → `str(val)`
  - `repath.py:181,191` — `urllib.quote(...)` → **the genuine stdlib function**:
    `six.py:356` `MovedAttribute("quote", "urllib", "urllib.parse")` resolves via
    `MovedAttribute._resolve()` (`six.py:164-166`) to `getattr(urllib.parse, "quote")`. Live identity
    check: `six.moves.urllib.parse.quote is urllib.parse.quote` → `True` (same for `quote_plus`,
    `parse_qs`).
  The only way to remove the dead py2 half is to fork or patch upstream, which the no-patching rule
  forbids; and 34,703 bytes is noise next to a Flutter APK. **Ship it whole.**
- **Evidence:** the identity checks above; `stat` on `six.py` → 34,703 bytes / 1,003 lines.
- **Fix / opportunity:** none. Note for the record: `six.moves.urllib.parse` is *not* the stdlib
  module object — it is the lazy proxy `six.Module_six_moves_urllib_parse` (`six.py:340-343`, registered
  at `:378`), whose **attributes** are the genuine stdlib objects. (`six.moves.urllib_parse` — the
  `MovedModule` at `six.py:315` — *is* stdlib `urllib.parse`.) The prior study's phrasing "resolves to
  stdlib `urllib.parse`" is behaviourally right and object-identity imprecise; nothing in repath depends
  on the distinction.
- **Risk if ignored:** none.

## Missed capabilities (dependency audits only)

**There are none, and that is the finding.** six's entire public surface (71 live `dir(six)` names,
matching the study's census exactly) exists to paper over the Python 2/3 split. This project targets
Python 3.14 exclusively (`pyproject.toml:8` `requires-python = ">=3.14"`), so:

| six capability | API location | py3.14 native equivalent | Verdict |
|---|---|---|---|
| `six.string_types` / `text_type` / `binary_type` / `integer_types` | `six.py:41-45` | `str`, `bytes`, `int` | No value; the project never imports six. |
| `six.ensure_str` / `ensure_text` / `ensure_binary` | `six.py:921,944,903` | `str()` / `bytes()` with explicit encoding | Not needed; the app has no str/bytes coercion boundary. |
| `six.moves.urllib.parse.quote` | `six.py:356` | `urllib.parse.quote` | Already available as stdlib — the builder uses stdlib `urllib.request`/`urllib.error` outright (`build_flet_proot_wheel.py:18-19`). |
| `six.with_metaclass` / `add_metaclass` | `six.py:861,885` | native `class X(metaclass=M)` | Not needed. |
| `six.add_move` / `remove_move` | `six.py:515,520` | n/a (py2-only relocation registry) | No value. |
| `six.raise_from` | `six.py:751-756` (live) / `:758-759` (py2 dead branch) | native `raise X from Y` | No value. |

The only "capability" six confers on this repo is **the ability of flet's router to exist** — and the
app does not use that router today (the sibling `repath.md` report establishes this in full: no
`ft.Router`/`ft.TemplateRoute`/`page.render_views` anywhere in `src/`; navigation is three peer tabs
plus one live-session takeover plus modals). **Value: negative if adopted, positive only as insurance
against a future routing adoption (F1). Cost: 34,703 bytes.** Keep it; do not use it.

## Verified-good list

- **The app never imports six** — 32/32 app modules import cleanly with `six`, `repath` and `dateutil`
  all absent from `sys.modules`. Zero grep hits for `import six|from six|import repath|from repath` in
  `src/`, `tests/`, `build_flet_proot_wheel.py`, `pyproject.toml`.
- **The wheel builder does not use six** — `build_flet_proot_wheel.py:10-21` is stdlib-only; it uses
  `urllib.request`/`urllib.error` directly rather than `six.moves.urllib`.
- **six is correctly NOT declared in `pyproject.toml:8-15`** — it is a transitive requirement of
  flet → repath, and `flet build` resolves that closure itself (`flet_cli/commands/build_base.py:2605-2606`).
- **The Licences screen discloses six correctly** — `src/screens/views.py:41` lists it next to `repath`
  (`:40`); `_py_entries()` (`:600-606`) renders `six 1.17.0 (MIT)` from live metadata.
- **`[tool.flet.cleanup].package_files = ["oauthlib/**"]` (`pyproject.toml:63`) correctly excludes
  `six/**` and `repath/**`** — pruning either would set up the F1 crash.
- **The house import guard (`tests/test_imports_vs_deps.py:46-59`) would catch a future `import six`
  in `src/`** — `packages_distributions()` maps `six → ['six']`, `repath → ['repath']`, neither declared.
- **six 1.17.0 is verified installed and frozen** — `six.py:32`; METADATA `Version: 1.17.0`;
  `uv.lock:786-790`; `docs/swarm/dependency-tree/installed.json` (`{"name": "six", "version": "1.17.0"}`).
- **six has no dependencies of its own** — METADATA contains **no** `Requires-Dist` line
  (`grep -c "Requires-Dist"` → `0`); `six.py:23,25-29` imports only stdlib. Nothing in the tree depends
  on six proceeding it; removing six breaks only its importers.
- **The prior study's API line references all re-verified against the installed source**:
  `six.py:32` (version), `:36-38` (PY2/PY3/PY34), `:41-47` (py3 aliases), `:49-53` (py2 alias block),
  `:91` `_LazyDescr`, `:108` `MovedModule`, `:129` `_LazyModule`, `:144` `MovedAttribute`, `:169`
  `_SixMetaPathImporter`, `:242` `_importer`, `:315-317` (urllib `MovedModule` entries), `:336`
  `moves = _MovedItems(...)`, `:340` `Module_six_moves_urllib_parse`, `:345`
  `_urllib_parse_moved_attributes`, `:356` (`MovedAttribute("quote", "urllib", "urllib.parse")`),
  `:515` `add_move`, `:520` `remove_move`, `:718` `reraise`, `:861` `with_metaclass`, `:885`
  `add_metaclass`, `:903` `ensure_binary`, `:921` `ensure_str`, `:944` `ensure_text`, `:963`
  `python_2_unicode_compatible`.
- **The study's two "unverified" items are now resolved.** `raise_from` is defined at `six.py:751-756`
  via `exec_` (the `if sys.version_info[:2] > (3,)` branch at `:750` is **live** on 3.14; the `else`
  branch at `:758-759` is the dead py2 path) — it is a `raise value from from_value` wrapper. The
  `six.moves` importer machinery is `_SixMetaPathImporter` (`six.py:169-241`), installed as `_importer`
  at `:242` and registered into `sys.meta_path` (`:242` onward); `moves` is `_MovedItems` at `:336`.
- **The 71-name public census is exact** — live `dir(six)` yields 71 non-underscore names, matching
  the study's inventory name-for-name.
- **flet's routing modules are the only repath consumers** — `grep -rn "import repath" flet/` →
  `flet/components/router.py:16` and `flet/controls/template_route.py:3`, nothing else; and
  `grep -rn "import six" flet/` → zero hits, so flet never reaches six except through repath.

## Unverified

- **Whether `six.py` physically lands in the shipped APK/AAB.** The mechanism is well supported —
  flet-cli hands `pyproject.toml [project].dependencies` to serious_python as pip requirements
  (`flet_cli/commands/build_base.py:2605-2606`), and pip resolves flet → repath → six — but the actual
  artifact was not produced or inspected in this audit, and serious_python's own default cleanup globs
  (the `--cleanup-packages` path at `build_base.py:2789-2790`) live in the Flutter-side serious_python
  package, which is **not** vendored in this repo and **not** present in `.venv` (`find . -iname
  "*serious_python*"` → no hits). Whether any default glob could also match `six.py` is therefore
  **UNVERIFIED**. The sibling `flet-cli.md` report covers the packaging side.
- **Whether a future flet release could drop the repath requirement.** `flet` is pinned at 1.0.4
  (D-010, `docs/decisions.md:33-34`) and `flet-1.0.4.dist-info/METADATA:16` is unconditional, so the
  question is moot for this audit; but if flet ever removed `Requires-Dist: repath`, six would leave the
  runtime set automatically (the dev-only dateutil chain would remain). No upstream signal was checked.
- **The `docs/roadmap.md` multi-screen plan** cited by the prior study (§5) could not be consulted:
  `docs/roadmap.md`, `docs/roadmap-synthesis.md` and `docs/compliance/*` are **deleted** in this working
  tree (`git status --short` → ` D docs/roadmap.md` etc.), alongside `LICENSES/*`, `src/LICENSES/*`,
  `check_elf_alignment.py` and `generate_third_party_sources.py`. This is the same workspace-state
  artifact already recorded by the sibling `repath.md` report; I did not restore anything. The
  roadmap's M3 routing plan — the study's justification for keeping the pair — is therefore
  **UNVERIFIED** in this tree, though the keep-decision rests on the mechanical F1/F2 evidence, not on
  the roadmap.
- **`src/LICENSES/` and `LICENSES/` are absent in this working tree**, so `src/screens/views.py:628`
  currently renders the literal `"(text missing)"` for every licence text, including the MIT text that
  covers six. Whether that deletion is intentional is **UNVERIFIED** (same workspace artifact as
  above). It does not affect six's attribution row, which is generated from live package metadata
  (`src/screens/views.py:565-572`) and renders correctly.
