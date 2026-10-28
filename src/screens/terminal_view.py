"""The terminal view — Terminal in the component tree, wired once per
session. M0-spike pattern: plain Terminal control (not MobileTerminal) to avoid
renderer context issues on Android. CollabShell pattern: in-screen switcher tabs,
action cluster, zoom/blink controls, full-width flat chrome, and hardened PTY lifecycle.
"""

from __future__ import annotations

import json

import flet as ft
from flet_terminal import BUILTIN_THEMES, Terminal

from components.app_header import theme_button
from components.banner_ad import pooled_banner_ad
from components.ui import NO_CONTAINERS_MESSAGE, card
from core import theme, tokens
from core.state import state
from core.styles import status_dot
from screens.terminal_controls import (
    _compact_btn_style,
    _confirm_close,
    _cycle_terminal_theme,
    _theme_name,
    _write,
)
from services.session_manager import SessionEntry
from state.controller_ctx import ControllerMethodsCtx

# Commands execute immediately when tapped — trailing newline is required
# or characters sit un-submitted at the prompt.
_QUICK_COMMANDS = (
    ("ls", "ls\n"),
    ("apt update", "apt update\n"),
    ("apt install …", "apt install "),
    ("top", "top\n"),
    ("clear", "clear\n"),
    ("exit", "exit\n"),
)


@ft.component
def TerminalView(entry: SessionEntry) -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    _st, _ = ft.use_state(state)
    note_dismissed, set_note_dismissed = ft.use_state(state.apt_note_dismissed)
    fullscreen, set_fullscreen = ft.use_state(state.terminal_fullscreen)
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "session_manager", None)

    # Wakelock keeps screen/CPU awake during active terminal sessions
    def _sync_wakelock():
        wl = getattr(page, "wakelock", None)
        if wl is not None:
            page.run_task(wl.enable)

            def _cleanup():
                if wl is not None:
                    page.run_task(wl.disable)

            return _cleanup
        return None

    ft.on_mounted(_sync_wakelock)

    # Use plain Terminal control (M0-spike pattern) instead of MobileTerminal
    # to avoid "no current renderer is set" issues on Android
    if entry.mt is None:
        entry.mt = Terminal(
            scrollback=10000,
            font_family=tokens.MONO_FONT,
            theme=BUILTIN_THEMES.get(_theme_name()),
            auto_focus=False,
            expand=True,
        )

    mt = entry.mt

    if not entry.wired:

        def _on_resize(e) -> None:
            data = json.loads(e.data)
            cols = int(data.get("cols", 80))
            rows = int(data.get("rows", 24))
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
                    manager.set_title(entry.container, title)

        def _on_bell(_e) -> None:
            haptics = getattr(page, "haptics", None)
            if haptics is not None:
                page.run_task(haptics.selection_click)

        def _on_shortcut(e) -> None:
            sc = getattr(e, "shortcut", "") or ""
            if sc == "clear":
                mt.clear()
            elif sc == "copy":
                # Plain Terminal doesn't have copy_selection_async
                pass
            elif sc == "paste":
                page.run_task(mt.paste_async)
            elif sc == "new_terminal":
                _open_new_session_sheet()
            elif sc == "close_terminal":
                _confirm_close(page, methods, entry.container)
            # Note: toggle_search, zoom_in, zoom_out, zoom_reset not available on plain Terminal

        mt.set_on_bytes(lambda payload: _write(entry, payload))
        mt.on_data = lambda e: _write(
            entry, e.data.encode("utf-8", "ignore") if isinstance(e.data, str) else b""
        )
        mt.on_resize = _on_resize
        mt.on_mount = _on_mount
        mt.on_title_change = _on_title
        mt.on_bell = _on_bell
        mt.on_shortcut = _on_shortcut
        entry.wired = True

    theme_btn = theme_button(lambda: page.run_task(methods.cycle_theme_mode))

    def _apply_theme() -> None:
        name = _theme_name()
        mt.set_theme(name)

        ft.use_effect(_apply_theme, [state.theme_revision])

    def _quick(label: str, command: str) -> ft.Control:
        def _send(_e) -> None:
            _write(entry, command.encode("utf-8"))

        return ft.TextButton(label, on_click=_send)

    def _toggle_fullscreen(_e) -> None:
        state.terminal_fullscreen = not fullscreen
        set_fullscreen(not fullscreen)

    def _open_new_session_sheet() -> None:
        installed = [r.get("name", "") for r in state.containers if r.get("name")]
        unopened = [c for c in installed if manager and c not in manager.entries]
        if not unopened:
            msg = (
                "All installed containers already have a running shell."
                if installed
                else NO_CONTAINERS_MESSAGE
            )
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("New Terminal", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                    content=ft.Text(msg, size=tokens.FONT_SM),
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
                    "Open Shell in Container",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=[
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                            title=ft.Text(c, size=tokens.FONT_MD, weight=ft.FontWeight.W_600),
                            on_click=lambda _e, name=c: _launch(name),
                        )
                        for c in unopened
                    ],
                    spacing=tokens.SPACE_XS,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog())],
            )
        )

    status_indicators: list[ft.Control] = [status_dot(entry.ready)]
    if not entry.ready:
        status_indicators.append(
            ft.ProgressRing(
                width=tokens.PROGRESS_RING_XS,
                height=tokens.PROGRESS_RING_XS,
                stroke_width=tokens.PROGRESS_RING_STROKE,
            )
        )

    def _browse_files() -> None:
        from screens.files.modal import show_manage_files_modal

        show_manage_files_modal(page, entry.container)

    action_menu = ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT_ROUNDED,
        icon_size=tokens.ICON_MD,
        tooltip="Terminal Actions",
        items=[
            ft.PopupMenuItem(
                icon=ft.Icons.ADD_ROUNDED,
                content=ft.Text("New Terminal", size=tokens.FONT_SM),
                on_click=lambda _e: _open_new_session_sheet(),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                content=ft.Text("Paste", size=tokens.FONT_SM),
                on_click=lambda _e: page.run_task(mt.paste_async),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.CLEAR_ALL_ROUNDED,
                content=ft.Text("Clear Terminal", size=tokens.FONT_SM),
                on_click=lambda _e: mt.clear(),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.VISIBILITY_ROUNDED,
                content=ft.Text("Toggle Cursor Blink", size=tokens.FONT_SM),
                on_click=lambda _e: mt.toggle_cursor_blink(),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.FOLDER_OPEN_ROUNDED,
                content=ft.Text("Browse Files", size=tokens.FONT_SM),
                on_click=lambda _e: _browse_files(),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.CLOSE_ROUNDED,
                content=ft.Text("Close Shell", size=tokens.FONT_SM),
                on_click=lambda _e: _confirm_close(page, methods, entry.container),
            ),
        ],
    )

    # CollabShell flat full-width session header
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Back to the session list (the shell stays alive)",
                    on_click=lambda _e: page.run_task(methods.leave_session),
                ),
                ft.Icon(
                    ft.Icons.TERMINAL_ROUNDED,
                    size=tokens.ICON_MD,
                    color=theme.primary(),
                ),
                ft.Text(
                    entry.title,
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                    color=theme.text(),
                    expand=True,
                ),
                ft.Row(
                    controls=status_indicators,
                    spacing=tokens.SPACE_XS,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.IconButton(
                    icon=ft.Icons.FULLSCREEN_ROUNDED
                    if not fullscreen
                    else ft.Icons.FULLSCREEN_EXIT_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Full screen",
                    on_click=_toggle_fullscreen,
                ),
                theme_btn,
                action_menu,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_SM),
    )

    # Multi-shell switcher tabs: CollabShell switcher_box pattern
    tab_chips: list[ft.Control] = []
    if manager:
        for cname, e in manager.entries.items():
            is_active = cname == entry.container
            tab_chips.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.TERMINAL_ROUNDED,
                                size=tokens.ICON_XS,
                                color=theme.primary() if is_active else theme.text_dim(),
                            ),
                            ft.Text(
                                e.title or cname,
                                size=tokens.FONT_XS,
                                color=theme.primary() if is_active else theme.text(),
                                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                            ),
                            ft.GestureDetector(
                                content=ft.Icon(
                                    ft.Icons.CLOSE_ROUNDED,
                                    size=tokens.ICON_XS,
                                    color=theme.text_dim(),
                                ),
                                on_tap=lambda _evt, c=cname: _confirm_close(page, methods, c),
                            ),
                        ],
                        spacing=tokens.SPACE_XXS,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_SM, tokens.SPACE_XXS, tokens.SPACE_XS, tokens.SPACE_XXS
                    ),
                    border_radius=tokens.RADIUS_SM,
                    bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary())
                    if is_active
                    else theme.TRANSPARENT,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(tokens.OPACITY_SELECTED, theme.primary())
                        if is_active
                        else ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.text_dim()),
                    ),
                    on_click=lambda _evt, c=cname: setattr(state, "active_session", c),
                    ink=True,
                )
            )

    tab_chips.append(
        ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_size=tokens.ICON_SM,
            tooltip="New Terminal",
            style=_compact_btn_style(),
            on_click=lambda _e: _open_new_session_sheet(),
        )
    )

    switcher_box = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=tab_chips,
                        spacing=tokens.SPACE_XS,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.PALETTE_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Cycle Terminal Theme",
                    style=_compact_btn_style(),
                    on_click=lambda _e: _cycle_terminal_theme(mt),
                ),
                ft.IconButton(
                    icon=ft.Icons.ZOOM_OUT,
                    icon_size=tokens.ICON_SM,
                    tooltip="Zoom Out",
                    style=_compact_btn_style(),
                    on_click=lambda _e: mt.zoom_out(),
                ),
                ft.IconButton(
                    icon=ft.Icons.ZOOM_IN,
                    icon_size=tokens.ICON_SM,
                    tooltip="Zoom In",
                    style=_compact_btn_style(),
                    on_click=lambda _e: mt.zoom_in(),
                ),
                ft.IconButton(
                    icon=ft.Icons.SEARCH_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Search Buffer",
                    style=_compact_btn_style(),
                    on_click=lambda _e: mt.toggle_search(),
                ),
            ],
            spacing=tokens.SPACE_NONE,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_SM, 0, tokens.SPACE_SM, 0),
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_WHISPER, theme.text()),
    )

    quick_strip = ft.Container(
        content=ft.Row(
            controls=[_quick(label, cmd) for label, cmd in _QUICK_COMMANDS],
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.Padding.symmetric(horizontal=tokens.SPACE_XS),
    )

    controls: list[ft.Control] = []
    if not fullscreen:
        # D-017.7: the ad sits strictly ABOVE the app chrome.
        controls.append(pooled_banner_ad("terminal-1", page))
        controls.append(header)
        controls.append(switcher_box)
        # Note sits beneath the header/switcher so dismissing it causes no header jump.
        if not note_dismissed:
            controls.append(
                card(
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.INFO_OUTLINE,
                                size=tokens.ICON_XS,
                                color=theme.warn(),
                            ),
                            ft.Text(
                                "Package installs work; upgrading an already-installed "
                                "package can fail — reinstalling is always safe.",
                                size=tokens.FONT_XS,
                                color=theme.text_dim(),
                                expand=True,
                            ),
                            ft.TextButton(
                                "Got it",
                                on_click=lambda _e: (
                                    setattr(state, "apt_note_dismissed", True),
                                    set_note_dismissed(True),
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            )
    else:
        controls.append(
            ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.FULLSCREEN_EXIT_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Leave full screen",
                    on_click=_toggle_fullscreen,
                ),
                alignment=ft.Alignment.TOP_LEFT,
                padding=tokens.SPACE_XS,
            )
        )
    controls.append(mt)
    if not fullscreen:
        controls.append(quick_strip)

    return ft.Column(controls=controls, spacing=tokens.SPACE_XS, expand=True)
