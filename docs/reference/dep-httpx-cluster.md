# dep-httpx-cluster.md — httpx / httpcore / h11 / anyio / idna / certifi / typing-extensions

Verified 2026-10-16 against `.venv/Lib/site-packages` (R2 study). All **pure-Python**, all ship unmodified into the APK.

| Package | Version | License | Parent | Role here |
|---|---|---|---|---|
| httpx | 0.28.1 | BSD-3-Clause | flet (direct, `platform_system != "Emscripten"`) | flet's OAuth HTTP client |
| httpcore | 1.0.9 | BSD-3-Clause | httpx | connection pooling / HTTP state machines |
| h11 | 0.16.0 | MIT | httpcore | HTTP/1.1 state machine |
| anyio | 4.15.1 | MIT | httpx | async abstraction (asyncio backend in practice) |
| idna | 3.20 | BSD-3-Clause | httpx/anyio | IDN hostname encoding (~283 KB Unicode tables) |
| certifi | 2026.7.22 | MPL-2.0 | httpx/httpcore | Mozilla CA bundle, 240 KB |
| typing-extensions | 4.16.0 | PSF-2.0 | flet + anyio | `dataclass_transform` used EVERY app launch |

## Key facts
- **The whole cluster except typing-extensions is dormant unless the app uses `flet.auth` OAuth** — flet imports httpx only inside `auth/` methods (lazy). No OAuth flow in our app → zero runtime cost, but they're hard deps and still packaged.
- httpcore ships mirrored sync/async trees; only async is reachable (sync half is dead weight on device).
- **certifi = build-time-pinned Mozilla bundle, not the Android system trust store** — OS-level CA changes are invisible to httpx calls (fine for public endpoints).
- anyio reaches a CPython private (`asyncio.base_events._run_until_complete_cb`) — the only spot coupled to interpreter internals; only a Python major bump in the build recipe could bite.
- pypi.flet.dev returns Not Found for all of them — **normal**: the index hosts only wheels needing Android-native builds; pure `py3-none-any` wheels resolve from PyPI. No action required.
