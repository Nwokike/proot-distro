"""The two views, as state-driven components."""

from __future__ import annotations

import contextlib
import importlib.metadata as importlib_metadata
import logging
from pathlib import Path

import flet as ft

from components import card, empty_state, probe_banner, section_header
from components.banner_ad import pooled_banner_ad
from components.brand_hero import build_brand_hero
from core import theme, tokens
from core.changelog import notes_for
from core.constants import (
    APP_BUILD_NUMBER,
    APP_NAME,
    APP_VERSION,
    PRIVACY_POLICY_URL,
)
from core.shared_services import launch_url
from core.state import state
from state.controller_ctx import ControllerMethodsCtx

logger = logging.getLogger(__name__)

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


def _step_row(num: str, title: str, desc: str) -> ft.Row:
    """Numbered step row matching CollabShell / DDGS home patterns."""
    return ft.Row(
        controls=[
            ft.Container(
                content=ft.Text(
                    num,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                width=26,
                height=26,
                border_radius=tokens.RADIUS_PILL,
                bgcolor=theme.primary(),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Column(
                controls=[
                    ft.Text(
                        title,
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600,
                        color=theme.text(),
                    ),
                    ft.Text(desc, size=tokens.FONT_XS, color=theme.text_dim()),
                ],
                spacing=tokens.SPACE_XXS,
                expand=True,
            ),
        ],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _feature_card(icon: ft.IconData, title: str, desc: str) -> ft.Container:
    """Card explaining a feature capability matching CollabShell home."""
    return card(
        ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=tokens.ICON_LG, color=theme.primary()),
                    width=42,
                    height=42,
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(0.12, theme.primary()),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            title,
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            color=theme.text(),
                        ),
                        ft.Text(desc, size=tokens.FONT_XS, color=theme.text_dim(), max_lines=3),
                    ],
                    spacing=tokens.SPACE_XXS,
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        padding=tokens.SPACE_MD,
    )


# ── distro manager ───────────────────────────────────────────────────────────


@ft.component
def DistroView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    query, set_query = ft.use_state("")
    name, _set_name = ft.use_state("")

    is_narrow = bool(
        page
        and (
            (hasattr(page, "platform") and page.platform.is_mobile())
            or (getattr(page, "width", None) and page.width < 650)
        )
    )

    def _consent_install(target_ref: str | None = None, target_name: str | None = None) -> None:
        image = (target_ref or query).strip()
        if not image or st.installing:
            return
        container_tag = (target_name or name or "").strip()

        is_submitting = False

        def _confirm(_e) -> None:
            nonlocal is_submitting
            if is_submitting:
                return
            is_submitting = True
            page.pop_dialog()
            page.run_task(methods.install_distro, image, container_tag)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Install {image}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "Download size is not known until the registry responds. "
                    "The download starts only after you tap Install. Package "
                    "downloads inside the container happen only when you run commands.",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.FilledButton(
                        "Download & Install",
                        on_click=_confirm,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        ),
                    ),
                ],
            )
        )

    async def _on_paste(_e=None) -> None:
        clipboard = getattr(page, "clipboard", None)
        if clipboard is not None:
            with contextlib.suppress(Exception):
                pasted = await clipboard.get()
                if pasted and isinstance(pasted, str):
                    set_query(pasted.strip())

    def _on_search(_e=None) -> None:
        q = query.strip()
        if not q:
            return
        if ":" in q:
            _consent_install(q)
        else:
            page.run_task(methods.search_distro, q)

    def _distro_tile(label: str, ref: str) -> ft.Container:
        return card(
            ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.APPS_ROUNDED,
                            size=tokens.ICON_MD,
                            color=theme.primary(),
                        ),
                        width=38,
                        height=38,
                        border_radius=tokens.RADIUS_SM,
                        bgcolor=ft.Colors.with_opacity(0.10, theme.primary()),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Text(
                        label,
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.W_600,
                        color=theme.text(),
                        expand=True,
                    ),
                    ft.FilledButton(
                        "Install",
                        on_click=lambda _e, r=ref: _consent_install(r, ref),
                        height=34,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        ),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_SM,
            ),
            padding=tokens.SPACE_SM,
        )

    def _menu_items(cname: str) -> list[ft.PopupMenuItem]:
        return [
            ft.PopupMenuItem(
                icon=ft.Icons.EDIT_ROUNDED,
                content=ft.Text("Rename", size=tokens.FONT_SM),
                on_click=lambda _e: _ask_rename(cname),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.ARCHIVE_ROUNDED,
                content=ft.Text("Backup snapshot", size=tokens.FONT_SM),
                on_click=lambda _e: _ask_backup(cname),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.FOLDER_COPY_ROUNDED,
                content=ft.Text("Copy a path", size=tokens.FONT_SM),
                on_click=lambda _e: _ask_copy(cname),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.SYNC_ROUNDED,
                content=ft.Text("Sync folder", size=tokens.FONT_SM),
                on_click=lambda _e: _ask_sync(cname),
            ),
            ft.PopupMenuItem(
                icon=ft.Icons.INFO_OUTLINE_ROUNDED,
                content=ft.Text("Inspect container", size=tokens.FONT_SM),
                on_click=lambda _e: page.run_task(methods.inspect_container, cname),
            ),
        ]

    def _ask_rename(container: str) -> None:
        new_name = ft.TextField(
            label="New name",
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
            page.run_task(methods.rename_container, container, new_name.value or "")

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Rename {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
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

    def _ask_backup(container: str) -> None:
        dest = ft.TextField(
            label="Archive name",
            value=f"{container}-backup.tar.gz",
            text_size=tokens.FONT_SM,
            height=44,
            border=ft.OutlineInputBorder(
                border_radius=tokens.RADIUS_MD,
                side=ft.BorderSide(1, theme.surface_alt()),
            ),
        )

        def _save(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.backup_container, container, dest.value or "")

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"Backup {container}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=dest,
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
            page.run_task(methods.copy_path, source.value or "", destination.value or "")

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Copy a path", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Column(
                    controls=[source, destination], spacing=tokens.SPACE_XS, tight=True
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

    def _ask_sync(container: str) -> None:
        source = ft.TextField(
            hint_text="source folder (host or container:/path)",
            text_size=tokens.FONT_SM,
            height=44,
            border=ft.OutlineInputBorder(
                border_radius=tokens.RADIUS_MD,
                side=ft.BorderSide(1, theme.surface_alt()),
            ),
        )
        dest = ft.TextField(
            hint_text="destination folder",
            text_size=tokens.FONT_SM,
            height=44,
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

    def _container_card(row: dict) -> ft.Control:
        cname = row.get("name", "?")

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
                        "The container files are deleted. Cached downloads stay.",
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

        details_col = ft.Column(
            controls=[
                ft.Text(
                    cname,
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.BOLD,
                    color=theme.text(),
                ),
                ft.Text(
                    f"{row.get('image', '')} · {_fmt_size(row.get('size_bytes', 0))} · {row.get('arch', '')}",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
            ],
            spacing=0,
            expand=not is_narrow,
        )

        btn_shell = ft.FilledButton(
            "Open shell",
            on_click=lambda _e: page.run_task(methods.open_session, cname),
            height=34,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
            ),
        )
        btn_reset = ft.Button("Reset", on_click=_reset, height=34)
        btn_remove = ft.Button("Remove", on_click=_remove, height=34)
        menu_btn = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            icon_size=tokens.ICON_MD,
            tooltip="More actions",
            items=_menu_items(cname),
        )

        if is_narrow:
            card_content = ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.APPS_ROUNDED, size=tokens.ICON_MD, color=theme.primary()
                            ),
                            details_col,
                            menu_btn,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    ft.Row(
                        controls=[btn_shell, btn_reset, btn_remove],
                        spacing=tokens.SPACE_SM,
                        wrap=True,
                    ),
                ],
                spacing=tokens.SPACE_SM,
            )
        else:
            card_content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.APPS_ROUNDED, size=tokens.ICON_MD, color=theme.primary()),
                    details_col,
                    btn_shell,
                    btn_reset,
                    btn_remove,
                    menu_btn,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_SM,
            )

        return card(card_content, padding=tokens.SPACE_SM)

    # Modern install box (DDGS SearchBar pattern) — the "box to type in what
    # you want". Submitting runs the install consent flow directly.
    install_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.SEARCH_ROUNDED, size=tokens.ICON_MD, color=theme.primary()),
                ft.TextField(
                    hint_text="docker image ref (e.g. debian)",
                    value=query,
                    text_size=tokens.FONT_SM,
                    height=44,
                    expand=True,
                    border=ft.NoInputBorder(),
                    on_change=lambda e: set_query(e.control.value),
                    on_submit=lambda _e: _consent_install(),
                ),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Paste from clipboard",
                    on_click=lambda _e: page.run_task(_on_paste),
                ),
                ft.FilledButton(
                    "Install",
                    on_click=lambda _e: _consent_install(),
                    height=34,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                    ),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(1, theme.glass_border()),
        border_radius=tokens.RADIUS_MD,
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
    )

    # Certified distros: bare names and bare refs. No versions, no sizes, no
    # descriptions — Docker Hub resolves each image's current latest when the
    # user taps Install, and upstream's derive_alias names the container.
    _POPULAR_DISTROS = (
        ("Debian", "debian"),
        ("Ubuntu", "ubuntu"),
        ("Alpine", "alpine"),
    )

    controls: list[ft.Control] = [
        build_brand_hero("Linux on Android — no root"),
    ]
    if not st.probe_passed:
        controls.append(probe_banner(st.probe_summary))

    # Install first, the type-in box next, popular distros under it.
    controls.append(section_header("Install"))
    controls.append(install_bar)
    controls.extend([_distro_tile(label, ref) for label, ref in _POPULAR_DISTROS])

    # Install logs — the live stage line under the install section.
    if st.installing:
        progress = f"installing {st.installing} — {st.install_stage}"
    elif st.busy_note:
        progress = st.busy_note
    else:
        progress = ""
    if progress:
        controls.append(ft.Text(progress, size=tokens.FONT_SM, color=theme.accent()))

    controls.append(pooled_banner_ad("home-1", page))

    # Installed containers section
    controls.append(section_header("Containers"))
    if st.containers:
        controls.extend([_container_card(row) for row in st.containers])
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

    controls.append(pooled_banner_ad("home-2", page))

    # Separate search section (Docker Hub keyword search)
    search_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.SEARCH_ROUNDED, size=tokens.ICON_MD, color=theme.primary()),
                ft.TextField(
                    hint_text="search Docker Hub (e.g. archlinux)",
                    value=query,
                    text_size=tokens.FONT_SM,
                    height=44,
                    expand=True,
                    border=ft.NoInputBorder(),
                    on_change=lambda e: set_query(e.control.value),
                    on_submit=lambda _e: _on_search(),
                ),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Paste from clipboard",
                    on_click=lambda _e: page.run_task(_on_paste),
                ),
                ft.FilledButton(
                    "Search",
                    on_click=_on_search,
                    height=34,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                    ),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(1, theme.glass_border()),
        border_radius=tokens.RADIUS_MD,
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
    )

    controls.append(section_header("Search Docker Hub"))
    controls.append(search_bar)
    if st.search_status:
        controls.append(ft.Text(st.search_status, size=tokens.FONT_XS, color=theme.text_dim()))
    if st.search_results:
        result_cards = []
        for r in st.search_results[:8]:
            r_name = r.get("name", "")
            r_desc = r.get("description", "") or "No description"
            result_cards.append(
                card(
                    ft.Row(
                        controls=[
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        r_name, size=tokens.FONT_SM, weight=ft.FontWeight.W_600
                                    ),
                                    ft.Text(
                                        r_desc,
                                        size=tokens.FONT_XS,
                                        color=theme.text_dim(),
                                        max_lines=2,
                                    ),
                                ],
                                spacing=tokens.SPACE_XXS,
                                expand=True,
                            ),
                            ft.FilledButton(
                                "Install",
                                on_click=lambda _e, target=r_name: _consent_install(target),
                                height=32,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                                ),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    padding=tokens.SPACE_SM,
                )
            )
        controls.extend(result_cards)

    controls.append(pooled_banner_ad("home-3", page))

    # How It Works section matching CollabShell / DDGS
    controls.extend(
        [
            section_header("How It Works"),
            card(
                ft.Column(
                    controls=[
                        _step_row(
                            "1",
                            "Pick or Search a Distro",
                            "Select Debian, Ubuntu, Alpine or enter any public container image reference.",
                        ),
                        _step_row(
                            "2",
                            "One-Tap Install",
                            "Downloads and unpacks official container layers directly into private app storage.",
                        ),
                        _step_row(
                            "3",
                            "Launch Interactive Terminal",
                            "Enjoy full bash shell access with apt package manager, tools, and multi-session tabs.",
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
                padding=tokens.SPACE_LG,
            ),
        ]
    )

    # Feature capabilities matching CollabShell home
    controls.extend(
        [
            section_header("What Proot Distro Can Do"),
            _feature_card(
                ft.Icons.SECURITY_ROUNDED,
                "Rootless Linux Userspace",
                "Execute full Linux userland binaries without rooting your Android device or altering system partitions.",
            ),
            _feature_card(
                ft.Icons.TERMINAL_ROUNDED,
                "Native Interactive PTY",
                "True terminal experience with soft keyboard handling, extra virtual keys, zoom controls, and live title tracking.",
            ),
            _feature_card(
                ft.Icons.FOLDER_COPY_ROUNDED,
                "Container Backup & Sync",
                "Backup snapshots to tar archives, synchronize folders, and inspect container configurations anytime.",
            ),
            ft.Container(height=tokens.NAV_BAR_CLEARANCE),
        ]
    )

    return ft.Column(
        controls=controls, spacing=tokens.SPACE_SM, expand=True, scroll=ft.ScrollMode.AUTO
    )


# ── settings (Sherlock verbatim port) ─────────────────────────────────────────


def _settings_card(controls: list[ft.Control]) -> ft.Container:
    """Grouped settings card with Material 3 glass surface matching Sherlock."""
    return ft.Container(
        content=ft.Column(controls=controls, spacing=0),
        border_radius=tokens.RADIUS_LG,
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(width=1, color=theme.glass_border()),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )


def _setting_row(
    icon: ft.IconData,
    title: str,
    subtitle: str,
    trailing: ft.Control,
    stacked: bool = False,
) -> ft.Container:
    """Reusable settings row with icon box, title, subtitle, and responsive stacked trailing."""
    icon_box = ft.Container(
        content=ft.Icon(
            icon,
            size=tokens.ICON_MD,
            color=theme.primary(),
        ),
        width=36,
        height=36,
        border_radius=tokens.RADIUS_SM,
        bgcolor=ft.Colors.with_opacity(0.12, theme.primary()),
        alignment=ft.Alignment.CENTER,
    )
    text_col = ft.Column(
        controls=[
            ft.Text(
                title,
                size=tokens.FONT_MD,
                weight=ft.FontWeight.W_500,
                color=theme.text(),
            ),
            ft.Text(
                subtitle,
                size=tokens.FONT_XS,
                color=theme.text_dim(),
            ),
        ],
        spacing=tokens.SPACE_XXS,
        expand=True,
    )

    if stacked:
        trailing_line = ft.Row(
            controls=[
                ft.Container(width=36 + tokens.SPACE_MD),
                trailing,
            ],
            spacing=0,
        )
        content = ft.Column(
            controls=[
                ft.Row(
                    controls=[icon_box, text_col],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                trailing_line,
            ],
            spacing=tokens.SPACE_XS,
        )
    else:
        content = ft.Row(
            controls=[icon_box, text_col, trailing],
            spacing=tokens.SPACE_MD,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    return ft.Container(
        content=content,
        padding=ft.Padding(
            tokens.SPACE_LG,
            tokens.SPACE_MD,
            tokens.SPACE_LG,
            tokens.SPACE_MD,
        ),
    )


@ft.component
def SettingsView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    token, set_token = ft.use_state(st.docker_token)

    is_narrow = bool(page and getattr(page, "width", None) and page.width < 600)

    def _create_theme_card(mode: str, label: str, icon: ft.IconData) -> ft.Container:
        selected = st.theme_mode == mode
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(
                        icon,
                        size=tokens.ICON_LG,
                        color=theme.primary() if selected else theme.text_dim(),
                    ),
                    ft.Text(
                        label,
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400,
                        color=theme.primary() if selected else theme.text(),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_XS,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, theme.primary()) if selected else theme.surface(),
            border=ft.Border.all(
                1,
                theme.primary() if selected else theme.surface_alt(),
            ),
            border_radius=tokens.RADIUS_MD,
            padding=tokens.SPACE_MD,
            expand=True,
            ink=True,
            on_click=lambda _e, m=mode: page.run_task(methods.set_theme_mode, m),
        )

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
                    "Removes downloaded OCI image layers. Installed containers "
                    "continue working without interruption.",
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
                    f"Removes the cached layers for {identifier}. Installed containers remain operational.",
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

    def _open_changelog(_e=None) -> None:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    f"What's New in {APP_NAME} v{APP_VERSION}",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
                content=ft.Column(
                    controls=[
                        ft.Text(notes_for(APP_VERSION), size=tokens.FONT_SM),
                    ],
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                ),
                actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
            )
        )

    def _open_probe_dialog(_e=None) -> None:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "System Environment Probe", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=ft.Column(
                    controls=[
                        ft.Text(
                            f"Probe status: {'PASSED' if st.probe_passed else 'WARNING'}",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.BOLD,
                            color=theme.ok() if st.probe_passed else theme.warn(),
                        ),
                        ft.Text(
                            st.probe_summary
                            or "Payload verified and 16 KiB page alignment confirmed.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                    ],
                    tight=True,
                    spacing=tokens.SPACE_SM,
                ),
                actions=[
                    ft.TextButton(
                        "Re-check",
                        on_click=lambda _e: (page.pop_dialog(), page.run_task(methods.check_probe)),
                    ),
                    ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
                ],
            )
        )

    def _licenses(_e=None) -> None:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(
                    "Open-Source Licenses", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
                ),
                content=licenses_view(),
                actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
            )
        )

    # 1. Appearance & Theme Card
    appearance_card = _settings_card(
        [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Theme", size=tokens.FONT_MD, weight=ft.FontWeight.W_500),
                        ft.Row(
                            controls=[
                                _create_theme_card("light", "Light", ft.Icons.LIGHT_MODE_ROUNDED),
                                _create_theme_card("dark", "Dark", ft.Icons.DARK_MODE_ROUNDED),
                                _create_theme_card(
                                    "system", "System", ft.Icons.BRIGHTNESS_AUTO_ROUNDED
                                ),
                            ],
                            spacing=tokens.SPACE_SM,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                ),
                padding=tokens.SPACE_LG,
            ),
        ]
    )

    # 2. Container Storage & Cache Card
    cached_rows = []
    if st.cached_images:
        for img in st.cached_images:
            ident = str(img.get("identifier", ""))
            if not ident or ident == "?":
                continue
            arch = str(img.get("arch", ""))
            size = _fmt_size(img.get("size_bytes", 0))
            cached_rows.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.LAYERS_ROUNDED, size=tokens.ICON_XS, color=theme.primary()
                            ),
                            ft.Text(f"{ident} ({arch}) · {size}", size=tokens.FONT_XS, expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_size=tokens.ICON_SM,
                                tooltip=f"Remove cached {ident}",
                                on_click=lambda _e, i=ident: _confirm_remove_cached(i),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, 0),
                )
            )

    storage_card = _settings_card(
        [
            _setting_row(
                ft.Icons.STORAGE_ROUNDED,
                "Storage Footprint",
                f"Containers and cache: {_fmt_size(st.storage_bytes)}"
                + (f" · {st.cached_count} cached image(s)" if st.cached_count else ""),
                ft.TextButton("Clear all cache", on_click=lambda _e: _clear_cache()),
                stacked=is_narrow,
            ),
            ft.Divider(height=1, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CLEANING_SERVICES_ROUNDED,
                "Sweep Orphan Layers",
                "Reclaim storage from interrupted pulls or untagged OCI blobs",
                ft.TextButton(
                    "Sweep", on_click=lambda _e: page.run_task(methods.clear_orphan_layers)
                ),
                stacked=is_narrow,
            ),
            *cached_rows,
        ]
    )

    # 3. Registry Authentication Card (matching Sherlock custom manifest card layout)
    auth_card = _settings_card(
        [
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.VPN_KEY_ROUNDED,
                                size=tokens.ICON_MD,
                                color=theme.primary(),
                            ),
                            width=36,
                            height=36,
                            border_radius=tokens.RADIUS_SM,
                            bgcolor=ft.Colors.with_opacity(0.12, theme.primary()),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    "Docker Hub Token",
                                    size=tokens.FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                    color=theme.text(),
                                ),
                                ft.Text(
                                    "Stored locally on this device. Lifts anonymous rate limits.",
                                    size=tokens.FONT_XS,
                                    color=theme.text_dim(),
                                ),
                            ],
                            spacing=tokens.SPACE_XXS,
                            expand=True,
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=tokens.SPACE_MD,
                    bottom=tokens.SPACE_SM,
                ),
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.TextField(
                            value=token,
                            hint_text="Personal Access Token (optional)",
                            password=True,
                            can_reveal_password=True,
                            text_size=tokens.FONT_SM,
                            expand=True,
                            border=ft.OutlineInputBorder(
                                border_radius=tokens.RADIUS_SM,
                                side=ft.BorderSide(1, theme.surface_alt()),
                            ),
                            on_change=lambda e: set_token(e.control.value),
                            on_submit=lambda _e: _save_token(),
                        ),
                        ft.FilledButton(
                            "Save",
                            on_click=lambda _e: _save_token(),
                            height=44,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_SM)
                            ),
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
                padding=ft.Padding(
                    left=tokens.SPACE_LG,
                    right=tokens.SPACE_LG,
                    top=0,
                    bottom=tokens.SPACE_MD,
                ),
            ),
        ]
    )

    # 4. About & System Status Card (Sherlock pattern: Privacy Policy is here,
    # and UMP ad consent is deliberately NOT a settings entry).
    about_card = _settings_card(
        [
            _setting_row(
                ft.Icons.INFO_OUTLINE_ROUNDED,
                f"{APP_NAME} v{APP_VERSION} ({APP_BUILD_NUMBER})",
                "Release notes and change details",
                ft.TextButton("Changelog", on_click=_open_changelog),
                stacked=is_narrow,
            ),
            ft.Divider(height=1, color=theme.glass_border()),
            _setting_row(
                ft.Icons.GAVEL_ROUNDED,
                "Open-Source Licenses",
                "Complete license texts for PRoot, talloc, and Python dependencies",
                ft.TextButton("View Licenses", on_click=_licenses),
                stacked=is_narrow,
            ),
            ft.Divider(height=1, color=theme.glass_border()),
            _setting_row(
                ft.Icons.POLICY_ROUNDED,
                "Privacy Policy",
                "Container data stays on this device; see the full policy",
                ft.OutlinedButton(
                    "View Policy",
                    on_click=lambda _e: page.run_task(launch_url, PRIVACY_POLICY_URL, page),
                    height=36,
                ),
                stacked=is_narrow,
            ),
            ft.Divider(height=1, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                if st.probe_passed
                else ft.Icons.WARNING_ROUNDED,
                "Environment Probe",
                st.probe_summary or "Native library directory and proot payload ready",
                ft.TextButton("Inspect", on_click=_open_probe_dialog),
                stacked=is_narrow,
            ),
        ]
    )

    return ft.Column(
        controls=[
            section_header("Appearance & Theme"),
            appearance_card,
            section_header("Storage & Cache"),
            storage_card,
            pooled_banner_ad("settings-1", page),
            section_header("Registry Authentication"),
            auth_card,
            section_header("About & System Status"),
            about_card,
            pooled_banner_ad("settings-2", page),
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


def licenses_view() -> ft.Control:
    rows: list[ft.Control] = [
        ft.Text(
            f"{APP_NAME} v{APP_VERSION} incorporates open-source components "
            "licensed under free and copyleft licenses.",
            size=tokens.FONT_SM,
        ),
        ft.Divider(),
        ft.Text("GPL §6(b) Source Code Offer", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Source code offer (GPL-2.0 §3(b) / GPL-3.0 §6(b)). The complete "
            "machine-readable Corresponding Source for the GPL-licensed "
            "components above — including this application — is available "
            "at https://github.com/Nwokike/proot-distro and will remain "
            "available for at least three (3) years from the date of each "
            "release. Upstream: github.com/termux/proot, "
            "github.com/termux/proot-distro, github.com/termux/termux-packages "
            "(build recipes), talloc.samba.org.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
            selectable=True,
        ),
        ft.Divider(),
        ft.Text(
            "Debian is a registered trademark owned by Software in the "
            "Public Interest, Inc. This app is not affiliated with, "
            "endorsed by, or sponsored by the Debian project.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Text(
            "Ubuntu and Canonical are registered trademarks of Canonical "
            "Ltd. This app is not affiliated with, endorsed by, or "
            "sponsored by Canonical.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Text(
            "Alpine Linux is a registered trademark of the Alpine Linux "
            "Foundation. This app is not affiliated with, endorsed by, or "
            "sponsored by the Alpine Linux project.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Text(
            "This is an unofficial Flet-based Android client. It is not "
            "affiliated with, endorsed by, or sponsored by the Termux "
            "project or the PRoot-Distro project.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Divider(),
        ft.Text("Native Payload Components", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD),
    ]
    for pkg, lic in _NATIVE_LICENSES.items():
        rows.append(
            ft.ListTile(
                title=ft.Text(pkg, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"License: {lic}", size=tokens.FONT_XS, color=theme.text_dim()),
            )
        )
    rows.append(ft.Divider())
    rows.append(ft.Text("Python Dependencies", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD))
    for dist in _PY_DISTS:
        ver, lic = _dist_license(dist)
        rows.append(
            ft.ListTile(
                title=ft.Text(
                    f"{dist} {ver}".strip(), size=tokens.FONT_SM, weight=ft.FontWeight.BOLD
                ),
                subtitle=ft.Text(
                    f"License: {lic or 'See license text'}",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
            )
        )
    rows.append(ft.Divider())
    rows.append(ft.Text("License Texts", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD))
    for fname, label in _TEXT_FILES:
        path = _LICENSES_DIR / fname
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else "(text missing)"
        )
        rows.append(
            ft.ExpansionTile(
                title=ft.Text(label, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD),
                controls=[
                    ft.Container(
                        content=ft.Text(text, size=tokens.FONT_XS, font_family="JetBrains Mono"),
                        padding=tokens.SPACE_SM,
                    )
                ],
            )
        )
    return ft.Column(controls=rows, scroll=ft.ScrollMode.AUTO, expand=True)
