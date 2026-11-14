"""Help — ONE reference surface for the whole app (Colab/GitHub pattern).

A searchable sheet grouped by task, replacing the repeated "How it works"
explainers: Getting started (the single canonical walkthrough), the terminal's
real keys/gestures, the display viewer's real gestures (upstream noVNC's own
mappings), resources (repo/releases/store/privacy/terms/licenses/changelog),
diagnostics (version, probe, live logs, copy-diagnostics) and About.

Entries: the header help icon, the terminal FAB menu, the display view menu and
a Settings row — the header is hidden while a shell/display owns the screen, so
the in-session entries matter.
"""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.constants import (
    APP_BUILD_NUMBER,
    APP_NAME,
    APP_VERSION,
    GITHUB_RELEASES_URL,
    PLAY_STORE_URL,
    PRIVACY_POLICY_URL,
    REPO_NAME,
    REPO_OWNER,
    TERMS_OF_SERVICE_URL,
)
from core.logger_handler import MemoryLogHandler
from core.state import state

REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"


def _kbd(text: str) -> ft.Control:
    return ft.Container(
        content=ft.Text(
            text,
            font_family=tokens.MONO_FONT,
            size=tokens.FONT_XXS,
            weight=ft.FontWeight.W_600,
            color=theme.text(),
        ),
        padding=ft.Padding(tokens.SPACE_XS, 0, tokens.SPACE_XS, 0),
        border_radius=tokens.RADIUS_XS,
        bgcolor=theme.surface_alt(),
    )


def _row(icon: ft.IconData, title: str, what: str) -> ft.Control:
    return ft.Row(
        controls=[
            ft.Icon(icon, size=tokens.ICON_SM, color=theme.primary()),
            ft.Column(
                controls=[
                    ft.Text(title, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                    ft.Text(what, size=tokens.FONT_XXS, color=theme.text_dim()),
                ],
                spacing=tokens.SPACE_NONE,
                expand=True,
            ),
        ],
        vertical_alignment=ft.CrossAxisAlignment.START,
        spacing=tokens.SPACE_SM,
    )


def _key_row(keycaps: str, what: str) -> ft.Control:
    return ft.Row(
        controls=[
            _kbd(keycaps),
            ft.Text(what, size=tokens.FONT_XXS, color=theme.text_dim(), expand=True),
        ],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=tokens.SPACE_SM,
    )


def _link_row(icon: ft.IconData, title: str, url: str) -> ft.Control:
    def _open(_e=None) -> None:
        # run_task is the scheduled path: a sync flet handler's returned
        # coroutine is discarded (the links would silently never open).
        from core import shared_services

        page = ft.context.page
        page.run_task(shared_services.launch_url, url)

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(icon, size=tokens.ICON_SM, color=theme.primary()),
                ft.Text(title, size=tokens.FONT_SM, expand=True),
                ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=tokens.ICON_SM),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=tokens.SPACE_SM,
        ),
        on_click=_open,
        ink=True,
    )


def _diagnostics_text() -> str:
    lines = [
        f"{APP_NAME} {APP_VERSION} (build {APP_BUILD_NUMBER})",
        f"probe: passed={state.probe_passed} — {state.probe_summary or 'n/a'}",
        f"orientation: {state.device_orientation} · keyboard inset: {state.keyboard_inset:.0f} px",
        "— recent logs —",
    ]
    lines.extend(MemoryLogHandler.get_logs()[-50:])
    return "\n".join(lines)


def show_help_sheet(page: ft.Page, methods=None) -> None:
    """Open the Help sheet (searchable, grouped, actionable rows)."""

    def _open_dialog(fn) -> None:
        page.pop_dialog()
        fn(page)

    def _settings_dialog(name: str):
        """Open one of the existing Settings dialogs on top of nothing (the
        help sheet closes first so the stack stays honest)."""

        def _handler(_e) -> None:
            from screens.settings import dialogs

            _open_dialog(getattr(dialogs, name))

        return _handler

    def _notification_settings(_e=None) -> None:
        from core import shared_services

        if methods is not None:
            ft.context.page.run_task(methods.open_notification_settings)
        else:  # keep the sheet honest when the context is unavailable
            shared_services.logger.debug("notification settings unavailable")

    def _share_diagnostics(_e=None) -> None:
        share = getattr(ft.context.page, "share", None)
        if share is None:
            return
        ft.context.page.run_task(
            share.share_text, _diagnostics_text(), title=f"{APP_NAME} diagnostics"
        )

    def _copy_diagnostics(_e=None) -> None:
        clipboard = getattr(page, "clipboard", None)
        if clipboard is None:
            return
        page.run_task(clipboard.set, _diagnostics_text())
        if methods is not None:
            methods.show_snack("diagnostics copied to clipboard")

    sections: list[tuple[str, list[tuple[str, ft.Control]]]] = [
        (
            "Getting started",
            [
                (
                    "pick search distro install",
                    _row(
                        ft.Icons.SEARCH_ROUNDED,
                        "1 · Pick or search a distro",
                        "Search Docker Hub, or tap a popular distro. Any public image works.",
                    ),
                ),
                (
                    "install one tap rootfs",
                    _row(
                        ft.Icons.DOWNLOAD_ROUNDED,
                        "2 · One-tap install",
                        "proot-distro downloads the rootfs; live output streams while it works.",
                    ),
                ),
                (
                    "launch shell display terminal",
                    _row(
                        ft.Icons.TERMINAL_ROUNDED,
                        "3 · Launch",
                        "Open shell for a terminal. Open display for one app — or a full desktop.",
                    ),
                ),
            ],
        ),
        (
            "Terminal",
            [
                (
                    "extra keys ctrl alt escape tab arrows",
                    _key_row(
                        "ESC  TAB  CTRL  ALT  ← ↑ ↓ →  ↵  ⌫",
                        "Extra keys row. CTRL/ALT are sticky — tap to hold for the next keys.",
                    ),
                ),
                (
                    "fab actions new shell copy paste clear zoom search files fullscreen",
                    _row(
                        ft.Icons.MORE_HORIZ_ROUNDED,
                        "The FAB holds the terminal actions",
                        "New shell, Copy selection, Copy full output, Paste, Clear, theme, "
                        "zoom, search, files, full screen, close.",
                    ),
                ),
                (
                    "cross architecture qemu speed tb size",
                    _row(
                        ft.Icons.MEMORY_ROUNDED,
                        "Foreign-architecture containers",
                        "QEMU user-mode emulators ship with the app. For a speed boost, "
                        "add QEMU_TB_SIZE=64M to the shell's Environment lines.",
                    ),
                ),
                (
                    "long press select copy",
                    _row(
                        ft.Icons.CONTENT_COPY_ROUNDED,
                        "Select and copy",
                        "Long-press for the engine's copy menu; Copy full output copies the "
                        "whole scrollback, not just the visible screen.",
                    ),
                ),
            ],
        ),
        (
            "Display viewer",
            [
                (
                    "tap click long press right click two finger scroll pinch",
                    _key_row(
                        "TAP",
                        "Left click. Long-press (or two-finger tap) = right click, "
                        "three-finger tap = middle click.",
                    ),
                ),
                (
                    "two finger drag scroll wheel",
                    _key_row("2-FINGER DRAG", "Scroll wheel inside the guest app."),
                ),
                (
                    "pinch zoom ctrl wheel",
                    _key_row("PINCH", "Ctrl+wheel zoom in apps that support it."),
                ),
                (
                    "toolbar keyboard clipboard extra keys reconnect settings",
                    _row(
                        ft.Icons.TUNE_ROUNDED,
                        "The viewer's own toolbar",
                        "Keyboard (soft-keyboard typing), clipboard panel, extra keys, "
                        "clip/scale/remote-resize settings, and auto-reconnect on drops.",
                    ),
                ),
            ],
        ),
        (
            "Files & backups",
            [
                (
                    "backup share save folder archive",
                    _row(
                        ft.Icons.ARCHIVE_ROUNDED,
                        "Backups never go through memory",
                        "After the archive is staged you pick a folder to save it into, "
                        "or send it to another app with the share sheet.",
                    ),
                ),
                (
                    "restore overwrite container archive",
                    _row(
                        ft.Icons.UNARCHIVE_ROUNDED,
                        "Restore replaces the container",
                        "A restore wipes the container's filesystem and extracts the "
                        "archive over it — it asks for confirmation first.",
                    ),
                ),
                (
                    "paste image clipboard png files",
                    _row(
                        ft.Icons.IMAGE_ROUNDED,
                        "Paste an image into the container",
                        "In Files, the image button saves the clipboard image as a PNG "
                        "in the folder you are browsing.",
                    ),
                ),
            ],
        ),
        (
            "Resources",
            [
                (
                    "repository github source",
                    _link_row(ft.Icons.CODE_ROUNDED, "Source code", REPO_URL),
                ),
                (
                    "releases downloads changelog",
                    _link_row(ft.Icons.NEW_RELEASES_ROUNDED, "Releases", GITHUB_RELEASES_URL),
                ),
                (
                    "play store listing",
                    _link_row(ft.Icons.SHOP_ROUNDED, "Play Store listing", PLAY_STORE_URL),
                ),
                (
                    "privacy policy",
                    _link_row(ft.Icons.PRIVACY_TIP_ROUNDED, "Privacy policy", PRIVACY_POLICY_URL),
                ),
                (
                    "terms of service",
                    _link_row(
                        ft.Icons.DESCRIPTION_ROUNDED, "Terms of service", TERMS_OF_SERVICE_URL
                    ),
                ),
                (
                    "licenses open source",
                    ft.TextButton(
                        "Open-source licenses",
                        icon=ft.Icons.GAVEL_ROUNDED,
                        on_click=_settings_dialog("open_licenses"),
                    ),
                ),
                (
                    "changelog whats new",
                    ft.TextButton(
                        "Changelog",
                        icon=ft.Icons.HISTORY_ROUNDED,
                        on_click=_settings_dialog("open_changelog"),
                    ),
                ),
            ],
        ),
        (
            "Diagnostics",
            [
                (
                    "version build",
                    _row(
                        ft.Icons.INFO_OUTLINE_ROUNDED,
                        f"{APP_NAME} v{APP_VERSION} (build {APP_BUILD_NUMBER})",
                        "Python 3.14 · Flet 1.1 · proot-distro",
                    ),
                ),
                (
                    "probe environment status",
                    _row(
                        ft.Icons.MONITOR_HEART_ROUNDED,
                        "Environment probe",
                        state.probe_summary or "not probed yet",
                    ),
                ),
                (
                    "live logs activity terminal",
                    ft.TextButton(
                        "Live activity terminal",
                        icon=ft.Icons.TERMINAL_ROUNDED,
                        on_click=_settings_dialog("open_live_activity_terminal"),
                    ),
                ),
                (
                    "copy diagnostics support",
                    ft.TextButton(
                        "Copy diagnostics",
                        icon=ft.Icons.CONTENT_COPY_ROUNDED,
                        on_click=_copy_diagnostics,
                    ),
                ),
                (
                    "share diagnostics support send",
                    ft.TextButton(
                        "Share diagnostics",
                        icon=ft.Icons.SHARE_ROUNDED,
                        on_click=_share_diagnostics,
                    ),
                ),
                (
                    "notifications permission settings alerts",
                    ft.TextButton(
                        "Notification settings",
                        icon=ft.Icons.NOTIFICATIONS_ROUNDED,
                        on_click=_notification_settings,
                    ),
                ),
            ],
        ),
        (
            "Troubleshooting",
            [
                (
                    "gpu opengl chromium software rendering angle",
                    _row(
                        ft.Icons.MEMORY_ROUNDED,
                        "GPU-accelerated OpenGL isn't available",
                        "The in-app X server has no GPU path (no DRI3/GBM), so browsers "
                        "and 3D apps render in software. Chromium flags that keep the "
                        "fallback clean: --disable-gpu  ·  LIBGL_ALWAYS_SOFTWARE=1",
                    ),
                ),
                (
                    "zypper metadata empty document repomd",
                    _row(
                        ft.Icons.DOWNLOAD_ROUNDED,
                        "openSUSE: 'repomd.xml Document is empty'",
                        "The mirror served an empty body or a stale cache is pinned. Run "
                        "zypper clean -a && zypper ref --force, or switch the repo host "
                        "to mirrorcache.opensuse.org.",
                    ),
                ),
            ],
        ),
        (
            "About",
            [
                (
                    "proot distro license",
                    _row(
                        ft.Icons.FAVORITE_ROUNDED,
                        f"{APP_NAME} — Linux on Android, no root",
                        "PRoot user-space, GPL corresponding source in the repo and licenses.",
                    ),
                ),
            ],
        ),
    ]
    body = ft.Column(spacing=tokens.SPACE_XS, tight=True, width=tokens.DIALOG_WIDTH_LG)

    def _render(query: str) -> None:
        q = query.strip().lower()

        def _visible(text: str) -> bool:
            return not q or q in text

        rows: list[ft.Control] = []
        for title, items in sections:
            hits = [(text, control) for text, control in items if _visible(f"{title} {text}")]
            if not hits:
                continue
            rows.append(
                ft.ExpansionTile(
                    title=ft.Text(title, size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
                    expanded=bool(q),
                    controls=[control for _text, control in hits],
                )
            )
        if not rows:
            rows.append(
                ft.Text(
                    "nothing matches that search",
                    size=tokens.FONT_SM,
                    color=theme.text_dim(),
                )
            )
        body.controls = rows
        try:
            dlg.update()
        except Exception:
            pass

    search = ft.TextField(
        hint_text="Search help",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        on_change=lambda e: _render(e.control.value or ""),
        border=ft.OutlineInputBorder(border_radius=tokens.RADIUS_MD),
        text_size=tokens.FONT_SM,
        dense=True,
    )

    dlg = ft.AlertDialog(
        title=ft.Text("Help", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[search, body],
            spacing=tokens.SPACE_SM,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            width=tokens.DIALOG_WIDTH_LG,
        ),
        actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
    )
    _render("")
    page.show_dialog(dlg)
