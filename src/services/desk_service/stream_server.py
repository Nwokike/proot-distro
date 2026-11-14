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
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

logger = logging.getLogger(__name__)

_NOVNC_DIR = Path(__file__).parent / "novnc"
# Upstream requires revalidation so a bumped vnc.html never pairs with stale
# cached JS (docs/EMBEDDING.md — "the confusingly named Cache-Control: no-cache").
_NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}


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
        """Upstream's viewer URL: autoconnect + the access code riding inside
        the `path` setting (upstream builds the WebSocket URL from `path`
        verbatim, query string included — verified in app/ui.js `UI.connect`).
        `quality`/`compression` are upstream's own setting names."""
        return (
            f"http://127.0.0.1:{self.port}{self.viewer_path()}?"
            f"autoconnect=1&path={quote(f'/websockify?code={self.code}', safe='')}"
            f"&quality={self.quality}&compression={self.compression}"
        )

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
        target = (
            f"{self.viewer_path()}?autoconnect=1"
            f"&path={quote(f'/websockify?code={code}', safe='')}"
            f"&quality={self.quality}&compression={self.compression}"
        )
        raise web.HTTPFound(target)

    async def _static(self, request: web.Request) -> web.FileResponse:
        root = _NOVNC_DIR.resolve()
        path = (root / request.match_info["tail"]).resolve()
        if not str(path).startswith(str(root)) or not path.is_file():
            raise web.HTTPNotFound
        # Upstream's deployment requirement: revalidate, or a bumped vnc.html
        # can pair with stale cached JS (docs/EMBEDDING.md).
        return web.FileResponse(path, headers=_NO_CACHE_HEADERS)

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
