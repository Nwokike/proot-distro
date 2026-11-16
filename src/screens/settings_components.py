"""Reusable rows and grouped surfaces for SettingsView."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def _settings_card(controls: list[ft.Control]) -> ft.Container:
    """Grouped settings card with Material 3 glass surface matching Sherlock."""
    return ft.Container(
        content=ft.Column(controls=controls, spacing=tokens.SPACE_NONE),
        border_radius=tokens.RADIUS_LG,
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(width=tokens.HAIRLINE, color=theme.glass_border()),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def _setting_row(
    icon: ft.IconData,
    title: str,
    subtitle: str,
    trailing: ft.Control | None = None,
    stacked: bool = False,
    value: str | None = None,
    on_tap=None,
) -> ft.Container:
    """Settings row: icon box, title, subtitle and a trailing control.

    Pass `value` to show the live value in the row itself (the Material
    overview pattern) — the value text plus a chevron when the row navigates.
    `on_tap` makes the whole row tappable; no "Open/View/Inspect" buttons."""
    icon_box = ft.Container(
        content=ft.Icon(
            icon,
            size=tokens.ICON_MD,
            color=theme.primary(),
        ),
        width=tokens.CONTROL_MD,
        height=tokens.CONTROL_MD,
        border_radius=tokens.RADIUS_SM,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
        alignment=ft.Alignment.CENTER,
    )
    text_col = ft.Column(
        controls=[
            ft.Text(
                title,
                size=tokens.FONT_MD,
                weight=ft.FontWeight.W_500,
                color=theme.text(),
            ),
            ft.Text(
                subtitle,
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            ),
        ],
        spacing=tokens.SPACE_XXS,
        expand=True,
    )

    tail_controls: list[ft.Control] = []
    if value is not None:
        tail_controls.append(
            ft.Text(
                value,
                size=tokens.FONT_XS,
                color=theme.text(),
                text_align=ft.TextAlign.RIGHT,
                no_wrap=False,
            )
        )
    if trailing is not None:
        tail_controls.append(trailing)
    # The chevron marks a row that NAVIGATES. A row that already carries its own
    # trailing control (an external-link icon, a Manage button) gets no second
    # arrow.
    if on_tap is not None and trailing is None and value is None:
        tail_controls.append(
            ft.Icon(
                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                size=tokens.ICON_SM,
                color=theme.text_dim(),
            )
        )

    trailing_control = (
        ft.Row(
            controls=tail_controls,
            spacing=tokens.SPACE_XS,
            tight=True,
            alignment=ft.MainAxisAlignment.END,
        )
        if tail_controls
        else None
    )

    trailing_controls = [trailing_control] if trailing_control is not None else []

    if stacked:
        trailing_line = ft.Row(
            controls=[
                ft.Container(width=tokens.CONTROL_MD + tokens.SPACE_MD),
                *trailing_controls,
            ],
            spacing=tokens.SPACE_NONE,
        )
        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[icon_box, text_col],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                trailing_line,
            ],
            spacing=tokens.SPACE_XS,
        )
    else:
        content = ft.Row(
            controls=[icon_box, text_col, *trailing_controls],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Container(
        content=content,
        padding=ft.Padding(
            tokens.SPACE_LG,
            tokens.SPACE_MD,
            tokens.SPACE_LG,
            tokens.SPACE_MD,
        ),
        on_click=on_tap,
        ink=on_tap is not None,
    )
