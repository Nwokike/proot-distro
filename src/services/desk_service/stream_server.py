"""Per-session stream server — the whole "websockify" in one handler.

Serves the VENDORED UPSTREAM noVNC viewer (vnc.html + app/, verbatim — no
viewer code is maintained here) and proxies its single WebSocket straight to
Xvnc's RFB port on loopback: RFB is a byte stream, so the proxy is transparent
(no protocol parsing). The 6-char access code gates the WebSocket upgrade —
upstream's page carries it inside the `path` setting (upstream builds the
WebSocket URL from `path` verbatim, query string included), so the same code
gates loopback, LAN and tunnel clients without forking the viewer.
"""

from __future__ import annotations

import asyncio
import logging
import socket
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

logger = logging.getLogger(__name__)

_NOVNC_DIR = Path(__file__).parent / "novnc"
# vnc.html must revalidate; app/ only changes with an APK build, so it caches.
_NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}
_APP_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}
_WS_MAX_MSG = 64 * 1024  # inbound RFB messages (pointer/key/clipboard) are tiny
_WS_HEARTBEAT = 25.0  # dead viewers are dropped instead of lingering
_WRITE_HIGH_WATER = 512 * 1024  # drain only when the buffer passes this


class DisplayStreamServer:
    """One session's HTTP+WS surface. `start()` returns after binding — the
    manager never calls run()."""

    def __init__(
        self,
        host: str,
        port: int,
        rfb_port: int,
        code: str,
        quality: int = 6,
        compression: int = 2,
        resize_mode: str = "remote",
        bell: bool = True,
        show_dot: bool = False,
        logging_level: str = "warn",
        view_only: bool = False,
    ):
        self.host = host
        self.port = port
        self.rfb_port = rfb_port
        self.code = code
        # noVNC's own client settings (upstream reads ?key=value verbatim).
        self.bell = bell
        self.show_dot = show_dot
        self.logging_level = (
            logging_level if logging_level in ("error", "warn", "info", "debug") else "warn"
        )
        self.view_only = view_only
        self.quality = max(0, min(9, int(quality)))
        self.compression = max(0, min(9, int(compression)))
        # noVNC's own `resize` setting: remote (server follows the viewport),
        # scale (local letterbox), off (pan/scroll the framebuffer).
        self.resize_mode = resize_mode if resize_mode in ("remote", "scale", "off") else "remote"
        self._runner: web.AppRunner | None = None

    def viewer_query(self) -> str:
        """The viewer settings shared by the local URL and the `/` redirect —
        one builder, so a LAN/tunnel open never drops a setting."""
        return (
            f"autoconnect=1&path={quote(f'/websockify?code={self.code}', safe='')}"
            f"&quality={self.quality}&compression={self.compression}"
            f"&resize={self.resize_mode}"
            f"&bell={'on' if self.bell else 'off'}"
            f"&show_dot={'true' if self.show_dot else 'false'}"
            f"&logging={self.logging_level}"
            f"&view_only={'true' if self.view_only else 'false'}"
        )

    def local_url(self) -> str:
        """Upstream's viewer URL. `quality`/`compression`/`resize`/`bell`/
        `show_dot`/`logging`/`view_only` are upstream's own setting names; the
        access code rides inside `path` (noVNC builds the WebSocket URL from it
        verbatim — verified in app/ui.js `UI.connect`)."""
        return f"http://127.0.0.1:{self.port}{self.viewer_path()}?{self.viewer_query()}"

    def viewer_path(self) -> str:
        """The upstream page's URL path (served verbatim under /novnc/)."""
        return "/novnc/vnc.html"

    def _build_app(self) -> web.Application:
        """The session's HTTP surface (extracted so tests can bind it with
        aiohttp's TestServer)."""
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/health", self._health)
        app.router.add_get("/novnc/{tail:.*}", self._static)
        app.router.add_get("/websockify", self._websockify)
        return app

    async def start(self) -> None:
        self._runner = web.AppRunner(self._build_app(), access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
        self._runner = None

    # ── handlers ──────────────────────────────────────────────────────────────

    async def _health(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True})

    async def _index(self, request: web.Request) -> web.Response:
        """`/` is the shared entry point (the URL the app hands out): it gates
        the access code, then forwards to the upstream viewer with the code
        inside `path`. A missing/wrong code never reaches the viewer."""
        code = request.query.get("code", "")
        if code != self.code:
            raise web.HTTPForbidden(
                text="missing or invalid access code — open the full URL from "
                "the app's Share dialog"
            )
        raise web.HTTPFound(f"{self.viewer_path()}?{self.viewer_query()}")

    async def _static(self, request: web.Request) -> web.FileResponse:
        root = _NOVNC_DIR.resolve()
        path = (root / request.match_info["tail"]).resolve()
        if not str(path).startswith(str(root)) or not path.is_file():
            raise web.HTTPNotFound
        # Upstream's deployment requirement: revalidate the entry page, or a
        # The app/ JS itself ships with the APK and only changes on update.
        cacheable = path.suffix in (".js", ".css", ".woff2", ".png", ".svg")
        return web.FileResponse(
            path, headers=_APP_CACHE_HEADERS if cacheable else _NO_CACHE_HEADERS
        )

    async def _websockify(self, request: web.Request) -> web.WebSocketResponse:
        # RFB payloads are already compressed by the server's encodings;
        # permessage-deflate (aiohttp's default) re-compresses every frame and
        # costs CPU on both sides. Bounded inbound messages keep pointer/key
        # traffic from being able to balloon memory.
        ws = web.WebSocketResponse(
            compress=False,
            max_msg_size=_WS_MAX_MSG,
            heartbeat=_WS_HEARTBEAT,
        )
        await ws.prepare(request)
        if request.query.get("code", "") != self.code:
            await ws.close(code=4401, message=b"bad access code")
            return ws
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", self.rfb_port)
        except OSError as exc:
            logger.warning("RFB connect failed on %d: %s", self.rfb_port, exc)
            await ws.close(code=1011, message=b"the display server is not reachable")
            return ws

        # Loopback Nagle delays small RFB messages (pointer/key) by up to ~40 ms.
        sock = writer.get_extra_info("socket")
        if sock is not None:
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError as exc:
                logger.debug("TCP_NODELAY failed: %r", exc)

        async def ws_to_tcp() -> None:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    writer.write(msg.data)
                    transport = writer.transport
                    if (
                        transport is not None
                        and transport.get_write_buffer_size() > _WRITE_HIGH_WATER
                    ):
                        await writer.drain()
                elif msg.type in (
                    web.WSMsgType.CLOSE,
                    web.WSMsgType.CLOSING,
                    web.WSMsgType.ERROR,
                ):
                    break

        async def tcp_to_ws() -> None:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                await ws.send_bytes(chunk)

        try:
            await asyncio.gather(ws_to_tcp(), tcp_to_ws())
        except ConnectionError, asyncio.CancelledError:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError, OSError:
                pass
            await ws.close()
        return ws
