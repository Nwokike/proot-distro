"""Shared UI pieces — headers, cards, empty states, probe warning, hints.

Every control here reads its colors through `core.theme` at construction time
inside a render, so a theme flip re-renders correctly in both palettes.
"""

from __future__ import annotations

import flet as ft

from core import theme


def card(content: ft.Control, padding: int = 8) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=theme.surface(),
        padding=padding,
        border_radius=8,
    )


def section_header(title: str, subtitle: str | None = None) -> ft.Control:
    controls = [ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=theme.text())]
    if subtitle:
        controls.append(ft.Text(subtitle, size=11, color=theme.text_dim()))
    return ft.Container(
        content=ft.Column(controls=controls, spacing=2),
        padding=ft.Padding.only(left=8, right=8, top=8),
    )


def empty_state(title: str, hint: str) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(title, size=13, color=theme.text_dim()),
                ft.Text(hint, size=11, color=theme.text_dim()),
            ],
            spacing=2,
        ),
        padding=16,
    )


def probe_banner(summary: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(f"⚠ {summary}", size=12, color=theme.AppColors.WARN),
        bgcolor=theme.surface(),
        padding=4,
    )


def hints_card(dismissed: bool, on_dismiss) -> ft.Control:
    """CollabShell-style capability hints; every line is a real app ability."""
    items = [
        "Everything here runs the real proot-distro — the same engine Termux uses, without Termux.",
        "Install any Docker image: type a reference (e.g. debian:bookworm, alpine:3.21) or search Docker Hub.",
        "Installed containers can be removed or reset any time; cached downloads are reclaimed in Settings.",
    ]
    if dismissed:
        return ft.Container()
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.INFO, size=14, color=theme.primary()),
                        ft.Text(
                            "How this works",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=theme.text(),
                            expand=True,
                        ),
                        ft.TextButton("Got it", on_click=on_dismiss),
                    ]
                ),
                *[ft.Text(f"• {line}", size=11, color=theme.text_dim()) for line in items],
            ],
            spacing=2,
        ),
        bgcolor=theme.surface(),
        padding=8,
        border_radius=8,
    )
