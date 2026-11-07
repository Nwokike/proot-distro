"""Container picker for the Files tab (moved out of FilesView)."""

from __future__ import annotations

import flet as ft

from components import card, section_header
from components.banner_ad import pooled_banner_ad
from core import theme, tokens


def build_container_picker(installed, containers_state, default_path, page, on_open) -> ft.Control:
    picker_rows = []
    banner_count = 0
    total = len(installed)
    for idx, c in enumerate(installed, start=1):
        row_meta = next((r for r in (containers_state or []) if r.get("name") == c), {})

        def _open(_e, name=c) -> None:
            on_open(name)

        picker_rows.append(
            card(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.FOLDER_ROUNDED,
                                size=tokens.ICON_MD,
                                color=theme.primary(),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        c,
                                        size=tokens.FONT_LG,
                                        weight=ft.FontWeight.W_600,
                                        color=theme.text(),
                                    ),
                                    ft.Text(
                                        f"{row_meta.get('image', '')} · "
                                        f"{row_meta.get('arch', '')}".strip(" ·"),
                                        size=tokens.FONT_XS,
                                        color=theme.text_dim(),
                                    ),
                                ],
                                spacing=tokens.SPACE_XXS,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                size=tokens.ICON_MD,
                                color=theme.text_dim(),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    on_click=_open,
                    ink=True,
                ),
                padding=tokens.SPACE_SM,
            )
        )
        # Banner rule (owner): always immediately after the LAST container
        # card; when there are more than 5 containers, also after every 5th.
        if idx == total or (total > 5 and idx % 5 == 0):
            banner_count += 1
            picker_rows.append(pooled_banner_ad(f"files-picker-{banner_count}", page))
    return ft.Column(
        controls=[
            section_header("Browse a container"),
            ft.ListView(
                controls=picker_rows,
                spacing=tokens.SPACE_SM,
                expand=True,
            ),
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ],
        spacing=tokens.SPACE_SM,
        expand=True,
    )
