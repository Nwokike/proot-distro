"""The launcher, new-display and app sheets."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.command_cell import build_command_cell
from core import theme, tokens
from core.state import state
from services.desk_service import DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
from services.desk_service.provision import install_script, package_manager_for

from .advanced import _advanced_display_controls
from .common import (
    _dialog_height,
    _picker_with_custom,
    _pill_style,
    _set_setting,
    _sheet_width,
    _status_line,
    _stream_session_log,
)

logger = logging.getLogger(__name__)

# Probed guest apps for the "Open an app" sheet: (label, command) pairs.
_APP_PRESETS = (
    ("Terminal", "xterm"),
    ("Files", "thunar"),
    ("Browser", "firefox"),
    ("Text editor", "mousepad"),
    ("Image editor", "gimp"),
    ("Office", "libreoffice"),
    ("VS Code", "code"),
)

_CUSTOM = "__custom__"


def show_display_sheet(page: ft.Page, methods, container: str, caps: dict) -> None:
    """Open the launcher sheet for a container. Plain controls; repaint in
    place when the DE pick or the install log changes."""
    selected = {DEFAULT_DESKTOP: True}

    def _current() -> str:
        return next((key for key, on in selected.items() if on), DEFAULT_DESKTOP)

    body: ft.Column = ft.Column(spacing=tokens.SPACE_SM, tight=True, width=_sheet_width(page))
    dlg: ft.AlertDialog

    # App-first: the command cell is the primary path in the ready branch too —
    # any command on its own display, edits honored, log streamed below.
    def _start_app_job(ctrl) -> None:
        cmd = ctrl.source().strip()
        if not cmd:
            methods.show_snack("enter a command for the display")
            ctrl.set_running(False)
            return
        ctrl.set_running(True)
        ctrl.clear_output()

        async def _job() -> None:

            poll = asyncio.create_task(_stream_session_log(page, ctrl, container))
            try:
                await methods.start_display(container, None, cmd, None)
            finally:
                poll.cancel()
            ctrl.set_running(False)
            if state.display_status == "running":
                page.pop_dialog()
            else:
                methods.show_snack(state.display_error or "the display did not start")

        page.run_task(_job)

    _app_cell = build_command_cell(
        page,
        source="",
        hint="command to run on its own display",
        on_run=_start_app_job,
        label="Start",
    )

    # The notebook cell (CollabShell copy) for the not-ready branch: pre-filled
    # with the install script, EDITABLE, Run streams output below. Created once
    # per sheet; the DE pick regenerates its source. The controller is stashed
    # on the page so install_display_support streams chunks into it.
    def _run_install(ctrl) -> None:
        page.run_task(methods.install_display_support, container, _current(), ctrl.source())

    try:
        _install_cell = build_command_cell(
            page,
            source=install_script(caps, DEFAULT_DESKTOP) if package_manager_for(caps) else "",
            hint="install script — edit if needed",
            on_run=_run_install,
            label="Install display support",
        )
        page._display_install_cell = _install_cell[1]
    except Exception:
        _install_cell = (ft.Container(), None)

    def _rebuild() -> None:
        # Repaint in place: build rows into a NAME, then assign (the files-modal
        # pattern) — never a literal list at the assignment site.
        caps_now = (state.display_support or {}).get(container) or {}
        has_desktop = any((caps_now.get("desktops") or {}).values())
        pm = package_manager_for(caps_now)
        rows = [_status_line(caps_now)]
        # App-first in EVERY state: single apps run with zero guest installs.
        rows.append(_app_cell[0])
        rows.append(
            ft.Text(
                "Examples:  firefox  ·  xterm  ·  gimp  ·  python3 my_pywebview_app.py",
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
        )

        def _open_apps(_e) -> None:
            page.pop_dialog()
            from .app_sheet import _show_app_sheet  # deferred: avoids a cycle

            _show_app_sheet(page, methods, container)

        rows.append(
            ft.OutlinedButton(
                "Open an app on a new display…",
                icon=ft.Icons.WINDOW_ROUNDED,
                on_click=_open_apps,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=_pill_style(),
            )
        )
        if has_desktop:
            rows.append(
                ft.Dropdown(
                    label="Desktop environment (full desktop session)",
                    value=next(
                        (de.key for de in DESKTOP_ENVIRONMENTS if de.key == _current()),
                        DEFAULT_DESKTOP,
                    ),
                    options=[ft.dropdown.Option(de.key, de.name) for de in DESKTOP_ENVIRONMENTS],
                    on_select=lambda e: _pick(e.control.value),
                    width=tokens.DROPDOWN_WIDTH,
                    border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                    text_size=tokens.FONT_XS,
                )
            )
            rows.append(
                ft.FilledButton(
                    "Start desktop session",
                    icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
                    on_click=lambda _e: (
                        page.pop_dialog(),
                        page.run_task(methods.start_display, container, _current(), None, None),
                    ),
                    width=float("inf"),
                    height=tokens.CONTROL_MD,
                    style=_pill_style(),
                )
            )
        else:
            rows.append(
                ft.Text(
                    "No desktop environment is installed here. Pick one and install it "
                    "(a few hundred MB from the container's package manager) — the display "
                    "itself runs in this app, so the apps above need nothing.",
                    size=tokens.FONT_SM,
                    color=theme.text(),
                )
            )
            rows.append(ft.Text("Desktop environment", size=tokens.FONT_XS, color=theme.text_dim()))
            de_row = ft.Row(
                controls=[
                    ft.OutlinedButton(
                        de.name + ("  ★" if de.best else ""),
                        on_click=lambda _e, k=de.key: _pick(k),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1,
                                theme.primary()
                                if selected.get(de.key)
                                else ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.text_dim()),
                            ),
                        ),
                    )
                    for de in DESKTOP_ENVIRONMENTS
                ],
                spacing=tokens.SPACE_XS,
                wrap=True,
            )
            rows.append(de_row)
            if pm and _install_cell[1] is not None:
                # Notebook cell (CollabShell copy): the install script is the
                # EDITABLE input — tweak it if needed, Run streams the output
                # into the OUTPUT panel below until the desktop is installed.
                # The DE pick regenerates the source (user edits are lost on
                # pick — intentional: a new DE means a new script).
                _install_cell[1].set_source(install_script(caps_now, _current()))
                rows.append(
                    ft.Text(
                        "Edit the script if you need to, then Run — output streams below.",
                        size=tokens.FONT_XXS,
                        color=theme.text_dim(),
                    )
                )
                rows.append(_install_cell[0])
        rows.append(
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Quality",
                        (("50", "50"), ("70", "70"), ("85", "85"), ("95", "95")),
                        "quality",
                        hint="1-95 (viewer image quality)",
                    ),
                    _picker_with_custom(
                        "Compression",
                        (("2", "2 — fast"), ("6", "6"), ("9", "9 — smallest")),
                        "compression",
                        hint="0-9 (CPU vs bandwidth)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            )
        )
        rows.append(
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Resolution",
                        (
                            ("auto", "Auto (screen shape)"),
                            ("1280x720", "1280 x 720"),
                            ("1600x900", "1600 x 900"),
                            ("1920x1080", "1920 x 1080"),
                        ),
                        "geometry",
                        hint="WxH, e.g. 2560x1440",
                    ),
                    ft.Dropdown(
                        label="Fit to screen",
                        value=str((state.display_settings or {}).get("resize", "remote")),
                        options=[
                            ft.dropdown.Option("remote", "Resize the desktop"),
                            ft.dropdown.Option("scale", "Scale (letterbox)"),
                            ft.dropdown.Option("off", "Keep the resolution"),
                        ],
                        on_select=lambda e: _set_setting("resize", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "Orientation",
                        (
                            ("landscape", "Landscape"),
                            ("portrait", "Portrait"),
                            ("auto", "System default"),
                        ),
                        "orientation",
                        hint="orientation",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            )
        )
        rows.append(
            ft.Row(
                controls=[
                    ft.Switch(
                        label="LAN — open to Wi-Fi devices",
                        value=bool((state.display_settings or {}).get("lan")),
                        on_change=lambda e: _set_setting("lan", bool(e.control.value)),
                    ),
                    ft.Switch(
                        label="Public URL — localhost.run tunnel",
                        value=bool((state.display_settings or {}).get("tunnel")),
                        on_change=lambda e: _set_setting("tunnel", bool(e.control.value)),
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
        )
        rows.append(
            ft.Text(
                "LAN binds the server to the phone's Wi-Fi address; the tunnel "
                "publishes a public *.lhr.life URL. Both are protected by the "
                "access code — share it only with your own devices.",
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
        )
        # Real server options for technical users (collapsed by default).
        rows.append(_advanced_display_controls())

        body.controls = rows
        try:
            dlg.update()
        except Exception:
            pass

    def _pick(key: str) -> None:
        selected.clear()
        selected[key] = True
        _rebuild()

    dlg = ft.AlertDialog(
        title=ft.Text(f"Display — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[body],
            scroll=ft.ScrollMode.AUTO,
            width=_sheet_width(page),
            height=_dialog_height(page),
        ),
        actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
    )

    def _on_dismiss(_e=None) -> None:
        rebuilds = getattr(page, "_display_sheet_rebuilds", None) or {}
        if rebuilds.get(container) is _rebuild:
            del rebuilds[container]
        page._display_sheet_rebuilds = rebuilds

    dlg.on_dismiss = _on_dismiss
    rebuilds = getattr(page, "_display_sheet_rebuilds", None) or {}
    rebuilds[container] = _rebuild
    page._display_sheet_rebuilds = rebuilds
    _rebuild()
    page.show_dialog(dlg)


def rebuild_display_sheet(page: ft.Page, container: str) -> None:
    """Repaint an open sheet in place (called after the display install ends),
    so the not-ready branch becomes the ready branch without reopening."""
    rebuilds = getattr(page, "_display_sheet_rebuilds", None) or {}
    rebuild = rebuilds.get(container)
    if rebuild is None:
        return
    try:
        rebuild()
    except Exception:
        pass
