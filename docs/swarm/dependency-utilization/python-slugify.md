# python-slugify 9.1.3 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/swarm/BRIEF.md`; `docs/dependency-studies/python-slugify.md`; `docs/dependency-studies/{cookiecutter,text-unidecode}.md`; `docs/reference/dep-cookiecutter-stack.md`; `docs/decisions.md` (D-003); `docs/roadmap.md` @ HEAD (deleted in the working tree — cited as `HEAD:docs/roadmap.md`); `pyproject.toml`; `uv.lock`; `src/**` (import scan + `src/services/proot_service.py` in full, `src/app_controller.py` (install/rename/backup), `src/screens/views.py` (install panel, search hits, rename dialog)); `tests/{test_imports_vs_deps,test_proot_surfaces}.py`; `.venv/Lib/site-packages/slugify/{__init__,slugify,_legacy,special,__main__,__version__}.py`; `.venv/Lib/site-packages/cookiecutter/extensions.py`; `.venv/Lib/site-packages/flet/utils/{__init__,slugify}.py`; `.venv/Lib/site-packages/flet_cli/commands/{build_base,create}.py`; `.venv/Lib/site-packages/proot_distro/{names.py,message.py,paths.py,session.py}`; `.venv/Lib/site-packages/proot_distro/helpers/docker/refs.py`; `.venv/Lib/site-packages/proot_distro/commands/{install,rename,backup,copy,remove,reset,restore,run,kill,build}.py`; `flet-build-template.zip` @ `v1.0.4` (272 entries, read-only, inspected in /tmp) · **Date:** 2026-10-20

## What it does / how the app uses it

**It does not — and that is the correct outcome.** `python-slugify` 9.1.3 is installed in `.venv` but is a **dev-only, transitive, and entirely unexercised** package:

```
pyproject.toml:77-84  [dependency-groups] dev = [flet-cli, flet-desktop, pytest, pytest-timeout, ruff]
  └─ uv.lock:220-233  flet-cli 1.0.4 → { name = "cookiecutter" }        (uv.lock:226)
       └─ uv.lock:174-190  cookiecutter 2.7.1 → arrow, binaryornot, click, jinja2,
                            { name = "python-slugify" } (uv.lock:182), pyyaml, requests, rich
            └─ uv.lock:671-680  python-slugify 9.1.3 → { name = "text-unidecode" } (uv.lock:675)
```

The **runtime** closure never touches it. Computed live from the installed metadata (`importlib.metadata`, `Requires-Dist` walked from the roots in `pyproject.toml:9-15` + `pyproject.toml:43-52`): `runtime closure contains python_slugify? False`, `text_unidecode? False`, `cookiecutter? False`, `jinja2? False`; `dev closure contains python_slugify? True`. The only installed distribution that requires it is `cookiecutter -> python-slugify>=4.0.0` (`.venv/Lib/site-packages/cookiecutter-2.7.1.dist-info/METADATA`). `flet build` packages **only** `project.dependencies` + `tool.flet.<platform>.dependencies` — `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576` and `:2605-2609` — so the dev group is never consulted and python-slugify **cannot reach the device**.

The app imports it nowhere: `grep -rn "slugify" src/ -i` → **0 hits**; `grep -rn "slug" tests/ -i` → **0 hits**.

**And it is not even executed on the build host.** Its sole consumer is cookiecutter's Jinja `slugify` filter (`.venv/Lib/site-packages/cookiecutter/extensions.py:15-16` imports it; `:54-93` registers the filter). The only cookiecutter render in this repo's build is the flet v1.0.4 template, and **that template never uses the filter**: scanning all 272 entries of `flet-build-template.zip` for the string `slugify` → **0 files**. flet-cli computes the template's `project_name_slug` itself, with its *own* slugifier, not python-slugify: `.venv/Lib/site-packages/flet_cli/commands/build_base.py:37` (`from flet.utils import … slugify`) and `:1047` (`project_name_slug = slugify(cast(str, project_name_raw))`); same in `create.py:11,124`. The template's `cookiecutter.json` carries `project_name_slug` as a bare default (`''`).

**Plainly: python-slugify is a dormant transitive import. It contributes nothing to the app, to the build, or to the release.** The app needs no slug generator, because every identifier it ever handles is owned, formatted and validated by upstream `proot-distro` (F2).

## Findings

### F1 · P1 · HALLUCINATION in the prior study: the app never uses python-slugify, and the "M3 container/distro naming" it advertises does not exist

- **Where:**
  - `docs/dependency-studies/python-slugify.md:46-53` — *"Our-project utilization (M3 container/distro naming) — Every user-typed name becomes a filesystem/OCI-safe identifier through `slugify`: custom container names, imported-profile names, export filenames."*
  - `docs/dependency-studies/python-slugify.md:55-59` — *"Better than Termux's proot-distro? … friendly names ('My Debian Dev') map deterministically to safe identifiers (`my-debian-dev`) with no illegal-character failures at install time — Termux users hit raw `mkdir`/proot errors for bad names instead."*
  - `docs/dependency-studies/python-slugify.md:63-66` (verification refs) — lists no app-side file at all.
  - App side: `grep -rn "slugify" src/ -i` → **0**; `grep -rn "slug" tests/ -i` → **0**; no import of it in `src/` (full import inventory of `src/` contains only stdlib + `flet`/`flet_ads`/`flet_terminal`/`httpx`/`proot_distro`/`flet_proot`).
  - The plan the study mistook for shipped code: `HEAD:docs/roadmap.md:86` (*"**Certified catalog:** YAML manifests (pyyaml …); names via `slugify`; timestamps via arrow/dateutil/tzdata; optional Jinja2 profile templates with `StrictUndefined`."*, under M3 = *DONE 2026-10-19*). The same document classifies slugify as **dev-only** at `HEAD:docs/roadmap.md:136` — the roadmap contradicts itself, and the study picked the wrong half.
- **What:** there is no certified catalog, no YAML manifest, no import-profile feature, no export feature and no slug anywhere in `src/`: `grep -rn "yaml" src/ -i` → **0**; `grep -rn "export" src/ -i` → **0**; `grep -rn "certified\|catalog" src/ -i` → 3 hits, all unrelated (`src/core/proot_probe.py:100-101` "manifest unavailable", `src/core/storage_paths.py:27` "oci_manifests/", `src/screens/views.py:576` flet-proot wheel manifest). Container names are **not** slugified — they are passed to upstream verbatim (`src/services/proot_service.py:108-114` → `custom_container_name=name`) and upstream either accepts them under its own rule or refuses them. "Imported-profile names" and "export filenames" describe features that do not exist. The identical false claim was already made about `arrow` and had to be corrected in `docs/swarm/dependency-utilization/arrow.md:9,41`.
- **Evidence:**
  ```
  $ grep -rn "slugify" src/ -i | wc -l          → 0
  $ grep -rn "slug" tests/ -i | wc -l            → 0
  $ grep -rn "yaml" src/ -i | wc -l              → 0
  $ grep -rn "export" src/ -i | wc -l            → 0
  $ grep -rn "import arrow\|from arrow" src/     → (0; see docs/swarm/dependency-utilization/arrow.md)
  ```
  and the live runtime-closure proof (see "Evidence" of F3 for the command).
- **Fix / opportunity:** correct `docs/dependency-studies/python-slugify.md:46-53` and `:55-59` to state the truth: python-slugify is a **dev-only, transitive, never-executed** dependency of `cookiecutter`; the app performs no slug generation; container identifiers are upstream's (`proot_distro.names`) and image aliases are upstream's (`derive_alias`). Delete the "Better than Termux's proot-distro?" section, or rewrite it as the (true) statement that upstream already refuses illegal names with a readable message. Do **not** "implement the plan" by importing the package — see F2.
- **Risk if ignored:** an engineer trusts the study and adds `from slugify import slugify` to `src/` to implement the "certified catalog". That import is a **guaranteed `ModuleNotFoundError` on every Android device at startup** — the package is not in the shipped set (F3) — while `pytest`/`ruff`/`flet run` on the host stay green, because the host venv has it installed. The repo's own guard catches this (F4), but only if someone remembers to run the suite.

### F2 · P2 · The app needs no slug generator — upstream owns the name format, and slugifying would silently rewrite names the user asked for

- **Where:**
  - Upstream rule (single source of truth): `.venv/Lib/site-packages/proot_distro/names.py:40` — `_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*\Z")`; `:48-50` `is_valid_name`; `:53-62` `require_valid_name`; the module docstring at `:21-29` states it is used by *every* command that accepts a container name.
  - Enforcement call sites: `commands/install.py:148` (`require_valid_name(custom_container_name)`), `:202,214,221` (`is_valid_name(derived)`); `commands/rename.py:59-60`; `commands/backup.py:458`; `commands/remove.py:131`; `commands/run.py:117`; `commands/kill.py:125`; `commands/restore.py:220`; `commands/build.py:185`; `paths.py:284,552`; `session.py:303`.
  - Upstream alias derivation (authoritative): `.venv/Lib/site-packages/proot_distro/helpers/docker/refs.py:362-376` `derive_alias` → `parse_image_ref(image_ref)` then `repo.split("/")[-1]`; invoked by `commands/install.py:220` (`derived = custom_container_name if custom_container_name else derive_alias(image_ref)`).
  - App side: `src/services/proot_service.py:108-114` (`_ns_install` → `custom_container_name=name`), `:221` (`name or None` — an empty name becomes `None`, so upstream derives the alias), `:141-148` (`_ns_backup`), `:357-363` (`backup_container` → `command_backup`), `:348-354` (`rename_container` → `command_rename`); `src/app_controller.py:342-354` (backup), `:347` (`file_name=f"{container}.tar.gz"`), `:332-340` (rename); `src/screens/views.py:331-339` (the "name (optional)" field).
- **What:** every identifier the app handles is already somebody else's responsibility, and the correct dependency direction is *app → upstream*, never *app → python-slugify*:
  - **Container names** — the user's string is forwarded verbatim and validated upstream. Upstream's rule permits `_` and `.`; python-slugify's output (`[a-z0-9-]`) is a strict *subset*, so slugifying would **rewrite** names upstream already accepts (`my_debian` → `my-debian`, `my.debian` → `my-debian`) and **transliterate** the rest (`Übuntu` → `ubuntu`, `容器` → `rong-qi` — pinyin). The user would get a container whose name they never typed, with no indication.
  - **Image aliases** — `derive_alias` is upstream's and is already called whenever the app passes no name (`src/services/proot_service.py:221` → `commands/install.py:220`). Re-deriving it in app code would fork the rule.
  - **Backup filenames** — `f"{container}.tar.gz"` (`src/app_controller.py:347`) is built from a name upstream has already accepted, and the compression is derived by upstream from the output path's extension (`commands/backup.py:480-487` → `_compression_mode`, `:103-120`). Nothing to slugify; a container named `my.debian` legitimately yields `my.debian.tar.gz`.
  - **Export names** — no export feature exists (F1).
- **Evidence** (upstream rule vs. slugify output, computed live against the installed packages; the regex is copied verbatim from `names.py:40`):
  ```
  'debian'     upstream_valid=True  | slugify='debian'
  'My Debian'  upstream_valid=False | slugify='my-debian'   ← slugify would silently rename
  'my_debian'  upstream_valid=True  | slugify='my-debian'   ← slugify would silently rename
  'my.debian'  upstream_valid=True  | slugify='my-debian'   ← slugify would silently rename
  '-lead'      upstream_valid=False | slugify='lead'
  'Übuntu'     upstream_valid=False | slugify='ubuntu'
  '容器'        upstream_valid=False | slugify='rong-qi'     ← pinyin transliteration
  ''           upstream_valid=False | slugify=''             ← empty slug
  ```
  Upstream's refusal is already user-visible: `commands/install.py:148` → `names.py:60-62` → `crit_error` (`message.py:227-229`) → `msg` → `print(..., file=sys.stderr)` (`message.py:187-207`), all captured by the app's redirect in `src/services/proot_service.py:89-94` and surfaced by `friendly_job_error` (`src/services/proot_service.py:415-423`) as *"container name 'My Debian' is not valid. It must begin with a letter or digit and contain only letters, digits, underscores, dots, or hyphens."*
- **Fix / opportunity:** **do not add python-slugify to the app.** If the name field's UX is to be improved (F5), the fix is upstream's own rule, not a slugifier: expose `proot_distro.names.is_valid_name` through `src/services/proot_service.py` (the one module allowed to import `proot_distro`, per its own module docstring at `:1`) and validate the field before dispatch.
- **Risk if ignored:** a "helpful" slug layer would (a) require a D-003 owner sign-off plus a lock bump to add a runtime dependency that is currently dev-only, (b) produce container names the user did not ask for, including pinyin transliterations of non-Latin names, and (c) fork upstream's naming rule — the exact drift upstream centralised `names.py` to prevent.

### F3 · P2 · python-slugify is not in the shipped dependency set: `from slugify import slugify` in `src/` is a device-only crash

- **Where:** `pyproject.toml:9-15` (runtime `dependencies` = flet, flet-ads, httpx, flet-terminal, proot-distro) and `pyproject.toml:43-52` (`[tool.flet.android] dependencies = ["flet-proot==5.1.107.98"]`); `pyproject.toml:77-84` (the dev group); `uv.lock:586-601` (the lock's own split: runtime at `:586-592`, `[package.dev-dependencies] dev` at `:594-601`); `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2576` + `:2605-2609` (the packaged site-packages is `project.dependencies` + `tool.flet.<platform>.dependencies` only — no reference to dependency-groups or `uv.lock` anywhere in that function); `docs/decisions.md:12-13` (D-003: runtime set frozen, additions need owner sign-off); `docs/reference/dep-cookiecutter-stack.md:3` ("Build-host only; none ship to Android") and `:16` ("python-slugify 9.1.3 + text-unidecode 1.3 — slug filter").
- **What:** the host venv has python-slugify, so every desktop check (`pytest`, `ruff`, `flet run`) would pass with an import that cannot resolve on a device. The failure is at *import time*, i.e. at app launch, on the only platform the app ships to.
- **Evidence** (live, against the installed environment):
  ```
  runtime roots: ['flet', 'flet_ads', 'httpx', 'flet_terminal', 'proot_distro', 'flet_proot']
  dev roots    : ['flet_cli', 'flet_desktop', 'pytest', 'pytest_timeout', 'ruff']
  runtime closure contains python_slugify? False
  runtime closure contains text_unidecode? False
  runtime closure contains cookiecutter?    False
  dev closure contains python_slugify?     True
  who requires python-slugify (installed):  cookiecutter -> python-slugify>=4.0.0
  who requires text-unidecode (installed):  python-slugify -> text-unidecode>=1.3
  ```
- **Fix / opportunity:** none needed — this is the status quo and it is correct. The actionable part is documentation: the study's "Our-project utilization" section (F1) must not be read as a licence to import it into `src/`.
- **Risk if ignored:** a device-only startup crash, invisible to the entire host-side test loop.

### F4 · P2 · The repo's own guard already blocks a dev-only import from `src/` — but only one of the two guards names the package

- **Where:** `tests/test_imports_vs_deps.py:46-59` (`test_imports_all_declared` — every import in `src/` must map to a declared runtime dependency) and `:62-67` (`_dist_map` via `importlib.metadata.packages_distributions`); `tests/test_proot_surfaces.py:133-148` (`test_dev_only_packages_are_not_imported_from_src`, whose `dev_only` set is `{chardet, cookiecutter, pytest, ruff, flet_cli, flet_desktop, binaryornot, jinja2, requests}` — **no `slugify`, no `text_unidecode`**).
- **What:** the `test_imports_vs_deps` guard is the real gate, and it *does* catch a slugify import. Proof, live, replaying the guard's own logic against the installed metadata:
  ```
  slugify          providers=['python_slugify']  declared_match=False  -> guard_would_flag=True
  text_unidecode   providers=['text_unidecode']  declared_match=False  -> guard_would_flag=True
  cookiecutter     providers=['cookiecutter']     declared_match=False  -> guard_would_flag=True
  ```
  (`declared` = `pyproject.toml:9-15` + `:43-52`, normalised as the guard does at `tests/test_imports_vs_deps.py:26-32`.) But `tests/test_proot_surfaces.py:133-148` — the guard whose docstring is literally *"The build-host tree must never reach the app (licensing A4)"* — does **not** list `slugify`/`text_unidecode`, so a targeted "no build-host import" review that reads only that set would miss them.
- **Fix / opportunity:** add `"slugify"` and `"text_unidecode"` to the `dev_only` set at `tests/test_proot_surfaces.py:133-148` (one line, no behaviour change to the app) so the build-host tree list is complete for this package family. (No app code is touched by this recommendation — the report is read-only.)
- **Risk if ignored:** a dev-only import of `slugify` would be caught by one guard but not the other; a reviewer relying on the explicit list alone would call it safe.

### F5 · P3 · The app hand-rolls a second alias derivation at `src/screens/views.py:146` — it should defer to upstream `derive_alias`, not to a slugifier

- **Where:** `src/screens/views.py:146` (`set_name(label.split(":")[0].split("/")[-1])` — the search-hit prefill of the "name (optional)" field at `:331-339`); the hit's `name` comes from `src/services/proot_service.py:263-269` → `.venv/Lib/site-packages/proot_distro/helpers/docker/search.py:120` / `:132-140`; upstream's own derivation is `.venv/Lib/site-packages/proot_distro/helpers/docker/refs.py:362-376`; the app's install path is `src/screens/views.py:100` → `src/app_controller.py:161-180` → `src/services/proot_service.py:212-223` → `commands/install.py:179-181,220`.
- **What:** the app reimplements upstream's alias rule in one line of UI code. For every name Docker Hub can return the two agree (`library/debian` → `debian`; `myuser/img` → `img`), because Hub repository names carry neither a tag nor a registry. They diverge the moment a *registry with a port* is involved: the app's split yields `localhost` for `localhost:5000/foo:tag`, while upstream's `parse_image_ref`-based `derive_alias` yields `foo` (`refs.py:302-324` exists precisely so "a colon in a registry host (port number) is not mistaken for the start of the tag"). The user can reach that state today: the hit prefill writes the name field, and the image-ref field stays editable afterwards (`src/screens/views.py:144-146` sets both), so a stale name can be installed under a ref that upstream would have named differently.
- **Evidence:** `refs.py:362-376` (docstring: *"'localhost:5000/foo:tag' -> 'foo'"*) versus `src/screens/views.py:146` (`label.split(":")[0].split("/")[-1]` → `"localhost"` for the same string). The divergence is **UNVERIFIED at runtime** — `proot_distro` cannot be imported on this Windows host (`import proot_distro.commands.install` → `AttributeError("module 'os' has no attribute 'O_DIRECTORY'")`), so the comparison was done by reading both implementations.
- **Fix / opportunity:** delete the duplicate derivation — pass an empty name and let upstream derive (`src/services/proot_service.py:221` already maps an empty name to `None`, and `commands/install.py:220` then calls `derive_alias`), or ask upstream for the alias through `proot_service` (`from proot_distro.helpers.docker.refs import derive_alias`) rather than re-deriving it in the view. Either keeps upstream authoritative; a slugifier would be the wrong instrument (it would also lowercase and hyphenate names upstream accepts verbatim, and transliterate the rest).
- **Risk if ignored:** a container can be created under a name the user never chose (and cannot easily predict), for a narrow but real class of references.

### F6 · P3 · The prior study's worked example is wrong: `allow_unicode=True` does **not** produce `ubuntu-image`

- **Where:** `docs/dependency-studies/python-slugify.md:32-33` — *"print(slugify("Übuntu image", allow_unicode=True))  # ubuntu-image (unicode path keeps word chars)"*; the behaviour is `.venv/Lib/site-packages/slugify/slugify.py:162-166` (the `allow_unicode` branch does NFKC normalisation and **no** transliteration) and `.venv/Lib/site-packages/slugify/_legacy.py:138-141` (same, in the frozen legacy pipeline that is the default).
- **What:** the live output is `übuntu-image`, not `ubuntu-image`. The comment contradicts its own parenthetical ("unicode path keeps word chars") — the unicode path *keeps* the non-ASCII characters; it does not transliterate them. Anyone who trusts the comment and writes `slugify(name, allow_unicode=True)` expecting an ASCII-safe result will get a non-ASCII identifier.
- **Evidence:** live, installed 9.1.3: `slugify("Übuntu image", allow_unicode=True)` → `'übuntu-image'`; `slugify("Übuntu image")` → `'ubuntu-image'`.
- **Fix / opportunity:** correct the comment at `docs/dependency-studies/python-slugify.md:33` to `# übuntu-image`, and note that the ASCII form requires the default `allow_unicode=False` (transliteration via `slugify.py:51-66`).
- **Risk if ignored:** low for this repo (the package is unused); non-zero for the next reader of the study.

## Missed capabilities (dependency audits only)

**None — and the correct answer is "none".** Every capability python-slugify offers is either redundant with something the repo already ships, or actively wrong for this app's identifier rules:

| Capability | API location | Why the app must not use it |
|---|---|---|
| `slugify(text, …)` core | `slugify/slugify.py:185-229` | Would rewrite upstream-validated container names (F2). |
| `smart_truncate` | `slugify/_legacy.py:68-102` | The app has no long-name surface; upstream's own rule has no length limit (`names.py:40`). |
| `max_length` / `word_boundary` / `save_order` | `slugify/slugify.py:190-193`, `_legacy.py:159-161` | Same: no truncation need; truncation would break the upstream name rule's "names the user chose" contract. |
| `stopwords` | `slugify/slugify.py:194`, `_legacy.py:152-154` | No stopword semantics in container naming. |
| `replacements` / `replacement_stage` | `slugify/slugify.py:197,200`, `_legacy.py:133-135,155-157` | No user-facing text substitution in identifiers. |
| `allow_unicode` | `slugify/slugify.py:198`, `_legacy.py:138-139` | Upstream's name regex is ASCII-only (`names.py:40`); a unicode container name is *invalid upstream*, so producing one is pointless. |
| `regex_pattern` | `slugify/slugify.py:195`, `_legacy.py:148` | Upstream's regex is the rule; a second pattern would fork it. |
| `backend` (`auto`/`text-unidecode`/`unidecode`/`anyascii`) | `slugify/slugify.py:25,51-66` | The transliteration engine is the ~3 MB `text-unidecode` table (see `docs/dependency-studies/text-unidecode.md`) — a device-cost argument against shipping it for a feature the app does not have. |
| `algorithm='modern'` | `slugify/slugify.py:202,218-229`, `_modern_slugify` at `:122-182` | The frozen legacy pipeline is the default and "must never change" (`_legacy.py:1-9`); opting into `modern` for a brand-new identifier space would be a gratuitous behaviour difference. |
| `slugify.special` language tables (`PRE_TRANSLATIONS`, `CYRILLIC`, `GERMAN`, `GREEK`) | `slugify/special.py:26-55` | Re-exported at package level through `slugify/__init__.py:1`; not referenced by `slugify()` itself (the default pipeline never consults them). Unused here. |
| `slugify.__main__` CLI | `slugify/__main__.py:1-…` | A host-side CLI with no role in the app or the build. |

**The already-shipped alternative.** If a *future* surface ever needs a normalized identifier that is **not** a container name (a profile label, a catalog key, an export stem), the repo already ships a slugifier **in the runtime set**: `flet.utils.slugify` — `.venv/Lib/site-packages/flet/utils/slugify.py:5-14` (NFKD → ASCII → strip non-word → lowercase → `[-_\s]+` → `-`), exported at `.venv/Lib/site-packages/flet/utils/__init__.py:35,75`. `flet` is a declared runtime dependency (`pyproject.toml:10`), so using it costs **zero** new packages, zero lock churn and zero D-003 sign-off. (Behavioural note: it is ASCII-only — `flet.utils.slugify("容器")` → `''` — whereas python-slugify transliterates to `'rong-qi'`. Neither is upstream's rule, so neither may decide a *container* name.) The sibling cookiecutter study already noted this split: `docs/dependency-studies/cookiecutter.md:260` — *"flet uses sibling `slugify` in Python (not this filter) for `project_name_slug`"*.

## Verified-good list

- **Upstream is the single authority for container-name format, and every entry point enforces it.** `proot_distro/names.py:40` + 11 call sites (`install.py:148,202,214,221`; `rename.py:59-60`; `backup.py:458`; `remove.py:131`; `run.py:117`; `kill.py:125`; `restore.py:220`; `build.py:185`; `paths.py:284,552`; `session.py:303`). The app therefore has **no** name-sanitising job of its own.
- **The app never imports python-slugify** — `grep -rn "slugify" src/ -i` → 0; `grep -rn "slug" tests/ -i` → 0. No dead import, no unused dependency in the runtime set.
- **python-slugify cannot reach the device.** Packaged deps = `project.dependencies` + `tool.flet.<platform>.dependencies` only (`flet_cli/commands/build_base.py:2566-2576,2605-2609`); the runtime closure computed from installed metadata contains no `python_slugify`/`text_unidecode`/`cookiecutter`/`jinja2`.
- **The dependency is dev-only in the lock's own words**: `uv.lock:586-592` (runtime) vs `uv.lock:594-601` (`[package.dev-dependencies] dev`); `uv.lock:182` is the only edge into python-slugify and it hangs off `cookiecutter` (`uv.lock:174-190`), which hangs off `flet-cli` (`uv.lock:220-233,226`).
- **Even on the build host the package is never called.** All 272 entries of `flet-build-template.zip` @ v1.0.4 scanned: **0** mention `slugify`; flet-cli computes `project_name_slug` with `flet.utils.slugify` (`flet_cli/commands/build_base.py:37,1047-1048`; `create.py:11,124`).
- **`flet build` never sees the dev group** — no reference to `dependency-groups`/`uv.lock` anywhere in `package_python_app`; `tests/test_imports_vs_deps.py:46-59` encodes the same rule for `src/`.
- **The empty-name path is correct**: `src/services/proot_service.py:221` maps `""` → `None`, so upstream derives the alias (`commands/install.py:220`) instead of the app inventing one; `commands/install.py:143-145` therefore never hits its "container name can't be empty" branch.
- **The backup path is correctly delegated**: the app only *suggests* a file name (`src/app_controller.py:347`, `f"{container}.tar.gz"`), the user picks the real path, and upstream derives the compression from the extension (`commands/backup.py:480-487` → `_compression_mode` at `:103-120`).
- **The app does not hand-roll any other identifier derivation.** `grep -rn "re\.sub\|\.lower()\|\.replace(" src/` returns only three hits, none of them a name transform: `src/services/proot_service.py:443` (rate-limit marker matching), `src/services/session_service.py:45` (line-continuation unwrap), `src/services/update_service.py:36` (hostname lowercasing).
- **The upstream validation error is user-visible**: `crit_error` → `msg` → `print(..., file=sys.stderr)` (`message.py:187-207,227-229`) is captured by `src/services/proot_service.py:89-94` and rendered by `friendly_job_error` (`:415-423`). The `tty_safe_for_writes` guard (`message.py:116-148`) returns True under the app's `io.StringIO` redirect because `StringIO.fileno()` raises `io.UnsupportedOperation`, which inherits from **both** `OSError` and `ValueError` (verified live) and is caught at `message.py:135-138`.
- **`docs/reference/dep-cookiecutter-stack.md:3,16` is already correct** ("Build-host only; none ship to Android"; "python-slugify 9.1.3 + text-unidecode 1.3 — slug filter"). Only the *study* is wrong, not the reference doc.
- **Sibling swarm reports do not conflict**: `docs/swarm/dependency-utilization/cookiecutter.md:11` reaches the same dev-only conclusion for the parent package; `docs/swarm/dependency-utilization/arrow.md` documents the identical study-hallucination pattern for the sibling case.

## Unverified

- **End-to-end runtime of the upstream name rejection on a device.** `proot_distro` cannot be imported on this Windows host (`import proot_distro.commands.install` → `AttributeError: module 'os' has no attribute 'O_DIRECTORY'`), so the install-with-a-bad-name path was verified by **source reading only** (`commands/install.py:143-148` → `names.py:60-62` → `message.py:227-229` → the app's capture at `src/services/proot_service.py:89-94`), not executed. The regex behaviour itself was executed (the `_NAME_RE` pattern was copied verbatim from `names.py:40`).
- **The F5 divergence on a registry-with-a-port reference** was derived by reading `src/screens/views.py:146` against `refs.py:362-376`; it was not executed (same import limitation). The claim that Docker Hub's search API never returns a port-bearing name is supported by `search.py:120` (`is_repository_path(name)`) but was not tested against the live API.
- **`docs/roadmap.md` and `THIRD-PARTY-SOURCES.md` are currently deleted in the working tree** (`git status --short` shows ` D docs/roadmap.md`, ` D THIRD-PARTY-SOURCES.md`, and 20 other deletions; `docs/swarm/` is untracked). The roadmap citations in F1 were read from `git show HEAD:docs/roadmap.md` (last touched by commit `550b1df`) and are quoted from that revision, not from the working tree. The `THIRD-PARTY-SOURCES.md` / `generate_third_party_sources.py` licence-manifest question (whether python-slugify is listed as a shipped component) could not be checked against the current tree; the deleted `generate_third_party_sources.py` was **not** executed.
- **Whether the owner intends to revive the M3 "certified catalog"** (the plan line that names `slugify`) is unknown. F1 asserts only that the study's *present-tense* claim is false today, not that the feature is cancelled — the same caveat the arrow audit recorded.
- **The exact byte size python-slugify + text-unidecode would add to the APK** was not measured (no `flet build` was run — D-005 forbids local `flet build`; owner rule). The qualitative argument stands on its own: the package is not in the packaged dependency set at all.
