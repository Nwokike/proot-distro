# dep-flet.md — flet 1.0.4 (core)

Verified 2026-10-16 against `.venv/Lib/site-packages/flet` (R1 study).

## Identity
Version `1.0.4` (`flet/version.py:19`); Apache-2.0 (no LICENSE file ships in dist-info); `py3-none-any`, **pure Python** (279 files, ~2.6 MB, zero `.so`) — rendering lives in flet-desktop/flet-web (lazy-installed extras) or the Flutter client baked at `flet build` (Flutter **3.44.8** pinned). `Requires-Python >=3.10`.

## Public API our app uses
- Lazy re-export: `flet/__init__.py` is a name→module map resolved by `__getattr__`; `ft.run`/`ft.run_async` → `flet.app`; `Page` = `@control("Page", isolated=True)`.
- `ft.run()` = `asyncio.run(run_async())`; transport on Android = **embedded dart_bridge** (`FLET_PLATFORM=android`, `FLET_DART_BRIDGE_PORT`), with `_swap_to_port` handling Android process reuse (Dart VM restarts with fresh ports).
- `Service` classes auto-register on the current page (`Service.__post_init__` → `page._services.register_service`); registry prunes by refcount after every event (`session.py:570`) — the CollabShell/Sherlock rule to keep them alive is `page.services.append(...)`.

## Extension mechanism (source of the flet-terminal hatch)
- **No `_get_control_name` in 1.0** — extensions are just `import flet` + `@ft.control("Name")` subclass; the decorator writes `_c` (the wire type discriminator used by the MsgPack protocol). **No registration, no entry points, no manifest in the flet package.**
- Flutter-side discovery is NOT in flet: each extension wheel ships `site-packages/flutter/flet_<name>/` (pubspec + lib/) and **flet-cli** collects those dirs into the generated project at build time.
- Consequence: **under `flet run` (prebuilt clients) extension widgets cannot render** — see `../testing-findings.md`.

## Dependencies + lockstep danger
Only 4 hard runtime deps: `oauthlib`, `httpx` (both dropped on Emscripten), `repath`, `msgpack`; `typing-extensions` (marker). flet-cli/web/desktop are extras pinned `==1.0.4`, and `flet/utils/pip.py` **auto-`pip`-reinstalls them on ANY version mismatch at startup** → keep the whole flet family lock-stepped; never let a second flet version leak into the app env.

## Risks noted for us
Headless-Linux forces web transport (`is_linux_server()`) — relevant to desktop dev only; env vars (`FLET_SERVER_PORT/IP/UDS_PATH/FORCE_WEB_SERVER/DART_BRIDGE_PORT`) silently change transport — audit the environment if we ever wrap proot around a *flet-in-flet* scenario; `StoragePaths` etc. are client-implemented `_invoke_method` stubs — storage behavior is validated on the built APK, not in Python source.
