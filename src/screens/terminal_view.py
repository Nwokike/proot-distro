"""The terminal view — MobileTerminal in the component tree, wired once per
session. CollabShell/example pattern: both input paths, resize with keyboard
inset, scrollback replay on mount, theme following the app.
"""

from __future__ import annotations

import contextlib
import json

import flet as ft
from flet_terminal import BUILTIN_THEMES, MobileTerminal

from components.app_header import theme_button
from components.banner_ad import pooled_banner_ad
from components.ui import card, empty_state, section_header
from core import theme, tokens
from core.state import state
from core.styles import status_dot
from services.session_manager import SessionEntry
from state.controller_ctx import ControllerMethodsCtx

_QUICK_COMMANDS = (
    ("ls", "ls"),
    ("apt update", "apt update"),
    ("apt install …", "apt install "),
    (" top", "top"),
    ("clear", "clear"),
    ("exit", "exit"),
)


def _theme_name() -> str:
    return "Colab Light" if theme.is_light_theme() else "JetBrains Dark"


def _write(entry: SessionEntry, payload: bytes) -> None:
    if entry.session is not None:
        entry.session.write(payload)


def _confirm_close(page, methods, container: str) -> None:
    def _yes(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.close_session, container)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Close {container}?"),
            content=ft.Text("The shell is terminated; unsaved work inside it is lost.", size=12),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.TextButton("Close", on_click=_yes),
            ],
        )
    )


@ft.component
def TerminalView(entry: SessionEntry) -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    _st, _ = ft.use_state(state)
    inset, set_inset = ft.use_state(0)
    note_dismissed, set_note_dismissed = ft.use_state(state.apt_note_dismissed)
    fullscreen, set_fullscreen = ft.use_state(state.terminal_fullscreen)

    if entry.mt is None:
        entry.mt = MobileTerminal(
            show_extra_keys=True,
            show_search=True,
            show_settings=False,
            scrollback=10000,
            font_family="JetBrains Mono",
            theme=BUILTIN_THEMES.get(_theme_name()),
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
                bottom = int(data.get("bottom_inset", 0) or 0)
            except ValueError:
                return
            if entry.session is not None:
                entry.session.resize(cols, rows)
            if bottom != inset:
                set_inset(bottom)

        def _on_mount(_e) -> None:
            mt.clear_pending()
            entry.replay(mt.send_bytes)

        def _on_title(e) -> None:
            title = e.data if isinstance(e.data, str) else ""
            if title:
                entry.title = title

        mt.set_on_bytes(lambda payload: _write(entry, payload))
        mt.on_data = lambda e: _write(
            entry, e.data.encode("utf-8", "ignore") if isinstance(e.data, str) else b""
        )
        mt.on_resize = _on_resize
        mt.on_mount = _on_mount
        mt.on_title_change = _on_title
        entry.wired = True

    theme_btn = theme_button(lambda: page.run_task(methods.cycle_theme_mode))

    # A theme flip repaints the terminal palette (CollabShell's effect).
    def _apply_theme() -> None:
        name = _theme_name()
        with contextlib.suppress(Exception):
            mt.set_theme(name)

    ft.use_effect(_apply_theme, [state.theme_revision])

    def _quick(label: str, command: str) -> ft.Control:
        def _send(_e) -> None:
            _write(entry, command.encode("utf-8"))

        return ft.TextButton(label, on_click=_send)

    def _toggle_fullscreen(_e) -> None:
        state.terminal_fullscreen = not fullscreen
        set_fullscreen(not fullscreen)

    header = card(
        ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    icon_size=18,
                    tooltip="Back to the session list (the shell stays alive)",
                    on_click=lambda _e: page.run_task(methods.leave_session),
                ),
                ft.Icon(ft.Icons.TERMINAL, size=16, color=theme.primary()),
                ft.Text(entry.title, size=13, weight=ft.FontWeight.BOLD, expand=True),
                ft.Text(
                    "live" if entry.ready else (entry.error or "starting…"),
                    size=10,
                    color=theme.AppColors.OK if entry.ready else theme.text_dim(),
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_size=18,
                    tooltip="Close this shell",
                    on_click=lambda _e: _confirm_close(page, methods, entry.container),
                ),
                ft.IconButton(
                    icon=ft.Icons.FULLSCREEN if not fullscreen else ft.Icons.FULLSCREEN_EXIT,
                    icon_size=18,
                    tooltip="Full screen (hide the chrome and the ad)",
                    on_click=_toggle_fullscreen,
                ),
                theme_btn,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO,
        )
    )

    quick_strip = ft.Container(
        content=ft.Row(
            controls=[_quick(label, cmd) for label, cmd in _QUICK_COMMANDS],
            scroll=ft.ScrollMode.AUTO,
        ),
        padding=ft.Padding.symmetric(horizontal=4),
    )

    controls: list[ft.Control] = []
    if not fullscreen:
        # The ad sits ABOVE the app's own chrome, never next to the terminal:
        # the header row stays between them, so no tap target is adjacent.
        controls.append(pooled_banner_ad("terminal-1", page))
        controls.append(header)
    else:
        controls.append(
            ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.FULLSCREEN_EXIT,
                    icon_size=16,
                    tooltip="Leave full screen",
                    on_click=_toggle_fullscreen,
                ),
                alignment=ft.Alignment.TOP_LEFT,
            )
        )
    controls.append(mt)
    if not fullscreen:
        controls.append(quick_strip)
    if not fullscreen and not note_dismissed:
        controls.insert(
            1,
            card(
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO, size=14, color=theme.AppColors.WARN),
                        ft.Text(
                            "Package installs work; upgrading an already-installed "
                            "package can fail — reinstalling is always safe.",
                            size=10,
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
            ),
        )

    body = ft.Column(controls=controls, spacing=4, expand=True)
    if inset > 0:
        body = ft.Container(content=body, padding=ft.Padding.only(bottom=inset), expand=True)
    return body


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
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.TERMINAL,
                                size=16,
                                color=theme.AppColors.OK if entry.ready else theme.text_dim(),
                            ),
                            ft.Text(entry.title, size=13, expand=True),
                            status_dot(entry.ready),
                            ft.Text(
                                "live" if entry.ready else (entry.error or "idle"),
                                size=tokens.FONT_SM,
                                color=theme.text_dim(),
                            ),
                            ft.TextButton("Resume", on_click=_resume),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=theme.surface(),
                    padding=4,
                    border_radius=8,
                )
            )
        sections.append(
            ft.Column(
                controls=[section_header("Open shells"), *rows],
                spacing=4,
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
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.APPS, size=16, color=theme.primary()),
                            ft.Text(name, size=13, expand=True),
                            ft.TextButton("Open shell", on_click=_open),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=theme.surface(),
                    padding=4,
                    border_radius=8,
                )
            )
        sections.append(
            ft.Column(
                controls=[section_header("Installed containers"), *rows],
                spacing=4,
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
            ft.Text(state.session_error, size=10, color=theme.AppColors.WARN, selectable=True)
        )

    return ft.Column(controls=sections, spacing=4, expand=True, scroll=ft.ScrollMode.AUTO)
