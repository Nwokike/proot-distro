# Roadmap synthesis — full corpus harvest → complete milestone plan (M1–M6)

> **Status:** harvest **COMPLETE 2026-10-16** — all 47 dependency studies + 3 compliance docs + 16 reference studies + core docs read personally (owner-directed; no sub-agent) and harvested below. The synthesized M0–M6 milestone plan is **integrated into [roadmap.md](roadmap.md)** (superseding the pre-study milestone list); this file remains the append-only harvest/evidence log.
> Method: every item cites its source document; nothing invented; corrections and open issues are tracked in dedicated sections.
> Corpus: `docs/dependency-studies/` (47 files + INDEX) · `docs/compliance/` (3) · `docs/reference/` (16 integration studies) · `docs/roadmap.md` (superseded plan for M1–M6) · `docs/decisions.md` · `docs/m0-checklist.md` · `docs/testing-findings.md`.
> **Doc-integrity findings this pass:** `compliance/distro-images.md` carried a write-tool truncation baked into the committed file (literal marker at line 369; missing tail unrecoverable anywhere) — §3.2(2)–§7 reconstructed + repair-note added in-file; `m0-checklist.md` was missing the apt investigation (retests #4–#6, spikes 8/9/10) — recorded; everything else verified complete.

## Corpus harvest log (append-only as each document is read)

### [read] proot-distro-api.md (1,222 lines)
- Identity: GPL-3.0-only; zero runtime deps; entry `pd`/`proot-distro`; 77 py files; 18 commands (`cli.py:64-84`).
- M3 facade surfaces: SAFE = env contract (`constants.py:47-86`), on-disk layout, pure helpers (`paths.*`, `docker/refs.*`, `docker/cache.iter_cached_images`, `arch.*`, `search_images`, `progress.fmt_size`, `guestfile.*`, `names.*`, `execenv.*`, `compress.require_*`). FRAGILE (behind ONE wrapper): `command_*` internals (argparse namespace + `sys.exit(1)`), `build_proot_args` (27 kwargs, exact order `proot_cmd.py:55-128`), `_run_install`/`_login_with_rootfs`, `ContainerLock` semantics, `rootfs_fd` convention, `register_session` PID-identity, `run_step._exec_proot`.
- In-process callers must catch `SystemExit` AND `RuntimeError`; every error path exits 1 (164 sys.exit sites).
- Proven: install keeps `open_container_pair` fds through extraction; etc fixups + `setup_fake_sysdata` run at install (`install.py:357-381`); `pull_image` raises RuntimeError incl. InvalidReference and supports fully-offline cached installs; `PD_DOCKER_AUTH` for private registries; `PD_FORCE_NO_COLORS`.
- Layout: `containers/<name>/{rootfs,manifest.json,shm,sysdata,.l2s}`; sessions `sessions/<pid>.json`; locks `locks/`; caches `oci_layers/`, `oci_manifests/`, `build_cache_index.json`.
- Utilization backlog (M3/M4): backup/restore snapshots; sync/copy host↔guest bridge; ps/kill session manager + force-stop escalation (SIGTERM→SIGKILL 2s grace); search → in-app image browser; rename/reset; remove --image + clear-cache → storage manager (free-X-MB UI); `command_run` → structured one-shot mode primitive (M4 dual-mode); `login --detach` → background services; `command_build` + build_engine + push → on-device image bakery + share (M4/M5, "Remix this container"); `arch.*`+get_proot_bin → `core/proot_probe.py`; `busy_locks()` → "install in progress" states; `atomic.*`+`statedir.*` → crash-safe facade state.
- Termux differentiators (10): zero-Termux generic mode; in-app search/one-tap install; snapshots UI; session manager not `ps`; structured command mode; on-device image bakery+push; storage transparency; safe concurrency; probe-gated UX; ads+Play distribution.
- Update-safety: re-verify list for every 5.x bump (constants, build_proot_args, parser, session record, manifest keys, cache shapes, cli probe exemptions).
- Unverified ledger (7 items): build.py namespace fields; `_login_with_rootfs` line pins; `.l2s` marker filename; oci_writer zstd omission intent; docker re-export identity; (2 process notes).
### [read] flet.md (514 lines)
- 538 public exports; lazy PEP 562 loading (`_LAZY` map; cold start pay-per-control); Flutter pinned 3.44.8; Apache-2.0.
- M3 services arsenal (now named precisely): `SharedPreferences`, `StoragePaths` (cache/documents/support/temp + `FLET_APP_STORAGE_*`), `Connectivity` (gate OCI pulls on wifi + on_change pause/resume), `FilePicker` (import/export rootfs), `UrlLauncher`, `Clipboard`, `Share` (report/file export), `HapticFeedback`, `Wakelock`/`ScreenBrightness` (long downloads, WITH refcount discipline).
- **Refcount rule §3.7**: `unregister_services` prunes services at `sys.getrefcount <= min_refs` (3 on py3.14); screens must drop refs on unmount or the registry leaks (battery rule too).
- Android: embedded dart_bridge (no socket loop); `_DartBridgeServerHandle._swap_to_port` = connection replaced on process reuse → **session state lives in Python only**; `get_platform()/get_arch()` raise on mobile — use `page.platform`/`FLET_PLATFORM`.
- M4 chrome: `Pagelet`+AppBar for terminal embedding; TabBar for multi-session (one ProotSession/tab); stdin prompts via `use_dialog`+AlertDialog (CollabShell pattern); pubsub fan-out for multi-view; `DataChannel` reserved for future binary transfer (probe-gated).
- M6: licenses screen via Markdown/ListView (GPL texts + source links).
- Testing: `Tester`+`Finder`+`pytest_plugin` for scripted UI tests (core widgets only — extension panes stay device-gated D-005).
- Unverified ledger U-1..U-6 (widget ctor detail omissions noted; canvas/fastapi shims; support-dir env name; push_route; Dart-side behavior).

### [read] flet-terminal.md (328 lines)
- 8 root exports; Terminal 10 props/10 events/18 methods with queue semantics; 13 extra-key byte sequences + sticky CTRL/ALT; 4 theme palettes (JetBrains Dark default); search; `thaw/control_update`; `ready/pending_count/flush` (0.3.9).
- M1 must-fixes (verified): (1) `MobileTerminal()` renderer-context RuntimeError outside component trees; (2) `ctrl_active/alt_active` setters call nonexistent `ExtraKeysBar.refresh_buttons` → latent AttributeError.
- M1 blueprint deltas: requires-python `>=3.14`→`>=3.10`; add license metadata; narrow `**/*` package-data glob; URL order; tests/contract suite; compat matrix; README house format.
- M4 parity mapping table (every capability → milestone use); font_family Android fallback unverified (ship font or verify).

### [read] flet-cli.md (589 lines)
- 13 subcommands; full `[tool.flet*]` key inventory; precedence CLI > platform > global > default; env: FLET_CACHE_DIR, FLET_CLI_*, FLET_WEB_*, FLET_ASSETS_DIR, FLET_ANDROID_SIGNING_*, FLET_PYTHON_BUILD_* (date/manifest); **no UV_/PIP_ reads in flet-cli**.
- Build pipeline order (9 steps); `package_python_app` contract (serious_python owns pip/index behavior — unverified side); template zip NO checksum + hooks = trust boundary; `.python-version` switch wipes build/; requirements assembly (poetry OR project.dependencies OR requirements.txt OR flet fallback; platform deps appended; dev_packages → file:// + --no-cache-dir).
- M5 levers unused today: `--source-packages`, `--android-extract-packages`, `--no-rich-output`, `flet doctor/emulators/devices/clean`, `dev_packages` (M1 co-dev), `flutter.build_args` (obfuscate), cleanup.app_files/package_files (oauthlib/** first), `--include/--no-default-excludes` for .env safety. Never: untrusted --template; target_sdk_version/min_sdk_version (absent 1.0.4).
- `flet pack` (PyInstaller desktop, compiles extension Dart) exists — O-9 owner decision under no-local-builds.

### [read] msgpack.md (322 lines)
- THE wire protocol: `packb([action, body], default=...)` + `0x00` frame (bridge: no length prefix; socket: LE length); actions 1–7 (Dart-enum lockstep); ext codes 1–4 = flet's (datetime/time/Duration/str) — never reuse for our records; DataChannel 0x01 raw framing is NOT msgpack.
- **Binding rules**: never pin ≥1.2.0 anywhere (Forge wheels 1.1.x only, cp314 arm64 filename verified); `use_bin_type=True` always; `strict_map_key=True` always; catch broad `Exception` (UnpackException is not total); `ExtraData` = corruption; streaming Unpacker.feed for multi-record; max_buffer_size on untrusted input.
- M3/M4 uses: container-metadata snapshots, crash-safe progress checkpoints, structured cell-output batches, session handoff records — all behind the facade/`core/codec.py`. Non-uses: spike, cross-process IPC, flet wire path, MSGPACK_PUREPYTHON in app code.
- Failure semantics: pack failure = silent UI stall risk; unpack failure = dropped frame, session survives; no version negotiation (lockstep mandatory).
- Android: C extension ships in Forge wheel; silent fallback to pure-Python if load fails (check `Packer.__module__` when sluggish).

### [read] httpx.md (255 lines)
- Full client/transport/exceptions inventory; **httpx ships NO retry policy** → app-owned `retry_http`-style wrapper mirroring upstream's 5×5s + `is_retryable_http_error` gate; per-phase `Timeout(connect/read/write/pool)`; `stream + aiter_bytes` for progress (replaces stderr scraping!); `MockTransport` for offline tests; env-proxy free w/ trust_env; cross-origin `Authorization` strip on redirect = parity with upstream's stripper.
- M3 `HttpService` sketch (sole importer, keep-alive pool 6/2, capped `fetch_json` 16 MiB read cap mirrored from upstream MAX_METADATA_BYTES, download with progress_cb); certifi-vs-Android-trust-store gap → `verify=` bundle override in Settings; pause/resume on network loss with Range probe.
- Migration map upstream urllib → httpx documented row-by-row (parity preserved).

### [read] anyio.md (390 lines)
- MIT 4.15.1, pure-Python; asyncio-only in our env (trio/sniffio/outcome/uvloop absent; assert `get_available_backends()==("asyncio",)` at startup); rides the APK via httpx regardless.
- M3/M4 arsenal: structured concurrency = no orphan installs; `CancelScope` + `shield=True` two-phase cancel (cancel → shielded cleanup deletes partial rootfs + releases ContainerLock); `move_on_after` soft timeouts; `CapacityLimiter` caps (explicit small limiters — never the ~40 default); memory-object streams = typed progress pipeline replacing stderr scraping; `to_thread.run_sync(..., limiter=...)` preferred over `asyncio.to_thread` (defined cancel semantics); `open_process` byte streams for ProotSession (no PTY — matches M0 view-only decision); `MockBackend`-style offline tests via `wait_all_tasks_blocked`+`get_running_tasks`.
- Proposals carried into plan: P1 install_pipeline (producer→stream→UI async for), P2 cancellable installs (Cancel button → scope.cancel, move_on_after(600) default), P3 session_manager one task group per tab + CapacityLimiter(4), P4 startup probe gather.
- Android: private import `asyncio.base_events._run_until_complete_cb` (`_backends/_asyncio.py:21`) — only a CPython major bump in the build recipe can break it (pin-watch, never patch); `open_signal_receiver` POSIX-only → unusable, use cancellation; `open_process`/`run_process` on serious_python needs M0-gate-4 proof — keep raw-subprocess `--get-proot-cmd` fallback behind the same interface.
- Non-goals: trio, to_process/to_interpreter, UDP/TCP listeners.

### [read] httpcore.md (272 lines)
- BSD-3 1.0.9 pure-Python; httpx engine; **h2 + socksio ABSENT** → HTTP/2 and SOCKS classes are import-time stubs in our venv (dead, not installable-now); `HTTP11Connection` is the only usable protocol conn; `MockBackend`/`AsyncMockBackend` for offline network tests; `Trace` + `extensions` (timeout connect/read/write/pool, sni_hostname) for byte-level debugging; `ConnectionPool(max_connections=10, keepalive_expiry, retries)` params.
- `default_ssl_context()` = ssl default ctx + certifi bundle.
- Exception totality table: 15 httpcore exceptions → exact httpx mappings (PoolTimeout/ConnectError/RemoteProtocolError/ProxyError/…Timeout) — the “what do I catch” reference for `friendly_job_error`.
- House call: stay on httpx; direct httpcore only for pool tuning/backpressure, proxy control, mock tests, protocol debugging. Never for general requests/HTTP2/SOCKS.

### [read] h11.md (139 lines)
- MIT 0.16.0, zero-dep HTTP/1.1 state machine under httpcore; `Connection(our_role=h11.CLIENT, max_incomplete_event_size=16384)`; `send`/`receive_data`/`next_event` (returns NEED_DATA/PAUSED) — **no `receive`/`receive_failed` in 0.16.0** (corrected); `start_next_cycle()` = keep-alive reuse; `trailing_data` for CONNECT/upgrade; states IDLE→SEND_BODY→DONE→MUST_CLOSE/CLOSED/ERROR.
- Local vs Remote ProtocolError split = “fix OUR request” vs “distrust the MIRROR” — feeds friendly error translation.
- Utilization: never direct in app code; test/diagnostic only (replay captured bytes, fuzz `next_event` to prove RemoteProtocolError handling).

### [read] flet-ads.md (421 lines)
- Apache-2.0 1.0.4, pins **`flet==1.0.4` HARD** (D-004 atomic bump pair); pure `py3-none-any` + bundled Dart plugin (`google_mobile_ads ^9.0.0`); 12-name export surface; **NativeAd dead on 3 counts**; 1.0.4 has NO rewarded/app-open/adaptive-banner; no patcher in wheel.
- API: `BaseAd` (unit_id required; events load/error/open/close/impression/click); `BannerAd` (fixed 320×50 `AdSize.banner` only; iOS-only on_will_dismiss; on_paid carries MICROS); `InterstitialAd` (single-show instance, load-coupled to attach, **static shared native slot → max ONE live instance**); `ConsentManager` 8 UMP methods; canonical launch = request_consent_info_update → load_and_show_consent_form_if_required → can_request_ads gate → load ads.
- Platform guard: `before_update` raises `FletUnsupportedPlatformException` on web+desktop → ALL ad surfaces need platform-availability placeholders under `flet run` (device truth = CI APK only).
- Android: APPLICATION_ID is OUR job via `[tool.flet.android.meta_data]` (no manifest patcher exists); needs only INTERNET + ACCESS_NETWORK_STATE (already our permission set).
- Plan posture: consent always at launch; interstitial only at natural breaks (install-complete / remove / return-to-list), never mid-terminal; banner reserved fixed row on NON-terminal screens only; `DebugGeography.EEA` + hashed test IDs from logcat in dev; `reset()` never in shipped paths.
- Unverified: resolved google_mobile_ads 9.x minor; exact missing-APPLICATION_ID failure text; targetSdk 35/36 behavior.

### [read] flet-platform-assets.md (453 lines)
- Apache-2.0 1.0.4; sole dep `pillow>=11.3.0`; build-host only (0 APK bytes); 27-name surface; **render pure / write impure** split; warnings are data (`RenderResult.warnings`).
- Mechanism: one `assets/icon.png` → iOS 15 files ALL opaque; macOS 7 (auto/grid/raw squircle); Android 5 mipmaps + 5 adaptive foregrounds; Windows multi-entry `.ico` (16/32/48/256); Linux hicolor 8 sizes + app_icon.png; web favicon/maskables/apple-touch. Splash: Android per-density + android12 (2/3-circle fit; icon_background shrinks canvas 288→240dp) + night + stale-FNS sweep; iOS 1x/2x/3x + dark + 1x1 swatch; web 4x light/dark.
- Rules: MAX_SOURCE_SIZE 2048 (one reduction); FRAMING shrink-only idempotent (tolerance 1.02); derived vs explicit `icon_<platform>.png` (explicit never reframed); hash-stamped skip; `declared_only` write guard.
- M5 config semantics: `icon_background` = PIXELS (flatten iOS/macOS/web-opaque; falls through to Android resource); `adaptive_icon_background` = colour RESOURCE only; splash `icon_background` = canvas-shrink only; key aliases (icon_bgcolor/icon_dark_bgcolor/android_12_fit) read for BC; splash platforms exclude macOS/Windows/Linux.

### [read] flet-desktop.md (270 lines)
- Apache-2.0 1.0.4; deps `flet==1.0.4` + `rich`; NEVER in APK; only `flet run`/`flet pack` use it.
- API: `ensure_client_cached()` (cache `~/.flet/client/flet-desktop-{flavor}-{version}[-fp]`; bundled archive + sha256 fingerprint sidecar else GitHub download — **no network checksum**; atomic rename; 30-day GC); `open_flet_view`/`open_flet_view_async`/`close_flet_view` (PID-file SIGKILL); artifact names per platform+flavor+distro; env knobs FLET_VIEW_PATH/FLET_CLIENT_URL/FLET_APP_ID/FLET_LINUX_DISTRO/FLET_DESKTOP_FLAVOR.
- Client resolution order: build output in CWD (warned — stale client lacks new extensions) → FLET_VIEW_PATH → cache.
- **Load-bearing (roadmap §1b):** prebuilt viewer has NO third-party Dart → flet-terminal / MobileTerminal / flet-ads can NEVER render under `flet run`; local dev shows placeholders, device truth from CI APKs only.

### [read] pillow.md (192 lines)
- MIT-CMU 12.3.0 compiled host wheel; arrives via dev group (flet-desktop → flet-platform-assets → pillow); never Android-resolved, 0 APK bytes.
- Toolchain contract: the 18 exact calls (open lazy → load → exif_transpose → seek(0) → convert RGBA; premultiplied RGBa LANCZOS single-step resample; alpha_composite/paste/putalpha; getchannel+extrema/bbox/histogram probes; GaussianBlur; `save(optimize=True)` deterministic; ICO multi-size supplied explicitly).
- Future in-app imaging shortlist (only if ever needed): open/load in try-catch, exif_transpose, contain/cover/fit for thumbnails, flatten-before-JPEG, decompression-bomb defaults. Stance: do NOT add Pillow to the Android closure.

### [read] oauthlib.md (481 lines)
- BSD-3 4.0.0; ~1 MB / 75 py files; no extras installed (no cryptography/jwt/blinker → noop fallbacks); flet floor `oauthlib>=3.2.2; platform_system != "Emscripten"` — upstream already ships configs without it.
- flet usage: EXACTLY 3 function-local `WebApplicationClient` imports in `flet/auth/authorization_service.py:93,120,208`; reachable only via `Page.login()` (deferred import — `import flet` never loads oauthlib); server/validator halves (~40 modules) dead under every scenario we'd ship.
- **Prune target (packaging)**: `[tool.flet.cleanup] package_files = ["oauthlib/**"]` (Sherlock precedent); breaks exactly Page.login() with loud ModuleNotFoundError; ~1 MB saved; re-add = one-line un-glob, no code change.

### [read] repath.md (166 lines)
- MIT 0.9.0; 8 KB single file; Express-pattern → regex; flet consumers = ONLY `components/router.py` (5× `repath.pattern`, `end=False` prefixes) + legacy `template_route.py`; needs six.
- **Keep unconditionally**: M3 navigation (`/distro/:name/...` params via Router) dies at import if removed; cleanup glob would save 8 KB — never worth it.

### [read] six.md (170 lines)
- MIT 1.17.0 frozen; 34 KB single file; repath's ONLY import (hard top-level); removal chain: prune both or neither; keep both (~43 KB) = entire routing foundation; on py3.14 all six usage resolves to stdlib names (zero behavior, hard import).

### [read] idna.md (341 lines)
- BSD-3 3.20 pure-Python; Unicode 18.0.0 tables ~283 KB; transitive via httpx/anyio; dormant (no OAuth → never imported at runtime).
- API: `encode(strict/uts46/std3_rules)`, `decode(..., display=True)` (WHATWG display recovery), alabel/ulabel, `IDNAError.code` = 26 stable machine codes (never regex the message); codec name `"idna2008"` (≠ stdlib `"idna"` 2003).
- Guidance: never import directly; if needed use `idna.encode(host, uts46=True)` (the anyio-tested form) and `decode(host, display=True)` for UI.

### [read] certifi.md (270 lines)
- MPL-2.0 2026.7.22; 240 KB cacert.pem (121 CAs); entire API = `where()` / `contents()`.
- httpx default `verify=True` → `cafile=certifi.where()` unless SSL_CERT_FILE/SSL_CERT_DIR + trust_env; httpcore `default_ssl_context` adds certifi on top of platform defaults.
- Android divergence (documented for M5/M6): pinned bundle ≠ Android system store; our endpoints (Docker Hub, GitHub, apt mirrors) are all public-CA = fine; private-mirror escape hatches = `verify=ssl.create_default_context(cafile=combined)` (supported form) or SSL_CERT_FILE (proot-distro urllib path **unverified** — test when/if a mirror lands); `verify=False` MUST NOT ship. CA updates ride version bumps only; emergency distrust needs an app update (accepted risk).

### [read] typing-extensions.md (223 lines)
- PSF-2.0 4.16.0; single 165 KB file; 121 exports; flet's load-bearing touch = `@dataclass_transform()` (base_control.py:91) — resolves to STDLIB on py3.14 (version-guarded import), so TE contributes shape, not runtime behavior here.
- Our code rule: py3.14 floor → default `typing`; TE only for names missing from 3.14; never pin tightly (hard dep of flet+anyio); no Android wheel needed.
- Value carried: typed control contracts at PR time; TypedDict/Protocol for facade seams; `assert_never` for install-job state exhaustiveness.

### [read] ruff.md (328 lines)
- MIT 0.17.1 binary; dev-only; commands check/format/rule/config/linter/clean/server/analyze; 59 rule families with the full Sherlock-vs-ffmpeg select matrix; unknown config key = **hard error** (verified) — renamed keys break loudly at gate time.
- Our target config: Sherlock select/ignores (`E F W UP B Q C4 PERF ERA I T20 DTZ RUF S TRY BLE EM A SIM RET RSE`; ignore `E501 EM101/102/103 TRY003 BLE001 S110 SIM105 TRY300 TRY301`; tests `S101`) + ffmpeg's `PTH` + `ASYNC`; `line-length = 100`; `target-version = "py313"` (importable by the Flet verifier); `required-version = "==0.17.1"` pin; CI = `check` + `format --check` before pytest.
- Default-selected rule set **unverified** in 0.17.1 CLI → always set `select` explicitly.

### [read] pytest.md (366 lines)
- MIT 9.1.1; complete fixture/marker/hook/ini inventory (41 ini keys); house targets: `pythonpath=["src"]`, `timeout=60`, `timeout_method="thread"`, `strict_config`+`strict_markers`, `live` marker registered, own-module warnings-as-errors; `[tool.pytest.ini_options]` vs `[tool.pytest]` mutually exclusive (UsageError).
- Uses carried into plan: `tmp_path` fake rootfs trees; `monkeypatch.setenv` + `delitem(sys.modules, "proot_distro...")` for hermetic re-import tests (env-before-import = documented contract, NOT patching upstream); `caplog`/`capsys`/`capfd` for stage-line + redirect_stderr assertions; `pytestconfig` parity guard tests (test_imports_vs_deps, version sync).
- Plugin-provided extras (anyio_backend, timeout marker) are NOT pytest builtins — don't document as such.
- House tooling adopt-list: test_imports_vs_deps.py-style guard, version-sync guard, FakePage/offline suite pattern.

### [read] pytest-timeout.md (222 lines)
- MIT 2.4.0; ini `timeout`/`timeout_method`/`timeout_func_only`/`session_timeout`; `PYTEST_TIMEOUT` env (env > ini > default); `timeout` marker with method/func_only/disable_debugger_detection.
- Windows default = thread, POSIX = signal → house PINS `thread` for CI parity; signal method is house-forbidden.
- Thread caveat: reports deadline + dumps ALL thread stacks but cannot preempt native blocks (directly relevant to future ProotSession spawn tests) → keep CI job timeout as real backstop; the stack dump IS the hang diagnosis.
- live tests: per-test `@pytest.mark.timeout(300, func_only=True)`; never disable globally.

### [read] pluggy.md (235 lines)
- MIT 1.7.0; pytest's hook engine; full `PluginManager` method table + HookspecOpts/HookimplOpts + `Result` API; `wrapper=True` is the new-style wrapper (legacy `hookwrapper` present but do-not-rely); `firstresult`/`historic` semantics; `_verify_hook` arg-checking = the "unexpected keyword" errors.
- Judgment: never instantiate PluginManager in our code; consume pluggy only through pytest (conftest fixtures cover every house need); value = correct wrapper hooks + ordering literacy.

### [read] iniconfig.md (100 lines)
- MIT 2.3.1; pytest's INI parser; `IniConfig.parse/get(..., convert=)` + `lineof()` line pinning; nothing to configure for us.
- Payoff: `strict_config` typo → startup failure naming file+line; DIAGNOSTIC knowledge for getini surprises; pyproject path is native TOML in pytest (exclusion rule lives there, not here).

### [read] packaging.md (145 lines)
- Apache-2.0 OR BSD-2-Clause 26.3; Version/SpecifierSet/Requirement/Marker + utils (`canonicalize_name`, `parse_wheel_filename`, …); pytest uses for `minversion`+`required_plugins`; flet-cli build metadata (call sites unverified).
- House uses: guard tests normalize names via `canonicalize_name`; `parse_wheel_filename` if M2 ever asserts Android wheel ABI tags; machine-checked floors = the "bump a version" path verified by tests.

### [read] colorama.md (107 lines)
- BSD 0.4.6; dev-only cosmetics (pytest Windows ANSI + flet-cli); `init/just_fix_windows_console/deinit`; zero config, zero APK bytes.
- `test_imports_vs_deps.py`: list as allowed transitive (pytest/flet-cli support), never a direct import.

### [read] watchdog.md (276 lines)
- Apache-2.0 6.0.0; the `flet run` hot-reload engine (run.py: Observer/schedule/start + 0.5 s debounce Handler + stop/join; `--recursive`, `--ignore-dirs`); platform dispatch inotify→fsevents/kqueue/winapi→polling; `watchmedo` CLI exists.
- Posture: dev-loop only — use via `flet run`; NEVER add to dependencies, never in-app (Android has no use; polling burns battery); Linux `ENOSPC` → host inotify-limit tuning, not app code.

### [read] qrcode.md (202 lines)
- BSD 8.2 pure-Python; transitive via flet-cli for device-connect ASCII QR (`print_ascii(invert=True)`; android.flet.dev / flet:// URLs).
- Gotcha: `ERROR_CORRECT_M == 0` (non-alphabetical constant values).
- Verdict: dev flows only — NO in-app QR screen (no Flet QR widget; would add qrcode+pillow runtime deps for a niche); optional `tools/print_qr.py` for harness URLs in M0/M5 rituals reusing the 3-line pattern.

### [read] cookiecutter.md (573 lines)
- BSD 2.7.1; flet-cli build path calls `cookiecutter(template=local cached zip, checkout=flet_version, directory=subdir, output_dir=…/build/<platform>/flutter, no_input=True, overwrite_if_exists=True, extra_context=template_data minus None)`; flet's OWN template fetch = stdlib urllib (`template_cache.py`) → cookiecutter only unzips locally for builds.
- Traps that bite us: top-level unknown `extra_context` keys are **silently ignored** (every key must exist in the template's cookiecutter.json — CI should diff template_data keys per flet bump); context must be JSON-serializable (`replay.dump` every run); `StrictUndefined` (missing key = hard fail; None stripped by flet); **hooks EXECUTE at build time** (`accept_hooks` default True) and pre_prompt can copy the repo — trust boundary.
- Trust-boundary actions for M5: pin `template_ref = flet_version` (default), forbid custom `--template/--template-ref/--template-dir` in release workflows, consider pre-seed + `sha256` verify of `flet-build-template.zip` (cache has NO checksum; path `<FLET_CACHE_DIR>/build-template/v<version>/`), log template source+ref, ephemeral runners.
- `template_data` key inventory (the contract with cookiecutter.json): bundle_id, org_name, project_name(+slug/description), product_name, artifact_name, python_module_name, route_url_strategy, boot_screen, splash, adaptive_icon_background, android_signing, legacy_packaging, options{android_permissions, android_meta_data, android_features, deep_linking, target_arch, split_per_abi, …}, flutter{dependencies}, pyproject.

### [read] requests.md (403 lines)
- Apache-2.0 2.34.2; arrives ONLY via cookiecutter (remote-zip templates) on the HOST; NEVER in APK (dev-group only; uv.lock subtree; on-device downloader is stdlib `urllib.request` in `proot_distro/helpers/download.py:42-44`).
- Snapshot: Session defaults (max_redirects 30, trust_env on, ordered adapters, verify=certifi); **HTTPAdapter default max_retries=0** (opt-in Retry); `apparent_encoding` currently resolves via chardet 5.2.0 (binaryornot brought it) — behavior note, not a bug.
- House call: new tooling on httpx; requests stays indirect. If used: always `timeout=`, Session-as-context-manager, explicit Retry adapter for registry polling, never `verify=False` off-localhost.

### [read] urllib3.md (363 lines)
- MIT 2.8.0; requests' engine; same host-only guarantee chain; OpenSSL 1.1.1+ import floor = free CI hygiene.
- `Retry` full knob table (total/connect/read/redirect/status/other; `allowed_methods` — `method_whitelist` GONE in 2.8.0; status_forcelist; backoff_factor + backoff_jitter; respect_retry_after_header; retry_after_max 21600; remove_headers_on_redirect defaults strip Cookie/Authorization/Proxy-Authorization = credential-leak protection on GitHub→S3 redirects).
- Trap: urllib3 `Retry.DEFAULT = Retry(3)` but requests zeroes it — must OPT IN via adapter (documented).
- Sanctioned direct use: `from urllib3.util.retry import Retry` in release-asset/registry polling adapters only; never touch connectionpool internals; bump with the group (`urllib3<3`).

### [read] charset-normalizer.md (223 lines)
- MIT 3.5.2; compiled `.pyd` + .py fallbacks; hard dep of requests; in our venv chardet 5.2.0 wins at runtime (requests tries chardet FIRST), CN is the pinned fallback; both satisfy requests' `check_compatibility`.
- API: `from_bytes/from_fp/from_path/is_binary` + `CharsetMatch` (chaos/coherence/languages/output/alpha_extents) + `CharsetMatches.best()`; legacy `detect()` shim w/ `CHARDET_CORRESPONDENCE` rename map.
- Guidance: don't add direct uses; explicit UTF-8 everywhere for OUR bytes; guessing only for third-party text (`is_binary()` gate + `best()` + chaos check). Pin `<4`, bump with requests group.

### [read] rich.md (419 lines)
- MIT 15.0.0; terminal render engine; deps markdown-it-py + pygments; no `__version__` attribute; Console → Segment pipeline.
- flet-cli usage quoted: shared Console + Theme + `Progress(transient=True)` + Live/Group/Panel in flutter_base; per-command imports (build/create/clean/debug/emulators/serve/test); **`--no-rich-output` mechanism** (checks `sys.argv` + FLET_CLI_NO_RICH_OUTPUT env BEFORE console build; kills spinner flood/emoji/Live in CI).
- House rule: always `--no-rich-output` in GitHub Actions so build logs stay greppable; rich animations local-only.
- Utilization: optional `tools/build_report.py` (Table/Panel/filesize.decimal); never in APK.

### [read] markdown-it-py.md (226 lines)
- MIT 4.2.0; CommonMark+extensions parser (port of markdown-it); sole dep mdurl (~0.1); linkify/pygments extras NOT installed.
- API: `MarkdownIt(config="commonmark"|"default"|"zero", renderer_cls=RendererHTML)`; `parse/render/enable/disable/use/set/configure/validateLink`; Token model (nesting/-1|0|1; inline children); rule trees enumerated; presets differ mainly in html/xhtmlOut.
- rich Markdown builds its own parser `MarkdownIt().enable("strikethrough").enable("table")` — linkify/typographer NEVER active in rich; fence → `Syntax(...)` = the pygments bridge.
- Two tracks: (A) host-side doc rendering/lint now (free with rich); (B) in-app markdown rendering = possible (pure-Python) but needs an owned Token→ft.Markdown mapper + APK weight — explicit M4 plan-mode proposal, not a decision.

### [read] mdurl.md (126 lines)
- MIT 0.1.2; zero deps; encode/decode/parse/format/URL (NamedTuple: protocol, slashes, auth, port, hostname, hash, search, pathname; NO `.host`/`.href`).
- `encode(s, ENCODE_COMPONENT_CHARS)` = correct single-segment encoding (safer than `urllib.parse.quote`). Moves with markdown-it-py (ceiling `mdurl~=0.1`).

### [read] pygments.md (175 lines)
- BSD-2 2.21.0; pure-Python; 602 lexers / 18 formatters / 51 styles; zero deps (colorama only on windows-terminal extra).
- rich bridge: `Syntax(code, lexer)` → `get_lexer_by_name`/`guess_lexer_for_filename`; theme string → `get_style_by_name` (fallback "default"); formatters NOT used in terminal rendering.
- Track A (free via rich): highlighted dev-script output/build reports/tracebacks. Track B (M4 option): syntax-highlighted guest-file preview — pure-Python so mechanically Android-OK, but LARGE; decide in M4 plan mode w/ APK-size measurement; options = ship whole / cleanup-glob strip (fragile, dynamic imports) / host-side pre-render.

### [read] binaryornot.md (66 lines)
- BSD 0.4.4; 4 functions total (`is_binary(path)`, `get_starting_chunk`, `is_binary_string` chardet-fallback heuristic, `print_as_hex`); cookiecutter uses `is_binary` to copy binary template files WITHOUT Jinja render (`generate.py:221`) — that's what preserves icons/blobs in flet builds.
- M3 use: the text/binary gate for the import/export viewer (decode-and-show vs save/share path). Do NOT vendor (chardet LGPL); if on-device needed reimplement the ratio check or depend on binaryornot.

### [read] chardet.md (54 lines)
- LGPL 5.2.0 — **never vendor**; API `detect`/`detect_all`/`UniversalDetector`; second stage of binaryornot's probe.
- M3 use: decode-codec picker for guest files in unknown locales — trust confidence >0.8 else UTF-8 + errors="replace" and say so in UI.

### [read] arrow.md (64 lines)
- Apache-2.0 1.4.0; deps dateutil + tzdata; `arrow.now(tz)/utcnow/get`; `Arrow.shift/**` powers cookiecutter `{% now %}` offsets; `format("YYYY-MM-DD HH:mm:ssZZ")`, `humanize()`.
- M4/M5: all app-displayed timestamps (install history, session logs, report headers) + retention windows via `shift`; keep arrow+dateutil+tzdata bumped as a group; on Android the tz DB comes from THIS chain, not the OS.

### [read] python-dateutil.md (64 lines)
- Dual BSD-3/Apache-2.0 2.9.0.post0; arrow's parser/tz engine; `parse` (free-form) vs `isoparse` (strict ISO — prefer for machine stamps); `relativedelta` (month-aware retention math); `rrule` (schedules); `tz` helpers.
- Rule: `isoparse` for machine-generated, `parse` only for human/guest text.

### [read] tzdata.md (53 lines)
- Apache-2.0 2026.5 (IANA 2026e); data-only; consumed by stdlib `zoneinfo.ZoneInfo`; Android ships no usable IANA DB to Python → this chain gives deterministic local-time/DST across devices; bump with arrow group.

### [read] click.md (69 lines)
- BSD-3 8.5.0; 74 names; `__version__` deprecated (use importlib.metadata); ceiling `click<9`.
- FIRST-CLASS house tooling pattern: our `tools/` CLIs (build_proot_wheel, check_apk_alignment, future manifest-lint) use `@click.group` + `Path(exists=True)` + `secho` gates + `confirmation_option` for destructive ops; one entry-point group per repo documenting the whole device-test/CI ritual.

### [read] jinja2.md (74 lines)
- BSD 3.1.6; deps MarkupSafe>=2.0; ceiling `<4`; `StrictUndefined` = cookiecutter fail-closed; loaders; 5 cookiecutter extensions; `select_autoescape` lives in `jinja2.utils` (top-level import fails).
- M3/M5: our distro/profile templates (install manifests, shell profiles, MOTD with `{{ arch }}`/`{% now %}`) rendered with StrictUndefined; DictLoader for inline tests.

### [read] markupsafe.md (56 lines)
- BSD-3 3.0.4; `Markup(str)` + `escape/escape_silent/soft_str`; on Android the pure-Python `_native.py` fallback path (no wheel needed).
- Rule: any HTML we render (error dialogs with guest output, report pages) escapes untrusted guest strings by construction; never `Markup(untrusted)`.

### [read] pyyaml.md (90 lines)
- MIT 6.0.3; C bindings on host; THE serialization format: cookiecutter config + flet-cli pubspec read/patch (`build_base.py:3615-3639`) + OUR catalog/manifest sidecars.
- Rules: always `safe_load` + `except yaml.YAMLError`; `sort_keys=True, allow_unicode=True` on dump for stable diffs; manifest layer for our distro catalog and per-image metadata.

### [read] python-slugify.md (67 lines)
- MIT 9.1.3; `slugify(...)` full signature; `slugify_unicode` does NOT exist in 9.x; backend 'auto' tries unidecode → text-unidecode; pure-ASCII skips the ~3 MB table import.
- M3 use: every user-typed container/profile name → filesystem/OCI-safe identifier (friendly "My Debian Dev" → `my-debian-dev`); keep `allow_unicode` off unless the consumer provably accepts it.

### [read] text-unidecode.md (54 lines)
- Artistic License 1.3; single function `unidecode(txt)`; ~3 MB table (why ASCII skips it); slugify's auto-backend fallback in our venv (no standalone unidecode installed).
- Caveat: the 3 MB table ships wherever slugify's non-ASCII path ships — build-host fine; measure APK delta before any on-device slug use. Always call through `slugify(..., backend=...)`, not direct import.



### [read] compliance/licensing.md (721 lines)
- GPL-2.0 (proot+loader) / GPL-3.0 (talloc) / GPL-3.0-only (proot-distro) shipped in-APK; permissive rest; dev-only trees never ship (ported into roadmap §M5/M6). FSF FAQ quotes + 3 options (A=license app GPL = only fully-supported option; B=process-separate UNVERIFIED; C=community practice UNVERIFIED). Source-offer mechanics: GPL-3 §6(d) network + §6(b) written offer; GPL-2 §3(a)/(b) (3(c) unavailable — commercial via AdMob). Checklist A1–A10 (A8 = counsel + Option A/B at M3 plan mode; A6 = flet-terminal license metadata in M1; A9 = download-size consent in install flow). UNVERIFIED ledger 11 items.

### [read] compliance/distro-images.md (368 lines + reconstructed tail)
- Per-image licensing/trademark table (Ubuntu/Debian/Alpine certified; Kali/Arch/Fedora custom-ref notes; Fedora strictest). Docker Hub ToS quotes + rate limits (100/6h anon per IPv4, 200 personal): per-device pulls self-limiting; no central proxy; optional PD_DOCKER_AUTH token; per-distro registry field. Guest archives = designed workload; pre-upgrade default OFF; refresh only on user action. §1.3 attribution copy block. **Tail §3.2(2)–§7 RECONSTRUCTED after truncation defect** (digest-pinned certified defaults, UI wording rules, checklist B1–B7, UNVERIFIED ledger).

### [read] compliance/play-policy.md (393 lines)
- DNA policy quotes: rootfs = user data (3-pronged argument + UserLAnd/Termux/Andronix live precedent); zero dex/JAR/.so downloaded; apt-in-guest indistinguishable from a browser. targetSdk 36 mandatory post-2026-08-31; 16 KB pages (our CI already proves 0x4000); 64-bit; AAB; upload-key RSA-2048 + Play App Signing. Data safety form ~90% AdMob (transcribe from SDK Index at M5). AdMob placement: NO banner on terminal (interactive-content rule); interstitials at natural breaks; UMP one-to-one with our ConsentManager. FGS default NO (types list; decision at M4). Checklist A-1–A-16. UNVERIFIED ledger 6 items.

### [read] docs/reference/* (16 files, 391 lines) + core docs re-read (roadmap.md, decisions.md, m0-checklist.md, testing-findings.md)
- House standards: Sherlock (service-per-lib, controller bridge, keep-alive refcount rule, render flusher ~2 Hz, cleanup globs incl. oauthlib/**), DDGS (floor pins, honest-import test, prerelease-always), CollabShell (notebook I/O spec, stdin hook, terminal wiring, offline test templates; remote-PTY = view proof only), FFmpeg (two-artifact Forge shape, probe-gating, extract_packages rule, 6 CI drifts to fix in ours), Data Formulator (sole-importer + constructor injection + Android compile proof).
- M1 basis: flet-terminal blueprint + MobileTerminal renderer-context landmine (works inside component trees — our M3 AppShell does) + latent refresh_buttons bug.
- Milestone plan integrated into roadmap.md; m0-checklist gained the apt investigation arc (retests #4–#6: backup-link fix → chown ENOENT open bug → spike-10 Termux argv + --no-upgrade + G4b; CI green 38939581051; device retest pending).
