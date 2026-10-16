# dep-cookiecutter-stack.md — cookiecutter + 18 build-host deps

Verified 2026-10-16 against `.venv/Lib/site-packages` (D3 study). Build-host only; none ship to Android.

## cookiecutter 2.7.1 (BSD) — mechanics that matter
- flet-cli renders the Flutter build template via `cookiecutter(..., no_input=True, overwrite_if_exists=True, extra_context=template_data)`; the template zip is fetched through flet's own cache (`template_cache.py`, stdlib urllib), not cookiecutter's downloader.
- **Unknown top-level context keys are silently ignored** — every `template_data` key must already exist in the template's `cookiecutter.json`; a typo vanishes without error. Nested dicts can gain keys.
- `extra_context` must be **JSON-serializable** (it's dumped for replay); non-str scalars get stringified; StrictUndefined fails closed on missing keys (flet strips `None`s for this reason).
- ``overwrite_if_exists=True`` restores placeholder assets on re-render — that's why icon/splash stamps chain off the template digest.
- Hooks (`pre/post_gen`) execute template code at build time.

## Trust boundary (flag for CI)
`flet-build-template.zip` is cached with **no checksum/signature check** and its hooks run during every build → keep template ref = the flet version pin; never point `--template`/`--template-dir` at untrusted URLs. (cookiecutter's own zip extraction is `extractall` — only trusted template sources, ever.)

## Per-package notes (all pure-Python, all build-only)
binaryornot 0.4.4 (BSD) + chardet 5.2.0 (LGPL — don't vendor) — binary-vs-text probe; arrow 1.4.0 (Apache) + python-dateutil 2.9.0 + tzdata 2026.5 — `{% now %}`; click 8.5.0 (BSD) — cookiecutter's own CLI; jinja2 3.1.6 + markupsafe 3.0.4 (BSD) — renderer + escaping; pyyaml 6.0.3 (MIT) — also flet's `safe_load` for pubspec patching; python-slugify 9.1.3 + text-unidecode 1.3 — slug filter; rich 15.0.0 + markdown-it-py 4.2.0 + mdurl 0.1.2 + pygments 2.21.0 (MIT/BSD) — CLI output; requests 2.34.2 + charset-normalizer 3.5.2 + urllib3 2.8.0 (Apache/MIT) — only used for `flet create` remote template zips (network-facing: keep TLS stack current).

## Bump groups (ceiling pins will block naive bumps)
`jinja2+markupsafe` | `requests+urllib3+charset-normalizer` | `markdown-it-py+mdurl` | `arrow+dateutil+tzdata`. Ceilings: Jinja2<4, click<9, binaryornot<0.5, chardet<6, mdurl~=0.1, pygments<3, urllib3<3.
