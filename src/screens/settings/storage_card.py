"""Settings -> Storage & Cache card (split out to keep the view under 500 lines)."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from screens.formatting import format_size as _fmt_size
from screens.settings_components import _setting_row, _settings_card


def build_storage_card(
    st,
    *,
    narrow: bool = False,
    on_layout,
    on_sweep,
    on_build_cache,
    on_clear_app,
    on_clear_all,
    on_remove_cached,
) -> ft.Control:
    """Honest numbers: what lives in containers, what lives in the OCI cache,
    the real cached images, and the reclaim actions (OCI, app cache, all)."""
    cached_rows: list[ft.Control] = []
    images = [
        img for img in (st.cached_images or []) if str(img.get("identifier", "")) not in ("", "?")
    ]
    if images:
        cached_rows.append(
            ft.Container(
                content=ft.Text(
                    "Cached images",
                    size=tokens.FONT_XS,
                    weight=ft.FontWeight.W_600,
                    color=theme.text_dim(),
                ),
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_XXS),
            )
        )
    for img in images:
        ident = str(img.get("identifier", ""))
        arch = str(img.get("arch", ""))
        # A missing byte count is honest; "0 B" is not.
        size = _fmt_size(img["size_bytes"]) if img.get("size_bytes") else "size unavailable"
        cached_rows.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.LAYERS_ROUNDED, size=tokens.ICON_XS, color=theme.primary()
                        ),
                        ft.Text(
                            f"{ident}" + (f" ({arch})" if arch else "") + f" · {size}",
                            size=tokens.FONT_XS,
                            expand=True,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_size=tokens.ICON_SM,
                            tooltip=f"Remove cached {ident}",
                            on_click=lambda _e, i=ident: on_remove_cached(i),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, 0),
            )
        )

    return _settings_card(
        [
            _setting_row(
                ft.Icons.STORAGE_ROUNDED,
                "Storage in use",
                f"containers {_fmt_size(st.storage_containers_bytes)} · "
                f"OCI cache {_fmt_size(st.storage_cache_bytes)}",
                value=_fmt_size(st.storage_bytes),
                on_tap=on_layout,
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            *cached_rows,
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CLEANING_SERVICES_ROUNDED,
                "Sweep orphan layers",
                "Layers no container references (interrupted pulls, untagged blobs)",
                ft.TextButton("Sweep", on_click=lambda _e: on_sweep()),
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.BUILD_ROUNDED,
                "Clear build cache",
                "Dockerfile layer cache and the blobs only it pins",
                ft.TextButton("Clear", on_click=lambda _e: on_build_cache()),
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CLEANING_SERVICES_ROUNDED,
                "Clear app cache",
                "Probe results and temp files. Rebuilt on the next use",
                ft.TextButton("Clear", on_click=lambda _e: on_clear_app()),
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.DELETE_SWEEP_ROUNDED,
                "Clear all cache",
                "Cached layers and manifests. Installed containers are not touched",
                ft.TextButton("Clear all", on_click=lambda _e: on_clear_all()),
                stacked=narrow,
            ),
        ]
    )
