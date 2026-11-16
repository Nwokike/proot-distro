"""The ONE display sheet: App | Desktop, sharing every common option.

One sheet replaced the three partial ones: the card launcher, the "run one
app" sheet and the "+" new-display sheet. Both modes share the display number,
image options, viewer options, the advanced Xvnc/audio surface and the login
flags. Only the mode block differs: the app list plus a command box and saved
presets, or the desktop environment plus the install cell.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.command_cell import build_command_cell
from components.ui import pill_dropdown
from core import theme, tokens
from core.state import state
from screens.container_dialogs.shell_options import option_error
from services import proot_service
from services.desk_service import DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
from services.desk_service.provision import install_script, package_manager_for
from services.session_service.login_options import parse_env_bind

from .advanced import _advanced_display_controls
from .common import (
    _dialog_height,
    _pill_style,
    _sheet_width,
    _status_line,
    _stream_session_log,
)
from .sheet_parts import (
    add_display_options,
    install_cell_placeholder,
    mode_pill,
    new_preset_dialog,
    preset_tile,
    run_as_block,
)

logger = logging.getLogger(__name__)


def show_display_sheet(
    page: ft.Page, methods, container: str, caps: dict, start_mode: str = "app"
) -> None:
    """Open the display sheet for a container. App first (owner ruling
    2026-11-15) — one app needs nothing installed; Desktop is the second pill.
    `start_mode` opens straight into either; the switch is always visible."""
    mode = {"value": start_mode}
    selected = {DEFAULT_DESKTOP: True}
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)
    next_free = manager.next_free_display() if manager is not None else 0
    display_no = {"value": next_free if next_free >= 0 else 0}
    body: ft.Column = ft.Column(spacing=tokens.SPACE_SM, tight=True, width=_sheet_width(page))
    dlg: ft.AlertDialog
    fields: dict = {}
    # Built ONCE: a fresh block per repaint would drop whatever the user typed
    # when they switch modes or pick a desktop environment.
    run_as_control = run_as_block(fields)

    def _current() -> str:
        return next((key for key, on in selected.items() if on), DEFAULT_DESKTOP)

    def _open_apps(_e) -> None:
        mode["value"] = "app"
        _rebuild()

    def _open_desktop(_e) -> None:
        mode["value"] = "desktop"
        _rebuild()

    # ── install cell (desktop mode, not installed) ────────────────────────────
    def _run_install(ctrl) -> None:
        page.run_task(methods.install_display_support, container, _current(), ctrl.source())

    def _source_for(caps_now: dict) -> str:
        if package_manager_for(caps_now):
            return install_script(caps_now, _current())
        return install_cell_placeholder(container)

    try:
        _install_cell = build_command_cell(
            page,
            source=_source_for(caps or {}),
            hint="install script (edit if needed)",
            on_run=_run_install,
            label="Install desktop",
        )
        page._display_install_cell = _install_cell[1]
    except Exception:
        logger.exception("install cell unavailable for %s", container)
        _install_cell = (ft.Container(), None)

    def _recheck(_e) -> None:
        page.run_task(methods.probe_display, container)
        page.run_task(rebuild_display_sheet, page, container)

    # ── app probe (App mode) ──────────────────────────────────────────────────
    app_results = ft.Column(
        controls=[ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD)],
        spacing=tokens.SPACE_XS,
    )
    probed = {"done": False}

    def _start_app_job(ctrl) -> None:
        """Run the cell's command on its own display, streaming its log into the
        cell's OUTPUT panel, exactly like CollabShell's notebook cell. The
        display takes over once it starts."""
        cmd = ctrl.source().strip()
        if not cmd:
            methods.show_snack("enter a command for the app display")
            ctrl.set_running(False)
            return
        opts = _options()
        if opts is None:
            ctrl.set_running(False)
            return
        ctrl.set_running(True)
        ctrl.clear_output()

        async def _job() -> None:
            poll = asyncio.create_task(_stream_session_log(page, ctrl, container))
            try:
                await methods.start_display(container, None, cmd, display_no["value"], opts or None)
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
        hint="command to run on its own display (e.g. python3 app.py)",
        on_run=_start_app_job,
        label="Start",
    )

    def _cell_source() -> str:
        controller = _app_cell[1]
        return (controller.source() if controller is not None else "") or ""

    def _save_preset_dialog(_e=None) -> None:
        new_preset_dialog(page, methods, container, _cell_source(), _rebuild)

    def _preset_tile(preset: dict) -> ft.Control:
        cmd = str(preset.get("cmd", ""))
        name = str(preset.get("name", ""))

        def _run(_e) -> None:
            _start(app_command=cmd, preset=preset)

        return preset_tile(
            preset,
            _run,
            lambda _e, n=name: _delete_preset(n),
        )

    def _delete_preset(name: str) -> None:
        async def _do() -> None:
            await methods.delete_app_preset(name)
            _rebuild()

        page.run_task(_do)

    async def _probe() -> None:
        # ONE source of truth: the controller's probe_apps fills
        # state.detected_apps from the container's .desktop entries.
        found = (state.detected_apps or {}).get(container)
        if found is None:
            await methods.probe_apps(container)
            found = (state.detected_apps or {}).get(container) or []
        rows = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                title=ft.Text(app["label"], size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                subtitle=ft.Text(app["cmd"], size=tokens.FONT_XS, color=theme.text_dim()),
                on_click=lambda _e, c=app["cmd"]: _start(app_command=c),
            )
            for app in found
        ]
        app_results.controls = rows or [
            ft.Text(
                "No app entries found in this container. Type a command below.",
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            )
        ]
        probed["done"] = True
        try:
            dlg.update()
        except Exception:
            pass

    # ── run ───────────────────────────────────────────────────────────────────
    def _options() -> dict | None:
        """The login/run options, validated against the container first."""
        opts: dict = {}
        user = (fields["user"].value or "").strip()
        if user:
            opts["user"] = user
        work_dir = (fields["work_dir"].value or "").strip()
        if work_dir:
            opts["work_dir"] = work_dir
        env_lines, bind_lines, error = parse_env_bind(fields["env"].value, fields["bind"].value)
        if error:
            methods.show_snack(error)
            return None
        if env_lines:
            opts["env"] = env_lines
        if bind_lines:
            opts["bind"] = bind_lines
        for key in ("shared_tmp", "shared_home", "isolated", "fix_low_ports"):
            if fields[key].value:
                opts[key] = True
        for key in ("hostname", "kernel", "emulator"):
            value = (fields[key].value or "").strip()
            if value:
                opts[key] = value
        users = proot_service.container_users(container)
        problem = option_error(
            container,
            users,
            {
                **opts,
                "user": user or "root",
                # Raw text too: the validator checks host bind paths and env
                # syntax, which only exist in the fields.
                "bind_text": fields["bind"].value,
                "env_text": fields["env"].value,
            },
        )
        if problem:
            methods.show_snack(problem)
            return None
        return opts

    def _start(app_command: str | None = None, preset: dict | None = None) -> None:
        if mode["value"] == "app" and not (app_command or "").strip():
            methods.show_snack("type a command for the app display")
            return
        opts = _options()
        if opts is None:
            return
        if preset:
            # A saved preset carries its own launch options.
            if preset.get("work_dir"):
                opts = {**opts, "work_dir": preset["work_dir"]}
            if preset.get("env"):
                opts = {**opts, "env": list(preset["env"])}
        page.pop_dialog()
        page.run_task(
            methods.start_display,
            container,
            _current() if mode["value"] == "desktop" else None,
            app_command if mode["value"] == "app" else None,
            display_no["value"],
            opts or None,
        )

    def _rebuild() -> None:
        caps_now = (state.display_support or {}).get(container) or {}
        has_desktop = any((caps_now.get("desktops") or {}).values())
        rows: list[ft.Control] = [
            ft.Container(
                alignment=ft.Alignment.CENTER,
                content=ft.Container(
                    border=ft.Border.all(
                        tokens.HAIRLINE,
                        ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.text()),
                    ),
                    border_radius=tokens.RADIUS_SM,
                    padding=ft.Padding.all(tokens.SPACE_XXS),
                    content=ft.Row(
                        controls=[
                            mode_pill(
                                "App",
                                ft.Icons.WINDOW_ROUNDED,
                                mode["value"] == "app",
                                _open_apps,
                            ),
                            mode_pill(
                                "Desktop",
                                ft.Icons.DESKTOP_WINDOWS_ROUNDED,
                                mode["value"] == "desktop",
                                _open_desktop,
                            ),
                        ],
                        spacing=tokens.SPACE_XS,
                    ),
                ),
            ),
            _status_line(caps_now),
        ]

        if mode["value"] == "app":
            if not probed["done"]:
                # Opening in App mode, or switching to it later, starts the
                # detection; otherwise the spinner would stay forever.
                page.run_task(_probe)
            rows.append(
                ft.Text(
                    "One app alone on its own display. Nothing to install.",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                )
            )
            rows.append(ft.Text("Preset apps", size=tokens.FONT_XS, color=theme.text_dim()))
            rows.append(app_results)
            presets = state.app_presets or []
            if presets:
                rows.append(ft.Text("Your presets", size=tokens.FONT_XS, color=theme.text_dim()))
                rows.extend(_preset_tile(preset) for preset in presets)
            # The command cell carries its own play button and OUTPUT panel
            # (CollabShell's notebook shape). Preset saving sits UNDER it, which
            # also keeps two buttons off one line on a small screen.
            rows.append(_app_cell[0])
            rows.append(
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Save as preset…",
                            icon=ft.Icons.BOOKMARK_ADD_ROUNDED,
                            on_click=_save_preset_dialog,
                            tooltip="Name this command and keep it for one-tap runs",
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                )
            )
        elif has_desktop:
            rows.append(
                ft.Row(
                    controls=[
                        pill_dropdown(
                            "Desktop environment",
                            ft.Icons.DESKTOP_WINDOWS_ROUNDED,
                            [de.key for de in DESKTOP_ENVIRONMENTS],
                            _current(),
                            _pick,
                            tooltip="Desktop environment (full desktop session)",
                            labels={de.key: de.name for de in DESKTOP_ENVIRONMENTS},
                        ),
                    ],
                )
            )
            rows.append(
                ft.FilledButton(
                    "Start desktop",
                    icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
                    on_click=lambda _e: _start(),
                    width=float("inf"),
                    height=tokens.CONTROL_MD,
                    style=_pill_style(),
                )
            )
        else:
            rows.append(
                ft.Text(
                    "No desktop is installed in this container. A desktop needs the "
                    "session, a panel and a terminal. Install them below, or switch "
                    "to App mode (nothing to install).",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                )
            )
            rows.append(ft.Text("Desktop environment", size=tokens.FONT_XS, color=theme.text_dim()))
            rows.append(
                ft.Row(
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
                                    else ft.Colors.with_opacity(
                                        tokens.OPACITY_LIGHT, theme.text_dim()
                                    ),
                                ),
                            ),
                        )
                        for de in DESKTOP_ENVIRONMENTS
                    ],
                    spacing=tokens.SPACE_XS,
                    wrap=True,
                )
            )
            if _install_cell[1] is not None:
                _install_cell[1].set_source(_source_for(caps_now))
                rows.append(
                    ft.Text(
                        "Edit the script if your distro needs something else, then "
                        "Run. Output streams below.",
                        size=tokens.FONT_XXS,
                        color=theme.text_dim(),
                    )
                )
                rows.append(_install_cell[0])
            rows.append(
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Re-check container",
                            icon=ft.Icons.REFRESH_ROUNDED,
                            on_click=_recheck,
                            tooltip="Probe again after installing by hand",
                        ),
                    ],
                )
            )

        # ── shared options (identical in both modes) ──────────────────────────
        rows.extend(add_display_options(display_no))
        rows.append(_advanced_display_controls())
        rows.append(run_as_control)

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
        title=ft.Text(f"Display: {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
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
        logger.debug("display sheet rebuild failed", exc_info=True)
