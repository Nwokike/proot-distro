# noVNC — vendored viewer

| | |
|---|---|
| Upstream | noVNC 1.7.0 (https://github.com/novnc/noVNC) |
| Vendor script | `scripts/fetch_novnc.py` |
| Served by | `services/desk_service/stream_server.py` (`/novnc/…`, verbatim) |

## Rule: upstream verbatim

The viewer is **not** maintained here. `fetch_novnc.py` copies the upstream tree
(`vnc.html`, `app/`, `core/`, `vendor/`) and writes only a deployment
`defaults.json` (`resize=remote`, `reconnect=true`, `reconnect_delay=3000`).
Keyboard, clipboard panel, extra keys, scaling and reconnect are upstream's own
UI; the server adds nothing to the page.

## How it is wired

- `/` validates the session access code, then 302s to
  `/novnc/vnc.html?autoconnect=1&path=/websockify?code=…&quality=…&compression=…
  &resize=…&bell=…&show_dot=…&logging=…&view_only=…`.
- `/websockify` proxies the WebSocket to Xvnc's RFB port (TCP_NODELAY,
  compress=False, bounded messages, heartbeat).
- `vnc.html` revalidates (upstream requirement); `app/` assets are cacheable
  (they only change with an APK build).

## Update procedure

1. Bump `NOVNC_VERSION` and `TARBALL_SHA256` in `scripts/fetch_novnc.py`.
2. `uv run python scripts/fetch_novnc.py` and commit the refreshed tree.
3. Verify: `tests/test_wheel_builders.py` (vendored file set),
   `tests/test_xvnc_runtime.py` (viewer URL settings).
4. Device-check: viewer loads, keyboard opens, clipboard works, settings panel
   reads quality/compression.
