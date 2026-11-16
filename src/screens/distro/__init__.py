"""DistroView — home: install, containers, search. Sections live in sections.py."""

from __future__ import annotations

import flet as ft

from components import card, empty_state, pill_dropdown, probe_banner, section_header
from components.banner_ad import pooled_banner_ad
from components.brand_hero import build_brand_hero
from components.ui import house_field, search_field
from core import layout, theme, tokens
from core.constants import (
    AD_EVERY_ROWS,
    AD_SLOT_CONTAINERS,
    AD_SLOT_SEARCH_EMPTY,
    SEARCH_LIMIT_DEFAULT,
)
from core.state import state
from screens.container_card import build_container_card
from services import proot_service
from state.controller_ctx import ControllerMethodsCtx

from . import sections


@ft.component
def DistroView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    query, set_query = ft.use_state("")
    name, set_name = ft.use_state("")
    arch_choice, set_arch_choice = ft.use_state("host")
    insecure, set_insecure = ft.use_state(False)
    search_limit, set_search_limit = ft.use_state("25")
    # Sherlock's email/username swap: one bar, two modes.
    mode, set_mode = ft.use_state("install")  # "install" | "search"

    # Upstream's own accepted architectures: the list is DERIVED from
    # proot_distro.arch (native names, Docker names and linux/ platform
    # strings, each validated through normalize_arch), never hardcoded here.
    _ARCH_CHOICES = proot_service.arch_choices()

    is_narrow = layout.is_mobile_layout(page)

    def _consent_install(target_ref: str | None = None, target_name: str | None = None) -> None:
        image = (target_ref or query).strip()
        if not image or st.installing:
            return
        container_tag = (target_name or name or "").strip()
        arch_sel = "" if arch_choice == "host" else arch_choice
        extras = []
        if arch_sel:
            extras.append(f"arch {arch_sel}")
        if insecure:
            extras.append("insecure registry allowed")
        note = (" · " + ", ".join(extras)) if extras else ""

        def _confirm(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.install_distro, image, container_tag, arch_sel, insecure)
            from components.install_progress_modal import show_install_progress_modal

            show_install_progress_modal(page, container_tag or image)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(f"Install {image}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                content=ft.Text(
                    "Downloads official rootfs layers into private storage. "
                    "The download starts only after you tap Install." + note,
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
        try:
            # No ceiling — the limit is passed straight through to upstream,
            # which forwards it to the Docker Hub API.
            limit = max(1, int(search_limit or SEARCH_LIMIT_DEFAULT))
        except ValueError:
            limit = SEARCH_LIMIT_DEFAULT
        if ":" in q:
            _consent_install(q)
        else:
            page.run_task(methods.search_distro, q, limit)

    def _distro_tile(label: str, ref: str) -> ft.Container:
        # The container name is upstream derive_alias(ref): the last path
        # component, tag stripped ("kalilinux/kali-rolling" → "kali-rolling",
        # "opensuse/tumbleweed" → "tumbleweed", bare names unchanged). Compare
        # THAT, not the raw ref — namespaced refs never equal the name, so
        # Kali/openSUSE used to show Install while already installed.
        alias = ref.strip().split("@")[0].split(":")[0].rsplit("/", 1)[-1]
        installed_names = {r.get("name", "") for r in (st.containers or [])}
        already = alias in installed_names

        def _action(_e, r=ref) -> None:
            if already:
                page.run_task(methods.open_session, r)
            else:
                _consent_install(r, ref)

        return card(
            ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(
                            ft.Icons.TERMINAL_ROUNDED if already else ft.Icons.APPS_ROUNDED,
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
                        "Open" if already else "Install",
                        icon=ft.Icons.TERMINAL_ROUNDED if already else None,
                        on_click=_action,
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

    # One full-width SearchBar with an Install | Search swap (Sherlock's
    # email/username segmented pattern). Trailing controls swap with the mode:
    # install → insecure switch (inside the box, like the limit in search);
    # search → tiny limit dropdown. Both keep paste.
    limit_dropdown = pill_dropdown(
        "Limit",
        ft.Icons.FILTER_ALT_ROUNDED,
        [str(n) for n in (25, 50, 100)],
        search_limit if search_limit in ("25", "50", "100") else str(SEARCH_LIMIT_DEFAULT),
        set_search_limit,
        tooltip="Max results (limit), up to Docker Hub page size",
    )
    # Tiny insecure toggle inside the bar (shield icon; lit when on).
    insecure_switch = ft.IconButton(
        icon=ft.Icons.SHIELD_ROUNDED if insecure else ft.Icons.SHIELD_OUTLINED,
        icon_size=tokens.ICON_SM,
        icon_color=theme.warn() if insecure else theme.text_dim(),
        tooltip="Allow insecure registry (--allow-insecure): ON"
        if insecure
        else "Allow insecure registry (--allow-insecure)",
        on_click=lambda _e: set_insecure(not insecure),
    )

    def _mode_pill(value: str, label: str, icon: ft.IconData) -> ft.Container:
        """One pill of Sherlock's email/username swap (home_screen.py:860-933)."""
        active = mode == value
        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(
                        icon,
                        size=tokens.ICON_SM,
                        color=theme.WHITE if active else theme.text_dim(),
                    ),
                    ft.Text(
                        label,
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.BOLD,
                        color=theme.WHITE if active else theme.text_dim(),
                    ),
                ],
                spacing=tokens.SPACE_XS,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=theme.primary() if active else theme.TRANSPARENT,
            border_radius=tokens.RADIUS_SM,
            padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
            ink=True,
            expand=True,
            alignment=ft.Alignment.CENTER,
            on_click=lambda _e, v=value: set_mode(v),
        )

    # Sherlock's exact swap: a bordered track with two equal pills, CENTERED.
    mode_swap = ft.Container(
        alignment=ft.Alignment.CENTER,
        content=ft.Container(
            border=ft.Border.all(
                tokens.HAIRLINE, ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.text())
            ),
            border_radius=tokens.RADIUS_SM,
            padding=ft.Padding.all(tokens.SPACE_XXS),
            content=ft.Row(
                controls=[
                    _mode_pill("install", "Install", ft.Icons.DOWNLOAD_ROUNDED),
                    _mode_pill("search", "Search", ft.Icons.SEARCH_ROUNDED),
                ],
                spacing=tokens.SPACE_XS,
            ),
        ),
    )
    main_bar = ft.Container(
        alignment=ft.Alignment.CENTER,  # centered like Sherlock's search bar
        content=search_field(
            hint=(
                "docker image ref (e.g. debian)"
                if mode == "install"
                else "search Docker Hub (e.g. archlinux)"
            ),
            value=query,
            # No leading icon (owner ruling) — the action icon at the end IS
            # the mode: big Download in install, Search in search.
            trailing=[
                insecure_switch if mode == "install" else limit_dropdown,
                ft.IconButton(
                    icon=ft.Icons.CONTENT_PASTE_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Paste from clipboard",
                    on_click=lambda _e: page.run_task(_on_paste),
                ),
                ft.IconButton(
                    icon=ft.Icons.DOWNLOAD_ROUNDED
                    if mode == "install"
                    else ft.Icons.SEARCH_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    icon_color=theme.primary(),
                    tooltip="Install" if mode == "install" else "Search",
                    on_click=lambda _e: _consent_install() if mode == "install" else _on_search(),
                ),
            ],
            on_submit=lambda _e: _consent_install() if mode == "install" else _on_search(),
            on_change=lambda e: set_query(e.control.value),
        ),
        expand=True,
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
    )

    # Certified distros: bare names and bare refs. No versions, no sizes, no
    # descriptions — Docker Hub resolves each image's current latest when the
    # user taps Install, and upstream's derive_alias names the container.
    # Modern/rolling first (Alpine, Arch, Fedora, openSUSE, Kali), the
    # old-guard stable pair last.
    _POPULAR_DISTROS = (
        ("Alpine", "alpine"),
        ("Fedora", "fedora"),
        ("openSUSE", "opensuse/tumbleweed"),
        ("Kali", "kalilinux/kali-rolling"),
        ("Ubuntu", "ubuntu"),
        ("Debian", "debian"),
    )

    # Containers first (owner ruling): what you have, then ONE banner, then the
    # install/search area exactly as before underneath it.
    controls: list[ft.Control] = [
        build_brand_hero("Linux on Android, no root"),
    ]
    if not st.probe_passed:
        controls.append(probe_banner(st.probe_summary))

    from components.install_progress_modal import build_active_install_banner

    active_banner = build_active_install_banner(page)
    if active_banner:
        controls.append(active_banner)

    controls.append(section_header("Containers"))
    if st.containers:
        controls.extend(
            build_container_card(row, page, methods, is_narrow) for row in st.containers
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
    # One banner between the container list and the install area (owner ruling).
    controls.append(pooled_banner_ad(AD_SLOT_CONTAINERS, page))

    # Install options — Sherlock pattern: an options row UNDER the install bar,
    # single horizontal track that scrolls on narrow screens (START-aligned so
    # the leading control never clips). Compact controls, no card.
    install_options = ft.Container(
        visible=mode == "install",  # arch + name apply to installs only
        content=ft.Row(
            controls=[
                pill_dropdown(
                    "Arch (-a)",
                    ft.Icons.MEMORY_ROUNDED,
                    list(_ARCH_CHOICES),
                    arch_choice,
                    set_arch_choice,
                    tooltip="Target CPU architecture (-a/--architecture; default: host)",
                    labels={"host": f"host ({proot_service.host_arch()})"},
                ),
                house_field(
                    hint="container name (-n, optional)",
                    value=name,
                    on_change=lambda e: set_name(e.control.value),
                    height=tokens.CONTROL_SM,
                    text_size=tokens.FONT_XS,
                    width=tokens.FIELD_NAME_WIDTH,
                    tooltip="Custom container name (-n); blank = derived from the image",
                ),
            ],
            wrap=False,
            scroll=ft.ScrollMode.AUTO,
            alignment=ft.MainAxisAlignment.START,
            spacing=tokens.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_XS, tokens.SPACE_LG, 0),
    )

    # Install/search bar first, its options row under it, popular distros below.
    controls.append(section_header("Install" if mode == "install" else "Search Docker Hub"))
    controls.append(mode_swap)
    controls.append(main_bar)
    controls.append(install_options)
    if mode == "install":
        controls.extend([_distro_tile(label, ref) for label, ref in _POPULAR_DISTROS])

    # Install logs — the live stage line under the install section.
    if mode == "install" and (st.installing or st.busy_note):
        progress = (
            f"installing {st.installing}: {st.install_stage}" if st.installing else st.busy_note
        )
        controls.append(ft.Text(progress, size=tokens.FONT_SM, color=theme.accent()))

    # Search status + results sit DIRECTLY under the search bar in both modes
    # (mirrors the examples under the install box), so results never land after
    # containers or bunched at the bottom. Long result lists get a banner after
    # every 5th; an empty result set gets one sticky banner.
    if st.search_status:
        controls.append(ft.Text(st.search_status, size=tokens.FONT_XS, color=theme.text_dim()))
    result_cards = sections.build_search_results(st, _consent_install)
    for i in range(AD_EVERY_ROWS - 1, len(result_cards), AD_EVERY_ROWS):
        result_cards.insert(i + 1, pooled_banner_ad(f"search-{i // AD_EVERY_ROWS + 1}", page))
    if result_cards:
        controls.extend(result_cards)
    elif mode == "search":
        # No results yet — including the fresh search screen before the first
        # query — keeps one sticky banner (owner ruling).
        controls.append(pooled_banner_ad(AD_SLOT_SEARCH_EMPTY, page))

    # No banner after the last section — banners live between sections only.
    controls.append(ft.Container(height=tokens.NAV_BAR_CLEARANCE))

    return ft.Column(
        controls=controls, spacing=tokens.SPACE_SM, expand=True, scroll=ft.ScrollMode.AUTO
    )
