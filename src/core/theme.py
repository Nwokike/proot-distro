"""Theme — light/dark palettes and mode resolution (CollabShell pattern).

`is_light_theme()` mirrors the client's SYSTEM resolution via
`page.platform_brightness` and subscribes to the state so components re-render
when the mode flips. Callers read the adaptive helpers inside render.
"""

from __future__ import annotations

import flet as ft


class AppColors:
    # Terminal-native brand: Catppuccin-derived dark, clean light.
    LIGHT_BG = "#F4F4F8"
    LIGHT_SURFACE = "#FFFFFF"
    LIGHT_SURFACE_ALT = "#EDEDF2"
    LIGHT_TEXT = "#1E1E2E"
    LIGHT_TEXT_DIM = "#5C5C6E"
    LIGHT_PRIMARY = "#1E66F5"

    DARK_BG = "#121218"
    DARK_SURFACE = "#1E1E2E"
    DARK_SURFACE_ALT = "#313244"
    DARK_TEXT = "#CDD6F4"
    DARK_TEXT_DIM = "#A6ADC8"
    DARK_PRIMARY = "#89B4FA"

    ACCENT = "#89B4FA"
    WARN = "#F38BA8"
    OK = "#A6E3A1"
    TERMINAL_BG = "#0D0D0D"


def _page() -> ft.Page | None:
    try:
        return ft.context.page
    except RuntimeError:
        return None


def is_light_theme(page: ft.Page | None = None) -> bool:
    """Effective light/dark; SYSTEM follows the platform brightness.

    Reads `state.theme_mode`/`theme_revision` so callers subscribe and
    re-render on theme switch.
    """
    from core.state import state as _state

    requested = _state.theme_mode
    _ = _state.theme_revision  # read for subscription; underscore is exempt

    if requested == "light":
        return True
    if requested == "dark":
        return False

    p = page or _page()
    if p is None:
        return False  # terminal-native default
    tm = getattr(p, "theme_mode", None)
    if tm == ft.ThemeMode.LIGHT:
        return True
    if tm == ft.ThemeMode.DARK:
        return False
    brightness = getattr(p, "platform_brightness", None)
    return brightness == ft.Brightness.LIGHT


def bg() -> str:
    return AppColors.LIGHT_BG if is_light_theme() else AppColors.DARK_BG


def surface() -> str:
    return AppColors.LIGHT_SURFACE if is_light_theme() else AppColors.DARK_SURFACE


def surface_alt() -> str:
    return AppColors.LIGHT_SURFACE_ALT if is_light_theme() else AppColors.DARK_SURFACE_ALT


def text() -> str:
    return AppColors.LIGHT_TEXT if is_light_theme() else AppColors.DARK_TEXT


def text_dim() -> str:
    return AppColors.LIGHT_TEXT_DIM if is_light_theme() else AppColors.DARK_TEXT_DIM


def primary() -> str:
    return AppColors.LIGHT_PRIMARY if is_light_theme() else AppColors.DARK_PRIMARY


def build_theme() -> tuple[ft.Theme, ft.Theme]:
    """(light_theme, dark_theme) — installed on the page at boot."""

    def scheme(primary_c, surface_c, on_surface_c, on_surface_variant_c) -> ft.ColorScheme:
        return ft.ColorScheme(
            primary=primary_c,
            surface=surface_c,
            on_surface=on_surface_c,
            on_surface_variant=on_surface_variant_c,
            error=AppColors.WARN,
            outline=on_surface_variant_c,
        )

    light = ft.Theme(
        color_scheme=scheme(
            AppColors.LIGHT_PRIMARY,
            AppColors.LIGHT_SURFACE,
            AppColors.LIGHT_TEXT,
            AppColors.LIGHT_TEXT_DIM,
        )
    )
    dark = ft.Theme(
        color_scheme=scheme(
            AppColors.DARK_PRIMARY,
            AppColors.DARK_SURFACE,
            AppColors.DARK_TEXT,
            AppColors.DARK_TEXT_DIM,
        )
    )
    return light, dark
