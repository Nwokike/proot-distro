"""Display launcher sheets — public facade.

The implementation lives in screens/display_sheets/ (common widgets, the
advanced options, and the sheets themselves). This module only re-exports the
entry points so existing imports keep working.
"""

from __future__ import annotations

from .display_sheets.launcher_sheet import show_display_sheet

__all__ = ["show_display_sheet"]
