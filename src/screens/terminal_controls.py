"""Shared terminal input, theme, and close-dialog controls."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from services.session_manager import SessionEntry

_THEME_PRESETS = ("JetBrains Dark", "Dracula", "Matrix Green", "Colab Light")


def _theme_name() -> str:
    return "Colab Light" if theme.is_light_theme() else "JetBrains Dark"


def _write(entry: SessionEntry, payload: bytes) -> None:
    if entry.session is not None:
        entry.session.write(payload)


def _compact_btn_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        padding=ft.Padding(tokens.SPACE_XS, tokens.SPACE_XS, tokens.SPACE_XS, tokens.SPACE_XS),
        visual_density=ft.VisualDensity.COMPACT,
    )


def _cycle_terminal_theme(mt) -> None:
    cur = mt.theme_name or _theme_name()
    idx = _THEME_PRESETS.index(cur) if cur in _THEME_PRESETS else 0
    next_theme = _THEME_PRESETS[(idx + 1) % len(_THEME_PRESETS)]
    mt.set_theme(next_theme)


def _confirm_close(page: ft.Page, methods, container: str) -> None:
    def _yes(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.close_session, container)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Close {container}?",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Text(
                "The shell is terminated; unsaved work inside it is lost.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Close",
                    on_click=_yes,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )
