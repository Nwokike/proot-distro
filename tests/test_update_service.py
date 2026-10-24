"""Update-service tests: URL allow-list and MockTransport feed tests.

The launcher boundary is security-critical — the feed is remote content, so
every launch goes through is_allowed_launch_url first.
Feed fetching and retry behaviors are tested using httpx.MockTransport.
"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest

from services.update_service import (
    check_for_update,
    is_allowed_launch_url,
    is_newer,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Nwokike/proot-distro/releases/latest",
        "https://raw.githubusercontent.com/Nwokike/proot-distro/main/version.json",
        "https://play.google.com/store/apps/details?id=ng.kiri.prootdistro",
    ],
)
def test_project_urls_are_allowed(url):
    assert is_allowed_launch_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.com",
        "https://evil.com/github.com",
        "https://github.com.evil.com/",
        "http://github.com",  # plain http never launches
        "github.com/releases",  # not a URL
        "https://github.com@evil.com/",  # userinfo trick: host is evil.com
        "",
        None,
    ],
)
def test_other_urls_are_refused(url):
    assert is_allowed_launch_url(url) is False


def test_backslash_bypass_is_closed():
    """THE regression: urlsplit reads host github.com (allowed) while Chrome
    opens evil.com — the exact split-brain the normalization kills."""
    assert is_allowed_launch_url("https://evil.com\\@github.com/") is False


@pytest.mark.parametrize(
    "url",
    [
        # After backslash normalization these genuinely ARE github.com URLs
        # (Python and Chrome agree on the host) — allowed by design.
        "https://github.com\\@evil.com/x",
        "https://user:pass@github.com/",  # host is github.com; creds ignored
    ],
)
def test_host_trusted_after_normalization(url):
    assert is_allowed_launch_url(url) is True


# ── MockTransport feed tests ──────────────────────────────────────────────────


def test_is_newer_version_comparison():
    # Newer by build number
    assert is_newer(2, "1.0.0") is True
    # Same build number, same version
    assert is_newer(1, "1.0.0") is False
    # Same version string format (1.0 vs 1.0.0 normalized)
    assert is_newer(1, "1.0") is False
    # Newer version string
    assert is_newer(1, "1.1.0") is True
    assert is_newer(1, "2.0.0") is True


def test_check_for_update_returns_data_when_newer():
    feed_data = {
        "version": "1.1.0",
        "build_number": 2,
        "type": "update",
        "title": "Version 1.1.0 available",
        "release_notes": "New features and fixes",
        "mandatory": False,
        "github_url": "https://github.com/Nwokike/proot-distro/releases/latest",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=feed_data)

    async def _run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await check_for_update(client=client)

    result = asyncio.run(_run())
    assert result is not None
    assert result["version"] == "1.1.0"
    assert result["build_number"] == 2
    assert result["type"] == "update"


def test_check_for_update_returns_none_when_up_to_date():
    feed_data = {
        "version": "1.0.0",
        "build_number": 1,
        "type": "update",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=feed_data)

    async def _run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await check_for_update(client=client)

    result = asyncio.run(_run())
    assert result is None


def test_check_for_update_handles_404_as_none():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async def _run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await check_for_update(client=client)

    result = asyncio.run(_run())
    assert result is None


def test_check_for_update_retries_transient_500():
    attempts = 0
    feed_data = {"version": "1.2.0", "build_number": 3}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500)
        return httpx.Response(200, json=feed_data)

    async def _run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with patch("asyncio.sleep", return_value=None):
                return await check_for_update(client=client)

    result = asyncio.run(_run())
    assert attempts == 2
    assert result is not None
    assert result["version"] == "1.2.0"


def test_check_for_update_raises_on_permanent_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async def _run():
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            with (
                patch("asyncio.sleep", return_value=None),
                pytest.raises(RuntimeError, match="Network error"),
            ):
                await check_for_update(client=client)

    asyncio.run(_run())
