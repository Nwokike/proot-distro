"""Shared widgets for the display sheets."""

from __future__ import annotations

import asyncio
import logging

import flet as ft

from core import layout, theme, tokens
from core.state import state

logger = logging.getLogger(__name__)

# Probed guest apps for the "Open an app" sheet: (label, command) pairs.
_APP_PRESETS = (
    ("Terminal", "xterm"),
    ("Files", "thunar"),
    ("Browser", "firefox"),
    ("Text editor", "mousepad"),
    ("Image editor", "gimp"),
    ("Office", "libreoffice"),
    ("VS Code", "code"),
)

_CUSTOM = "__custom__"


def _sheet_width(page: ft.Page) -> int:
    """Responsive dialog width (one definition: core.layout)."""
    return layout.sheet_size(page)[0]


def _dialog_height(page: ft.Page) -> int:
    """Bounded sheet height so tall options scroll instead of overflowing."""
    return layout.sheet_size(page)[1]


async def _stream_session_log(page: ft.Page, ctrl, container: str) -> None:
    """Tail the newest starting session's log into a command cell (worker-safe:
    log_tail is a thread deque; reads are fine from the event loop)."""

    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "desk_manager", None)
    seen = 0
    while True:
        session = None
        if manager is not None:
            # StrEnum compares equal to its string value directly — no need to
            # go through the enum's name attribute (the house guard flags that
            # spelling as imperative-mutation syntax).
            starting = [s for s in manager.for_container(container) if s.status == "starting"]
            session = starting[0] if starting else None
        if session is not None:
            lines = list(session.log_tail)
            for line in lines[seen:]:
                ctrl.append_output(line)
            seen = len(lines)
        elif state.display_status != "starting":
            break  # the start is over (running/error) — no more polls
        await asyncio.sleep(0.4)


def _status_line(caps: dict) -> ft.Control:
    """The sheet's status dot — the display runs in the app, so it is always
    ready; the probed facts only matter to a full desktop session."""
    os_name = (caps.get("os") or {}).get("pretty_name", "") or "unknown distro"
    return ft.Row(
        controls=[
            ft.Container(
                width=tokens.STATUS_DOT_SM,
                height=tokens.STATUS_DOT_SM,
                border_radius=50,
                bgcolor=theme.ok(),
            ),
            ft.Text(f"X11 display ready · {os_name}", size=tokens.FONT_SM, color=theme.text_dim()),
        ],
        spacing=tokens.SPACE_XS,
    )


def _pill_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL))


def _set_setting(key: str, value: object) -> None:
    state.display_settings = {**(state.display_settings or {}), key: value}


def _picker_with_custom(
    label: str,
    options: tuple[tuple[str, str], ...],
    key: str,
    *,
    hint: str,
) -> ft.Control:
    """Dropdown + a Custom… option that reveals a free-text field — the
    upstream value ranges are ranges, not our presets."""
    settings = state.display_settings or {}
    current = str(settings.get(key, options[0][0]))
    is_custom = current not in {v for v, _t in options}
    custom_field = ft.TextField(
        label=f"{label} (custom)",
        hint_text=hint,
        value=current if is_custom else "",
        width=tokens.DROPDOWN_WIDTH,
        height=tokens.CONTROL_SM,
        text_size=tokens.FONT_XS,
        visible=is_custom,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        on_change=lambda e: _set_setting(key, e.control.value or ""),
    )
    dropdown = ft.Dropdown(
        label=label,
        value=(_CUSTOM if is_custom else current),
        options=[ft.dropdown.Option(v, t) for v, t in options]
        + [ft.dropdown.Option(_CUSTOM, "Custom…")],
        on_select=lambda e: _set_setting(
            key, e.control.value if e.control.value != _CUSTOM else custom_field.value or current
        ),
        width=tokens.DROPDOWN_WIDTH,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        text_size=tokens.FONT_XS,
    )
    return ft.Column(controls=[dropdown, custom_field], spacing=tokens.SPACE_XXS, tight=True)


def _switch_row(label: str, key: str, default: bool) -> ft.Switch:
    return ft.Switch(
        label=label,
        value=bool((state.display_settings or {}).get(key, default)),
        on_change=lambda e: _set_setting(key, bool(e.control.value)),
    )
