"""The desktop view — the display surface, shown full-screen in the app.

Mirrors TerminalView's takeover: app_shell hides its chrome while a display
runs and this view owns the screen. The WebView is created ONCE per session
and stored on the session object (`session.wv`) — rebuilding it per render
would reload the viewer and, under flet 1.1, mutating mounted controls
mid-patch raises the frozen-control error.

The WebView loads UPSTREAM noVNC verbatim (vnc.html + app/, served by the
stream server): its own toolbar provides the extra-keys panel, the on-screen
keyboard (the hidden-textarea IME path — typing works), the clipboard pane,
clip/scale/resize settings and auto-reconnect. This view therefore adds only
the app chrome around it: back, title, terminal hand-off, fullscreen and the
session menu. No JavaScript bridges live here.
"""

from __future__ import annotations

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
from screens.help import show_help_sheet
from services.desk_service import DeskStatus
from state.controller_ctx import ControllerMethodsCtx


@ft.component
def DesktopView(session) -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    st, _ = ft.use_state(state)
    log_open, set_log_open = ft.use_state(False)
    # Subscribe to the guest-log rev so the output panel streams live.
    _ = st.display_log_rev
    log_lines = list(session.log_tail)
    # The ONE app-wide Clipboard (mounted by shared_services on the page) —
    # a fresh ft.Clipboard() is an unmounted Service and its set() raises;
    # the controller exposes no clipboard attribute.
    clipboard = getattr(page, "clipboard", None)

    # ── starting / stopping ───────────────────────────────────────────────────
    # Keyed off THIS session's status — the global display_status belongs to
    # whichever session last transitioned, and a second display starting
    # while this one is viewed must not replace the live viewer (device
    # audit 2026-11-13).
    if session.status is DeskStatus.STARTING or session.status is DeskStatus.STOPPING:
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
    if session.status is DeskStatus.ERROR:
        tail = "\n".join(list(session.log_tail)[-20:])
        return ft.Column(
            controls=[
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=theme.warn()),
                ft.Text(
                    session.error or st.display_error or "The display could not start.",
                    size=tokens.FONT_MD,
                ),
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
                            on_click=lambda _e: page.run_task(methods.retry_display, session.key),
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

        session.wv = WebView(
            url=st.display_url or session.url,
            expand=True,
            bgcolor=ft.Colors.BLACK,
            on_web_resource_error=_on_resource_error,
            on_console_message=_on_console,
        )

    async def _open_terminal(_e=None) -> None:
        """Hand off to a shell for this container. The display keeps running in
        the background (leave_display only drops it from the front); the app
        shell then shows the terminal, and the Display tab / the 'Display
        running' banner brings the display back."""
        await methods.leave_display()
        await methods.open_session(session.container)

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
                        content=ft.Text("Help"),
                        on_click=lambda _e: show_help_sheet(page, methods),
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
        if clipboard is None:
            return
        await clipboard.set("\n".join(log_lines))

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
        controls=[toolbar, surface, output_panel],
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
