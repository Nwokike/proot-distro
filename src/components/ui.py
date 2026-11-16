"""Shared UI pieces — thin wrappers over the house styles."""

from __future__ import annotations

import flet as ft

from core import styles, theme, tokens
from core.constants import AD_SLOT_NO_CONTAINERS

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


def house_field(
    *,
    label: str | None = None,
    hint: str = "",
    value: str = "",
    on_change=None,
    on_submit=None,
    on_blur=None,
    password: bool = False,
    can_reveal_password: bool = False,
    multiline: bool = False,
    prefix_icon: ft.IconData | None = None,
    suffix: ft.Control | None = None,
    width: float | None = None,
    expand: bool = False,
    height: float | None = tokens.CONTROL_INPUT,
    text_size: int = tokens.FONT_SM,
    dense: bool = False,
    keyboard_type=None,
    tooltip: str = "",
    read_only: bool = False,
    autofocus: bool = False,
    min_lines: int | None = None,
    max_lines: int | None = None,
    visible: bool = True,
    font_family: str | None = None,
    bgcolor: str | None = None,
) -> ft.TextField:
    """The ONE house input: a filled, borderless rounded surface.

    Material 3's filled field instead of the outlined box the owner rejected
    everywhere — same visual family as the SearchBar the app already uses
    (bar_bgcolor = glass). No outline, one tinted fill, house radius.
    """
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        on_change=on_change,
        on_submit=on_submit,
        on_blur=on_blur,
        password=password,
        can_reveal_password=can_reveal_password,
        multiline=multiline,
        prefix_icon=prefix_icon,
        suffix=suffix,
        width=width,
        expand=expand,
        height=height if not multiline else None,
        text_size=text_size,
        dense=dense,
        keyboard_type=keyboard_type,
        tooltip=tooltip or None,
        read_only=read_only,
        autofocus=autofocus,
        min_lines=min_lines,
        max_lines=max_lines,
        visible=visible,
        filled=True,
        bgcolor=bgcolor,
        fill_color=ft.Colors.with_opacity(tokens.FIELD_FILL_OPACITY, theme.text()),
        # Rounded fill, no visible outline: a zero-width side on an outline
        # border. (`border_radius=` alone is deprecated in Flet 1.1.)
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(0),
        ),
        content_padding=ft.Padding(
            tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS
        ),
        hint_style=ft.TextStyle(size=text_size, color=theme.text_dim()),
        text_style=ft.TextStyle(size=text_size, color=theme.text(), font_family=font_family),
    )


def switch_row(label: str, value: bool, on_change, *, tooltip: str = "") -> ft.Control:
    """The ONE house toggle: Material's Switch at house scale + a compact label.

    Material's default Switch is ~60x40 dp and dominated every row (owner
    ruling 2026-11-15); `scale` is a real property, so nothing is faked.
    """
    return ft.Row(
        controls=[
            ft.Switch(
                value=value,
                scale=tokens.SWITCH_SCALE,
                on_change=on_change,
                tooltip=tooltip or label,
            ),
            ft.Text(label, size=tokens.FONT_XS, color=theme.text()),
        ],
        spacing=tokens.SPACE_XXS,
        tight=True,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def search_field(
    *,
    hint: str,
    value: str = "",
    on_change=None,
    on_submit=None,
    trailing: list[ft.Control] | None = None,
    expand: bool = True,
    autofocus: bool = False,
) -> ft.SearchBar:
    """The ONE search input — Flet's SearchBar in the home bar's shape.

    The owner's ruling: search is NOT a text field. Wherever the app searches
    (Home install/search, Files filter, Help) it uses this control: glass fill,
    house border, no leading icon, compact text.
    """
    return ft.SearchBar(
        value=value,
        bar_hint_text=hint,
        bar_trailing=trailing or [],
        bar_bgcolor=theme.glass_bg(),
        bar_border_side=ft.BorderSide(tokens.HAIRLINE, theme.glass_border()),
        bar_shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_MD),
        bar_text_style=ft.TextStyle(size=tokens.FONT_SM, weight=ft.FontWeight.W_500),
        bar_hint_text_style=ft.TextStyle(size=tokens.FONT_SM, color=theme.text_dim()),
        full_screen=False,
        expand=expand,
        autofocus=autofocus,
        on_change=on_change,
        on_submit=on_submit,
    )


def changelog_rows(version: str) -> list[ft.Control]:
    """One row per changelog bullet, so each note sits on its own line.

    A single Text with "•" bullets and newlines collapses into a paragraph
    when it goes through Markdown (and wraps badly on a phone)."""
    from core.changelog import notes_for

    rows: list[ft.Control] = []
    for raw in notes_for(version).splitlines():
        line = raw.strip().lstrip("•").strip()
        if not line:
            continue
        rows.append(
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CIRCLE, size=tokens.ICON_MICRO, color=theme.primary()),
                    ft.Text(line, size=tokens.FONT_SM, color=theme.text(), expand=True),
                ],
                spacing=tokens.SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.START,
            )
        )
    return rows


def no_containers_empty_state() -> ft.Control:
    """The shared empty state for screens that require an installed container."""
    return empty_state(
        NO_CONTAINERS_TITLE,
        NO_CONTAINERS_MESSAGE,
        icon=ft.Icons.FOLDER_OFF_ROUNDED,
    )


def containers_required_empty_state(page=None, ad_slot: str = AD_SLOT_NO_CONTAINERS) -> ft.Control:
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
    labels: dict[str, str] | None = None,
) -> ft.Control:
    """A tiny pill dropdown — CollabShell's model_pill pattern
    (components/model_pill.py): PopupMenuButton whose face is a small pill
    (icon + elided label + chevron), not a big rectangle.

    `labels` maps an option value to the text shown for it (the value itself is
    still what `on_select` receives), so real option keys stay exact while the
    face stays readable."""
    text_for = labels or {}

    def _text(opt: str) -> str:
        return text_for.get(opt, opt)

    return ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(icon, size=tokens.ICON_SM, color=theme.primary()),
                    ft.Text(
                        _text(value) if value else label,
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
                            _text(opt),
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
