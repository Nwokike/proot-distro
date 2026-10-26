"""Update service — checks the release feed and reports a newer build.

Sherlock's shape with ffmpeg's hardening: https-only URLs, length caps,
retry with backoff over transient network failures, and comparison by
build number OR version. Delivery is browser-based: the dialog opens
the release page; nothing is downloaded in-app.
"""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlsplit

from core.constants import (
    APP_BUILD_NUMBER,
    APP_VERSION,
    GITHUB_RELEASES_URL,
    PLAY_STORE_URL,
    UPDATE_CONFIG_URL,
)

logger = logging.getLogger(__name__)

_ALLOWED_HOSTS = ("github.com", "raw.githubusercontent.com", "play.google.com")


def is_allowed_launch_url(url: str) -> bool:
    """Only https links into the project's own domains may launch.

    Backslashes are normalized to slashes first: `urlsplit` treats
    `https://evil.com\\@github.com/` as host `github.com`, while Chrome (the
    thing that actually opens the URL) reads host `evil.com` — without the
    normalization the allow-list is bypassable.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parts = urlsplit(url.replace("\\", "/"))
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    host = (parts.hostname or "").lower()
    if "@" in host:  # urlsplit strips userinfo; a survivor means a crafted netloc
        return False
    return any(host == domain or host.endswith(f".{domain}") for domain in _ALLOWED_HOSTS)


def _safe_text(value, limit: int, default: str = "") -> str:
    return value[:limit] if isinstance(value, str) else default


def _safe_url(value, default: str | None = None) -> str | None:
    if not isinstance(value, str) or not value:
        return default
    return value if is_allowed_launch_url(value) else default


def _release_tuple(version) -> tuple[int, ...] | None:
    if not version:
        return None
    v = str(version).strip().lstrip("vV")
    head = re.split(r"[-+a-zA-Z]", v, maxsplit=1)[0]
    parts = head.split(".")
    if not parts or not any(p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts if p.isdigit()]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def is_newer(remote_build, remote_version=None) -> bool:
    """True when the feed is newer by build number OR by version string."""
    try:
        if int(remote_build) > APP_BUILD_NUMBER:
            return True
    except (TypeError, ValueError):
        # Invalid build number format, fall through to version comparison
        pass
    remote = _release_tuple(remote_version)
    local = _release_tuple(APP_VERSION)
    return bool(remote and local and remote > local)


async def check_for_update(
    config_url: str = UPDATE_CONFIG_URL,
    client: object | None = None,
) -> dict | None:
    """Return the update info when the feed is ahead; None when up to date.

    Raises RuntimeError on network failure so the caller knows the check failed.
    """
    import httpx

    timeout = httpx.Timeout(5.0, connect=4.0)

    async def _fetch(c: httpx.AsyncClient) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                resp = await c.get(config_url)
                if resp.status_code >= 500 and attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                return resp
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                if attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                raise RuntimeError(f"Network error: {exc}") from exc
        if last_exc is not None:
            raise RuntimeError(f"Network error: {last_exc}") from last_exc
        raise RuntimeError("Request failed")

    if client is not None:
        response = await _fetch(client)  # type: ignore[arg-type]
    else:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as local_c:
            response = await _fetch(local_c)

    if response.status_code == 404:
        # Feed not published yet — clean up-to-date fallback.
        return None
    if response.status_code != 200:
        logger.debug("Update check returned HTTP %s", response.status_code)
        return None

    try:
        data = response.json()
    except Exception as exc:
        logger.warning("Failed to parse update feed JSON: %s", exc)
        return None

    if not isinstance(data, dict):
        return None

    server_build = data.get("build_number") or 0
    if not is_newer(server_build, data.get("version")):
        return None

    raw_type = data.get("type")
    kind = raw_type if raw_type in ("update", "announcement") else "update"
    return {
        "version": _safe_text(data.get("version"), 50, APP_VERSION),
        "build_number": server_build,
        "type": kind,
        "title": _safe_text(data.get("title"), 500),
        "release_notes": _safe_text(data.get("release_notes"), 10000),
        "mandatory": data.get("mandatory") is True,
        "github_url": _safe_url(data.get("github_url"), GITHUB_RELEASES_URL),
        "playstore_url": _safe_url(data.get("playstore_url"), PLAY_STORE_URL),
    }
