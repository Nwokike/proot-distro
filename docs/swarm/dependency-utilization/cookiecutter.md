# cookiecutter 2.7.1 utilization — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `docs/dependency-studies/cookiecutter.md`; `docs/reference/dep-cookiecutter-stack.md`; `docs/requests/mobile-forge-recipe-flet-proot/{README.md,build.sh,meta.yaml}`; `docs/swarm/BRIEF.md`; `pyproject.toml`; `uv.lock`; `.github/workflows/app.yml`; `build_flet_proot_wheel.py`; `tests/test_proot_surfaces.py`; `tests/test_imports_vs_deps.py`; `src/` (import scan); `.venv/Lib/site-packages/cookiecutter/` (17 files, read in full); `.venv/Lib/site-packages/flet_cli/commands/{build.py,build_base.py,create.py}`; `.venv/Lib/site-packages/flet_cli/utils/{template_cache.py,pyproject_toml.py,hash_stamp.py}`; `.venv/Lib/site-packages/flet/version.py`; `flet-build-template.zip` @ `v1.0.4` (272 entries, inspected) · **Date:** 2026-10-20

## What it does / how the app uses it

**cookiecutter is dev-only, transitively, and the repo never calls it.** It enters the environment through the dev group only:

`pyproject.toml:78-84` (dev group: `flet-cli>=1.0.4`) → `uv.lock:220-233` (flet-cli 1.0.4 → `{ name = "cookiecutter" }` at `uv.lock:226`) → `uv.lock:174-190` (cookiecutter 2.7.1 → arrow, binaryornot, click, jinja2, python-slugify, pyyaml, requests, rich).

The **runtime** closure never touches it: `pyproject.toml:9-15` lists only flet, flet-ads, httpx, flet-terminal, proot-distro; `uv.lock:193-201` (flet 1.0.4 → httpx, msgpack, oauthlib, repath) contains no cookiecutter edge. And the app's *packaged* dependency set is computed from `project.dependencies` + `tool.flet.<platform>.dependencies` only — `.venv/Lib/site-packages/flet_cli/commands/build_base.py:2566-2577` — so the dev group is never consulted when the APK's site-packages is built. cookiecutter (and jinja2, requests, arrow, pyyaml, rich) cannot reach the device. The repo already asserts this itself: `tests/test_proot_surfaces.py:133-148` fails if any `src/` file imports `cookiecutter`, `jinja2`, `requests`, `flet_cli`, `flet_desktop`, `binaryornot`, `chardet`, `pytest` or `ruff`.

**The only consumer is flet-cli, and it uses cookiecutter as a library** — never as a CLI: `flet_cli/commands/build_base.py:1893` (`from cookiecutter.main import cookiecutter`) and `flet_cli/commands/create.py:90`. The build path is:

```
flet build apk
  └─ flet_cli/commands/build.py:110   self.create_flutter_project()          # pass 1
       └─ flet_cli/commands/build_base.py:1856-1861  get_cached_template_zip(DEFAULT_TEMPLATE_URL, ref)
            └─ flet_cli/commands/build_base.py:1895-1905  cookiecutter(template=<local zip>, …)
                 └─ cookiecutter/main.py:29  →  cookiecutter/generate.py:327  →  build/flutter/
  └─ flet_cli/commands/build.py:111   self.package_python_app()               # installs flet-proot wheel
  └─ flet_cli/commands/build.py:113   self.create_flutter_project(second_pass=True)  # pass 2 (re-render)
  └─ flet_cli/commands/build.py:114-115  customize_icons() / customize_splash_images()
```

**The render is what produces the Android shell that carries our native payload.** The template's `pubspec.yaml` pins `flet: 1.0.4` and `serious_python: 5.0.0`; the serious_python Gradle plugin is what performs the `opt/**/*.so → jniLibs` copy that delivers `build_flet_proot_wheel.py`'s `opt/lib/libproot.so` into the APK (`docs/reference/dep-flet-cli.md:13`, `docs/requests/proot-mobile-forge-request.md:13`). The template's `android/app/build.gradle.kts` also renders `useLegacyPackaging = true` from `cookiecutter.options.android_legacy_packaging` and the ABI excludes from `cookiecutter.options.android_excluded_abis` — both driven by our `pyproject.toml`.

**No repo-owned code uses cookiecutter, and none of the repo's own scripts should** — see "Missed capabilities" below: the recommendation is **against** a second use.

## Findings

### F1 · P1 · The build template is fetched without integrity verification, and its code executes inside the CI job that holds the release signing key

- **Where:**
  - `.venv/Lib/site-packages/flet_cli/utils/template_cache.py:21-32` (`get_cached_template_zip` — *"caching is a simple 'use if present, else download once' — no revalidation"*), `:37-42` (download via `urllib.request.urlopen` → `.tmp` → `os.replace`; **no hash, no signature, no content check**).
  - `.venv/Lib/site-packages/flet_cli/commands/build_base.py:67-70` (`DEFAULT_TEMPLATE_URL = "https://github.com/flet-dev/flet/releases/download/v{version}/flet-build-template.zip"`), `:1856-1861` (the fetch), `:1895-1905` (the render — `accept_hooks` is **not** passed, so it keeps its default `True`, `cookiecutter/main.py:42`).
  - `.venv/Lib/site-packages/cookiecutter/environment.py:19-56` (`ExtensionLoaderMixin` loads `context['cookiecutter']['_extensions']` as importable module paths) + `.venv/Lib/site-packages/cookiecutter/main.py:203-212` (`_patch_import_path_for_repo` → `sys.path.append(self._repo_dir)`) → **the template's own Python module is imported and executed inside the build process**.
  - `.github/workflows/app.yml:143-146` (the *same job* decodes the release signing keystore from `secrets.KEYSTORE_BASE64`), `:151-161` (`flet build apk` runs there), `:26-27` (workflow-level `permissions: contents: write`).
- **What:** the *study* and the *reference doc* both name the wrong code-execution vector. `docs/dependency-studies/cookiecutter.md:480-490` and `docs/reference/dep-cookiecutter-stack.md:13` both say "template hooks execute". For the v1.0.4 template that is **false** — the zip has **no `hooks/` directory at all**. The live vector is different and stronger: the template's `cookiecutter.json` declares a **custom Jinja extension** that cookiecutter imports from the downloaded zip:
  ```
  _extensions: ['cookiecutter_extensions.FletExtension']
  ```
  `cookiecutter/environment.py:37-43` passes that dotted path to Jinja, and `cookiecutter/main.py:209` has already put the template directory on `sys.path` — so `build/cookiecutter_extensions.py` from the zip is imported and its module body executes in the build interpreter. (The extension itself is benign — it only registers a `get_pyproject()` Jinja global — but *the mechanism* is arbitrary code execution from an unverified download.) There is no checksum anywhere on that path: `template_cache.py:31-32` never revalidates a cached copy, and a warm `~/.flet/cache` is reused verbatim across builds.
- **Evidence:** (inspected `flet-build-template.zip` @ `v1.0.4`, 272 entries, read-only — no script was executed)
  ```
  $ python - <<'PY'   # zipfile only
  import zipfile, json
  z = zipfile.ZipFile('.git/fbt.zip'); names = z.namelist()
  print('entries:', len(names))
  print('entries containing "hook":', [n for n in names if 'hook' in n.lower()] or 'NONE')
  tpl = json.loads(z.read('build/cookiecutter.json').decode())
  print('_extensions:', tpl['_extensions'])
  PY
  entries: 272
  entries containing "hook": NONE
  _extensions: ['cookiecutter_extensions.FletExtension']
  ```
  and the import path that makes it executable:
  ```
  .venv/.../cookiecutter/main.py:207-209
      def __enter__(self) -> None:
          self._path = copy(sys.path)
          sys.path.append(self._repo_dir)
  .venv/.../cookiecutter/environment.py:37,40
          extensions = default_extensions + self._read_extensions(context)
          super().__init__(extensions=extensions, **kwargs)
  ```
- **Fix / opportunity:** pin the template by hash in CI, exactly as the study's own §4.4 mitigation 2 already prescribes (it was never implemented). Concretely, in `.github/workflows/app.yml` before the `flet build` steps: download `flet-build-template.zip` for `v1.0.4` once, verify it against a checked-in `sha256`, then pre-seed the cache path `<FLET_CACHE_DIR>/build-template/v1.0.4/flet-build-template.zip` with `FLET_CACHE_DIR` exported — `template_cache.py:31-32` then short-circuits the network entirely. Also drop `contents: write` from the workflow-level `permissions` (`app.yml:26-27`) and grant it per-job to the release job only, so a compromised template cannot push to the repo.
- **Risk if ignored:** a compromised (or re-uploaded) `flet-build-template.zip` release asset executes arbitrary code in the job that holds `KEYSTORE_BASE64`, `KEY_ALIAS`, `KEYSTORE_PASSWORD` and `KEY_PASSWORD` (`app.yml:144-146,154-157`) — i.e. the release signing key and every secret in the job, in a workflow that publishes signed APKs to a public GitHub Release (`app.yml:177-181`). The trust boundary is documented; the mitigation is not implemented.

### F2 · P2 · The rendered `minSdk`/`targetSdk` are delegated to the upstream template + Flutter defaults, and CI's Play gate asserts on exactly that delegated value

- **Where:**
  - Template (v1.0.4 zip) `build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts`:
    ```jinja
    {% set min_sdk_version = get_pyproject("tool.flet.android.min_sdk_version") %}
    {% set target_sdk_version = get_pyproject("tool.flet.android.target_sdk_version") %}
    …
    val resolvedMinSdk = {{ min_sdk_version if min_sdk_version else "flutter.minSdkVersion" }}
    minSdk = resolvedMinSdk
    val resolvedTargetSdk = {{ target_sdk_version if target_sdk_version else "flutter.targetSdkVersion" }}
    targetSdk = resolvedTargetSdk
    ```
    (the `get_pyproject` global is the template's own `cookiecutter_extensions.FletExtension`; the `pyproject` value it reads is the dict flet passes at `flet_cli/commands/build_base.py:1654` → `flet_cli/utils/pyproject_toml.py:22-26,40-41`).
  - `pyproject.toml:43-52` — `[tool.flet.android]` sets `bundle_id`, `split_per_abi`, `legacy_packaging`, `target_arch`, `dependencies` — **no `min_sdk_version`, no `target_sdk_version`**.
  - `grep -rn "min_sdk_version\|target_sdk_version\|targetSdk\|minSdk" .venv/Lib/site-packages/flet_cli/` → **0 hits**: flet-cli 1.0.4 has no CLI flag and no config key for either. The *only* way to set them is the pyproject key the template reads.
  - `.github/workflows/app.yml:233-240` — the Play gate: `target=$(… android:targetSdkVersion=…)`; `if [ -z "$target" ] || [ "$target" -lt 36 ]; then exit 1`.
  - `build_flet_proot_wheel.py:182-185` — our payload wheels are tagged `py3-none-android_24_*` (API 24 floor).
  - `.venv/Lib/site-packages/flet/version.py:29` — `flutter_version = "3.44.8"` (the SDK that supplies `flutter.targetSdkVersion` / `flutter.minSdkVersion`).
- **What:** the number CI asserts on is **not** owned by this repo. Because neither key is pinned, the render falls back to the Flutter SDK's defaults, which are set by whichever Flutter version flet 1.0.4 pins — a value that changes on a flet bump, not on a repo change. The same applies to `minSdk`, which has no CI gate at all yet bounds where our `android_24` wheel can be installed. Both values are decided *inside the cookiecutter render* (via the template's `get_pyproject` global), which is exactly the class of coupling this audit is about.
- **Evidence:** the template reads the repo's pyproject directly (grep over the zip's text entries):
  ```
  build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts: get_pyproject('tool.flet.android.min_sdk_version')
  build/{{cookiecutter.out_dir}}/android/app/build.gradle.kts: get_pyproject('tool.flet.android.target_sdk_version')
  build/{{cookiecutter.out_dir}}/lib/flet_generated.dart:      get_pyproject('tool.flet.app.hide_window_on_start')
  ```
  and flet-cli itself never mentions either key (0 grep hits across `flet_cli/`).
- **Fix / opportunity:** pin both in `pyproject.toml` under `[tool.flet.android]` — `target_sdk_version = 36` (the value the CI gate demands, `app.yml:237`) and `min_sdk_version = 24` (the floor our `android_24` wheel tag implies, `build_flet_proot_wheel.py:183`). The template picks them up verbatim on the next render, and the render becomes independent of the Flutter default. Two lines, no code change.
- **Risk if ignored:** a flet/Flutter bump that lowers the default target SDK fails the release **after** the full APK/AAB build (the gate is the last step of the `aab` job, `app.yml:237-240`) — a late, expensive failure. A lowered min SDK below 24 would let a device install the app but fail to install the `android_24` payload wheel, i.e. an APK that launches and then has no `libproot.so` — the app *is* the container engine, so that is a dead app, not a degraded one.

### F3 · P2 · The payload pin set is duplicated and has already drifted; the second copy also points at files that do not exist

- **Where:** `build_flet_proot_wheel.py:34-81` (`_PINNED_SOURCES` — proot **5.1.107.98**, sha256 `29de40ef…` aarch64 / `1c31ad7e…` x86_64) vs `docs/requests/mobile-forge-recipe-flet-proot/build.sh:32-40` (proot **5.1.107.96**, sha256 `8199dca0…` / `77ea4554…`) and `docs/requests/mobile-forge-recipe-flet-proot/meta.yaml:1-2` (`{% set version = "5.1.107.96" %}`).
- **What:** two hand-maintained copies of the same pins, already out of sync by one upstream version — exactly the failure mode a generator is supposed to prevent. The recipe's own README compounds it: `docs/requests/mobile-forge-recipe-flet-proot/README.md:36-37` declares the source of truth to be `tools/flet_proot_sources.json` and `tools/build_flet_proot_wheel.py`, **neither of which exists** (the builder is at the repo root, and the pins live inline in `_PINNED_SOURCES`; there is no `tools/` directory — `git ls-files` shows no such path).
- **Evidence:**
  ```
  $ grep -n "5.1.107" docs/requests/mobile-forge-recipe-flet-proot/build.sh docs/requests/mobile-forge-recipe-flet-proot/meta.yaml
  docs/requests/mobile-forge-recipe-flet-proot/meta.yaml:1:# {% set version = "5.1.107.96" %}
  docs/requests/mobile-forge-recipe-flet-proot/build.sh:35:        "ver": "5.1.107.96",

  $ grep -n '"version"' build_flet_proot_wheel.py | head -1
  40:            "version": "5.1.107.98",
  $ git ls-files | grep -c "^tools/"   # -> 0
  ```
- **Fix / opportunity:** one machine-readable pin file (`pinned_sources.json`) at the repo root, read by **both** `build_flet_proot_wheel.py` and the recipe's `build.sh` (the recipe already renders `meta.yaml` with Jinja on the forge side, `meta.yaml:1-2`). **This is explicitly not a cookiecutter job** — see "Missed capabilities": a cookiecutter template would add a *third* representation (a template tree + `cookiecutter.json`) plus a JSON-serializability constraint and a template code-execution surface, without removing the duplication. Also fix the README's `tools/…` paths.
- **Risk if ignored:** the mobile-forge recipe — the upstream path that would let `flet-proot` be consumed by *other* Flet apps — would build a payload with different bits than the one CI ships and tests, and would publish version `5.1.107.96` in its metadata. The recipe is still "prepared, not yet submitted" (`README.md:3`), so nothing user-visible ships today; the risk is a wrong submission.

### F4 · P3 · The render-invalidation hash covers the template's *identity*, never its *bytes* — and two CI jobs fetch it independently

- **Where:** `flet_cli/commands/build_base.py:1864-1865` (`hash.update(template_source)`; `hash.update(template_ref)` — the URL string and the ref, not the content), `:1871` (`hash.update(self.template_data)`), `:1889-1890` (`hash_changed` decides whether to re-render); `flet_cli/utils/hash_stamp.py:25-26` (`self._hash.update(str(data).encode())` — identity, not content); `flet_cli/utils/template_cache.py:31-32` (a cached zip is never revalidated); `.github/workflows/app.yml:151-161` (apk job) and `:205-215` (aab job) — two independent `flet build` runs, each with its own download, both `needs: [prepare-release]` (`app.yml:130,183`) so they run in parallel.
- **What:** if the release asset at `…/v1.0.4/flet-build-template.zip` is replaced (GitHub permits re-uploading a release asset under the same name), then: a developer with a warm cache keeps rendering the **old** bytes, while a fresh CI runner renders the **new** bytes — and neither detects the swap. The APK and the AAB published under the same release tag (`app.yml:37,177-181,296-303`) are not guaranteed to come from identical template bytes.
- **Evidence:** `build_base.py:1864-1865` hashes `template_source` (the URL) and `template_ref`; `hash_stamp.py:26` hashes `str(data)`; nothing in the chain hashes the zip. `template_cache.py:31-32` returns the cached path without reading the file.
- **Fix / opportunity:** the sha256 pin from F1 solves this too (one verified download, one verified asset). Optionally, publish the digest in the build log next to the existing status line (`build_base.py:1886-1890`) so the artifact provenance is recoverable.
- **Risk if ignored:** low on its own (requires an upstream asset swap) but it is the same root cause as F1 — both are fixed by one hash pin.

### F5 · P3 · `extra_context` must survive `json.dump`, and the whole `pyproject.toml` is passed as a dict — a TOML date-time would abort the build after the download

- **Where:** `flet_cli/commands/build_base.py:1654` (`"pyproject": self.get_pyproject()`) → `flet_cli/utils/pyproject_toml.py:22-26` (`tomllib.loads`) → `cookiecutter/main.py:181` (`dump(config_dict['replay_dir'], template_name, context)`) → `cookiecutter/replay.py:26-37` (`json.dump(context, outfile, indent=2)`).
- **What:** `tomllib` turns TOML date-times into `datetime` objects, which `json.dump` cannot serialize → `TypeError` at dump time — *after* the template zip was fetched and unzipped, *before* any file is written. Our `pyproject.toml` has no date-time values today, so there is **no current breakage**; this is a latent constraint of the "pass the whole pyproject" shortcut. The same `pyproject` value is also what the template's `FletExtension.get_pyproject` consumes, and that extension requires a **dict** (`d = d.get(k)`) — so the dict form is load-bearing, not incidental.
- **Evidence:** `cookiecutter/replay.py:34-37`:
  ```python
  with open(replay_file, 'w', encoding="utf-8") as outfile:
      json.dump(context, outfile, indent=2)
  ```
  and the template extension:
  ```python
  d = pyproject
  for k in setting.split("."):
      d = d.get(k)
      if d is None: return None
  ```
- **Fix / opportunity:** none required now. If the house ever wants a "no TOML datetimes in `pyproject.toml`" rule, note that `flet-cli` itself would hit the same wall (it passes the same dict to cookiecutter), so the constraint is upstream, not ours.
- **Risk if ignored:** a future `pyproject.toml` timestamp turns into a confusing `TypeError: Object of type datetime is not JSON serializable` in the middle of a release build.

### F6 · P3 · The APK/AAB "no development files" prune check does not name any of the build-host packages

- **Where:** `.github/workflows/app.yml:163-172` (apk prune grep: `pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/`) and `:275-288` (aab equivalent); the packaged dependency set is proven at `flet_cli/commands/build_base.py:2566-2577`; the dev-only edges are at `uv.lock:220-233` and `uv.lock:174-190`.
- **What:** the exclusion of cookiecutter/jinja2/requests from the APK is **structural** (flet-cli is dev-group-only, and the packager only reads `project.dependencies` + `tool.flet.<platform>.dependencies`) — so the risk is already closed. But the CI's own belt-and-braces grep names none of the build-host stack, so if someone ever added `flet-cli` to `[project].dependencies` the prune step would pass silently.
- **Fix / opportunity:** extend the grep in both places to `pytest/|ruff/|uvicorn/|starlette/|fastapi/|docs/|cookiecutter/|jinja2/|requests/|flet_cli/`. One regex change per step; it converts a structural guarantee into an asserted one.
- **Risk if ignored:** low today; the check exists precisely to catch a regression nobody has made yet, and it currently covers only half of the build-host stack.

### F7 · P3 · The prior study's `main.py` anchors are wrong by ~17 lines, and its hook claim is not true of the v1.0.4 template

- **Where:** `docs/dependency-studies/cookiecutter.md:79` (`cookiecutter._output_dir = abspath(output_dir)` → "(`main.py:152`)" — installed: `main.py:173`), `:88` ("`main.py:167-201`" — installed: `183-201`), `:95` ("unconditional `replay.dump` (`main.py:164`)" — installed: `main.py:181`; and "`main.py:113-162`" — installed: `169-179`), `:531-534` and `docs/reference/dep-cookiecutter-stack.md:13` ("Hooks (`pre/post_gen`) execute template code at build time" — the v1.0.4 template has no `hooks/` dir, see F1).
- **What:** the study's other anchors are exact (signature `main.py:29-44`, `generate.py:59-124`, `generate.py:126-173`, `generate.py:175-260`, `generate.py:263-297`, `generate.py:327-466`, `replay.py:26-37`, `hooks.py:80-105`, `find.py:18-38`, `config.py:28-33`, `environment.py:59-71`, `utils.py:102-106`; and every file's line count matches the study). The drift is confined to the `main.py:100-201` region, where the study's anchors are systematically ~17 lines early — the region where the context is assembled and dumped.
- **Evidence:** `awk 'NR>=160 && NR<=185' .venv/.../cookiecutter/main.py` → `:164 prompt_for_config(context_for_prompting, no_input)`, `:169 # include template dir or url in the context dict`, `:173 context['cookiecutter']['_output_dir'] = os.path.abspath(output_dir)`, `:181 dump(config_dict['replay_dir'], template_name, context)`.
- **Fix / opportunity:** correct the four anchors and the hook claim in the study / reference doc. (Not modified by this audit — read-only outside this report.)
- **Risk if ignored:** the synthesis cites a wrong line for the JSON-serializability constraint, and repeats a hook claim that would misdirect a CI-hardening decision toward a mechanism that is inactive in the current template while the *active* mechanism (custom `_extensions`) goes unmentioned.

## Missed capabilities (dependency audits only)

**Verdict: recommend against a second, repo-owned use of cookiecutter.** The capability exists and works, but adopting it would not remove real code — and the brief's own bar ("using capabilities we already ship instead of hand-rolling them") is not met.

| Candidate | What it would replace | Cost | Verdict |
|---|---|---|---|
| Cookiecutter-ise the wheel builder (`build_flet_proot_wheel.py:378-385`, the 8-line `manifest` f-string) | 8 lines of f-string | a template tree + `cookiecutter.json` + a JSON-serializable context + a new code-exec surface | **No** — strictly more code, and the script's own contract is "One self-contained file… Stdlib only" (`build_flet_proot_wheel.py:1-5`) |
| Per-distro script templates (study §4.1) | nothing — the repo generates **no** per-distro files | — | **No** — `src/` writes no files at all (the only write is a temp dir, `src/core/proot_probe.py:41`); the install scripts live inside the `proot_distro` PyPI package, and `grep -rl "cookiecutter\|jinja\|template" .venv/.../proot_distro/` → 0 hits |
| CI/scaffold templates for the workflow | nothing — `.github/workflows/app.yml` is consumed by GitHub, not by a renderer | — | **No** |
| A single generated pin set (F3) | the duplicated `SOURCES` in the mobile-forge recipe | — | **Yes, but as JSON, not cookiecutter** — the study's §4.1 idea is sound; the tool is not. A JSON file read by both the builder and the recipe removes the duplication with ~30 lines, versus a template tree + context + trust boundary |

**Why a second use is the wrong trade here, concretely:**

1. *No N-variant generation to do.* The repo has one app (`pyproject.toml:30-31`, `[tool.flet.app] path = "src"`), one wheel builder, and three host CLIs (`build_flet_proot_wheel.py`, `check_elf_alignment.py`, `generate_third_party_sources.py`). There is no "template with variants" to extract — cookiecutter's value is amortising a template across many instantiations.
2. *flet-cli already owns the cookiecutter surface.* `flet_cli/commands/build_base.py:1895-1905` and `flet_cli/commands/create.py:134-142` already exercise every mechanic (template cache, `extra_context`, `overwrite_if_exists`, `no_input`). A second consumer would duplicate the trust-boundary reasoning, not share it.
3. *It adds a code-execution surface to a repo that currently has none.* A repo-owned template would need `_extensions`/hooks discipline that today is entirely upstream's problem (F1); a `hooks/` dir in this repo would run with CI's privileges and secrets (`app.yml:144-146`).
4. *It adds a JSON-serializability constraint* to a stdlib-only script (F5) for no gain.

The one pattern worth borrowing from cookiecutter is the *idea* of a declarative single source of truth expanded into generated artifacts — applied to the pin set (F3) with a plain JSON file.

## Verified-good list

- **Dev-only, provably.** cookiecutter 2.7.1 is installed (`.venv/Scripts/python.exe -c "import cookiecutter; print(cookiecutter.__version__)"` → `2.7.1`) and is reachable only through the dev group (`pyproject.toml:79` → `uv.lock:226` → `uv.lock:174-190`); the runtime closure has no edge to it (`uv.lock:193-201`), and the packaged app dep set is `project.dependencies` + `tool.flet.<platform>.dependencies` only (`flet_cli/commands/build_base.py:2566-2577`). It cannot ship to Android. The repo's own guard is `tests/test_proot_surfaces.py:133-148`.
- **The app never imports it.** `grep -rn "cookiecutter\|jinja" src/` → 0 hits; `src/` imports no templating library at all.
- **`build_flet_proot_wheel.py` correctly stays stdlib-only** (`:1-5` docstring; imports at `:10-21` are all stdlib) and correctly does **not** use cookiecutter: it produces a wheel, not a project tree, and its own sha256 pinning (`:202-210`) is the stronger, simpler mechanism.
- **The "silently ignored unknown key" trap does not bite today.** Verified against the actual v1.0.4 template zip: all **41** effective top-level `template_data` keys flet sends (37 literals at `build_base.py:1521-1654` + the 4 `**`-unpacked web-runtime keys at `:1573`) exist in the template's `cookiecutter.json`; only 4 template keys fall back to template defaults — `org_name_2`, `package_name`, `kotlin_dir` (all Jinja-derived from `bundle_id`) and `use_color_emoji` (`False`). The silent-ignore branch is `cookiecutter/generate.py:66-74`.
- **The template's `get_pyproject` global resolves against our pyproject safely.** `flet_generated.dart` reads `tool.flet.app.hide_window_on_start` (unset → `None` → `bool.tryParse("none") ?? false` → `false`); the extension returns `None` on the first missing segment instead of raising (`cookiecutter_extensions.py`, `d.get(k)` then `if d is None: return None`).
- **The render fails closed and loudly.** Any cookiecutter exception → `rmtree(self.flutter_dir)` + `cleanup(1, f"{e}")` (`build_base.py:1906-1908`) — no half-rendered shell is ever packaged, and `StrictUndefined` (`cookiecutter/environment.py:59-71`) turns a missing context key into a build error rather than a half-rendered `AndroidManifest.xml`.
- **`overwrite_if_exists=True` is an in-place overlay, not a clean re-render** — `cookiecutter/generate.py:287-293` does not delete the target dir; only `_copy_without_render` dirs are removed first (`generate.py:416-418`) and the v1.0.4 template sets no `_copy_without_render` (verified: `null`). flet's ordering is correct and load-bearing: the second render (`build.py:113`) happens *before* `customize_icons()` / `customize_splash_images()` (`build.py:114-115`), which is why the comment at `build_base.py:1874-1878` ("a re-render restores the template's placeholder assets over generated ones") holds.
- **The template is the declared source of the Android namespace.** `applicationId`/`namespace` render to `{{ cookiecutter.org_name_2 }}.{{ cookiecutter.package_name }}` = `ng.kiri` + `prootdistro` = `ng.kiri.prootdistro`, matching `pyproject.toml:44`; the Kotlin source dir `src/main/kotlin/{{ cookiecutter.kotlin_dir }}/` resolves via `org_name_2` + `package_name` + `sep` (the build host's `os.sep`, `build_base.py:1523`) — correct on the Linux CI runner.
- **The rendered gradle honours our pyproject.** `useLegacyPackaging = true` is rendered from `cookiecutter.options.android_legacy_packaging` (our `pyproject.toml:48` `legacy_packaging = true`), which is exactly what `pyproject.toml:46-47` says the payload needs ("Native libs must extract from the APK (SELinux allows execve only from nativeLibraryDir)"); `split_per_abi = true` (`pyproject.toml:45`) suppresses the template's `abiFilters` block.
- **The template pins the Flutter runtime the payload depends on**: `pubspec.yaml` declares `flet: 1.0.4` and `serious_python: 5.0.0`; serious_python is the component that performs the `opt/**/*.so → jniLibs` copy that delivers `build_flet_proot_wheel.py`'s payload (`docs/reference/dep-flet-cli.md:13`).

## Unverified

- The **sha256 of the v1.0.4 release asset** and whether upstream publishes a checksum/Sigstore attestation for `flet-build-template.zip` (no upstream contact; the asset was fetched once for this audit and never checksum-verified).
- The **actual rendered `minSdk`/`targetSdk` values** (F2) — requires a Gradle build against Flutter 3.44.8 (`flet/version.py:29`); not run here. The *fallback path* is proven from the template source; the *resulting number* is not.
- Whether GitHub **permits replacing a release asset** under the same URL (assumed possible in F4; not tested).
- The **APK/AAB bytes** produced by the repo's CI — no CI run was observed; the template inspection used the published v1.0.4 asset only.
- The `flet create` **app** template (a different zip, `DEFAULT_APP_TEMPLATE_URL`) was not inspected; only the build template was.
- The mobile-forge recipe's `build.sh` conventions remain **UNVERIFIED against the forge environment** — that is the recipe's own stated status (`docs/requests/mobile-forge-recipe-flet-proot/README.md:15`) and is unchanged by this audit.
- **Working-tree note (not a repo defect):** `LICENSES/*`, `check_elf_alignment.py` and `generate_third_party_sources.py` are shown deleted in `git status` but are present at `HEAD` (`git show HEAD:check_elf_alignment.py` → the file's shebang). This is a pre-existing artifact of the audit environment; `app.yml:175,291,294` reference the HEAD versions, so the workflow is intact. Do not report it as a missing-file bug.
