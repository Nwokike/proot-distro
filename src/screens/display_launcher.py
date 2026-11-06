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

import flet as ft

from core import theme, tokens
from core.state import state
from services import session_service
from services.desk_service import DEFAULT_DESKTOP, DESKTOP_ENVIRONMENTS
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


def _status_line(ready: bool, caps: dict) -> ft.Control:
    os_name = (caps.get("os") or {}).get("pretty_name", "") or "unknown distro"
    label = "X11 desktop ready" if ready else "desktop not installed"
    return ft.Row(
        controls=[
            ft.Container(
                width=tokens.STATUS_DOT_SM,
                height=tokens.STATUS_DOT_SM,
                border_radius=50,
                bgcolor=theme.ok() if ready else theme.warn(),
            ),
            ft.Text(f"{label} · {os_name}", size=tokens.FONT_SM, color=theme.text_dim()),
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
        on_change=lambda e: _set_setting(
            key, e.control.value if e.control.value != _CUSTOM else custom_field.value or current
        ),
        width=tokens.DROPDOWN_WIDTH,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        text_size=tokens.FONT_XS,
    )
    return ft.Column(controls=[dropdown, custom_field], spacing=tokens.SPACE_XXS, tight=True)


def show_display_sheet(page: ft.Page, methods, container: str, caps: dict) -> None:
    """Open the launcher sheet for a container. Plain controls; repaint in
    place when the DE pick or the install log changes."""
    selected = {DEFAULT_DESKTOP: True}

    def _current() -> str:
        return next((key for key, on in selected.items() if on), DEFAULT_DESKTOP)

    body: ft.Column = ft.Column(spacing=tokens.SPACE_SM, tight=True, width=tokens.DIALOG_WIDTH)
    dlg: ft.AlertDialog

    def _rebuild() -> None:
        # Repaint in place: build rows into a NAME, then assign (the files-modal
        # pattern) — never a literal list at the assignment site.
        ready = bool((state.display_support or {}).get(container, {}).get("desk_ready")) and bool(
            (state.display_support or {}).get(container, {}).get("x_server")
        )
        pm = package_manager_for((state.display_support or {}).get(container) or {})
        rows = [_status_line(ready, (state.display_support or {}).get(container) or {})]
        if ready:
            rows.append(
                ft.FilledButton(
                    "Start display",
                    icon=ft.Icons.DESKTOP_WINDOWS,
                    on_click=lambda _e: (
                        page.pop_dialog(),
                        page.run_task(methods.start_display, container, _current(), None, None),
                    ),
                    width=float("inf"),
                    height=tokens.CONTROL_MD,
                    style=_pill_style(),
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
            rows.append(
                ft.Dropdown(
                    label="Desktop environment",
                    value=next(
                        (de.key for de in DESKTOP_ENVIRONMENTS if de.key == _current()),
                        DEFAULT_DESKTOP,
                    ),
                    options=[ft.dropdown.Option(de.key, de.name) for de in DESKTOP_ENVIRONMENTS],
                    on_change=lambda e: _pick(e.control.value),
                    width=tokens.DROPDOWN_WIDTH,
                    border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                    text_size=tokens.FONT_XS,
                )
            )
            rows.append(
                ft.Row(
                    controls=[
                        _picker_with_custom(
                            "FPS",
                            (("8", "8 fps"), ("12", "12 fps"), ("15", "15 fps"), ("24", "24 fps")),
                            "fps",
                            hint="any number > 0, e.g. 30",
                        ),
                        _picker_with_custom(
                            "Quality",
                            (("50", "50"), ("70", "70"), ("85", "85"), ("95", "95")),
                            "quality",
                            hint="1-95 (upstream JPEG bound)",
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
                        _picker_with_custom(
                            "Fullscreen",
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
        else:
            rows.append(
                ft.Text(
                    "The desktop is not installed in this container. Installing pulls an X "
                    "server, the desktop, and the clipboard tools (a few hundred MB) from "
                    "the container's package manager. The display server itself is "
                    "already bundled in this app.",
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
            if pm:
                rows.append(
                    ft.Container(
                        content=ft.Text(
                            install_script(
                                (state.display_support or {}).get(container) or {}, _current()
                            ),
                            font_family=tokens.MONO_FONT,
                            size=tokens.FONT_XXS,
                            color=theme.text_dim(),
                            selectable=True,
                        ),
                        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
                        border=ft.Border.all(tokens.HAIRLINE, theme.surface_alt()),
                        border_radius=tokens.RADIUS_SM,
                        padding=tokens.SPACE_SM,
                    )
                )

            def _install(_e) -> None:
                page.run_task(methods.install_display_support, container, _current())

            rows.append(
                ft.FilledButton(
                    "Install desktop",
                    icon=ft.Icons.DOWNLOAD_ROUNDED,
                    on_click=_install,
                    width=float("inf"),
                    height=tokens.CONTROL_MD,
                    style=_pill_style(),
                )
            )
            rows.append(_install_log_box(page, container))

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
            width=tokens.DIALOG_WIDTH,
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
    """The Display tab's "+": pick a container, then Desktop or Single app —
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
    """Mode picker: Desktop (with DE dropdown) or Single app (command field)."""
    mode = {"value": "desktop"}
    selected = {DEFAULT_DESKTOP: True}
    command = {"value": ""}
    body: ft.Column = ft.Column(spacing=tokens.SPACE_SM, tight=True, width=tokens.DIALOG_WIDTH)
    dlg: ft.AlertDialog

    def _current() -> str:
        return next((key for key, on in selected.items() if on), DEFAULT_DESKTOP)

    def _pick(key: str) -> None:
        selected.clear()
        selected[key] = True
        _rebuild()

    def _start(_e) -> None:
        if mode["value"] == "app" and not command["value"].strip():
            methods.show_snack("enter a command for the single-app display")
            return
        page.pop_dialog()
        if mode["value"] == "app":
            page.run_task(methods.start_display, container, None, command["value"].strip(), None)
        else:
            page.run_task(methods.start_display, container, _current(), None, None)

    def _rebuild() -> None:
        is_app = mode["value"] == "app"
        controls = [
            ft.Text(
                "A new X display (:N) on this container — a full desktop, or one app alone.",
                size=tokens.FONT_SM,
                color=theme.text_dim(),
            ),
            ft.Row(
                controls=[
                    ft.OutlinedButton(
                        "Desktop",
                        icon=ft.Icons.DESKTOP_WINDOWS,
                        on_click=lambda _e: _set_mode("desktop"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1,
                                theme.primary() if not is_app else theme.surface_alt(),
                            ),
                        ),
                    ),
                    ft.OutlinedButton(
                        "Single app",
                        icon=ft.Icons.WINDOW_ROUNDED,
                        on_click=lambda _e: _set_mode("app"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1, theme.primary() if is_app else theme.surface_alt()
                            ),
                        ),
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
        ]
        if is_app:
            controls.append(
                ft.TextField(
                    label="Command to run on its own display",
                    hint_text="e.g. firefox   |   python3 -m http.server 8080   |   pywebview app",
                    value=command["value"],
                    on_change=lambda e: command.__setitem__("value", e.control.value or ""),
                    text_size=tokens.FONT_SM,
                    height=tokens.CONTROL_INPUT,
                    border=ft.OutlineInputBorder(
                        border_radius=tokens.RADIUS_MD,
                        side=ft.BorderSide(1, theme.surface_alt()),
                    ),
                )
            )
        else:
            controls.append(
                ft.Dropdown(
                    label="Desktop environment",
                    value=_current(),
                    options=[ft.dropdown.Option(de.key, de.name) for de in DESKTOP_ENVIRONMENTS],
                    on_change=lambda e: _pick(e.control.value),
                    width=tokens.DROPDOWN_WIDTH,
                    border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                    text_size=tokens.FONT_XS,
                )
            )
        controls.append(
            ft.FilledButton(
                "Start",
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
        content=body,
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
                    10.0,
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
            tight=True,
            spacing=tokens.SPACE_SM,
            width=tokens.DIALOG_WIDTH,
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
