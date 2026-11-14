"""Responsive rules — ONE definition of the breakpoints used across screens.

Before this module the same thresholds were inlined in five screens with three
different values (600, 650, page_width - 48), so a tablet could stack on one
screen and not another. Screens call these helpers instead.
"""

from __future__ import annotations

from core import tokens

NARROW_BREAKPOINT = 600
MOBILE_BREAKPOINT = 650
DIALOG_GUTTER = 48


def _int_attr(page, name: str) -> int:
    try:
        return int(getattr(page, name, 0) or 0)
    except TypeError, ValueError:
        return 0


def page_width(page) -> int:
    return _int_attr(page, "width")


def page_height(page) -> int:
    return _int_attr(page, "height")


def is_narrow(page, width_limit: int = NARROW_BREAKPOINT) -> bool:
    """True when the layout must stack (page narrower than the breakpoint)."""
    width = page_width(page)
    return bool(width and width < width_limit)


def is_mobile_layout(page) -> bool:
    """Mobile platform OR a phone-width page (the container grid's rule)."""
    platform = getattr(page, "platform", None)
    mobile = bool(platform.is_mobile()) if platform is not None else False
    return mobile or is_narrow(page, MOBILE_BREAKPOINT)


def dialog_width(
    page,
    *,
    min_width: int = tokens.DIALOG_MIN_WIDTH,
    max_width: int = tokens.DIALOG_WIDTH,
) -> int:
    """A dialog that never exceeds the page (48 px gutter) or its own cap."""
    width = page_width(page)
    if not width:
        return max_width
    return min(max_width, max(min_width, width - DIALOG_GUTTER))


def sheet_size(
    page,
    *,
    min_height: int = 320,
    max_height: int = 620,
    fallback_height: int = 520,
    chrome: int = 190,
) -> tuple[int, int]:
    """(width, height) for a tall sheet: scroll inside instead of overflowing."""
    height = page_height(page)
    bounded = max(min_height, min(height - chrome, max_height)) if height > 512 else fallback_height
    return dialog_width(page), bounded
