"""stream_server — the session HTTP surface: noVNC hosting, the access-code
gate, and the transparent WS↔RFB pump. Tested with aiohttp's TestServer (the
pytest-aiohttp plugin is not installed) against a fake RFB TCP server.
"""

from __future__ import annotations

import asyncio

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from services.desk_service.stream_server import DisplayStreamServer

CODE = "AB23CD"


@pytest.fixture
def server():
    return DisplayStreamServer("127.0.0.1", 0, 5900, CODE, quality=7, compression=3)


@pytest.fixture
async def client(server):
    """A TestClient bound to the server's app (a random port, no real site)."""
    async with TestClient(TestServer(server._build_app())) as client:
        yield client


# ── static surface + code gate ───────────────────────────────────────────────


async def test_health_is_open(client):
    response = await client.get("/health")
    assert response.status == 200
    assert (await response.json()) == {"ok": True}


async def test_auth_gate_accepts_only_the_session_code(client):
    good = await client.get("/auth", params={"code": CODE})
    assert good.status == 200
    bad = await client.get("/auth", params={"code": "XXXXXX"})
    assert bad.status == 403
    missing = await client.get("/auth")
    assert missing.status == 403


async def test_index_serves_our_viewer_page(client):
    response = await client.get("/")
    assert response.status == 200
    body = await response.text()
    assert "novnc/core/rfb.js" in body  # the vendored library, our page around it


async def test_vendored_novnc_files_serve(client):
    response = await client.get("/novnc/core/rfb.js")
    assert response.status == 200
    assert b"class RFB" in await response.read()


async def test_static_paths_cannot_escape(client):
    for path in ("/novnc/../index.html", "/novnc/../../pyproject.toml", "/novnc/nope.js"):
        response = await client.get(path)
        assert response.status in (404, 405), path


def test_knobs_are_clamped_to_noVNCs_range():
    server = DisplayStreamServer("127.0.0.1", 0, 5900, CODE, quality=99, compression=-5)
    assert server.quality == 9
    assert server.compression == 0


# ── the WS↔RFB pump ──────────────────────────────────────────────────────────


class _FakeRFBServer:
    """A minimal TCP server standing in for Xvnc's RFB port: records what the
    proxy sends, answers with one banner, and counts handler completions."""

    def __init__(self):
        self.received = b""
        self.connections_closed = 0
        self.server = None
        self.port = 0

    async def start(self):
        async def handler(reader, writer):
            try:
                data = await asyncio.wait_for(reader.read(4096), timeout=2.0)
                self.received += data
            except TimeoutError, ConnectionError:
                pass
            writer.write(b"RFB-BANNER")
            await writer.drain()
            try:
                # EOF when the proxy tears its side down with the client
                await asyncio.wait_for(reader.read(4096), timeout=5.0)
            except TimeoutError, ConnectionError:
                pass
            self.connections_closed += 1
            writer.close()

        self.server = await asyncio.start_server(handler, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()


async def test_websockify_refuses_a_wrong_code(server):
    async with TestClient(TestServer(server._build_app())) as client:
        ws = await client.ws_connect("/websockify?code=XXXXXX")
        async for msg in ws:
            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                break
        assert ws.close_code == 4401


async def test_websockify_proxies_rfb_bytes_both_ways(server):
    fake = _FakeRFBServer()
    await fake.start()
    server.rfb_port = fake.port
    try:
        async with TestClient(TestServer(server._build_app())) as client:
            ws = await client.ws_connect(f"/websockify?code={CODE}")
            # client → RFB: the fake server records our bytes
            await ws.send_bytes(b"client-hello")
            # RFB → client: the fake server's banner arrives through the proxy
            banner = await ws.receive_bytes(timeout=5.0)
            assert banner == b"RFB-BANNER"
            await asyncio.sleep(0.1)  # let the pump deliver our bytes
            assert fake.received == b"client-hello"
            await ws.close()
    finally:
        await fake.stop()


async def test_websockify_closes_the_rfb_side_with_the_client(server):
    """Client disconnect → the proxy tears the TCP side down (no leaked Xvnc
    connections per viewer open/close)."""
    fake = _FakeRFBServer()
    await fake.start()
    server.rfb_port = fake.port
    try:
        async with TestClient(TestServer(server._build_app())) as client:
            ws = await client.ws_connect(f"/websockify?code={CODE}")
            await ws.receive_bytes(timeout=5.0)  # banner flowed; pump is live
            await ws.close()
            # the fake server's handler returns when its reader hits EOF
            for _ in range(100):
                if fake.connections_closed == 1:
                    break
                await asyncio.sleep(0.05)
            assert fake.connections_closed == 1
    finally:
        await fake.stop()


def test_local_url_carries_the_code_and_knobs(server):
    url = server.local_url()
    assert url.startswith("http://127.0.0.1:0/")
    assert f"code={CODE}" in url
    assert "quality=7" in url
    assert "compression=3" in url
