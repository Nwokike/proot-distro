"""FilesView — Modular container filesystem explorer matching CollabShell.

Browse, select, upload, download, delete, create folders, and preview files
within any installed container's filesystem.
"""

from __future__ import annotations

import asyncio
import logging
import posixpath
from pathlib import Path

import flet as ft

from components import card, empty_state, section_header
from components.file_item import build_file_item
from core import theme, tokens
from core.state import state
from screens.files.components import (
    build_breadcrumbs,
    build_empty_dir_view,
    parent_path,
)
from services import container_files_service

logger = logging.getLogger(__name__)


@ft.component
def FilesView(
    default_container: str | None = None,
    default_path: str = "/root",
) -> ft.Control:
    """Container filesystem explorer matching CollabShell's FilesScreen.

    Like the Terminal tab: no container is pre-opened. The screen first shows
    the installed containers to pick from; only after a pick does the browser
    open (with a back button returning to the picker).
    """
    page = ft.context.page
    _st, _ = ft.use_state(state)

    # Installed containers
    installed = [row.get("name", "") for row in (state.containers or []) if row.get("name")]
    selected_container, set_selected_container = ft.use_state(default_container or "")
    current_path, set_current_path = ft.use_state(default_path)
    listing, set_listing = ft.use_state([])
    selected_items, set_selected_items = ft.use_state(set())
    selection_mode, set_selection_mode = ft.use_state(False)
    is_loading, set_is_loading = ft.use_state(False)
    error_msg, set_error_msg = ft.use_state("")

    def _load_dir(target_dir: str | None = None) -> None:
        target = target_dir or current_path
        if not selected_container:
            set_listing([])
            return
        set_is_loading(True)
        set_error_msg("")

        def _scan() -> list[dict]:
            # If default path /root does not exist, fall back to /
            try:
                return container_files_service.list_container_dir(selected_container, target)
            except Exception:
                if target != "/":
                    return container_files_service.list_container_dir(selected_container, "/")
                raise

        async def _do_scan() -> None:
            try:
                items = await asyncio.to_thread(_scan)
                set_listing(items)
                set_current_path(target)
            except Exception as exc:
                logger.warning("Directory scan failed: %s", exc)
                set_error_msg(f"Could not open {target}: {exc}")
                set_listing([])
            finally:
                set_is_loading(False)

        page.run_task(_do_scan)

    ft.use_effect(lambda: _load_dir(current_path), [selected_container])

    def _navigate(subpath: str) -> None:
        set_selected_items(set())
        set_selection_mode(False)
        _load_dir(subpath)

    def _go_up(_e=None) -> None:
        p = parent_path(current_path)
        if p is not None:
            _navigate(p)

    def _toggle_select(item_path: str) -> None:
        new_sel = set(selected_items)
        if item_path in new_sel:
            new_sel.remove(item_path)
        else:
            new_sel.add(item_path)
        set_selected_items(new_sel)
        if not new_sel:
            set_selection_mode(False)
        else:
            set_selection_mode(True)

    def _preview_file(file_path: str) -> None:
        async def _read() -> None:
            try:
                data = await asyncio.to_thread(
                    container_files_service.read_preview, selected_container, file_path
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
                        font_family="JetBrains Mono",
                        height=320,
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

    def _open_new_folder_dialog(_e=None) -> None:
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
                        selected_container,
                        current_path,
                        name,
                    )
                    _load_dir()
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

    def _open_delete_dialog(_e=None) -> None:
        if not selected_items:
            return
        items_list = list(selected_items)

        def _confirm_delete(_e=None) -> None:
            page.pop_dialog()

            async def _do_del() -> None:
                try:
                    errors = await asyncio.to_thread(
                        container_files_service.delete_items, selected_container, items_list
                    )
                    if errors:
                        from components.snack import show_snack

                        show_snack(page, f"Delete errors: {', '.join(errors)}")
                    set_selected_items(set())
                    set_selection_mode(False)
                    _load_dir()
                except Exception as exc:
                    from components.snack import show_snack

                    show_snack(page, f"Delete failed: {exc}")

            page.run_task(_do_del)

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

    async def _handle_upload(_e=None) -> None:
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
        for f in picked:
            try:
                if f.bytes is not None:
                    await asyncio.to_thread(
                        container_files_service.write_file_bytes,
                        selected_container,
                        current_path,
                        f.name,
                        f.bytes,
                    )
                elif f.path is not None:
                    await asyncio.to_thread(
                        container_files_service.copy_local_file_in,
                        selected_container,
                        current_path,
                        f.path,
                    )
            except Exception as exc:
                from components.snack import show_snack

                show_snack(page, f"Upload error: {exc}")
        _load_dir()

    async def _handle_download(_e=None) -> None:
        if not selected_items:
            return
        picker = getattr(page, "file_picker", None)
        items_to_download = list(selected_items)

        for item_path in items_to_download:
            base = posixpath.basename(item_path)
            # Find item meta in listing
            meta = next((x for x in listing if x["path"] == item_path), None)
            is_dir = meta.get("is_dir", False) if meta else False

            try:
                if is_dir:
                    zip_name = f"{base}.zip"
                    # Zip directory into temp staging first
                    from core import storage_paths

                    staging = storage_paths.temp_root() / zip_name
                    await asyncio.to_thread(
                        container_files_service.zip_folder,
                        selected_container,
                        item_path,
                        str(staging),
                    )
                    data_bytes = staging.read_bytes()
                    file_save_name = zip_name
                else:
                    _, host_file = container_files_service.resolve_guest_path(
                        selected_container, item_path
                    )
                    data_bytes = host_file.read_bytes()
                    file_save_name = base

                if picker is not None:
                    target = await picker.save_file(
                        dialog_title=f"Save {file_save_name}",
                        file_name=file_save_name,
                        src_bytes=data_bytes,
                    )
                    from components.snack import show_snack

                    if target:
                        show_snack(page, f"Saved {file_save_name} to {target}")
                else:
                    # Mobile fallback write to Download directory
                    dest_dir = Path("/storage/emulated/0/Download")
                    if not dest_dir.is_dir():
                        dest_dir = Path.home() / "Downloads"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    out = dest_dir / file_save_name
                    out.write_bytes(data_bytes)
                    from components.snack import show_snack

                    show_snack(page, f"Downloaded to {out}")
            except Exception as exc:
                from components.snack import show_snack

                show_snack(page, f"Download failed for {base}: {exc}")

        set_selected_items(set())
        set_selection_mode(False)

    if not installed:
        return ft.Column(
            controls=[
                empty_state(
                    "No containers installed",
                    "Install a container first to explore and manage its files.",
                    icon=ft.Icons.FOLDER_OFF_ROUNDED,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    # No container open yet — the picker, mirroring the Terminal tab: each
    # installed container is a card you select to open its filesystem.
    if not selected_container:
        picker_rows = []
        for c in installed:
            row_meta = next((r for r in (state.containers or []) if r.get("name") == c), {})

            def _open(_e, name=c) -> None:
                set_selected_items(set())
                set_selection_mode(False)
                set_selected_container(name)
                set_current_path(default_path)

            picker_rows.append(
                card(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.FOLDER_ROUNDED,
                                    size=tokens.ICON_MD,
                                    color=theme.primary(),
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            c,
                                            size=tokens.FONT_LG,
                                            weight=ft.FontWeight.W_600,
                                            color=theme.text(),
                                        ),
                                        ft.Text(
                                            f"{row_meta.get('image', '')} · "
                                            f"{row_meta.get('arch', '')}".strip(" ·"),
                                            size=tokens.FONT_XS,
                                            color=theme.text_dim(),
                                        ),
                                    ],
                                    spacing=tokens.SPACE_XXS,
                                    expand=True,
                                ),
                                ft.Icon(
                                    ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                    size=tokens.ICON_MD,
                                    color=theme.text_dim(),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=tokens.SPACE_SM,
                        ),
                        on_click=_open,
                        ink=True,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
        return ft.Column(
            controls=[
                section_header("Browse a container"),
                *picker_rows,
            ],
            spacing=tokens.SPACE_SM,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    # 1. Top container switcher chips
    container_chips = []
    for c in installed:
        is_sel = c == selected_container
        container_chips.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.APPS_ROUNDED,
                            size=tokens.ICON_XS,
                            color=theme.primary() if is_sel else theme.text_dim(),
                        ),
                        ft.Text(
                            c,
                            size=tokens.FONT_SM,
                            color=theme.primary() if is_sel else theme.text(),
                            weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.W_400,
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
                padding=ft.Padding(
                    tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS
                ),
                border_radius=tokens.RADIUS_PILL,
                bgcolor=ft.Colors.with_opacity(0.12, theme.primary())
                if is_sel
                else theme.surface(),
                border=ft.Border.all(1, theme.primary() if is_sel else theme.surface_alt()),
                ink=True,
                on_click=lambda _e, name=c: set_selected_container(name),
            )
        )

    # 2. Browser header: back to the container picker, container chips, then
    # the breadcrumb row (up button + path crumbs).
    nav_row = ft.Row(
        controls=[
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK_ROUNDED,
                icon_size=tokens.ICON_SM,
                tooltip="All containers",
                on_click=lambda _e: set_selected_container(""),
            ),
            ft.IconButton(
                icon=ft.Icons.ARROW_UPWARD_ROUNDED,
                icon_size=tokens.ICON_SM,
                tooltip="Go Up One Directory",
                disabled=parent_path(current_path) is None,
                on_click=_go_up,
            ),
            ft.Container(
                content=build_breadcrumbs(current_path, _navigate),
                expand=True,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
    )

    # 3. Actions Toolbar
    if selection_mode:
        action_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Text(
                        f"{len(selected_items)} selected",
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600,
                        color=theme.primary(),
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Download Selected",
                        on_click=lambda _e: page.run_task(_handle_download),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        icon_color=theme.warn(),
                        tooltip="Delete Selected",
                        on_click=_open_delete_dialog,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Cancel Selection",
                        on_click=lambda _e: (set_selected_items(set()), set_selection_mode(False)),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.08, theme.primary()),
            border_radius=tokens.RADIUS_MD,
            padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
        )
    else:
        action_bar = ft.Container(
            content=ft.Row(
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.CREATE_NEW_FOLDER_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="New Folder",
                        on_click=_open_new_folder_dialog,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Upload File",
                        on_click=lambda _e: page.run_task(_handle_upload),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHECKLIST_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Select Items",
                        on_click=lambda _e: set_selection_mode(True),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Refresh Directory",
                        on_click=lambda _e: _load_dir(),
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            padding=ft.Padding(0, 0, tokens.SPACE_SM, 0),
        )

    # 4. Files List
    if is_loading:
        file_list_content = ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(width=24, height=24),
                    ft.Text("Scanning directory…", size=tokens.FONT_SM, color=theme.text_dim()),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=tokens.SPACE_MD,
            ),
            padding=tokens.SPACE_XXL,
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
    elif error_msg:
        file_list_content = ft.Container(
            content=ft.Text(error_msg, size=tokens.FONT_SM, color=theme.warn()),
            padding=tokens.SPACE_LG,
            alignment=ft.Alignment.CENTER,
        )
    elif not listing:
        file_list_content = build_empty_dir_view(lambda _e: page.run_task(_handle_upload))
    else:
        file_items = []
        for item in listing:
            item_path = item["path"]
            is_sel = item_path in selected_items

            def _click(e=None, i=item):
                if selection_mode:
                    _toggle_select(i["path"])
                elif i["is_dir"]:
                    _navigate(i["path"])
                else:
                    _preview_file(i["path"])

            file_items.append(
                build_file_item(
                    item=item,
                    is_selected=is_sel,
                    selection_mode=selection_mode,
                    on_click=_click,
                    on_long_press=lambda _e, p=item_path: _toggle_select(p),
                )
            )
        file_list_content = ft.ListView(
            controls=file_items,
            spacing=tokens.SPACE_XXS,
            height=340,
        )

    return ft.Column(
        controls=[
            ft.Row(controls=container_chips, scroll=ft.ScrollMode.AUTO, spacing=tokens.SPACE_SM),
            nav_row,
            action_bar,
            ft.Divider(height=1, color=theme.glass_border()),
            card(file_list_content, padding=tokens.SPACE_SM),
        ],
        spacing=tokens.SPACE_SM,
        scroll=ft.ScrollMode.AUTO,
    )
