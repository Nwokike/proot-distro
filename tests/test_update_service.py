"""Update-service allow-list: the only URLs the app will ever launch.

The launcher boundary is security-critical — the feed is remote content, so
every launch goes through is_allowed_launch_url first.
"""

from __future__ import annotations

import pytest

from services.update_service import is_allowed_launch_url


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
