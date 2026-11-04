"""The desktop view — the TermuxDesk display surface, shown full-screen in the app.

Mirrors TerminalView's takeover: app_shell hides its chrome while a display
runs and this view owns the screen. The WebView is created ONCE per session
and stored on the session object (`session.wv`) — rebuilding it per render
would reload the viewer and, under flet 1.1, mutating mounted controls
mid-patch raises the frozen-control error.

Auto-authentication: TermuxDesk's viewer shows a 6-char access-code overlay
before the WebSocket connects. The server writes the code to a rootfs file
the manager reads; after `page_started` this view injects it via
`run_javascript` (set the input value, click the connect button) — the
overlay never blocks the user. `run_javascript` is async, and flet awaits
async event handlers (base_control checks iscoroutinefunction), so the
handler is a coroutine.

Host↔guest input bridges (no upstream fork — they drive the viewer's own
public surface): the viewer listens for window keydown/keyup and exposes
`#pasteButton`/`#authInput`, so a touchscreen keyboard strip dispatches
synthetic KeyboardEvents and the host clipboard lands in the guest by
writing navigator.clipboard then clicking the viewer's Paste button.
"""

from __future__ import annotations

import json

import flet as ft

try:
    from flet_webview import WebView

    _HAS_WEBVIEW = True
except ImportError:
    # Desktop preview (`flet run`) has no mobile WebView — render a placeholder
    # pane instead of dying at import (same guard as TerminalView).
    WebView = None
    _HAS_WEBVIEW = False

from core import theme, tokens
from core.state import state
from state.controller_ctx import ControllerMethodsCtx


def auth_js(code: str) -> str:
    """Fill the viewer's access-code overlay and connect (one statement pair).

    setAttribute('value', …) sets the live input value too — the overlay
    input is pristine (fresh page, untouched), so the IDL value reflects the
    attribute (no dirty-value flag)."""
    return (
        "document.querySelector('#authInput')"
        f".setAttribute('value', {json.dumps(code)});"
        "document.querySelector('#authButton').click();"
    )


def key_event_js(event: str, key: str) -> str:
    """Dispatch one synthetic KeyboardEvent on window — exactly what the
    viewer's own keydown/keyup listeners receive from a hardware keyboard."""
    return (
        f"window.dispatchEvent(new KeyboardEvent({json.dumps(event)},{{key:{json.dumps(key)}}}));"
    )


def press_js(key: str) -> str:
    """A full key press (down + up) — special keys and characters alike.
    Sticky modifiers are separate: toggling Ctrl dispatches only the
    keydown/keyup of 'Control' so the guest sees the modifier held, like a
    real keyboard."""
    return key_event_js("keydown", key) + key_event_js("keyup", key)


def paste_js(text: str) -> str:
    """Host clipboard → guest: write the text into the WebView's
    navigator.clipboard, then click the viewer's Paste button, which sends
    it to the X11 clipboard via xclip."""
    return (
        f"navigator.clipboard.writeText({json.dumps(text)}).then("
        "() => document.querySelector('#pasteButton').click());"
    )


@ft.component
def DesktopView(session) -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    st, _ = ft.use_state(state)
    kb_on, set_kb_on = ft.use_state(False)
    ctrl_on, set_ctrl_on = ft.use_state(False)
    alt_on, set_alt_on = ft.use_state(False)
    kb_text, set_kb_text = ft.use_state("")
    controller = getattr(page, "_controller", None)
    clipboard = getattr(controller, "clipboard", None)

    # ── starting / stopping ───────────────────────────────────────────────────
    if st.display_status in ("starting", "stopping"):
        return ft.Column(
            controls=[
                ft.ProgressRing(width=36, height=36, stroke_width=3),
                ft.Text(st.display_status_text or "Starting display…", size=tokens.FONT_MD),
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Show logs",
                            on_click=lambda _e: page.run_task(
                                methods.show_display_logs, session.container
                            ),
                        ),
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda _e: page.run_task(
                                methods.stop_display, session.container
                            ),
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_MD,
            expand=True,
        )

    # ── error ─────────────────────────────────────────────────────────────────
    if st.display_status == "error":
        tail = "\n".join(list(session.log_tail)[-20:])
        return ft.Column(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=theme.warn()),
                ft.Text(st.display_error or "The display could not start.", size=tokens.FONT_MD),
                ft.Container(
                    content=ft.Text(
                        tail or "(no logs)",
                        font_family=tokens.MONO_FONT,
                        size=tokens.FONT_XXS,
                        color=theme.text_dim(),
                        selectable=True,
                    ),
                    width=tokens.DIALOG_WIDTH_LG,
                    height=160,
                ),
                ft.Row(
                    controls=[
                        ft.FilledButton(
                            "Retry",
                            on_click=lambda _e: page.run_task(
                                methods.start_display, session.container, None
                            ),
                        ),
                        ft.TextButton(
                            "Show logs",
                            on_click=lambda _e: page.run_task(
                                methods.show_display_logs, session.container
                            ),
                        ),
                        ft.TextButton(
                            "Back",
                            on_click=lambda _e: page.run_task(methods.leave_display),
                        ),
                    ],
                    spacing=tokens.SPACE_SM,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
            expand=True,
        )

    async def _run_js(js: str) -> None:
        """run_javascript is async — schedule it where a sync handler can't."""
        webview = session.wv
        if webview is None:
            return
        try:
            await webview.run_javascript(js)
        except Exception:
            pass

    # ── running: toolbar + WebView ───────────────────────────────────────────
    if session.wv is None and _HAS_WEBVIEW:

        def _on_resource_error(e) -> None:
            msg = str(getattr(e, "data", "") or "")
            if msg:
                session.log_tail.append(f"webview: {msg}")
                state.display_logs = list(session.log_tail)

        def _on_console(e) -> None:
            message = getattr(e, "message", "")
            if message:
                session.log_tail.append(f"console: {message}")
                state.display_logs = list(session.log_tail)

        async def _on_page_started(e) -> None:
            # Auto-authenticate: the viewer's overlay needs the 6-char access
            # code the server generated. Setting the input value and clicking
            # the button is the only way in — the auth logic lives inside the
            # viewer's closure and is deliberately not reachable from outside.
            code = session.code
            if not code or session.wv is None:
                return
            try:
                await session.wv.run_javascript(auth_js(code))
            except Exception:
                pass

        session.wv = WebView(
            url=st.display_url or session.url,
            expand=True,
            bgcolor=ft.Colors.BLACK,
            on_web_resource_error=_on_resource_error,
            on_console_message=_on_console,
            on_page_started=_on_page_started,
        )

    async def _paste_from_host(_e=None) -> None:
        if clipboard is None or session.wv is None:
            return
        try:
            text = await clipboard.get()
        except Exception:
            return
        if text:
            await _run_js(paste_js(text))

    def _toggle_modifier(current: bool, setter, key: str):
        def _handler(_e) -> None:
            next_on = not current
            setter(next_on)
            # Held-modifier semantics: keydown on engage, keyup on release —
            # the guest then sees Ctrl/Alt held for everything typed after.
            page.run_task(_run_js, key_event_js("keydown" if next_on else "keyup", key))

        return _handler

    toolbar_row = ft.Row(
        controls=[
            ft.IconButton(
                icon=ft.Icons.ARROW_BACK_ROUNDED,
                icon_size=tokens.ICON_MD,
                tooltip="Back (the display keeps running in the background)",
                on_click=lambda _e: page.run_task(methods.leave_display),
            ),
            ft.Text(
                session.container,
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
                color=theme.text(),
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.IconButton(
                icon=ft.Icons.CONTENT_PASTE_GO_ROUNDED,
                icon_size=tokens.ICON_MD,
                tooltip="Paste from this device into the desktop",
                on_click=lambda _e: page.run_task(_paste_from_host),
            ),
            ft.IconButton(
                icon=ft.Icons.KEYBOARD_ROUNDED,
                icon_size=tokens.ICON_MD,
                selected_icon=ft.Icons.KEYBOARD_HIDE_ROUNDED,
                selected=kb_on,
                tooltip="Type with the phone keyboard",
                on_click=lambda _e, v=not kb_on: set_kb_on(v),
            ),
            ft.IconButton(
                icon=ft.Icons.FULLSCREEN_EXIT_ROUNDED
                if st.display_fullscreen
                else ft.Icons.FULLSCREEN_ROUNDED,
                icon_size=tokens.ICON_MD,
                tooltip="Exit full screen" if st.display_fullscreen else "Full screen",
                on_click=lambda _e: page.run_task(
                    methods.set_display_fullscreen, not st.display_fullscreen
                ),
            ),
            ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT_ROUNDED,
                icon_size=tokens.ICON_MD,
                items=[
                    ft.PopupMenuItem(
                        content=ft.Text("Reload"),
                        on_click=lambda _e: page.run_task(_reload),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Share"),
                        on_click=lambda _e: page.run_task(methods.share_display, session.container),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Logs"),
                        on_click=lambda _e: page.run_task(
                            methods.show_display_logs, session.container
                        ),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Stop"),
                        on_click=lambda _e: page.run_task(methods.stop_display, session.container),
                    ),
                ],
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=tokens.SPACE_XS,
    )

    async def _reload(_e=None) -> None:
        if session.wv is not None:
            try:
                await session.wv.reload()
            except Exception:
                pass

    def _type_text(e) -> None:
        # Read-only: each keystroke's accumulated text is dispatched into the
        # guest and the field is reset via state (never mutate a mounted
        # control — frozen-control rule).
        text = getattr(e.control, "value", "") or ""
        if text:
            page.run_task(_run_js, "".join(press_js(ch) for ch in text))
            set_kb_text("")

    kb_field = ft.TextField(
        value=kb_text,
        hint_text="type here — it goes to the desktop",
        text_size=tokens.FONT_SM,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        on_change=_type_text,
    )
    keyboard_row = ft.Row(
        controls=[
            kb_field,
            ft.OutlinedButton(
                "⌫",
                height=tokens.CONTROL_SM,
                tooltip="Backspace",
                on_click=lambda _e: page.run_task(_run_js, press_js("Backspace")),
            ),
            ft.OutlinedButton(
                "Esc",
                height=tokens.CONTROL_SM,
                on_click=lambda _e: page.run_task(_run_js, press_js("Escape")),
            ),
            ft.OutlinedButton(
                "Tab",
                height=tokens.CONTROL_SM,
                on_click=lambda _e: page.run_task(_run_js, press_js("Tab")),
            ),
            ft.OutlinedButton(
                "Ctrl",
                height=tokens.CONTROL_SM,
                tooltip="Hold Ctrl for the next keys (press again to release)",
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                    side=ft.BorderSide(1, theme.primary() if ctrl_on else theme.surface_alt()),
                ),
                on_click=_toggle_modifier(ctrl_on, set_ctrl_on, "Control"),
            ),
            ft.OutlinedButton(
                "Alt",
                height=tokens.CONTROL_SM,
                tooltip="Hold Alt for the next keys (press again to release)",
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                    side=ft.BorderSide(1, theme.primary() if alt_on else theme.surface_alt()),
                ),
                on_click=_toggle_modifier(alt_on, set_alt_on, "Alt"),
            ),
            ft.OutlinedButton(
                "↵",
                height=tokens.CONTROL_SM,
                tooltip="Enter",
                on_click=lambda _e: page.run_task(_run_js, press_js("Enter")),
            ),
        ],
        spacing=tokens.SPACE_XS,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    keyboard_strip = ft.Container(
        content=ft.Column(
            controls=[
                keyboard_row,
                ft.Row(
                    controls=[
                        ft.OutlinedButton(
                            arrow,
                            height=tokens.CONTROL_SM,
                            on_click=lambda _e, k=key: page.run_task(_run_js, press_js(k)),
                        )
                        for arrow, key in (
                            ("←", "ArrowLeft"),
                            ("↑", "ArrowUp"),
                            ("↓", "ArrowDown"),
                            ("→", "ArrowRight"),
                        )
                    ],
                    spacing=tokens.SPACE_XS,
                ),
            ],
            spacing=tokens.SPACE_XXS,
            tight=True,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XXS, tokens.SPACE_SM, tokens.SPACE_XXS),
        visible=kb_on and not st.display_fullscreen,
    )

    # Fresh wrapper each render with visible at construction — the mounted
    # toolbar row itself is never mutated (frozen-control rule).
    toolbar = ft.Container(
        content=toolbar_row,
        bgcolor=theme.surface(),
        padding=ft.Padding(tokens.SPACE_XS, tokens.SPACE_XXS, tokens.SPACE_SM, tokens.SPACE_XXS),
        visible=not st.display_fullscreen,
    )

    if session.wv is not None:
        surface = ft.Container(
            content=session.wv,
            expand=True,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
    else:
        surface = ft.Container(
            content=ft.Text(
                "Display view needs Android (flet-webview renders only on Android/iOS/macOS).",
                size=tokens.FONT_SM,
                color=theme.text_dim(),
            ),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )

    return ft.Column(
        controls=[toolbar, keyboard_strip, surface],
        spacing=tokens.SPACE_NONE,
        expand=True,
    )
