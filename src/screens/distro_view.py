from __future__ import annotations

import flet as ft

from components import card, empty_state, probe_banner, section_header
from components.banner_ad import pooled_banner_ad
from components.brand_hero import build_brand_hero
from core import theme, tokens
from core.state import state
from screens.container_card import build_container_card
from state.controller_ctx import ControllerMethodsCtx


def _step_row(num: str, title: str, desc: str) -> ft.Row:
    """Numbered step row matching CollabShell / DDGS home patterns."""
    return ft.Row(
        controls=[
            ft.Container(
                content=ft.Text(
                    num,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.BOLD,
                    color=theme.WHITE,
                ),
                width=tokens.CONTROL_XS,
                height=tokens.CONTROL_XS,
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
                    width=tokens.CONTROL_XL,
                    height=tokens.CONTROL_XL,
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
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

        def _confirm(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.install_distro, image, container_tag)
            from components.install_progress_modal import show_install_progress_modal

            show_install_progress_modal(page, container_tag or image)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Install {image}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "Downloads official rootfs layers into private storage. "
                    "The download starts only after you tap Install.",
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
                        width=tokens.CONTROL_LG,
                        height=tokens.CONTROL_LG,
                        border_radius=tokens.RADIUS_SM,
                        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TINT, theme.primary()),
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
                        height=tokens.CONTROL_SM,
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
                    height=tokens.CONTROL_INPUT,
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
                    height=tokens.CONTROL_SM,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                    ),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(tokens.HAIRLINE, theme.glass_border()),
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

    from components.install_progress_modal import build_active_install_banner

    active_banner = build_active_install_banner(page)
    if active_banner:
        controls.append(active_banner)

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

    # Banner 1: after the Install section (install box, popular distros, logs).
    controls.append(pooled_banner_ad("home-1", page))

    # Installed containers section
    controls.append(section_header("Containers"))
    if st.containers:
        controls.extend(
            [build_container_card(row, page, methods, is_narrow) for row in st.containers]
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

    # Separate search section (Docker Hub keyword search)
    search_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.SEARCH_ROUNDED, size=tokens.ICON_MD, color=theme.primary()),
                ft.TextField(
                    hint_text="search Docker Hub (e.g. archlinux)",
                    value=query,
                    text_size=tokens.FONT_SM,
                    height=tokens.CONTROL_INPUT,
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
                    height=tokens.CONTROL_SM,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                    ),
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.glass_bg(),
        border=ft.Border.all(tokens.HAIRLINE, theme.glass_border()),
        border_radius=tokens.RADIUS_MD,
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
    )

    controls.append(section_header("Search Docker Hub"))
    controls.append(search_bar)
    if st.search_status:
        controls.append(ft.Text(st.search_status, size=tokens.FONT_XS, color=theme.text_dim()))
    if st.search_results:
        result_cards = []
        for r in st.search_results:
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
                                height=tokens.CONTROL_COMPACT,
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

    # Banner 2: after How It Works.
    controls.append(pooled_banner_ad("home-2", page))

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
        ]
    )

    # Banner 3: after what Proot Distro can do — the last content banner.
    controls.append(pooled_banner_ad("home-3", page))
    controls.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))

    return ft.Column(
        controls=controls, spacing=tokens.SPACE_SM, expand=True, scroll=ft.ScrollMode.AUTO
    )
