"""Onboarding — the first-run deck (CollabShell/DDGS pattern: chrome-free, skippable).

Three slides with animated dot indicators, 120px circular icon backdrops,
and full-screen gesture detection.
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
        "body": (
            "Full Debian, Ubuntu or Alpine containers running on Android — "
            "no root, no Termux, nothing to set up."
        ),
    },
    {
        "icon": ft.Icons.DOWNLOAD_ROUNDED,
        "title": "Any image\nyou can pull",
        "body": (
            "Install a container by typing a reference like debian:bookworm, "
            "or search Docker Hub and tap a result."
        ),
    },
    {
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "title": "A shell\nthat is really yours",
        "body": (
            "Open a terminal in any container and use it like a normal "
            "Linux shell — the same proot-distro engine Termux runs."
        ),
    },
)

ICON_CONTAINER_SIZE = 120


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

    icon_control: ft.Control
    if slide["icon"] is None:
        icon_control = ft.Image(
            src=app_icon_svg(),
            width=64,
            height=64,
            fit=ft.BoxFit.CONTAIN,
            color=None if theme.is_light_theme() else ft.Colors.WHITE,
            color_blend_mode=ft.BlendMode.SRC_IN,
            error_content=ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=64),
        )
    else:
        icon_control = ft.Icon(
            slide["icon"],
            size=64,
            color=theme.primary(),
        )

    slide_art = ft.Container(
        content=icon_control,
        width=ICON_CONTAINER_SIZE,
        height=ICON_CONTAINER_SIZE,
        border_radius=ICON_CONTAINER_SIZE // 2,
        bgcolor=ft.Colors.with_opacity(0.10, theme.primary()),
        alignment=ft.Alignment.CENTER,
    )

    slide_content = ft.Column(
        controls=[
            slide_art,
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
    )

    # GestureDetector with expand=True covers the entire screen, eliminating
    # the dead swipe zone reported in the file audit.
    gesture_area = ft.GestureDetector(
        on_horizontal_drag_end=_swipe,
        content=slide_content,
        expand=True,
    )

    return ft.SafeArea(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(height=tokens.SPACE_SM),
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            ft.TextButton("Skip", on_click=_skip, visible=not last),
                        ]
                    ),
                    gesture_area,
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=24 if i == index else 8,
                                height=8,
                                border_radius=tokens.RADIUS_PILL,
                                bgcolor=theme.primary() if i == index else theme.surface_alt(),
                                animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
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
                        height=48,
                        on_click=_next,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        ),
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
                    ft.Container(height=tokens.SPACE_SM),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_SM,
                expand=True,
            ),
            bgcolor=theme.bg(),
            expand=True,
        ),
        expand=True,
    )
