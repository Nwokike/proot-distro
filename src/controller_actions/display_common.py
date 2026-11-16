"""Helpers shared by the display action mixins."""

from __future__ import annotations

import logging
import os

from core import tokens
from core.state import state

logger = logging.getLogger(__name__)


def _tail_file_lines(path, max_bytes: int) -> list[str]:
    """The last `max_bytes` of a log as lines — a cold reopen must not read a
    whole multi-MB log just to show 200 lines."""
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            data = fh.read()
    except OSError:
        return []
    return data.decode("utf-8", "replace").splitlines()


# Xvnc screen for "auto" geometry: long side 1280 keeps RFB updates sane on
# phones; the viewer letterboxes any aspect anyway, and a preset/custom
# resolution bypasses this.
_AUTO_GEOMETRY_LONG_SIDE = tokens.AUTO_GEOMETRY_LONG_SIDE

# In-flight probe dedup (error results are never cached — see probe_display).
_probing: set[str] = set()


def _int_setting(value, default: int, low: int, high: int) -> int:
    """User-typed numeric option → a clamped int. A bad/empty custom value must
    never bubble a ValueError out of start_display (the fields accept text)."""
    try:
        parsed = int(str(value).strip())
    except TypeError, ValueError:
        return default
    return max(low, min(high, parsed))


def _auto_geometry(page, orientation: str = "landscape") -> str:
    width = max(1, int(getattr(page, "width", 0) or 0))
    height = max(1, int(getattr(page, "height", 0) or 0))
    # The screen must match the LOCKED orientation, not the (portrait) page the
    # start sheet happened to render in — otherwise fullscreen shows a portrait
    # desktop letterboxed inside the landscape viewer.
    if (orientation == "landscape" and height > width) or (
        orientation == "portrait" and width > height
    ):
        width, height = height, width
    long_side = max(width, height)
    scale = _AUTO_GEOMETRY_LONG_SIDE / long_side
    even_w = max(2, round(width * scale / 2) * 2)
    even_h = max(2, round(height * scale / 2) * 2)
    return f"{even_w}x{even_h}"


def invalidate_display_support(container: str) -> None:
    """Drop the cached capability probe — call on remove/reset/rename."""
    if state.display_support and container in state.display_support:
        state.display_support = {k: v for k, v in state.display_support.items() if k != container}
    # The regenerable copies under cache/ must go too, or a recreated container
    # of the same name would show the previous one's desktops and apps.
    from core import probe_cache

    probe_cache.drop("caps", container)
    probe_cache.drop("apps", container)
    if state.detected_apps and container in state.detected_apps:
        state.detected_apps = {k: v for k, v in state.detected_apps.items() if k != container}
