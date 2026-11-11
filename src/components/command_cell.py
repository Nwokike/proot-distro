"""Command cell — a faithful copy of CollabShell's notebook code cell
(components/notebook_cell): editable mono input + Run/Stop row + an OUTPUT
panel (dark bg, auto-scrolling ListView, dynamic height, COPY/CLEAR actions)
inside the left-accent-border container.

Built as PLAIN controls with a controller object (refs + .update()) because
the sheets that host it are opened imperatively — constructing a @ft.component
outside a render raises "No current renderer" (device-proven). The visual and
the mechanism are the notebook's; only the plumbing differs.
"""

from __future__ import annotations

import flet as ft

from core import theme, tokens


class CommandCellController:
    """Drives one cell: source edits, running state, streamed output."""

    def __init__(
        self,
        page: ft.Page,
        editor: ft.TextField,
        output_list: ft.ListView,
        output_panel: ft.Container,
        run_row: ft.Row,
        stop_row: ft.Row,
    ):
        self._page = page
        self._editor = editor
        self._output_list = output_list
        self._output_panel = output_panel
        self._run_row = run_row
        self._stop_row = stop_row
        self._lines: list[str] = []
        self.running = False

    # ── state ────────────────────────────────────────────────────────────────

    def source(self) -> str:
        return self._editor.value or ""

    def set_source(self, text: str) -> None:
        self._editor.value = text
        try:
            self._editor.update()
        except Exception:
            pass

    def set_running(self, running: bool) -> None:
        self.running = running
        self._run_row.visible = not running
        self._stop_row.visible = running
        try:
            self._run_row.update()
            self._stop_row.update()
        except Exception:
            pass

    # ── output ───────────────────────────────────────────────────────────────

    def append_output(self, line: str) -> None:
        """Stream one line (call via the page loop from worker threads)."""
        clean = line.rstrip()
        if not clean:
            return
        self._lines.append(clean)
        if len(self._lines) > 400:
            self._lines = self._lines[-400:]
        self._output_list.controls = [
            ft.Text(
                ln,
                font_family=tokens.MONO_FONT,
                size=tokens.FONT_XXS,
                color=theme.text_dim(),
            )
            for ln in self._lines[-200:]
        ]
        # Dynamic height, CollabShell's 36..220 clamp.
        self._output_list.height = min(max(len(self._output_list.controls) * 18 + 8, 36), 220)
        self._output_panel.visible = True
        try:
            self._output_list.update()
            self._output_panel.update()
        except Exception:
            pass

    def clear_output(self) -> None:
        self._lines = []
        self._output_list.controls = []
        self._output_list.height = 36
        self._output_panel.visible = False
        try:
            self._output_list.update()
            self._output_panel.update()
        except Exception:
            pass

    def output_text(self) -> str:
        return "\n".join(self._lines)


def build_command_cell(
    page: ft.Page,
    *,
    source: str = "",
    hint: str = "",
    on_run,
    on_stop=None,
    label: str | None = None,
) -> tuple[ft.Container, CommandCellController]:
    """Build the cell; return (control, controller). `on_run(source)` fires on
    Play; `on_stop()` on Stop. Visual copy of CollabShell's code cell."""
    editor = ft.TextField(
        value=source,
        multiline=True,
        min_lines=1,
        max_lines=10,
        text_style=ft.TextStyle(font_family=tokens.MONO_FONT, size=tokens.FONT_SM),
        border=ft.OutlineInputBorder(side=ft.BorderSide(color=ft.Colors.TRANSPARENT)),
        bgcolor=ft.Colors.TRANSPARENT,
        hint_text=hint,
        content_padding=tokens.SPACE_SM,
        expand=True,
    )
    controller = CommandCellController(page, editor, None, None, None, None)  # type: ignore[arg-type]

    def _fire_run(_e) -> None:
        on_run(controller)

    def _fire_stop(_e) -> None:
        if on_stop is not None:
            on_stop()

    run_row = ft.Row(
        controls=[
            ft.IconButton(
                ft.Icons.PLAY_ARROW_ROUNDED,
                icon_size=tokens.ICON_MD,
                icon_color=theme.ok(),
                on_click=_fire_run,
                tooltip=label or "Run",
            ),
            ft.Container(expand=True),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    stop_row = ft.Row(
        controls=[
            ft.ProgressRing(width=tokens.ICON_SM, height=tokens.ICON_SM, stroke_width=2),
            ft.IconButton(
                ft.Icons.STOP_ROUNDED,
                icon_size=tokens.ICON_SM,
                icon_color=theme.warn(),
                on_click=_fire_stop,
                tooltip="Stop",
            ),
            ft.Container(expand=True),
        ],
        spacing=tokens.SPACE_XS,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        visible=False,
    )

    output_list = ft.ListView(
        controls=[],
        spacing=tokens.SPACE_XXS,
        auto_scroll=True,
        height=36,
        expand=False,
    )
    output_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
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
                                    on_click=lambda _e: page.run_task(
                                        ft.Clipboard().set, controller.output_text()
                                    ),
                                ),
                                ft.IconButton(
                                    ft.Icons.CLEAR_ALL_ROUNDED,
                                    icon_size=tokens.ICON_SM,
                                    tooltip="Clear Output",
                                    on_click=lambda _e: controller.clear_output(),
                                ),
                            ],
                            spacing=0,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                output_list,
            ],
            spacing=tokens.SPACE_XXS,
        ),
        padding=tokens.SPACE_SM,
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_TEXT_HINT, theme.text()),
        border_radius=tokens.RADIUS_SM,
        visible=False,
        width=float("inf"),
    )
    controller._output_list = output_list
    controller._output_panel = output_panel
    controller._run_row = run_row
    controller._stop_row = stop_row

    cell = ft.Container(
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            editor,
                            ft.Container(
                                content=ft.Row([run_row, stop_row]),
                                padding=ft.Padding(
                                    tokens.SPACE_XS, 0, tokens.SPACE_SM, tokens.SPACE_XS
                                ),
                            ),
                        ],
                        spacing=0,
                    ),
                    border_radius=tokens.RADIUS_SM,
                    bgcolor=ft.Colors.with_opacity(0.03, theme.text()),
                ),
                ft.Container(
                    content=output_panel,
                    padding=ft.Padding(0, tokens.SPACE_XS, 0, 0),
                ),
            ],
            spacing=0,
        ),
        padding=tokens.SPACE_SM,
        border=ft.Border(left=ft.BorderSide(3, theme.primary())),
        margin=ft.Margin(0, tokens.SPACE_SM, 0, tokens.SPACE_SM),
    )
    return cell, controller
