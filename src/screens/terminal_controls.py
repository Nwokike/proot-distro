"""Shared terminal input, theme, and close-dialog controls."""

from __future__ import annotations

import signal

import flet as ft

from core import theme, tokens
from services.session_manager import SessionEntry

_THEME_PRESETS = ("JetBrains Dark", "Dracula", "Matrix Green", "Colab Light")


def _theme_name() -> str:
    """Terminal theme follows the app's light/dark mode (CollabShell pattern)."""
    return "Colab Light" if theme.is_light_theme() else "JetBrains Dark"


def _write(entry: SessionEntry, payload: bytes) -> None:
    if entry.session is not None:
        entry.session.write(payload)


# Job-control bytes the PTY line discipline would normally turn into signals.
# The session child setsids in preexec_fn and takes the slave as its
# controlling tty, but the bytes are delivered to the session's process group
# directly anyway so Ctrl-C/Ctrl-\/Ctrl-Z always reach proot + guests.
_SIGNAL_FOR_BYTE = {
    0x03: signal.SIGINT,  # Ctrl-C
    0x1C: signal.SIGQUIT,  # Ctrl-backslash
    0x1A: signal.SIGTSTP,  # Ctrl-Z
}


def _input(entry: SessionEntry, payload: bytes) -> None:
    """Terminal input: job-control bytes become killpg signals, the rest go to the PTY."""
    session = entry.session
    if session is None:
        return
    out = bytearray()
    for b in payload:
        sig = _SIGNAL_FOR_BYTE.get(b)
        if sig is not None:
            session.send_signal(sig)
        else:
            out.append(b)
    if out:
        session.write(bytes(out))


def _compact_btn_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        padding=ft.Padding(tokens.SPACE_XS, tokens.SPACE_XS, tokens.SPACE_XS, tokens.SPACE_XS),
        visual_density=ft.VisualDensity.COMPACT,
    )


def _cycle_terminal_theme(mt) -> None:
    """Cycle the terminal through the preset themes (switcher-row palette button)."""
    cur = getattr(mt, "theme_name", None) or _theme_name()
    idx = _THEME_PRESETS.index(cur) if cur in _THEME_PRESETS else 0
    mt.set_theme(_THEME_PRESETS[(idx + 1) % len(_THEME_PRESETS)])


def _confirm_close(page: ft.Page, methods, session_key: str, title: str = "") -> None:
    def _yes(_e) -> None:
        page.pop_dialog()
        page.run_task(methods.close_session, session_key)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Close {title or session_key}?",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Text(
                "The shell is terminated; unsaved work inside it is lost.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Close",
                    on_click=_yes,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )
