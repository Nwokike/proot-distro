# Dependency studies — index (47/47 packages, verified 2026-10-16)

**Purpose:** exhaustive, API-level documentation for every dependency and sub-dependency in the app's environment, per the owner's rule — *"I already have them, so why not utilize them to the fullest"* and *"the only way we beat Termux is by utilizing every dependency to the fullest."*

**Method & rules (enforced in every file):**
- Every API claim verified against the **installed source** in `.venv` (`file:line`) or live introspection with the venv Python; nothing guessed.
- Unverifiable claims are explicitly labeled **unverified** (each file has its own section for these).
- Each file includes **"How this dependency makes our app significantly better than Termux's proot-distro"**.
- One file per dependency/sub-dependency. Reconciliation against `uv tree` (48 entries incl. project root): **zero misses** — the only names without a dedicated file are `proot-distro` (→ `proot-distro-api.md`) and the project root itself.

**Companion libraries:** `../reference/` (integration/house-pattern studies produced earlier — app-*, dep-* summaries) · `../compliance/` (licensing, Play policy, distro-images — in progress) · `../decisions.md` · `../roadmap.md`.

## Runtime (ships in the APK)

| File | Package | Highlight |
|---|---|---|
| [proot-distro-api.md](proot-distro-api.md) | proot-distro 5.10.0 | **The integration bible** — every module/function signature, env contract, on-disk formats, exit-code map, update-safety index, milestone utilization map |
| [flet.md](flet.md) | flet 1.0.4 | Full namespace map; service-refcount eviction rule (`page.py:228`); `_swap_to_port` Android process reuse; `ft.Button`/`ft.Border.all` corrections |
| [flet-ads.md](flet-ads.md) | flet-ads 1.0.4 | 12 exports; `NativeAd` triple-verified dead; UMP consent flow; APPLICATION_ID is ours to declare |
| [flet-terminal.md](flet-terminal.md) | flet-terminal 0.3.9 | Every prop/event/method + queue semantics; 13 extra-key byte sequences; 4 theme palettes; renderer-context RuntimeError + `refresh_buttons` AttributeError (M1 must-fixes) |
| [httpx.md](httpx.md) | httpx 0.28.1 | No built-in retries; auth stripped cross-origin; certifi vs Android trust store; M3 `HttpService` sketch |
| [msgpack.md](msgpack.md) | msgpack 1.2.3 | The Flet wire protocol (`packb([action,body])`, `0x00` framing); never pin ≥1.2.0 (Android wheels stop at 1.1.2) |
| [anyio.md](anyio.md) | anyio 4.15.1 | asyncio-only backend; memory-stream progress pipelines; `CancelScope` installs; `CapacityLimiter(1–2)` |
| [httpcore.md](httpcore.md) | httpcore 1.0.9 | HTTP2/SOCKS paths dead without extras; the exact httpx→pool→h11 chain |
| [h11.md](h11.md) | h11 0.16.0 | Real surface is `receive_data`/`next_event`; 8-state machine; which exception means what |
| [oauthlib.md](oauthlib.md) | oauthlib 4.0.0 | Prunable (~1 MB): only `Page.login()` touches it → `cleanup.package_files=["oauthlib/**"]` |
| [idna.md](idna.md) | idna 3.20 | Full encode/decode surface; Unicode 18 tables (~283 KB); dormant without OAuth |
| [certifi.md](certifi.md) | certifi 2026.7.22 | 121-CA bundle; httpx=cafile-only vs httpcore=additive; private-CA `verify=` guidance |
| [typing-extensions.md](typing-extensions.md) | typing-extensions 4.16.0 | All 121 exports; on py3.14 `dataclass_transform` resolves to stdlib — keep floating |
| [repath.md](repath.md) | repath 0.9.0 | 8 KB, 9 functions; powers flet Router — keep with six or prune both |
| [six.md](six.md) | six 1.17.0 | repath's sole import; 34 KB |

## Dev / build host (never ships to APK)

| File | Package | Highlight |
|---|---|---|
| [flet-cli.md](flet-cli.md) | flet-cli 1.0.4 | All 13 subcommands + 8 build targets; full `[tool.flet*]` key inventory; CLI > platform > global precedence; no UV_/PIP_ reads |
| [flet-desktop.md](flet-desktop.md) | flet-desktop 1.0.4 | Viewer cache (`~/.flet/client/`); `open/close_flet_view` |
| [flet-platform-assets.md](flet-platform-assets.md) | flet-platform-assets 1.0.4 | 27 exports; full icon/splash matrix; adaptive-icon mechanics |
| [pillow.md](pillow.md) | pillow 12.3.0 | The 18-call toolchain contract behind icons/splash; build-host only |
| [cookiecutter.md](cookiecutter.md) | cookiecutter 2.7.1 | 15-param semantics; overwrite/hook/replay internals; no-checksum template cache gap |
| [ruff.md](ruff.md) | ruff 0.17.1 | 59 rule families vs Sherlock/ffmpeg sets; adopt Sherlock set + CI gate; unknown keys hard-error |
| [pytest.md](pytest.md) | pytest 9.1.1 | 19 builtins, 8 markers, 41 ini keys — the reference for our house pytest config |
| [pytest-timeout.md](pytest-timeout.md) | pytest-timeout 2.4.0 | `timeout_method="thread"` pin for Windows/Linux parity |
| [pluggy.md](pluggy.md) | pluggy 1.7.0 | Full API; verdict: don't adopt directly |
| [iniconfig.md](iniconfig.md) | iniconfig 2.3.1 | IniConfig surface + lineof |
| [packaging.md](packaging.md) | packaging 26.3 | Version/Specifier/Requirement/Marker with pytest call sites |
| [colorama.md](colorama.md) | colorama 0.4.6 | `just_fix_windows_console`; why present (pytest + qrcode) |
| [watchdog.md](watchdog.md) | watchdog 6.0.0 | `flet run` hot-reload only — never in-app |
| [qrcode.md](qrcode.md) | qrcode 8.2 | Dev-flow QR (`print_ascii`); honest no-ship verdict for APK |
| [rich.md](rich.md) | rich 15.0.0 | Every Console param/method; `--no-rich-output` mechanics for CI fidelity |
| [markdown-it-py.md](markdown-it-py.md) | markdown-it-py 4.2.0 | Pure-Python — candidate for in-app markdown rendering (M4 decision) |
| [mdurl.md](mdurl.md) | mdurl 0.1.2 | 5 functions; 8-field URL |
| [pygments.md](pygments.md) | pygments 2.21.0 | 602 lexers/51 styles; APK-size caveat for future previews |
| [requests.md](requests.md) | requests 2.34.2 | Zero retries by default; host/CI only |
| [urllib3.md](urllib3.md) | urllib3 2.8.0 | Retry knobs inventory; TLS helpers |
| [charset-normalizer.md](charset-normalizer.md) | charset-normalizer 3.5.2 | Full detection API; chardet shadows it in requests' lookup |
| [click.md](click.md) | click 8.5.0 | `__version__` deprecated; first-class for our tooling CLIs |
| [jinja2.md](jinja2.md) | jinja2 3.1.6 | `select_autoescape` lives in utils; distro-config templates candidate |
| [markupsafe.md](markupsafe.md) | markupsafe 3.0.4 | Compiled speedup on host, fallback on Android |
| [pyyaml.md](pyyaml.md) | pyyaml 6.0.3 | Manifests read/write; safe_load only |
| [arrow.md](arrow.md) | arrow 1.4.0 | Report timestamps; datetime API inventory |
| [python-dateutil.md](python-dateutil.md) | python-dateutil 2.9.0 | Parser/rrule surface; arrow's engine |
| [tzdata.md](tzdata.md) | tzdata 2026.5 | IANA db; zoneinfo fallback |
| [binaryornot.md](binaryornot.md) | binaryornot 0.4.4 | File-type probe for import/export features |
| [chardet.md](chardet.md) | chardet 5.2.0 | **LGPL — never vendor**; dev-only shadow of charset-normalizer |
| [python-slugify.md](python-slugify.md) | python-slugify 9.1.3 | No `slugify_unicode` in 9.x |
| [text-unidecode.md](text-unidecode.md) | text-unidecode 1.3 | Transliteration tables |

## How to use this library when building the app
1. **Before writing any module that touches a dependency**, read its file here — the API inventory tells you what exists (no guessing, no reinventing).
2. **Before adding a feature**, check the file's "fullest-utilization" + Termux-differentiator sections — the capability may already be in a dependency we ship.
3. **When bumping any dependency**, check §Update-safety in `proot-distro-api.md` and the per-file unverified sections for the re-verify list.
4. **Compliance files** (`../compliance/`) override convenience: e.g., pillow/pygments sizes, chardet's LGPL, GPL source-offer duties.
