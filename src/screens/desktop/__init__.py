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

import asyncio
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
    """Fill the viewer's access-code overlay and connect.

    Overlay-guarded and retry-safe: a NO-OP once the overlay is hidden (the
    session already connected) and a no-op marker when the DOM isn't ready —
    the page-started handler retries on a timer because navigation can begin
    before the viewer's elements exist."""
    return (
        "(function(){var o=document.getElementById('auth');"
        "if(!o||o.hidden){return 'done';}"
        "var i=document.getElementById('authInput');"
        "if(!i){return 'retry';}"
        f"i.setAttribute('value', {json.dumps(code)});"
        "var b=document.getElementById('authButton');"
        "if(!b){return 'retry';}"
        "b.click();return 'sent';})()"
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
    log_open, set_log_open = ft.use_state(False)
    # Subscribe to the guest-log rev so the output panel streams live.
    _ = st.display_log_rev
    log_lines = list(session.log_tail)
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
                                methods.show_display_logs, session.key
                            ),
                        ),
                        ft.TextButton(
                            "Cancel",
                            on_click=lambda _e: page.run_task(methods.stop_display, session.key),
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
                                methods.start_display, session.container, None, None, None
                            ),
                        ),
                        ft.TextButton(
                            "Show logs",
                            on_click=lambda _e: page.run_task(
                                methods.show_display_logs, session.key
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
            # code the server generated. Navigation can begin before the
            # viewer's DOM exists, so retry on a timer — the injected JS is
            # overlay-guarded, so a retry after connect is a no-op.
            code = session.code
            if not code or session.wv is None:
                return
            await asyncio.sleep(0.4)
            for _ in range(8):
                try:
                    await session.wv.run_javascript(auth_js(code))
                except Exception:
                    return
                await asyncio.sleep(0.6)

        session.wv = WebView(
            url=st.display_url or session.url,
            expand=True,
            bgcolor=ft.Colors.BLACK,
            on_web_resource_error=_on_resource_error,
            on_console_message=_on_console,
            on_page_started=_on_page_started,
        )

    async def _open_terminal(_e=None) -> None:
        """Hand off to a shell for this container. The display keeps running in
        the background (leave_display only drops it from the front); the app
        shell then shows the terminal, and the Display tab / the 'Display
        running' banner brings the display back."""
        await methods.leave_display()
        await methods.open_session(session.container)

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
                f"{session.container} :{session.display}"
                + (f" · {session.app_command}" if session.app_command else ""),
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
                color=theme.text(),
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.IconButton(
                icon=ft.Icons.TERMINAL_ROUNDED,
                icon_size=tokens.ICON_MD,
                tooltip="Open a terminal for this container",
                on_click=lambda _e: page.run_task(_open_terminal),
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
                        on_click=lambda _e: page.run_task(methods.share_display, session.key),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Logs"),
                        on_click=lambda _e: page.run_task(methods.show_display_logs, session.key),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Text("Stop"),
                        on_click=lambda _e: page.run_task(methods.stop_display, session.key),
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

    # ── compact key strip: ONE horizontally scrollable row of small keys ──
    # (flet-terminal ExtraKeysBar pattern: Row(scroll=AUTO), ~28px keys,
    # compact density). Text typing is left to the phone keyboard / the
    # viewer's own inputs — this strip carries only the special keys.
    def _key_btn(label: str, key: str) -> ft.Control:
        return ft.Button(
            content=ft.Text(label, size=tokens.FONT_XS, weight=ft.FontWeight.W_600),
            height=28,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=6, vertical=0),
                visual_density=ft.VisualDensity.COMPACT,
                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
            ),
            on_click=lambda _e, k=key: page.run_task(_run_js, press_js(k)),
        )

    def _mod_btn(label: str, current: bool, setter, key: str) -> ft.Control:
        return ft.Button(
            content=ft.Text(label, size=tokens.FONT_XS, weight=ft.FontWeight.W_600),
            height=28,
            tooltip=f"Hold {label} for the next keys (press again to release)",
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=6, vertical=0),
                visual_density=ft.VisualDensity.COMPACT,
                shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                side=ft.BorderSide(1, theme.primary() if current else theme.surface_alt()),
            ),
            on_click=_toggle_modifier(current, setter, key),
        )

    keyboard_strip = ft.Container(
        content=ft.Row(
            controls=[
                _key_btn("Esc", "Escape"),
                _key_btn("Tab", "Tab"),
                _mod_btn("Ctrl", ctrl_on, set_ctrl_on, "Control"),
                _mod_btn("Alt", alt_on, set_alt_on, "Alt"),
                _key_btn("←", "ArrowLeft"),
                _key_btn("↑", "ArrowUp"),
                _key_btn("↓", "ArrowDown"),
                _key_btn("→", "ArrowRight"),
                _key_btn("↵", "Enter"),
                _key_btn("⌫", "Backspace"),
            ],
            spacing=tokens.SPACE_XS,
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding(2, 1, 2, 1),
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

    # ── inline output panel: the guest log, one tap to expand/collapse ──────
    # A slim bar stays visible with the last line as a preview; expanding
    # streams the full log (CollabShell notebook pattern — a fresh list each
    # render, scroll position under the user's control).
    last_line = log_lines[-1] if log_lines else "no output yet"

    async def _copy_log() -> None:
        await ft.Clipboard().set("\n".join(log_lines))

    output_panel = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.TERMINAL_ROUNDED,
                            size=tokens.ICON_SM,
                            color=theme.primary(),
                        ),
                        ft.Text(
                            "output",
                            size=tokens.FONT_SM,
                            weight=ft.FontWeight.W_600,
                            color=theme.text(),
                        ),
                        ft.Text(
                            last_line,
                            size=tokens.FONT_XS,
                            color=theme.text_dim(),
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                        ft.IconButton(
                            ft.Icons.EXPAND_LESS_ROUNDED
                            if log_open
                            else ft.Icons.EXPAND_MORE_ROUNDED,
                            icon_size=tokens.ICON_SM,
                            tooltip="Collapse output" if log_open else "Expand output",
                            on_click=lambda _e: set_log_open(not log_open),
                        ),
                        ft.IconButton(
                            ft.Icons.COPY_ALL_ROUNDED,
                            icon_size=tokens.ICON_SM,
                            tooltip="Copy output",
                            on_click=lambda _e: page.run_task(_copy_log),
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=tokens.SPACE_XS,
                ),
                ft.Container(
                    content=ft.ListView(
                        controls=[
                            ft.Text(
                                line,
                                font_family=tokens.MONO_FONT,
                                size=tokens.FONT_XXS,
                                color=theme.text_dim(),
                            )
                            for line in log_lines[-200:]
                        ],
                        spacing=tokens.SPACE_XXS,
                        auto_scroll=True,
                        height=140,
                    ),
                    visible=log_open,
                ),
            ],
            spacing=tokens.SPACE_NONE,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding(tokens.SPACE_SM, tokens.SPACE_XS, tokens.SPACE_SM, tokens.SPACE_XS),
        border_radius=tokens.RADIUS_MD,
        # Full screen is immersive: the output stays behind until it's left.
        visible=not st.display_fullscreen,
    )

    body = ft.Column(
        controls=[toolbar, keyboard_strip, surface, output_panel],
        spacing=tokens.SPACE_NONE,
        expand=True,
    )
    if not st.display_fullscreen:
        return body

    # Fullscreen hides the whole toolbar — a floating exit button stays
    # visible so there is ALWAYS an on-screen way out (house rule: FAB
    # visible incl. fullscreen; the Android back button via on_view_pop is
    # the second exit). Positioned with right/bottom so it does NOT expand
    # over the screen or intercept touches to the viewer.
    exit_fab = ft.FloatingActionButton(
        content=ft.Icon(ft.Icons.FULLSCREEN_EXIT_ROUNDED, size=tokens.ICON_LG),
        tooltip="Exit full screen",
        on_click=lambda _e: page.run_task(methods.set_display_fullscreen, False),
    )
    return ft.Stack(
        controls=[
            body,
            ft.Container(
                content=exit_fab,
                right=tokens.SPACE_MD,
                bottom=tokens.SPACE_MD,
            ),
        ],
        expand=True,
    )
