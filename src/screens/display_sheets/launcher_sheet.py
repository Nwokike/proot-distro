"""The ONE display sheet: run any command on its own display.

One sheet replaced the three partial ones (card launcher, "run one app", "+"
new display). It shows the container's status, its detected apps, the user's
saved presets for THAT container, the command cell, and the shared display /
viewer / login options. There is no desktop installer and no App | Desktop
switch (owner rulings 2026-11-15 and 2026-11-17): a desktop is simply a
command such as startxfce4 typed into the cell.

The presets block refreshes like CollabShell: a spinner while the container is
being re-scanned and a refresh button that forces a fresh scan, so an app
installed inside the container shows up without restarting the app.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.command_cell import build_command_cell
from core import theme, tokens
from core.state import state
from screens.container_dialogs.shell_options import option_error
from services import proot_service
from services.session_service.login_options import parse_env_bind

from .advanced import _advanced_display_controls
from .common import (
    _dialog_height,
    _sheet_width,
    _status_line,
    _stream_session_log,
)
from .sheet_parts import (
    add_display_options,
    new_preset_dialog,
    preset_row,
    run_as_block,
    sandbox_default,
    with_sandbox,
)

logger = logging.getLogger(__name__)

GESTURE_HINT = "One finger drags the mouse. Two fingers scroll. Pinch zooms."


def show_display_sheet(page: ft.Page, methods, container: str, caps: dict) -> None:
    """ONE display sheet: run any command on its own display."""
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)
    next_free = manager.next_free_display() if manager is not None else 0
    display_no = {"value": next_free if next_free >= 0 else 0}
    body: ft.Column = ft.Column(spacing=tokens.SPACE_SM, tight=True, width=_sheet_width(page))
    dlg: ft.AlertDialog
    fields: dict = {}
    # Built ONCE: a fresh block per repaint would drop whatever the user typed.
    run_as_control = run_as_block(fields)
    # Per-app "--no-sandbox" checkbox state, keyed by the app command. Default
    # ON only for the families that refuse to run as root without it.
    sandbox_checks: dict[str, bool] = {}

    # ── app probe (with the CollabShell spinner + refresh) ───────────────────
    app_results = ft.Column(
        controls=[ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD)],
        spacing=tokens.SPACE_XS,
    )
    probe_ui = {"busy": False, "done": False}

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
                await methods.start_display(container, cmd, display_no["value"], opts or None)
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
        controller_ = _app_cell[1]
        return (controller_.source() if controller_ is not None else "") or ""

    def _save_preset_dialog(_e=None) -> None:
        new_preset_dialog(page, methods, container, _cell_source(), _rebuild)

    def _preset_tile(preset: dict) -> ft.Control:
        cmd = str(preset.get("cmd", ""))
        name = str(preset.get("name", ""))
        # A user-made preset starts UNCHECKED: it is the user's own command.
        sandbox_checks.setdefault(cmd, False)

        def _run(_e) -> None:
            _start(
                app_command=with_sandbox(cmd, sandbox_checks.get(cmd, False)),
                preset=preset,
            )

        return preset_row(
            preset,
            _run,
            lambda _e, n=name: _delete_preset(n),
            sandbox_checked=sandbox_checks.get(cmd, False),
            on_sandbox=lambda enabled, c=cmd: _set_preset_sandbox(c, enabled),
        )

    def _set_preset_sandbox(cmd: str, enabled: bool) -> None:
        sandbox_checks[cmd] = enabled
        _rebuild()

    def _delete_preset(name: str) -> None:
        async def _do() -> None:
            await methods.delete_app_preset(name)
            _rebuild()

        page.run_task(_do)

    def _app_row(app: dict) -> ft.Control:
        cmd = str(app.get("cmd", ""))
        # Detected apps default to checked only for the Chromium/Electron
        # families; a GTK app rejects the unknown flag (owner ruling
        # 2026-11-17: detected checked, except apps that do not take it).
        sandbox_checks.setdefault(cmd, sandbox_default(cmd))
        subtitle = ft.Text(
            with_sandbox(cmd, sandbox_checks[cmd]),
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        )

        def _toggle(e, command=cmd) -> None:
            sandbox_checks[command] = bool(e.control.value)
            # Repaint through the sheet's rebuild: the command line above the
            # rows shows the flag appear/disappear, and the row's subtitle
            # follows from the same dict.
            _rebuild()

        def _run(_e) -> None:
            _start(app_command=with_sandbox(cmd, sandbox_checks.get(cmd, sandbox_default(cmd))))

        return ft.ListTile(
            is_three_line=True,
            leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
            title=ft.Text(app["label"], size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
            subtitle=ft.Column(
                controls=[
                    subtitle,
                    # The checkbox sits on its OWN line: at the trailing edge it
                    # squeezed the title on a narrow phone (device 2026-11-17).
                    ft.Row(
                        controls=[
                            ft.Checkbox(
                                label="no sandbox",
                                value=sandbox_checks[cmd],
                                scale=tokens.SWITCH_SCALE,
                                tooltip="Add --no-sandbox for this app "
                                "(Chromium and Electron need it)",
                                on_change=_toggle,
                            )
                        ],
                        spacing=tokens.SPACE_XXS,
                        tight=True,
                    ),
                ],
                spacing=tokens.SPACE_XXS,
                tight=True,
            ),
            on_click=_run,
        )

    async def _probe(force: bool = False) -> None:
        probe_ui["busy"] = True
        _rebuild()
        try:
            await methods.probe_apps(container, force)
        finally:
            probe_ui["busy"] = False
        probe_ui["done"] = True
        _render_app_results((state.detected_apps or {}).get(container) or [])
        try:
            dlg.update()
        except Exception:
            pass

    def _render_app_results(found: list) -> None:
        """Rebuild the detected rows (their checkbox state and command preview)."""
        rows = [_app_row(app) for app in found]
        app_results.controls = rows or [
            ft.Text(
                "No app entries found in this container. Type a command below.",
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            )
        ]

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
        if not (app_command or "").strip():
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
            app_command,
            display_no["value"],
            opts or None,
        )

    def _rebuild() -> None:
        caps_now = (state.display_support or {}).get(container) or {}
        if not probe_ui["done"] and not probe_ui["busy"]:
            page.run_task(_probe)
        if probe_ui["done"]:
            # Re-render the detected rows so their checkbox and the command
            # preview reflect the current sandbox choices.
            _render_app_results((state.detected_apps or {}).get(container) or [])
        rows: list[ft.Control] = [_status_line(caps_now)]

        # ── detected apps: label + refresh, then the rows ─────────────────────
        rows.append(
            ft.Row(
                controls=[
                    ft.Text("Preset apps", size=tokens.FONT_XS, color=theme.text_dim()),
                    ft.Container(expand=True),
                    ft.ProgressRing(
                        width=tokens.PROGRESS_RING_SM,
                        height=tokens.PROGRESS_RING_SM,
                        stroke_width=tokens.PROGRESS_RING_STROKE,
                        visible=probe_ui["busy"],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        icon_size=tokens.ICON_SM,
                        tooltip="Scan this container again for installed apps",
                        disabled=probe_ui["busy"],
                        on_click=lambda _e: page.run_task(_probe, True),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_XS,
            )
        )
        rows.append(app_results)
        # ONLY this container's presets (owner ruling 2026-11-17): a preset
        # made for another distro must not appear in every sheet.
        presets = [
            preset
            for preset in (state.app_presets or [])
            if str(preset.get("container") or container) == container
        ]
        if presets:
            rows.append(ft.Text("Your presets", size=tokens.FONT_XS, color=theme.text_dim()))
            rows.extend(_preset_tile(preset) for preset in presets)
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
        rows.append(
            ft.Text(
                GESTURE_HINT,
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
        )

        # ── shared options ─────────────────────────────────────────────────────
        rows.extend(add_display_options(display_no))
        rows.append(_advanced_display_controls())
        rows.append(run_as_control)

        body.controls = rows
        try:
            dlg.update()
        except Exception:
            pass

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
