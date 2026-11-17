"""Distro home sections: search results and info sections."""

from __future__ import annotations

import flet as ft

from components import card
from core import theme, tokens


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
                                        max_lines=tokens.MAX_LINES_TWO,
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
