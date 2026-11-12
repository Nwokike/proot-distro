"""Display tab — the two things a display IS, as obvious sections:

**Desktop** — a full desktop streamed from an installed container (the
per-container cards: Open display / Install display support), and **GUI application** — one
app alone on its own :N (pywebview-style). Running displays surface at the top
grouped the same way. The + on a section header starts a NEW display.

The starting card is driven by the OBSERVABLE state (state.display_status), so
it appears the instant start_display begins — no tab switch needed.
"""

from __future__ import annotations

import flet as ft

from components import card, containers_required_empty_state, section_header
from components.banner_ad import pooled_banner_ad
from core import theme, tokens
from core.state import display_progress as progress
from core.state import state
from screens.display_progress_card import DisplayProgressCard
from services.desk_service import DeskStatus
from state.controller_ctx import ControllerMethodsCtx


def _section(title: str, action, rows: list[ft.Control]) -> ft.Control:
    """A display section: title in the header, cards under it."""
    return ft.Column(
        controls=[section_header(title, action=action), *rows],
        spacing=tokens.SPACE_SM,
    )


@ft.component
def DisplayView() -> ft.Control:
    """The Display tab: GUI application first, then Desktop; running displays on top."""
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
        tooltip="New display — GUI app or desktop",
        on_click=_new_display,
    )

    def _single_app(_e) -> None:
        from screens.display_launcher import show_new_display_sheet

        show_new_display_sheet(page, methods)

    sections: list[ft.Control] = []
    # Reading display_sessions_rev subscribes this view to DeskManager
    # transitions (start/stop), so rows appear/vanish without a tab switch.
    _ = st.display_sessions_rev
    running = manager.visible() if manager else []

    def _session_rows(sessions: list) -> list:
        rows = []
        for session in sessions:
            # A running display is not necessarily a desktop (single-app mode
            # runs on its own :N) — the row icon says which, the section is
            # simply "Running".
            row_icon = (
                ft.Icons.DESKTOP_WINDOWS if session.mode == "desktop" else ft.Icons.WINDOW_ROUNDED
            )
            stopping = session.status is DeskStatus.STOPPING

            def _resume(_e, key=session.key) -> None:
                page.run_task(methods.resume_display, key)

            def _stop(_e, key=session.key) -> None:
                page.run_task(methods.stop_display, key)

            if stopping:
                # Immediate feedback while the stop runs — the row is removed
                # by the next transition notification once it completes.
                row_controls = [
                    ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD),
                    ft.Text(
                        session.key,
                        size=tokens.FONT_LG,
                        weight=ft.FontWeight.W_600,
                        color=theme.text(),
                        expand=True,
                    ),
                    ft.Text("stopping…", size=tokens.FONT_SM, color=theme.text_dim()),
                ]
            else:
                row_controls = [
                    ft.Icon(row_icon, size=tokens.ICON_MD, color=theme.ok()),
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
                ]
            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=row_controls,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=tokens.SPACE_SM,
                        ),
                        on_click=None if stopping else _resume,
                        ink=not stopping,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
        return rows

    if running:
        sections.append(_section("Running", plus_button, _session_rows(running)))

    # A display still starting gets a live progress card — driven by the
    # OBSERVABLE display_status (set the instant start_display begins), so it
    # appears without any tab switch. The manager lookup only supplies the key.
    starting_key = ""
    if st.display_status == "starting":
        starting = manager.starting() if manager else []
        if starting:
            starting_key = starting[0].key
    if starting_key:

        def _cancel(_e) -> None:
            page.run_task(methods.stop_display, starting_key)

        sections.insert(
            0,
            card(
                ft.Row(
                    controls=[
                        ft.ProgressRing(
                            width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD
                        ),
                        ft.Text(
                            st.display_status_text or f"starting {starting_key}…",
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
    if not containers and not running and not starting_key and not progress.is_running:
        return containers_required_empty_state(page, ad_slot="display-empty")

    # ── Install progress card — CollabShell NotebookCell mechanism ───────────
    # `display_progress` is a SMALL observable model passed as the component's
    # argument; its mutations re-render this card reactively (that is the part
    # that makes CollabShell's notebook output move constantly). Includes the
    # owner-requested collapse/expand chevrons.
    if progress.is_running or progress.logs:

        def _cancel_install(_e) -> None:
            # The install runs as a PTY capture; Stop kills that session.
            page.run_task(methods.cancel_install_display)

        sections.insert(
            0,
            DisplayProgressCard(progress, on_cancel=_cancel_install),
        )

    # ── GUI application section (first — the app-first design): one app alone
    # on its own :N. The desktop is the secondary option, not the headline.
    sections.append(
        _section(
            "GUI application",
            None,
            [
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.WINDOW_ROUNDED,
                                    size=tokens.ICON_MD,
                                    color=theme.primary(),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Run one app on its own display",
                                            size=tokens.FONT_MD,
                                            weight=ft.FontWeight.W_600,
                                            color=theme.text(),
                                        ),
                                        ft.Text(
                                            "A browser, an editor, a pywebview app — streamed "
                                            "alone, no desktop around it.",
                                            size=tokens.FONT_XS,
                                            color=theme.text_dim(),
                                        ),
                                    ],
                                    spacing=tokens.SPACE_XXS,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.ADD_CIRCLE_ROUNDED,
                                    icon_size=tokens.ICON_LG,
                                    icon_color=theme.primary(),
                                    tooltip="New GUI application display",
                                    on_click=_single_app,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=tokens.SPACE_SM,
                        ),
                        on_click=_single_app,
                        ink=True,
                    ),
                    padding=tokens.SPACE_SM,
                )
            ],
        )
    )

    # ── Desktop section: per-container desktop cards ─────────────────────────
    if containers:
        rows = []
        for name in containers:
            caps = (st.display_support or {}).get(name) or {}
            # The display runs IN THE APP — the card always opens one (the
            # launcher sheet leads with GUI applications); only a full desktop
            # session depends on the probed desktop facts.
            installing_this = progress.is_running and progress.container == name
            label = "Installing…" if installing_this else "Open display"

            def _open(_e, container=name) -> None:
                page.run_task(methods.open_display, container)

            icon = ft.Icon(ft.Icons.DESKTOP_WINDOWS, size=tokens.ICON_MD, color=theme.primary())
            name_text = ft.Text(
                name,
                size=tokens.FONT_LG,
                weight=ft.FontWeight.W_600,
                color=theme.text(),
            )
            distro_text = ft.Text(
                caps.get("os", {}).get("pretty_name", "") if caps else "probing…",
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            )
            action = ft.FilledButton(
                label,
                icon=ft.Icons.DESKTOP_WINDOWS,
                on_click=_open,
                height=tokens.CONTROL_SM,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)),
            )
            # Matching distro screen card layout: icon + expanding text column + right-aligned action
            content = ft.Row(
                controls=[
                    icon,
                    ft.Column(
                        controls=[name_text, distro_text],
                        spacing=tokens.SPACE_XXS,
                        expand=True,
                    ),
                    action,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_SM,
            )
            rows.append(
                card(
                    ft.Container(
                        content=content,
                        on_click=_open,
                        ink=True,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )

        sections.append(_section("Desktop", plus_button, rows))

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
