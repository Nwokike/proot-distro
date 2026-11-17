"""Row builders for the Display tab's Running and Failed sections.

Split out of display_view.py (file-size rule): these are pure builders that
receive the page and the controller methods, so the view's component body stays
small while the row shapes (immediate "stopping…", crash honesty with Retry and
Dismiss) stay in one place.
"""

from __future__ import annotations

import flet as ft

from components import card
from core import theme, tokens
from services.desk_service import DeskStatus


def session_rows(sessions: list, *, page, methods) -> list[ft.Control]:
    """One card per live session: key, port, Open, and the session menu."""
    rows = []
    for session in sessions:
        # An app display runs one command; a bare display is the X server
        # started from a terminal. The row icon says which.
        row_icon = (
            ft.Icons.DESKTOP_WINDOWS if session.mode == "display" else ft.Icons.WINDOW_ROUNDED
        )
        stopping = session.status is DeskStatus.STOPPING

        def _resume(_e, key=session.key) -> None:
            page.run_task(methods.resume_display, key)

        def _stop(_e, key=session.key) -> None:
            page.run_task(methods.stop_display, key)

        if stopping:
            # Immediate feedback while the stop runs — the row is removed
            # by the next transition notification once it completes.
            row_controls = [
                ft.ProgressRing(width=tokens.PROGRESS_RING_MD, height=tokens.PROGRESS_RING_MD),
                ft.Text(
                    session.key,
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.W_600,
                    color=theme.text(),
                    expand=True,
                ),
                ft.Text("stopping…", size=tokens.FONT_SM, color=theme.text_dim()),
            ]
        else:
            row_controls = [
                ft.Icon(row_icon, size=tokens.ICON_MD, color=theme.ok()),
                ft.Text(
                    session.key,
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.W_600,
                    color=theme.text(),
                    expand=True,
                ),
                ft.Text(
                    f"port {session.port}",
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                ),
                ft.FilledButton(
                    "Open",
                    on_click=_resume,
                    height=tokens.CONTROL_MD,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="More",
                    items=[
                        ft.PopupMenuItem(
                            content=ft.Text("Share"),
                            on_click=lambda _e, k=session.key: page.run_task(
                                methods.share_display, k
                            ),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("Logs"),
                            on_click=lambda _e, k=session.key: page.run_task(
                                methods.show_display_logs, k
                            ),
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("Stop"),
                            on_click=_stop,
                        ),
                    ],
                ),
            ]
        rows.append(
            card(
                ft.Container(
                    content=ft.Row(
                        # No wrap: a Row with an expand child inside a Wrap
                        # is the Expanded-in-Wrap layout bug (the row
                        # scattered its actions). The title flexes instead.
                        controls=row_controls,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                    on_click=None if stopping else _resume,
                    ink=not stopping,
                ),
                padding=tokens.SPACE_SM,
            )
        )
    return rows


def failed_rows(sessions: list, *, page, methods) -> list[ft.Control]:
    """Crash honesty: a failed display is a VISIBLE row — what happened,
    its log, a same-shape Retry, and a Dismiss (never silent; device
    audit 2026-11-13: crashed rows used to vanish without a word)."""
    rows = []
    for session in sessions:

        def _retry(_e, s=session) -> None:
            page.run_task(methods.retry_display, s.key)

        def _logs(_e, key=session.key) -> None:
            page.run_task(methods.show_display_logs, key)

        def _dismiss(_e, key=session.key) -> None:
            page.run_task(methods.stop_display, key)

        rows.append(
            card(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.ERROR_OUTLINE,
                                size=tokens.ICON_MD,
                                color=theme.warn(),
                            ),
                            ft.Column(
                                controls=[
                                    ft.Text(
                                        session.key,
                                        size=tokens.FONT_LG,
                                        weight=ft.FontWeight.W_600,
                                        color=theme.text(),
                                    ),
                                    ft.Text(
                                        session.error or "the display failed",
                                        size=tokens.FONT_XS,
                                        color=theme.text_dim(),
                                        max_lines=tokens.MAX_LINES_TWO,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=tokens.SPACE_XXS,
                                expand=True,
                            ),
                            ft.TextButton("Logs", on_click=_logs),
                            ft.TextButton("Retry", on_click=_retry),
                            ft.IconButton(
                                icon=ft.Icons.CLOSE_ROUNDED,
                                icon_color=theme.warn(),
                                tooltip="Dismiss (stop the failed display)",
                                on_click=_dismiss,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=tokens.SPACE_SM,
                    ),
                ),
                padding=tokens.SPACE_SM,
            )
        )
    return rows
