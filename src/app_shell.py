"""AppShell — CollabShell's shape: SafeArea, a FIXED header bar at shell
level (title = the active tab), the screen body scrolling beneath it, and a
NavigationBar that steps aside while a shell is open or fullscreen.
"""

from __future__ import annotations

import flet as ft

from components.app_header import AppHeader
from core import theme
from core.state import state
from screens import (
    DistroView,
    FilesView,
    OnboardingView,
    SessionSelectorView,
    SettingsView,
    TerminalView,
)

TAB_DISTRO = 0
TAB_TERMINAL = 1
TAB_FILES = 2
TAB_SETTINGS = 3

_TABS = (
    ("Distros", ft.Icons.APPS),
    ("Terminal", ft.Icons.TERMINAL),
    ("Files", ft.Icons.FOLDER_OUTLINED),
    ("Settings", ft.Icons.SETTINGS),
)


def _session_entry(controller, active_container: str | None) -> object | None:
    if controller is None or not active_container:
        return None
    manager = getattr(controller, "session_manager", None)
    if manager is None:
        return None
    return manager.entries.get(active_container)


@ft.component
def AppShell() -> ft.Control:
    # Subscribe to the observable state: attribute reads alone do NOT
    # re-render a component — without use_state(state) the onboarding deck
    # dead-ends on first run and shell open/close never swaps the tree.
    st, _ = ft.use_state(state)
    page = ft.context.page
    active_tab, set_active_tab = ft.use_state(TAB_DISTRO)
    controller = getattr(page, "_controller", None)

    def _on_change(e):
        set_active_tab(int(e.data))

    if not st.onboarding_done:
        return OnboardingView()

    entry = _session_entry(controller, st.active_session)
    fullscreen = st.terminal_fullscreen
    if entry is not None:
        body = TerminalView(entry)
    elif active_tab == TAB_DISTRO:
        body = DistroView()
    elif active_tab == TAB_TERMINAL:
        body = SessionSelectorView()
    elif active_tab == TAB_FILES:
        body = FilesView()
    else:
        body = SettingsView()

    chrome: list[ft.Control] = []
    if entry is None:
        # CollabShell: one fixed bar for every tab; the session screen has
        # its own header, so the shell bar steps aside while it is open.
        chrome.append(
            AppHeader(
                _TABS[active_tab][0],
                lambda: page.run_task(controller.cycle_theme_mode),
                page=page,
            )
        )
    chrome.append(ft.Container(content=body, expand=True, bgcolor=theme.bg()))
    if entry is None and not fullscreen:
        # The session owns the whole screen (true full screen, extra room
        # for the keyboard) — the nav bar hides while a shell is open.
        chrome.append(
            ft.NavigationBar(
                destinations=[
                    ft.NavigationBarDestination(icon=icon, label=label) for label, icon in _TABS
                ],
                selected_index=active_tab,
                on_change=_on_change,
                bgcolor=theme.surface(),
                indicator_color=ft.Colors.with_opacity(0.12, theme.primary()),
                label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
            )
        )

    return ft.SafeArea(
        content=ft.Column(controls=chrome, spacing=0, expand=True),
        expand=True,
    )
