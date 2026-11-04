"""Container action dialogs shared by the distro list."""

from __future__ import annotations

import flet as ft

from core import theme, tokens


def container_menu_items(page: ft.Page, methods, cname: str) -> list[ft.PopupMenuItem]:
    """Grouped container menu: info/actions first, then a separator, and the
    destructive pair last (warn-colored) so accidents don't sit next to
    everyday actions."""
    return [
        ft.PopupMenuItem(
            icon=ft.Icons.TERMINAL_ROUNDED,
            content=ft.Text("Shell with options…", size=tokens.FONT_SM),
            on_click=lambda _e: ask_shell_options(page, methods, cname),
        ),
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
        ft.PopupMenuItem(content=ft.Divider(height=1)),
        ft.PopupMenuItem(
            icon=ft.Icons.RESTART_ALT_ROUNDED,
            icon_color=theme.warn(),
            content=ft.Text("Reset", size=tokens.FONT_SM, color=theme.warn()),
            on_click=lambda _e: ask_reset(page, methods, cname),
        ),
        ft.PopupMenuItem(
            icon=ft.Icons.DELETE_FOREVER_ROUNDED,
            icon_color=theme.warn(),
            content=ft.Text("Remove", size=tokens.FONT_SM, color=theme.warn()),
            on_click=lambda _e: ask_remove(page, methods, cname),
        ),
    ]


def ask_reset(page: ft.Page, methods, container: str) -> None:
    def _yes(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.reset_container, container)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Reset {container}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                "Container files are wiped back to the clean base image.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Reset",
                    on_click=_yes,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )


def ask_remove(page: ft.Page, methods, container: str) -> None:
    clean_cache_cb = ft.Checkbox(
        label="Also remove cached download layers",
        value=True,
    )

    def _yes(_e) -> None:
        page.pop_dialog()
        should_clean = bool(clean_cache_cb.value)

        async def _do_remove() -> None:
            await methods.remove_container(container)
            if should_clean:
                await methods.clear_orphan_layers()

        page.run_task(_do_remove)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Remove {container}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Are you sure? This permanently deletes all files in this container.",
                        size=tokens.FONT_SM,
                    ),
                    clean_cache_cb,
                ],
                tight=True,
                spacing=tokens.SPACE_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Remove",
                    on_click=_yes,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )


def ask_shell_options(page: ft.Page, methods, container: str) -> None:
    """The upstream login options we wrap one-to-one (user/work-dir/env/bind/
    shared homes/tmp, low-port fixing, isolated mode) — opened from the menu;
    the card keeps exactly three inline items."""
    user = ft.TextField(
        label="User (-u)",
        value="root",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    work_dir = ft.TextField(
        label="Work dir (-w)",
        hint_text="/root",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    env = ft.TextField(
        label="Env (-e VAR=VALUE)",
        hint_text="one per line",
        text_size=tokens.FONT_SM,
        multiline=True,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    bind = ft.TextField(
        label="Bind (-b PATH[:PATH])",
        hint_text="one per line",
        text_size=tokens.FONT_SM,
        multiline=True,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    shared_tmp = ft.Switch(label="Shared tmp (--shared-tmp)", value=False)
    shared_home = ft.Switch(label="Shared home (--shared-home)", value=False)
    fix_low_ports = ft.Switch(label="Fix low ports (--fix-low-ports)", value=False)
    isolated = ft.Switch(label="Isolated (--isolated)", value=False)

    def _lines(field: ft.TextField) -> list[str]:
        return [ln.strip() for ln in (field.value or "").splitlines() if ln.strip()]

    def _save(_e) -> None:
        page.pop_dialog()
        opts = {
            "user": (user.value or "").strip() or "root",
            "work_dir": (work_dir.value or "").strip() or None,
            "env": _lines(env),
            "bind": _lines(bind),
            "shared_tmp": bool(shared_tmp.value),
            "shared_home": bool(shared_home.value),
            "fix_low_ports": bool(fix_low_ports.value),
            "isolated": bool(isolated.value),
        }
        page.run_task(methods.open_session_with_options, container, opts)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Shell options — {container}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=[
                    user,
                    work_dir,
                    env,
                    bind,
                    shared_tmp,
                    shared_home,
                    fix_low_ports,
                    isolated,
                ],
                tight=True,
                spacing=tokens.SPACE_XS,
                scroll=ft.ScrollMode.AUTO,
                width=tokens.DIALOG_WIDTH,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Open shell",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )


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
