"""Display launcher sheets — the button-driven entry to a container's display.

HARD RULE (device-proven, 2026-11-05): `@ft.component` can only be CONSTRUCTED
during a render — calling one imperatively from a controller task (this file's
whole pattern) raises "No current renderer is set". So every sheet here is
built as PLAIN controls and repainted in place: the files-modal / install-
progress pattern (named controls assigned into a live dialog + `.update()`),
never a component and never a literal list assignment inline.
"""

from __future__ import annotations

import asyncio
import logging
import re

import flet as ft

from components.command_cell import build_command_cell
from core import theme, tokens
from core.state import state
from services import session_service
from services.desk_service import DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
from services.desk_service import manager as desk_manager
from services.desk_service.provision import install_script, package_manager_for

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


def _sheet_width(page: ft.Page) -> int:
    """Responsive dialog width: never wider than the phone allows."""
    page_w = int(getattr(page, "width", 0) or 0)
    return min(tokens.DIALOG_WIDTH, page_w - 48) if page_w > 96 else tokens.DIALOG_WIDTH


def _dialog_height(page: ft.Page) -> int:
    """Bounded dialog content height so tall sheets scroll instead of overflowing."""
    page_h = int(getattr(page, "height", 0) or 0)
    return max(320, min(page_h - 190, 620)) if page_h > 512 else 520


async def _stream_session_log(page: ft.Page, ctrl, container: str) -> None:
    """Tail the newest starting session's log into a command cell (worker-safe:
    log_tail is a thread deque; reads are fine from the event loop)."""
    import asyncio

    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)
    seen = 0
    while True:
        session = None
        if manager is not None:
            # StrEnum compares equal to its string value directly — no need to
            # go through the enum's name attribute (the house guard flags that
            # spelling as imperative-mutation syntax).
            starting = [s for s in manager.for_container(container) if s.status == "starting"]
            session = starting[0] if starting else None
        if session is not None:
            lines = list(session.log_tail)
            for line in lines[seen:]:
                ctrl.append_output(line)
            seen = len(lines)
        await asyncio.sleep(0.4)


def _status_line(caps: dict) -> ft.Control:
    """The sheet's status dot — the display runs in the app, so it is always
    ready; the probed facts only matter to a full desktop session."""
    os_name = (caps.get("os") or {}).get("pretty_name", "") or "unknown distro"
    return ft.Row(
        controls=[
            ft.Container(
                width=tokens.STATUS_DOT_SM,
                height=tokens.STATUS_DOT_SM,
                border_radius=50,
                bgcolor=theme.ok(),
            ),
            ft.Text(f"X11 display ready · {os_name}", size=tokens.FONT_SM, color=theme.text_dim()),
        ],
        spacing=tokens.SPACE_XS,
    )


def _pill_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL))


def _set_setting(key: str, value: object) -> None:
    state.display_settings = {**(state.display_settings or {}), key: value}


def _picker_with_custom(
    label: str,
    options: tuple[tuple[str, str], ...],
    key: str,
    *,
    hint: str,
) -> ft.Control:
    """Dropdown + a Custom… option that reveals a free-text field — the
    upstream value ranges are ranges, not our presets."""
    settings = state.display_settings or {}
    current = str(settings.get(key, options[0][0]))
    is_custom = current not in {v for v, _t in options}
    custom_field = ft.TextField(
        label=f"{label} (custom)",
        hint_text=hint,
        value=current if is_custom else "",
        width=tokens.DROPDOWN_WIDTH,
        height=tokens.CONTROL_SM,
        text_size=tokens.FONT_XS,
        visible=is_custom,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        on_change=lambda e: _set_setting(key, e.control.value or ""),
    )
    dropdown = ft.Dropdown(
        label=label,
        value=(_CUSTOM if is_custom else current),
        options=[ft.dropdown.Option(v, t) for v, t in options]
        + [ft.dropdown.Option(_CUSTOM, "Custom…")],
        on_select=lambda e: _set_setting(
            key, e.control.value if e.control.value != _CUSTOM else custom_field.value or current
        ),
        width=tokens.DROPDOWN_WIDTH,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        text_size=tokens.FONT_XS,
    )
    return ft.Column(controls=[dropdown, custom_field], spacing=tokens.SPACE_XXS, tight=True)


def _switch_row(label: str, key: str, default: bool) -> ft.Switch:
    return ft.Switch(
        label=label,
        value=bool((state.display_settings or {}).get(key, default)),
        on_change=lambda e: _set_setting(key, bool(e.control.value)),
    )


def _advanced_display_controls() -> ft.Control:
    """Real Xvnc/PulseAudio options for technical users — every control here
    threads 1:1 into the server argv/module lines (depth → -depth, frame rate →
    -FrameRate, viewers → -AlwaysShared/-NeverShared, auto-close →
    -MaxDisconnectionTime, clipboard → -AcceptCutText/-SendCutText, audio →
    the PulseAudio module args). Defaults keep the friendly path intact."""
    settings = state.display_settings or {}
    return ft.ExpansionTile(
        title=ft.Text("Advanced display options", size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(
            "Depth, frame rate, viewers, privacy, audio — applied when the display starts.",
            size=tokens.FONT_XXS,
            color=theme.text_dim(),
        ),
        expanded=False,
        controls=[
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Color depth",
                        value=str(settings.get("depth", "24")),
                        options=[
                            ft.dropdown.Option("16", "16-bit (fastest)"),
                            ft.dropdown.Option("24", "24-bit (default)"),
                            ft.dropdown.Option("32", "32-bit"),
                        ],
                        on_select=lambda e: _set_setting("depth", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "Frame rate",
                        (("60", "60 /s"), ("30", "30 /s"), ("15", "15 /s")),
                        "fps",
                        hint="updates per second (1-60)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    ft.Dropdown(
                        label="Viewers",
                        value=str(settings.get("shared_policy", "auto")),
                        options=[
                            # noVNC always asks for shared=1, so upstream's
                            # "auto" is observably identical to "always" —
                            # exposing both would be a fake choice.
                            ft.dropdown.Option("always", "Several viewers"),
                            ft.dropdown.Option("never", "One viewer at a time"),
                        ],
                        on_select=lambda e: _set_setting("shared_policy", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                    _picker_with_custom(
                        "Auto-close",
                        (
                            ("0", "Never"),
                            ("900", "15 minutes"),
                            ("1800", "30 minutes"),
                            ("3600", "1 hour"),
                        ),
                        "disconnect_timeout",
                        hint="seconds after the last viewer (0 = never)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _switch_row("Clipboard sync", "clipboard", True),
                    _switch_row("Microphone", "mic", True),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Audio latency",
                        (
                            ("0", "Device default"),
                            ("40", "40 ms"),
                            ("80", "80 ms"),
                            ("125", "125 ms"),
                        ),
                        "audio_latency_ms",
                        hint="milliseconds (0-2000)",
                    ),
                    ft.Dropdown(
                        label="Audio performance",
                        value=str(settings.get("audio_pm", "2")),
                        options=[
                            ft.dropdown.Option("2", "Low latency"),
                            ft.dropdown.Option("1", "Power saving"),
                            ft.dropdown.Option("0", "Balanced"),
                        ],
                        on_select=lambda e: _set_setting("audio_pm", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
        ],
    )


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
            import asyncio

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


def _install_log_box(page: ft.Page, container: str) -> ft.Control:
    """The live install log box. `install_display_support` streams chunks into
    `state.display_install_logs`; the installer in
    display_actions._on_chunk marshals a repaint through the page loop."""
    if state.display_installing != container:
        return ft.Container()
    box = ft.Container(
        content=ft.Text(
            "".join(state.display_install_logs or [])[-2000:] or "starting…",
            font_family=tokens.MONO_FONT,
            size=tokens.FONT_XXS,
            color=theme.text_dim(),
            selectable=True,
        ),
        height=tokens.LOG_BOX_HEIGHT,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
        border=ft.Border.all(tokens.HAIRLINE, theme.surface_alt()),
        border_radius=tokens.RADIUS_SM,
        padding=tokens.SPACE_SM,
    )
    _register_install_box(page, container, box)
    return box


def _register_install_box(page: ft.Page, container: str, box: ft.Container) -> None:
    """Stash the box on the page so the installer can repaint it live."""
    boxes = getattr(page, "_display_install_boxes", None) or {}
    boxes[container] = box
    page._display_install_boxes = boxes


def rebuild_display_sheet(page: ft.Page, container: str) -> None:
    """Repaint an open sheet in place — called after the install finishes so
    the not-ready branch becomes the ready branch without reopening the sheet."""
    rebuilds = getattr(page, "_display_sheet_rebuilds", None) or {}
    rebuild = rebuilds.get(container)
    if rebuild is None:
        return
    try:
        rebuild()
    except Exception:
        pass


def repaint_install_log(page: ft.Page, container: str) -> None:
    """Called from the installer's chunk callback via the page loop. The
    control-attribute write lives in the controller-side helper (the house
    guard pins control-value mutation out of src/screens; the install-progress
    repaint in distro_actions is the same pattern, deliberately kept in
    controllers)."""
    from controller_actions.display_actions import repaint_display_install_box

    repaint_display_install_box(page, container)


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
        env_lines = [
            line.strip() for line in (fields["env"].value or "").splitlines() if line.strip()
        ]
        bad_env = [line for line in env_lines if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", line)]
        if bad_env:
            methods.show_snack(f"env lines must look like VAR=VALUE: {bad_env[0]}")
            return None
        if env_lines:
            opts["env"] = env_lines
        bind_lines = [
            line.strip() for line in (fields["bind"].value or "").splitlines() if line.strip()
        ]
        if any(not line for line in bind_lines):
            methods.show_snack("bind lines cannot be empty")
            return None
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
            import asyncio

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
    adv_shared_tmp = ft.Switch(label="Shared tmp", label_position=ft.LabelPosition.LEFT, scale=0.9)
    adv_shared_home = ft.Switch(
        label="Shared home", label_position=ft.LabelPosition.LEFT, scale=0.9
    )
    adv_isolated = ft.Switch(label="Isolated", label_position=ft.LabelPosition.LEFT, scale=0.9)
    adv_fix_ports = ft.Switch(
        label="Fix low ports", label_position=ft.LabelPosition.LEFT, scale=0.9
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
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)),
    )

    display_dd = ft.Dropdown(
        label="Display",
        value=str(display_no["value"]),
        options=[
            ft.dropdown.Option(str(n), f":{n}") for n in range(desk_manager.MAX_DISPLAY_NUMBER + 1)
        ],
        on_select=lambda e: display_no.__setitem__("value", int(e.control.value or 0)),
        width=140,
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


def _show_app_sheet(page: ft.Page, methods, container: str) -> None:
    """Second-level sheet: probed guest apps + a custom command — each starts a
    SINGLE-APP display (bare Xvfb, no desktop) on the next free display number."""
    results = ft.Column(
        controls=[ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD)],
        spacing=tokens.SPACE_XS,
    )
    custom = ft.TextField(
        hint_text="custom command (e.g. python3 app.py)",
        height=tokens.CONTROL_SM,
        text_size=tokens.FONT_XS,
        expand=True,
    )

    def _start_app(cmd: str) -> None:
        if not cmd.strip():
            return
        page.pop_dialog()
        page.run_task(methods.start_display, container, None, cmd.strip(), None)

    async def _probe_one(label: str, cmd: str) -> tuple[str, str] | None:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    session_service.command_capture,
                    container,
                    ["/bin/sh", "-c", f"command -v {cmd}"],
                    # timeout=, NOT a positional: the 3rd arg is work_dir
                    timeout=10.0,
                ),
                timeout=12.0,
            )
        except Exception as exc:
            logger.debug("app probe for %s failed: %s", cmd, exc)
            return None
        if result.get("ok") and result.get("output", "").strip():
            return (label, cmd)
        return None

    async def _probe() -> None:
        # Probes run in PARALLEL — one slow probe must not serialize the sheet.
        probed = await asyncio.gather(*(_probe_one(label, cmd) for label, cmd in _APP_PRESETS))
        found = [item for item in probed if item is not None]
        # Named variable, never a literal list assignment.
        rows = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                title=ft.Text(label, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                subtitle=ft.Text(
                    f"{cmd} — on its own display", size=tokens.FONT_XS, color=theme.text_dim()
                ),
                on_click=lambda _e, c=cmd: _start_app(c),
            )
            for label, cmd in found
        ]
        results.controls = rows or [
            ft.Text(
                "no preset apps found in this container — use the custom command",
                size=tokens.FONT_SM,
            )
        ]
        try:
            dlg.update()
        except Exception:
            pass

    dlg = ft.AlertDialog(
        title=ft.Text(f"Open an app — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[
                ft.Text(
                    "Each app gets its own X display (:N) and streams like a desktop:",
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                ),
                results,
                ft.Row(
                    controls=[
                        custom,
                        ft.FilledButton(
                            "Start", on_click=lambda _e: _start_app(custom.value or "")
                        ),
                    ]
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            width=_sheet_width(page),
            height=_dialog_height(page),
        ),
        actions=[
            ft.TextButton(
                "Back",
                on_click=lambda _e: (
                    page.pop_dialog(),
                    show_display_sheet(
                        page, methods, container, (state.display_support or {}).get(container) or {}
                    ),
                ),
            ),
        ],
    )
    page.show_dialog(dlg)
    page.run_task(_probe)
