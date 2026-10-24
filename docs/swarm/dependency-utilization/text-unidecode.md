# text-unidecode 1.3 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/text-unidecode.md`; `docs/dependency-studies/python-slugify.md`; `docs/dependency-studies/INDEX.md:33,68`; `docs/dependency-studies/{cookiecutter,proot-distro-api}.md` (cross-ref only); `docs/reference/dep-cookiecutter-stack.md:1-19`; `docs/decisions.md:12-13` (D-003); `pyproject.toml:9-15,43-52,77-84`; `uv.lock:174-190,220-233,586-601,671-680,794-801`; `src/**` (import scan over all 27 modules + `src/services/proot_service.py` in full, `src/screens/views.py` in full, `src/app_controller.py:140-200,216-228,320-370`, `src/screens/terminal_view.py:42-49,107-126,233-315`, `src/core/state.py:1-54`, `src/core/storage_paths.py:31-33`); `tests/test_imports_vs_deps.py:1-68`; `tests/test_proot_surfaces.py:23-52,120-156`; `.venv/Lib/site-packages/text_unidecode/__init__.py:1-21`; `.venv/Lib/site-packages/text_unidecode-1.3.dist-info/{METADATA,LICENSE.txt,RECORD}`; `.venv/Lib/site-packages/slugify/{__init__,slugify,_legacy}.py`; `.venv/Lib/site-packages/cookiecutter/{environment,extensions}.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py:37,1047,2566-2576,2605-2609`; `.venv/Lib/site-packages/flet_cli/utils/project_dependencies.py:110-133`; `.venv/Lib/site-packages/flet/utils/slugify.py:1-14`; `.venv/Lib/site-packages/flet/utils/__init__.py:35,75`; `.venv/Lib/site-packages/flet/controls/core/text.py:222-238`; `.venv/Lib/site-packages/proot_distro/names.py:1-62`; `.venv/Lib/site-packages/proot_distro/paths.py:284,552`; `.venv/Lib/site-packages/proot_distro/message.py:116-148,187-207,227-229,242-272`; `.venv/Lib/site-packages/proot_distro/helpers/docker/refs.py:73-88,260-267,362-376`; `.venv/Lib/site-packages/proot_distro/helpers/docker/search.py:105-139,142-147,191-254`; `.venv/Lib/site-packages/proot_distro/commands/{install,rename,remove,reset,backup,restore,kill,run,build,login/__init__}.py` (name-validation call sites); `flet-build-template.zip` @ v1.0.4 (272 entries, read-only, inspected in %TEMP%) · **Date:** 2026-10-22

## What it does / how the app uses it

**It does not — and that is the correct outcome.** `text-unidecode` 1.3 is installed in `.venv` but is a **dev-only, transitive, and entirely dormant** package. It is a ~305 KiB data table that transliterates Unicode to ASCII approximations, exposed as exactly one function:

```
.venv/Lib/site-packages/text_unidecode/__init__.py:6    _replaces = pkgutil.get_data(__name__, 'data.bin').decode('utf8').split('\x00')
.venv/Lib/site-packages/text_unidecode/__init__.py:8    def unidecode(txt):
.venv/Lib/site-packages/text_unidecode/__init__.py:10       for ch in txt:
.venv/Lib/site-packages/text_unidecode/__init__.py:11           codepoint = ord(ch)
.venv/Lib/site-packages/text_unidecode/__init__.py:17           try:
.venv/Lib/site-packages/text_unidecode/__init__.py:18               chars.append(_replaces[codepoint-1])
.venv/Lib/site-packages/text_unidecode/__init__.py:19           except IndexError:
.venv/Lib/site-packages/text_unidecode/__init__.py:20               pass
```

The whole public surface is `unidecode(txt) -> str` (`__init__.py:8`); live introspection of the installed module gives `public names: ['absolute_import', 'os', 'pkgutil', 'unicode_literals', 'unidecode']` — i.e. one function plus the `from __future__`/stdlib imports of `__init__.py:2-4`.

**It is dev-only, through the python-slugify chain, exactly as the sibling study says:**

```
pyproject.toml:77-84  [dependency-groups] dev = [flet-cli, flet-desktop, pytest, pytest-timeout, ruff]
  └─ uv.lock:220-233  flet-cli 1.0.4 → { name = "cookiecutter" }              (uv.lock:226)
       └─ uv.lock:174-190  cookiecutter 2.7.1 → … { name = "python-slugify" } (uv.lock:182)
            └─ uv.lock:671-680  python-slugify 9.1.3 → { name = "text-unidecode" } (uv.lock:675)
                 └─ uv.lock:794-801  text-unidecode 1.3 (no dependencies of its own)
```

Live, against the installed metadata (`importlib.metadata`, `Requires-Dist` walked from the roots in `pyproject.toml:9-15` + `:43-52`):

```
text-unidecode   runtime_closure=False dev_closure=True
python-slugify   runtime_closure=False dev_closure=True
cookiecutter     runtime_closure=False dev_closure=True
jinja2           runtime_closure=False dev_closure=True
unidecode        runtime_closure=False dev_closure=False
anyascii         runtime_closure=False dev_closure=False

who requires text-unidecode (installed):  python-slugify 9.1.3 -> text-unidecode>=1.3
```

**And it is never even imported — not by the app, not by the build.** `text_unidecode` is imported *lazily*, inside `slugify`'s `_transliterate`, and only for non-ASCII input (`.venv/Lib/site-packages/slugify/slugify.py:51-66`; `:53-54` short-circuits pure ASCII, `:55-61` is the `auto` fallback chain, `:63` the explicit-backend import, `:65` the call). The default slug pipeline reaches it at `.venv/Lib/site-packages/slugify/_legacy.py:141`. Its only consumer is cookiecutter's Jinja `slugify` filter (`.venv/Lib/site-packages/cookiecutter/extensions.py:15-16` imports it, `:54-93` defines it, `:93` registers `environment.filters['slugify']`), and that filter is registered by default (`.venv/Lib/site-packages/cookiecutter/environment.py:30-36`, `SlugifyExtension` at `:33`). But the **flet v1.0.4 build template never calls it**: scanning all 272 entries of `flet-build-template.zip` for the string `slugify` → **0 files**. Proof by import-tracking, live:

```
after import slugify          -> text_unidecode in sys.modules: False
after import cookiecutter.ext -> text_unidecode in sys.modules: False
slugify("debian") -> 'debian'  ; text_unidecode in sys.modules after ascii slugify: False
slugify("Übuntu") -> 'ubuntu'  ; text_unidecode in sys.modules after non-ascii slugify: True
```

`import flet` does not pull it in either (`text_unidecode in sys.modules: False`, `slugify in sys.modules: False`); `flet` does not vendor it (`find flet -iname "*unidecode*"` → 0). And no module of the `slugify` package imports `text_unidecode` at import time — the only reference in the whole package is the lazy `import_module` inside `_transliterate` (`grep -rn "^import\|^from" .venv/Lib/site-packages/slugify/*.py` → no `text_unidecode`; `slugify/__init__.py:1-2` pulls only `.special` and `.slugify`).

**Plainly: text-unidecode is a dormant transitive import. It contributes nothing to the app, to the build, or to the release.**

**Does the app need transliteration anywhere? No — in all three places named, and here is why.**

| Surface | Where | Why no transliteration |
|---|---|---|
| Container names | `src/services/proot_service.py:108-114` (`custom_container_name=name`), `:212-223` (`:221` `name or None`), `:348-354` (rename), `:357-363` (backup) | Upstream owns the format: `.venv/Lib/site-packages/proot_distro/names.py:40` `_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*\Z")` — **ASCII-only**, enforced at `names.py:53-62` and by 19 call sites (`commands/install.py:148,202,214,221`; `rename.py:59-60`; `backup.py:458`; `remove.py:131`; `reset.py:48`; `restore.py:220,226`; `kill.py:125`; `run.py:117`; `build.py:185,461`; `login/__init__.py:84`; `paths.py:284,552`; `session.py:303`). A non-ASCII name is *rejected*, with a readable message (`names.py:42-45,60-62` → `message.py:227-229` → `:187-207`), which the app already surfaces (`src/services/proot_service.py:89-94` capture, `:415-423` `friendly_job_error`). |
| Search | `src/services/proot_service.py:263-269` → `src/app_controller.py:216-228` → `src/screens/views.py:132-135` | The query is forwarded **verbatim**: `.venv/Lib/site-packages/proot_distro/helpers/docker/search.py:204` (strip), `:207-216` (UTF-8 validation only), `:142-147` (`urlencode`). Hub's repository grammar is ASCII-lowercase by construction (`.venv/Lib/site-packages/proot_distro/helpers/docker/refs.py:73-76` `_ALNUM = r"[a-z0-9]+"`, `:88` `re.compile(…, re.ASCII)`), so a non-ASCII query can only ever match nothing — transliterating it would silently query for something else. |
| Display of non-ASCII | `src/screens/views.py:137-163` (`:142` description slice, `:151-156` the two `ft.Text` lines) | Upstream already sanitises what comes off the wire: `search.py:124-130` collapses whitespace and runs `quote_path`, which escapes control characters and lone surrogates (`message.py:242-272`). The control takes a plain `str` with no ASCII constraint (`.venv/Lib/site-packages/flet/controls/core/text.py:235` `value: str = ""`). Transliterating *display* text would misrepresent the registry's own description. |

## Findings

### F1 · P3 · Dormant by design — and provably unable to reach the device, so it must stay that way

- **Where:**
  - `src/**` — `grep -rn --include="*.py" -i "unidecode|slugify" . --exclude-dir=.venv --exclude-dir=.git --exclude-dir=docs` → **0 hits**; `grep -rn "unidecode" src/ tests/ -i` → **0**; `grep -rn "transliter\|ascii\|latin" src/ tests/ -i` → **0**.
  - `pyproject.toml:9-15` (runtime deps), `:43-52` (`tool.flet.android.dependencies`), `:77-84` (dev group); `docs/decisions.md:12-13` (D-003: runtime set frozen).
  - Build packaging: `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576` + `:2605-2609`; `.venv/Lib/site-packages/flet_cli/utils/project_dependencies.py:110-133`.
- **What:** the app has no use for it and cannot have one without a D-003 change. `flet build` packages *only* `project.dependencies` + `tool.flet.<platform>.dependencies` — the dev group is never consulted — so `text-unidecode` (and `python-slugify`, `cookiecutter`, `jinja2`) are absent from the APK by construction.
- **Evidence** (live, using flet-cli's own resolver against this repo's `pyproject.toml`):
  ```
  project.dependencies      -> ['flet >=1.0.4', 'flet-ads >=1.0.4', 'flet-terminal >=0.4.0', 'httpx >=0.28.1', 'proot-distro >=5.10.0']
  tool.flet.android.deps    -> ['flet-proot==5.1.107.98']
  build dependency set      -> ['flet >=1.0.4', 'flet-ads >=1.0.4', 'flet-proot==5.1.107.98', 'flet-terminal >=0.4.0', 'httpx >=0.28.1', 'proot-distro >=5.10.0']
    text-unidecode   in build deps: False
    python-slugify   in build deps: False
    cookiecutter     in build deps: False
    jinja2           in build deps: False
  ```
- **Fix / opportunity:** **none for the app — this is the status quo and it is correct.** The actionable part is documentation only: `docs/dependency-studies/text-unidecode.md` must not be read as a licence to import it (see F2). Do **not** add `text-unidecode` to `pyproject.toml:9-15`; it would need D-003 sign-off, a lock bump, and would add ~305 KiB to the APK for a feature the app must not have (F5).
- **Risk if ignored:** an engineer reads the prior study's "Our-project utilization" section and adds `from text_unidecode import unidecode` to `src/` → a **guaranteed `ModuleNotFoundError` at app launch on every Android device**, invisible to the entire host-side test loop (the host venv has the package installed). The repo's own guard catches it (F4's sibling guard, `tests/test_imports_vs_deps.py:46-59`), but only if someone runs the suite.

### F2 · P1 · HALLUCINATION in the prior study: the "M3 container/distro naming pipeline" and "transliterate instead of erroring" describe an app that does not exist

- **Where:**
  - `docs/dependency-studies/text-unidecode.md:36-42` — *"## Our-project utilization (M3 naming, with a size caveat) — Same container/profile naming pipeline as python-slugify — this is its engine. … Keep it as a locked transitive dep, not a direct import — always call it through `slugify(..., backend=...)`."*
  - `docs/dependency-studies/text-unidecode.md:44-47` — *"## Better than Termux's proot-distro? — Same naming-robustness story as slugify (its engine): non-Latin distro/profile names transliterate instead of erroring. Invisible infrastructure, correctly boring."*
  - `docs/dependency-studies/text-unidecode.md:34` — *"So every `|slugify` call on non-ASCII input in template rendering runs through this table."*
  - App side: `grep -rn --include="*.py" -i "unidecode|slugify" . --exclude-dir=.venv --exclude-dir=.git --exclude-dir=docs` → **0 hits** outside `docs/`. Container names are forwarded **verbatim** to upstream (`src/services/proot_service.py:108-114` `custom_container_name=name`; `:221` `name or None`), never slugified and never transliterated.
  - The upstream behaviour the study denies: `proot_distro/names.py:40` + `:53-62`, reached from `commands/install.py:148` → `message.py:227-229` → the app's capture at `src/services/proot_service.py:89-94` → `friendly_job_error` (`:415-423`): *"container name 'My Debian' is not valid. It must begin with a letter or digit and contain only letters, digits, underscores, dots, or hyphens."* The app **errors**, it does not transliterate.
- **What:** the study invents a shipped feature ("M3 naming", "profile names", "non-Latin names transliterate") that the codebase does not contain — the same defect already found and recorded for the parent package in `docs/swarm/dependency-utilization/python-slugify.md:29-48` (F1 there). The text-unidecode study repeats it verbatim and adds two further falsehoods (F3). "Imported-profile names" describe a feature that does not exist (`grep -rn "profile" src/ -i` → **0**; `grep -rn "yaml\|export\|catalog" src/ -i` → **0**).
- **Evidence:**
  ```
  $ grep -rn --include="*.py" -i "unidecode|slugify" . --exclude-dir=.venv --exclude-dir=.git --exclude-dir=docs | wc -l   → 0
  $ grep -rn "unidecode" src/ tests/ -i | wc -l                                                                            → 0
  $ grep -rn "transliter\|ascii" src/ tests/ -i | wc -l                                                                     → 0
  $ grep -rn "profile" src/ -i | wc -l                                                                                      → 0
  $ grep -rn "yaml\|export\|catalog" src/ -i | wc -l                                                                        → 0
  ```
  and the live upstream rule (`proot_distro.names` imports cleanly on this Windows host, unlike `proot_distro.commands.install`):
  ```
  'debian'       is_valid_name=True      'Übuntu'    is_valid_name=False
  'My Debian'    is_valid_name=False     '容器'       is_valid_name=False
  'my_debian'    is_valid_name=True      'Café'      is_valid_name=False
  'my.debian'    is_valid_name=True      ''          is_valid_name=False
  ```
- **Fix / opportunity:** correct `docs/dependency-studies/text-unidecode.md:36-47` to state the truth: text-unidecode is a **dev-only, transitive, never-imported** dependency of `python-slugify`; the app performs **no** slug generation and **no** transliteration; container identifiers are upstream's (`proot_distro.names`), and upstream already refuses illegal names with a readable message. Delete or rewrite the "Better than Termux's proot-distro?" section. The study's closing advice at `:41-42` ("always call it through `slugify(..., backend=...)`") is actively unsafe — `slugify` is **also** dev-only and equally un-importable from `src/` (F1).
- **Risk if ignored:** the same device-only startup crash as F1, arrived at through a *documented* recommendation rather than an accident. **Dedupe note for the synthesis:** this finding is the text-unidecode half of `docs/swarm/dependency-utilization/python-slugify.md:29-48`; the two should be merged into one finding about the *study pair*, not counted twice.

### F3 · P3 · Two hard numbers in the prior study are wrong: the table is ~305 KiB (not "~3 MB"), and unmapped codepoints are *dropped*, not replaced with `?`

- **Where:**
  - `docs/dependency-studies/text-unidecode.md:3-6` — *"data-heavy (~3 MB transliteration table — the reason `slugify._transliterate` skips backend import for pure-ASCII input, `slugify.py:52`)"* and `:39-40` — *"the ~3 MB table ships wherever slugify's non-ASCII path ships"*.
  - `docs/dependency-studies/text-unidecode.md:11-14` — *"unknown/unmappable codepoints become `?`-style fallbacks per the table data (exact fallback char unverified — spot-check with `help()`/REPL for your target scripts)."*
  - Source of the size claim: `.venv/Lib/site-packages/slugify/slugify.py:52` — *"Every backend maps 7-bit ASCII to itself; skip importing one (text-unidecode's table is ~3 MB)."* The study copied the upstream comment instead of measuring the installed artefact.
- **What:** the installed `data.bin` is **311,077 bytes**; the whole package is **312,613 B (305.3 KiB)** and the distribution (package + dist-info) is **325,159 B (317.5 KiB)** — roughly **one tenth** of the stated figure. The "3 MB" number is upstream's own comment and is stale for the version actually installed. Separately, the fallback is not `?`: the table holds 65,535 entries (`__init__.py:6` splits `data.bin` on `\x00`), so every codepoint in the BMP maps to *something* (often a space), and codepoints **above** the BMP are **silently dropped** by the `except IndexError: pass` at `__init__.py:19-20`.
- **Evidence** (live, against the installed package):
  ```
  data.bin bytes: 311077
  package bytes: 312613  = 305.3 KiB
  dist-info bytes: 12546 = 12.3 KiB   total: 325159 = 317.5 KiB
  len(_replaces): 65535
  unidecode(chr(0x1F600)) -> ''      # emoji: DROPPED, not '?'
  unidecode('emoji \U0001F600') -> 'emoji '
  unidecode('a\x00b') -> 'a\x00b'     # NUL preserved (__init__.py:13-15)
  ```
- **Fix / opportunity:** replace "~3 MB" with "~305 KiB installed (311,077-byte `data.bin`)" at `docs/dependency-studies/text-unidecode.md:4` and `:39`; fix the fallback sentence at `:12-14` to state that unmapped codepoints (beyond U+FFFF) are **dropped**, and that in-BMP codepoints map to whatever the table holds (a space is common — `unidecode('容器')` → `'Rong Qi '`). The size correction matters: the study's "measure the APK delta first" caveat is built on a number that is 10× too high, so it overstates the cost of a hypothetical feature by an order of magnitude.
- **Risk if ignored:** a future decision to ship transliteration would be argued against with a 10× inflated cost, and code written against the study's "`?` fallback" assumption would silently *lose* characters rather than see them replaced.

### F4 · P3 · The build-host guard does not name `text_unidecode` — one of two guards would miss it

- **Where:** `tests/test_proot_surfaces.py:133-148` — `test_dev_only_packages_are_not_imported_from_src`, whose `dev_only` set (`:135-145`) is `{chardet, cookiecutter, pytest, ruff, flet_cli, flet_desktop, binaryornot, jinja2, requests}` — **no `slugify`, no `text_unidecode`**. The docstring at `:134` is *"The build-host tree must never reach the app (licensing A4)"*.
- **What:** the *other* guard is the real gate and it does catch it: `tests/test_imports_vs_deps.py:46-59` (`test_imports_all_declared`) requires every import in `src/` to map to a declared runtime dependency, and `tests/test_imports_vs_deps.py:62-67` (`_dist_map`) resolves the providing distribution. Replaying that guard's own logic against the installed metadata:
  ```
  text_unidecode   providers=['text_unidecode']  declared_match=False -> guard_would_flag=True
  slugify          providers=['python_slugify']   declared_match=False -> guard_would_flag=True
  cookiecutter     providers=['cookiecutter']     declared_match=False -> guard_would_flag=True
  ```
  But a targeted "no build-host import" review that reads only the explicit `dev_only` set would call `text_unidecode` safe. The list is incomplete for this package family.
- **Fix / opportunity:** add `"slugify"` and `"text_unidecode"` to the `dev_only` set at `tests/test_proot_surfaces.py:135-145` — one line, no app behaviour change (the report is read-only; this is a recommendation for the owner). The same recommendation is already recorded against the parent package at `docs/swarm/dependency-utilization/python-slugify.md:95-106` (F4 there) — **dedupe**.
- **Risk if ignored:** a dev-only import of `text_unidecode` is caught by one guard but not the other; a reviewer relying on the explicit list alone would sign it off.

### F5 · P3 · The name field has no client-side validation — the capability to reach for is upstream's `is_valid_name`, **not** a transliterator

- **Where:**
  - The field: `src/screens/views.py:330-340` (`hint_text="name (optional)"`, `:339` `on_change=lambda e: set_name(e.control.value)` — no validation), submitted at `src/screens/views.py:100` (`methods.install_distro, image, name.strip()`).
  - The controller: `src/app_controller.py:161-180` (`:164` busy-lock check, `:167` `state.installing = name or image`, `:180` `self.proot.install(image, name, on_line=_on_line)`) — no name check before dispatch.
  - The facade: `src/services/proot_service.py:212-223` (`install`), `:108-114` (`_ns_install`) — the name is passed through verbatim, `:221` maps `""` → `None` so upstream derives the alias.
  - The rename path: `src/screens/views.py:192-208` (`:197` `methods.rename_container, container, field.value or ""`), `src/app_controller.py:332-340` (`:333` `new = new.strip()`, `:334-335` early return on empty) → `src/services/proot_service.py:348-354` → upstream `commands/rename.py:59-60` (`require_valid_name` on both the old and the new name).
  - The capability that exists: `.venv/Lib/site-packages/proot_distro/names.py:48-50` `is_valid_name(name) -> bool`, `:53-62` `require_valid_name(name, kind=...)` with the user-facing `NAME_RULE_HINT` at `:42-45`.
- **What:** the app has *no* name-sanitising job, and it should not acquire one — but it also never uses upstream's *validator*, so the user learns that "My Debian" is illegal only after the consent dialog is dismissed and the install has been dispatched. The correct instrument is upstream's own predicate, surfaced through the one module allowed to import `proot_distro` (`src/services/proot_service.py:1` *"The only module allowed to import proot_distro."*; the rule is enforced by `tests/test_proot_surfaces.py:34-42`). A transliterator is the wrong instrument, for three measured reasons:
  1. **It rewrites names upstream accepts.** `unidecode`/`slugify` output is a strict subset of upstream's rule: `my_debian` → `my-debian`, `my.debian` → `my-debian` — both legal upstream, both rewritten.
  2. **It does not produce a legal name for the cases people would use it for.** `unidecode('容器')` → `'Rong Qi '` and `unidecode('日本語')` → `'Ri Ben Yu '` — **still rejected** by `names.py:40` (the space), even after `.strip()`, because `unidecode` does not remove spaces and does not lowercase. Only the Latin-diacritics case survives (`'Übuntu'` → `'Ubuntu'`, valid).
  3. **It is not reachable on device.** `text-unidecode` is dev-only (F1); `python-slugify` is too, so `slugify(..., backend="text-unidecode")` cannot be called from `src/` at all.
- **Evidence** (live, upstream predicate and installed transliterator side by side):
  ```
  input          upstream_ok unidecode()        slugify()      translit_changes_name
  'debian'       True        'debian'           'debian'       no
  'My Debian'    False       'My Debian'        'my-debian'    n/a
  'my_debian'    True        'my_debian'        'my-debian'    no
  'my.debian'    True        'my.debian'        'my-debian'    no
  '-lead'        False       '-lead'            'lead'         n/a
  'Übuntu'       False       'Ubuntu'           'ubuntu'       n/a
  '容器'           False       'Rong Qi '         'rong-qi'      n/a
  'Café'         False       'Cafe'             'cafe'         n/a
  ''             False       ''                 ''             n/a
  ```
  and the CJK legality check specifically:
  ```
  '容器'  -> unidecode 'Rong Qi '   is_valid_name('Rong Qi ') = False   stripped 'Rong Qi' -> False
  '日本語' -> unidecode 'Ri Ben Yu ' is_valid_name('Ri Ben Yu ') = False stripped 'Ri Ben Yu' -> False
  '한국어' -> unidecode 'hangugeo'  is_valid_name('hangugeo') = True
  'Übuntu' -> unidecode 'Ubuntu'    is_valid_name('Ubuntu') = True
  ```
- **Fix / opportunity:** expose upstream's predicate, not a transliterator: add `is_valid_container_name(name) -> bool` to `src/services/proot_service.py` (delegating to `proot_distro.names.is_valid_name`) and use it in `src/screens/views.py:339` to drive **state**, not imperative widget mutation (D-015) — e.g. a `name_error` field on `src/core/state.py:8-47` rendered next to the field, so the user sees the rule *before* tapping Install. `proot_distro.names` imports cleanly on the Windows host (verified), so this is testable in the existing suite. **Do not** transliterate: upstream's error is already actionable, and a silent rewrite produces a container whose name the user never typed.
- **Risk if ignored:** low but real — a user who types a name with a space or a non-ASCII character waits through the consent dialog and an install dispatch before learning the rule; and the tempting "fix" (slugify it) silently renames their container.

### F6 · P3 · Licence: dual **Artistic-1.0 / GPLv2+** — build-host only, so no shipped obligation, and the repo's records are already correct

- **Where:** `.venv/Lib/site-packages/text_unidecode-1.3.dist-info/METADATA:8` (`License: Artistic License`), `:12-14` (classifiers: `License :: OSI Approved :: Artistic License`, `… GNU General Public License (GPL)`, `… GNU General Public License v2 or later (GPLv2+)`), `:43-49` (*"You can redistribute it and/or modify this port under the terms of either: `Artistic License`, or GPL or GPLv2+"*); `.venv/Lib/site-packages/text_unidecode-1.3.dist-info/LICENSE.txt:1-5` (*"…under the terms of either: * GPL or GPLv2+ …, or * Artistic License - see below"*), the Artistic text at `:8-134`.
  Shipped-set records: `src/screens/views.py:26-42` (`_PY_DISTS` — the Python distributions the app lists) and `:43-51` (`_TEXT_FILES` — the licence texts the app shows); `docs/reference/dep-cookiecutter-stack.md:3` (*"Build-host only; none ship to Android"*) and `:16` (*"python-slugify 9.1.3 + text-unidecode 1.3 — slug filter"*); `docs/dependency-studies/INDEX.md:33,68` (text-unidecode is listed under *"Dev / build host (never ships to APK)"*).
- **What:** the package is dual-licensed — the permissive **Artistic License 1.0 (Perl)** or **GPL/GPLv2+**. Because it never ships, **neither arm creates an obligation for this app**: it is absent from `_PY_DISTS` (`views.py:26-42`), absent from the licence-text list (`views.py:43-51`), and absent from the third-party manifest. The repo's records are therefore already correct; the only thing to know is that *if* transliteration were ever shipped, the **Artistic** arm is the one to rely on (the GPL arm is copyleft and would be a materially different obligation), and an `Artistic.txt` would have to be added to `LICENSES/` and to `_TEXT_FILES`.
- **Evidence:**
  ```
  $ git show HEAD:THIRD-PARTY-SOURCES.md | grep -i -E "text-unidecode|slugify"   → (no output: not a shipped component)
  $ git ls-files | grep -i licenses
  LICENSES/{Apache-2.0,BSD-3-Clause,GPL-2.0,GPL-3.0,MIT,MPL-2.0,PSF-2.0}.txt
  src/LICENSES/{Apache-2.0,BSD-3-Clause,GPL-2.0,GPL-3.0,MIT,MPL-2.0,PSF-2.0}.txt   (no Artistic.txt — correct, it does not ship)
  ```
- **Fix / opportunity:** **none** while the package stays on the build host. If a future change puts transliteration in the runtime set, add `LICENSES/Artistic.txt` and an `("Artistic.txt", "Artistic-1.0")` entry to `_TEXT_FILES` (`src/screens/views.py:43-51`) and a `text-unidecode` row to `_PY_DISTS` (`:26-42`) — and prefer the Artistic arm over the GPL arm explicitly.
- **Risk if ignored:** none today. The risk is only forward-looking: a future "let's transliterate names on device" change that ships the package without adding its licence text to the in-app licence screen would be an incomplete attribution.

## Missed capabilities (dependency audits only)

**None from text-unidecode — and "none" is the correct answer.** The package exposes exactly one function (`unidecode(txt)`, `text_unidecode/__init__.py:8`), it is dev-only (F1), it is never imported even on the build host (F1), and every capability it offers is either redundant with something the repo already ships or actively wrong for this app's identifier rules:

| Capability | API location | Why the app must not use it |
|---|---|---|
| `unidecode(txt)` — the entire surface | `text_unidecode/__init__.py:8-21` | Dev-only; unreachable from `src/` (F1). Its output is not a valid container name for the cases it would be used for (`'Rong Qi '` — F5), and it silently drops non-BMP characters (F3). |
| The `slugify` Jinja filter that drives it | `cookiecutter/extensions.py:54-93`; registered at `cookiecutter/environment.py:33` | Never invoked: 0 of 272 entries of `flet-build-template.zip` mention `slugify`; flet-cli computes `project_name_slug` with its *own* slugifier, `flet.utils.slugify` (`flet_cli/commands/build_base.py:37,1047`; `create.py:11,124`). |
| The `text-unidecode` backend of `slugify(..., backend=…)` | `slugify/slugify.py:25,51-66`; legacy pipeline `slugify/_legacy.py:141` | `python-slugify` is dev-only too — calling through it from `src/` crashes on device (F1). And it rewrites names upstream accepts (F5). |
| The **ASCII fallback** it provides for free | `text_unidecode/__init__.py:6` (65,535-entry table) | The repo already ships an ASCII slugifier **in the runtime set**: `flet.utils.slugify` (`.venv/Lib/site-packages/flet/utils/slugify.py:5-14`; exported at `flet/utils/__init__.py:35,75`; `flet` is a declared runtime dependency, `pyproject.toml:10`). Zero new packages, zero lock churn, zero D-003 sign-off. Behavioural note measured live: `flet.utils.slugify('Übuntu')` → `'ubuntu'`, `'Café'` → `'cafe'`, `'容器'` → `''` (empty), `'my_debian'` → `'my-debian'`, `'my.debian'` → `'mydebian'` (the dot is *dropped*, not hyphenated) — i.e. it mangles names upstream accepts just as python-slugify does, so it is not a container-name normaliser either. |

**The capability that *is* being missed is upstream's, not this package's** (F5): `proot_distro.names.is_valid_name` / `require_valid_name` (`names.py:48-50,53-62`), reachable through the app's own facade (`src/services/proot_service.py`), for inline validation of the name field (`src/screens/views.py:330-340`) — with no transliteration anywhere.

## Verified-good list

- **The app imports neither `text_unidecode` nor `slugify`, and does not hand-roll any transliteration.** `grep -rn --include="*.py" -i "unidecode|slugify" . --exclude-dir=.venv --exclude-dir=.git --exclude-dir=docs` → **0**; `grep -rn "transliter\|ascii\|latin" src/ tests/ -i` → **0**.
- **`text-unidecode` is dev-only by every measure available:** the lock's own split (`uv.lock:586-592` runtime vs `:594-601` dev), the dependency chain (`uv.lock:226` → `:182` → `:675`), the installed metadata (`python-slugify 9.1.3 -> text-unidecode>=1.3`), and a live runtime-closure walk (`text_unidecode? False`).
- **It cannot reach the device**: flet-cli packages only `project.dependencies` + `tool.flet.<platform>.dependencies` (`flet_cli/commands/build_base.py:2566-2576,2605-2609`; `flet_cli/utils/project_dependencies.py:110-133`), and `import flet` does not pull `text_unidecode` in.
- **It is never even imported on the build host**: `text_unidecode` is lazily imported by `slugify`'s `_transliterate` (`slugify/slugify.py:51-66`), whose only caller is the cookiecutter `slugify` filter (`cookiecutter/extensions.py:93`), and the flet v1.0.4 build template never calls it (0/272 entries).
- **Upstream is the single authority for container-name format**, and every entry point enforces it: `proot_distro/names.py:40` + `:53-62`, with 19 call sites (`commands/install.py:148,202,214,221`; `rename.py:59-60`; `backup.py:458`; `remove.py:131`; `reset.py:48`; `restore.py:220,226`; `kill.py:125`; `run.py:117`; `build.py:185,461`; `login/__init__.py:84`; `paths.py:284,552`; `session.py:303`). The app therefore has **no** name-sanitising job of its own — and that is the architecture, not an omission.
- **The empty-name path is correct**: `src/services/proot_service.py:221` maps `""` → `None`, so upstream derives the alias (`commands/install.py:220` → `helpers/docker/refs.py:362-376` `derive_alias`) instead of the app inventing one; `commands/install.py:143-145`'s "container name can't be empty" branch is therefore unreachable.
- **The upstream refusal is user-visible and cheap**: `require_valid_name` (`names.py:60-62`) runs at `commands/install.py:148`, i.e. **before** any network work (`_run_install` is at `:186-189`), and the message travels `message.py:227-229` → `:187-207` → the app's capture at `src/services/proot_service.py:89-94` → `friendly_job_error` (`:415-423`). `msg`'s TTY guard does not swallow it: `message.py:132-138` catches the `io.UnsupportedOperation` raised by `StringIO.fileno()` (a subclass of both `OSError` and `ValueError`) and returns `True`.
- **The search path needs no transliteration, and does not perform one**: the query is forwarded verbatim (`src/services/proot_service.py:263-269` → `helpers/docker/search.py:204,207-216,142-147`), and Hub's repository grammar is ASCII-lowercase by construction (`helpers/docker/refs.py:73-76,88,260-267`), so upstream's `search.py:120-122` already drops anything unnameable.
- **The search-hit prefill is safe today**: `src/screens/views.py:146` (`label.split(":")[0].split("/")[-1]`) duplicates upstream's alias derivation, but Hub names are `[a-z0-9]` only (`refs.py:73-76`), so they contain neither `:` nor `/` and the two agree for every hit the API can return. (The general divergence of that hand-rolled line for a registry-with-a-port reference is already recorded at `docs/swarm/dependency-utilization/python-slugify.md:108-114`, F5 there — **dedupe**, and it does not apply to the Hub-search path.)
- **Display of non-ASCII is safe and correct**: upstream escapes control characters and lone surrogates before the data leaves the module (`search.py:130` → `message.py:242-272`), the app only slices the string (`src/screens/views.py:142`), and `ft.Text.value` is a plain `str` with no ASCII constraint (`.venv/Lib/site-packages/flet/controls/core/text.py:235`).
- **The app's own text I/O is explicitly UTF-8** where it writes bytes: `src/screens/terminal_view.py:107` (`e.data.encode("utf-8", "ignore")`) and `:126` (`command.encode("utf-8")`).
- **Container names never become filesystem paths in app code.** The only join is `containers_dir / name` (`src/services/proot_service.py:200`), and `name` comes from upstream's `paths.installed_container_names()`, which filters by `is_valid_name` (`paths.py:284`) — i.e. ASCII by construction. `src/core/storage_paths.py:31-33` only builds the parent directory.
- **The repo's real guard catches a dev-only import of this package**: `tests/test_imports_vs_deps.py:46-59` + `:62-67`, replayed live → `text_unidecode providers=['text_unidecode'] declared_match=False -> guard_would_flag=True`.
- **The dependency records are already correct**: `docs/reference/dep-cookiecutter-stack.md:3,16`; `docs/dependency-studies/INDEX.md:33,68` (listed under "Dev / build host (never ships to APK)"); `HEAD:THIRD-PARTY-SOURCES.md` lists only shipped Python components — text-unidecode is absent, correctly. `docs/decisions.md:12-13` (D-003) keeps the runtime set frozen.
- **Sibling swarm reports do not conflict**: `docs/swarm/dependency-utilization/python-slugify.md` reaches the same dev-only conclusion for the parent package and already documents the identical study-hallucination pattern.

## Unverified

- **End-to-end runtime of the upstream name rejection on a device.** `proot_distro.commands.install` cannot be imported on this Windows host (`AttributeError: module 'os' has no attribute 'O_DIRECTORY'`), so the install-with-a-bad-name path was verified by **source reading** (`commands/install.py:143-148` → `names.py:60-62` → `message.py:227-229` → the app's capture at `src/services/proot_service.py:89-94`), not executed. `proot_distro.names` itself *does* import cleanly, and the `_NAME_RE` behaviour quoted in F2/F5 was **executed** against it.
- **On-device rendering of non-ASCII `ft.Text` content** was not exercised (no `flet build`, no device). The claim in "Verified-good" is the *contract* — `Text.value: str` (`flet/controls/core/text.py:235`) with no ASCII coercion in the control — not an observed render.
- **The exact APK byte delta** text-unidecode would add was not measured (no `flet build` — D-005 forbids local builds, owner rule). The qualitative argument stands on its own: the package is not in the packaged dependency set at all, and the installed artefact is 317.5 KiB (F3).
- **`docs/roadmap.md`, `THIRD-PARTY-SOURCES.md`, `src/LICENSES/` and 21 other files are deleted in the working tree** (`git status --short` → 24 ` D ` lines, including ` D THIRD-PARTY-SOURCES.md`, ` D src/LICENSES/*.txt` (7), ` D docs/roadmap.md`; `docs/swarm/` is untracked). The `THIRD-PARTY-SOURCES.md` and `LICENSES/` citations in F6 were read from `git show HEAD:…`, not from the working tree; `src/LICENSES/` is currently absent on disk, which means the in-app licence-text tiles at `src/screens/views.py:625-634` render *"(text missing)"* for every entry in the current tree — a pre-existing working-tree condition, **not** a text-unidecode finding and not something this audit attributes to the package.
- **Whether the owner intends to revive the roadmap's M3 "certified catalog"** (the plan line the study mistook for shipped code) is unknown. F2 asserts only that the study's *present-tense* claim is false today, not that the feature is cancelled — the same caveat the arrow and python-slugify audits recorded.
- **The 272-entry build-template scan** was performed against the copy of `flet-build-template.zip` present in `%TEMP%` (fetched by an earlier audit on 2026-10-20, `flet-build-template.zip` @ v1.0.4). Its provenance was not re-verified against flet's release URL in this audit; the flet-cli pin is `flet-cli 1.0.4` (`uv.lock:220-233`).
