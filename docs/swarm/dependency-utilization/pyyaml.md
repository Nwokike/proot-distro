# pyyaml 6.0.3 utilization — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `docs/dependency-studies/pyyaml.md`; `docs/dependency-studies/INDEX.md`; `docs/swarm/BRIEF.md`; `docs/decisions.md` (D-003, D-004); `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `build_flet_proot_wheel.py`; `version.json`; `src/` (full import/IO scan); `tests/{test_proot_surfaces.py,test_imports_vs_deps.py,test_version_sync.py}`; `.venv/Lib/site-packages/yaml/` (16 modules, read in full); `.venv/Lib/site-packages/cookiecutter/config.py`; `.venv/Lib/site-packages/flet_cli/commands/build_base.py`; `.venv/Lib/site-packages/flet_cli/utils/{project_dependencies.py,pyproject_toml.py}`; `.venv/Lib/site-packages/proot_distro/{paths.py,commands/install.py,commands/backup.py,commands/restore.py}`; `.venv/Lib/site-packages/flet_terminal/mobile_terminal.py`; `git show HEAD:docs/roadmap.md` (deleted in the working tree) · **Date:** 2026-10-20

## What it does / how the app uses it

**PyYAML 6.0.3 is a dev-only, transitive dependency. The app itself never reads or writes YAML, and there is no YAML manifest layer, catalog, config file, backup-metadata format or distro-alias table anywhere in `src/`.** It enters the environment only as `flet-cli → cookiecutter → pyyaml`:

`pyproject.toml:9-15` (runtime deps: flet, flet-ads, httpx, flet-terminal, proot-distro — **no pyyaml**) → `pyproject.toml:77-84` (dev group: `flet-cli>=1.0.4`) → `uv.lock:596` (`{ name = "flet-cli" }` under `[package.dev-dependencies]`) → `uv.lock:220-233` (flet-cli 1.0.4 → cookiecutter at `:226`) → `uv.lock:174-186` (cookiecutter 2.7.1 → `{ name = "pyyaml" }` at `:183`) → `uv.lock:683-706` (pyyaml 6.0.3).

The runtime closure has no edge to it: `uv.lock:193-201` (flet 1.0.4 → httpx, msgpack, oauthlib, repath), `uv.lock:574-582` (proot-distro 5.10.0 — **no dependency list at all**). And the *packaged* app's dependency set is computed from `project.dependencies` + `tool.flet.<platform>.dependencies` only — `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2577` — so the dev group is never consulted when the APK's site-packages is built. **pyyaml cannot reach a device.**

**Its one real job is legitimate and load-bearing: it is flet-cli's YAML engine for `pubspec.yaml`.** `.venv/Lib/site-packages/flet_cli/commands/build_base.py:13` (`import yaml`), `:3615-3627` (`load_yaml` → `yaml.safe_load`), `:3629-3639` (`save_yaml` → `yaml.dump`), and the patch sites `:1917`, `:1932`, `:1955`, `:1968`, `:2054` (`pubspec = self.load_yaml(self.pubspec_path)`) plus the pre-render escaping at `:1588-1591`. Every `flet build apk` / `flet build aab` runs that path — `.github/workflows/app.yml:151-161` and `:205-215` — with the dev group installed at `:149` and `:203` (`uv sync --frozen --group dev`). cookiecutter uses the same package for `~/.cookiecutterrc`: `.venv/Lib/site-packages/cookiecutter/config.py:11`, `:70` (`yaml.safe_load(file_handle) or {}`), `:71` (`except yaml.YAMLError`), `:78` (merge against `DEFAULT_CONFIG`).

**Per-surface answer to "does the app read/write YAML anywhere?" — no, on every surface:**

| Surface | What the app actually does | Format |
|---|---|---|
| Container manifest | `src/services/proot_service.py:194` → `paths.container_image_origin(name)` → `read_container_manifest` → `json.loads(raw)` at `.venv/Lib/site-packages/proot_distro/paths.py:340`. The app never parses it; upstream does. | **JSON** (`proot_distro/commands/install.py:340` writes it) |
| Backup metadata | `src/services/proot_service.py:357-363` delegates to upstream `command_backup`; the archive member is `manifest.json` — `.venv/Lib/site-packages/proot_distro/commands/backup.py:22`, restored at `commands/restore.py:235-236,742-744` | **JSON** (upstream's format; forking it is forbidden by BRIEF rule 4) |
| App config / settings | `ft.SharedPreferences` key-value store — `src/core/shared_services.py:28`, read/write at `src/app_controller.py:119,123,257,268,298,307` | **key-value** (no file, no format) |
| Update feed | `src/services/update_service.py:80` (`response.json()`) over `version.json` (`src/core/constants.py:17`); the same file is read by CI at `.github/workflows/app.yml:69-72` and by `tests/test_version_sync.py:35-38` | **JSON** |
| Terminal resize event | `src/screens/terminal_view.py:85` (`json.loads(e.data)`) — mirrors the producer's own parser, `.venv/Lib/site-packages/flet_terminal/mobile_terminal.py:113-117` | **JSON** (upstream wire format) |
| Distro aliases / certified catalog | **does not exist.** The image reference is free text: `src/screens/views.py:83` (`hint_text="docker image ref (e.g. debian:bookworm)"`), `src/components/ui.py:48`, `src/screens/onboarding_view.py:25`. `grep -rnw "yaml\|YAML" src/ --include="*.py"` → **0 hits**. | **none** |
| Anything the app writes at all | staged `.so` bytes and a probe file — `src/core/proot_probe.py:97`, `:131-132`; directories at `:77`, `:129` | bytes/dirs only |

**The app therefore uses JSON where YAML would be wrong** — in all three cases JSON is not a stylistic choice but a *contract*: the update feed is an HTTP document shared with CI and a test, the terminal payload is produced by an upstream Dart extension, and the container manifest is upstream's on-disk format. A YAML switch would break the second and third consumers and gain nothing in the first.

## Findings

### F1 · P2 · The study's "our manifest layer — first-class" claim is false for the current tree, and the plan it rests on is listed DONE

- **Where:**
  - `docs/dependency-studies/pyyaml.md:64-72` — *"PyYAML is our manifest layer: container `manifest.json` companions, distro catalog entries (certified map: `ubuntu:24.04`, `debian:bookworm`, `alpine:3.21`), per-image metadata (`oci_manifests/` mirrors), and build/CI config."*
  - `docs/dependency-studies/INDEX.md:61` — the one-line summary: *"Manifests read/write; safe_load only"*.
  - `docs/dependency-studies/pyyaml.md:89` — the verification ref `docs/roadmap.md §M3/M5`.
  - `git show HEAD:docs/roadmap.md:86` — *"**Certified catalog:** YAML manifests (pyyaml; `safe_load` + stable dumps) with tag+digest+registry"* — under a milestone heading `git show HEAD:docs/roadmap.md:80` reads *"### M3 — App scaffold + distro manager → **DONE (2026-10-19; rulings in D-015)**"*.
  - The app: `src/screens/views.py:83`, `src/components/ui.py:48`, `src/screens/onboarding_view.py:25` (free-text image ref — no catalog), and `grep -rnw "yaml\|YAML" src/ --include="*.py"` → 0 hits.
- **What:** the study describes an implementation that does not exist. There is no manifest layer, no catalog, no per-image metadata file, no `oci_manifests/` YAML mirror, and no build/CI YAML usage in the repo. The roadmap line the study cites is a **plan line under a milestone marked DONE** whose deliverable was never built — the sibling jinja2 audit reached the same conclusion independently (`docs/swarm/dependency-utilization/jinja2.md:99`). The study also credits "M5 Android compile-proof step that reads lock/manifest trees" (`pyyaml.md:70`); the CI compile-proof step reads `pyproject.toml` with `tomllib` and `version.json` with `json` (`.github/workflows/app.yml:62-72`), never YAML.
- **Evidence:**
  ```
  $ grep -rnw "yaml\|YAML" src/ --include="*.py"          # → (no output)
  $ grep -rn "yaml" .venv/Lib/site-packages/proot_distro/ --include="*.py" | wc -l   # → 0
  $ grep -rn "yaml" .venv/Lib/site-packages/flet_cli/ --include="*.py" | wc -l      # → 30 (build_base.py only)
  $ git show HEAD:docs/roadmap.md | sed -n '80p;86p;136p'
  ### M3 — App scaffold + distro manager → *DONE (2026-10-19; rulings in D-015)*
  - **Certified catalog:** YAML manifests (pyyaml; `safe_load` + stable dumps) with tag+digest+registry (`distro-images.md` §4); names via `slugify`; timestamps via arrow/dateutil/tzdata; optional Jinja2 profile templates with `StrictUndefined`.
  - **dev stack** (pytest 9.1.1 / pytest-timeout 2.4.0 / ruff 0.17.1 / packaging / pluggy / iniconfig / colorama / watchdog / qrcode / click / rich / pyyaml / slugify / arrow-chain / jinja2 / chardet / binaryornot): dev-only; config recipes captured per file.
  ```
  Note the roadmap contradicts itself: `:86` needs pyyaml at runtime for the catalog; `:136` lists pyyaml as **dev-only**.
- **Fix / opportunity:** correct `docs/dependency-studies/pyyaml.md:64-72` and `docs/dependency-studies/INDEX.md:61` to say *dev-only, transitive, used by flet-cli for `pubspec.yaml` and by cookiecutter for `~/.cookiecutterrc`; the app itself uses no YAML*. If the certified catalog is revived (roadmap `:42`, `:86`), ship it as **JSON** — see F3 for why YAML is the wrong format here.
- **Risk if ignored:** the synthesis adopts a "capability we already ship" that does not exist. Worse, the study's wording invites the obvious next step — "we already have pyyaml, so the catalog is free" — which would add pyyaml to `[project].dependencies` (a D-003 change needing owner sign-off, `docs/decisions.md:12-13`) and ship ~800 KB of parser plus a C extension to every device for a file the app does not read (F3).

### F2 · P2 · `yaml.Loader` is **not** a `FullLoader` alias — it is the unsafe constructor loader, and the study points readers at it

- **Where:**
  - `docs/dependency-studies/pyyaml.md:26-27` — *"`FullLoader` (full YAML without arbitrary code), `UnsafeLoader` (full object construction — never on untrusted input), `Loader` (= FullLoader alias, unverified alias claim — check `yaml.Loader` before relying)"*.
  - `.venv/Lib/site-packages/yaml/loader.py:41-48` — `class Loader(Reader, Scanner, Parser, Composer, Constructor, Resolver)` — the **`Constructor`**, not `FullConstructor`.
  - `.venv/Lib/site-packages/yaml/loader.py:51-62` — the library's own comment: *"UnsafeLoader is the same as Loader (which is and was always unsafe on untrusted input) … Loader is left intact to ensure backwards compatibility."*; `class UnsafeLoader(Reader, Scanner, Parser, Composer, Constructor, Resolver)`.
  - `.venv/Lib/site-packages/yaml/loader.py:21-29` — `FullLoader` (the `FullConstructor` variant) is a **separate class**.
- **What:** the study's parenthetical is wrong in the dangerous direction. `yaml.Loader` is *more* permissive than `FullLoader` — it is `yaml.UnsafeLoader` under another name, and it can construct arbitrary Python objects from an untrusted document. The study invites a reader to "check before relying"; the check refutes it.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "
  import yaml
  print(yaml.Loader.__mro__)
  print(yaml.UnsafeLoader is yaml.Loader, yaml.FullLoader is yaml.Loader)"
  (<class 'yaml.loader.Loader'>, <class 'yaml.reader.Reader'>, <class 'yaml.scanner.Scanner'>,
   <class 'yaml.parser.Parser'>, <class 'yaml.composer.Composer'>,
   <class 'yaml.constructor.Constructor'>, <class 'yaml.resolver.Resolver'>, <class 'object'>)
  False False
  ```
  and `yaml/loader.py:51-54` states outright that `Loader` is unsafe.
- **Fix / opportunity:** correct `docs/dependency-studies/pyyaml.md:26-27` to: `Loader` ≡ `UnsafeLoader` (unsafe object construction); use `safe_load`/`SafeLoader` or `full_load`/`FullLoader` on untrusted input. If the catalog ever ships as YAML, the house rule must be **`safe_load` only, never `load(f, Loader)`**.
- **Risk if ignored:** a contributor who reads the study, sees "Loader = FullLoader", and "simplifies" a `safe_load` call to `yaml.load(f, yaml.Loader)` gets arbitrary object construction on a file that may be user-supplied or fetched over the network — the exact hazard `yaml/loader.py:51-54` warns about.

### F3 · P2 · PyYAML publishes **no Android wheel** — the M3 "YAML manifest" plan is not implementable at runtime without new native-wheel work

- **Where:**
  - `uv.lock:687-706` — the complete published wheel set for pyyaml 6.0.3: `macosx_10_13_x86_64`, `macosx_11_0_arm64`, `manylinux2014_{aarch64,i686,s390x,x86_64}`, `musllinux_1_2_{aarch64,i686,s390x,x86_64}`, `win_amd64`, `win_arm64` (+ the `cp314t` free-threaded twins). **No `android_*` tag** (`grep -c android` over that block → 0).
  - `build_flet_proot_wheel.py:183-184` — the house's precedent for shipping an ABI-specific artifact to Android: `"aarch64": "py3-none-android_24_arm64_v8a"`, `"x86_64": "py3-none-android_24_x86_64"`.
  - `docs/decisions.md:16` (D-004) — the house already carries an Android-wheel ceiling rule (the msgpack rule).
  - `git show HEAD:docs/roadmap.md:86` — the catalog plan that would make pyyaml a runtime dependency.
- **What:** the plan behind the study's "first-class" claim requires parsing YAML **on the device**. PyYAML upstream ships no Android wheel, so `pip` on Android would fall back to the sdist and need a C compiler — the failure mode the `flet-proot` wheel was built to work around (`build_flet_proot_wheel.py`, `pyproject.toml:50-52`). The package also carries a C extension (`yaml/_yaml.cp314-win_amd64.pyd` on this host) that has no Android build. So "add pyyaml to the runtime deps for the M3 catalog" is not a one-line pyproject change; it is a native-wheel project of its own.
- **Evidence:**
  ```
  $ sed -n '683,706p' uv.lock | grep -o "pyyaml-6.0.3-[^\"]*" | sed 's/.*-cp314//' | sort
  -macosx_10_13_x86_64.whl
  -macosx_11_0_arm64.whl
  -manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl
  -manylinux2014_i686.manylinux_2_17_i686.manylinux_2_28_i686.whl
  -manylinux2014_s390x…  -manylinux2014_x86_64…
  -musllinux_1_2_{aarch64,i686,s390x,x86_64}.whl
  -win_amd64.whl  -win_arm64.whl   (+ cp314t twins)
  $ sed -n '683,706p' uv.lock | grep -c android
  0
  ```
  (The `manylinux2014_i686`/`musllinux i686` entries are elided above for width; the count of `android` matches is 0 either way.)
- **Fix / opportunity:** if the certified catalog is revived, ship it as **JSON** — `json` is stdlib, works on every target, needs no wheel, and the repo already has a shipped-JSON precedent (`version.json`, `src/services/update_service.py:80`, `tests/test_version_sync.py:35-38`). If a human-editable catalog is the goal, keep the YAML file **host-side** and render it to JSON at build time (the same "render host-side, ship the rendered output" conclusion the jinja2 audit reached, `docs/swarm/dependency-utilization/jinja2.md:73`).
- **Risk if ignored:** a plan that looks like a one-line dependency addition is actually a native-wheel + signing + 16 KB-alignment task (`.github/workflows/app.yml:174-175`, `:290-291`), discovered mid-milestone.

### F4 · P3 · `safe_load` does **not** use the C loader — the study's "`safe_load` picks C when present" is false, and the gap is ~6×

- **Where:**
  - `docs/dependency-studies/pyyaml.md:69-70` — *"…`CSafeLoader`-equivalent default (`safe_load` picks C when present)…"*.
  - `.venv/Lib/site-packages/yaml/__init__.py:117-125` — `def safe_load(stream): … return load(stream, SafeLoader)`.
  - `.venv/Lib/site-packages/yaml/loader.py:31-39` — `SafeLoader` is the **pure-Python** `Reader, Scanner, Parser, Composer, SafeConstructor, Resolver` stack.
  - `.venv/Lib/site-packages/yaml/cyaml.py:23-28` — `class CSafeLoader(CParser, SafeConstructor, Resolver)` — the libyaml path, reachable only by asking for it by name.
  - `.venv/Lib/site-packages/yaml/__init__.py:12-16` — `from .cyaml import *` → `__with_libyaml__ = True` on this host (the C extension `yaml/_yaml.cp314-win_amd64.pyd` is present).
- **What:** `safe_load` is pure Python everywhere. The C loader is available and free, but must be requested explicitly (`yaml.load(stream, yaml.CSafeLoader)`). The study's "CSafeLoader-equivalent default" would mislead anyone who assumes `safe_load` is already the fast path.
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "
  import timeit, yaml
  doc = '\n'.join('key_%d: value_%d' % (i, i) for i in range(2000))
  print('safe_load (pure SafeLoader):', round(timeit.timeit(lambda: yaml.safe_load(doc), number=20), 3), 's / 20 iters')
  print('CSafeLoader (libyaml C ext)  :', round(timeit.timeit(lambda: yaml.load(doc, yaml.CSafeLoader), number=20), 3), 's / 20 iters')"
  safe_load (pure SafeLoader): 9.89 s / 20 iters
  CSafeLoader (libyaml C ext)  : 1.611 s / 20 iters        # ≈6.1× faster
  ```
- **Fix / opportunity:** correct `docs/dependency-studies/pyyaml.md:69-70`. If YAML is ever parsed on-device, use `yaml.load(f, yaml.CSafeLoader)` (and `yaml.CSafeDumper` for writes — `.venv/Lib/site-packages/yaml/cyaml.py:68-83`), guarded by `yaml.__with_libyaml__`.
- **Risk if ignored:** an on-device catalog parse at ~6× the necessary cost, on the main thread, at app start.

### F5 · P3 · The dev-only import guard does not name `yaml`, and the APK/AAB prune grep does not name the build-host stack

- **Where:**
  - `tests/test_proot_surfaces.py:133-148` — `test_dev_only_packages_are_not_imported_from_src`, docstring *"The build-host tree must never reach the app (licensing A4)"*; the `dev_only` set at `:135-145` = chardet, cookiecutter, pytest, ruff, flet_cli, flet_desktop, binaryornot, jinja2, requests — **no `yaml`**.
  - `tests/test_imports_vs_deps.py:46-59` — the guard that *does* catch it: it maps module → distribution via `importlib.metadata.packages_distributions()` (`:62-67`) and compares against `project.dependencies` + `tool.flet.<platform>.dependencies` (`:19-31`).
  - `.github/workflows/app.yml:166-172` and `:280-288` — the prune grep `pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/`.
  - `pyproject.toml:62-63` — `[tool.flet.cleanup] package_files = ["oauthlib/**"]`, the existing mechanism for excluding a package from the APK.
- **What:** the app is protected today by the *other* test: `packages_distributions()` maps the module `yaml` to the distribution `PyYAML`, and `"pyyaml"` is not in `project.dependencies`, so `test_imports_all_declared` fails on any `import yaml` in `src/` (verified: `packages_distributions()['yaml'] == ['PyYAML']`; both guard tests pass today — 10 passed). But the guard whose stated purpose is the **licensing A4 boundary** names every other build-host package and skips the one the M3 plan would promote to runtime; and the CI prune grep names none of the build-host stack (the sibling cookiecutter audit already proposed half of this fix at `docs/swarm/dependency-utilization/cookiecutter.md:147-152`).
- **Evidence:**
  ```
  $ .venv/Scripts/python.exe -c "
  from importlib import metadata
  print(metadata.packages_distributions()['yaml'])"      # -> ['PyYAML']
  $ .venv/Scripts/python.exe -m pytest tests/test_imports_vs_deps.py tests/test_proot_surfaces.py -q
  ..........                                              # 10 passed
  $ grep -n "yaml" tests/test_proot_surfaces.py          # -> (no output)
  ```
- **Fix / opportunity:** add `"yaml"` (and `"pyyaml"`) to the `dev_only` set at `tests/test_proot_surfaces.py:135-145`; extend the prune greps at `.github/workflows/app.yml:168` and `:282` to `…|docs/|yaml/|cookiecutter/|jinja2/|requests/|flet_cli/`.
- **Risk if ignored:** low today (the other guard holds), but the named list that exists to enforce a licensing boundary has a hole exactly where the next dependency addition would land.

### F6 · P3 · flet-cli *writes* YAML with the permissive `yaml.dump`, so "always `safe_load`" is only half the upstream contract

- **Where:**
  - `.venv/Lib/site-packages/flet_cli/commands/build_base.py:3615-3627` (`load_yaml` → `yaml.safe_load`) **vs** `:3629-3639` (`save_yaml` → `yaml.dump(doc, f)`).
  - `.venv/Lib/site-packages/yaml/__init__.py:248-253` (`dump` → `Dumper=Dumper`) vs `:263-269` (`safe_dump` → `Dumper=SafeDumper`).
  - `.venv/Lib/site-packages/yaml/dumper.py:27-43` (`SafeDumper` = `SafeRepresenter`) vs `:45-61` (`Dumper` = full `Representer`).
  - `docs/dependency-studies/pyyaml.md:68-69` — the study's house rule: *"always `safe_load` + `except yaml.YAMLError`; `sort_keys=True, allow_unicode=True` on every dump so diffs are stable"*.
- **What:** the read side upstream is safe; the write side is the **full** dumper, which will happily emit `!!python/object/...` tags for non-standard types. It is harmless for `pubspec.yaml` (a plain dict of str/list) — but the study presents the house rule as if it were observed upstream, and it is not: `yaml.dump` at `:3639` sets neither `sort_keys` nor `allow_unicode` explicitly (the `sort_keys=True` default comes from the Dumper constructor, `dumper.py:45-52`; `allow_unicode` defaults to `None` → the emitter's own default).
- **Evidence:**
  ```
  build_base.py:3615  def load_yaml(self, path):
  build_base.py:3627          return yaml.safe_load(f)
  build_base.py:3629  def save_yaml(self, path, doc):
  build_base.py:3639          yaml.dump(doc, f)
  yaml/__init__.py:248  def dump(data, stream=None, Dumper=Dumper, **kwds):
  yaml/__init__.py:263  def safe_dump(data, stream=None, **kwds):
  ```
- **Fix / opportunity:** in the study, mark the `safe_load` + `sort_keys`/`allow_unicode` rule as **our** rule for any future catalog writer, not as an upstream observation, and note that the upstream write path uses the permissive dumper.
- **Risk if ignored:** a catalog writer modelled on flet-cli's `save_yaml` inherits the permissive dumper; if it ever dumps a non-standard type, the file gains `!!python/object` tags that `safe_load` will refuse to read back — a self-inflicted round-trip failure.

## Missed capabilities (dependency audits only)

**Verdict: nothing meaningful is missed, and nothing should be adopted.** PyYAML is a build-host package here, and the app has no YAML surface to give it one. The capabilities below are listed because the study's "first-class" framing invites them — and the honest answer to each is "not now, not like this".

| Capability | API location | Proposed integration point | Value vs cost |
|---|---|---|---|
| `CSafeLoader` / `CSafeDumper` (libyaml, ~6.1× faster; `__with_libyaml__ = True` on this host) | `yaml/cyaml.py:23-28`, `:68-83`; `yaml/__init__.py:12-16` | only if a YAML catalog is ever parsed on-device | **Value 0 today** (no YAML is parsed). If the catalog ever ships as YAML, use it — but see F3: there is no Android wheel, so it cannot ship at all without native-wheel work. |
| `safe_load_all` / `safe_dump_all` (multi-document) | `yaml/__init__.py:127-135`, `:255-261` | n/a | No multi-document format exists or is planned. **No.** |
| `add_constructor` / `add_representer` / `add_implicit_resolver` / `add_path_resolver` (typed schema hooks) | `yaml/__init__.py:271-341` | a typed catalog schema | Would let a YAML catalog carry typed fields — but the app's data model is already plain dicts (`src/core/state.py`), and the same typing is available for free with a JSON file + a hand-written `dataclass`/Pydantic-free validation. **Cost (a runtime YAML dep + Android wheel) exceeds the value.** |
| `YAMLObject` / `YAMLObjectMetaclass` (declarative serializable classes) | `yaml/nodes.py`, `yaml/constructor.py` | n/a | A class-based serialization model for a format the app does not use, and one that cannot be re-serialized by `safe_load`. **No.** |
| The one capability worth *borrowing* is not a pyyaml API at all: **`json` (stdlib) already provides the whole catalog surface with zero dependencies, zero wheel work, and an in-repo precedent** (`version.json` → `src/services/update_service.py:80` → `tests/test_version_sync.py:35-38` → `.github/workflows/app.yml:69-72`). | `src/services/update_service.py:80` | a future `catalog.json` shipped as app data | **High value, zero cost.** The catalog's per-entry fields (`tag` + `digest` + `registry`, per `git show HEAD:docs/compliance/distro-images.md` §4.1–4.2) are flat strings — JSON is the natural shape. |

**If the certified catalog is revived, the correct answer is JSON, not YAML.** The roadmap's own line 136 lists pyyaml as dev-only; the JSON path keeps it that way, needs no D-003 change, needs no Android wheel, and reuses the format the app already ships and CI already reads.

## Verified-good list

- **pyyaml 6.0.3 is genuinely installed and is the version the study names.** `yaml/__init__.py:11` (`__version__ = '6.0.3'`); `.venv/Lib/site-packages/pyyaml-6.0.3.dist-info/METADATA:2-3` (`Name: PyYAML`, `Version: 6.0.3`), `License: MIT` at `:9`.
- **It is dev-only, transitively, and provably unreachable from the packaged app.** `pyproject.toml:9-15` (runtime) vs `:77-84` (dev); `uv.lock:596` → `:226` → `:183` → `uv.lock:683-706`; the runtime closure has no pyyaml edge (`uv.lock:193-201`, `:574-582`); the packaged dep set is `project.dependencies` + `tool.flet.<platform>.dependencies` only (`flet_cli/commands/build_base.py:2566-2577`), so the dev group never enters `build/site-packages`. The repo asserts the same boundary in `tests/test_proot_surfaces.py:133-148` and `tests/test_imports_vs_deps.py:46-59` (both green: 10 passed).
- **Its actual job works and is load-bearing.** `flet_cli/commands/build_base.py:13, 930, 1588-1591, 1917, 1932, 1955, 1968, 2054, 3615, 3627, 3639` — every anchor the study lists is **exact** (checked line by line). The pubspec patch path runs on every `flet build apk|aab` (`.github/workflows/app.yml:151-161`, `:205-215`) with the dev group installed (`:149`, `:203`).
- **cookiecutter's use is also exact.** `cookiecutter/config.py:11, 70, 71, 78` — all four anchors match the study; `safe_load` + `except yaml.YAMLError` + merge against `DEFAULT_CONFIG`, exactly as described.
- **`yaml` really is backed by libyaml here.** `yaml/__init__.py:12-16` sets `__with_libyaml__ = True`; `yaml/_yaml.cp314-win_amd64.pyd` is present; `yaml/cyaml.py:3-4` exports `CBaseLoader, CSafeLoader, CFullLoader, CUnsafeLoader, CLoader, CBaseDumper, CSafeDumper, CDumper`, and live introspection confirms all of them are attributes of the `yaml` module (plus `SafeLoader`, `SafeDumper`, `FullLoader`, `UnsafeLoader`, `BaseLoader`, `Loader`, `Dumper`, `YAMLError`, `MarkedYAMLError`, `YAMLObject`, `safe_load`, `safe_load_all`, `safe_dump`, `safe_dump_all`, `load`, `load_all`, `dump`, `dump_all`, `add_representer`, `add_constructor`, `add_implicit_resolver`, `add_path_resolver`, `serialize`, `serialize_all`, `emit`, `parse`, `compose`, `scan`, `compose_all`, `full_load`, `unsafe_load`).
- **The app's own formats are correct as they stand.** The update feed is JSON and is read identically by the app, CI, and the test (`src/services/update_service.py:80`, `.github/workflows/app.yml:69-72`, `tests/test_version_sync.py:35-38`); the terminal resize payload is parsed exactly as its producer parses it (`src/screens/terminal_view.py:85` vs `.venv/Lib/site-packages/flet_terminal/mobile_terminal.py:113-117`); the container manifest is upstream's JSON and the app never re-implements the parse (`src/services/proot_service.py:194` → `proot_distro/paths.py:380-405` → `:340`); settings are a key-value store, not a file (`src/core/shared_services.py:28`, `src/app_controller.py:119,123,257,268,298,307`).
- **`proot_service.py` has no manifest handling of its own** — the study's "M3 `proot_service.py` reads upstream's on-disk `manifest.json` files (JSON)" (`pyyaml.md:71-72`) is directionally right but locates the read in the wrong file: the parse is `proot_distro/paths.py:340`, reached through `proot_service.py:194`. The service's only manifest-adjacent duties are the row projection (`:184-203`) and the backup/restore delegation (`:357-372`).
- **The payload wheel adds no YAML.** `build_flet_proot_wheel.py:400-411` — the generated `flet-proot` METADATA declares no `Requires-Dist` at all, so it cannot pull pyyaml into the runtime closure (it is added at `pyproject.toml:52` as `tool.flet.android.dependencies`).
- **No false alarm on `except TypeError, ValueError:`** at `src/services/update_service.py:63` — that is valid Python 3.14 (PEP 758, unparenthesized multiple exception types); `compile()` succeeds on this host's 3.14.7. Recorded so the synthesis does not re-open it.

## Unverified

- **Whether `pypi.flet.dev` (the house's Android extra index, referenced in `git show HEAD:docs/roadmap.md` §M3 tests) publishes an Android pyyaml wheel.** No network check was performed. This does not weaken F3: pyyaml is not a flet-family package, so that index is not its publisher, and upstream PyPI's own wheel list (`uv.lock:687-706`) contains no Android tag.
- **Whether the owner intends to revive the M3 certified catalog** (`git show HEAD:docs/roadmap.md:42, 86`; `git show HEAD:docs/compliance/distro-images.md` §4.1–4.2). The roadmap lists it under a milestone marked DONE and the feature is absent from `src/`; whether that means "dropped" or "deferred" is not stated anywhere in the tree. F1 and F3 assert only that the plan is not implemented and that it would be expensive as written.
- **`docs/roadmap.md` and `docs/compliance/*` are deleted in this working tree** (`git status --porcelain`) and were read from `HEAD` — a pre-existing environment artifact, not a repo defect (same note as `docs/swarm/dependency-utilization/cookiecutter.md:203`).
- **The bytes of a real `flet build apk` site-packages tree.** The *rule* that excludes the dev group is proven from source (`flet_cli/commands/build_base.py:2566-2577`); no Android build was run here, so the produced APK was not inspected. The CI prune greps (`.github/workflows/app.yml:166-172`, `:280-288`) were not exercised.
- **Whether `yaml.safe_dump`'s `sort_keys`/`allow_unicode` defaults match what the study's house rule assumes** for `safe_dump` specifically — the study's rule is stated as ours, not upstream's, and upstream's own write path uses `yaml.dump` (F6). The exact emitted text was not compared byte-for-byte.
