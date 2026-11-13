"""Desktop-install progress card — the CollabShell NotebookCell mechanism
copied exactly for the display flow.

`DisplayProgress` (core/state.py) is a small @ft.observable model passed as
this component's ARGUMENT; every mutation (logs reassignment + rev bump)
re-renders the card reactively — no refs, no manual update(), no reliance on
the global AppState subscription. The output body hands the reconciler a
FRESH list each render (mutating the rendered list in place makes old == new
in the diff and new lines would never paint — the notebook lesson).

Header: spinner + "installing desktop in X…" + collapse/expand chevrons
(owner request). Expanded shows the streaming OUTPUT panel (auto-scroll
ListView, dynamic height); collapsed shows just the header line.
"""

from __future__ import annotations

import flet as ft

from components import card
from core import theme, tokens
from core.state import DisplayProgress


@ft.component
def DisplayProgressCard(
    progress: DisplayProgress,
    on_cancel=None,
) -> ft.Control:
    """One reactive card for the running desktop install."""
    page = ft.context.page
    expanded, set_expanded = ft.use_state(True)

    def _copy_output(e=None) -> None:
        # The ONE app-wide Clipboard (mounted by shared_services) — a fresh
        # ft.Clipboard() is an unmounted Service and its set() raises.
        clipboard = getattr(page, "clipboard", None)
        if clipboard is None:
            return
        page.run_task(clipboard.set, "\n".join(progress.logs))

    # Incremental body: only render the tail, fresh list every time.
    lines = list(progress.logs[-60:])
    body = ft.ListView(
        controls=[
            ft.Text(
                ln,
                font_family=tokens.MONO_FONT,
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
            for ln in lines
        ],
        spacing=tokens.SPACE_XXS,
        auto_scroll=True,
        height=min(max(len(lines) * 18 + 8, 36), 220),
        expand=False,
    )

    header = ft.Row(
        controls=[
            ft.ProgressRing(
                width=tokens.PROGRESS_RING_MD,
                height=tokens.PROGRESS_RING_MD,
                stroke_width=3,
            ),
            ft.Text(
                f"installing desktop in {progress.container}…"
                if progress.container
                else "installing desktop…",
                size=tokens.FONT_SM,
                weight=ft.FontWeight.W_600,
                color=theme.text(),
                expand=True,
            ),
            # Collapse / expand chevrons (owner request).
            ft.IconButton(
                ft.Icons.EXPAND_LESS_ROUNDED if expanded else ft.Icons.EXPAND_MORE_ROUNDED,
                icon_size=tokens.ICON_MD,
                tooltip="Collapse" if expanded else "Expand",
                on_click=lambda _e: set_expanded(not expanded),
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=tokens.SPACE_SM,
    )

    actions = ft.Row(
        controls=[
            ft.Text(
                "OUTPUT",
                size=tokens.FONT_XXS,
                color=ft.Colors.with_opacity(0.5, theme.text()),
                weight=ft.FontWeight.W_600,
            ),
            ft.Row(
                controls=[
                    ft.IconButton(
                        ft.Icons.COPY_ALL_ROUNDED,
                        icon_size=tokens.ICON_SM,
                        tooltip="Copy Output",
                        on_click=_copy_output,
                    ),
                    ft.IconButton(
                        ft.Icons.STOP_CIRCLE_ROUNDED,
                        icon_size=tokens.ICON_SM,
                        icon_color=theme.warn(),
                        tooltip="Stop install",
                        on_click=lambda _e: on_cancel() if on_cancel else None,
                        visible=progress.is_running,
                    ),
                ],
                spacing=0,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    output_panel = ft.Container(
        content=ft.Column(controls=[body, actions], spacing=tokens.SPACE_XXS),
        padding=tokens.SPACE_SM,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
        border_radius=tokens.RADIUS_SM,
        width=float("inf"),
    )

    return card(
        ft.Column(
            controls=[header, ft.Container(content=output_panel, visible=expanded)],
            spacing=tokens.SPACE_SM,
        ),
        padding=tokens.SPACE_SM,
    )
