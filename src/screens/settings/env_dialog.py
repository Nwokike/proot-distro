"""Guest-default environment dialog — CollabShell's env editor, mirrored.

Row shape (components/env_dialog.py there): masked VALUE with reveal, a caption
line with Remove, a validation error, and Add row / Clear / Cancel / Save.
Draft rows live on the page so Add/Remove reopen with every typed value intact
(the frozen-controls rule forbids mutating a mounted dialog's column).
"""

from __future__ import annotations

import contextlib
import re

import flet as ft

from components.ui import house_field
from core import theme, tokens
from core.state import state

_ENV_KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_DRAFT_ATTR = "_env_draft"


def env_rows_summary() -> str:
    """The row's live value: how many defaults are set."""
    count = len(state.env_defaults or {})
    if not count:
        return "No default variables"
    return f"{count} variable{'s' if count != 1 else ''} set"


def open_env_dialog(page: ft.Page, methods=None) -> None:
    """Manage the KEY=VALUE defaults injected into every new shell and display."""
    with contextlib.suppress(Exception):
        page.pop_dialog()

    draft = getattr(page, _DRAFT_ATTR, None)
    if draft is None:
        draft = [(str(k), str(v)) for k, v in (state.env_defaults or {}).items()]
        setattr(page, _DRAFT_ATTR, draft)

    def _reopen(rows: list[tuple[str, str]] | None = None) -> None:
        if rows is not None:
            setattr(page, _DRAFT_ATTR, rows)
        open_env_dialog(page, methods)

    def _row(index: int, key: str, value: str) -> ft.Control:
        key_field = house_field(label="KEY", value=key, expand=True)
        value_field = house_field(
            label="VALUE", value=value, expand=True, password=True, can_reveal_password=True
        )

        def _store(_e=None) -> None:
            rows = list(getattr(page, _DRAFT_ATTR) or [])
            if index < len(rows):
                rows[index] = ((key_field.value or "").strip(), value_field.value or "")
                setattr(page, _DRAFT_ATTR, rows)

        key_field.on_blur = _store
        key_field.on_submit = _store
        value_field.on_blur = _store
        value_field.on_submit = _store

        def _remove(_e) -> None:
            _store()
            rows = list(getattr(page, _DRAFT_ATTR) or [])
            _reopen([pair for i, pair in enumerate(rows) if i != index])

        return ft.Column(
            controls=[
                ft.Row(controls=[key_field, value_field], spacing=tokens.SPACE_SM),
                ft.Row(
                    controls=[
                        ft.Text(
                            "Injected into every new shell and display",
                            size=tokens.FONT_XXS,
                            color=theme.text_dim(),
                            italic=True,
                        ),
                        ft.Container(expand=True),
                        ft.TextButton("Remove", on_click=_remove),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
            ],
            spacing=tokens.SPACE_XXS,
        )

    def _add(_e=None) -> None:
        rows = list(getattr(page, _DRAFT_ATTR) or [])
        _reopen([*rows, ("", "")])

    def _clear(_e=None) -> None:
        _reopen([])

    def _cancel(_e=None) -> None:
        setattr(page, _DRAFT_ATTR, None)
        page.pop_dialog()

    def _save(_e=None) -> None:
        parsed: dict[str, str] = {}
        for key, value in getattr(page, _DRAFT_ATTR) or []:
            name = (key or "").strip()
            if not name and not value:
                continue
            if "=" in name or not _ENV_KEY_RE.fullmatch(name):
                # Report through the page snack (never mutate the open dialog).
                from components.snack import show_snack

                show_snack(
                    page,
                    f"Invalid key {name!r}: letters, digits and _ only, "
                    "and it cannot start with a digit.",
                )
                return
            parsed[name] = value
        setattr(page, _DRAFT_ATTR, None)
        page.pop_dialog()
        if methods is not None:
            page.run_task(methods.save_env_defaults, parsed)

    body = ft.Column(
        controls=[_row(i, k, v) for i, (k, v) in enumerate(draft)],
        spacing=tokens.SPACE_MD,
        tight=True,
        scroll=ft.ScrollMode.AUTO,
    )

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=ft.Text("Default environment", weight=ft.FontWeight.W_700),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(
                            "Injected into every shell and every app or display you "
                            "launch. The display's own DISPLAY/XAUTHORITY always win.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                        ),
                        body
                        if body.controls
                        else ft.Text(
                            "No default variables yet.",
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                            italic=True,
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                    tight=True,
                ),
                width=tokens.DIALOG_WIDTH,
            ),
            actions=[
                ft.TextButton("Add row", on_click=_add),
                ft.TextButton("Clear", on_click=_clear),
                ft.TextButton("Cancel", on_click=_cancel),
                ft.FilledButton(
                    "Save",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
    )
