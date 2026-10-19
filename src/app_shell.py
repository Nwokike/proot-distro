"""AppShell — the component shell: navigation over the two views."""

from __future__ import annotations

import flet as ft

from core import theme
from screens import DistroView, SettingsView

TAB_DISTRO = 0
TAB_SETTINGS = 1


@ft.component
def AppShell() -> ft.Control:
    active_tab, set_active_tab = ft.use_state(TAB_DISTRO)

    def _on_change(e):
        set_active_tab(1 if e.data == "1" else 0)

    body = DistroView() if active_tab == TAB_DISTRO else SettingsView()

    return ft.Column(
        controls=[
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
