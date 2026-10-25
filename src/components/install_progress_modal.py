"""Install progress modal and sticky banner — real-time distro installation progress.

Provides a live progress modal with streaming log output, a 'Run in Background'
option, and a sticky top-of-page banner for ongoing and completed installs.
"""

from __future__ import annotations

import contextlib

import flet as ft

from core import theme, tokens
from core.state import state


def show_install_progress_modal(page: ft.Page, target: str) -> None:
    """Open the modal dialog displaying real-time install progress."""
    logs_column = ft.Column(
        controls=[
            ft.Text(
                line,
                font_family="JetBrains Mono",
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
            for line in state.install_logs[-60:]
        ],
        spacing=tokens.SPACE_NANO,
        scroll=ft.ScrollMode.AUTO,
        height=180,
    )

    stage_text = ft.Text(
        state.install_stage or "Preparing download…",
        size=tokens.FONT_SM,
        weight=ft.FontWeight.W_500,
        color=theme.text(),
        expand=True,
    )

    progress_ring = ft.ProgressRing(width=22, height=22, stroke_width=2.5)

    status_row = ft.Row(
        controls=[progress_ring, stage_text],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    log_box = ft.Container(
        content=logs_column,
        bgcolor=ft.Colors.with_opacity(0.06, theme.text()),
        border=ft.Border.all(1, theme.surface_alt()),
        border_radius=tokens.RADIUS_SM,
        padding=tokens.SPACE_SM,
    )

    def _minimize(_e) -> None:
        state.install_dialog_minimized = True
        with contextlib.suppress(Exception):
            page.pop_dialog()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=theme.primary(), size=tokens.ICON_MD),
                ft.Text(f"Installing {target}", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            ],
            spacing=tokens.SPACE_SM,
        ),
        content=ft.Column(
            controls=[status_row, log_box],
            spacing=tokens.SPACE_MD,
            tight=True,
            width=tokens.DIALOG_WIDTH,
        ),
        actions=[
            ft.TextButton(
                "Run in Background",
                icon=ft.Icons.VISIBILITY_OFF_ROUNDED,
                on_click=_minimize,
            )
        ],
    )
    # Store control references on the page so _apply_line can update them live.
    page._install_stage_text = stage_text
    page._install_logs_column = logs_column
    page._install_dialog = dialog
    page.show_dialog(dialog)


def build_active_install_banner(page: ft.Page) -> ft.Control | None:
    """Sticky banner rendered at the top of the home view during/after an install."""
    controller = getattr(page, "_controller", None)

    if state.install_completed and state.last_installed:

        def _open(_e) -> None:
            c = state.last_installed
            state.install_completed = False
            state.last_installed = ""
            if controller:
                page.run_task(controller.open_session, c)

        def _dismiss(_e) -> None:
            state.install_completed = False
            state.last_installed = ""
            page.update()

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=theme.ok(), size=tokens.ICON_MD),
                    ft.Text(
                        f"Installed {state.last_installed}! Container is ready.",
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.W_600,
                        color=theme.text(),
                        expand=True,
                    ),
                    ft.FilledButton(
                        "Open shell",
                        icon=ft.Icons.TERMINAL_ROUNDED,
                        on_click=_open,
                        height=34,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=tokens.ICON_SM,
                        tooltip="Dismiss",
                        on_click=_dismiss,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_SM,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, theme.ok()),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, theme.ok())),
            padding=tokens.SPACE_SM,
            border_radius=tokens.RADIUS_MD,
        )

    if state.installing:

        def _open_modal(_e) -> None:
            state.install_dialog_minimized = False
            show_install_progress_modal(page, state.installing or "container")

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.ProgressRing(width=18, height=18, stroke_width=2),
                    ft.Column(
                        controls=[
                            ft.Text(
                                f"Installing {state.installing}…",
                                size=tokens.FONT_SM,
                                weight=ft.FontWeight.BOLD,
                                color=theme.text(),
                            ),
                            ft.Text(
                                state.install_stage or "Downloading layers…",
                                size=tokens.FONT_XS,
                                color=theme.text_dim(),
                                max_lines=1,
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    ft.TextButton(
                        "View Output",
                        icon=ft.Icons.VISIBILITY_ROUNDED,
                        on_click=_open_modal,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=tokens.SPACE_SM,
            ),
            bgcolor=theme.glass_bg(),
            border=ft.Border.all(1, theme.primary()),
            padding=tokens.SPACE_SM,
            border_radius=tokens.RADIUS_MD,
        )

    return None
