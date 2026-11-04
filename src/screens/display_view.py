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
from services.desk_service import DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
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

            def _resume(_e, name=session.container) -> None:
                state.active_display = name

            def _stop(_e, name=session.container) -> None:
                page.run_task(methods.stop_display, name)

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
                                    session.container,
                                    size=tokens.FONT_LG,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.text(),
                                    expand=True,
                                ),
                                ft.Text(
                                    f":{session.display} · port {session.port}",
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

    containers = [row.get("name", "?") for row in st.containers]
    if not containers and not running:
        return containers_required_empty_state(page, ad_slot="display-empty")
    if containers:
        rows = []
        for name in containers:
            caps = (st.display_support or {}).get(name) or {}
            ready = bool(caps.get("desk_ready") and caps.get("x_server"))
            label = "Open display" if ready else "Set up display"

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
                controls=[section_header("Installed containers"), *rows],
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


def build_de_cards(selected: dict, on_pick) -> list[ft.Control]:
    """ServalDesk-style desktop-environment cards: name + description + RAM
    note, `BEST` badge on the recommended default. `selected` is a one-key
    dict {key: True} so the highlight survives re-renders."""
    rows: list[ft.Control] = []
    for de in DESKTOP_ENVIRONMENTS:
        is_selected = bool(selected.get(de.key)) or (not selected and de.key == DEFAULT_DESKTOP)
        rows.append(
            card(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.Text(
                                                de.name,
                                                size=tokens.FONT_MD,
                                                weight=ft.FontWeight.W_600,
                                                color=theme.text(),
                                                expand=True,
                                            ),
                                            ft.Container(
                                                content=ft.Text(
                                                    "BEST",
                                                    size=tokens.FONT_XXS,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=theme.primary(),
                                                ),
                                                visible=de.best,
                                                padding=ft.Padding(
                                                    tokens.SPACE_XS,
                                                    tokens.SPACE_XXS,
                                                    tokens.SPACE_XS,
                                                    tokens.SPACE_XXS,
                                                ),
                                                border=ft.Border.all(
                                                    1,
                                                    ft.Colors.with_opacity(
                                                        tokens.OPACITY_BORDER, theme.primary()
                                                    ),
                                                ),
                                                border_radius=tokens.RADIUS_SM,
                                            ),
                                        ],
                                        spacing=tokens.SPACE_XS,
                                    ),
                                    ft.Text(
                                        de.description,
                                        size=tokens.FONT_XS,
                                        color=theme.text_dim(),
                                    ),
                                    ft.Text(
                                        de.ram_note,
                                        size=tokens.FONT_XXS,
                                        color=theme.text_dim(),
                                    ),
                                ],
                                spacing=tokens.SPACE_XXS,
                                expand=True,
                            ),
                            ft.Radio(
                                group="de-picker",
                                value=de.key,
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary())
                    if is_selected
                    else None,
                    on_click=lambda _e, k=de.key: on_pick(k),
                    ink=True,
                ),
                padding=tokens.SPACE_SM,
            )
        )
    return rows
