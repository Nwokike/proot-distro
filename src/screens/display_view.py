"""Display tab.

Running and failed displays on top. Then one card per container: the apps that
container actually has (its .desktop entries, detected once), a "Preset apps"
button for the full list and a command box, and the Desktop action. One app and
a desktop are different sessions, but they share every option, so both start
from the same sheet.

The starting card is driven by the OBSERVABLE state (state.display_status), so
it appears the instant start_display begins, with no tab switch needed.
"""

from __future__ import annotations

import flet as ft

from components import card, containers_required_empty_state, section_header
from components.banner_ad import pooled_banner_ad
from core import styles, theme, tokens
from core.constants import AD_SLOT_DISPLAY
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
    """The Display tab: running sessions on top, then one card per container."""
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)

    # Probe every installed container once per mount: desktop facts (rootfs
    # reads) and the preset GUI apps it actually has (one `command -v` each).
    for row in st.containers or []:
        name = row.get("name", "")
        if not name:
            continue
        if name not in (st.display_support or {}):
            page.run_task(methods.probe_display, name)
        if st.detected_apps is None or name not in st.detected_apps:
            page.run_task(methods.probe_apps, name)

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
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="More",
                        items=[
                            ft.PopupMenuItem(
                                content=ft.Text("Share"),
                                on_click=lambda _e, k=session.key: page.run_task(
                                    methods.share_display, k
                                ),
                            ),
                            ft.PopupMenuItem(
                                content=ft.Text("Logs"),
                                on_click=lambda _e, k=session.key: page.run_task(
                                    methods.show_display_logs, k
                                ),
                            ),
                            ft.PopupMenuItem(
                                content=ft.Text("Stop"),
                                on_click=_stop,
                            ),
                        ],
                    ),
                ]
            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            # No wrap: a Row with an expand child inside a Wrap
                            # is the Expanded-in-Wrap layout bug (the row
                            # scattered its actions). The title flexes instead.
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

    def _failed_rows(sessions: list) -> list:
        """Crash honesty: a failed display is a VISIBLE row — what happened,
        its log, a same-shape Retry, and a Dismiss (never silent; device
        audit 2026-11-13: crashed rows used to vanish without a word)."""
        rows = []
        for session in sessions:

            def _retry(_e, s=session) -> None:
                page.run_task(methods.retry_display, s.key)

            def _logs(_e, key=session.key) -> None:
                page.run_task(methods.show_display_logs, key)

            def _dismiss(_e, key=session.key) -> None:
                page.run_task(methods.stop_display, key)

            rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.ERROR_OUTLINE,
                                    size=tokens.ICON_MD,
                                    color=theme.warn(),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            session.key,
                                            size=tokens.FONT_LG,
                                            weight=ft.FontWeight.W_600,
                                            color=theme.text(),
                                        ),
                                        ft.Text(
                                            session.error or "the display failed",
                                            size=tokens.FONT_XS,
                                            color=theme.text_dim(),
                                            max_lines=tokens.MAX_LINES_TWO,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                    spacing=tokens.SPACE_XXS,
                                    expand=True,
                                ),
                                ft.TextButton("Logs", on_click=_logs),
                                ft.TextButton("Retry", on_click=_retry),
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE_ROUNDED,
                                    icon_color=theme.warn(),
                                    tooltip="Dismiss (stop the failed display)",
                                    on_click=_dismiss,
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=tokens.SPACE_SM,
                        ),
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
        return rows

    # Errors render ABOVE the content — never under the banner.
    if state.display_error:
        sections.append(
            ft.Text(
                state.display_error,
                size=tokens.FONT_XS,
                color=theme.warn(),
                selectable=True,
            )
        )

    if running:
        sections.append(_section("Running", None, _session_rows(running)))

    failed = manager.failed() if manager else []
    if failed:
        sections.append(_section("Failed", None, _failed_rows(failed)))

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
    if progress.is_running:

        def _cancel_install(_e) -> None:
            # The install runs as a PTY capture; Stop kills that session.
            page.run_task(methods.cancel_install_display)

        sections.insert(
            0,
            DisplayProgressCard(progress, on_cancel=_cancel_install),
        )

    # ── Presets first, then the containers ────────────────────────────────────
    # Presets are listed GLOBALLY, not per distro: one list, and each row says
    # which container it runs in. Below it, each container gets the same card
    # Home shows, with the one "Open display" button.
    def _run_preset(preset: dict):
        def _handler(_e) -> None:
            opts = None
            if preset.get("work_dir") or preset.get("env"):
                opts = {}
                if preset.get("work_dir"):
                    opts["work_dir"] = preset["work_dir"]
                if preset.get("env"):
                    opts["env"] = list(preset["env"])
            page.run_task(
                methods.start_display,
                str(preset.get("container") or (containers[0] if containers else "")),
                None,
                str(preset.get("cmd", "")),
                None,
                opts,
            )

        return _handler

    def _delete_preset(name: str):
        def _handler(_e) -> None:
            page.run_task(methods.delete_app_preset, name)

        return _handler

    presets = st.app_presets or []
    preset_rows: list[ft.Control] = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.BOOKMARK_ROUNDED, color=theme.primary()),
            title=ft.Text(
                str(preset.get("name", "")),
                size=tokens.FONT_SM,
                weight=ft.FontWeight.W_600,
                color=theme.text(),
            ),
            subtitle=ft.Text(
                " · ".join(
                    part
                    for part in (
                        str(preset.get("cmd", "")),
                        str(preset.get("container", "")),
                    )
                    if part
                ),
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            ),
            on_click=_run_preset(preset),
            trailing=ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                icon_size=tokens.ICON_SM,
                tooltip="Delete preset",
                on_click=_delete_preset(str(preset.get("name", ""))),
            ),
        )
        for preset in presets
    ]
    preset_content: ft.Control = (
        ft.Column(controls=preset_rows, spacing=tokens.SPACE_XXS)
        if preset_rows
        else ft.Text(
            "No presets yet. Open a display, type a command and use Save as preset.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        )
    )
    sections.append(_section("Presets", None, [card(preset_content, padding=tokens.SPACE_SM)]))

    def _display_card(name: str) -> ft.Control:
        caps = (st.display_support or {}).get(name) or {}
        installing_this = progress.is_running and progress.container == name

        def _open(_e) -> None:
            page.run_task(methods.open_display, name)

        return card(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.DESKTOP_WINDOWS,
                            size=tokens.ICON_MD,
                            color=theme.primary(),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    name,
                                    size=tokens.FONT_LG,
                                    weight=ft.FontWeight.W_600,
                                    color=theme.text(),
                                ),
                                ft.Text(
                                    caps.get("os", {}).get("pretty_name", ""),
                                    size=tokens.FONT_XS,
                                    color=theme.text_dim(),
                                ),
                            ],
                            spacing=tokens.SPACE_XXS,
                            expand=True,
                        ),
                        ft.FilledButton(
                            "Installing…" if installing_this else "Open display",
                            icon=ft.Icons.DESKTOP_WINDOWS,
                            on_click=_open,
                            disabled=installing_this,
                            height=tokens.CONTROL_SM,
                            style=styles.pill_button_style(),
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

    if containers:
        sections.append(_section("Displays", None, [_display_card(n) for n in containers]))

    # Banner at the very bottom — same position as the Terminal tab.
    sections.append(pooled_banner_ad(AD_SLOT_DISPLAY, page))
    sections.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))
    return ft.Column(
        controls=sections,
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
