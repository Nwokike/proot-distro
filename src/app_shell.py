"""AppShell — the component shell: shared header + navigation over the views."""

from __future__ import annotations

import flet as ft

from components.app_header import AppHeader
from core import theme
from core.state import state
from screens import DistroView, SettingsView
from state.controller_ctx import ControllerMethodsCtx

TAB_DISTRO = 0
TAB_SETTINGS = 1

_TAB_META = (
    ("Proot Distro", "Linux containers on your phone"),
    ("Settings", "Storage · theme · licenses"),
)


@ft.component
def AppShell() -> ft.Control:
    active_tab, set_active_tab = ft.use_state(TAB_DISTRO)
    _st, _ = ft.use_state(state)  # subscribe: theme flips repaint the header
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page

    def _on_change(e):
        set_active_tab(1 if e.data == "1" else 0)

    def _cycle_theme():
        page.run_task(methods.cycle_theme_mode)

    title, subtitle = _TAB_META[active_tab]
    body = DistroView() if active_tab == TAB_DISTRO else SettingsView()

    return ft.Column(
        controls=[
            AppHeader(
                title=title,
                subtitle=subtitle,
                on_cycle_theme=_cycle_theme,
            ),
            ft.Container(content=body, expand=True, bgcolor=theme.bg()),
            ft.NavigationBar(
                destinations=[
                    ft.NavigationBarDestination(icon=ft.Icons.APPS, label="Distros"),
                    ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Settings"),
                ],
                selected_index=active_tab,
                on_change=_on_change,
                bgcolor=theme.surface(),
            ),
        ],
        spacing=0,
        expand=True,
    )
