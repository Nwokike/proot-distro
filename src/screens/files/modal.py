"""Manage Files Modal Dialog — standalone container file browser dialog with live actions.

Ported from CollabShell's screens/files/modal.py pattern: an imperative
AlertDialog with internal `_render()` and `dlg.update()`, so it never needs an
active @ft.component renderer context and can be called safely from any event handler.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components.file_item import build_file_item
from core import theme, tokens
from screens.files.components import (
    build_breadcrumbs,
    build_empty_dir_view,
    parent_path,
)
from screens.files.operations import (
    handle_download,
    handle_upload,
    open_delete_dialog,
    open_new_folder_dialog,
    preview_file,
)
from services import container_files_service

logger = logging.getLogger("ManageFilesModal")


def show_manage_files_modal(page: ft.Page, container: str, initial_path: str = "/root") -> None:
    """Opens a standalone modal dialog for container file management."""
    if not page or not container:
        return

    current_path = initial_path
    listing: list[dict] = []
    selected_files: set[str] = set()
    is_loading = False
    selection_mode = False

    breadcrumb_container = ft.Container(expand=True)
    action_row = ft.Row(spacing=tokens.SPACE_XS)
    list_container = ft.Container(
        content=ft.ProgressRing(),
        alignment=ft.Alignment.CENTER,
        expand=True,
    )

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.FOLDER_ROUNDED, color=theme.primary()),
                ft.Text(
                    f"Files — {container}",
                    weight=ft.FontWeight.W_600,
                    size=tokens.FONT_LG,
                    color=theme.text(),
                ),
            ],
            spacing=tokens.SPACE_SM,
        ),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[breadcrumb_container],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(
                            tokens.SPACE_SM,
                            tokens.SPACE_NONE,
                            tokens.SPACE_SM,
                            tokens.SPACE_NONE,
                        ),
                    ),
                    ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
                    list_container,
                ],
                spacing=tokens.SPACE_XS,
                expand=True,
            ),
            width=tokens.DIALOG_WIDTH_LG + 120,
            height=tokens.FILE_MODAL_HEIGHT,
        ),
        actions=[
            ft.Row(
                controls=[
                    action_row,
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Close",
                        on_click=lambda _: page.pop_dialog(),
                    ),
                ],
                spacing=tokens.SPACE_SM,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.START,
    )

    def _render():
        nonlocal selection_mode
        up_target = parent_path(current_path)
        breadcrumb_container.content = ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_UPWARD_ROUNDED,
                    tooltip="Go up",
                    icon_size=tokens.ICON_SM,
                    disabled=up_target is None,
                    on_click=(None if up_target is None else lambda _: _on_navigate(up_target)),
                ),
                ft.Container(
                    content=build_breadcrumbs(current_path, on_navigate=_on_navigate),
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_NONE,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        n_sel = len(selected_files)
        actions: list[ft.Control] = []

        if selection_mode:
            has_sel = n_sel > 0
            actions.append(
                ft.Container(
                    content=ft.Text(
                        f"{n_sel} sel" if has_sel else "Tap to select",
                        size=tokens.FONT_XS,
                        weight=ft.FontWeight.W_600,
                        color=theme.primary() if has_sel else theme.text_dim(),
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_XS,
                        tokens.SPACE_NONE,
                        tokens.SPACE_XS,
                        tokens.SPACE_NONE,
                    ),
                )
            )
            actions.extend(
                [
                    ft.IconButton(
                        icon=ft.Icons.DOWNLOAD_ROUNDED,
                        tooltip="Download",
                        icon_size=tokens.ICON_SM,
                        disabled=not has_sel,
                        on_click=(
                            None
                            if not has_sel
                            else lambda _: page.run_task(
                                handle_download,
                                page,
                                container,
                                selected_files,
                                listing,
                                _set_selected,
                                _set_selection_mode,
                            )
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_ROUNDED,
                        tooltip="Delete",
                        icon_size=tokens.ICON_SM,
                        icon_color=theme.warn() if has_sel else theme.text_dim(),
                        disabled=not has_sel,
                        on_click=(
                            None
                            if not has_sel
                            else lambda e: open_delete_dialog(
                                page,
                                container,
                                selected_files,
                                _set_selected,
                                _set_selection_mode,
                                lambda: _fetch_listing(current_path),
                                e,
                            )
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        tooltip="Cancel selection",
                        icon_size=tokens.ICON_SM,
                        on_click=lambda _: _clear_selection(),
                    ),
                ]
            )
        else:
            actions.extend(
                [
                    ft.IconButton(
                        icon=ft.Icons.CHECKLIST_ROUNDED,
                        tooltip="Select",
                        icon_size=tokens.ICON_SM,
                        on_click=lambda _: _enter_selection_mode(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                        tooltip="Upload",
                        icon_size=tokens.ICON_SM,
                        on_click=lambda _: page.run_task(
                            handle_upload,
                            page,
                            container,
                            current_path,
                            lambda: _fetch_listing(current_path),
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CREATE_NEW_FOLDER_ROUNDED,
                        tooltip="New folder",
                        icon_size=tokens.ICON_SM,
                        on_click=lambda e: open_new_folder_dialog(
                            page,
                            container,
                            current_path,
                            lambda: _fetch_listing(current_path),
                            e,
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        tooltip="Refresh",
                        icon_size=tokens.ICON_SM,
                        on_click=lambda _: _fetch_listing(current_path),
                    ),
                ]
            )

        action_row.controls = actions

        if is_loading:
            list_container.content = ft.Container(
                content=ft.ProgressRing(),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        elif not listing:
            list_container.content = build_empty_dir_view(
                lambda _: page.run_task(
                    handle_upload,
                    page,
                    container,
                    current_path,
                    lambda: _fetch_listing(current_path),
                )
            )
        else:
            list_container.content = ft.ListView(
                controls=[
                    build_file_item(
                        item=item,
                        is_selected=(item["path"] in selected_files),
                        selection_mode=selection_mode,
                        on_click=lambda _e, i=item: _on_item_click(i),
                        on_long_press=lambda _e, p=item["path"]: _toggle_select(p),
                    )
                    for item in listing
                ],
                expand=True,
                spacing=tokens.SPACE_XXS,
                padding=ft.Padding(
                    tokens.SPACE_SM,
                    tokens.SPACE_NONE,
                    tokens.SPACE_SM,
                    tokens.SPACE_SM,
                ),
            )

        try:
            dlg.update()
        except Exception:
            logger.debug("Modal render dialog update suppressed")

    def _set_selected(new_sel: set[str]):
        nonlocal selected_files
        selected_files = set(new_sel)
        _render()

    def _set_selection_mode(val: bool):
        nonlocal selection_mode
        selection_mode = val
        _render()

    def _clear_selection():
        nonlocal selection_mode
        selected_files.clear()
        selection_mode = False
        _render()

    def _enter_selection_mode():
        nonlocal selection_mode
        selection_mode = True
        _render()

    def _toggle_select(item_path: str):
        nonlocal selection_mode
        if item_path in selected_files:
            selected_files.remove(item_path)
            if not selected_files:
                _clear_selection()
                return
        else:
            selected_files.add(item_path)
            # Long-press enters selection mode too — same as pressing Select
            # then tapping the item: the selection action bar must appear.
            selection_mode = True
        _render()

    def _on_navigate(path: str):
        _fetch_listing(path)

    def _on_item_click(item: dict):
        nonlocal selection_mode
        if selection_mode:
            _toggle_select(item["path"])
        elif item.get("is_dir"):
            _on_navigate(item["path"])
        else:
            preview_file(page, container, item["path"])

    def _fetch_listing(target_dir: str):
        nonlocal is_loading, listing, current_path
        current_path = target_dir
        is_loading = True
        _render()

        def _scan():
            try:
                return container_files_service.list_container_dir(container, target_dir)
            except Exception as exc:
                # Log the real error before falling back — otherwise a
                # permissions bug looks like an empty root.
                logger.warning(
                    "list %s in %s failed (%r) — falling back to /", target_dir, container, exc
                )
                if target_dir != "/":
                    return container_files_service.list_container_dir(container, "/")
                return []

        async def _do():
            nonlocal is_loading, listing
            try:
                items = await asyncio.to_thread(_scan)
                listing = items
                selected_files.clear()
            except Exception as exc:
                logger.warning("Modal listing scan failed: %s", exc)
                listing = []
            finally:
                is_loading = False
                _render()

        page.run_task(_do)

    page.show_dialog(dlg)
    _fetch_listing(current_path)
