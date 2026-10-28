"""FilesView — Modular container filesystem explorer matching CollabShell.

Browse, select, upload, download, delete, create folders, and preview files
within any installed container's filesystem.
"""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from components import card, no_containers_empty_state, section_header
from components.banner_ad import pooled_banner_ad
from components.file_item import build_file_item
from core import theme, tokens
from core.state import state
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

    if not installed:
        return ft.Column(
            controls=[
                no_containers_empty_state(),
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
                bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary())
                if is_sel
                else theme.surface(),
                border=ft.Border.all(
                    tokens.HAIRLINE, theme.primary() if is_sel else theme.surface_alt()
                ),
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
        spacing=tokens.SPACE_NONE,
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
                        on_click=lambda _e: page.run_task(
                            handle_download,
                            page,
                            selected_container,
                            selected_items,
                            listing,
                            set_selected_items,
                            set_selection_mode,
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        icon_color=theme.warn(),
                        tooltip="Delete Selected",
                        on_click=lambda e: open_delete_dialog(
                            page,
                            selected_container,
                            selected_items,
                            set_selected_items,
                            set_selection_mode,
                            _load_dir,
                            e,
                        ),
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
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.primary()),
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
                        on_click=lambda e: open_new_folder_dialog(
                            page, selected_container, current_path, _load_dir, e
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                        icon_size=tokens.ICON_MD,
                        tooltip="Upload File",
                        on_click=lambda _e: page.run_task(
                            handle_upload, page, selected_container, current_path, _load_dir
                        ),
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
            padding=ft.Padding(
                tokens.SPACE_NONE, tokens.SPACE_NONE, tokens.SPACE_SM, tokens.SPACE_NONE
            ),
        )

    # 4. Files List
    if is_loading:
        file_list_content = ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(width=tokens.PROGRESS_RING_LG, height=tokens.PROGRESS_RING_LG),
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
        file_list_content = build_empty_dir_view(
            lambda _e: page.run_task(
                handle_upload, page, selected_container, current_path, _load_dir
            )
        )
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
                    preview_file(page, selected_container, i["path"])

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
            expand=True,
        )

    return ft.Column(
        controls=[
            ft.Row(controls=container_chips, scroll=ft.ScrollMode.AUTO, spacing=tokens.SPACE_SM),
            pooled_banner_ad("files-1", page),
            nav_row,
            action_bar,
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            card(file_list_content, padding=tokens.SPACE_SM),
        ],
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
