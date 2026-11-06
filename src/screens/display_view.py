"""Display tab — running DISPLAYS (grouped: Desktops / Apps) + every installed
container's entry, sharing the Terminal tab's rhythm: header → cards → banner
→ NAV_BAR_CLEARANCE. A display is the live streamed surface (desktop OR single
app on its own :N); a desktop is what you install in the container. The + on a
section header starts a NEW display of either kind.
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
    """The Display tab: running desktops/apps + every container's entry."""
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

    def _new_display(_e) -> None:
        from screens.display_launcher import show_new_display_sheet

        show_new_display_sheet(page, methods)

    plus_button = ft.IconButton(
        icon=ft.Icons.ADD_ROUNDED,
        icon_size=tokens.ICON_MD,
        tooltip="New display (desktop or single app)",
        on_click=_new_display,
    )

    sections: list[ft.Control] = []
    running = manager.running() if manager else []
    desktops = [s for s in running if s.mode == "desktop"]
    apps = [s for s in running if s.mode == "app"]

    def _session_rows(sessions: list, icon) -> list:
        rows = []
        for session in sessions:

            def _resume(_e, key=session.key) -> None:
                state.active_display = key

            def _stop(_e, key=session.key) -> None:
                page.run_task(methods.stop_display, key)

            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(icon, size=tokens.ICON_MD, color=theme.ok()),
                                ft.Text(
                                    session.key,
                                    size=tokens.FONT_LG,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.text(),
                                    expand=True,
                                ),
                                ft.Text(
                                    f"port {session.port}",
                                    size=tokens.FONT_SM,
                                    color=theme.text_dim(),
                                ),
                                ft.FilledButton(
                                    "Open",
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
        return rows

    if desktops:
        sections.append(
            ft.Column(
                controls=[
                    section_header("Desktops", action=plus_button),
                    *_session_rows(desktops, ft.Icons.DESKTOP_WINDOWS),
                ],
                spacing=tokens.SPACE_SM,
            )
        )
    if apps:
        section_action = plus_button if not desktops else None
        sections.append(
            ft.Column(
                controls=[
                    section_header("Apps", action=section_action),
                    *_session_rows(apps, ft.Icons.WINDOW_ROUNDED),
                ],
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
            label = "Open desktop" if ready else ("Checking…" if not caps else "Install desktop")

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

        sections.append(
            ft.Column(
                controls=[
                    section_header("Installed containers", action=plus_button),
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
