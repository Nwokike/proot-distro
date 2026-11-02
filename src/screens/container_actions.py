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
        ft.PopupMenuItem(
            icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
            content=ft.Text("Run command", size=tokens.FONT_SM),
            on_click=lambda _e: ask_run(page, methods, cname),
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
    compress = ft.Dropdown(
        options=[
            ft.dropdown.Option(c, text=t)
            for c, t in (
                ("", "from file extension"),
                ("gzip", "gzip"),
                ("bzip2", "bzip2"),
                ("xz", "xz"),
                ("zstd", "zstd (needs Python 3.14+ libzstd)"),
                ("none", "none"),
            )
        ],
        value="",
        width=tokens.DIALOG_COPY_WIDTH,
        tooltip="Force a compression (-c/--compress); default: inferred from the file name",
    )

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.backup_container, container, compress.value or None)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Backup {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(controls=[dest, compress], spacing=tokens.SPACE_XS, tight=True),
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


def ask_run(page: ft.Page, methods, container: str) -> None:
    """`proot-distro run` — Entrypoint/Cmd plus args, captured on a PTY."""
    args_field = ft.TextField(
        label="Args after -- (appended to Entrypoint, replace Cmd)",
        hint_text="e.g. -c 'echo hi'  (empty = image default)",
        text_size=tokens.FONT_SM,
        multiline=True,
        autofocus=True,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD,
            side=ft.BorderSide(1, theme.surface_alt()),
        ),
    )

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.run_container, container, args_field.value or "")
        from components.install_progress_modal import show_run_dialog

        show_run_dialog(page, container, args_field.value or "")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Run in {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=args_field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Run",
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

    use_move = ft.Checkbox(label="Move (delete source after copy)", value=False)
    use_recursive = ft.Checkbox(label="Recursive", value=True)

    def _save(_e) -> None:
        page.pop_dialog()
        page.run_task(
            methods.copy_path,
            source.value or "",
            destination.value or "",
            bool(use_move.value),
            bool(use_recursive.value),
        )

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Copy a path", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[source, destination, use_move, use_recursive],
                spacing=tokens.SPACE_XS,
                tight=True,
            ),
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
