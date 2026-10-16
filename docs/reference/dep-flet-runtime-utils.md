# dep-flet-runtime-utils.md — msgpack / oauthlib / repath / six

Verified 2026-10-16 against `.venv/Lib/site-packages` (R3 study).

## msgpack 1.2.3 (Apache-2.0) — CRITICAL, load-bearing every session
- flet's **Python↔Dart wire protocol** (`messaging/flet_dart_bridge_server.py`, `protocol.py` — every control update and keystroke crosses it). Loads when a session starts, not at cold import.
- C extension with pure-Python fallback (`MSGPACK_PUREPYTHON`).
- **Android wheel trap**: pypi.flet.dev ships msgpack Android wheels only for **1.1.x** (incl. `msgpack-1.1.2-1-cp314-cp314-android_24_arm64_v8a.whl`), NOT 1.2.3 (desktop-only). flet's spec is `msgpack>=1.1.0` → **never pin ≥1.2.0 anywhere in this project**; keep it floating so the mobile resolver settles on 1.1.2 while desktop keeps 1.2.3.

## oauthlib 4.0.0 (BSD-3-Clause) — prunable
- Direct flet dep; imported lazily only inside `flet/auth/authorization_service.py`. Reachable only via `Page.login()`.
- Our app has no login flow → mirror Sherlock's cleanup glob **`oauthlib/**`** (breaks only `Page.login()` — documented, verified safe). Pure-Python; no Android wheel needed.

## repath 0.9.0 + six 1.17.0 (MIT) — tiny, keep
- `repath` compiles route templates for flet's Router/TemplateRoute (used only if we route); `six` is its import-time dep — prune one and the other breaks. Both single-file pure Python (~170 KB total incl. six).

## Umbrella note
None of these four are on pypi.flet.dev, and none need to be — pure universal wheels ride in as source. The only build-risk item in the whole cluster is the msgpack pin rule above.
