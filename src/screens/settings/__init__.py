from __future__ import annotations

import flet as ft

from components import section_header
from components.banner_ad import pooled_banner_ad
from components.ui import house_field, pill_dropdown, switch_row
from core import layout, theme, tokens
from core.constants import (
    AD_SLOT_SETTINGS_1,
    AD_SLOT_SETTINGS_2,
    AD_SLOT_SETTINGS_3,
    PRIVACY_POLICY_URL,
    TERMS_OF_SERVICE_URL,
)
from core.shared_services import launch_url
from core.state import DEFAULT_TERMINAL_SETTINGS, state
from screens.settings_components import _setting_row, _settings_card
from state.controller_ctx import ControllerMethodsCtx

from . import dialogs
from .sections import build_about_card


@ft.component
def SettingsView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    token, set_token = ft.use_state(st.docker_token)
    # Terminal defaults render inline, so their live values are component state
    # (a saved value must show immediately, not after reopening Settings).
    term, set_term = ft.use_state({**DEFAULT_TERMINAL_SETTINGS, **(state.terminal_settings or {})})
    # Side-by-side values stack UNDER the title on small screens (owner ruling
    # 2026-11-16: never squeeze a value and a button onto one narrow line).
    is_narrow = layout.is_narrow(page)
    # Clearing the log needs a re-render; a counter is the declarative trigger.
    _debug_rev, set_debug_rev = ft.use_state(0)

    if st.settings_section == "build":
        from screens.build_view import BuildView

        def _back(_e=None) -> None:
            page.run_task(methods.open_settings_section, "")

        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(
                            ft.Icons.ARROW_BACK_ROUNDED,
                            tooltip="Back to Settings",
                            on_click=_back,
                        ),
                        ft.Text("Build & push", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(content=BuildView(), expand=True),
            ],
            spacing=tokens.SPACE_SM,
            expand=True,
        )

    def _save_token() -> None:
        page.run_task(methods.set_docker_token, token)

    def _clear_cache() -> None:
        dialogs.confirm_clear_cache(page, lambda: page.run_task(methods.clear_cache))

    def _sweep_orphans() -> None:
        dialogs.confirm_simple(
            page,
            "Sweep orphan layers?",
            "Deletes cached image layers no container references. Containers are not touched.",
            "Sweep",
            lambda: page.run_task(methods.clear_orphan_layers),
        )

    def _clear_build_cache() -> None:
        dialogs.confirm_simple(
            page,
            "Clear the build cache?",
            "Dockerfile layer cache is removed; the next build starts from scratch.",
            "Clear",
            lambda: page.run_task(methods.clear_build_cache),
        )

    def _confirm_remove_cached(identifier: str) -> None:
        dialogs.confirm_remove_cached(
            page, identifier, lambda: page.run_task(methods.remove_cached_image, identifier)
        )

    def _open_changelog(_e=None) -> None:
        dialogs.open_changelog(page)

    def _open_help(_e=None) -> None:
        from screens.help import show_help_sheet

        show_help_sheet(page, methods)

    def _open_storage_detail(_e=None) -> None:
        dialogs.open_storage_detail(page, methods)

    def _open_live_terminal(_e=None) -> None:
        dialogs.open_debugging_output(page)

    def _open_probe_dialog(_e=None) -> None:
        dialogs.open_probe_dialog(page, st.probe_passed, st.probe_summary, methods.check_probe)

    def _licenses(_e=None) -> None:
        dialogs.open_licenses(page)

    # 1. Appearance & Theme Card
    from .appearance_card import build_appearance_card

    appearance_card = build_appearance_card(
        st.theme_mode,
        lambda mode: page.run_task(methods.set_theme_mode, mode),
    )

    # 2. Container Storage & Cache Card
    from .storage_card import build_storage_card

    storage_card = build_storage_card(
        st,
        narrow=is_narrow,
        on_layout=_open_storage_detail,
        on_sweep=_sweep_orphans,
        on_build_cache=_clear_build_cache,
        on_clear_app=lambda: page.run_task(methods.clear_app_cache),
        on_clear_all=_clear_cache,
        on_remove_cached=_confirm_remove_cached,
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
                                    "Docker Hub credentials",
                                    size=tokens.FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                    color=theme.text(),
                                ),
                                ft.Text(
                                    "username:token (a Personal Access Token as the password). Lifts anonymous rate limits.",
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
                        house_field(
                            value=token,
                            hint="username:token (optional)",
                            password=True,
                            can_reveal_password=True,
                            expand=True,
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

    def _open_environment(_e=None) -> None:
        from .env_dialog import open_env_dialog

        open_env_dialog(page, methods)

    def _open_running(_e=None) -> None:
        page.run_task(methods.list_sessions)

    def _open_privacy_ads(_e=None) -> None:
        page.run_task(methods.show_privacy_options)

    def _open_notifications(_e=None) -> None:
        page.run_task(methods.open_notification_settings)

    def _check_updates(_e=None) -> None:
        page.run_task(methods.check_updates_now)

    def _replay_intro(_e=None) -> None:
        page.run_task(methods.replay_onboarding)

    def _open_build(_e=None) -> None:
        page.run_task(methods.open_developer_tools, True)

    def _set_term(key: str, value: object) -> None:
        """Terminal defaults save on change (no hidden second step)."""
        updated = {**term, key: value}
        set_term(updated)
        state.terminal_settings = updated
        state.terminal_theme_rev += 1
        page.run_task(methods.save_terminal_settings)

    def _set_term_size(text: str) -> None:
        try:
            size = float((text or "").strip() or 0)
        except ValueError:
            return
        term["font_size"] = max(0.0, min(32.0, size))
        _set_term("font_size", term["font_size"])

    # ── value helpers ─────────────────────────────────────────────────────────
    def _terminal_summary() -> str:
        size = float(term.get("font_size") or 0)
        saved_theme = str(term.get("theme") or "")
        return " · ".join(
            [
                saved_theme or "theme follows the app mode",
                f"{size:g}pt" if size else "default size",
                "blink on" if term.get("cursor_blink", True) else "blink off",
            ]
        )

    def _notifications_value() -> str:
        if st.notifications_enabled is None:
            return "tap to check"
        return "Allowed" if st.notifications_enabled else "Blocked: tap to allow"

    def _privacy_value() -> str:
        return "Personalized" if st.can_request_ads else "Non-personalized"

    def _running_value() -> str:
        if st.running_sessions is None:
            return "tap to list"
        count = len(st.running_sessions)
        return "No running processes" if count == 0 else f"{count} running"

    def _env_value() -> str:
        from .env_dialog import env_rows_summary

        return env_rows_summary()

    def _debug_lines() -> list[str]:
        from core.logger_handler import in_memory_log_handler

        return in_memory_log_handler.get_logs()[-20:]

    def _copy_debug(_e=None) -> None:
        from components.snack import show_snack
        from core.logger_handler import in_memory_log_handler

        async def _do() -> None:
            clipboard = getattr(page, "clipboard", None)
            if clipboard is None:
                return
            await clipboard.set("\n".join(in_memory_log_handler.get_logs()))
            show_snack(page, "debugging output copied")

        page.run_task(_do)

    def _clear_debug(_e=None) -> None:
        from core.logger_handler import in_memory_log_handler

        in_memory_log_handler.clear_logs()
        set_debug_rev(_debug_rev + 1)

    from screens.terminal_controls import _THEME_PRESETS

    from .display_defaults import build_display_defaults

    def _persist_display() -> None:
        page.run_task(methods.save_display_settings)

    terminal_controls_row = ft.Container(
        content=ft.Row(
            controls=[
                pill_dropdown(
                    "Theme",
                    ft.Icons.PALETTE_ROUNDED,
                    ["auto", *(_THEME_PRESETS)],
                    str(term.get("theme") or "auto"),
                    lambda value: _set_term("theme", "" if value == "auto" else value),
                    tooltip="Terminal theme for new shells (auto follows the app mode)",
                    labels={"auto": "Auto (Dracula / Colab Light)"},
                ),
                house_field(
                    value=(
                        f"{float(term['font_size']):g}" if float(term.get("font_size") or 0) else ""
                    ),
                    hint="size",
                    width=tokens.FIELD_COMPACT_WIDTH,
                    height=tokens.CONTROL_CHIP,
                    dense=True,
                    text_size=tokens.FONT_XS,
                    keyboard_type=ft.KeyboardType.NUMBER,
                    suffix=ft.Text("pt", size=tokens.FONT_XS, color=theme.text_dim()),
                    tooltip="Font size in pt (empty = widget default)",
                    on_blur=lambda e: _set_term_size(e.control.value),
                    on_submit=lambda e: _set_term_size(e.control.value),
                ),
                switch_row(
                    "Cursor blink",
                    bool(term.get("cursor_blink", True)),
                    lambda e: _set_term("cursor_blink", bool(e.control.value)),
                ),
            ],
            spacing=tokens.SPACE_MD,
            # NEVER wrap=True here: a TextField inside a Wrap is the
            # "WrapParentData is not a subtype of FlexParentData" crash
            # (proven by rendering it alone, 2026-11-15).
            wrap=False,
            scroll=ft.ScrollMode.AUTO,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_SM),
    )

    experience_card = _settings_card(
        [
            _setting_row(
                ft.Icons.DESKTOP_WINDOWS_ROUNDED,
                "Display defaults",
                "Applied to every new desktop and app display",
            ),
            ft.Container(
                content=build_display_defaults(_persist_display),
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_SM),
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.TERMINAL_ROUNDED,
                "Terminal defaults",
                "Theme, size and cursor used by new shells",
                value=_terminal_summary(),
                stacked=is_narrow,
            ),
            terminal_controls_row,
        ]
    )

    system_card = _settings_card(
        [
            _setting_row(
                ft.Icons.NOTIFICATIONS_ROUNDED,
                "Notifications",
                "The persistent notification keeps your work alive in the background",
                value=_notifications_value(),
                on_tap=_open_notifications,
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.PRIVACY_TIP_ROUNDED,
                "Privacy & Ads",
                "Ads always serve; this is the personalization verdict",
                value=_privacy_value(),
                on_tap=_open_privacy_ads,
                stacked=is_narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.MEMORY_ROUNDED,
                "Running processes",
                "Every live guest session: stop one or stop all",
                value=_running_value(),
                on_tap=_open_running,
                stacked=is_narrow,
            ),
        ]
    )

    from .developer_card import build_developer_card

    developer_card = build_developer_card(
        st,
        narrow=is_narrow,
        lines=_debug_lines(),
        env_value=_env_value(),
        on_build=_open_build,
        on_probe=_open_probe_dialog,
        on_environment=_open_environment,
        on_copy=_copy_debug,
        on_clear=_clear_debug,
        on_full_log=_open_live_terminal,
    )

    about_card = build_about_card(
        page,
        on_help=_open_help,
        on_changelog=_open_changelog,
        on_licenses=_licenses,
        on_privacy=lambda _e: page.run_task(launch_url, PRIVACY_POLICY_URL, page),
        on_terms=lambda _e: page.run_task(launch_url, TERMS_OF_SERVICE_URL, page),
        on_update=_check_updates,
        on_intro=_replay_intro,
        on_exit=lambda _e: dialogs.confirm_exit(page, lambda: page.run_task(methods.exit_app)),
        on_link=lambda url: page.run_task(launch_url, url, page),
        on_debug=_open_live_terminal,
        probe_summary=st.probe_summary,
        update_available=st.update_available,
    )

    return ft.Column(
        controls=[
            section_header("Appearance & Theme"),
            appearance_card,
            section_header("Display & Terminal"),
            experience_card,
            # Banner 1: after the display/terminal surface (owner: banners sit
            # BETWEEN every two major sections, three across Settings).
            pooled_banner_ad(AD_SLOT_SETTINGS_1, page),
            section_header("System"),
            system_card,
            section_header("Developer tools"),
            developer_card,
            # Banner 2.
            pooled_banner_ad(AD_SLOT_SETTINGS_2, page),
            section_header("Storage & Cache"),
            storage_card,
            section_header("Registry Authentication"),
            auth_card,
            # Banner 3.
            pooled_banner_ad(AD_SLOT_SETTINGS_3, page),
            section_header("About & System Status"),
            about_card,
            # Banners live BETWEEN sections only, never as the last element.
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ],
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
