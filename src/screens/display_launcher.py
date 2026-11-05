"""Display launcher sheets — the button-driven entry to a container's display.

Opened imperatively via page.show_dialog. The sheet body is a reactive
component reading the observable state, so the capability probe, the DE pill
selection, the install log, and the settings all update live while open.

Two entry points:
- `show_display_sheet` — per container: running → resume is in the tab list;
  ready → Start display / Open an app on a new display… / settings; not ready
  → DE pills + exact install script + live install log + Install.
- `show_new_display_sheet` — the "+" on the Display tab: pick container, then
  mode (Desktop with DE picker, or Single app with a command) → a new
  `container:N` session.
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


@ft.component
def _DisplaySheetBody(page: ft.Page, methods, container: str) -> ft.Control:
    """The reactive body of the per-container display sheet (reads state)."""
    st, _ = ft.use_state(state)
    caps = (st.display_support or {}).get(container) or {}
    sel, set_sel = ft.use_state({DEFAULT_DESKTOP: True})

    def _current() -> str:
        return next((key for key, on in sel.items() if on), DEFAULT_DESKTOP)

    def _pick(key: str) -> None:
        set_sel({k: k == key for k in (de.key for de in DESKTOP_ENVIRONMENTS)})

    ready = bool(caps.get("desk_ready") and caps.get("x_server"))
    pm = package_manager_for(caps) if caps else None

    content_controls: list[ft.Control] = [_status_line(ready, caps)]

    if ready:
        content_controls.append(
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

        content_controls.append(
            ft.OutlinedButton(
                "Open an app on a new display…",
                icon=ft.Icons.WINDOW_ROUNDED,
                on_click=_open_apps,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=_pill_style(),
            )
        )
        content_controls.append(
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

        # ── Display settings — the full upstream param surface (fps/quality),
        # the Xvfb screen size, the fullscreen orientation, and the two ways
        # other devices can reach this display (LAN binding / localhost.run
        # tunnel). Presets plus Custom… free fields; everything lands in
        # state.display_settings for the next start.
        content_controls.append(
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
        content_controls.append(
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
        content_controls.append(
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
            )
        )
        content_controls.append(
            ft.Text(
                "LAN binds the server to the phone's Wi-Fi address; the tunnel "
                "publishes a public *.lhr.life URL. Both are protected by the "
                "access code — share it only with your own devices.",
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
        )
    else:
        content_controls.append(
            ft.Text(
                "The desktop is not installed in this container. Installing pulls an X "
                "server, the desktop, and the clipboard tools (a few hundred MB) from "
                "the container's package manager. The display server itself is "
                "already bundled in this app.",
                size=tokens.FONT_SM,
                color=theme.text(),
            )
        )
        content_controls.append(
            ft.Text("Desktop environment", size=tokens.FONT_XS, color=theme.text_dim())
        )
        content_controls.append(
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
                                if sel.get(de.key)
                                else ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.text_dim()),
                            ),
                        ),
                    )
                    for de in DESKTOP_ENVIRONMENTS
                ],
                spacing=tokens.SPACE_XS,
                wrap=True,
            )
        )
        if pm:
            content_controls.append(
                ft.Container(
                    content=ft.Text(
                        install_script(caps, _current()),
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

        content_controls.append(
            ft.FilledButton(
                "Install desktop",
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                on_click=_install,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=_pill_style(),
            )
        )
        if state.display_installing == container:
            content_controls.append(
                ft.Container(
                    content=ft.Text(
                        "".join(state.display_install_logs or [])[-2000:],
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
            )

    return ft.Column(
        controls=content_controls,
        tight=True,
        spacing=tokens.SPACE_SM,
        scroll=ft.ScrollMode.AUTO,
        width=tokens.DIALOG_WIDTH,
    )


def show_display_sheet(page: ft.Page, methods, container: str, caps: dict) -> None:
    """Open the launcher sheet for a container. `caps` is only the initial
    probe snapshot — the body re-reads state.display_support live."""
    dlg = ft.AlertDialog(
        title=ft.Text(f"Display — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=_DisplaySheetBody(page, methods, container),
        actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
    )
    page.show_dialog(dlg)


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


@ft.component
def _NewDisplaySheetBody(page: ft.Page, methods, container: str) -> ft.Control:
    """Mode picker body: Desktop (with DE dropdown) or Single app (command)."""
    mode, set_mode = ft.use_state("desktop")
    sel, set_sel = ft.use_state({DEFAULT_DESKTOP: True})
    cmd_value, set_cmd_value = ft.use_state("")

    def _current() -> str:
        return next((key for key, on in sel.items() if on), DEFAULT_DESKTOP)

    def _start(_e) -> None:
        if mode == "app" and not cmd_value.strip():
            methods.show_snack("enter a command for the single-app display")
            return
        page.pop_dialog()
        if mode == "app":
            page.run_task(methods.start_display, container, None, cmd_value.strip(), None)
        else:
            page.run_task(methods.start_display, container, _current(), None, None)

    return ft.Column(
        controls=[
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
                        on_click=lambda _e: set_mode("desktop"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1, theme.primary() if mode == "desktop" else theme.surface_alt()
                            ),
                        ),
                    ),
                    ft.OutlinedButton(
                        "Single app",
                        icon=ft.Icons.WINDOW_ROUNDED,
                        on_click=lambda _e: set_mode("app"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            side=ft.BorderSide(
                                1, theme.primary() if mode == "app" else theme.surface_alt()
                            ),
                        ),
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Dropdown(
                label="Desktop environment",
                value=_current(),
                visible=mode == "desktop",
                options=[ft.dropdown.Option(de.key, de.name) for de in DESKTOP_ENVIRONMENTS],
                on_change=lambda e: set_sel(
                    {k: k == e.control.value for k in (d.key for d in DESKTOP_ENVIRONMENTS)}
                ),
                width=tokens.DROPDOWN_WIDTH,
                border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                text_size=tokens.FONT_XS,
            ),
            ft.TextField(
                label="Command to run on its own display",
                hint_text="e.g. firefox   |   python3 -m http.server 8080   |   pywebview app",
                value=cmd_value,
                on_change=lambda e: set_cmd_value(e.control.value or ""),
                visible=mode == "app",
                text_size=tokens.FONT_SM,
                height=tokens.CONTROL_INPUT,
                border=ft.OutlineInputBorder(
                    border_radius=tokens.RADIUS_MD,
                    side=ft.BorderSide(1, theme.surface_alt()),
                ),
            ),
            ft.FilledButton(
                "Start",
                icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
                on_click=_start,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=_pill_style(),
            ),
        ],
        tight=True,
        spacing=tokens.SPACE_SM,
        width=tokens.DIALOG_WIDTH,
    )


def _show_new_display_mode_sheet(page: ft.Page, methods, container: str) -> None:
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"New display — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
            ),
            content=_NewDisplaySheetBody(page, methods, container),
            actions=[ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog())],
        )
    )


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
        # Event-handler context (post-render, followed by dlg.update()) — assign
        # a named variable, never a literal list.
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
