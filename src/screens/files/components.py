"""Filesystem UI components: breadcrumbs, empty state, and path helpers matching CollabShell."""

from __future__ import annotations

import posixpath

import flet as ft

from core import theme, tokens


def parent_path(path: str) -> str | None:
    """Parent directory of `path`, or None when already at filesystem root."""
    norm = posixpath.normpath(path or "/")
    if norm == "/":
        return None
    parent = posixpath.dirname(norm)
    return parent if parent else "/"


def build_empty_dir_view(on_upload) -> ft.Control:
    """Centered placeholder when current directory has zero files."""
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(
                    ft.Icons.FOLDER_OPEN_ROUNDED,
                    size=tokens.ICON_XXL,
                    color=ft.Colors.with_opacity(0.3, theme.text_dim()),
                ),
                ft.Text(
                    "Empty directory",
                    size=tokens.FONT_MD,
                    color=theme.text(),
                    weight=ft.FontWeight.W_500,
                ),
                ft.Text(
                    "No files or folders found in this location",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
                ft.Container(height=tokens.SPACE_XS),
                ft.FilledButton(
                    "Upload a file",
                    icon=ft.Icons.UPLOAD_ROUNDED,
                    on_click=on_upload,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
        ),
        alignment=ft.Alignment.CENTER,
        padding=tokens.SPACE_XXL,
        expand=True,
    )


def build_breadcrumbs(path: str, on_navigate) -> ft.Control:
    """Interactive POSIX directory path breadcrumbs with chevrons."""
    norm = posixpath.normpath(path or "/")
    parts = [p for p in norm.split("/") if p]
    at_root = not parts
    root_crumb: ft.Control = (
        ft.Text(
            "/",
            size=tokens.FONT_SM,
            weight=ft.FontWeight.W_600,
            color=theme.text(),
        )
        if at_root
        else ft.TextButton(
            "/",
            on_click=lambda _e: on_navigate("/"),
            style=ft.ButtonStyle(
                padding=ft.Padding(4, 2, 4, 2),
                color=theme.primary(),
            ),
        )
    )
    crumbs: list[ft.Control] = [root_crumb]
    built = ""
    for i, part in enumerate(parts):
        built += f"/{part}"
        captured = built
        is_last = i == len(parts) - 1
        crumbs.append(
            ft.Icon(
                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                size=tokens.ICON_SM,
                color=theme.text_dim(),
            )
        )
        if is_last:
            crumbs.append(
                ft.Text(
                    part,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.W_600,
                    color=theme.text(),
                )
            )
        else:
            crumbs.append(
                ft.TextButton(
                    part,
                    on_click=lambda _e, p=captured: on_navigate(p),
                    style=ft.ButtonStyle(
                        padding=ft.Padding(4, 2, 4, 2),
                        color=theme.primary(),
                    ),
                )
            )
    return ft.Row(controls=crumbs, spacing=0, scroll=ft.ScrollMode.AUTO)
