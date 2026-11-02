"""Distro home sections: step/feature helpers, search results, info sections."""

from __future__ import annotations

import flet as ft

from components import card, section_header
from components.banner_ad import pooled_banner_ad
from core import theme, tokens


def _step_row(num: str, title: str, desc: str) -> ft.Row:
    """Numbered step row matching CollabShell / DDGS home patterns."""
    return ft.Row(
        controls=[
            ft.Container(
                content=ft.Text(
                    num,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.BOLD,
                    color=theme.WHITE,
                ),
                width=tokens.CONTROL_XS,
                height=tokens.CONTROL_XS,
                border_radius=tokens.RADIUS_PILL,
                bgcolor=theme.primary(),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Column(
                controls=[
                    ft.Text(
                        title, size=tokens.FONT_SM, weight=ft.FontWeight.W_600, color=theme.text()
                    ),
                    ft.Text(desc, size=tokens.FONT_XS, color=theme.text_dim()),
                ],
                spacing=tokens.SPACE_XXS,
                expand=True,
            ),
        ],
        spacing=tokens.SPACE_SM,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _feature_card(icon: ft.IconData, title: str, desc: str) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=tokens.ICON_MD, color=theme.primary()),
                    width=tokens.CONTROL_XL,
                    height=tokens.CONTROL_XL,
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            title,
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            color=theme.text(),
                        ),
                        ft.Text(desc, size=tokens.FONT_XS, color=theme.text_dim()),
                    ],
                    spacing=tokens.SPACE_XXS,
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=tokens.SPACE_MD,
    )


def build_search_results(st, consent_install) -> list[ft.Control]:
    """One card per Docker Hub result (the status line is rendered by the view)."""
    controls: list[ft.Control] = []
    if st.search_results:
        for r in st.search_results:
            r_name = r.get("name", "")
            r_desc = r.get("description", "") or "No description"
            controls.append(
                card(
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        r_name, size=tokens.FONT_SM, weight=ft.FontWeight.W_600
                                    ),
                                    ft.Text(
                                        r_desc,
                                        size=tokens.FONT_XS,
                                        color=theme.text_dim(),
                                        max_lines=2,
                                    ),
                                ],
                                spacing=tokens.SPACE_XXS,
                                expand=True,
                            ),
                            ft.FilledButton(
                                "Install",
                                on_click=lambda _e, target=r_name: consent_install(target),
                                height=tokens.CONTROL_COMPACT,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
    return controls


def build_info_sections(page: ft.Page) -> list[ft.Control]:
    """How It Works + capabilities sections, with the banner between them."""
    return [
        section_header("How It Works"),
        card(
            ft.Column(
                controls=[
                    _step_row(
                        "1",
                        "Pick or Search a Distro",
                        "Select Debian, Ubuntu, Alpine or enter any public container image reference.",
                    ),
                    _step_row(
                        "2",
                        "One-Tap Install",
                        "Downloads and unpacks official container layers directly into private app storage.",
                    ),
                    _step_row(
                        "3",
                        "Launch Interactive Terminal",
                        "Enjoy full bash shell access with apt package manager, tools, and multi-session tabs.",
                    ),
                ],
                spacing=tokens.SPACE_MD,
            ),
            padding=tokens.SPACE_LG,
        ),
        pooled_banner_ad("home-2", page),
        section_header("What Proot Distro Can Do"),
        _feature_card(
            ft.Icons.SECURITY_ROUNDED,
            "Rootless Linux Userspace",
            "Execute full Linux userland binaries without rooting your Android device or altering system partitions.",
        ),
        _feature_card(
            ft.Icons.TERMINAL_ROUNDED,
            "Native Interactive PTY",
            "True terminal experience with soft keyboard handling, extra virtual keys, zoom controls, and live title tracking.",
        ),
        _feature_card(
            ft.Icons.FOLDER_COPY_ROUNDED,
            "Container Backup & Sync",
            "Backup snapshots to tar archives, synchronize folders, and inspect container configurations anytime.",
        ),
    ]
