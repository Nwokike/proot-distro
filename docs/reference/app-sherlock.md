# app-sherlock.md — Sherlock (production standard)

Verified 2026-10-16 against `/home/maikel/.zcode/workspace/default/Sherlock`.

## Identity
`sherlock` v2.3.0 build 13, Python 3.14, repo Nwokike/Sherlock. Wraps `maigret 0.6.6`, `holehe-v2 1.0.3`, `socid-extractor 0.1.1` (+ transitive curl-cffi/reportlab/xmind/networkx pulled by袅 eigret). Product "Sherlock", org `ng.kiri`, bundle `ng.kiri.sherlock`.

## Dependencies (pin policy = the one to copy)
Loose floors in pyproject + exact in `uv.lock` + `uv sync --frozen` in CI:
`flet>=1.0.4`, `flet-ads>=1.0.4`, `flet-notifications>=0.1.4`, `holehe-v2>=1.0.3`, `httpx[http2,socks]>=0.28.1`, `maigret>=0.6.6`, `socid-extractor>=0.1.1`; dev: `pytest>=9.1.1`, `pytest-timeout>=2.4`, `ruff>=0.15.14`. Updates = version-bump only (`uv add` only, never hand-edit).

## Wrapping pattern (multi-lib house standard)
- **One service per upstream lib**, controller owns instances, screens stay thin:
  - `SherlockService` (maigret): import-availability flag, worker thread + private event loop, `search(username, on_progress, timeout, after_primary)`, `cancel()`.
  - `EmailService` (holehe): deliberately does NOT use upstream `run_all()` — drives each `validate_*` itself under a semaphore; classifies status.
  - `EnrichService` (socid-extractor): `asyncio.to_thread` + `anyio.CapacityLimiter(12)`, per-host `Semaphore(2)`.
- AppController constructs all services (`src/main.py`); exposes via `ControllerMethods` dataclass with `_noop_*` defaults (`src/state/controller_ctx.py`); `AppShell` single-view; `@ft.observable AppState`.
- **Service keep-alive (correctness-critical, replicate)**: Flet drops services with refcount ≤3 after every event → `page.services.append(...)` + `mount_shared_services` once.
- **Render flusher**: ~2 Hz flush + 500 ms progress coalescing — Flet has zero batching; without it long progress streams freeze the app.

## Patch/override audit (owner treats these as smell)
1. `[tool.flet.flutter.pubspec.dependency_overrides] jni = "1.1.0"` — build-blocking upstream workaround; **likely stale at flet 1.0.4 — verify by CI-branch removal test before carrying anywhere**.
2. `_SilentBar` monkeypatch of `maigret.checking.alive_bar` — **FATAL on mobile** (alive_progress reads a file inside site-packages.zip → Errno 20). Direct runtime patch = rule violation; avoid needing this class of fix.
3. `aiohttp.TCPConnector.__init__` monkeypatch (perf only, removable).
4. Zip-safe validator loader replacing upstream Path-glob loader (fatal on mobile, reimplementation not edit).
5. `ContextVar` TLS-fingerprint wrapper (best-effort, passthrough args).
6. `_resolve_local_db()` materializing package data via `pkgutil.get_data` (fatal on mobile; transferable pattern).
7. `flet-notifications-patch` 3-phase CI build (Gradle desugaring + receivers + foreground service) — **the heaviest build complication in the house; do not inherit unless the feature is truly needed**.

## Config/CI/tests worth copying
`[tool.flet]` org/product/company/build_number/icon + boot_screen message + android bundle_id/perms/meta_data/signing + `cleanup.package_files` (audited globs incl. `oauthlib/**`). CI: quality (version-consistency script across pyproject/constants/version.json/workflow, ruff, `pytest -m "not live"`) → placeholder release → parallel apk-split/aab/windows/linux jobs; keystore only via `FLET_ANDROID_SIGNING_*` secrets. pytest: `pythonpath=["src"]`, `timeout=60`, strict markers/config, own-module warnings as errors. Ruff: richest set (E,F,W,UP,B,Q,C4,PERF,ERA,I,T20,DTZ,RUF,S,TRY,BLE,EM,A,SIM,RET,RSE) with commented ignores.

## Transferable checklist for proot-distro
src layout `{main.py, app_shell.py, core/, state/, services/, components/, screens/, hooks/}` + `tests/{conftest.py(FakePage), flet_tree.py}`; observable state + controller bridge + keep-alive services + render flusher; JSON KV storage with atomic replace + flush on lifecycle events; `version.json` + update service + changelog; ads service with UMP + interstitial interval; cleanup globs audited to the real tree (ours: near-zero — only `oauthlib/**`).
