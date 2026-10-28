"""Light/dark palettes and mode resolution."""

from __future__ import annotations

import flet as ft

from core.tokens import OPACITY_CONTAINER


class AppColors:
    WHITE = ft.Colors.WHITE
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

    # Glass surfaces (the house card treatment): each must be visually
    # distinct from the surface behind it or cards lose their elevation.
    LIGHT_GLASS_BG = "#FFFFFF"
    LIGHT_GLASS_BORDER = "#E4E4EA"
    DARK_GLASS_BG = "#26263A"
    DARK_GLASS_BORDER = "#3E415C"

    ACCENT = "#89B4FA"
    WARN = "#F38BA8"
    OK = "#A6E3A1"
    TERMINAL_BG = "#0D0D0D"
    TRANSPARENT = ft.Colors.TRANSPARENT

    # Light-mode status colors — the dark pastels fail 3:1 on white
    # (measured 1.49/2.32 in the design-system audit); these are the ≥3:1
    # equivalents for the light palette.
    LIGHT_OK = "#1B7F3B"
    LIGHT_WARN = "#B3261E"
    LIGHT_ACCENT = "#1E66F5"


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


def ok() -> str:
    """Status green with ≥3:1 contrast in the active palette."""
    return AppColors.LIGHT_OK if is_light_theme() else AppColors.OK


def warn() -> str:
    """Status red/warn with ≥3:1 contrast in the active palette."""
    return AppColors.LIGHT_WARN if is_light_theme() else AppColors.WARN


def accent() -> str:
    """Accent with ≥3:1 contrast in the active palette."""
    return AppColors.LIGHT_ACCENT if is_light_theme() else AppColors.ACCENT


FONT_FAMILY = "Outfit"
FONT_FILES = {"Outfit": "fonts/Outfit-Variable.ttf"}


def build_theme() -> tuple[ft.Theme, ft.Theme]:
    """(light_theme, dark_theme) — installed on the page at boot.

    The ColorScheme carries enough roles that Material surfaces (SnackBars,
    dialogs, the NavigationBar) never fall back to an uncontrolled inverse
    color — the black-on-black snack trap from the CollabShell audit.
    """

    def scheme(primary_c, surface_c, on_surface_c, on_surface_variant_c, warn_c) -> ft.ColorScheme:
        return ft.ColorScheme(
            primary=primary_c,
            on_primary=AppColors.WHITE,
            primary_container=ft.Colors.with_opacity(OPACITY_CONTAINER, primary_c),
            on_primary_container=primary_c,
            secondary=primary_c,
            on_secondary=AppColors.WHITE,
            surface=surface_c,
            on_surface=on_surface_c,
            surface_container=AppColors.LIGHT_SURFACE_ALT
            if surface_c == AppColors.LIGHT_SURFACE
            else AppColors.DARK_SURFACE_ALT,
            on_surface_variant=on_surface_variant_c,
            error=warn_c,
            on_error=AppColors.WHITE,
            outline=on_surface_variant_c,
        )

    light = ft.Theme(
        color_scheme=scheme(
            AppColors.LIGHT_PRIMARY,
            AppColors.LIGHT_SURFACE,
            AppColors.LIGHT_TEXT,
            AppColors.LIGHT_TEXT_DIM,
            AppColors.LIGHT_WARN,
        ),
        font_family=FONT_FAMILY,
    )
    dark = ft.Theme(
        color_scheme=scheme(
            AppColors.DARK_PRIMARY,
            AppColors.DARK_SURFACE,
            AppColors.DARK_TEXT,
            AppColors.DARK_TEXT_DIM,
            AppColors.WARN,
        ),
        font_family=FONT_FAMILY,
    )
    return light, dark


def glass_bg() -> str:
    return AppColors.LIGHT_GLASS_BG if is_light_theme() else AppColors.DARK_GLASS_BG


def glass_border() -> str:
    return AppColors.LIGHT_GLASS_BORDER if is_light_theme() else AppColors.DARK_GLASS_BORDER


WHITE = AppColors.WHITE
TRANSPARENT = AppColors.TRANSPARENT


def apply_theme_mode(page: ft.Page, mode: str) -> None:
    """Write one theme mode to the page (the single mapping site)."""
    mapping = {
        "light": ft.ThemeMode.LIGHT,
        "dark": ft.ThemeMode.DARK,
        "system": ft.ThemeMode.SYSTEM,
    }
    page.theme_mode = mapping.get(mode, ft.ThemeMode.SYSTEM)


def follow_platform_brightness(page: ft.Page) -> bool:
    """Re-resolve "system" mode after a platform brightness change.

    Returns True when the mode is system and the palette was re-synced.
    """
    from core.state import state as _state

    if _state.theme_mode != "system":
        return False
    _state.theme_revision += 1  # subscribed views re-render with the new palette
    apply_theme_mode(page, "light" if is_light_theme(page) else "dark")
    return True
