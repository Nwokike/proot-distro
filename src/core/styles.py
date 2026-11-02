"""House design pieces — the shapes every screen composes from.

Glass cards, uppercase section headers, chips, status dots, icon empty states
and loading states — the house language from `docs/reference/house-ui-design.md`.
"""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def glass_card(content: ft.Control, padding: int | ft.Padding = tokens.SPACE_MD) -> ft.Control:
    """The standard surface: glass background, hairline border, house radius."""
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=tokens.RADIUS_LG,
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(tokens.HAIRLINE, theme.glass_border()),
    )


def section_header(title: str, action: ft.Control | None = None) -> ft.Control:
    """Uppercase label in the brand color (an optional action on the right)."""
    label = ft.Text(
        title.upper(),
        size=tokens.FONT_SM,
        weight=ft.FontWeight.BOLD,
        color=theme.primary(),
        style=ft.TextStyle(letter_spacing=tokens.LETTER_SPACING),
    )
    if action is None:
        return ft.Container(
            content=label,
            padding=ft.Padding(
                left=tokens.SPACE_LG,
                right=tokens.SPACE_LG,
                top=tokens.SPACE_MD,
                bottom=tokens.SPACE_XS,
            ),
        )
    return ft.Container(
        content=ft.Row(
            controls=[label, action],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(
            left=tokens.SPACE_LG,
            right=tokens.SPACE_LG,
            top=tokens.SPACE_MD,
            bottom=tokens.SPACE_XS,
        ),
    )


def status_dot(is_running: bool = True, size: int = tokens.STATUS_DOT) -> ft.Control:
    """A small pill dot: green when live, muted when idle."""
    return ft.Container(
        width=size,
        height=size,
        border_radius=tokens.RADIUS_PILL,
        bgcolor=theme.ok() if is_running else theme.text_dim(),
    )


def chip(
    label: str,
    icon: str | None = None,
    active: bool = False,
    color: str | None = None,
) -> ft.Control:
    """A tinted pill — the house's inline status/filter chip."""
    tint = color or theme.primary()
    return ft.Container(
        content=ft.Row(
            controls=[
                *([ft.Icon(icon, size=tokens.ICON_XS, color=tint)] if icon else []),
                ft.Text(
                    label,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.W_600 if active else ft.FontWeight.W_400,
                    color=tint if active else theme.text_dim(),
                ),
            ],
            spacing=tokens.SPACE_XS,
            tight=True,
        ),
        padding=ft.Padding.symmetric(
            horizontal=tokens.CHIP_PADDING_H, vertical=tokens.CHIP_PADDING_V
        ),
        border_radius=tokens.RADIUS_SM,
        bgcolor=(
            ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, tint)
            if active
            else ft.Colors.with_opacity(tokens.OPACITY_SUBTLE, tint)
        ),
    )


def empty_state(icon: str, title: str, message: str = "") -> ft.Control:
    """The house empty state: a big icon in a tinted circle, then the words."""
    controls: list[ft.Control] = [
        ft.Container(
            content=ft.Icon(
                icon,
                size=tokens.ICON_EMPTY,
                color=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
            ),
            width=tokens.EMPTY_ICON_SIZE,
            height=tokens.EMPTY_ICON_SIZE,
            border_radius=tokens.ICON_EMPTY,
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.primary()),
            alignment=ft.Alignment.CENTER,
            margin=ft.Margin(bottom=tokens.SPACE_XL),
        ),
        ft.Text(
            title,
            size=tokens.FONT_XL,
            weight=ft.FontWeight.W_600,
            text_align=ft.TextAlign.CENTER,
            color=theme.text(),
        ),
    ]
    if message:
        controls.append(
            ft.Text(
                message,
                size=tokens.FONT_MD,
                color=ft.Colors.with_opacity(tokens.OPACITY_DIM, theme.text()),
                text_align=ft.TextAlign.CENTER,
                width=tokens.MESSAGE_MAX_WIDTH,
            )
        )
    return ft.Container(
        content=ft.Column(
            controls=controls,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=tokens.SPACE_LG, vertical=tokens.SPACE_XXL),
    )


def loading_state(label: str = "Loading…") -> ft.Control:
    """The house loading state: a spinner with a muted label."""
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.ProgressRing(width=tokens.PROGRESS_RING_XL, height=tokens.PROGRESS_RING_XL),
                ft.Text(label, size=tokens.FONT_SM, color=theme.text_dim()),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_MD,
        ),
        padding=ft.Padding.symmetric(vertical=tokens.SPACE_XXXL),
        expand=True,
    )
