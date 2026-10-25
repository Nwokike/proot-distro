"""File item — reusable list item for the container file browser matching CollabShell."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def _file_icon(name: str, is_dir: bool) -> ft.IconData:
    """Return an appropriate icon based on file type."""
    if is_dir:
        return ft.Icons.FOLDER_ROUNDED
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    icon_map = {
        "py": ft.Icons.CODE_ROUNDED,
        "sh": ft.Icons.TERMINAL_ROUNDED,
        "bash": ft.Icons.TERMINAL_ROUNDED,
        "csv": ft.Icons.TABLE_CHART_ROUNDED,
        "json": ft.Icons.DATA_OBJECT_ROUNDED,
        "yaml": ft.Icons.DATA_OBJECT_ROUNDED,
        "yml": ft.Icons.DATA_OBJECT_ROUNDED,
        "toml": ft.Icons.DATA_OBJECT_ROUNDED,
        "txt": ft.Icons.DESCRIPTION_ROUNDED,
        "md": ft.Icons.ARTICLE_ROUNDED,
        "png": ft.Icons.IMAGE_ROUNDED,
        "jpg": ft.Icons.IMAGE_ROUNDED,
        "jpeg": ft.Icons.IMAGE_ROUNDED,
        "svg": ft.Icons.IMAGE_ROUNDED,
        "gif": ft.Icons.IMAGE_ROUNDED,
        "pdf": ft.Icons.PICTURE_AS_PDF_ROUNDED,
        "zip": ft.Icons.FOLDER_ZIP_ROUNDED,
        "tar": ft.Icons.FOLDER_ZIP_ROUNDED,
        "gz": ft.Icons.FOLDER_ZIP_ROUNDED,
        "xz": ft.Icons.FOLDER_ZIP_ROUNDED,
        "so": ft.Icons.SETTINGS_APPLICATIONS_ROUNDED,
        "deb": ft.Icons.ARCHIVE_ROUNDED,
        "rpm": ft.Icons.ARCHIVE_ROUNDED,
    }
    return icon_map.get(ext, ft.Icons.INSERT_DRIVE_FILE_ROUNDED)


def _format_size(size_bytes: float | None) -> str:
    """Format file size to human-readable string."""
    if size_bytes is None or size_bytes == 0:
        return ""
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def build_file_item(
    item: dict,
    is_selected: bool = False,
    selection_mode: bool = False,
    on_click=None,
    on_long_press=None,
) -> ft.Container:
    """Build a file browser list item matching CollabShell's visual style."""
    name = item.get("name", "")
    is_dir = item.get("is_dir", False)
    size = item.get("size", 0)

    icon = _file_icon(name, is_dir)

    controls: list[ft.Control] = [
        ft.Icon(
            icon,
            size=tokens.ICON_LG,
            color=theme.primary() if is_dir else theme.text_dim(),
        ),
        ft.Column(
            controls=[
                ft.Text(
                    name,
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.W_500 if is_dir else ft.FontWeight.W_400,
                    color=theme.text(),
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    "Folder" if is_dir else _format_size(size),
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
            ],
            spacing=tokens.SPACE_XXS,
            expand=True,
        ),
    ]

    if selection_mode or is_selected:
        controls.append(
            ft.Icon(
                ft.Icons.CHECK_CIRCLE_ROUNDED if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
                size=tokens.ICON_MD,
                color=theme.primary() if is_selected else theme.text_dim(),
            )
        )

    return ft.Container(
        bgcolor=ft.Colors.with_opacity(0.12, theme.primary())
        if is_selected
        else ft.Colors.TRANSPARENT,
        border_radius=tokens.RADIUS_MD,
        content=ft.Row(
            controls=controls,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_MD,
        ),
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
        on_click=on_click,
        on_long_press=on_long_press,
        ink=True,
    )
