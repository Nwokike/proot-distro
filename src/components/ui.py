"""Shared UI pieces — thin wrappers over the house styles."""

from __future__ import annotations

import flet as ft

from core import styles, theme, tokens


def card(content: ft.Control, padding: int | ft.Padding = tokens.SPACE_MD) -> ft.Control:
    """The house surface (glass card)."""
    return styles.glass_card(content, padding)


def section_header(title: str, action: ft.Control | None = None) -> ft.Control:
    """The house section label."""
    return styles.section_header(title, action)


def empty_state(title: str, message: str = "", icon: str = ft.Icons.INBOX) -> ft.Control:
    """The house empty state."""
    return styles.empty_state(icon, title, message)


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


def hints_card(dismissed: bool, on_dismiss) -> ft.Control:
    """The capability hints: what this app can do, dismissible."""
    if dismissed:
        return ft.Container()
    items = [
        "Runs real Linux containers on your phone — the same proot-distro engine Termux uses, without Termux.",
        "Install any Docker image: type a reference (debian:bookworm, ubuntu:24.04, alpine:3.21) or search Docker Hub.",
        "Open a shell in any container, and manage it: rename, back up, restore, copy, reset or remove.",
    ]
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=tokens.ICON_XS, color=theme.primary()),
                        ft.Text(
                            "How this works",
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.BOLD,
                            color=theme.text(),
                            expand=True,
                        ),
                        ft.TextButton("Got it", on_click=on_dismiss),
                    ]
                ),
                *[
                    ft.Text(f"• {line}", size=tokens.FONT_SM, color=theme.text_dim())
                    for line in items
                ],
            ],
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(tokens.HAIRLINE, theme.glass_border()),
        border_radius=tokens.RADIUS_LG,
        padding=ft.Padding.symmetric(horizontal=tokens.SPACE_MD, vertical=tokens.SPACE_SM),
    )
