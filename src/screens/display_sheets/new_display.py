"""The launcher, new-display and app sheets."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.command_cell import build_command_cell
from core import styles, theme, tokens
from core.state import state
from services.desk_service import DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
from services.desk_service import manager as desk_manager

from .advanced import _advanced_display_controls
from .common import (
    _dialog_height,
    _pill_style,
    _sheet_width,
    _stream_session_log,
)

logger = logging.getLogger(__name__)


_CUSTOM = "__custom__"


def show_new_display_sheet(page: ft.Page, methods) -> None:
    """The Display tab's "+": pick a container, then GUI application or Desktop —
    starts a NEW `container:N` display session."""
    containers = [r.get("name", "") for r in state.containers if r.get("name")]
    if not containers:
        methods.show_snack("install a container first")
        return
    if len(containers) == 1:
        _show_new_display_mode_sheet(page, methods, containers[0])
        return

    def _picked(c: str) -> None:
        page.pop_dialog()
        _show_new_display_mode_sheet(page, methods, c)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                "New display — container", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
            ),
            content=ft.Column(
                controls=[
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                        title=ft.Text(c, size=tokens.FONT_MD, weight=ft.FontWeight.W_600),
                        on_click=lambda _e, name=c: _picked(name),
                    )
                    for c in containers
                ],
                tight=True,
                spacing=tokens.SPACE_XS,
                scroll=ft.ScrollMode.AUTO,
                width=tokens.DIALOG_WIDTH,
            ),
            actions=[ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog())],
        )
    )


def _show_new_display_mode_sheet(page: ft.Page, methods, container: str) -> None:
    """App-first display launcher.

    The command cell is the primary path (any command, edits honored — the
    CollabShell notebook copy); Desktop mode picks a DE instead. The display
    number is explicit, and EVERY option the dependency supports lives in the
    collapsed "Advanced options" section — simple by default, full control one
    tap away."""
    mode = {"value": "app"}
    selected = {DEFAULT_DESKTOP: True}
    body: ft.Column = ft.Column(spacing=tokens.SPACE_SM, tight=True, width=_sheet_width(page))
    dlg: ft.AlertDialog
    advanced = {"value": False}
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)
    next_free = manager.next_free_display() if manager is not None else 0
    display_no = {"value": next_free if next_free >= 0 else 0}
    fields: dict = {}

    def _current() -> str:
        return next((key for key, on in selected.items() if on), DEFAULT_DESKTOP)

    def _collect_options() -> dict | None:
        """The advanced login options, or None (with a snack) when a value is
        malformed — same validation as the shell options dialog."""
        opts: dict = {}
        user = (fields["user"].value or "").strip()
        if user and user != "root":
            opts["user"] = user
        work_dir = (fields["work_dir"].value or "").strip()
        if work_dir:
            opts["work_dir"] = work_dir
        from services.session_service.login_options import parse_env_bind

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
        return opts

    def _start_app_job(ctrl) -> None:
        """Run the app display FROM the cell: the command stays editable, the
        session log streams into the OUTPUT panel, and when the display is
        running the sheet closes — the display takes over."""
        cmd = ctrl.source().strip()
        if not cmd:
            methods.show_snack("enter a command for the display")
            ctrl.set_running(False)
            return
        options = _collect_options()
        if options is None:
            ctrl.set_running(False)
            return
        ctrl.set_running(True)
        ctrl.clear_output()

        async def _job() -> None:

            poll = asyncio.create_task(_stream_session_log(page, ctrl, container))
            try:
                await methods.start_display(container, None, cmd, display_no["value"], options)
            finally:
                poll.cancel()
            ctrl.set_running(False)
            if state.display_status == "running":
                # The display takes over — AppShell swaps to the live surface.
                page.pop_dialog()
            else:
                methods.show_snack(state.display_error or "the display did not start")

        page.run_task(_job)

    def _pick(key: str) -> None:
        selected.clear()
        selected[key] = True
        _rebuild()

    def _start(_e) -> None:
        if mode["value"] == "app":
            if _app_cell is not None:
                _start_app_job(_app_cell[1])
            return
        options = _collect_options()
        if options is None:
            return
        page.pop_dialog()
        page.run_task(
            methods.start_display,
            container,
            _current(),
            None,
            display_no["value"],
            options,
        )

    # The notebook command cell (CollabShell copy) for single-app mode: the
    # command is editable, Run streams the session log into OUTPUT, and the
    # sheet closes when the display takes over. Created once per sheet.
    def _app_run(ctrl) -> None:
        _start_app_job(ctrl)

    try:
        _app_cell = build_command_cell(
            page,
            source="",
            hint="command to run on its own display",
            on_run=_app_run,
            label="Start",
        )
    except Exception:
        _app_cell = (ft.Container(), None)

    # Advanced fields are created once so their values survive mode switches —
    # everything proot-distro's login supports, optional and collapsed.
    def _field(key: str, label: str, hint: str = "", multiline: bool = False) -> ft.TextField:
        tf = ft.TextField(
            label=label,
            hint_text=hint,
            multiline=multiline,
            text_size=tokens.FONT_XS,
            border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        )
        fields[key] = tf
        return tf

    adv_user = _field("user", "User (-u)", "root")
    adv_work = _field("work_dir", "Work dir (-w)", "/root")
    adv_env = _field("env", "Env (-e VAR=VALUE)", "one per line", multiline=True)
    adv_bind = _field("bind", "Bind (-b PATH[:PATH])", "one per line", multiline=True)
    adv_hostname = _field("hostname", "Hostname (--hostname)", "guest hostname")
    adv_kernel = _field("kernel", "Kernel release (--kernel)", "uname -r string")
    adv_emulator_path = _field(
        "emulator", "Emulator (--emulator PATH)", "qemu-user path (foreign-arch images)"
    )
    adv_shared_tmp = ft.Switch(
        label="Shared tmp", label_position=ft.LabelPosition.LEFT, scale=tokens.SWITCH_SCALE
    )
    adv_shared_home = ft.Switch(
        label="Shared home", label_position=ft.LabelPosition.LEFT, scale=tokens.SWITCH_SCALE
    )
    adv_isolated = ft.Switch(
        label="Isolated", label_position=ft.LabelPosition.LEFT, scale=tokens.SWITCH_SCALE
    )
    adv_fix_ports = ft.Switch(
        label="Fix low ports", label_position=ft.LabelPosition.LEFT, scale=tokens.SWITCH_SCALE
    )
    fields.update(
        {
            "shared_tmp": adv_shared_tmp,
            "shared_home": adv_shared_home,
            "isolated": adv_isolated,
            "fix_low_ports": adv_fix_ports,
        }
    )

    advanced_col = ft.Column(
        controls=[
            ft.Text(
                "Login options",
                size=tokens.FONT_XS,
                weight=ft.FontWeight.W_600,
                color=theme.text_dim(),
            ),
            adv_user,
            adv_work,
            adv_env,
            adv_bind,
            adv_hostname,
            adv_kernel,
            adv_emulator_path,
            ft.Row(
                controls=[adv_shared_tmp, adv_shared_home],
                wrap=True,
                spacing=tokens.SPACE_MD,
            ),
            ft.Row(
                controls=[adv_isolated, adv_fix_ports],
                wrap=True,
                spacing=tokens.SPACE_MD,
            ),
            ft.Text(
                "Display options",
                size=tokens.FONT_XS,
                weight=ft.FontWeight.W_600,
                color=theme.text_dim(),
            ),
            _advanced_display_controls(),
        ],
        spacing=tokens.SPACE_XS,
        visible=False,
    )

    def _toggle_adv() -> None:
        advanced["value"] = not advanced["value"]
        adv_toggle.icon = (
            ft.Icons.EXPAND_LESS_ROUNDED if advanced["value"] else ft.Icons.EXPAND_MORE_ROUNDED
        )
        adv_toggle.tooltip = "Hide advanced options" if advanced["value"] else "Advanced options"
        advanced_col.visible = advanced["value"]
        try:
            dlg.update()
        except Exception:
            pass

    adv_toggle = ft.OutlinedButton(
        "Advanced options",
        icon=ft.Icons.EXPAND_MORE_ROUNDED,
        on_click=lambda _e: _toggle_adv(),
        style=styles.pill_button_style(),
    )

    display_dd = ft.Dropdown(
        label="Display",
        value=str(display_no["value"]),
        options=[
            ft.dropdown.Option(str(n), f":{n}") for n in range(desk_manager.MAX_DISPLAY_NUMBER + 1)
        ],
        on_select=lambda e: display_no.__setitem__("value", int(e.control.value or 0)),
        width=tokens.FIELD_DISPLAY_WIDTH,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        text_size=tokens.FONT_XS,
    )

    def _rebuild() -> None:
        is_app = mode["value"] == "app"
        controls = [
            ft.Text(
                "Run any app on its own display — or a full desktop.",
                size=tokens.FONT_SM,
                color=theme.text_dim(),
            ),
            ft.Row(
                controls=[
                    ft.OutlinedButton(
                        "App",
                        icon=ft.Icons.WINDOW_ROUNDED,
                        on_click=lambda _e: _set_mode("app"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1, theme.primary() if is_app else theme.surface_alt()
                            ),
                        ),
                    ),
                    ft.OutlinedButton(
                        "Desktop",
                        icon=ft.Icons.DESKTOP_WINDOWS,
                        on_click=lambda _e: _set_mode("desktop"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1, theme.primary() if not is_app else theme.surface_alt()
                            ),
                        ),
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
        ]
        if is_app:
            # The notebook cell IS the input+output: type the command, Run, and
            # the session log streams below until the display takes over.
            controls.append(_app_cell[0])
            controls.append(
                ft.Text(
                    "Examples:  firefox  ·  xterm  ·  python3 -m http.server 8080  ·  "
                    "python3 my_pywebview_app.py",
                    size=tokens.FONT_XXS,
                    color=theme.text_dim(),
                )
            )
        else:
            controls.append(
                ft.Dropdown(
                    label="Desktop environment",
                    value=_current(),
                    options=[ft.dropdown.Option(de.key, de.name) for de in DESKTOP_ENVIRONMENTS],
                    on_select=lambda e: _pick(e.control.value),
                    width=tokens.DROPDOWN_WIDTH,
                    border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                    text_size=tokens.FONT_XS,
                )
            )
            caps_now = (state.display_support or {}).get(container) or {}
            if not any((caps_now.get("desktops") or {}).values()):
                controls.append(
                    ft.Text(
                        "No desktop environment is installed in this container yet — "
                        "open its card → Open display to install one first.",
                        size=tokens.FONT_XXS,
                        color=theme.warn(),
                    )
                )
        controls.append(
            ft.Row(
                controls=[
                    ft.Text("Display", size=tokens.FONT_SM, color=theme.text_dim()),
                    display_dd,
                ],
                spacing=tokens.SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        controls.append(adv_toggle)
        controls.append(advanced_col)
        controls.append(
            ft.FilledButton(
                "Start display",
                icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
                on_click=_start,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=_pill_style(),
            )
        )
        body.controls = controls
        try:
            dlg.update()
        except Exception:
            pass

    def _set_mode(next_mode: str) -> None:
        mode["value"] = next_mode
        _rebuild()

    dlg = ft.AlertDialog(
        title=ft.Text(f"New display — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[body],
            scroll=ft.ScrollMode.AUTO,
            width=_sheet_width(page),
            height=_dialog_height(page),
        ),
        actions=[ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog())],
    )
    _rebuild()
    page.show_dialog(dlg)
