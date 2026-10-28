"""Container picker and resume list for terminal sessions."""

from __future__ import annotations

import flet as ft

from components import card, no_containers_empty_state, section_header
from core import theme, tokens
from core.state import state
from core.styles import status_dot
from state.controller_ctx import ControllerMethodsCtx


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
                                    height=tokens.CONTROL_MD,
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
                                    height=tokens.CONTROL_MD,
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
        sections.append(no_containers_empty_state())
    if state.session_error:
        sections.append(
            ft.Text(
                state.session_error,
                size=tokens.FONT_XS,
                color=theme.warn(),
                selectable=True,
            )
        )

    sections.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))
    return ft.Column(
        controls=sections,
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
