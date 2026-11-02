"""Dialogs and actions used by the container file browser."""

from __future__ import annotations

import asyncio
import os
import posixpath
import shutil
from collections.abc import Callable
from pathlib import Path

import flet as ft

from core import theme, tokens
from services import container_files_service


def preview_file(page: ft.Page, container: str, file_path: str) -> None:
    async def _read() -> None:
        try:
            data = await asyncio.to_thread(
                container_files_service.read_file_preview, container, file_path
            )
            if data["type"] == "image":
                dialog_content = ft.Image(
                    src_base64=data["base64"],
                    fit=ft.BoxFit.CONTAIN,
                    width=tokens.DIALOG_WIDTH_LG,
                )
            else:
                dialog_content = ft.TextField(
                    value=data["content"],
                    read_only=True,
                    multiline=True,
                    text_size=tokens.FONT_XS,
                    font_family=tokens.MONO_FONT,
                    height=tokens.FILE_LIST_HEIGHT,
                    border=ft.NoInputBorder(),
                )
            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(
                        posixpath.basename(file_path),
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.BOLD,
                    ),
                    content=ft.Container(content=dialog_content, width=tokens.DIALOG_WIDTH_LG),
                    actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
                )
            )
        except Exception as exc:
            from components.snack import show_snack

            show_snack(page, f"Cannot preview file: {exc}")

    page.run_task(_read)


def open_new_folder_dialog(
    page: ft.Page,
    container: str,
    current_path: str,
    load_dir: Callable[[], None],
    _e=None,
) -> None:
    folder_field = ft.TextField(
        label="Folder Name",
        hint_text="e.g. scripts",
        text_size=tokens.FONT_SM,
        autofocus=True,
    )

    def _create(_e=None) -> None:
        name = (folder_field.value or "").strip()
        if not name:
            return
        page.pop_dialog()

        async def _do_create() -> None:
            try:
                await asyncio.to_thread(
                    container_files_service.create_folder,
                    container,
                    current_path,
                    name,
                )
                load_dir()
            except Exception as exc:
                from components.snack import show_snack

                show_snack(page, f"Create folder failed: {exc}")

        page.run_task(_do_create)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("New Folder", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=folder_field,
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Create",
                    on_click=_create,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )


def open_delete_dialog(
    page: ft.Page,
    container: str,
    selected_items: set[str],
    set_selected_items: Callable[[set[str]], None],
    set_selection_mode: Callable[[bool], None],
    load_dir: Callable[[], None],
    _e=None,
) -> None:
    if not selected_items:
        return
    items_list = list(selected_items)

    def _confirm_delete(_e=None) -> None:
        page.pop_dialog()

        async def _do_delete() -> None:
            try:
                errors = await asyncio.to_thread(
                    container_files_service.delete_items, container, items_list
                )
                if errors:
                    from components.snack import show_snack

                    show_snack(page, f"Delete errors: {', '.join(errors)}")
                set_selected_items(set())
                set_selection_mode(False)
                load_dir()
            except Exception as exc:
                from components.snack import show_snack

                show_snack(page, f"Delete failed: {exc}")

        page.run_task(_do_delete)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Delete {len(items_list)} item(s)?",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Text(
                "This action permanently removes the selected files and folders from the container.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Delete",
                    on_click=_confirm_delete,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )


async def handle_upload(
    page: ft.Page,
    container: str,
    current_path: str,
    load_dir: Callable[[], None],
) -> None:
    picker = getattr(page, "file_picker", None)
    if picker is None:
        from components.snack import show_snack

        show_snack(page, "File picker is unavailable on this build")
        return
    picked = await picker.pick_files(
        dialog_title="Upload File into Container",
        allow_multiple=True,
        with_data=True,
    )
    if not picked:
        return
    for file in picked:
        try:
            if file.bytes is not None:
                await asyncio.to_thread(
                    container_files_service.write_file_bytes,
                    container,
                    current_path,
                    file.name,
                    file.bytes,
                )
            elif file.path is not None:
                await asyncio.to_thread(
                    container_files_service.copy_local_file_in,
                    container,
                    current_path,
                    file.path,
                )
        except Exception as exc:
            from components.snack import show_snack

            show_snack(page, f"Upload error: {exc}")
    load_dir()


async def handle_download(
    page: ft.Page,
    container: str,
    selected_items: set[str],
    listing: list[dict],
    set_selected_items: Callable[[set[str]], None],
    set_selection_mode: Callable[[bool], None],
) -> None:
    """Download selected files/folders — CollabShell's same-device approach:
    on mobile write straight to the Download dir with a unique name (no bytes
    round-trip, no picker); folders are zipped to a local path. A progress
    dialog (ProgressBar + status) shows while it runs."""
    if not selected_items:
        return
    from components.snack import show_snack

    mobile = bool(getattr(page, "platform", None) and page.platform.is_mobile() and not page.web)

    def _unique_local_path(default_name: str) -> Path:
        dl_dir = Path("/storage/emulated/0/Download")
        if not dl_dir.is_dir():
            dl_dir = Path.home() / "Downloads"
        dl_dir.mkdir(parents=True, exist_ok=True)
        name_part, ext_part = os.path.splitext(default_name)
        unique = default_name
        counter = 1
        while (dl_dir / unique).exists():
            unique = f"{name_part} ({counter}){ext_part}"
            counter += 1
        return dl_dir / unique

    for item_path in list(selected_items):
        base = posixpath.basename(item_path)
        meta = next((item for item in listing if item["path"] == item_path), None)
        is_dir = meta.get("is_dir", False) if meta else False
        default_name = f"{base}.zip" if is_dir else base

        if mobile:
            local_path = _unique_local_path(default_name)
        else:
            picker = getattr(page, "file_picker", None)
            if picker is None:
                show_snack(page, "File picker is unavailable on this build")
                continue
            local_path_str = await picker.save_file(
                dialog_title=f"Save {default_name}", file_name=default_name
            )
            if not local_path_str:
                continue
            local_path = Path(local_path_str)

        prog_bar = ft.ProgressBar(
            color=theme.primary(),
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
        )
        status_text = ft.Text(
            ("Zipping folder… this can take a while" if is_dir else f"Saving {default_name}…"),
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        )
        dl_dialog = ft.AlertDialog(
            title=ft.Text(f"Downloading {default_name}", size=tokens.FONT_SM),
            content=ft.Column(
                controls=[prog_bar, status_text], spacing=tokens.SPACE_SM, tight=True
            ),
        )
        page.show_dialog(dl_dialog)
        try:
            if is_dir:
                await asyncio.to_thread(
                    container_files_service.zip_folder, container, item_path, str(local_path)
                )
            else:
                _, host_file = container_files_service.resolve_guest_path(container, item_path)
                await asyncio.to_thread(shutil.copyfile, host_file, local_path)
            show_snack(page, f"Saved to {local_path}")
        except Exception as exc:
            show_snack(page, f"Download failed for {base}: {exc}")
        finally:
            try:
                page.pop_dialog()
            except Exception:
                pass

    set_selected_items(set())
    set_selection_mode(False)
