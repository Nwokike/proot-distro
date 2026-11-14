"""Shared UI pieces — thin wrappers over the house styles."""

from __future__ import annotations

import flet as ft

from core import styles, theme, tokens

NO_CONTAINERS_TITLE = "No containers installed"
NO_CONTAINERS_MESSAGE = "Install a container first to get started."


def card(content: ft.Control, padding: int | ft.Padding = tokens.SPACE_MD) -> ft.Control:
    """The house surface (glass card)."""
    return styles.glass_card(content, padding)


def section_header(title: str, action: ft.Control | None = None) -> ft.Control:
    """The house section label."""
    return styles.section_header(title, action)


def empty_state(title: str, message: str = "", icon: str = ft.Icons.INBOX) -> ft.Control:
    """The house empty state."""
    return styles.empty_state(icon, title, message)


def no_containers_empty_state() -> ft.Control:
    """The shared empty state for screens that require an installed container."""
    return empty_state(
        NO_CONTAINERS_TITLE,
        NO_CONTAINERS_MESSAGE,
        icon=ft.Icons.FOLDER_OFF_ROUNDED,
    )


def containers_required_empty_state(page=None, ad_slot: str = "no-containers") -> ft.Control:
    """The ONE no-container state for Files AND Terminal — the Files empty
    state (icon + title + message) with the banner ad row beneath, so both
    tabs show the identical thing instead of hardcoded copies."""
    from components.banner_ad import pooled_banner_ad

    return ft.Column(
        controls=[
            ft.Container(
                content=no_containers_empty_state(),
                alignment=ft.Alignment.CENTER,
                expand=True,
            ),
            pooled_banner_ad(ad_slot, page),
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ],
        expand=True,
    )


def pill_dropdown(
    label: str,
    icon: str,
    options: list[str],
    value: str,
    on_select,
    tooltip: str = "",
) -> ft.Control:
    """A tiny pill dropdown — CollabShell's model_pill pattern
    (components/model_pill.py): PopupMenuButton whose face is a small pill
    (icon + elided label + chevron), not a big rectangle."""
    return ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=tokens.ICON_SM, color=theme.primary()),
                    ft.Text(
                        value or label,
                        size=tokens.FONT_XS,
                        weight=ft.FontWeight.W_600,
                        color=theme.primary(),
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Icon(
                        ft.Icons.EXPAND_MORE_ROUNDED, size=tokens.ICON_MICRO, color=theme.primary()
                    ),
                ],
                spacing=tokens.SPACE_XXS,
                tight=True,
            ),
            padding=ft.Padding.symmetric(
                horizontal=tokens.CHIP_PADDING_H, vertical=tokens.CHIP_PADDING_V
            ),
            border_radius=tokens.RADIUS_PILL,
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TINT, theme.primary()),
        ),
        items=[
            ft.PopupMenuItem(
                content=ft.Row(
                    controls=[
                        ft.Text(
                            opt,
                            size=tokens.FONT_XS,
                            weight=ft.FontWeight.W_600 if opt == value else ft.FontWeight.W_400,
                            color=theme.text(),
                        ),
                        *(
                            [
                                ft.Icon(
                                    ft.Icons.CHECK_ROUNDED,
                                    size=tokens.ICON_XS,
                                    color=theme.primary(),
                                )
                            ]
                            if opt == value
                            else []
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
                on_click=lambda _e, o=opt: on_select(o),
            )
            for opt in options
        ],
        menu_position=ft.PopupMenuPosition.UNDER,
        tooltip=tooltip or label,
    )


def probe_banner(summary: str) -> ft.Control:
    """A warning strip for a failed probe."""
    warn_color = theme.warn()
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=tokens.ICON_XS, color=warn_color),
                ft.Text(summary, size=tokens.FONT_SM, color=warn_color, expand=True),
            ],
            spacing=tokens.SPACE_XS,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TINT, warn_color),
        border_radius=tokens.RADIUS_SM,
        padding=ft.Padding.symmetric(horizontal=tokens.SPACE_MD, vertical=tokens.SPACE_SM),
    )
