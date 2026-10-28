"""OnboardingScreen — First-launch presentation matching CollabShell and DDGS house design.

Three structured slides with feature rows, step guides, animated indicator dots,
back/next navigation controls, and full-screen swipe support.
"""

from __future__ import annotations

import flet as ft

from components.brand_hero import build_brand_hero
from core import theme, tokens
from state.controller_ctx import ControllerMethodsCtx

TOTAL_SLIDES = 3


def _feature_row(icon: ft.IconData, title: str, subtitle: str) -> ft.Container:
    """Feature row with icon container and description matching CollabShell."""
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=tokens.ICON_LG, color=theme.primary()),
                    width=tokens.ONBOARDING_ICON,
                    height=tokens.ONBOARDING_ICON,
                    border_radius=tokens.RADIUS_MD,
                    bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary()),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    controls=[
                        ft.Text(
                            title,
                            size=tokens.FONT_MD,
                            weight=ft.FontWeight.W_600,
                            color=theme.text(),
                        ),
                        ft.Text(
                            subtitle,
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                    ],
                    spacing=tokens.SPACE_XXS,
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_LG,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=tokens.SPACE_NONE, vertical=tokens.SPACE_SM),
    )


def _onboarding_step_row(num: str, title: str, desc: str) -> ft.Row:
    """Numbered step row for slide 2 guide."""
    return ft.Row(
        controls=[
            ft.Container(
                content=ft.Text(
                    num,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.BOLD,
                    color=theme.WHITE,
                ),
                width=tokens.ONBOARDING_ICON_SM,
                height=tokens.ONBOARDING_ICON_SM,
                border_radius=tokens.RADIUS_PILL,
                bgcolor=theme.primary(),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Column(
                controls=[
                    ft.Text(
                        title,
                        size=tokens.FONT_MD,
                        weight=ft.FontWeight.W_600,
                        color=theme.text(),
                    ),
                    ft.Text(
                        desc,
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                    ),
                ],
                spacing=tokens.SPACE_XXS,
                expand=True,
            ),
        ],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _build_slide_1() -> ft.Column:
    """Slide 1: Brand welcome and core capabilities."""
    return ft.Column(
        controls=[
            build_brand_hero("Linux on Android — no root"),
            ft.Container(height=tokens.SPACE_MD),
            _feature_row(
                ft.Icons.SECURITY_ROUNDED,
                "Rootless Linux Containers",
                "Run Debian, Ubuntu, or Alpine in an isolated userspace on your device.",
            ),
            _feature_row(
                ft.Icons.TERMINAL_ROUNDED,
                "Real Interactive Terminal",
                "Native PTY shell with apt package manager, development tools, and extra keys.",
            ),
            _feature_row(
                ft.Icons.FOLDER_COPY_ROUNDED,
                "Container Backup & Sync",
                "Create tar snapshot backups, synchronize folders, and manage OCI images.",
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=tokens.SPACE_SM,
        scroll=ft.ScrollMode.AUTO,
    )


def _build_slide_2() -> ft.Column:
    """Slide 2: How it works step guide."""
    return ft.Column(
        controls=[
            ft.Container(height=tokens.SPACE_LG),
            ft.Icon(
                ft.Icons.ROCKET_LAUNCH_ROUNDED,
                size=tokens.ICON_XXXL,
                color=theme.primary(),
            ),
            ft.Container(height=tokens.SPACE_SM),
            ft.Text(
                "How It Works",
                size=tokens.FONT_XL,
                weight=ft.FontWeight.BOLD,
                color=theme.text(),
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=tokens.SPACE_MD),
            _onboarding_step_row(
                "1",
                "Choose a Distro",
                "Select Debian, Ubuntu, Alpine or enter any public container image reference.",
            ),
            ft.Container(height=tokens.SPACE_SM),
            _onboarding_step_row(
                "2",
                "One-Tap Download",
                "Official layers are pulled directly from container registries to your device.",
            ),
            ft.Container(height=tokens.SPACE_SM),
            _onboarding_step_row(
                "3",
                "Launch Your Shell",
                "Open an interactive terminal session and execute commands as root.",
            ),
            ft.Container(height=tokens.SPACE_LG),
            ft.Container(
                content=ft.Text(
                    "Tip: You can run multiple containers concurrently and switch between them seamlessly.",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                    text_align=ft.TextAlign.CENTER,
                ),
                padding=tokens.SPACE_MD,
                border_radius=tokens.RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=tokens.SPACE_NONE,
        scroll=ft.ScrollMode.AUTO,
    )


def _build_slide_3() -> ft.Column:
    """Slide 3: Privacy, security, and local sandbox verification."""
    return ft.Column(
        controls=[
            ft.Container(height=tokens.SPACE_LG),
            ft.Icon(
                ft.Icons.SHIELD_ROUNDED,
                size=tokens.ICON_XXXL,
                color=theme.primary(),
            ),
            ft.Container(height=tokens.SPACE_SM),
            ft.Text(
                "Private & Local Sandbox",
                size=tokens.FONT_XL,
                weight=ft.FontWeight.BOLD,
                color=theme.text(),
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=tokens.SPACE_SM),
            ft.Text(
                "All container data, installed packages, and terminal sessions stay strictly on your device.",
                size=tokens.FONT_SM,
                color=theme.text_dim(),
                text_align=ft.TextAlign.CENTER,
            ),
            ft.Container(height=tokens.SPACE_XL),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED,
                            size=tokens.ICON_MD,
                            color=theme.ok(),
                        ),
                        ft.Text(
                            "100% Local Sandbox · Zero Remote Tracking",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            color=theme.text(),
                        ),
                    ],
                    spacing=tokens.SPACE_MD,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=tokens.SPACE_MD,
                border_radius=tokens.RADIUS_MD,
                bgcolor=ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.ok()),
            ),
            ft.Container(height=tokens.SPACE_LG),
            ft.Text(
                "No registration or accounts required. PRoot translates system calls entirely in user-space without root access.",
                size=tokens.FONT_XS,
                color=theme.text_dim(),
                text_align=ft.TextAlign.CENTER,
            ),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=tokens.SPACE_NONE,
        scroll=ft.ScrollMode.AUTO,
    )


@ft.component
def OnboardingView() -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    slide_index, set_slide_index = ft.use_state(0)
    is_last = slide_index == TOTAL_SLIDES - 1

    def _next(_e=None) -> None:
        if is_last:
            page.run_task(methods.finish_onboarding)
        else:
            set_slide_index(slide_index + 1)

    def _back(_e=None) -> None:
        if slide_index > 0:
            set_slide_index(slide_index - 1)

    def _skip(_e=None) -> None:
        page.run_task(methods.finish_onboarding)

    def _swipe(e: ft.DragEndEvent) -> None:
        v = getattr(e, "primary_velocity", 0) or 0
        if v < -200 and slide_index < TOTAL_SLIDES - 1:
            set_slide_index(slide_index + 1)
        elif v > 200 and slide_index > 0:
            set_slide_index(slide_index - 1)

    def _render_current_slide() -> ft.Control:
        if slide_index == 0:
            return _build_slide_1()
        if slide_index == 1:
            return _build_slide_2()
        return _build_slide_3()

    # Indicator dots matching CollabShell / DDGS
    dots = [
        ft.Container(
            width=tokens.DOT_ACTIVE if i == slide_index else tokens.DOT_INACTIVE,
            height=tokens.DOT_HEIGHT,
            border_radius=tokens.DOT_RADIUS,
            bgcolor=theme.primary()
            if i == slide_index
            else ft.Colors.with_opacity(tokens.OPACITY_SELECTED, theme.text()),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        for i in range(TOTAL_SLIDES)
    ]

    nav_row = ft.Container(
        content=ft.Row(
            controls=[
                ft.TextButton(
                    "Back",
                    on_click=_back,
                    visible=slide_index > 0,
                ),
                ft.Row(
                    controls=dots,
                    spacing=tokens.SPACE_XS,
                ),
                ft.FilledButton(
                    "Get Started" if is_last else "Next",
                    on_click=_next,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_MD),
    )

    gesture_area = ft.GestureDetector(
        on_horizontal_drag_end=_swipe,
        content=_render_current_slide(),
        expand=True,
    )

    return ft.SafeArea(
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Container(expand=True),
                                ft.TextButton("Skip", on_click=_skip, visible=not is_last),
                            ]
                        ),
                        padding=ft.Padding(tokens.SPACE_SM, 0, tokens.SPACE_MD, 0),
                    ),
                    ft.Container(
                        content=gesture_area,
                        expand=True,
                        padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, 0),
                    ),
                    nav_row,
                ],
                spacing=tokens.SPACE_NONE,
                expand=True,
            ),
            bgcolor=theme.bg(),
            expand=True,
        ),
        expand=True,
    )
