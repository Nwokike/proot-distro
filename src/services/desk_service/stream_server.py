"""Per-session stream server — the whole "websockify" in one handler.

Serves the vendored noVNC viewer and proxies its single WebSocket straight to
Xvnc's RFB port on loopback: RFB is a byte stream, so the proxy is transparent
(no protocol parsing). The 6-char access code gates the WebSocket upgrade, which
is what LAN/tunnel clients must present; loopback clients get it in the URL the
same way the old viewer got it injected.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiohttp import web

logger = logging.getLogger(__name__)

_NOVNC_DIR = Path(__file__).parent / "novnc"


class DisplayStreamServer:
    """One session's HTTP+WS surface. `start()` returns after binding — the
    manager never calls run(), mirroring how TermuxDeskServer was driven."""

    def __init__(
        self,
        host: str,
        port: int,
        rfb_port: int,
        code: str,
        quality: int = 6,
        compression: int = 2,
    ):
        self.host = host
        self.port = port
        self.rfb_port = rfb_port
        self.code = code
        self.quality = max(0, min(9, int(quality)))
        self.compression = max(0, min(9, int(compression)))
        self._runner: web.AppRunner | None = None

    def local_url(self) -> str:
        return (
            f"http://127.0.0.1:{self.port}/"
            f"?code={self.code}&quality={self.quality}&compression={self.compression}"
        )

    def _build_app(self) -> web.Application:
        """The session's HTTP surface (extracted so tests can bind it with
        aiohttp's TestServer)."""
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/health", self._health)
        app.router.add_get("/auth", self._auth)
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

    async def _auth(self, request: web.Request) -> web.Response:
        """The code pre-check the page does before opening the WebSocket (the
        WebSocket upgrade itself re-checks — this is the friendly path)."""
        if request.query.get("code", "") != self.code:
            raise web.HTTPForbidden
        return web.json_response({"ok": True})

    async def _index(self, _request: web.Request) -> web.FileResponse:
        return web.FileResponse(_NOVNC_DIR / "index.html")

    async def _static(self, request: web.Request) -> web.FileResponse:
        root = _NOVNC_DIR.resolve()
        path = (root / request.match_info["tail"]).resolve()
        if not str(path).startswith(str(root)) or not path.is_file():
            raise web.HTTPNotFound
        return web.FileResponse(path)

    async def _websockify(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
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

        async def ws_to_tcp() -> None:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    writer.write(msg.data)
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
