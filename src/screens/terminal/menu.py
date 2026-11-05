"""Terminal FAB (page-level floating action button) + new-session sheet.

Mirrors CollabShell's `build_session_fab`: a mini FAB wrapping a
PopupMenuButton, with grouped items (bold disabled headers, checked theme
presets) — no hamburger in the header.
"""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.state import state
from screens.terminal_controls import _THEME_PRESETS, _confirm_close, _theme_name

_THEME_ICONS = {
    "Dracula": ft.Icons.DARK_MODE_ROUNDED,
    "JetBrains Dark": ft.Icons.CODE_ROUNDED,
    "Matrix Green": ft.Icons.GRID_ON_ROUNDED,
    "Colab Light": ft.Icons.LIGHT_MODE_ROUNDED,
}


def _item(content: str, icon, on_click, checked: bool | None = None) -> ft.PopupMenuItem:
    return ft.PopupMenuItem(content=content, icon=icon, on_click=on_click, checked=checked)


def show_full_output_dialog(page: ft.Page, entry) -> None:
    """Copy FULL OUTPUT — the whole scrollback, not just what's on screen.

    flet-terminal's native select_all only reaches the rendered viewport on
    device, and the package exposes no buffer-dump API — but we own every
    byte: SessionEntry.scrollback holds the complete PTY stream (capped at
    SCROLLBACK_CHUNKS). Decode it here and hand it to the clipboard."""
    raw = b"".join(entry.scrollback)
    text = raw.decode("utf-8", "replace")

    def _copy(_e) -> None:
        from components.snack import show_snack

        page.run_task(ft.Clipboard().set, text)
        show_snack(page, "full output copied to clipboard")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Full output — {entry.title or entry.key}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Container(
                content=ft.Text(
                    text or "(empty)",
                    font_family=tokens.MONO_FONT,
                    size=tokens.FONT_XXS,
                    selectable=True,
                ),
                width=tokens.DIALOG_WIDTH_LG,
                height=360,
            ),
            actions=[
                ft.FilledButton(
                    f"Copy all ({len(text):,} chars)",
                    icon=ft.Icons.COPY_ALL_ROUNDED,
                    on_click=_copy,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
                ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
            ],
        )
    )


def _header(label: str) -> ft.PopupMenuItem:
    return ft.PopupMenuItem(content=ft.Text(label, weight=ft.FontWeight.BOLD), disabled=True)


def _clear_terminal(entry, mt) -> None:
    """Real clear, CollabShell's way: Ctrl+L to the shell (clears screen and
    redraws the prompt at top) plus a widget-side buffer/scrollback clear."""
    from screens.terminal_controls import _write

    _write(entry, b"\x0c")
    entry.scrollback.clear()
    if mt is not None:
        mt.clear()


def build_terminal_fab(
    page: ft.Page,
    methods,
    entry,
    manager,
    fullscreen: bool,
    on_toggle_fullscreen,
    on_browse_files,
    on_new_terminal,
) -> ft.FloatingActionButton:
    """The terminal FAB: all session/terminal actions in one overflow menu."""
    mt = entry.mt
    cur_theme = (
        (getattr(mt, "theme_name", None) or _theme_name()) if mt is not None else _theme_name()
    )

    def _set_theme(name: str):
        def _go(_e):
            if mt is not None:
                mt.set_theme(name)

        return _go

    items: list[ft.PopupMenuItem] = [
        _item("New Terminal", ft.Icons.ADD_ROUNDED, lambda _e: on_new_terminal()),
        _item(
            "Copy Selection",
            ft.Icons.COPY_ALL_ROUNDED,
            lambda _e: page.run_task(mt.copy_selection_async),
        ),
        _item(
            "Select All",
            ft.Icons.SELECT_ALL_ROUNDED,
            lambda _e: mt.select_all(),  # synchronous API on MobileTerminal
        ),
        _item(
            "Copy Full Output",
            ft.Icons.COPY_ALL_ROUNDED,
            lambda _e: show_full_output_dialog(page, entry),
        ),
        _item("Paste", ft.Icons.CONTENT_PASTE_ROUNDED, lambda _e: page.run_task(mt.paste_async)),
        _item(
            "Clear Terminal",
            ft.Icons.CLEAR_ALL_ROUNDED,
            on_click=lambda _e: _clear_terminal(entry, mt),
        ),
        ft.PopupMenuItem(),
        _header("Theme Presets"),
        *[
            _item(name, _THEME_ICONS[name], _set_theme(name), cur_theme == name)
            for name in _THEME_PRESETS
        ],
        ft.PopupMenuItem(),
        _header("Font Size / Zoom"),
        _item("Zoom In", ft.Icons.ADD_ROUNDED, on_click=lambda _e: mt.zoom_in()),
        _item("Zoom Out", ft.Icons.REMOVE_ROUNDED, on_click=lambda _e: mt.zoom_out()),
        _item("Reset Zoom", ft.Icons.FIT_SCREEN_ROUNDED, on_click=lambda _e: mt.reset_zoom()),
        ft.PopupMenuItem(),
        _header("Toggle Options"),
        _item(
            "Cursor Blink",
            ft.Icons.VISIBILITY_ROUNDED,
            on_click=lambda _e: mt.toggle_cursor_blink(),
            checked=True,
        ),
        _item(
            "Search Bar",
            ft.Icons.SEARCH_ROUNDED,
            on_click=lambda _e: mt.toggle_search(),
            checked=False,
        ),
        ft.PopupMenuItem(),
        _item("Browse Files", ft.Icons.FOLDER_OPEN_ROUNDED, on_click=lambda _e: on_browse_files()),
        _item(
            "Exit Full Screen" if fullscreen else "Full Screen",
            ft.Icons.FULLSCREEN_EXIT_ROUNDED if fullscreen else ft.Icons.FULLSCREEN_ROUNDED,
            on_click=lambda _e: on_toggle_fullscreen(),
        ),
        _item(
            "Close Shell",
            ft.Icons.CLOSE_ROUNDED,
            on_click=lambda _e: _confirm_close(
                page, methods, entry.key, entry.title or entry.container
            ),
        ),
    ]

    return ft.FloatingActionButton(
        content=ft.PopupMenuButton(
            items=items,
            icon=ft.Icons.MORE_VERT_ROUNDED,
            icon_color=ft.Colors.WHITE,
            icon_size=tokens.ICON_MD,
        ),
        bgcolor=theme.primary(),
        mini=True,
        tooltip="Terminal actions",
    )


def open_new_session_sheet(page: ft.Page, methods, manager) -> None:
    """New Terminal: every installed container — one already running gets a
    SECOND shell on the same container (tmux-style; no artificial cap,
    the OS fd/memory limits are the only bound)."""
    installed = [r.get("name", "") for r in state.containers if r.get("name")]
    if not installed:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("New Terminal", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Text("Install a container first to open a shell.", size=tokens.FONT_SM),
                actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
            )
        )
        return

    def _launch(c: str) -> None:
        page.pop_dialog()
        page.run_task(methods.open_session, c)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                "New Terminal",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=[
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.primary()),
                        title=ft.Text(c, size=tokens.FONT_MD, weight=ft.FontWeight.W_600),
                        subtitle=ft.Text(
                            "opens a second shell on this container"
                            if manager and any(e.container == c for e in manager.entries.values())
                            else "",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                        on_click=lambda _e, name=c: _launch(name),
                    )
                    for c in installed
                ],
                spacing=tokens.SPACE_XS,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog())],
        )
    )
