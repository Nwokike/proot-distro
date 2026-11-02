from __future__ import annotations

import flet as ft

from components import section_header
from components.banner_ad import pooled_banner_ad
from core import theme, tokens
from core.constants import (
    APP_BUILD_NUMBER,
    APP_NAME,
    APP_VERSION,
    PRIVACY_POLICY_URL,
)
from core.shared_services import launch_url
from core.state import state
from screens.formatting import format_size as _fmt_size
from screens.settings_components import _setting_row, _settings_card
from state.controller_ctx import ControllerMethodsCtx

from . import dialogs


@ft.component
def SettingsView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    token, set_token = ft.use_state(st.docker_token)

    is_narrow = bool(page and getattr(page, "width", None) and page.width < 600)

    def _theme_card(mode: str, label: str, icon: ft.IconData) -> ft.Container:
        """Compact icon+label selector card — CollabShell's preferences pattern:
        one row, centered, PRIMARY tint + border when selected, 150ms animate."""
        selected = st.theme_mode == mode
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icon,
                        size=tokens.ICON_MD,
                        color=theme.primary() if selected else theme.text_dim(),
                    ),
                    ft.Text(
                        label,
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400,
                        color=theme.primary() if selected else theme.text(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=tokens.SPACE_XS,
                tight=True,
            ),
            expand=True,
            padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM),
            border_radius=tokens.RADIUS_MD,
            border=ft.Border.all(
                tokens.BORDER_WIDTH_EMPHASIS if selected else tokens.HAIRLINE,
                theme.primary() if selected else theme.glass_border(),
            ),
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TINT, theme.primary())
            if selected
            else ft.Colors.with_opacity(tokens.OPACITY_SUBTLE, theme.text()),
            animate=ft.Animation(tokens.ANIM_FAST_MS, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _e, m=mode: page.run_task(methods.set_theme_mode, m),
            ink=True,
        )

    def _save_token() -> None:
        page.run_task(methods.set_docker_token, token)

    def _clear_cache() -> None:
        dialogs.confirm_clear_cache(page, lambda: page.run_task(methods.clear_cache))

    def _confirm_remove_cached(identifier: str) -> None:
        dialogs.confirm_remove_cached(
            page, identifier, lambda: page.run_task(methods.remove_cached_image, identifier)
        )

    def _open_changelog(_e=None) -> None:
        dialogs.open_changelog(page)

    def _open_storage_detail(_e=None) -> None:
        dialogs.open_storage_detail(page, methods)

    def _open_env_dialog(_e=None) -> None:
        dialogs.open_env_dialog(page)

    def _open_live_terminal(_e=None) -> None:
        dialogs.open_live_activity_terminal(page)

    def _open_probe_dialog(_e=None) -> None:
        dialogs.open_probe_dialog(page, st.probe_passed, st.probe_summary, methods.check_probe)

    def _licenses(_e=None) -> None:
        dialogs.open_licenses(page)

    # 1. Appearance & Theme Card
    appearance_card = _settings_card(
        [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Theme", size=tokens.FONT_MD, weight=ft.FontWeight.W_500),
                        ft.Row(
                            controls=[
                                _theme_card("light", "Light", ft.Icons.LIGHT_MODE_ROUNDED),
                                _theme_card("dark", "Dark", ft.Icons.DARK_MODE_ROUNDED),
                                _theme_card("system", "System", ft.Icons.BRIGHTNESS_AUTO_ROUNDED),
                            ],
                            spacing=tokens.SPACE_SM,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
                padding=tokens.SPACE_LG,
            ),
        ]
    )

    # 2. Container Storage & Cache Card
    cached_rows = []
    if st.cached_images:
        for img in st.cached_images:
            ident = str(img.get("identifier", ""))
            if not ident or ident == "?":
                continue
            arch = str(img.get("arch", ""))
            size = _fmt_size(img.get("size_bytes", 0))
            cached_rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.LAYERS_ROUNDED, size=tokens.ICON_XS, color=theme.primary()
                            ),
                            ft.Text(f"{ident} ({arch}) · {size}", size=tokens.FONT_XS, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_size=tokens.ICON_SM,
                                tooltip=f"Remove cached {ident}",
                                on_click=lambda _e, i=ident: _confirm_remove_cached(i),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, 0),
                )
            )

    storage_card = _settings_card(
        [
            _setting_row(
                ft.Icons.STORAGE_ROUNDED,
                "Storage Footprint",
                f"Containers and cache: {_fmt_size(st.storage_bytes)}"
                + (f" · {st.cached_count} cached image(s)" if st.cached_count else ""),
                ft.TextButton("Clear all cache", on_click=lambda _e: _clear_cache()),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CLEANING_SERVICES_ROUNDED,
                "Sweep Orphan Layers",
                "Reclaim storage from interrupted pulls or untagged OCI blobs",
                ft.TextButton(
                    "Sweep", on_click=lambda _e: page.run_task(methods.clear_orphan_layers)
                ),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.BUILD_ROUNDED,
                "Clear Build Cache",
                "Drop build_cache_index.json and the layer blobs only it pins (clear-cache --build-cache)",
                ft.TextButton(
                    "Clear", on_click=lambda _e: page.run_task(methods.clear_build_cache)
                ),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.FOLDER_SPECIAL_ROUNDED,
                "Storage Layout",
                "Flet storage roots (data/cache/temp) and every proot-distro area under them",
                ft.TextButton("Inspect", on_click=_open_storage_detail),
                stacked=is_narrow,
            ),
            *cached_rows,
        ]
    )

    # 3. Registry Authentication Card (matching Sherlock custom manifest card layout)
    auth_card = _settings_card(
        [
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.VPN_KEY_ROUNDED,
                                size=tokens.ICON_MD,
                                color=theme.primary(),
                            ),
                            width=tokens.CONTROL_MD,
                            height=tokens.CONTROL_MD,
                            border_radius=tokens.RADIUS_SM,
                            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "Docker Hub Token",
                                    size=tokens.FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                    color=theme.text(),
                                ),
                                ft.Text(
                                    "Stored locally on this device. Lifts anonymous rate limits.",
                                    size=tokens.FONT_XS,
                                    color=theme.text_dim(),
                                ),
                            ],
                            spacing=tokens.SPACE_XXS,
                            expand=True,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=tokens.SPACE_MD,
                    bottom=tokens.SPACE_SM,
                ),
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.TextField(
                            value=token,
                            hint_text="Personal Access Token (optional)",
                            password=True,
                            can_reveal_password=True,
                            text_size=tokens.FONT_SM,
                            expand=True,
                            border=ft.OutlineInputBorder(
                                border_radius=tokens.RADIUS_SM,
                                side=ft.BorderSide(1, theme.surface_alt()),
                            ),
                            on_change=lambda e: set_token(e.control.value),
                            on_submit=lambda _e: _save_token(),
                        ),
                        ft.FilledButton(
                            "Save",
                            on_click=lambda _e: _save_token(),
                            height=tokens.CONTROL_INPUT,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_SM)
                            ),
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=0,
                    bottom=tokens.SPACE_MD,
                ),
            ),
        ]
    )

    # 4. About & System Status Card (CollabShell pattern: brand icon + tagline
    # at the top, version info, terms links, and system environment probe).
    from components.brand_hero import app_icon_svg

    about_card = _settings_card(
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
                ft.Icons.INFO_OUTLINE_ROUNDED,
                f"{APP_NAME} v{APP_VERSION} ({APP_BUILD_NUMBER})",
                "Release notes and change details",
                ft.TextButton("Changelog", on_click=_open_changelog),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.GAVEL_ROUNDED,
                "Open-Source Licenses",
                "Complete license texts for PRoot, talloc, and Python dependencies",
                ft.TextButton("View Licenses", on_click=_licenses),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.POLICY_ROUNDED,
                "Privacy Policy",
                "Container data stays on this device; see the full policy",
                ft.OutlinedButton(
                    "View Policy",
                    on_click=lambda _e: page.run_task(launch_url, PRIVACY_POLICY_URL, page),
                    height=tokens.CONTROL_MD,
                ),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                if st.probe_passed
                else ft.Icons.WARNING_ROUNDED,
                "Environment Probe",
                st.probe_summary or "Native library directory and proot payload ready",
                ft.TextButton("Inspect", on_click=_open_probe_dialog),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.TERMINAL_ROUNDED,
                "Environment Variables",
                "PD_PROOT_BIN, FLET_APP_STORAGE_*, PD_DOCKER_AUTH, PD_FORCE_NO_COLORS",
                ft.TextButton("View", on_click=_open_env_dialog),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.NEWSPAPER_ROUNDED,
                "Live Activity Terminal",
                "Real-time app diagnostics: sessions, installs, ads, errors",
                ft.TextButton("Open Terminal", on_click=_open_live_terminal),
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.POWER_SETTINGS_NEW_ROUNDED,
                "Exit App",
                "Kill all running sessions and close the app",
                ft.TextButton(
                    "Exit",
                    on_click=lambda _e: page.run_task(methods.exit_app),
                    style=ft.ButtonStyle(color=ft.Colors.RED),
                ),
                stacked=is_narrow,
            ),
        ]
    )

    return ft.Column(
        controls=[
            section_header("Appearance & Theme"),
            appearance_card,
            # Banner 1: after Appearance & Theme.
            pooled_banner_ad("settings-1", page),
            section_header("Storage & Cache"),
            storage_card,
            section_header("Registry Authentication"),
            auth_card,
            # Banner 2: after Registry Authentication.
            pooled_banner_ad("settings-2", page),
            section_header("About & System Status"),
            about_card,
            # Banners live BETWEEN sections only — never as the last element.
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ],
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
