"""Settings dialogs for the Display and Terminal defaults."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.shared_services import launch_url  # noqa: F401
from core.state import state


def open_display_defaults(page: ft.Page, methods=None) -> None:
    """Settings -> Display defaults: the same real option set the launch sheet
    mounts, reachable without starting (or owning) a display."""
    from screens.display_sheets.advanced import _advanced_display_controls
    from screens.display_sheets.common import _picker_with_custom

    body = ft.Column(
        controls=[
            _advanced_display_controls(),
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Quality",
                        (("70", "70"), ("85", "85"), ("95", "95")),
                        "quality",
                        hint="1-95 (viewer image quality)",
                    ),
                    _picker_with_custom(
                        "Compression",
                        (("0", "0 (fastest)"), ("2", "2 (default)"), ("9", "9 (smallest)")),
                        "compression",
                        hint="0-9 (Tight/ZRLE level)",
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
            ft.Row(
                controls=[
                    _picker_with_custom(
                        "Resolution",
                        (
                            ("auto", "Fit this phone"),
                            ("1280x720", "1280x720"),
                            ("1600x900", "1600x900"),
                            ("1920x1080", "1920x1080"),
                        ),
                        "geometry",
                        hint="WxH, e.g. 1440x900",
                    ),
                    ft.Dropdown(
                        label="Orientation",
                        value=str(state.display_settings.get("orientation", "landscape")),
                        options=[
                            ft.dropdown.Option("landscape", "Landscape"),
                            ft.dropdown.Option("portrait", "Portrait"),
                        ],
                        on_select=lambda e: _set_display("orientation", e.control.value),
                        width=tokens.DROPDOWN_WIDTH,
                        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
                        text_size=tokens.FONT_XS,
                    ),
                ],
                spacing=tokens.SPACE_SM,
                wrap=True,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        width=tokens.DIALOG_WIDTH,
        height=tokens.FILE_LIST_HEIGHT,
    )

    def _set_display(key: str, value: object) -> None:
        state.display_settings[key] = value

    def _save(_e) -> None:
        page.pop_dialog()
        if methods is not None:
            page.run_task(methods.save_display_settings)
        from components.snack import show_snack

        show_snack(page, "display defaults saved")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Display defaults", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=body,
            actions=[
                ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Save",
                    on_click=_save,
                    style=ft.ButtonStyle(color=theme.WHITE, bgcolor=theme.primary()),
                ),
            ],
        )
    )


def open_terminal_defaults(page: ft.Page, methods=None) -> None:
    """Settings -> Terminal defaults: theme, font size and cursor blink for the
    NEXT shells (each widget is created per shell)."""
    from core.state import DEFAULT_TERMINAL_SETTINGS
    from screens.terminal_controls import _THEME_PRESETS

    current = {**DEFAULT_TERMINAL_SETTINGS, **(state.terminal_settings or {})}
    theme_dropdown = ft.Dropdown(
        label="Theme",
        value=str(current.get("theme") or _THEME_PRESETS[0]),
        options=[ft.dropdown.Option(name) for name in _THEME_PRESETS],
        width=tokens.DROPDOWN_WIDTH,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        text_size=tokens.FONT_XS,
    )
    size_field = ft.TextField(
        label="Font size",
        hint_text="empty = widget default",
        value=str(current.get("font_size") or ""),
        width=tokens.DROPDOWN_WIDTH,
        text_size=tokens.FONT_XS,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
    )
    blink = ft.Switch(label="Cursor blink", value=bool(current.get("cursor_blink", True)))

    def _save(_e) -> None:
        try:
            size = float((size_field.value or "").strip() or 0)
        except ValueError:
            size = 0.0
        state.terminal_settings = {
            **current,
            "theme": theme_dropdown.value,
            "font_size": max(0.0, min(32.0, size)),
            "cursor_blink": bool(blink.value),
        }
        page.pop_dialog()
        if methods is not None:
            page.run_task(methods.save_terminal_settings)
        from components.snack import show_snack

        show_snack(page, "terminal defaults saved — new shells use them")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Terminal defaults", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[theme_dropdown, size_field, blink],
                spacing=tokens.SPACE_SM,
                tight=True,
                width=tokens.DIALOG_WIDTH,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Save",
                    on_click=_save,
                    style=ft.ButtonStyle(color=theme.WHITE, bgcolor=theme.primary()),
                ),
            ],
        )
    )
