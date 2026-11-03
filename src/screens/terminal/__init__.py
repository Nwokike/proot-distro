"""The terminal view — CollabShell's session screen, exactly:

minimal flat header (back + status dot + title), the sticky banner ad directly
UNDER the header (never inside the terminal), the multi-shell tab switcher,
and the MobileTerminal itself with no padding. All actions (new terminal,
copy/paste/clear, theme presets, zoom, toggles, files, fullscreen, close) live
in a page-level FAB — no hamburger in the header.
"""

from __future__ import annotations

import flet as ft

try:
    from flet_terminal import BUILTIN_THEMES, MobileTerminal

    _HAS_TERMINAL = True
except ImportError:
    # Extension not installed in this environment (e.g. `flet run` with the
    # system flet instead of the project venv) — render a placeholder pane
    # instead of dying at import (house pattern: ad_service.py guards the
    # same way; docs/testing-findings.md prescribes placeholder panes).
    BUILTIN_THEMES = {}
    MobileTerminal = None
    _HAS_TERMINAL = False

from components.app_header import theme_button
from components.banner_ad import pooled_banner_ad
from core import theme, tokens
from core.state import state
from core.styles import status_dot
from screens.terminal_controls import (
    _compact_btn_style,
    _confirm_close,
    _cycle_terminal_theme,
    _theme_name,
)
from services.session_manager import SessionEntry
from state.controller_ctx import ControllerMethodsCtx

from . import menu, wiring


@ft.component
def TerminalView(entry: SessionEntry) -> ft.Control:
    page = ft.context.page
    methods = ft.use_context(ControllerMethodsCtx)
    st, _ = ft.use_state(state)
    # Fullscreen comes straight from the observable state — a local use_state
    # copy desyncs from main.py's back-button handler, which sets the global.
    fullscreen = st.terminal_fullscreen
    controller = getattr(page, "_controller", None)
    manager = getattr(controller, "session_manager", None)

    # Wakelock keeps screen/CPU awake during active terminal sessions
    def _sync_wakelock():
        wl = getattr(page, "wakelock", None)
        if wl is None:
            return None
        try:
            page.run_task(wl.enable)
        except RuntimeError:
            pass  # session already destroyed — nothing left to update

        def _cleanup():
            # Effect cleanup can run after the page session is destroyed —
            # page.run_task then raises "An attempt to fetch destroyed session".
            try:
                page.run_task(wl.disable)
            except RuntimeError:
                pass

        return _cleanup

    ft.on_mounted(_sync_wakelock)

    # Constructed during render, exactly like the flet-terminal example /
    # CollabShell (extra keys, search and settings panes are the terminal's own).
    if entry.mt is None and _HAS_TERMINAL:
        entry.mt = MobileTerminal(
            show_extra_keys=True,
            show_search=False,
            show_settings=False,
            scrollback=10000,
            font_family=tokens.MONO_FONT,
            cursor_style="block",
            cursor_blink=True,
            theme=BUILTIN_THEMES.get(_theme_name()),
            auto_focus=False,
            expand=True,
        )

    mt = entry.mt

    def _open_new_session_sheet() -> None:
        menu.open_new_session_sheet(page, methods, manager)

    if mt is not None and not entry.wired:
        wiring.wire_terminal(entry, mt, page, manager, methods, _open_new_session_sheet)
        # Live output must target THIS page's loop (the app can be reopened in
        # the same process while the foreground service keeps it alive).
        entry.loop = getattr(page, "loop", None)

    # The terminal theme follows the app's light/dark mode (CollabShell's
    # _active_theme_name pattern): re-apply to every open shell on theme flips.
    def _apply_app_theme() -> None:
        name = _theme_name()
        if manager:
            for e in manager.entries.values():
                if e.mt is not None:
                    e.mt.set_theme(name)

    ft.use_effect(_apply_app_theme, [state.theme_revision])

    def _toggle_fullscreen(_e=None) -> None:
        state.terminal_fullscreen = not st.terminal_fullscreen

    def _browse_files() -> None:
        from screens.files.modal import show_manage_files_modal

        show_manage_files_modal(page, entry.container)

    # All terminal actions in a page-level FAB (CollabShell build_session_fab).
    # The FAB is ALWAYS visible, including in fullscreen — it has "Exit Full
    # Screen" as an option. Ownership is tracked with a Ref (CollabShell's
    # pattern): we write the view slot only when it is empty or already ours,
    # and clear it only while we still own it — so a fullscreen re-render can
    # never leave the slot empty. The slot mutation is pushed with a view-level
    # update so the FAB appears immediately, not on the next event.
    _fab_ref = ft.Ref[ft.FloatingActionButton]()

    def _sync_fab():
        try:
            view = page.views[0]
        except Exception:
            return None
        current = view.floating_action_button
        if current is not None and current is not _fab_ref.current:
            return None  # another component owns the FAB slot right now
        fab = menu.build_terminal_fab(
            page,
            methods,
            entry,
            manager,
            fullscreen,
            _toggle_fullscreen,
            _browse_files,
            _open_new_session_sheet,
        )
        _fab_ref.current = fab
        view.floating_action_button = fab
        try:
            view.update()
        except Exception:
            pass

        def _cleanup():
            try:
                if view.floating_action_button is _fab_ref.current:
                    view.floating_action_button = None
                    _fab_ref.current = None
                    view.update()
            except Exception:
                pass

        return _cleanup

    ft.use_effect(_sync_fab, [fullscreen, entry.key])

    status_indicators: list[ft.Control] = [status_dot(entry.ready)]
    if not entry.ready:
        status_indicators.append(
            ft.ProgressRing(
                width=tokens.PROGRESS_RING_XS,
                height=tokens.PROGRESS_RING_XS,
                stroke_width=tokens.PROGRESS_RING_STROKE,
            )
        )

    # Multi-shell switcher tabs: one chip per open shell (keyed by session id).
    tab_chips: list[ft.Control] = []
    if manager:
        for key, e in manager.entries.items():
            is_active = key == st.active_session
            tab_chips.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.TERMINAL_ROUNDED,
                                size=tokens.ICON_XS,
                                color=theme.primary() if is_active else theme.text_dim(),
                            ),
                            ft.Text(
                                e.title or key,
                                size=tokens.FONT_XS,
                                color=theme.primary() if is_active else theme.text(),
                                weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                            ),
                            ft.GestureDetector(
                                content=ft.Icon(
                                    ft.Icons.CLOSE_ROUNDED,
                                    size=tokens.ICON_XS,
                                    color=theme.text_dim(),
                                ),
                                on_tap=lambda _evt, k=key, t=e.title: _confirm_close(
                                    page, methods, k, t or k
                                ),
                            ),
                        ],
                        spacing=tokens.SPACE_XXS,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(
                        tokens.SPACE_SM, tokens.SPACE_XXS, tokens.SPACE_XS, tokens.SPACE_XXS
                    ),
                    border_radius=tokens.RADIUS_SM,
                    bgcolor=ft.Colors.with_opacity(tokens.OPACITY_MEDIUM, theme.primary())
                    if is_active
                    else theme.TRANSPARENT,
                    border=ft.Border.all(
                        1,
                        ft.Colors.with_opacity(tokens.OPACITY_SELECTED, theme.primary())
                        if is_active
                        else ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.text_dim()),
                    ),
                    on_click=lambda _evt, k=key: setattr(state, "active_session", k),
                    ink=True,
                )
            )

    tab_chips.append(
        ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_size=tokens.ICON_SM,
            tooltip="New Terminal (same container gets a second shell)",
            on_click=lambda _e: _open_new_session_sheet(),
        )
    )

    def _refresh_terminal(_e=None) -> None:
        # Replay the retained scrollback into the terminal (CollabShell refresh).
        if mt is not None:
            mt.clear_pending()
            entry.replay(mt.send_bytes)

    # ONE scrollable header row (animepahe-TV style): back + status + title,
    # the tab chips, and every terminal control all live in the header,
    # horizontally scrollable on narrow screens. Fullscreen only HIDES the
    # chrome (visible=False) — the terminal widget is never unmounted from the
    # tree, so its state (extra-keys ink, scrollback, subscriptions) survives
    # the fullscreen toggle instead of breaking after it.
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Back to the session list (the shell stays alive)",
                    on_click=lambda _e: page.run_task(methods.leave_session),
                ),
                ft.Row(
                    controls=status_indicators,
                    spacing=tokens.SPACE_XS,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    entry.title,
                    size=tokens.FONT_LG,
                    weight=ft.FontWeight.BOLD,
                    color=theme.text(),
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    tooltip=entry.title,
                ),
                *tab_chips,
                ft.IconButton(
                    icon=ft.Icons.REFRESH_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Refresh Terminal (replay scrollback)",
                    style=_compact_btn_style(),
                    on_click=_refresh_terminal,
                ),
                ft.IconButton(
                    icon=ft.Icons.PALETTE_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Cycle Terminal Theme",
                    style=_compact_btn_style(),
                    on_click=lambda _e: _cycle_terminal_theme(mt),
                ),
                ft.IconButton(
                    icon=ft.Icons.ZOOM_OUT,
                    icon_size=tokens.ICON_SM,
                    tooltip="Zoom Out",
                    style=_compact_btn_style(),
                    on_click=lambda _e: mt.zoom_out(),
                ),
                ft.IconButton(
                    icon=ft.Icons.ZOOM_IN,
                    icon_size=tokens.ICON_SM,
                    tooltip="Zoom In",
                    style=_compact_btn_style(),
                    on_click=lambda _e: mt.zoom_in(),
                ),
                ft.IconButton(
                    icon=ft.Icons.SEARCH_ROUNDED,
                    icon_size=tokens.ICON_SM,
                    tooltip="Search Buffer",
                    style=_compact_btn_style(),
                    on_click=lambda _e: mt.toggle_search(),
                ),
                ft.IconButton(
                    icon=ft.Icons.FULLSCREEN_EXIT_ROUNDED
                    if fullscreen
                    else ft.Icons.FULLSCREEN_ROUNDED,
                    icon_size=tokens.ICON_MD,
                    tooltip="Exit full screen" if fullscreen else "Full screen",
                    on_click=_toggle_fullscreen,
                ),
                theme_button(lambda: page.run_task(methods.cycle_theme_mode)),
            ],
            scroll=ft.ScrollMode.AUTO,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_XS,
        ),
        bgcolor=theme.surface(),
        padding=ft.Padding(tokens.SPACE_XS, tokens.SPACE_XXS, tokens.SPACE_SM, tokens.SPACE_XXS),
        visible=not fullscreen,
    )

    # Sticky banner directly under the header (1DM-style), never inside the
    # terminal; fullscreen leaves only the terminal (FAB stays).
    banner = pooled_banner_ad("terminal-1", page)
    banner.visible = not fullscreen

    controls: list[ft.Control] = [header, banner]
    if mt is not None:
        controls.append(mt)
    else:
        controls.append(
            ft.Container(
                content=ft.Text(
                    "Terminal extension (flet-terminal) is not available in this build.",
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                ),
                alignment=ft.Alignment.CENTER,
                expand=True,
            )
        )

    return ft.Column(controls=controls, spacing=tokens.SPACE_XS, expand=True)
