"""The two views, as state-driven components."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import logging
from pathlib import Path

import flet as ft

from components import card, empty_state, hints_card, probe_banner, section_header
from components.app_header import theme_button
from components.banner_ad import pooled_banner_ad
from components.brand_hero import build_brand_hero
from core import theme, tokens
from core.constants import PRIVACY_POLICY_URL
from core.shared_services import launch_url
from core.state import state
from state.controller_ctx import ControllerMethodsCtx

_LICENSES_DIR = Path(__file__).resolve().parent.parent / "LICENSES"
_NATIVE_LICENSES = {
    "proot": "GPL-2.0",
    "libtalloc": "GPL-3.0",
    "libandroid-shmem": "BSD-3-Clause",
}
_PY_DISTS = (
    "proot-distro",
    "flet",
    "flet-ads",
    "flet-terminal",
    "msgpack",
    "anyio",
    "httpx",
    "httpcore",
    "h11",
    "idna",
    "certifi",
    "typing-extensions",
    "oauthlib",
    "repath",
    "six",
)
_TEXT_FILES = (
    ("GPL-2.0.txt", "GPL-2.0"),
    ("GPL-3.0.txt", "GPL-3.0"),
    ("Apache-2.0.txt", "Apache-2.0"),
    ("MIT.txt", "MIT"),
    ("BSD-3-Clause.txt", "BSD-3-Clause"),
    ("MPL-2.0.txt", "MPL-2.0"),
    ("PSF-2.0.txt", "PSF-2.0"),
)


def _fmt_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GiB"


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


# ── distro manager ───────────────────────────────────────────────────────────


@ft.component
def DistroView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    query, set_query = ft.use_state("")
    name, set_name = ft.use_state("")

    def _field() -> ft.TextField:
        return ft.TextField(
            hint_text="docker image ref (e.g. debian:bookworm)",
            value=query,
            text_size=tokens.FONT_SM,
            height=44,
            expand=True,
            border=ft.OutlineInputBorder(
                border_radius=tokens.RADIUS_MD,
                side=ft.BorderSide(1, theme.surface_alt()),
            ),
            on_change=lambda e: set_query(e.control.value),
            on_submit=lambda _e: _consent_install(),
        )

    def _consent_install() -> None:
        image = query.strip()
        if not image or st.installing:
            return

        def _confirm(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.install_distro, image, name.strip())

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Download and install", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=ft.Column(
                    controls=[
                        ft.Text(image, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Download size is not known until the registry responds. "
                            "Typical base images: Alpine ~8 MB, Debian ~30 MB, "
                            "Ubuntu ~75 MB — an estimate, not a measurement.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                        ft.Text(
                            "The download starts only after you tap Install. "
                            "Package downloads inside the container happen only "
                            "when you run commands.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.FilledButton(
                        "Install",
                        on_click=_confirm,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                        ),
                    ),
                ],
            )
        )

    def _search() -> None:
        q = query.strip()
        if q:
            page.run_task(methods.search_distro, q)

    def _hit_row(hit: dict) -> ft.Control:
        label = hit.get("name", "?")
        stars = _fmt_count(hit.get("stars", 0))
        pulls = _fmt_count(hit.get("pulls", 0))
        official = " [official]" if hit.get("official") else ""
        desc = (hit.get("description") or "")[:80]

        def _pick(_e) -> None:
            set_query(label)
            set_name(label.split(":")[0].split("/")[-1])

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"{label}{official}  ★{stars} ⤓{pulls}",
                        size=tokens.FONT_SM,
                        color=theme.text(),
                        weight=ft.FontWeight.W_500,
                    ),
                    ft.Text(desc, size=tokens.FONT_XS, color=theme.text_dim()),
                ],
                spacing=tokens.SPACE_XXS,
            ),
            on_click=_pick,
            ink=True,
            padding=tokens.SPACE_XS,
            border_radius=tokens.RADIUS_SM,
        )

    def _container_row(row: dict) -> ft.Control:
        cname = row.get("name", "?")

        def _menu_items(container: str) -> list[ft.PopupMenuItem]:
            def _rename(_e) -> None:
                _ask_rename(container)

            def _backup(_e) -> None:
                page.run_task(methods.backup_container, container)

            def _copy(_e) -> None:
                _ask_copy(container)

            def _sync(_e) -> None:
                _ask_sync(container)

            def _inspect(_e) -> None:
                page.run_task(methods.inspect_container, container)

            def _sessions(_e) -> None:
                page.run_task(methods.list_sessions)

            def _restore(_e) -> None:
                page.run_task(methods.restore_container)

            return [
                ft.PopupMenuItem(
                    content=ft.Text("Inspect container", size=tokens.FONT_SM),
                    on_click=_inspect,
                ),
                ft.PopupMenuItem(content=ft.Text("Rename", size=tokens.FONT_SM), on_click=_rename),
                ft.PopupMenuItem(
                    content=ft.Text("Backup to a file", size=tokens.FONT_SM), on_click=_backup
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Restore from an archive", size=tokens.FONT_SM),
                    on_click=_restore,
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Copy a path", size=tokens.FONT_SM), on_click=_copy
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Sync folder", size=tokens.FONT_SM), on_click=_sync
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Running sessions", size=tokens.FONT_SM), on_click=_sessions
                ),
            ]

        def _ask_sync(container: str) -> None:
            source = ft.TextField(
                hint_text=f"source (e.g. {container}:/root or /sdcard/src)",
                text_size=tokens.FONT_SM,
                height=44,
                border=ft.OutlineInputBorder(
                    border_radius=tokens.RADIUS_MD,
                    side=ft.BorderSide(1, theme.surface_alt()),
                ),
            )
            destination = ft.TextField(
                hint_text=f"destination (e.g. {container}:/root/dest)",
                text_size=tokens.FONT_SM,
                height=44,
                border=ft.OutlineInputBorder(
                    border_radius=tokens.RADIUS_MD,
                    side=ft.BorderSide(1, theme.surface_alt()),
                ),
            )
            delete_box = ft.Checkbox(
                label="Prune files in destination that do not exist in source",
                value=False,
            )

            def _save(_e) -> None:
                page.pop_dialog()
                page.run_task(
                    methods.sync_path,
                    source.value or "",
                    destination.value or "",
                    True,
                    delete_box.value or False,
                )

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(
                        f"Sync Folder ({container})",
                        size=tokens.FONT_LG,
                        weight=ft.FontWeight.BOLD,
                    ),
                    content=ft.Column(
                        controls=[source, destination, delete_box],
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

        def _ask_rename(container: str) -> None:
            field = ft.TextField(
                hint_text="new name",
                value=container,
                text_size=tokens.FONT_SM,
                height=44,
                border=ft.OutlineInputBorder(
                    border_radius=tokens.RADIUS_MD,
                    side=ft.BorderSide(1, theme.surface_alt()),
                ),
            )

            def _save(_e) -> None:
                page.pop_dialog()
                page.run_task(methods.rename_container, container, field.value or "")

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(
                        f"Rename {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                    ),
                    content=field,
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

        def _ask_copy(container: str) -> None:
            source = ft.TextField(
                hint_text="source (container:/path)",
                text_size=tokens.FONT_SM,
                height=44,
                border=ft.OutlineInputBorder(
                    border_radius=tokens.RADIUS_MD,
                    side=ft.BorderSide(1, theme.surface_alt()),
                ),
            )
            destination = ft.TextField(
                hint_text="destination (container:/path)",
                text_size=tokens.FONT_SM,
                height=44,
                border=ft.OutlineInputBorder(
                    border_radius=tokens.RADIUS_MD,
                    side=ft.BorderSide(1, theme.surface_alt()),
                ),
            )

            def _save(_e) -> None:
                page.pop_dialog()
                page.run_task(
                    methods.copy_path,
                    source.value or "",
                    destination.value or "",
                )

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text("Copy a path", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                    content=ft.Column(controls=[source, destination], spacing=tokens.SPACE_XS),
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

        def _remove(_e) -> None:
            def _yes(_e) -> None:
                page.pop_dialog()
                page.run_task(methods.remove_container, cname)

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(
                        f"Remove {cname}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                    ),
                    content=ft.Text(
                        "The container's files are deleted. Cached downloads stay.",
                        size=tokens.FONT_SM,
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

        def _reset(_e) -> None:
            def _yes(_e) -> None:
                page.pop_dialog()
                page.run_task(methods.reset_container, cname)

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(
                        f"Reset {cname}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                    ),
                    content=ft.Text(
                        "The container is wiped and reinstalled from the cached "
                        "image — no re-download when the layers are cached.",
                        size=tokens.FONT_SM,
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                        ft.FilledButton(
                            "Reset",
                            on_click=_yes,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            ),
                        ),
                    ],
                )
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(
                                cname,
                                size=tokens.FONT_MD,
                                weight=ft.FontWeight.BOLD,
                                color=theme.text(),
                            ),
                            ft.Text(
                                f"{row.get('image', '')} · "
                                f"{_fmt_size(row.get('size_bytes', 0))} · "
                                f"{row.get('arch', '')}",
                                size=tokens.FONT_XS,
                                color=theme.text_dim(),
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    ft.FilledButton(
                        "Open shell",
                        on_click=lambda _e: page.run_task(methods.open_session, cname),
                        height=36,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        ),
                    ),
                    ft.Button("Reset", on_click=_reset, height=36),
                    ft.Button("Remove", on_click=_remove, height=36),
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT,
                        icon_size=tokens.ICON_MD,
                        tooltip="More actions",
                        items=_menu_items(cname),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=theme.glass_bg(),
            border=ft.Border.all(1, theme.glass_border()),
            padding=tokens.SPACE_SM,
            border_radius=tokens.RADIUS_MD,
        )

    _CERTIFIED_DISTROS = (
        ("Debian 12", "debian:bookworm", "debian"),
        ("Ubuntu 24.04", "ubuntu:24.04", "ubuntu"),
        ("Alpine 3.21", "alpine:3.21", "alpine"),
    )

    chips = []
    for clabel, cref, cdef_name in _CERTIFIED_DISTROS:
        is_sel = query == cref
        chips.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED
                            if is_sel
                            else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            size=tokens.ICON_XS,
                            color=theme.primary() if is_sel else theme.text_dim(),
                        ),
                        ft.Text(
                            clabel,
                            size=tokens.FONT_XS,
                            color=theme.primary() if is_sel else theme.text(),
                            weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.W_400,
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                    tight=True,
                ),
                padding=ft.Padding(
                    tokens.SPACE_SM,
                    tokens.SPACE_XXS,
                    tokens.SPACE_SM,
                    tokens.SPACE_XXS,
                ),
                border_radius=tokens.RADIUS_PILL,
                bgcolor=ft.Colors.with_opacity(0.12, theme.primary())
                if is_sel
                else theme.surface_alt(),
                border=ft.Border.all(
                    1,
                    ft.Colors.with_opacity(0.24, theme.primary())
                    if is_sel
                    else ft.Colors.TRANSPARENT,
                ),
                on_click=lambda _e, r=cref, n=cdef_name: (
                    set_query(r),
                    set_name(n),
                ),
                ink=True,
            )
        )

    controls: list[ft.Control] = [
        build_brand_hero("Linux on Android — no root, no Termux"),
        hints_card(st.hints_dismissed, lambda _e: page.run_task(methods.dismiss_hints)),
        section_header("Install"),
    ]
    if not st.probe_passed:
        controls.append(probe_banner(st.probe_summary))
    controls.append(
        card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=chips,
                        spacing=tokens.SPACE_XS,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    ft.Row(
                        controls=[
                            _field(),
                            ft.FilledButton(
                                "Install",
                                on_click=lambda _e: _consent_install(),
                                height=44,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                                ),
                            ),
                        ],
                        spacing=tokens.SPACE_SM,
                    ),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                hint_text="name (optional)",
                                value=name,
                                width=160,
                                text_size=tokens.FONT_SM,
                                height=44,
                                border=ft.OutlineInputBorder(
                                    border_radius=tokens.RADIUS_MD,
                                    side=ft.BorderSide(1, theme.surface_alt()),
                                ),
                                on_change=lambda e: set_name(e.control.value),
                            ),
                            ft.Button("Search", on_click=lambda _e: _search(), height=44),
                        ],
                        spacing=tokens.SPACE_SM,
                    ),
                    ft.Text(st.search_status, size=tokens.FONT_XS, color=theme.text_dim()),
                    ft.Column(
                        controls=[_hit_row(hit) for hit in st.search_results[:12]],
                        spacing=tokens.SPACE_XXS,
                    ),
                ],
                spacing=tokens.SPACE_SM,
            )
        )
    )

    if st.installing:
        progress = f"installing {st.installing} — {st.install_stage}"
    elif st.busy_note:
        progress = st.busy_note
    else:
        progress = ""
    if progress:
        controls.append(ft.Text(progress, size=tokens.FONT_SM, color=theme.accent()))

    controls.append(section_header("Containers"))
    if st.containers:
        controls.append(
            ft.Column(controls=[_container_row(r) for r in st.containers], spacing=tokens.SPACE_SM)
        )
    else:
        controls.append(
            empty_state(
                "No containers yet",
                "Install any Docker image to begin.",
                icon=ft.Icons.INVENTORY_2_OUTLINED,
            )
        )
    if st.data_note:
        controls.append(
            ft.Text(st.data_note, size=tokens.FONT_XS, color=theme.warn(), selectable=True)
        )

    controls.append(pooled_banner_ad("distros-1", page))
    controls.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))
    return ft.Column(
        controls=controls, spacing=tokens.SPACE_SM, expand=True, scroll=ft.ScrollMode.AUTO
    )


# ── settings ─────────────────────────────────────────────────────────────────


@ft.component
def SettingsView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    token, set_token = ft.use_state(st.docker_token)

    def _save_token() -> None:
        page.run_task(methods.set_docker_token, token)

    def _clear_cache() -> None:
        def _yes(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.clear_cache)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Clear cached downloads?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=ft.Text(
                    "Removes the downloaded image layers. Installed containers "
                    "keep working; a later reinstall re-downloads.",
                    size=tokens.FONT_SM,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.FilledButton(
                        "Clear",
                        on_click=_yes,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                            bgcolor=theme.warn(),
                        ),
                    ),
                ],
            )
        )

    def _confirm_remove_cached(identifier: str) -> None:
        def _yes(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.remove_cached_image, identifier)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Remove cached image {identifier}?",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Text(
                    f"Removes the cached layers for {identifier}. Installed containers "
                    "based on this image keep working.",
                    size=tokens.FONT_SM,
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

    def _make_cached_image_row(img: dict) -> ft.Control:
        ident = str(img.get("identifier", ""))
        arch = str(img.get("arch", ""))
        size = _fmt_size(img.get("size_bytes", 0))
        return ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.LAYERS_ROUNDED,
                    size=tokens.ICON_XS,
                    color=theme.primary(),
                ),
                ft.Text(
                    f"{ident} ({arch}) · {size}",
                    size=tokens.FONT_XS,
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip=f"Remove cached {ident}",
                    on_click=lambda _e: _confirm_remove_cached(ident),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _licenses(_e) -> None:
        def _close(_e) -> None:
            page.pop_dialog()

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Open-source licenses", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=licenses_view(),
                actions=[ft.TextButton("Close", on_click=_close)],
            )
        )

    mode_label = {"system": "System", "light": "Light", "dark": "Dark"}[st.theme_mode]

    return ft.Column(
        controls=[
            section_header("Appearance"),
            card(
                ft.Column(
                    controls=[
                        ft.Text(
                            "Theme follows the system unless you pick one.",
                            size=tokens.FONT_SM,
                            color=theme.text_dim(),
                        ),
                        ft.Row(
                            controls=[
                                ft.Text(
                                    f"Theme: {mode_label}",
                                    size=tokens.FONT_MD,
                                    color=theme.text(),
                                    expand=True,
                                ),
                                theme_button(lambda: page.run_task(methods.cycle_theme_mode)),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                )
            ),
            section_header("Storage"),
            card(
                ft.Column(
                    controls=[
                        ft.Text(
                            f"containers + cache: {_fmt_size(st.storage_bytes)}"
                            + (f" · {st.cached_count} cached image(s)" if st.cached_count else ""),
                            size=tokens.FONT_SM,
                            color=theme.text_dim(),
                        ),
                        *(
                            [
                                ft.Text(
                                    f"Active locks: {', '.join(st.busy_locks)}",
                                    size=tokens.FONT_XS,
                                    color=theme.accent(),
                                )
                            ]
                            if st.busy_locks
                            else []
                        ),
                        *(
                            [
                                ft.Text(
                                    st.data_note,
                                    size=tokens.FONT_XS,
                                    color=theme.warn(),
                                    selectable=True,
                                )
                            ]
                            if st.data_note
                            else []
                        ),
                        *(
                            [
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            "Cached Images",
                                            size=tokens.FONT_SM,
                                            weight=ft.FontWeight.W_600,
                                        ),
                                        *[
                                            _make_cached_image_row(img)
                                            for img in st.cached_images
                                            if img.get("identifier")
                                            and img.get("identifier") != "?"
                                        ],
                                    ],
                                    spacing=tokens.SPACE_XXS,
                                )
                            ]
                            if st.cached_images
                            else []
                        ),
                        ft.Row(
                            controls=[
                                ft.TextButton(
                                    "Clear all cache", on_click=lambda _e: _clear_cache()
                                ),
                                ft.TextButton(
                                    "Sweep orphan layers",
                                    on_click=lambda _e: page.run_task(methods.clear_orphan_layers),
                                ),
                            ],
                            spacing=tokens.SPACE_XS,
                        ),
                        ft.Text(
                            "Package downloads happen inside your container, from "
                            "the distro's own mirrors, only when you run a command "
                            "or tap an update action.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                )
            ),
            section_header("Docker Hub"),
            card(
                ft.Column(
                    controls=[
                        ft.TextField(
                            hint_text="Docker Hub token (optional)",
                            value=token,
                            password=True,
                            text_size=tokens.FONT_SM,
                            height=44,
                            border=ft.OutlineInputBorder(
                                border_radius=tokens.RADIUS_MD,
                                side=ft.BorderSide(1, theme.surface_alt()),
                            ),
                            on_change=lambda e: set_token(e.control.value),
                        ),
                        ft.Text(
                            "Stored on this device only. It lifts you from the "
                            "anonymous pull limit to your account's limit.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                        ft.TextButton("Save token", on_click=lambda _e: _save_token()),
                    ],
                    spacing=tokens.SPACE_XS,
                )
            ),
            section_header("About"),
            card(
                ft.Column(
                    controls=[
                        ft.ListTile(
                            title=ft.Text("Open-source licenses", size=tokens.FONT_MD),
                            on_click=_licenses,
                        ),
                        ft.ListTile(
                            title=ft.Text("Privacy policy", size=tokens.FONT_MD),
                            on_click=lambda _e: page.run_task(launch_url, PRIVACY_POLICY_URL, page),
                        ),
                        ft.ListTile(
                            title=ft.Text("Privacy options", size=tokens.FONT_MD),
                            subtitle=ft.Text(
                                "Manage advertising consent preferences", size=tokens.FONT_XS
                            ),
                            on_click=lambda _e: page.run_task(methods.show_privacy_options),
                        ),
                        ft.Text(
                            "Unofficial Flet-based Android client. Not affiliated "
                            "with the Termux project.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                        ft.Text(
                            f"Runtime probe: {st.probe_summary or '—'}",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                        ft.TextButton(
                            "Re-check probe",
                            on_click=lambda _e: page.run_task(methods.check_probe),
                        ),
                    ],
                    spacing=tokens.SPACE_XXS,
                )
            ),
            pooled_banner_ad("settings-1", page),
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ],
        spacing=tokens.SPACE_SM,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


# ── licenses (compliance §3.3 content contract) ──────────────────────────────


def _dist_license(dist: str) -> tuple[str, str]:
    try:
        meta = importlib_metadata.metadata(dist)
    except Exception:
        return ("", "")
    version = meta.get("Version", "")
    lic = meta.get("License-Expression") or meta.get("License") or ""
    return (version, lic)


def _native_entries() -> list[dict]:
    """Native payload provenance from the flet_proot wheel manifest (no hardcoding)."""
    entries: list[dict] = []
    try:
        import flet_proot  # type: ignore[import-not-found]

        version = getattr(flet_proot, "VERSION", "")
        for src in getattr(flet_proot, "SOURCES", []) or []:
            if not isinstance(src, dict):
                continue
            package = src.get("package", "?")
            entries.append(
                {
                    "component": package,
                    "version": str(src.get("version", "")),
                    "license": _NATIVE_LICENSES.get(package, ""),
                    "source": src.get("url", ""),
                    "via": f"flet-proot {version}",
                }
            )
    except Exception as exc:
        # The native-payload rows are compliance-critical (§3.3): a blank
        # list here must be visible in logs, not silently pass.
        logging.getLogger(__name__).warning("native license entries unavailable: %r", exc)
    return entries


def _py_entries() -> list[dict]:
    entries = []
    for dist in _PY_DISTS:
        version, lic = _dist_license(dist)
        if version:
            entries.append({"component": dist, "version": version, "license": lic, "source": ""})
    return entries


def licenses_view() -> ft.Control:
    """Licenses screen content (compliance §3.3). Plain function: it is also
    built inside dialog handlers, where a @ft.component would raise."""
    entries = _native_entries() + _py_entries()
    rows = [
        ft.Text(
            f"• {e['component']} {e['version']}"
            + (f" ({e['license']})" if e.get("license") else "")
            + (f" — {e['source']}" if e.get("source") else ""),
            size=11,
            color=theme.text(),
            selectable=True,
        )
        for e in entries
    ]

    texts = []
    for fname, label in _TEXT_FILES:
        path = _LICENSES_DIR / fname
        # Full text, no truncation: §3.3 requires scrollable complete texts,
        # and errors="replace" keeps one stray byte from killing the dialog.
        body = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else "(text missing)"
        )
        texts.append(
            ft.ExpansionTile(
                title=ft.Text(label, size=13),
                controls=[ft.Container(content=ft.Text(body, size=9, selectable=True), padding=8)],
            )
        )

    return ft.Column(
        controls=[
            ft.Text(
                "This app includes third-party software. Full texts below; "
                "the same texts ship in the repository's LICENSES/ directory.",
                size=11,
                color=theme.text_dim(),
            ),
            ft.Column(controls=rows, spacing=2),
            ft.Divider(),
            ft.Text(
                "Source code offer (GPL-2.0 §3(b) / GPL-3.0 §6(b)). The complete "
                "machine-readable Corresponding Source for the GPL-licensed "
                "components above — including this application — is available "
                "at https://github.com/Nwokike/proot-distro and will remain "
                "available for at least three (3) years from the date of each "
                "release. Upstream: github.com/termux/proot, "
                "github.com/termux/proot-distro, github.com/termux/termux-packages "
                "(build recipes), talloc.samba.org.",
                size=10,
                color=theme.text_dim(),
                selectable=True,
            ),
            ft.Divider(),
            ft.Text(
                "Debian is a registered trademark owned by Software in the "
                "Public Interest, Inc. This app is not affiliated with, "
                "endorsed by, or sponsored by the Debian project.",
                size=10,
                color=theme.text_dim(),
            ),
            ft.Text(
                "Ubuntu and Canonical are registered trademarks of Canonical "
                "Ltd. This app is not affiliated with, endorsed by, or "
                "sponsored by Canonical.",
                size=10,
                color=theme.text_dim(),
            ),
            ft.Text(
                "Alpine Linux is a registered trademark of the Alpine Linux "
                "Foundation. This app is not affiliated with, endorsed by, or "
                "sponsored by the Alpine Linux project.",
                size=10,
                color=theme.text_dim(),
            ),
            ft.Text(
                "This is an unofficial Flet-based Android client. It is not "
                "affiliated with, endorsed by, or sponsored by the Termux "
                "project or the PRoot-Distro project.",
                size=10,
                color=theme.text_dim(),
            ),
            ft.Divider(),
            *texts,
        ],
        spacing=4,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
