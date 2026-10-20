"""Update service — checks the release feed and reports a newer build.

Sherlock's shape with ffmpeg's hardening: https-only URLs, length caps,
silent failure, and a comparison by build number OR version. Delivery is
browser-based: the dialog opens the release page; nothing is downloaded
in-app.
"""

from __future__ import annotations

import logging
import re

from core.constants import (
    APP_BUILD_NUMBER,
    APP_VERSION,
    GITHUB_RELEASES_URL,
    UPDATE_CONFIG_URL,
)

logger = logging.getLogger(__name__)

_ALLOWED_HOSTS = ("github.com", "raw.githubusercontent.com", "play.google.com")


def is_allowed_launch_url(url: str) -> bool:
    """Only https links into the project's own domains may launch."""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    host = (parts.hostname or "").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in _ALLOWED_HOSTS)


def _safe_text(value, limit: int, default: str = "") -> str:
    return value[:limit] if isinstance(value, str) else default


def _safe_url(value, default: str | None = None) -> str | None:
    if not isinstance(value, str) or not value:
        return default
    return value if is_allowed_launch_url(value) else default


def _release_tuple(version) -> tuple[int, ...] | None:
    head = re.split(r"[-+]", str(version or "").strip(), maxsplit=1)[0]
    parts = head.split(".")
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def is_newer(remote_build, remote_version=None) -> bool:
    """True when the feed is newer by build number OR by version string."""
    try:
        if int(remote_build) > APP_BUILD_NUMBER:
            return True
    except TypeError, ValueError:
        pass
    remote = _release_tuple(remote_version)
    local = _release_tuple(APP_VERSION)
    return bool(remote and local and remote > local)


async def check_for_update(config_url: str = UPDATE_CONFIG_URL) -> dict | None:
    """Return the update info when the feed is ahead; None otherwise."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            response = await client.get(config_url)
            if response.status_code != 200:
                logger.debug("Update check returned %s", response.status_code)
                return None
            data = response.json()
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
            "playstore_url": _safe_url(data.get("playstore_url")),
        }
    except Exception as exc:
        logger.debug("Update check failed (expected if offline): %s", exc)
        return None
