"""Settings sections that are large enough to live on their own."""

from __future__ import annotations

import flet as ft

from components.brand_hero import app_icon_svg
from core import layout, theme, tokens
from core.constants import (
    APP_BUILD_NUMBER,
    APP_NAME,
    APP_VERSION,
    CONTACT_EMAIL,
    GITHUB_REPO_URL,
    KIRI_APPS_PLAY_URL,
    KIRI_APPS_URL,
    PLAY_STORE_URL,
    REPO_NAME,
    REPO_OWNER,
)
from screens.settings_components import _setting_row, _settings_card


def _store_device(page: ft.Page) -> bool:
    """Phones/TV are the Play audience; desktop rates on GitHub (DDGS rule)."""
    try:
        return page.platform in (
            ft.PagePlatform.ANDROID,
            ft.PagePlatform.IOS,
            ft.PagePlatform.ANDROID_TV,
        )
    except Exception:
        return False


def _external_icon() -> ft.Control:
    """Marks a row that LEAVES the app (browser / store / mail)."""
    return ft.Icon(
        ft.Icons.OPEN_IN_NEW_ROUNDED,
        size=tokens.ICON_XS,
        color=theme.text_dim(),
    )


def _in_app_icon() -> ft.Control:
    """Marks a row that opens an in-app sheet or dialog (never a browser)."""
    return ft.Icon(
        ft.Icons.CHEVRON_RIGHT_ROUNDED,
        size=tokens.ICON_SM,
        color=theme.text_dim(),
    )


def build_about_card(
    page: ft.Page,
    *,
    on_help,
    on_changelog,
    on_licenses,
    on_privacy,
    on_terms,
    on_update,
    on_intro,
    on_exit,
    on_link,
    on_debug=None,
    probe_summary: str = "",
    update_available: bool = False,
) -> ft.Control:
    """About — the owner's shape across Kiri apps (CollabShell about_section.py,
    DDGS sections_about.py): centered brand mark, a LIVE version header that
    opens the release notes, the reused Contact / Rate / More-apps rows, the
    policy pair, and a centered disclaimer.

    Audited 2026-11-15 for what the rest of the app has and About lacked: the
    source repository and the diagnostics surface (the probe state + the log)
    are support entry points, so they live here too."""
    version_line = (
        "Update available · tap to view"
        if update_available
        else f"Version {APP_VERSION} · build {APP_BUILD_NUMBER} · Flet {ft.__version__}"
    )
    store_device = _store_device(page)
    is_narrow = layout.is_narrow(page)
    rate_url = PLAY_STORE_URL if store_device else GITHUB_REPO_URL
    rate_subtitle = "Rate us on Google Play" if store_device else "Star us on GitHub"
    apps_url = KIRI_APPS_PLAY_URL if store_device else KIRI_APPS_URL

    def _open(url: str):
        return lambda _e: on_link(url)

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
                            "Linux on Android, no root",
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
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Text(
                                    APP_NAME,
                                    size=tokens.FONT_MD,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme.text(),
                                ),
                                ft.Text(
                                    version_line,
                                    size=tokens.FONT_XS,
                                    color=theme.primary() if update_available else theme.text_dim(),
                                ),
                            ],
                            spacing=tokens.SPACE_XXS,
                            tight=True,
                            expand=True,
                        ),
                        _in_app_icon(),
                    ],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(
                    tokens.SPACE_LG, tokens.SPACE_XS, tokens.SPACE_LG, tokens.SPACE_SM
                ),
                ink=True,
                on_click=on_update if update_available else on_changelog,
                tooltip="Release notes",
            ),
            _setting_row(
                ft.Icons.MAIL_OUTLINE_ROUNDED,
                "Contact developer",
                CONTACT_EMAIL,
                _external_icon(),
                on_tap=_open(f"mailto:{CONTACT_EMAIL}"),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.STAR_ROUNDED,
                "Rate 5 stars",
                rate_subtitle,
                _external_icon(),
                on_tap=_open(rate_url),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.APPS_ROUNDED,
                "More apps from Kiri",
                "Sherlock, DDGS, CollabShell and more",
                _external_icon(),
                on_tap=_open(apps_url),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.HELP_OUTLINE_ROUNDED,
                "Help & shortcuts",
                "Getting started, terminal keys, display gestures, diagnostics",
                on_tap=on_help,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.GAVEL_ROUNDED,
                "Open-source licenses",
                "PRoot, talloc and every Python dependency",
                on_tap=on_licenses,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CODE_ROUNDED,
                "Source code",
                f"github.com/{REPO_OWNER}/{REPO_NAME} (builds, issues, releases)",
                _external_icon(),
                on_tap=_open(GITHUB_REPO_URL),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
        ]
        + (
            [
                _setting_row(
                    ft.Icons.BUG_REPORT_ROUNDED,
                    "Diagnostics",
                    probe_summary or "Environment probe and the live app log",
                    _in_app_icon(),
                    on_tap=on_debug,
                    stacked=is_narrow,
                ),
                ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            ]
            if on_debug is not None
            else []
        )
        + [
            _setting_row(
                ft.Icons.REPLAY_ROUNDED,
                "Show the intro again",
                "Replay the onboarding screens",
                on_tap=on_intro,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.POWER_SETTINGS_NEW_ROUNDED,
                "Exit app",
                "Stops every shell and display, then closes",
                ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=tokens.ICON_SM, color=theme.danger()),
                on_tap=on_exit,
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            ft.Row(
                controls=[
                    ft.TextButton(
                        "Privacy Policy",
                        icon=ft.Icons.PRIVACY_TIP_ROUNDED,
                        style=ft.ButtonStyle(color=theme.primary()),
                        on_click=on_privacy,
                    ),
                    ft.TextButton(
                        "Terms of Service",
                        icon=ft.Icons.GAVEL_ROUNDED,
                        style=ft.ButtonStyle(color=theme.primary()),
                        on_click=on_terms,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            ),
            ft.Container(
                content=ft.Text(
                    "Unofficial client. Linux is a trademark of Linus Torvalds; "
                    "every distribution belongs to its own project.",
                    size=tokens.FONT_XXS,
                    color=theme.text_dim(),
                    italic=True,
                    text_align=ft.TextAlign.CENTER,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_SM),
            ),
        ]
    )
