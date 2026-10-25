"""Onboarding — first-run presentation deck matching CollabShell and DDGS house design.

Three slides with animated dot indicators, 120px circular icon backdrops,
full-screen gesture detection, and clean typography.
"""

from __future__ import annotations

import flet as ft

from components.brand_hero import app_icon_svg
from core import theme, tokens
from state.controller_ctx import ControllerMethodsCtx

_SLIDES = (
    {
        "icon": None,
        "title": "Linux on Android\nno root",
        "body": (
            "Run Debian, Ubuntu, Alpine, or any container image in an isolated, "
            "rootless Linux environment directly on your device."
        ),
    },
    {
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "title": "Native Terminal\nwith Full Shell",
        "body": (
            "Interactive bash sessions with apt, compilers, development tools, "
            "and multi-shell tabs without modifying Android partitions."
        ),
    },
    {
        "icon": ft.Icons.SHIELD_ROUNDED,
        "title": "Private, Local\n& Containerized",
        "body": (
            "All container data and commands reside strictly in your private "
            "storage sandbox. No accounts, no remote servers, no tracking."
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
            ft.Container(height=tokens.SPACE_MD),
            ft.Text(
                slide["body"],
                size=tokens.FONT_MD,
                color=theme.text_dim(),
                text_align=ft.TextAlign.CENTER,
                width=tokens.MESSAGE_MAX_WIDTH,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=0,
    )

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
                        width=240,
                        height=48,
                        on_click=_next,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        ),
                    ),
                    ft.Container(height=tokens.SPACE_SM),
                    ft.Text(
                        "An independent utility wrapping open-source PRoot.",
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
