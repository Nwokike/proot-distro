"""Display launcher sheet — the button-driven entry to a container's display.

Opened imperatively via page.show_dialog (the files-modal pattern). Two
states: display support installed (start display / DE picker / settings) or
not (ServalDesk-style DE cards + install, reusing the container-install
progress pattern with a live ANSI-stripped log).
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


def _status_line(ready: bool, caps: dict) -> ft.Control:
    os_name = (caps.get("os") or {}).get("pretty_name", "") or "unknown distro"
    label = "X11 display ready" if ready else "display support missing"
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


def show_display_sheet(page: ft.Page, methods, container: str, caps: dict) -> None:
    """Open the launcher sheet for a container. `caps` is the probed
    guest_capabilities dict (may be empty when probing failed)."""
    ready = bool(caps.get("desk_ready") and caps.get("x_server"))
    pm = package_manager_for(caps) if caps else None

    selected = {DEFAULT_DESKTOP: True}

    def _current() -> str:
        return next((key for key, on in selected.items() if on), DEFAULT_DESKTOP)

    content_controls: list[ft.Control] = [_status_line(ready, caps)]

    if ready:
        content_controls.append(
            ft.FilledButton(
                "Start display",
                icon=ft.Icons.DESKTOP_WINDOWS,
                on_click=lambda _e: (
                    page.pop_dialog(),
                    page.run_task(methods.start_display, container, _current()),
                ),
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)),
            )
        )

        def _open_apps(_e) -> None:
            page.pop_dialog()
            _show_app_sheet(page, methods, container)

        content_controls.append(
            ft.OutlinedButton(
                "Open an app…",
                icon=ft.Icons.WINDOW_ROUNDED,
                on_click=_open_apps,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)),
            )
        )

        content_controls.append(
            ft.Container(
                content=ft.Dropdown(
                    label="Desktop environment",
                    value=_current(),
                    options=[ft.dropdown.Option(de.key, de.name) for de in DESKTOP_ENVIRONMENTS],
                    on_change=lambda e: selected.__setitem__(e.control.value, True),
                    width=tokens.DROPDOWN_WIDTH,
                    border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                    text_size=tokens.FONT_XS,
                ),
                padding=ft.Padding(tokens.SPACE_NONE, 0, tokens.SPACE_NONE, 0),
            )
        )

        # ── Display settings — the full upstream param surface (fps/quality),
        # the Xvfb screen size, the fullscreen orientation, and the two ways
        # other devices can reach this display (LAN binding / localhost.run
        # tunnel). Everything lands in state.display_settings for the next
        # start; reassign the dict so the observable notifies.
        def _set_setting(key: str, value: object) -> None:
            state.display_settings = {**(state.display_settings or {}), key: value}

        def _picker(label: str, options: tuple[tuple[str, str], ...], key: str) -> ft.Control:
            settings = state.display_settings or {}
            return ft.Dropdown(
                label=label,
                value=str(settings.get(key, options[0][0])),
                options=[ft.dropdown.Option(v, t) for v, t in options],
                on_change=lambda e: _set_setting(key, e.control.value),
                width=tokens.DROPDOWN_WIDTH,
                border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                text_size=tokens.FONT_XS,
            )

        content_controls.append(
            ft.Row(
                controls=[
                    _picker(
                        "FPS",
                        (("8", "8 fps"), ("12", "12 fps"), ("15", "15 fps"), ("24", "24 fps")),
                        "fps",
                    ),
                    _picker(
                        "Quality",
                        (("50", "50"), ("70", "70"), ("85", "85"), ("95", "95")),
                        "quality",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            )
        )
        content_controls.append(
            ft.Row(
                controls=[
                    _picker(
                        "Resolution",
                        (
                            ("auto", "Auto (screen shape)"),
                            ("1280x720", "1280 x 720"),
                            ("1600x900", "1600 x 900"),
                            ("1920x1080", "1920 x 1080"),
                        ),
                        "geometry",
                    ),
                    _picker(
                        "Fullscreen",
                        (("landscape", "Landscape"), ("auto", "System default")),
                        "orientation",
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
                "Display support is not installed in this container. Installing pulls "
                "an X server, the desktop, and the guest python modules (a few hundred "
                "MB) from the container's package manager.",
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
                        de.name,
                        on_click=lambda _e, k=de.key: selected.__setitem__(k, True),
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
                "Install display support",
                icon=ft.Icons.DOWNLOAD_ROUNDED,
                on_click=_install,
                width=float("inf"),
                height=tokens.CONTROL_MD,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)),
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

    dlg = ft.AlertDialog(
        title=ft.Text(f"Display — {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=content_controls,
            tight=True,
            spacing=tokens.SPACE_SM,
            scroll=ft.ScrollMode.AUTO,
            width=tokens.DIALOG_WIDTH,
        ),
        actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
    )
    page.show_dialog(dlg)


def _show_app_sheet(page: ft.Page, methods, container: str) -> None:
    """Second-level sheet: probed guest apps + an advanced custom command."""
    results = ft.Column(
        controls=[ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD)],
        spacing=tokens.SPACE_XS,
    )
    custom = ft.TextField(
        hint_text="custom command (advanced)",
        height=tokens.CONTROL_SM,
        text_size=tokens.FONT_XS,
        expand=True,
    )

    def _start_app(cmd: str) -> None:
        if not cmd.strip():
            return
        page.pop_dialog()
        page.run_task(methods.start_display, container, None)

    async def _probe() -> None:
        # command_capture is blocking — run the whole probe set on a worker
        # thread so the sheet never freezes.
        found: list[tuple[str, str]] = []
        for label, cmd in _APP_PRESETS:
            try:
                result = await asyncio.to_thread(
                    session_service.command_capture,
                    container,
                    ["/bin/sh", "-c", f"command -v {cmd}"],
                    15.0,
                )
            except Exception as exc:
                logger.debug("app probe for %s failed: %s", cmd, exc)
                continue
            if result.get("ok") and result.get("output", "").strip():
                found.append((label, cmd))
        # Event-handler context (post-render, followed by dlg.update()) — the
        # files-modal pattern; assign a named variable, never a literal list.
        rows = [
            ft.ListTile(
                leading=ft.Icon(ft.Icons.APPS_ROUNDED, color=theme.primary()),
                title=ft.Text(label, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                subtitle=ft.Text(cmd, size=tokens.FONT_XS, color=theme.text_dim()),
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
                    "Installed apps found in the guest:",
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
