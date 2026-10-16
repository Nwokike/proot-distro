# flet-cli 1.0.4 — exhaustive API reference

> Companion to `docs/reference/dep-flet-cli.md` (summary). This file is the exhaustive,
> source-quoted companion. Every claim cites the installed source
> (`.venv/Lib/site-packages/flet_cli/...`); anything not established in source is
> labeled **unverified**. flet stays 1.0.4 per D-010. Verified 2026-10-16.

## 0. How to read this file

* `CLI:` = `flet_cli/cli.py`; `BB:` = `flet_cli/commands/build_base.py`;
  `B:` = `flet_cli/commands/build.py`; `FB:` = `flet_cli/commands/flutter_base.py`.
* `dest`/`default` are quoted verbatim from `add_argument()` calls.
* Precedence rule (global): **CLI flag > `[tool.flet.<config_platform>]` > `[tool.flet]` > built-in default** —
  implemented by `get_bool_setting()` (`BB:2905`) and `get_platform_setting()` (`BB:2925`),
  which checks `tool.flet.{config_platform}.{key}` then `tool.flet.{key}` (`BB:2936-2946`).
  Platform-scoped empty `[]`/`{}` wins over (clears) the global value (`BB:2925-2944` docstring).

---

## 1. Identity

| Item | Value | Source |
|---|---|---|
| Package / version | `flet-cli 1.0.4` | `flet_cli/version.py:1` (`version = "1.0.4"`); `flet_cli-1.0.4.dist-info/METADATA:3` |
| Pinned Flutter | `3.44.8` | `.venv/Lib/site-packages/flet/version.py:29` (`flutter_version = "3.44.8"`) |
| Pinned flet | `flet==1.0.4` (exact) | `flet_cli-1.0.4.dist-info/METADATA:12` (`Requires-Dist: flet==1.0.4`) |
| Runtime deps | `flet==1.0.4`, `flet-platform-assets==1.0.4`, `watchdog>=4.0.0`, `packaging>=25.0`, `qrcode>=7.4.2`, `tomli>=1.1.0; python_version < "3.11"`, `cookiecutter>=2.6.0`, `binaryornot<0.5`, `chardet<6`, `rich>=13.0.0` (+ `flet-mcp` under `extra == "mcp"`) | `METADATA:12-23` |
| `Requires-Python` | `>=3.10` | `METADATA:10` |
| License | `Apache-2.0` | `METADATA:6` (`License-Expression: Apache-2.0`) |
| Console script | `flet` → `.venv/Scripts/flet.exe` exists; **unverified**: `flet_cli-1.0.4.dist-info/entry_points.txt` contains only a `[pyinstaller40] hook-dirs` stanza, so the `flet` entry-point declaration lives outside this dist-info (presumably the `flet` package or build backend) — not established in installed source | `entry_points.txt` (whole file); `Scripts/flet.exe` observed on disk |
| `flet --version` text | `Flet: {flet_version}\nFlutter: {flutter_version}` | `CLI:37-41` (`_render_version`) |
| `flet --version --json` keys | `{"flet", "flutter", "linux_dependencies"}` | `CLI:20-35` (`_version_info`) |
| Module layout | `cli.py` (parser+dispatch), `version.py`, `commands/{base,options,build,build_base,flutter_base,run,create,pack,publish,debug,test,test_host,devices,emulators,doctor,clean,serve,mcp}.py`, `utils/{pyproject_toml,project_dependencies,template_cache,python_versions,android,flutter,merge,processes,cli,app_excludes,plist,hash_stamp,android_sdk,jdk,ios_sign,macos_sign,linux_deps,distros,pyodide}.py`, `__pyinstaller/` (PyInstaller hooks) | directory listing of installed `flet_cli` |

---

## 2. Complete CLI surface

Global parser (`CLI:117` `get_parser()`; dispatch `CLI:264` `main()`; arg-splitting `CLI:193` `parse_command_line()` + `CLI:158` `split_script_args()`):

| Flag | dest | Default | Semantics |
|---|---|---|---|
| `--version`, `-V` | `version` | `False` (`store_true`, `CLI:126`) | Print version and `sys.exit(0)` when set (`CLI:272-275`) |
| `--json` | `json` | `False` (`store_true`, `CLI:132`) | With `--version`: JSON doc instead of text (`CLI:37-40`) |
| `-v`, `--verbose` | `verbose` | `0` (`action="count"`, `commands/options.py:verbose_option`) | `-v` = verbose, `-vv` = more detail; controls log streaming vs capture (`FB:455`ff, `BB:2832`) |
| bare `--` separator | n/a | n/a | Everything after first bare `--` is stripped before parsing and forwarded: `run`→`script_args`, `test`→`pytest_args`, `build`/`debug`→`flutter_build_args`, `pack`→`pyinstaller_build_args`; any other command + `--` = parse error (`CLI:158-191`, `CLI:239-261`) |
| no args at all | n/a | n/a | Print help to stdout, `sys.exit(1)` (`CLI:264-268`) |
| default subcommand | `command` | `"run"` | `run` is prepended when no subcommand name present (`CLI:96-115` `set_default_subparser`, called at `CLI:230`) |

Subcommands registered (`CLI:141-152`, `CLI:160`): `create`, `run`, `build`, `clean`,
`debug`, `test`, `pack`, `publish`, `serve`, `emulators`, `devices`, `doctor`,
`mcp` (only if `flet_mcp` importable, `CLI:155-161`).

Shared Flutter-command flags (`FB:82-110`, inherited by `build/debug/test/devices/emulators`):

| Flag | dest | Default | Semantics |
|---|---|---|---|
| `--no-rich-output` | `no_rich_output` (`store_true`) | `False` (`FB:90-96`) | Plain output; also honored via `sys.argv` scan + `FLET_CLI_NO_RICH_OUTPUT` before argparse exists (`FB:24-31`) |
| `--yes` | `assume_yes` (`store_true`) | `False` (`FB:97-104`) | Answer yes to installs/prompts (Flutter, SDK, JDK) |
| `--skip-flutter-doctor` | `skip_flutter_doctor` (`store_true`) | `False` (`FB:105-111`) | Skip `flutter doctor` after failed builds; also via env (`FB:66`) |

### 2.1 `flet build` — targets

`B:62-76`: positional `target_platform` (`type=str.lower`), choices exactly
`macos | linux | windows | web | apk | aab | ipa | ios-simulator`.
`-o/--output` → `dest=output_dir`, not required; default `<python_app_path>/build/<target_platform>` (`B:77-84`, resolved `BB:917-935`).
Args after `--` → extra `flutter build` args (`B:docstring`, `BB:3094-3105`).

Platform matrix (`BB:157-225`):

| Target | `flutter_build_command` | `package_platform` / `config_platform` | Outputs glob | Buildable on (`can_be_run_on`) |
|---|---|---|---|---|
| `windows` | `windows` | `Windows` / `windows` | `build/windows/{arch}/runner/Release/*` | `Windows` |
| `macos` | `macos` | `Darwin` / `macos` | `build/macos/Build/Products/Release/{artifact_name}.app` | `Darwin` |
| `linux` | `linux` | `Linux` / `linux` | `build/linux/{arch}/release/bundle/*` | `Linux` |
| `web` | `web` | `Emscripten` / `web` | `build/web/*` | `Darwin`, `Windows`, `Linux` |
| `apk` | `apk` | `Android` / `android` | `build/app/outputs/flutter-apk/*` | `Darwin`, `Windows`, `Linux` |
| `aab` | `appbundle` | `Android` / `android` | `build/app/outputs/bundle/release/*` | `Darwin`, `Windows`, `Linux` |
| `ipa` | `ipa` | `iOS` / `ios` | `build/ios/archive/*`, `build/ios/ipa/*` | `Darwin` |
| `ios-simulator` | `ios` (+`--simulator`) | `iOS` / `ios` | `build/ios/iphonesimulator/*` | `Darwin` |

Wrong host or `--show-platform-matrix` prints the matrix table and exits 1 (`BB:956-990`).

`flutter build` arg derivation (`B:150-213`): `build <flutter_build_command>`;
`apk`+`split_per_abi` → `--split-per-abi`; `apk`/`aab`+`target_arch` →
`--target-platform <android-arm,...>` via `flutter_target_platforms()` mapping
`armeabi-v7a→android-arm, arm64-v8a→android-arm64, x86_64→android-x64`
(`utils/android.py:5-9`; unknown ABI raises `ValueError`); `ipa`+profile →
`--export-options-plist ios/exportOptions.plist` else `--no-codesign`;
`ios-simulator` → `--simulator`; `--build-number/--build-name` from
`--build-number` / `tool.flet.build_number` and `--build-version` /
`project.version` / `tool.poetry.version`; plus `flutter.build_args` entries;
always `--no-version-check --suppress-analytics`; `--verbose` iff `-vv`;
web + wasm-eligible → `--wasm` (see §3).

### 2.2 `flet build` / `flet debug` / `flet test` — shared build options (`BB:330-869`)

Positional `python_app_path` (`nargs="?"`, default `"."`, `BB:338-344`).
Every row: CLI flag → `dest`, action/default, scope note from its help text.

| Flag | dest / default | Scope / semantics |
|---|---|---|
| `--arch` | `target_arch`, `extend`+`nargs="+"`, default `[]` (`BB:345-355`) | macOS+Android only. Android values `arm64-v8a, armeabi-v7a, x86_64`; macOS `arm64, x86_64` |
| `--exclude` | `exclude`, `extend`/`nargs="+"`, `[]` | Extra app paths to exclude from packaging; repeatable |
| `--include` | `include`, `extend`/`nargs="+"`, `[]` | Rescue paths from default excludes (e.g. `.env`); repeatable |
| `--no-default-excludes` | `default_excludes`, `store_false`, default `None` (`BB:374-381`) | `None`=fall through to config; `False`=package hidden files, venvs, `__pycache__` |
| `--project` | `project_name`, no default | Bundle-ID/identifier stem; default for artifact/product names |
| `--artifact` | `artifact_name` | On-disk executable/bundle name |
| `--description` | `description` | Short app description |
| `--product` | `product_name` | Display name in launchers/titles/dialogs |
| `--org` | `org_name` | Reverse-DNS org, e.g. `com.mycompany` |
| `--bundle-id` | `bundle_id` | Used as iOS+Android+macOS+Linux bundle ID |
| `--company` / `--copyright` | `company_name` / `copyright` | About-dialog metadata |
| `--android-adaptive-icon-background` | `android_adaptive_icon_background` | Fill color for Android adaptive icons |
| `--linux-categories` | `linux_categories`, `extend`/`nargs="+"`, `[]` | freedesktop categories, linux only; repeatable |
| `--splash-color` / `--splash-dark-color` | `splash_color` / `splash_dark_color` | Splash background (light/dark) on iOS+Android+web |
| `--no-web-splash` / `--no-ios-splash` / `--no-android-splash` | `no_web_splash` etc., `store_true`, default `None` | Disable splash per platform (`None`=fall through to config) |
| `--ios-team-id` | `ios_team_id` (str) | Apple team ID (ipa only) |
| `--ios-export-method` | `ios_export_method` | Export method (default `debugging`); validated against `tool.flet.ios.export_methods` map (`BB:1448-1454`) |
| `--ios-provisioning-profile` | `ios_provisioning_profile` | Profile name or UUID (ipa) |
| `--ios-signing-certificate` | `ios_signing_certificate` | Cert name / SHA-1 / auto selector (ipa) |
| `--base-url` | `base_url` | Base URL the app is served from (web only) |
| `--web-renderer` | `web_renderer`, `str.lower`, choices `auto\|canvaskit\|skwasm` | Web only; default `canvaskit`; `[env: FLET_WEB_RENDERER=]` (`BB:516-529`) |
| `--route-url-strategy` | `route_url_strategy`, `str.lower`, choices `path\|hash` | Web only; `[env: FLET_WEB_ROUTE_URL_STRATEGY=]` |
| `--pwa-background-color` / `--pwa-theme-color` / `--pwa-short-name` | `pwa_*` | Web only; short-name defaults to product name |
| `--no-wasm` | `no_wasm`, `store_true`, default `False` | Web only; disable WASM target |
| `--no-cdn` | `no_cdn`, `store_true`, default `False` | Bundle CanvasKit+Pyodide+fonts; `[env: FLET_WEB_NO_CDN=]`; config mirror `tool.flet.web.cdn == false` (`BB:2875-2885`) |
| `--split-per-abi` | `split_per_abi`, `store_true`, default `None` | Android only; `None`=fall through to config |
| `--android-legacy-packaging` | `android_legacy_packaging`, `BooleanOptionalAction`, default `None` | Android only; `--[no-]android-legacy-packaging`; extract `.so` at install vs mmap from APK |
| `--compile-app` / `--compile-packages` | `compile_app` / `compile_packages`, `BooleanOptionalAction`, default `None` | Append `--compile-app/--compile-packages` to `serious_python package` when true; default on (`True`) when neither CLI nor config set (`BB:2744-2753`) |
| `--swift-package-manager` | `swift_package_manager`, `BooleanOptionalAction`, default `None` | iOS/macOS: SPM (default, Flutter 3.44+) vs CocoaPods; `--no-swift-package-manager` forces pods |
| `--cleanup-app` / `--cleanup-packages` | `cleanup_app` / `cleanup_packages`, `store_true`, default `None` | Strip junk globs on packaging (packages default on, app default off; specifying `*_files` forces the bool true, `BB:2755-2794`) |
| `--cleanup-app-files` / `--cleanup-package-files` | `cleanup_app_files` / `cleanup_package_files`, `extend`/`nargs="+"`, no default | Glob lists; comma-string also accepted and split (`BB:2770-2791`) |
| `--flutter-build-args` | `flutter_build_args`, `PassThroughArgsAction`, `nargs="*"` (`BB:639-649`) | Extra `flutter build` args; `-x` values must be `=`-attached or placed after `--` |
| `--source-packages` | `source_packages`, `extend`/`nargs="+"`, default `[]` | Packages to install from source dists → `SERIOUS_PYTHON_ALLOW_SOURCE_DISTRIBUTIONS` csv (`BB:2715-2723`) |
| `--android-extract-packages` | `android_extract_packages`, `extend`/`nargs="+"`, default `[]` | Android only; ship listed packages extracted to disk (merged over `ANDROID_DEFAULT_EXTRACT_PACKAGES`, currently `[]`, `BB:73-82`, `BB:2736-2742`) |
| `--python-version` | `python_version` (str), default `None` | Bundled Python short version (e.g. `3.13`); else `requires-python` else manifest default (`utils/python_versions.py:resolve_python_version`) |
| `--info-plist` | `info_plist`, `extend`/`nargs="+"`, `[]` | `<key>=<value>` pairs into Info.plist (macos/ipa/ios-simulator); values parse as bool/str/number/TOML array/inline-table; invalid → exit 1 (`BB:1176-1190`) |
| `--macos-entitlements` | `macos_entitlements`, `extend`/`nargs="+"`, `[]` | `<key>=<value>` entitlements (macos); invalid → exit 1 |
| `--android-features` | `android_features`, `extend`/`nargs="+"`, `[]` | `<feature>=true\|false` → AndroidManifest (android); invalid → exit 1 |
| `--android-permissions` | `android_permissions`, `extend`/`nargs="+"`, `[]` | `<permission>=true\|false` → AndroidManifest (android); invalid → exit 1 |
| `--android-meta-data` | `android_meta_data`, `extend`/`nargs="+"`, `[]` | `<name>=<value>` app meta-data → AndroidManifest (android); invalid → exit 1 |
| `--permissions` | `permissions`, `str.lower`+`extend`/`nargs="+"`, default `[]`, choices `location\|camera\|microphone\|photo_library` (`BB:731-741`) | Cross-platform permission bundles (see `BB:228-328` expansion tables) |
| `--deep-linking-scheme` / `--deep-linking-host` | `deep_linking_scheme` / `deep_linking_host` | iOS+Android deep-link config |
| `--android-signing-key-store` | `android_signing_key_store` | Upload `.jks` path; `[env: FLET_ANDROID_SIGNING_KEY_STORE=]` |
| `--android-signing-key-store-password` | `android_signing_key_store_password` | `[env: FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD=]` |
| `--android-signing-key-password` | `android_signing_key_password` | `[env: FLET_ANDROID_SIGNING_KEY_PASSWORD=]` |
| `--android-signing-key-alias` | `android_signing_key_alias`, default `None` | `[env: FLET_ANDROID_SIGNING_KEY_ALIAS=]`; effective default `upload` when a keystore is set (`BB:3082-3091`) |
| `--macos-signing-identity` | `macos_signing_identity` | macOS only; cert name/SHA-1/`-` ad-hoc; `[env: FLET_MACOS_SIGNING_IDENTITY=]` |
| `--macos-distribution` | `macos_distribution`, `str.lower`, choices `none\|developer-id\|app-store` | macOS signing/packaging channel; default `none` (sign only if identity configured) |
| `--macos-notary-profile` | `macos_notary_profile` | macOS only; or `APPLE_API_KEY*` env trio; `[env: FLET_MACOS_NOTARY_PROFILE=]` |
| `--macos-provisioning-profile` | `macos_provisioning_profile` | macOS App-Store `.provisionprofile` path; `[env: FLET_MACOS_PROVISIONING_PROFILE=]` |
| `--macos-installer-identity` | `macos_installer_identity` | macOS `.pkg` signer; `[env: FLET_MACOS_INSTALLER_IDENTITY=]` |
| `--build-number` | `build_number` (`type=int`) | Internal version number → `flutter build --build-number` |
| `--build-version` | `build_version` | `x.y.z` user version → `flutter build --build-name` |
| `--module-name` | `module_name` | Entry module (default `main`, `BB:1007-1012`) |
| `--template` / `--template-dir` / `--template-ref` | `template` / `template_dir` / `template_ref` (str) | Flutter bootstrap template: dir/URL (`--template`), subdir (`--template-dir`), git ref (`--template-ref`) |
| `--show-platform-matrix` | `show_platform_matrix`, `store_true`, default `False` | Print matrix table, exit |

### 2.3 Other commands

**`flet run`** (`commands/run.py:75-198`; default subcommand): positionals
`script` (default `"."`) + `script_args` (`nargs="*"`, default `[]`, `metavar="args"`);
`-p/--port` (`dest=port`, int, default `None` = random); `--host` (default `None`);
`--name` (`dest=app_name`, default `None`); `-m/--module` (`store_true`, `False`);
`-d/--directory` (`store_true`, `False`, watch script dir); `-r/--recursive`
(`store_true`, `False`); `-n/--hidden` (`store_true`, `False`); `-w/--web`
(`store_true`, `False`, serve + open browser); `--ios`/`--android` (`store_true`,
`False`, launch on device); `-a/--assets` (`dest=assets_dir`, default
`DEFAULT_ASSETS_DIR` from `flet.app`); `--ignore-dirs` (comma string, default `None`).
Runtime env exported to the child (`run.py:463-499`): `FLET_FORCE_WEB_SERVER`,
`FLET_SERVER_PORT/IP`, `FLET_WEB_APP_PATH`, `FLET_SERVER_UDS_PATH`,
`FLET_ASSETS_DIR`, `FLET_DISPLAY_URL_PREFIX`, `FLET_LOG_LEVEL`
(`debug` iff `-vv`), `FLET_APP_STORAGE_{DATA,CACHE,TEMP}`.

**`flet create`** (`commands/create.py:41-80`): positional `output_directory`
(default `"."`); `--project-name`; `--description`;
`--template` (`str.lower`, choices `app|extension`, default `"app"`);
`--template-ref` (git ref of `flet-app-templates`; defaults to flet version).
Template-data keys for the *app* scaffold: `template_name, flet_version, sep,
platform, out_dir, project_name, description?` (`create.py:96-118`); rendered via
`cookiecutter(..., no_input=True, overwrite_if_exists=True)`.

**`flet pack`** (`commands/pack.py:37-171`, PyInstaller for desktop): positional
`script` (required); `-i/--icon`; `-n/--name`; `-D/--onedir` (`store_true`, `False`,
Windows one-folder); `--distpath` (default `"dist"`); `--add-data` / `--add-binary` /
`--hidden-import` (`append`+`nargs="*"`, `source:destination[:platform]` shapes);
`--product-name`, `--file-description`, `--product-version`, `--file-version`
(`n.n.n.n`, Windows), `--company-name`, `--copyright`, `--codesign-identity`
(macOS), `--bundle-id` (macOS bundle id; on Linux the taskbar/`StartupWMClass`
identity, defaults to exe name); `--debug-console`; `--uac-admin` (`store_true`,
`False`, Windows UAC manifest); `--pyinstaller-build-args`
(`PassThroughArgsAction`, `=`-attach dash args or use `--`); `-y/--yes`
(`dest=non_interactive`, `store_true`, `False`).

**`flet publish`** (`commands/publish.py:43-155`, static web via Pyodide/micropip):
positional `script` (default `"."`); `--pre` (`store_true`, `False`, micropip
pre-releases — unrelated to `--python-version`); `--python-version` (str, default
`None`); `-a/--assets` (`dest=assets_dir`, default `None`, `[env: FLET_ASSETS_DIR=]`);
`--distpath` (default `"dist"`); `--app-name`, `--app-short-name`,
`--app-description`, `--base-url`; `--web-renderer` (choices
`auto|canvaskit|skwasm`, default `None`→`canvaskit`, `[env: FLET_WEB_RENDERER=]`);
`--route-url-strategy` (choices `path|hash`, default path,
`[env: FLET_WEB_ROUTE_URL_STRATEGY=]`); `--pwa-background-color`,
`--pwa-theme-color`; `--no-cdn` (`store_true`, `False`,
`[env: FLET_WEB_NO_CDN=]`).

**`flet debug`** (`commands/debug.py:42-76` + all `BB` args): positional `platform`
(`nargs="?"`, choices `macos|linux|windows|web|ios|android`); `--device-id/-d`;
`--show-devices` (`store_true`, `False`); `--release` (`store_true`, `False`);
`--route` (initial route for web/iOS/Android). Produces no packaged artifact path
(same pipeline minus output copy semantics — **unverified** beyond sharing
`BaseBuildCommand`).

**`flet test`** (`commands/test.py:126-173` + all `BB` args): positional `platform`
(`nargs="?"`, choices `macos|linux|windows|ios|android`, default = current desktop);
`--device-id/-d`; `--tests-dir` (default `"tests"`); `--update-goldens/-u`
(`store_true`, `False`); `--flutter-test-host` (reuse provisioned host, e.g.
CI-cached); `-k` (`dest=pytest_keyword`, pytest `-k` passthrough);
`pytest_args` default `[]` (post-`--` args). Forces `output_dir=None`,
`assume_yes=True` (`test.py:287-297`); provisions a Flutter test host and
propagates `SERIOUS_PYTHON_*` + Flutter SDK path into `os.environ` so the
FletTestApp-spawned `flutter test` bundles an identical app (`test.py:309-318`).

**`flet emulators`** (`commands/emulators.py:35-56` + `FB` args): positional
`action` (`nargs="?"`, choices `start|create|delete`); positional `emulator`
(`nargs="?"`, id/name, required for all three actions); `--cold` (`store_true`,
`False`, cold boot on start).

**`flet devices`** (`commands/devices.py`): positional `platform` (`nargs="?"`,
`str.lower`, choices `ios|android`, default `None`=both); `--device-timeout`
(`dest=device_timeout`, int, default `10`); `--device-connection`
(`str.lower`, choices `both|attached|wireless`, default `"both"`). Runs
`flutter devices --device-timeout N` and filters to iOS/Android rows.

**`flet doctor`** (`commands/doctor.py:17-39`): no options beyond `-v`. Prints
`Flet {ver} on {OS} {release} ({arch})` + `Python {ver} ({exe})`. Flutter-version
line is an explicit `TODO` in source — **unverified** beyond that.

**`flet clean`** (`commands/clean.py:35-76`): positional `python_app_path`
(default `"."`); deletes `<app>/build` (`shutil.rmtree`); exit 1 if app dir
missing or removal fails; prints "Nothing to clean" when no `build/` exists.

**`flet serve`** (`commands/serve.py:42-56`): positional `web_root` (default
`"./build/web"`); `-p/--port` (int, default `8000`); serves static files with
`Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Embedder-Policy:
require-corp`, `Access-Control-Allow-Origin: *` (`serve.py:26-33`); exit 1 if dir
missing or bind fails.

**`flet mcp`**: registered only when `flet_mcp` imports (`CLI:155-161`); not
installed here — **unverified** (no `flet_mcp` in this venv).

### 2.4 Env vars read (no `UV_*`/`PIP_*` reads found — searched `BB/FB/utils`)

| Var | Read at | Effect |
|---|---|---|
| `FLET_CACHE_DIR` | `utils/template_cache.py:15-17` | Cache root (default `~/.flet/cache`); written back to `os.environ` so Gradle children share it |
| `FLET_CLI_NO_RICH_OUTPUT` | `FB:30,66,95` | Plain output (bool env) |
| `FLET_CLI_SKIP_FLUTTER_DOCTOR` | `FB:66,110` | Skip doctor on failure (bool env) |
| `FLET_WEB_RENDERER` | `BB:1539` | Fallback for `--web-renderer` |
| `FLET_WEB_ROUTE_URL_STRATEGY` | `BB:1528` | Fallback for `--route-url-strategy` |
| `FLET_WEB_NO_CDN` | help text `BB:572`; `publish` help | Fallback for `--no-cdn` (exact `os.getenv` call site **unverified** for build; documented in help) |
| `FLET_ASSETS_DIR` | `publish` help; `run.py` exports `FLET_ASSETS_DIR` to child | Assets dir fallback (publish) |
| `FLET_ANDROID_SIGNING_KEY_STORE` / `_KEY_STORE_PASSWORD` / `_KEY_PASSWORD` / `_KEY_ALIAS` | `BB:1636,3064,3071-3088` | Signing fallback chain (see §3.3) |
| `FLET_MACOS_SIGNING_IDENTITY` / `_NOTARY_PROFILE` / `_PROVISIONING_PROFILE` / `_INSTALLER_IDENTITY` | help texts `BB:786-824` | macOS signing fallbacks (exact `os.getenv` wiring for macOS beyond help text **unverified**) |
| `FLET_PYTHON_BUILD_RELEASE_DATE` | `utils/python_versions.py:33,57` | Override pinned python-build manifest date (`20260921`, `python_versions.py:31`) |
| `FLET_PYTHON_BUILD_MANIFEST` | `utils/python_versions.py:34` + `_load_manifest` | Use a local `manifest.json` instead of fetching |
| `APPLE_API_KEY` / `APPLE_API_KEY_ID` / `APPLE_API_ISSUER` | `BB:macos-notary help` | Notary auth alternative (wiring **unverified** beyond help) |

`SERIOUS_PYTHON_*` / `FLET_ANDROID_SIGNING_*` (build side) are *set* by the CLI
for children, not read (see §4). No `UV_*`, `PIP_*`, `POETRY_*`, `VIRTUAL_ENV`
reads exist in `flet_cli/` (grep-verified; **unverified** only insofar as
`serious_python`/`pip` children may read them — out of scope here).

### 2.5 Exit codes

`FB:480 cleanup(exit_code, ...)` → `sys.exit(exit_code)`: `0` = success panel;
nonzero = error panel + `flutter doctor` unless skipped (`FB:490-520`).
Observed codes: `1` for all CLI-side failures (bad app path `BB:902-915`,
validation `BB:956-1019`, bad plist/entitlement/permission/feature/meta-data
values `BB:1185-1374`, missing `app.zip`/staging `BB:2841-2850`, IPA export
failure forced to `1` even when flutter exits 0 `BB:3123-3143`); otherwise the
child's returncode is passed through (`package_python_app` failure `BB:2832`,
`flutter build` failure `BB:3143`). `flet run`/`serve`/`clean` use bare
`exit(1)` on fatal errors. `flet build ipa` unsigned (no profile) is a
*supported* `0` producing only `.xcarchive` (`B:preflight_ios_signing`,
`B:describe_build_output`).

---

## 3. Complete config surface (`pyproject.toml`)

Reader: `load_pyproject_toml()` returns dotted-path getter, `None` on any
missing segment (`utils/pyproject_toml.py:18-50`). Full key inventory (every
`get_pyproject("...")` / `get_platform_setting("...")` found in `BB` + `B`):

### 3.1 Top-level / project metadata

| Key | Type | Default | Effect |
|---|---|---|---|
| `project.name` | str | dir name (`BB:1041-1049`) | Fallback for `project_name`, `artifact_name`, `product_name` |
| `project.version` | str | `None` | `--build-name` fallback (`B:197-203`) |
| `project.description` | str | `None` | `project_description` fallback (`BB:1500`) |
| `project.dependencies` | list[str] (PEP 508) | `[]` | App requirements (converted via `get_project_dependencies`, `utils/project_dependencies.py:88`; `BB:2566-2568`); skipped entirely when `tool.poetry.dependencies` present (poetry wins, `BB:2566`) |
| `project.requires-python` | str (PEP 440) | `None` | Python-row selection when `--python-version` absent (`python_versions.py:resolve_python_version`) |
| `tool.poetry.version` / `.description` / `.dependencies` | str/str/table | `None` | Legacy fallbacks (`B:197-203`, `BB:1500-1501`, `BB:2567`); poetry-dep values converted (`^`→`>=`, `~`→`~=`, bare→`==`, `*`→unpinned; `project_dependencies.py:18-44`) |

### 3.2 `[tool.flet]` + per-platform (`tool.flet.<platform>.*`)

`config_platform` per target: `apk/aab→android`, `ipa/ios-simulator→ios`,
else the target name (`BB:platforms`). `get_platform_setting()` = platform key,
then global key, then default.

| Key (global or `<platform>.*`) | Type | Default | Effect |
|---|---|---|---|
| `tool.flet.build_number` | int/str | `None` | `--build-number` fallback (`B:191-195`) |
| `tool.flet.artifact` / `tool.flet.<platform>.artifact` | str | project name | On-disk artifact name (`BB:1050-1057`) |
| `tool.flet.product` | str | project name | Display name (`BB:1064-1069`) |
| `tool.flet.org` / `tool.flet.<platform>.org` | str | `None` | Reverse-DNS org (`BB:1596-1597`) |
| `tool.flet.bundle_id` / `.<platform>.bundle_id` | str | `None` | Bundle id; also → `SERIOUS_PYTHON_BUNDLE_ID` (§4) |
| `tool.flet.company` / `tool.flet.copyright` | str | `None` | About metadata (`BB:1601-1605`) |
| `tool.flet.description` (**unverified** name — description falls back to `project`/`poetry` only; no `tool.flet.description` read found) | — | — | Do not add |
| `tool.flet.app.path` | str (rel dir) | app root | Package subtree instead of app root (`BB:1002-1005`) |
| `tool.flet.app.module` | str | `"main"` | Entry module stem (`BB:1007-1012`) |
| `tool.flet.app.exclude` / `app.include` / `app.default_excludes` | list / list / bool | `[]` / `[]` / `True` | Packaging include/exclude (see §3.5); `include` rescues from default excludes computed by `find_default_excludes()` (`BB:2660-2683`) |
| `tool.flet.<platform>.dependencies` | list[str] | `[]` | Appended after `project/poetry` deps (`BB:2571-2574`) |
| `tool.flet.<platform>.dev_packages` or `tool.flet.dev_packages` | table `{name = path-or-spec}` | `{}` | Local-path override per requirement name → rewritten to `name @ file:///...` + appends `--no-cache-dir` (`BB:2579-2603`); see §3.6 |
| `tool.flet.<platform>.source_packages` / `tool.flet.source_packages` | list[str] | `None` | → `SERIOUS_PYTHON_ALLOW_SOURCE_DISTRIBUTIONS` csv (`BB:2715-2723`) |
| `tool.flet.<platform>.extract_packages` / `tool.flet.extract_packages` | list[str] | `[]` | Android extracted-to-disk set, merged over built-in `[]` (`BB:2736-2742`) |
| `tool.flet.compile.app` / `compile.packages` | bool | `True` / `True` | `--compile-app/--compile-packages` on the package step (`BB:2744-2753`) |
| `tool.flet.cleanup.app` / `cleanup.packages` | bool | `False` / `True` | Junk-glob stripping (`BB:2755-2758`) |
| `tool.flet.cleanup.app_files` / `cleanup.package_files` | list[str] or comma-str | `None` | Extra globs; specifying forces the matching bool true (`BB:2760-2794`) |
| `tool.flet.android.split_per_abi` | bool | `False` (`BB:1072-1082`) | `--split-per-abi` fallback |
| `tool.flet.android.legacy_packaging` | bool | `False` (`BB:1084-1093`) | Native-lib packaging fallback |
| `tool.flet.android.adaptive_icon_background` | color str | splash `icon_background` → `"#ffffff"` (`BB:1643-1652`) | Adaptive-icon color resource |
| `tool.flet.android.proguard_default_rules` | bool | `True` (only `false` disables, `BB:1134`) | ProGuard default rules |
| `tool.flet.android.proguard_rules` | list | `[]` (`BB:1232`) | Extra ProGuard rules |
| `tool.flet.android.gradle_properties` | table | `{}` (`BB:1227`) | `android_gradle_properties` template context |
| `tool.flet.android.permission` | table `{NAME = true/false}` | `{}` (`BB:1222`) | Manifest permissions (merged with `--android-permissions` + `--permissions` bundle) |
| `tool.flet.android.feature` | table | `{}` (`BB:1271`) | Manifest features |
| `tool.flet.android.meta_data` | table | `{}` (`BB:1291`) | Manifest meta-data (AdMob `APPLICATION_ID` lives here for M5) |
| `tool.flet.android.provider` | table | `{}` (`BB:1304`) | Content-provider entries (**unverified** shape — no CLI flag mirrors it) |
| `tool.flet.android.signing.key_store` / `.key_alias` | str | `None` | Keystore path / alias (passwords NEVER from pyproject, §3.3) |
| `tool.flet.android.deep_linking.scheme/host`, `tool.flet.ios.deep_linking.*`, `tool.flet.deep_linking.*` | str | `None` | Deep-link template context; platform table beats global (`BB:1385-1400`) |
| `tool.flet.ios.export_method` / `.export_methods` (map) / `.provisioning_profile` / `.signing_certificate` / `.export_options` / `.team_id` | str/table | `None` (`debugging` default method, `BB:1448`) | IPA signing/export context; unknown method → exit 1 (`BB:1425-1435`) |
| `tool.flet.macos.info` / `tool.flet.ios.info` | table | `{}` (`BB:1170-1172`) | Extra Info.plist entries (macOS reads `.macos.info`, iOS targets `.ios.info`) |
| `tool.flet.macos.entitlement` | table | `{}` (`BB:1199`) | Extra macOS entitlements |
| `tool.flet.macos.icon_style` | str | `"auto"` (`BB:2113`) | Icon rendering style (**unverified** values) |
| `tool.flet.permissions` | list[str] | `[]` (`BB:1148`) | Cross-platform permission bundles (same 4 values as `--permissions`) |
| `tool.flet.linux.categories` | list/str | `None` | Desktop-entry categories; parse error → exit 1 (`BB:1512-1516`) |
| `tool.flet.web.base_url` | str | `"/"` (`BB:1033-1040`) | Base URL, slash-normalized |
| `tool.flet.web.route_url_strategy` | str | env-or-`None` (`BB:1527-1528`) | `path`/`hash` fallback |
| `tool.flet.web.renderer` | str | env-or-`canvaskit` (`BB:1538-1540`) | `auto`/`canvaskit`/`skwasm` |
| `tool.flet.web.pwa_background_color` / `.pwa_theme_color` / `.pwa_short_name` | str | splash color / `None` / product name (`BB:1542-1562`) | PWA manifest/template values |
| `tool.flet.web.wasm` | bool | `True` (only `false` disables, `BB:1563-1566`) | WASM target gate |
| `tool.flet.web.cdn` | bool | `True` (only `false` disables, `BB:2875-2885`) | `false` = bundle runtime (same as `--no-cdn`) |
| `tool.flet.splash.*` (+ per-platform `tool.flet.<platform>.splash.*`, old aliases `icon_background→icon_bgcolor` etc. `BB:88-93`, lookup `BB:1695-1721`) | colors/bools | built-in defaults (`BB:1723-1760`) | Splash template context; `enabled()`/`color()` resolution |
| `tool.flet.icon_background` / per-platform | color | `None` (`BB:2194-2196`) | Shared icon-background fallback |
| `tool.flet.template.url` / `.ref` / `.dir` | str | `None` → `DEFAULT_TEMPLATE_URL` @ flet version (`BB:67-70`, `BB:1830-1874`) | Custom bootstrap template (trust boundary — hooks execute; see §4) |
| `tool.flet.flutter.pubspec` | table | `None` | Post-render pubspec overrides (§3.4) |
| `tool.flet.flutter.build_args` (via `get_platform_setting("flutter.build_args")`, `BB:3093-3105`) | list/str | `None` | Extra flutter args (config mirror of `--flutter-build-args`) |
| `target_sdk_version` / `min_sdk_version` | — | — | **Do not use: zero reads in 1.0.4** (SDK levels come from the template) |

### 3.3 `tool.flet.flutter.pubspec.*` merge semantics (`BB:1964-1976`)

Rendered `pubspec.yaml` is loaded as YAML; then: `dependencies`,
`dependency_overrides`, `dev_dependencies` are **replaced per-section**
(`pubspec.setdefault(section, {}).update(pyproject_pop)`); every other key is
**deep-merged** via `merge_dict()` (dicts recurse, all else overwritten,
`utils/merge.py:1-23`). Applied post-render, saved back to YAML — not via
cookiecutter. `pubspec.yaml.orig` backup is kept (`BB:1978-1979`).

### 3.4 Signing mapping (CLI > pyproject > env)

Android (`BB:3056-3091`): keystore =
`--android-signing-key-store` > `tool.flet.android.signing.key_store` > `FLET_ANDROID_SIGNING_KEY_STORE`;
store password = CLI > `FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD` (no pyproject
key — passwords env/CLI only); key password = CLI > `FLET_ANDROID_SIGNING_KEY_PASSWORD`;
if either password set, both `FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD` and
`FLET_ANDROID_SIGNING_KEY_PASSWORD` are exported (missing one falls back to the
other); alias = CLI > pyproject `key_alias` > `FLET_ANDROID_SIGNING_KEY_ALIAS` >
`"upload"` (only when a keystore is set). Exported to the `flutter build` child
as `FLET_ANDROID_SIGNING_{KEY_STORE,KEY_STORE_PASSWORD,KEY_PASSWORD,KEY_ALIAS}`.

### 3.5 Cleanup semantics (`BB:2755-2794`)

`cleanup.packages` defaults **on**, `cleanup.app` defaults **off**; either
`*_files` list forces its bool on. String form (`"a/**,b/**"`) is comma-split.
Each glob becomes one `--cleanup-app-files/--cleanup-package-files` arg to
`serious_python package` (comma-safe: one flag per path, `BB:2706-2708`).
`-v` logs the resolved `compile/cleanup` triple (`BB:2796-2804`).

### 3.6 `dev_packages` semantics (`BB:2579-2603`)

For each TOML requirement whose `Requirement(name)` matches a `dev_packages`
key, the requirement is rewritten to `name @ file:///abs/path` (relative paths
resolved against the app dir; missing dir → raw value used verbatim) and
`--no-cache-dir` is appended to the pip requirement list. Forces a fresh
site-packages install (hash path skipped only when `dev_packages_configured`
is false, `BB:2817-2828`). M3/M5 use: point an extension at a local checkout
without editing `pyproject.dependencies`.

### 3.7 Full cookiecutter `extra_context` (build template, `BB:1021-1656`)

Scalar keys: `project_name` (slug, `-`→`_`), `project_name_slug`,
`artifact_name`, `product_name`, `project_description`, `pubspec_description`
(single-quote-escaped), `linux_desktop_exec` / `linux_categories` (pre-escaped),
`org_name`, `bundle_id`, `company_name`, `copyright`, `base_url` (`/x/`-wrapped),
`web_renderer` (**unverified** key name in context — renderer is resolved into
`flutter_bootstrap`/wasm logic; raw key presence not line-pinned),
`pwa_background_color`, `pwa_theme_color`, `pwa_short_name`, `no_wasm`,
`no_cdn`, `pyodide_version`, `no_cdn_js` / `canvas_kit_base_url_js` /
`pyodide_url_js` / `font_fallback_base_url_js` (JS literals, `BB:1658-1693`),
`split_per_abi`, `test_mode`, `adaptive_icon_background`, `boot_screen`,
`splash`, `pyproject` (whole parsed document), `flutter: {dependencies: [...]}`,
`options: {package_platform, config_platform, python_version (short),
target_arch, android_excluded_abis, info_plist, macos_entitlements,
android_permissions, android_features, android_meta_data,
android_gradle_properties, android_proguard_rules, android_providers,
deep_linking: {scheme, host}, android_signing (bool), android_legacy_packaging
(bool)}`, plus iOS keys `ios_export_method/provisioning_profile/
signing_certificate/export_options/team_id`. Unknown extra keys are
**unverified** (cookiecutter silently ignores keys absent from the template's
`cookiecutter.json` — D3-study behavior, not re-verified here).

---

## 4. Pipeline internals (`flet build apk` as reference; all targets share it)

Order (`B:96-149` `handle()`): `initialize_command()` → `validate_target_platform()`
→ `validate_entry_point()` → `setup_template_data()` → (macOS/iOS preflight) →
`create_flutter_project()` → `package_python_app()` →
`register_flutter_extensions()` → optional second-pass `create_flutter_project(second_pass=True)` +
`update_flutter_dependencies()` → `customize_icons()` + `customize_splash_images()` →
`run_flutter()` (`_run_flutter_command`) → `copy_build_output()` (+ `sign_macos_app`
for macOS) → `cleanup(0|rc)`.

1. **Initialize** (`BB:884-954`): resolve `package/config_platform`, `require_android_sdk`
   (Android only), `python_app_path`, `build/{flutter,flutter-packages,flutter-packages-temp}`,
   `out_dir`, `get_pyproject`; `resolve_python_version()` (CLI > `requires-python` >
   manifest default; unknown → exit 1). `.python-version` switch wipes `build/`
   (stale `.pyc` would crash with bad magic, `BB:940-954`).
2. **Toolchain** (`FB:126-196`): `install_flutter()` (pinned 3.44.8 into the
   Flet cache), `install_jdk()` + `install_android_sdk()` when
   `require_android_sdk`; prompts gated by `--yes`/`assume_yes`
   (`FB:381-423`). `flutter doctor` runs on failures unless skipped.
3. **Template** (`BB:1807-~1985`): ref = CLI/`tool.flet.template.*`/flet version;
   default URL `DEFAULT_TEMPLATE_URL` @ version (`BB:67-70`); zip fetched via
   `get_cached_template_zip()` — **no checksum, no revalidation**
   (`utils/template_cache.py:25-52`); hash-stamped (`build/.hash/template-1/2`)
   so unchanged renders are skipped; `cookiecutter(..., no_input=True,
   overwrite_if_exists=True, extra_context=§3.7)`; generated icons/splash are
   backed up + restored around re-render (`BB:2293-2336`, `template_digest`);
   then pubspec post-processing (§3.3) + `pubspec.yaml.orig` backup.
4. **package_python_app** (`BB:2514-2873`): subprocess
   `[dart, run, --suppress-analytics, serious_python:main, package, <app>,
   --platform <PackagePlatform>, --python-version <short>]`
   (+ `--arch a,b` comma-joined, one `--exclude <p>` per path, `--compile-app?`,
   `--compile-packages?`, `--cleanup-*?`, `--verbose` iff `-vv`), cwd =
   `build/flutter`, env = `SERIOUS_PYTHON_VERSION` (+ `SITE_PACKAGES`,
   `APP=build/python-app`, `BUNDLE_ID?`, `DARWIN_SPM/SPM_KEY_FILE?` on iOS/Darwin,
   `FLUTTER_PACKAGES=tempdir`, `ALLOW_SOURCE_DISTRIBUTIONS?`); output captured
   unless `-v`. Hash-stamped (`build/.hash/package` over args + requirements.txt
   contents); unchanged → `--skip-site-packages` (and Flutter-packages dir is
   kept, `BB:2817-2828`). Success contract: Emscripten must produce
   `flutter/app/app.zip`, native must stage `build/python-app` — else exit 1
   (`BB:2834-2850`). Web + `--no-cdn` additionally stages Pyodide via
   `ensure_pyodide()` into `flutter/web/pyodide` (else a stale copy is deleted,
   `BB:2852-2873`).
5. **Requirements assembly** (`BB:2560-2604`): `tool.poetry.dependencies`
   (converted) **OR** `project.dependencies` (normalized; poetry wins when both
   present) **OR** `requirements.txt` (passed as `-r -r -r <file>`, triple-`-r`
   verbatim `BB:2604`) **OR** fallback `flet==<running flet_version>` (`BB:2606`).
   Then `tool.flet.<platform>.dependencies` are appended. Then `dev_packages`
   rewriting (§3.6). Then `-r <each>` appended to the `serious_python package`
   argv. **Index behavior (pip flags, `--extra-index-url`, `--find-links`,
   `UV_*`/`PIP_*` passthrough): no reads in `flet_cli/` — owned by
   `serious_python`, **unverified** here.**
6. **register_flutter_extensions** (`BB:1994-2035`): move
   `flutter-packages-temp` → `flutter-packages` (unless site-packages skipped);
   every subdir with a `pubspec.yaml` becomes a `path:` dependency of the
   Flutter project (collected into `self.flutter_dependencies`).
   **update_flutter_dependencies** (`BB:2043-2070`, second pass only): merge
   those path deps into `pubspec.yaml` and (verbatim) run the equivalent of
   `flutter pub get` — exact argv **unverified** (not line-pinned in this pass).
7. **Icons/splash** (`BB:2072-2493`): rendered by `flet-platform-assets`
   (`DEFAULT_SPECS`, `render_icons/render_splash`) per `ICON_PLATFORMS`
   (`BB:83-91`; apk/aab→android incl. adaptive layers, ipa→ios, web splash only,
   linux hicolor created fresh); generator versions `ICONS_GENERATOR_VERSION=1`,
   `SPLASH_GENERATOR_VERSION=3` (`BB:78-81`) bust the stamps; missing-source
   behavior per `_icons_missing()`; iOS storyboard patched
   (`patch_launch_storyboard`, `BB:2452`).
8. **flutter build** (`BB:3032-3143`): argv per §2.1 + `flutter.build_args` +
   `--wasm` (web, renderer `auto`/`skwasm` and not `--no-wasm`, `BB:2887-2903`).
   Env = `_serious_python_build_env()` (`BB:2969-3030`: `SERIOUS_PYTHON_VERSION`,
   `SITE_PACKAGES`, `APP`, `BUNDLE_ID?`, `SP_NATIVE_SET?` (SPM key file),
   `ANDROID_EXTRACT_PACKAGES?`) + `FLET_ANDROID_SIGNING_*` (§3.4). Pre-run wipes
   the target's output dirs inside `build/flutter` (stale-artifact guard,
   `B:run_flutter`). `flutter build ipa` exit-0-without-`.ipa` is detected via
   glob and forced to exit 1 with a re-run hint (`BB:3123-3143`).
9. **Copy output** (`BB:3218-3386`): `copy_tree()` of each `outputs` glob into
   `out_dir` (wiping it first; single-glob filter `make_ignore_fn`);
   `assets/` dir contents copied alongside (non-web); apk/aab renamed
   `app[-suffix].apk/.aab` → `{artifact_name}[-suffix].apk/.aab`
   (`rename_android_build_outputs`, `BB:3323-3386`); web CDN pruning
   (`prune_cdn_assets`, `BB:3301`). Final message names the artifact
   (`describe_build_output`, `B:231-243`); web hints `flet serve`.

---

## 5. How this dependency makes our app significantly better than Termux's proot-distro

Termux ships `proot-distro` as scripts + manual `pkg install` steps inside a
general terminal. `flet-cli` lets us ship the opposite: a signed,
config-driven, one-command-release Android product.

* **One-command release pipeline vs manual assembly.** `flet build apk --split-per-abi`
  (`B:62-84`, `B:166`) plus `[tool.flet.android] split_per_abi` (`BB:1072-1082`)
  turns `main` into per-ABI APKs + AAB from CI — no local builds (D-005), no
  hand-staged SDKs (toolchain auto-installs, `FB:126-196`).
* **Declarative Android identity.** `--bundle-id/--org/--product` + manifest
  tables (`android.permission/feature/meta_data/provider`, `BB:1222-1304`) and
  the 4 cross-platform `--permissions` bundles (`BB:731-741`) encode our
  INTERNET-only + AdMob `meta_data` posture (M5) in `pyproject` instead of wiki
  instructions.
* **Exec-capable bundle, not a terminal recipe.** The `serious_python package`
  contract (`BB:2514-2656`) + native-build env (`BB:2969-3030`) is what carries
  our Python + `proot-distro` + `libproot.so` path (M2 wheel) into the APK as
  data the app can `subprocess`-spawn on-device (M0 gate 4: Python-side PTY,
  O-3 closed) — Termux users type spawn commands; our users tap a distro.
* **Reproducible CI.** `--yes` (`FB:97-104`), `FLET_CACHE_DIR`
  (`template_cache.py:15-17`), `FLET_PYTHON_BUILD_RELEASE_DATE`
  (`python_versions.py:33-57`), `.python-version` wipe (`BB:940-954`) and
  hash-stamped template/package steps (`BB:1827`, `BB:2530`) make `build-<sha>`
  prereleases bit-stable (M5 `build-all.yml`).
* **Safe iteration surface.** `dev_packages` local-path overrides (`BB:2579-2603`)
  let M1/M4 develop `flet-terminal` + app together; `flet run` (`run.py:75-198`)
  keeps the fast desktop loop while device truth stays on CI artifacts (D-005).
* **Store-readiness.** `FLET_ANDROID_SIGNING_*` env-only passwords (`BB:3056-3091`,
  D-008 house keystore), `rename_android_build_outputs` artifact naming
  (`BB:3323-3386`), and the web/`serve` offline story (`resolve_no_cdn`,
  `serve.py:26-33`) map directly onto M5/M6 (Play + GitHub/F-Droid fallback).

---

## 6. Fullest utilization for this project (M1–M6; CI uses a subset today)

| Lever (in 1.0.4, unused by our CI today) | Where | Use in milestone |
|---|---|---|
| `--source-packages` / `tool.flet.<platform>.source_packages` | `BB:source_packages` → `SERIOUS_PYTHON_ALLOW_SOURCE_DISTRIBUTIONS` (`BB:2715-2723`) | M2/M3: force source builds for arch-sensitive wheels if a Forge/ABI gap appears |
| `--android-extract-packages` / `extract_packages` | `BB:android_extract_packages` (`BB:2736-2742`, `_serious_python_build_env` `BB:3025-3030`) | M2/M3: ship `__file__`-hungry packages extracted (native-mmap comment `BB:69-82`); candidate if `proot-distro` data reads ever break from the zip |
| `--no-rich-output` + `FLET_CLI_NO_RICH_OUTPUT`, `-vv` | `FB:24-31,90-96`; `-vv` streams child output (`BB:2832`, `BB:3117`) | M5: plain logs always; `-vv` on failure-only reruns (today: plain `-v`) |
| `flet doctor` | `commands/doctor.py:17-39` | M5 CI triage step (thin today: OS + Python lines only; Flutter line is a `TODO`) |
| `flet emulators` / `flet devices` | `emulators.py:35-56`, `devices.py` | M5/M0: x86_64 emulator QA matrix (O-6) — create/start/cold-boot + `--device-timeout`/`--device-connection` filters |
| `flet pack` (PyInstaller) | `pack.py:29-171` | M1/M4: desktop harness that *does* compile extension Dart (roadmap §1b lever; needs owner sign-off under no-local-builds, O-9) |
| `flet publish` + `flet serve` | `publish.py:35-155`, `serve.py:42-56` | M4 docs/demo: static web export + COOP/COEP-correct local preview |
| `flet debug` / `flet test` hosts | `debug.py:34-76`, `test.py:126-180,287-318` | M4: on-device debug sessions; integration-test host (`--flutter-test-host` CI cache, `-k`, `--update-goldens`) for terminal golden tests |
| `dev_packages` | `BB:2579-2603` | M1: `flet-terminal` 0.4.0 co-development without version bumps |
| `flutter.build_args` / `--flutter-build-args` (+ post-`--` passthrough) | `BB:3093-3105`, `CLI:239-261` | M5: `--obfuscate`/`--split-debug-info` without waiting for first-class flags |
| `cleanup.app_files/package_files`, `compile.app/packages` | `BB:2744-2794` | M5: APK diet after the `[tool.flet.cleanup]` audit (roadmap M5: `oauthlib/**` first candidate) |
| `template.ref` pin + `FLET_PYTHON_BUILD_RELEASE_DATE` | `BB:1830-1874`, `python_versions.py:33-57` | M5: bump-parameterized rebuilds (template ref follows the flet pin; D-010 1.1.0 day) |
| `flet clean` | `clean.py:35-76` | M5 CI hygiene between matrix legs (plus the automatic `.python-version` wipe) |
| `--cleanup-*` + `--no-default-excludes`/`--include` for `.env*` | `BB:2660-2713` | M3: guarantee secrets never ship (CLI warns on `.env` exclusion, `BB:2694-2705`) |

Not recommended: `--template` at untrusted URLs (no-checksum zip + executing
hooks, `template_cache.py:25-52`); `target_sdk_version`/`min_sdk_version` keys
(absent in 1.0.4 — template-owned); passwords anywhere but env/CLI (§3.4).

---

## 7. Verification

* Sources: `flet_cli/cli.py` (282 lines), `commands/build.py` (903),
  `commands/build_base.py` (3639), `commands/flutter_base.py` (564),
  `commands/{run(693),pack(643),publish(411),debug(193),test(315),emulators(400),
  devices(242),doctor(39),clean(76),serve(102),create(177),options(78),base(102)}.py`,
  `utils/{template_cache(48),python_versions(213),project_dependencies(133),
  pyproject_toml(50),merge(23),android(53)}.py`, `METADATA`, `version.py`,
  `flet/version.py:19-29`. Line numbers above are per-installed-file `grep`/`sed`
  offsets and may shift by a few lines after edits; re-grep the symbol if a pin fails.
* `UV_*`/`PIP_*` reads: none found in `flet_cli/` (grep over `*.py` for
  `UV_|PIP_|getenv|environ` — only `FLET_*`/toolchain vars hit).
* **Unverified** items are labeled inline: console-script declaration site,
  `flet debug` artifact semantics beyond shared base, `flutter pub get` exact
  argv in `update_flutter_dependencies`, `android.provider` table shape,
  `macos.icon_style` values, `FLET_WEB_NO_CDN` build-side `getenv` call site,
  macOS `os.getenv` wiring beyond help text, cookiecutter unknown-key behavior
  (D3-study carryover), `flet mcp` (extra not installed), and any `serious_python`
  pip/index internals (child process, out of scope).
