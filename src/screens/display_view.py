"""Display tab.

Running and failed displays on top. Then one card per container (Distros) and
finally the Presets list: the apps each container actually has (its .desktop
entries) plus the user's own saved commands. Everything starts from the one
display sheet. The Presets block refreshes on its own (apps appear after an
in-container install without restarting the app) and can be refreshed by hand.

The starting card is driven by the OBSERVABLE state (state.display_status), so
it appears the instant start_display begins, with no tab switch needed.
"""

from __future__ import annotations

import asyncio

import flet as ft

from components import card, containers_required_empty_state, section_header
from components.banner_ad import insert_periodic, pooled_banner_ad
from core import styles, theme, tokens
from core.constants import AD_SLOT_DISPLAY
from core.state import state
from screens.display_rows import failed_rows, session_rows
from screens.display_sheets.sheet_parts import with_sandbox
from state.controller_ctx import ControllerMethodsCtx

GESTURE_HINT = "In the viewer: one finger drags the mouse, two fingers scroll, pinch zooms."


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
    refreshing, set_refreshing = ft.use_state(False)
    # Per-app "--no-sandbox" checkbox state (keyed by command), so it survives
    # the re-renders caused by session transitions or probe results.
    sandbox, set_sandbox = ft.use_state({})

    # Probe every installed container: display facts (rootfs reads) and the
    # preset GUI apps it actually has. probe_apps is idempotent (no-op while
    # fresh, deduped while in flight), so calling it on every render lets a
    # stale list refresh itself without an app restart.
    for row in st.containers or []:
        name = row.get("name", "")
        if not name:
            continue
        if name not in (st.display_support or {}):
            page.run_task(methods.probe_display, name)
        page.run_task(methods.probe_apps, name)

    sections: list[ft.Control] = []
    # Reading display_sessions_rev subscribes this view to DeskManager
    # transitions (start/stop), so rows appear/vanish without a tab switch.
    _ = st.display_sessions_rev
    running = manager.visible() if manager else []

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
        sections.append(
            _section("Running", None, session_rows(running, page=page, methods=methods))
        )

    failed = manager.failed() if manager else []
    if failed:
        sections.append(_section("Failed", None, failed_rows(failed, page=page, methods=methods)))

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
    if not containers and not running and not starting_key:
        return containers_required_empty_state(page, ad_slot="display-empty")

    # How the viewer behaves on a phone is not guessable: say it up front
    # (owner 2026-11-17, "I didn't notice the hints of two fingers to swipe").
    sections.append(ft.Text(GESTURE_HINT, size=tokens.FONT_XXS, color=theme.text_dim()))

    def _refresh_presets(_e=None) -> None:
        """Force a fresh app scan for every container (CollabShell refresh)."""

        async def _do() -> None:
            set_refreshing(True)
            try:
                await asyncio.gather(
                    *(methods.probe_apps(name, True) for name in containers if name)
                )
            finally:
                set_refreshing(False)

        page.run_task(_do)

    # ── Distros first (Open display per container), Presets LAST ─────────────
    # Owner ruling 2026-11-16: presets grow with installed apps, so they sit
    # after the distro cards. Detected apps (from .desktop entries) AND manual
    # presets are listed together, each row naming its container.
    def _preset_options(preset: dict) -> dict | None:
        if not (preset.get("work_dir") or preset.get("env")):
            return None
        opts = {}
        if preset.get("work_dir"):
            opts["work_dir"] = preset["work_dir"]
        if preset.get("env"):
            opts["env"] = list(preset["env"])
        return opts

    def _delete_preset(name: str):
        def _handler(_e) -> None:
            page.run_task(methods.delete_app_preset, name)

        return _handler

    def _manual_preset_row(preset: dict) -> ft.Control:
        """A saved preset: UNCHECKED sandbox by default (the user's command),
        toggleable like a detected app, with the same live command preview."""
        cmd = str(preset.get("cmd", ""))
        container_name = str(preset.get("container", ""))
        checked = bool(sandbox.get(cmd, False))

        def _run(_e) -> None:
            page.run_task(
                methods.start_display,
                container_name or (containers[0] if containers else ""),
                with_sandbox(cmd, bool(sandbox.get(cmd, False))),
                None,
                _preset_options(preset),
            )

        return ft.ListTile(
            leading=ft.Icon(ft.Icons.BOOKMARK_ROUNDED, color=theme.primary()),
            title=ft.Text(
                str(preset.get("name", "")),
                size=tokens.FONT_SM,
                weight=ft.FontWeight.W_600,
                color=theme.text(),
            ),
            subtitle=ft.Text(
                " · ".join(part for part in (with_sandbox(cmd, checked), container_name) if part),
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            ),
            on_click=_run,
            trailing=ft.Row(
                controls=[
                    ft.Checkbox(
                        label="no sandbox",
                        value=checked,
                        scale=tokens.SWITCH_SCALE,
                        tooltip="Add --no-sandbox for this app (Chromium and Electron need it)",
                        on_change=lambda e, c=cmd: set_sandbox(
                            {**sandbox, c: bool(e.control.value)}
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_size=tokens.ICON_SM,
                        tooltip="Delete preset",
                        on_click=_delete_preset(str(preset.get("name", ""))),
                    ),
                ],
                spacing=tokens.SPACE_XXS,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _display_card(name: str) -> ft.Control:
        caps = (st.display_support or {}).get(name) or {}

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
                            "Open display",
                            icon=ft.Icons.DESKTOP_WINDOWS,
                            on_click=_open,
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
        sections.append(_section("Distros", None, [_display_card(n) for n in containers]))
        # One banner between the two sections (owner ruling 2026-11-17).
        sections.append(pooled_banner_ad(AD_SLOT_DISPLAY, page))

    # ── Presets (last, grows with installed apps) ─────────────────────────────
    detected_rows: list[ft.Control] = []
    for container_name, apps in sorted((st.detected_apps or {}).items()):
        for app in apps:
            cmd = str(app.get("cmd", ""))
            # Default ON for every detected app; the user can uncheck an app
            # that rejects the flag. The subtitle shows the real command.
            checked = bool(sandbox.get(cmd, True))

            def _run_detected(_e, c=container_name, command=cmd) -> None:
                page.run_task(
                    methods.start_display,
                    c,
                    with_sandbox(command, bool(sandbox.get(command, True))),
                    None,
                    None,
                )

            detected_rows.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                    title=ft.Text(
                        app["label"],
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600,
                        color=theme.text(),
                    ),
                    subtitle=ft.Text(
                        " · ".join(
                            part for part in (with_sandbox(cmd, checked), container_name) if part
                        ),
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                    ),
                    on_click=_run_detected,
                    trailing=ft.Checkbox(
                        label="no sandbox",
                        value=checked,
                        scale=tokens.SWITCH_SCALE,
                        tooltip="Add --no-sandbox for this app (Chromium and Electron need it)",
                        on_change=lambda e, c=cmd: set_sandbox(
                            {**sandbox, c: bool(e.control.value)}
                        ),
                    ),
                )
            )
    preset_rows: list[ft.Control] = list(detected_rows)
    preset_rows.extend(_manual_preset_row(preset) for preset in st.app_presets or [])
    # A banner after every 5th preset, never after the last (owner ruling:
    # the same cadence as the Docker Hub search results).
    preset_rows = insert_periodic(preset_rows, "display-presets", page=page)
    preset_content: ft.Control = (
        ft.Column(controls=preset_rows, spacing=tokens.SPACE_XXS)
        if preset_rows
        else ft.Text(
            "No presets yet. Install apps in a container or save a preset from the display sheet.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        )
    )
    refresh_action = ft.Row(
        controls=[
            ft.ProgressRing(
                width=tokens.PROGRESS_RING_SM,
                height=tokens.PROGRESS_RING_SM,
                stroke_width=tokens.PROGRESS_RING_STROKE,
                visible=refreshing,
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                icon_size=tokens.ICON_SM,
                tooltip="Scan every container again for installed apps",
                disabled=refreshing,
                on_click=_refresh_presets,
            ),
        ],
        spacing=tokens.SPACE_XS,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        tight=True,
    )
    sections.append(
        _section("Presets", refresh_action, [card(preset_content, padding=tokens.SPACE_SM)])
    )

    sections.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))
    return ft.Column(
        controls=sections,
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
