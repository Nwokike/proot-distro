"""Install progress modal and sticky banner — real-time distro installation progress.

Provides a live progress modal with streaming log output, a 'Run in Background'
option, and a sticky top-of-page banner for ongoing and completed installs.
"""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.state import state

logger = logging.getLogger(__name__)


def show_install_progress_modal(page: ft.Page, target: str) -> None:
    """Open the modal dialog displaying real-time install progress."""
    logs_column = ft.Column(
        controls=[
            ft.Text(
                line,
                font_family=tokens.MONO_FONT,
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
            for line in state.install_logs[-60:]
        ],
        spacing=tokens.SPACE_NANO,
        scroll=ft.ScrollMode.AUTO,
        height=tokens.LOG_BOX_HEIGHT,
    )

    stage_text = ft.Text(
        state.install_stage or "Preparing download…",
        size=tokens.FONT_SM,
        weight=ft.FontWeight.W_500,
        color=theme.text(),
        expand=True,
    )

    progress_ring = ft.ProgressRing(
        width=tokens.PROGRESS_RING_MD,
        height=tokens.PROGRESS_RING_MD,
        stroke_width=tokens.PROGRESS_RING_STROKE_THIN,
    )

    status_row = ft.Row(
        controls=[progress_ring, stage_text],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    log_box = ft.Container(
        content=logs_column,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
        border=ft.Border.all(tokens.HAIRLINE, theme.surface_alt()),
        border_radius=tokens.RADIUS_SM,
        padding=tokens.SPACE_SM,
    )

    def _minimize(_e) -> None:
        state.install_dialog_minimized = True
        page.pop_dialog()
        _clear_install_controls()

    def _clear_install_controls() -> None:
        if getattr(page, "_install_dialog", None) is dialog:
            page._install_dialog = None
            page._install_stage_text = None
            page._install_logs_column = None

    def _on_dismiss(_e) -> None:
        _clear_install_controls()

    dialog = ft.AlertDialog(
        modal=True,
        on_dismiss=_on_dismiss,
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


def show_display_install_modal(page: ft.Page, target: str) -> None:
    """Desktop-install progress modal — the EXACT distro-install pattern:
    page-stored control refs that display_actions.install_display_support
    updates on every streamed chunk, so output moves live with zero
    close/reopen (owner ruling: copy the distro install flow verbatim)."""
    logs_column = ft.Column(
        controls=[],
        spacing=tokens.SPACE_NANO,
        scroll=ft.ScrollMode.AUTO,
        height=tokens.LOG_BOX_HEIGHT,
    )

    stage_text = ft.Text(
        "Preparing install…",
        size=tokens.FONT_SM,
        weight=ft.FontWeight.W_500,
        color=theme.text(),
        expand=True,
    )

    status_row = ft.Row(
        controls=[
            ft.ProgressRing(
                width=tokens.PROGRESS_RING_MD,
                height=tokens.PROGRESS_RING_MD,
                stroke_width=tokens.PROGRESS_RING_STROKE_THIN,
            ),
            stage_text,
        ],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    log_box = ft.Container(
        content=logs_column,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
        border=ft.Border.all(tokens.HAIRLINE, theme.surface_alt()),
        border_radius=tokens.RADIUS_SM,
        padding=tokens.SPACE_SM,
    )

    def _clear_install_controls() -> None:
        if getattr(page, "_display_install_dialog", None) is dialog:
            page._display_install_dialog = None
            page._display_install_stage_text = None
            page._display_install_logs_column = None

    def _on_dismiss(_e) -> None:
        _clear_install_controls()

    dialog = ft.AlertDialog(
        modal=True,
        on_dismiss=_on_dismiss,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=theme.primary(), size=tokens.ICON_MD),
                ft.Text(
                    f"Installing desktop — {target}",
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
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
                "Close",
                on_click=lambda _e: (page.pop_dialog(), _clear_install_controls()),
            )
        ],
    )
    page._display_install_stage_text = stage_text
    page._display_install_logs_column = logs_column
    page._display_install_dialog = dialog
    page.show_dialog(dialog)


def repaint_display_install(page: ft.Page, container: str) -> None:
    """Live update from the installer's chunk callback — the distro
    _apply_line pattern: set the stage line, rebuild the log rows from
    state, then .update() the stored controls."""
    stage_ctrl = getattr(page, "_display_install_stage_text", None)
    logs_ctrl = getattr(page, "_display_install_logs_column", None)
    if stage_ctrl is None and logs_ctrl is None:
        return
    if stage_ctrl is not None:
        stage_ctrl.value = f"installing desktop in {container}…"
        stage_ctrl.update()
    if logs_ctrl is not None:
        from core import tokens as _t

        logs_ctrl.controls = [
            ft.Text(
                line.rstrip(),
                font_family=_t.MONO_FONT,
                size=_t.FONT_XXS,
                color=theme.text_dim(),
            )
            for line in (state.display_install_logs or [])[-60:]
            if line.strip()
        ]
        logs_ctrl.update()
    dialog = getattr(page, "_display_install_dialog", None)
    if dialog is not None and getattr(dialog, "open", False):
        try:
            dialog.update()
        except RuntimeError:
            pass


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
                        height=tokens.CONTROL_SM,
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
            bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.ok()),
            border=ft.Border.all(
                tokens.HAIRLINE, ft.Colors.with_opacity(tokens.OPACITY_BORDER, theme.ok())
            ),
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
                    ft.ProgressRing(
                        width=tokens.PROGRESS_RING_SM,
                        height=tokens.PROGRESS_RING_SM,
                        stroke_width=tokens.PROGRESS_RING_STROKE,
                    ),
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
                        spacing=tokens.SPACE_NONE,
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
            border=ft.Border.all(tokens.HAIRLINE, theme.primary()),
            padding=tokens.SPACE_SM,
            border_radius=tokens.RADIUS_MD,
        )

    return None


def show_run_dialog(page: ft.Page, container: str, args_text: str) -> None:
    """Live output dialog for a `run` one-shot command (PTY-captured)."""
    from core import tokens as _t

    output_column = ft.Column(
        controls=(
            [
                ft.Text(
                    state.run_output[-4000:],
                    font_family=_t.MONO_FONT,
                    size=_t.FONT_XXS,
                    color=theme.text_dim(),
                    selectable=True,
                )
            ]
            if state.run_output
            else []
        ),
        spacing=tokens.SPACE_NANO,
        scroll=ft.ScrollMode.AUTO,
        height=tokens.LOG_BOX_HEIGHT,
    )
    stage_text = ft.Text(
        state.run_status or "starting…",
        size=tokens.FONT_SM,
        weight=ft.FontWeight.W_500,
        color=theme.text(),
        expand=True,
    )
    status_row = ft.Row(
        controls=[
            ft.ProgressRing(
                width=tokens.PROGRESS_RING_MD,
                height=tokens.PROGRESS_RING_MD,
                stroke_width=tokens.PROGRESS_RING_STROKE_THIN,
            )
            if state.run_busy
            else ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.primary(), size=tokens.ICON_MD),
            stage_text,
        ],
        spacing=tokens.SPACE_MD,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    log_box = ft.Container(
        content=output_column,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
        border=ft.Border.all(tokens.HAIRLINE, theme.surface_alt()),
        border_radius=tokens.RADIUS_SM,
        padding=tokens.SPACE_SM,
    )
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.PLAY_CIRCLE_ROUNDED, color=theme.primary(), size=tokens.ICON_MD),
                ft.Text(
                    f"Run in {container}" + (f" — {args_text}" if args_text else ""),
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            spacing=tokens.SPACE_SM,
        ),
        content=ft.Column(
            controls=[status_row, log_box],
            spacing=tokens.SPACE_MD,
            tight=True,
            width=tokens.DIALOG_WIDTH,
        ),
        actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
    )
    page._run_stage_text = stage_text
    page._run_output_column = output_column
    page._run_dialog = dialog
    page.show_dialog(dialog)
