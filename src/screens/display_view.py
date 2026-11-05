"""Display tab — running display sessions + every installed container's entry.

Mirrors the Terminal tab (session_selector_view.py): section header → cards →
banner at the bottom → NAV_BAR_CLEARANCE. Per-container capability probes are
cached in state.display_support and refreshed on mount. Not-ready containers
show ServalDesk-style desktop-environment cards (description + RAM note,
`BEST` badge on the recommended default) instead of a dead button.
"""

from __future__ import annotations

import flet as ft

from components import card, containers_required_empty_state, section_header
from components.banner_ad import pooled_banner_ad
from core import theme, tokens
from core.state import state
from state.controller_ctx import ControllerMethodsCtx


@ft.component
def DisplayView() -> ft.Control:
    """The Display tab: resume running displays + open/install per container."""
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)

    # Probe every installed container once per mount (rootfs reads only — fast).
    for row in st.containers or []:
        name = row.get("name", "")
        if name and name not in (st.display_support or {}):
            page.run_task(methods.probe_display, name)

    sections: list[ft.Control] = []
    running = manager.running() if manager else []
    if running:
        rows = []
        for session in running:

            def _resume(_e, key=session.key) -> None:
                state.active_display = key

            def _stop(_e, key=session.key) -> None:
                page.run_task(methods.stop_display, key)

            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.DESKTOP_WINDOWS,
                                    size=tokens.ICON_MD,
                                    color=theme.ok(),
                                ),
                                ft.Text(
                                    session.key,
                                    size=tokens.FONT_LG,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.text(),
                                    expand=True,
                                ),
                                ft.Text(
                                    f"{session.mode} · port {session.port}",
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
                                ft.IconButton(
                                    icon=ft.Icons.STOP_CIRCLE_ROUNDED,
                                    icon_color=theme.warn(),
                                    tooltip="Stop display",
                                    on_click=_stop,
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
                controls=[section_header("Running displays"), *rows],
                spacing=tokens.SPACE_SM,
            )
        )

    # A display still starting gets a live progress card in the tab (with
    # Cancel) — otherwise a slow first start looks like nothing happened.
    starting_sessions = manager.starting() if manager else []
    for session in starting_sessions:

        def _cancel(_e, key=session.key) -> None:
            page.run_task(methods.stop_display, key)

        sections.insert(
            0,
            card(
                ft.Row(
                    controls=[
                        ft.ProgressRing(
                            width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD
                        ),
                        ft.Text(
                            st.display_status_text or f"starting {session.key}…",
                            size=tokens.FONT_SM,
                            color=theme.text(),
                            expand=True,
                        ),
                        ft.TextButton("Cancel", on_click=_cancel),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_SM,
                ),
                padding=tokens.SPACE_SM,
            ),
        )

    containers = [row.get("name", "?") for row in st.containers]
    if not containers and not running and not starting_sessions:
        return containers_required_empty_state(page, ad_slot="display-empty")
    if containers:
        rows = []
        for name in containers:
            caps = (st.display_support or {}).get(name) or {}
            ready = bool(caps.get("desk_ready") and caps.get("x_server"))
            label = "Open display" if ready else "Install desktop"

            def _open(_e, container=name) -> None:
                page.run_task(methods.open_display, container)

            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.DESKTOP_WINDOWS,
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
                                ft.Text(
                                    caps.get("os", {}).get("pretty_name", "")
                                    if caps
                                    else "probing…",
                                    size=tokens.FONT_XS,
                                    color=theme.text_dim(),
                                ),
                                ft.FilledButton(
                                    label,
                                    icon=ft.Icons.DESKTOP_WINDOWS,
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

        def _new_display(_e) -> None:
            from screens.display_launcher import show_new_display_sheet

            show_new_display_sheet(page, methods)

        sections.append(
            ft.Column(
                controls=[
                    section_header(
                        "Installed containers",
                        action=ft.IconButton(
                            icon=ft.Icons.ADD_ROUNDED,
                            icon_size=tokens.ICON_MD,
                            tooltip="New display (desktop or single app)",
                            on_click=_new_display,
                        ),
                    ),
                    *rows,
                ],
                spacing=tokens.SPACE_SM,
            )
        )
    if state.display_error:
        sections.append(
            ft.Text(
                state.display_error,
                size=tokens.FONT_XS,
                color=theme.warn(),
                selectable=True,
            )
        )

    # Banner at the very bottom — same position as the Terminal tab.
    sections.append(pooled_banner_ad("display-1", page))
    sections.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))
    return ft.Column(
        controls=sections,
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
