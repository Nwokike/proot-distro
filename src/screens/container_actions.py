"""Container action dialogs shared by the distro list."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def container_menu_items(page: ft.Page, methods, cname: str) -> list[ft.PopupMenuItem]:
    return [
        ft.PopupMenuItem(
            icon=ft.Icons.EDIT_ROUNDED,
            content=ft.Text("Rename", size=tokens.FONT_SM),
            on_click=lambda _e: ask_rename(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.ARCHIVE_ROUNDED,
            content=ft.Text("Backup snapshot", size=tokens.FONT_SM),
            on_click=lambda _e: ask_backup(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.FOLDER_COPY_ROUNDED,
            content=ft.Text("Copy a path", size=tokens.FONT_SM),
            on_click=lambda _e: ask_copy(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.SYNC_ROUNDED,
            content=ft.Text("Sync folder", size=tokens.FONT_SM),
            on_click=lambda _e: ask_sync(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            content=ft.Text("Browse files", size=tokens.FONT_SM),
            on_click=lambda _e: browse_files(page, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.INFO_OUTLINE_ROUNDED,
            content=ft.Text("Inspect container", size=tokens.FONT_SM),
            on_click=lambda _e: page.run_task(methods.inspect_container, cname),
        ),
    ]


def browse_files(page: ft.Page, container: str) -> None:
    from screens.files.modal import show_manage_files_modal

    show_manage_files_modal(page, container)


def ask_rename(page: ft.Page, methods, container: str) -> None:
    new_name = ft.TextField(
        label="New name",
        value=container,
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.rename_container, container, new_name.value or "")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Rename {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=new_name,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Rename",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )


def ask_backup(page: ft.Page, methods, container: str) -> None:
    dest = ft.TextField(
        label="Archive name",
        value=f"{container}-backup.tar.gz",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.backup_container, container, dest.value or "")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Backup {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=dest,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Backup",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )


def ask_copy(page: ft.Page, methods, container: str) -> None:
    source = ft.TextField(
        hint_text="source (container:/path)",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )
    destination = ft.TextField(
        hint_text="destination (container:/path)",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.copy_path, source.value or "", destination.value or "")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Copy a path", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(controls=[source, destination], spacing=tokens.SPACE_XS, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Copy",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )


def ask_sync(page: ft.Page, methods, container: str) -> None:
    source = ft.TextField(
        hint_text="source folder (host or container:/path)",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )
    dest = ft.TextField(
        hint_text="destination folder",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )
    use_checksum = ft.Checkbox(label="Verify with checksums", value=False)
    prune_dest = ft.Checkbox(label="Prune files deleted in source", value=False)

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(
            methods.sync_path,
            source.value or "",
            dest.value or "",
            bool(use_checksum.value),
            bool(prune_dest.value),
        )

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Sync Directory", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[source, dest, use_checksum, prune_dest],
                spacing=tokens.SPACE_XS,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Sync",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )
