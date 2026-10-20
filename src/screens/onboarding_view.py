"""Onboarding — the first-run deck (house pattern: chrome-free, skippable).

Three slides: what this is, how it works, and the honest attribution line.
Persisted, so it only shows once.
"""

from __future__ import annotations

import flet as ft

from components.brand_hero import app_icon_svg
from core import theme, tokens
from state.controller_ctx import ControllerMethodsCtx

_SLIDES = (
    {
        "icon": None,
        "title": "Real Linux\non your phone",
        "body": "Full Debian, Ubuntu or Alpine containers running on Android — "
        "no root, no Termux, nothing to set up.",
    },
    {
        "icon": ft.Icons.DOWNLOAD_ROUNDED,
        "title": "Any image\nyou can pull",
        "body": "Install a container by typing a reference like debian:bookworm, "
        "or search Docker Hub and tap a result.",
    },
    {
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "title": "A shell\nthat is really yours",
        "body": "Open a terminal in any container and use it like a normal "
        "Linux shell — the same proot-distro engine Termux runs.",
    },
)


@ft.component
def OnboardingView() -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    index, set_index = ft.use_state(0)
    total = len(_SLIDES)
    slide = _SLIDES[index]
    last = index == total - 1

    def _next(_e=None) -> None:
        if last:
            page.run_task(methods.finish_onboarding)
            return
        set_index(index + 1)

    def _skip(_e=None) -> None:
        page.run_task(methods.finish_onboarding)

    def _swipe(e) -> None:
        velocity = getattr(e, "primary_velocity", 0) or 0
        if velocity < -200:
            _next()
        elif velocity > 200 and index > 0:
            set_index(index - 1)

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(height=tokens.SPACE_XXL),
                ft.Row(
                    controls=[
                        ft.Container(expand=True),
                        ft.TextButton("Skip", on_click=_skip, visible=not last),
                    ]
                ),
                ft.GestureDetector(
                    on_horizontal_drag_end=_swipe,
                    content=ft.Column(
                        controls=[
                            ft.Image(
                                src=app_icon_svg(),
                                width=tokens.HERO_ICON_SIZE,
                                height=tokens.HERO_ICON_SIZE,
                                fit=ft.BoxFit.CONTAIN,
                                color=None if theme.is_light_theme() else ft.Colors.WHITE,
                            ),
                            ft.Container(height=tokens.SPACE_XL),
                            ft.Text(
                                slide["title"],
                                size=tokens.FONT_HERO,
                                weight=ft.FontWeight.BOLD,
                                color=theme.text(),
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=tokens.SPACE_SM),
                            ft.Text(
                                slide["body"],
                                size=tokens.FONT_LG,
                                color=theme.text_dim(),
                                text_align=ft.TextAlign.CENTER,
                                width=tokens.MESSAGE_MAX_WIDTH,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=0,
                    ),
                ),
                ft.Container(expand=True),
                ft.Row(
                    controls=[
                        ft.Container(
                            width=24 if i == index else 8,
                            height=8,
                            border_radius=tokens.RADIUS_PILL,
                            bgcolor=theme.primary() if i == index else theme.surface_alt(),
                        )
                        for i in range(total)
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=tokens.SPACE_XS,
                ),
                ft.Container(height=tokens.SPACE_XL),
                ft.FilledButton(
                    "Get Started" if last else "Next",
                    width=220,
                    height=52,
                    on_click=_next,
                ),
                ft.Container(height=tokens.SPACE_SM),
                ft.Text(
                    "An unofficial client. Not affiliated with the Termux project "
                    "or the PRoot-Distro project.",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                    text_align=ft.TextAlign.CENTER,
                    width=tokens.MESSAGE_MAX_WIDTH,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
        ),
        bgcolor=theme.bg(),
        expand=True,
    )
