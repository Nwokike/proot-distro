"""Dialogs and actions used by the container file browser."""

from __future__ import annotations

import asyncio
import os
import posixpath
import shutil
from collections.abc import Callable
from pathlib import Path

import flet as ft

from components.ui import house_field
from core import theme, tokens
from services import container_files_service


async def handle_paste_image(page: ft.Page, container: str, guest_dir: str, refresh) -> None:
    """Paste a clipboard IMAGE into the container as a PNG file.

    `Clipboard.get_image()` is Flet's Android/iOS/web API; bytes go straight to
    the files service (no base64 round-trip)."""
    import time

    from components.snack import show_snack

    clipboard = getattr(page, "clipboard", None)
    if clipboard is None:
        return
    try:
        data = await clipboard.get_image()
    except Exception as exc:
        show_snack(page, f"clipboard image unavailable: {exc}")
        return
    if not data:
        show_snack(page, "the clipboard has no image")
        return
    name = f"clipboard-{int(time.time())}.png"
    try:
        await asyncio.to_thread(
            container_files_service.write_file_bytes, container, guest_dir, name, data
        )
    except Exception as exc:
        show_snack(page, f"could not save the image: {exc}")
        return
    show_snack(page, f"pasted {name}")
    refresh()


def preview_file(page: ft.Page, container: str, file_path: str, methods=None) -> None:
    async def _read() -> None:
        try:
            data = await asyncio.to_thread(
                container_files_service.read_file_preview, container, file_path
            )
            if data["type"] == "image":
                dialog_content = ft.Image(
                    src=data["base64"],
                    fit=ft.BoxFit.CONTAIN,
                    width=tokens.DIALOG_WIDTH_LG,
                )
            else:
                dialog_content = ft.TextField(
                    value=data["content"],
                    read_only=True,
                    multiline=True,
                    text_size=tokens.FONT_XS,
                    text_style=ft.TextStyle(size=tokens.FONT_XS, font_family=tokens.MONO_FONT),
                    height=tokens.FILE_LIST_HEIGHT,
                    border=ft.NoInputBorder(),
                )

            actions = [ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())]

            # Run-in-display affordance for non-directory files (owner ruling
            # 2026-11-16): pre-fill `./<name>` and let the user edit the command.
            name = posixpath.basename(file_path)
            run_cmd = house_field(
                label="Run command",
                hint=f"./{name}",
                value=f"./{name}",
                expand=True,
                dense=True,
                text_size=tokens.FONT_XS,
            )

            def _run_in_display(_e) -> None:
                cmd = (run_cmd.value or "").strip()
                if not cmd:
                    return
                page.pop_dialog()
                controller = getattr(page, "_controller", None)
                if controller is not None:
                    page.run_task(controller.start_display, container, None, cmd, None, None)

            def _run_in_terminal(_e) -> None:
                cmd = (run_cmd.value or "").strip()
                if not cmd:
                    return
                page.pop_dialog()
                controller = getattr(page, "_controller", None)
                if controller is not None:
                    page.run_task(controller.open_session, container)

                    # Write the command into the shell after a short delay.
                    async def _write():
                        import asyncio as _a

                        await _a.sleep(1.5)
                        entry = controller.session_manager.entries.get(container)
                        if entry is not None and entry.session is not None:
                            entry.session.write(f"{cmd}\n".encode())

                    page.run_task(_write)

            actions.append(
                ft.FilledButton(
                    "Run in display",
                    icon=ft.Icons.PLAY_CIRCLE_ROUNDED,
                    on_click=_run_in_display,
                )
            )
            actions.append(
                ft.OutlinedButton(
                    "Run in terminal",
                    icon=ft.Icons.TERMINAL_ROUNDED,
                    on_click=_run_in_terminal,
                )
            )

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(
                        name,
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.BOLD,
                    ),
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                dialog_content,
                                run_cmd,
                            ],
                            spacing=tokens.SPACE_SM,
                            tight=True,
                        ),
                        width=tokens.DIALOG_WIDTH_LG,
                    ),
                    actions=actions,
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
    folder_field = house_field(label="Folder Name", hint="e.g. scripts", autofocus=True)

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


async def _remove_later(path: Path, delay: float = 30.0) -> None:
    """Delete a staged export after the hand-off; a no-op if it is gone."""
    import asyncio

    try:
        await asyncio.sleep(delay)
        path.unlink(missing_ok=True)
    except OSError:
        pass


async def handle_download(
    page: ft.Page,
    container: str,
    selected_items: set[str],
    listing: list[dict],
    set_selected_items: Callable[[set[str]], None],
    set_selection_mode: Callable[[bool], None],
) -> None:
    """Download selected files/folders to a staged path, then hand them over.

    Writing to /storage/emulated/0/Download needs a storage permission this app
    does not request (the write just failed), so on mobile the export is staged
    in app storage and offered through the system share sheet — no permission,
    and the user picks the real destination. Folders are zipped first. A
    progress dialog (ProgressBar + status) shows while it runs."""
    if not selected_items:
        return
    from components.snack import show_snack

    mobile = bool(getattr(page, "platform", None) and page.platform.is_mobile() and not page.web)

    def _unique_local_path(default_name: str) -> Path:
        if mobile:
            from core import storage_paths

            dl_dir = storage_paths.exports_root()
        else:
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
            if mobile:
                share = getattr(page, "share", None)
                if share is not None:
                    try:
                        await share.share_files(
                            [ft.ShareFile.from_path(str(local_path))],
                            title=f"{container}: {default_name}",
                        )
                        show_snack(page, "ready: choose where to save it")
                        # The staged copy has done its job; remove it after the
                        # receiving app has had time to read it (no more orphan
                        # exports sitting in temp until the 24h sweep).
                        page.run_task(_remove_later, local_path)
                    except Exception as exc:
                        show_snack(page, f"export staged at {local_path} ({exc})")
                else:
                    show_snack(page, f"export staged at {local_path}")
            else:
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
