"""Backup and run dialogs."""

from __future__ import annotations

import flet as ft

from components.ui import house_field
from core import tokens


def ask_backup(page: ft.Page, methods, container: str) -> None:
    dest = house_field(
        label="Archive name",
        value=f"{container}-backup.tar.gz",
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
        page.run_task(
            methods.backup_container, container, compress.value or None, dest.value or None
        )

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
    args_field = house_field(
        label="Args after -- (appended to Entrypoint, replace Cmd)",
        hint="e.g. -c 'echo hi'  (empty = image default)",
        multiline=True,
        autofocus=True,
    )

    user_field = house_field(label="User (empty = image default)")
    workdir_field = house_field(label="Working directory (empty = image default)")
    env_field = house_field(
        label="Environment (one KEY=VALUE per line)",
        multiline=True,
        min_lines=2,
    )

    def _save(_e) -> None:
        page.pop_dialog()
        options: dict = {}
        if user_field.value and user_field.value.strip():
            options["user"] = user_field.value.strip()
        if workdir_field.value and workdir_field.value.strip():
            options["work_dir"] = workdir_field.value.strip()
        env_lines = [ln.strip() for ln in (env_field.value or "").splitlines() if ln.strip()]
        if env_lines:
            options["env"] = env_lines
        page.run_task(methods.run_container, container, args_field.value or "", options or None)
        from components.install_progress_modal import show_run_dialog

        show_run_dialog(page, container, args_field.value or "")

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(f"Run in {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[
                    args_field,
                    ft.ExpansionTile(
                        title=ft.Text("Advanced run options", size=tokens.FONT_SM),
                        expanded=False,
                        controls=[user_field, workdir_field, env_field],
                    ),
                ],
                spacing=tokens.SPACE_XS,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
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
