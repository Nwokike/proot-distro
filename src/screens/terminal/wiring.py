"""Terminal↔session wiring — extracted from TerminalView (module-level).

Wires the MobileTerminal's events to the ProotSession exactly once per entry.
"""

from __future__ import annotations

import json

import flet as ft

from core import tokens
from screens.terminal_controls import _confirm_close, _input
from services.session_manager import SessionEntry


async def copy_selection(page: ft.Page, mt) -> None:
    """Copy the terminal selection through the ONE app-wide Clipboard.

    flet-terminal's `copy_selection_async` builds its own `ft.Clipboard()`
    internally — a Service that may never be mounted, so the copy can fail
    silently. Reading the selection and using `page.clipboard` keeps the
    single-mount contract every other screen follows."""
    clipboard = getattr(page, "clipboard", None)
    if clipboard is None or mt is None:
        return
    try:
        text = await mt.get_selection_async()
    except Exception:
        return
    if text:
        await clipboard.set(text)


def wire_terminal(
    entry: SessionEntry, mt, page: ft.Page, manager, methods, open_new_session
) -> None:
    """Attach all MobileTerminal event handlers; sets entry.wired = True."""

    def _on_resize(e) -> None:
        data = json.loads(e.data)
        cols = int(data.get("cols", tokens.TERM_COLS_DEFAULT))
        rows = int(data.get("rows", tokens.TERM_ROWS_DEFAULT))
        if entry.session is not None:
            entry.session.resize(cols, rows)

    def _on_mount(_e) -> None:
        mt.clear_pending()
        entry.replay(mt.send_bytes)

    def _on_title(e) -> None:
        title = e.data if isinstance(e.data, str) else ""
        if title and title != entry.title:
            entry.title = title
            if manager:
                manager.set_title(entry.key, title)

    def _on_bell(_e) -> None:
        haptics = getattr(page, "haptics", None)
        if haptics is not None:
            page.run_task(haptics.selection_click)

    def _on_shortcut(e) -> None:
        sc = getattr(e, "shortcut", "") or ""
        if sc == "toggle_search":
            mt.toggle_search()
        elif sc == "zoom_in":
            mt.zoom_in()
        elif sc == "zoom_out":
            mt.zoom_out()
        elif sc == "zoom_reset":
            mt.reset_zoom()
        elif sc == "clear":
            mt.clear()
        elif sc == "copy":
            page.run_task(copy_selection, page, mt)
        elif sc == "paste":
            page.run_task(mt.paste_async)
        elif sc == "new_terminal":
            open_new_session()
        elif sc == "close_terminal":
            _confirm_close(page, methods, entry.key, entry.title or entry.container)

    mt.set_on_bytes(lambda payload: _input(entry, payload))
    mt.on_data = lambda e: _input(
        entry, e.data.encode("utf-8", "ignore") if isinstance(e.data, str) else b""
    )
    mt.on_resize = _on_resize
    mt.on_mount = _on_mount
    mt.on_title_change = _on_title
    mt.on_bell = _on_bell
    mt.on_shortcut = _on_shortcut
    entry.wired = True
