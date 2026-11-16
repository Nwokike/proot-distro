"""Destructive confirmations (reset/remove/restore/rename)."""

from __future__ import annotations

import flet as ft

from components.ui import house_field
from core import theme, tokens


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
        # The image this container came from — read BEFORE removal, then drop
        # its cached manifest/blobs. The old flow ran clear-cache --orphan,
        # which KEEPS every blob a cached image references, so the checkbox
        # was inert (device audit 2026-11-14).
        from core.state import state as _state

        image_ref = next(
            (
                str(row.get("image") or "")
                for row in (_state.containers or [])
                if row.get("name") == container
            ),
            "",
        )

        async def _do_remove() -> None:
            await methods.remove_container(container)
            if should_clean and image_ref:
                await methods.remove_cached_image(image_ref)

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


def _confirm_restore(page: ft.Page, methods) -> None:
    """A restore REPLACES the container's filesystem with the archive's.

    Upstream's restore destroys the target rootfs before extracting, so this
    is a destructive action that needs an explicit confirmation."""

    def _choose(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.restore_container)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Restore a backup?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                "Restoring replaces the container's filesystem with the archive's. "
                "Everything currently in the container is lost.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton("Choose archive…", on_click=_choose),
            ],
        )
    )


def ask_rename(page: ft.Page, methods, container: str) -> None:
    new_name = house_field(label="New name", value=container)

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


def browse_files(page: ft.Page, container: str) -> None:
    from screens.files.modal import show_manage_files_modal

    show_manage_files_modal(page, container)
