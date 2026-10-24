"""AppShell — navigation over the views, and the session subview when a shell
is open. CollabShell's shape: tabs on the bottom bar, the session takes over
the screen with a back button.
"""

from __future__ import annotations

import flet as ft

from core import theme
from core.state import state
from screens import (
    DistroView,
    OnboardingView,
    SessionSelectorView,
    SettingsView,
    TerminalView,
)

TAB_DISTRO = 0
TAB_TERMINAL = 1
TAB_SETTINGS = 2

_TABS = (
    ("Distros", ft.Icons.APPS),
    ("Terminal", ft.Icons.TERMINAL),
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
    if entry is not None:
        body = TerminalView(entry)
    elif active_tab == TAB_DISTRO:
        body = DistroView()
    elif active_tab == TAB_TERMINAL:
        body = SessionSelectorView()
    else:
        body = SettingsView()

    return ft.Column(
        controls=[
            ft.Container(content=body, expand=True, bgcolor=theme.bg()),
            ft.NavigationBar(
                destinations=[
                    ft.NavigationBarDestination(icon=icon, label=label) for label, icon in _TABS
                ],
                selected_index=active_tab,
                on_change=_on_change,
                bgcolor=theme.surface(),
            ),
        ],
        spacing=0,
        expand=True,
    )
