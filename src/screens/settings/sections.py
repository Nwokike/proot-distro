"""Settings sections that are large enough to live on their own."""

from __future__ import annotations

import flet as ft

from components.brand_hero import app_icon_svg
from core import theme, tokens
from core.constants import APP_BUILD_NUMBER, APP_NAME, APP_VERSION
from screens.settings_components import _setting_row, _settings_card


def build_about_card(
    *,
    is_narrow: bool,
    on_help,
    on_changelog,
    on_licenses,
    on_privacy,
    on_update,
    on_intro,
    on_exit,
) -> ft.Control:
    """About: brand, help, release notes, licenses, policy, updates, intro, exit."""
    return _settings_card(
        [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Container(
                            content=ft.Image(
                                src=app_icon_svg(),
                                width=tokens.HERO_ICON_SIZE,
                                height=tokens.HERO_ICON_SIZE,
                                fit=ft.BoxFit.CONTAIN,
                                color=None if theme.is_light_theme() else theme.WHITE,
                                color_blend_mode=ft.BlendMode.SRC_IN,
                            ),
                            alignment=ft.Alignment.CENTER,
                            margin=ft.Margin(0, tokens.SPACE_SM, 0, tokens.SPACE_XS),
                        ),
                        ft.Text(
                            "Linux on Android — no root",
                            size=tokens.FONT_SM,
                            color=theme.text_dim(),
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_XXS,
                ),
                padding=tokens.SPACE_MD,
                alignment=ft.Alignment.CENTER,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.HELP_OUTLINE_ROUNDED,
                "Help & Shortcuts",
                "Getting started, terminal keys, display gestures, diagnostics",
                ft.TextButton("Open Help", on_click=on_help),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.INFO_OUTLINE_ROUNDED,
                f"{APP_NAME} v{APP_VERSION} ({APP_BUILD_NUMBER})",
                "Release notes and change details",
                ft.TextButton("Changelog", on_click=on_changelog),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.GAVEL_ROUNDED,
                "Open-Source Licenses",
                "Complete license texts for PRoot, talloc, and Python dependencies",
                ft.TextButton("View Licenses", on_click=on_licenses),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.POLICY_ROUNDED,
                "Privacy Policy",
                "Container data stays on this device; see the full policy",
                ft.OutlinedButton("View Policy", on_click=on_privacy, height=tokens.CONTROL_MD),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.SYSTEM_UPDATE_ROUNDED,
                "Check for updates",
                "Ask the release feed now (the startup check is throttled)",
                ft.TextButton("Check", on_click=on_update),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.REPLAY_ROUNDED,
                "Show the intro again",
                "Replay the three onboarding screens",
                ft.TextButton("Replay", on_click=on_intro),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.POWER_SETTINGS_NEW_ROUNDED,
                "Exit App",
                "Kill all running sessions and close the app",
                ft.TextButton("Exit", on_click=on_exit, style=ft.ButtonStyle(color=theme.danger())),
                stacked=is_narrow,
            ),
        ]
    )
