"""Terminal view — plain Terminal control (spike-parity), kept minimal.

Switched from MobileTerminal to plain Terminal to match the M0 spike that
was proven on-device. MobileTerminal's extra-keys/search/zoom land in a
follow-up once the basic shell is confirmed working on the phone.
"""

from __future__ import annotations

import contextlib
import json

import flet as ft
from flet_terminal import Terminal

from components.app_header import theme_button
from components.banner_ad import pooled_banner_ad
from components.ui import card, empty_state, section_header
from core import theme, tokens
from core.state import state
from core.styles import status_dot
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


def _write(entry: SessionEntry, payload: bytes) -> None:
    if entry.session is not None:
        entry.session.write(payload)


@ft.component
def TerminalView(entry: SessionEntry) -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    _st, _ = ft.use_state(state)
    fullscreen, set_fullscreen = ft.use_state(state.terminal_fullscreen)
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "session_manager", None)

    # Wakelock keeps screen/CPU awake during active terminal sessions
    def _sync_wakelock():
        wl = getattr(page, "wakelock", None)
        if wl is not None:
            with contextlib.suppress(Exception):
                page.run_task(wl.enable)

    def _cleanup():
        wl = getattr(page, "wakelock", None)
        if wl is not None:
            with contextlib.suppress(Exception):
                page.run_task(wl.disable)

    ft.on_mounted(_sync_wakelock)

    if entry.mt is None:
        entry.mt = Terminal(
            scrollback=10000,
            font_family="JetBrains Mono",
            auto_focus=False,
            expand=True,
        )
    mt = entry.mt

    if not entry.wired:

        def _on_resize(e) -> None:
            try:
                data = json.loads(e.data)
                cols = int(data.get("cols", 80))
                rows = int(data.get("rows", 24))
            except ValueError, TypeError:
                return
            if entry.session is not None:
                entry.session.resize(cols, rows)

        def _on_mount(_e) -> None:
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
                with contextlib.suppress(Exception):
                    page.run_task(haptics.selection_click)

        def _on_shortcut(e) -> None:
            sc = getattr(e, "shortcut", "") or ""
            if sc == "clear":
                mt.clear()
            elif sc == "copy":
                page.run_task(mt.get_selection_async)
            elif sc == "paste":
                page.run_task(mt.paste_async)

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

    def _toggle_fullscreen(_e=None) -> None:
        state.terminal_fullscreen = not fullscreen
        set_fullscreen(not fullscreen)

    # Switcher tabs for concurrent shells
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
                    bgcolor=ft.Colors.with_opacity(0.12, theme.primary())
                    if is_active
                    else ft.Colors.TRANSPARENT,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(0.24, theme.primary())
                        if is_active
                        else ft.Colors.TRANSPARENT,
                    ),
                    ink=True,
                    on_click=lambda _e, c=cname: page.run_task(methods.open_session, c),
                )
            )

    def _open_new_session_sheet() -> None:
        containers = [row.get("name", "?") for row in state.containers]
        unopened = [c for c in containers if manager and c not in manager.entries]
        if not unopened:
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

    def _confirm_close(page: ft.Page, methods, container: str) -> None:
        def _yes(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.close_session, container)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Close {container}?",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Text(
                    "The shell is terminated; unsaved work inside it is lost.",
                    size=tokens.FONT_SM,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.FilledButton(
                        "Close",
                        on_click=_yes,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            bgcolor=theme.warn(),
                        ),
                    ),
                ],
            )
        )

    def _toggle_fullscreen(_e=None) -> None:
        state.terminal_fullscreen = not fullscreen
        set_fullscreen(not fullscreen)

    switcher_box = ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=tab_chips,
                    spacing=tokens.SPACE_XXS,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                ft.Row(
                    controls=[
                        ft.IconButton(
                            icon=ft.Icons.ADD_ROUNDED,
                            icon_size=tokens.ICON_SM,
                            tooltip="New Terminal",
                            on_click=lambda _e: _open_new_session_sheet(),
                        ),
                    ],
                    spacing=tokens.SPACE_XXS,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(1, theme.glass_border()),
        border_radius=tokens.RADIUS_MD,
    )

    status_indicators: list[ft.Control] = [status_dot(entry.ready)]
    if not entry.ready:
        status_indicators.append(ft.ProgressRing(width=14, height=14, stroke_width=2))

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
                icon=ft.Icons.CLEAR_ALL_ROUNDED,
                content=ft.Text("Clear Terminal", size=tokens.FONT_SM),
                on_click=lambda _e: mt.clear(),
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

    def _browse_files() -> None:
        from screens.files.modal import show_manage_files_modal

        show_manage_files_modal(page, entry.container)

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

    quick_strip = ft.Container(
        content=ft.Row(
            controls=[
                ft.TextButton(label, on_click=lambda _e, cmd=cmd: _write(entry, cmd.encode()))
                for label, cmd in _QUICK_COMMANDS
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.Padding.symmetric(horizontal=tokens.SPACE_XS),
    )

    controls: list[ft.Control] = []
    if not fullscreen:
        controls.append(pooled_banner_ad("terminal-1", page))
        controls.append(header)
        controls.append(switcher_box)
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


@ft.component
def SessionSelectorView() -> ft.Control:
    """The Terminal tab: open shells + every installed container that can open one."""
    _st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "session_manager", None)

    sections: list[ft.Control] = []
    open_entries = list(manager.entries.values()) if manager else []
    if open_entries:
        rows = []
        for entry in open_entries:

            def _resume(_e, container=entry.container) -> None:
                page.run_task(methods.open_session, container)

            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.TERMINAL_ROUNDED,
                                    size=tokens.ICON_MD,
                                    color=theme.ok() if entry.ready else theme.text_dim(),
                                ),
                                ft.Text(
                                    entry.title,
                                    size=tokens.FONT_LG,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.text(),
                                    expand=True,
                                ),
                                status_dot(entry.ready),
                                ft.Text(
                                    "live" if entry.ready else (entry.error or "idle"),
                                    size=tokens.FONT_SM,
                                    color=theme.text_dim(),
                                ),
                                ft.FilledButton(
                                    "Resume",
                                    on_click=_resume,
                                    height=36,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                                    ),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=tokens.SPACE_SM,
                        ),
                        on_click=_resume,
                        ink=True,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
        sections.append(
            ft.Column(
                controls=[section_header("Open shells"), *rows],
                spacing=tokens.SPACE_SM,
            )
        )

    containers = [row.get("name", "?") for row in state.containers]
    if containers:
        rows = []
        for name in containers:
            if manager and name in manager.entries:
                continue

            def _open(_e, container=name) -> None:
                page.run_task(methods.open_session, container)

            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.APPS_ROUNDED,
                                    size=tokens.ICON_MD,
                                    color=theme.primary(),
                                ),
                                ft.Text(
                                    name,
                                    size=tokens.FONT_LG,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.text(),
                                    expand=True,
                                ),
                                ft.FilledButton(
                                    "Open shell",
                                    on_click=_open,
                                    height=36,
                                    style=ft.ButtonStyle(
                                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                                    ),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=tokens.SPACE_SM,
                        ),
                        on_click=_open,
                        ink=True,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
        sections.append(
            ft.Column(
                controls=[section_header("Installed containers"), *rows],
                spacing=tokens.SPACE_SM,
            )
        )
    else:
        sections.append(
            empty_state(
                "No containers yet",
                "Install one from the Distros tab first.",
                icon=ft.Icons.INVENTORY_2_OUTLINED,
            )
        )
    if state.session_error:
        sections.append(
            ft.Text(
                state.session_error,
                size=tokens.FONT_XS,
                color=theme.warn(),
                selectable=True,
            )
        )

    sections.append(pooled_banner_ad("terminals-1", page))
    sections.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))
    return ft.Column(
        controls=sections,
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
