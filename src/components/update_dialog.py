"""The update / "What's New" dialog.

Two modes: up to date (the bundled changelog, offline) and update available
(the feed's release notes + the launch buttons). Remote links are opened
through the host allowlist — the notes are remote markdown.
"""

from __future__ import annotations

import logging

import flet as ft

from core import theme, tokens
from core.changelog import notes_for
from core.constants import APP_NAME, APP_VERSION, GITHUB_RELEASES_URL, PLAY_STORE_URL
from core.shared_services import launch_url
from services.update_service import is_allowed_launch_url

logger = logging.getLogger(__name__)


def _launch(page: ft.Page, url: str) -> None:
    if not is_allowed_launch_url(url):
        return
    page.run_task(launch_url, url, page)


def _dialog_width(page: ft.Page) -> int:
    """Fits a narrow phone; the action row lives outside the scroll."""
    try:
        page_width = int(getattr(page, "width", 0) or 0)
    except TypeError, ValueError:
        page_width = 0
    if not page_width:
        return tokens.DIALOG_WIDTH
    return min(tokens.DIALOG_WIDTH, max(tokens.DIALOG_MIN_WIDTH, page_width - 48))


def show_update_dialog(page: ft.Page, update_data: dict | None = None) -> None:
    """The dialog in both modes."""
    data = update_data or {}
    is_update = bool(data)
    width = _dialog_width(page)

    if is_update:
        title_text = data.get("title") or f"Version {data.get('version', '')} available"
        icon = (
            ft.Icons.CAMPAIGN_ROUNDED
            if data.get("type") == "announcement"
            else (ft.Icons.ROCKET_LAUNCH_ROUNDED)
        )
        body = ft.Column(
            controls=[
                ft.Text(
                    f"Version {data.get('version', '')} is now available.",
                    size=tokens.FONT_MD,
                    color=theme.text(),
                ),
                ft.Text(
                    "What's New:",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.BOLD,
                    color=theme.text(),
                ),
                ft.Container(
                    content=ft.Markdown(
                        data.get("release_notes", ""),
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=lambda e: _launch(page, e.data),
                    ),
                    width=width,
                ),
            ],
            spacing=tokens.SPACE_SM,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )
        actions = _update_actions(page, data)
        mandatory = bool(data.get("mandatory"))
    else:
        title_text = "You're up to date"
        icon = ft.Icons.VERIFIED_ROUNDED
        body = ft.Column(
            controls=[
                ft.Container(
                    content=ft.Markdown(
                        notes_for(APP_VERSION),
                        selectable=True,
                        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                        on_tap_link=lambda e: _launch(page, e.data),
                    ),
                    width=width,
                ),
            ],
            spacing=tokens.SPACE_SM,
            scroll=ft.ScrollMode.AUTO,
            tight=True,
        )
        actions = [
            # run_task, not a bare call: _check_again is a coroutine, and a
            # sync handler's return value is discarded by Flet — the bare
            # lambda made this button a silent no-op.
            ft.TextButton(
                "Check for Updates", on_click=lambda _e: page.run_task(_check_again, page)
            ),
            ft.FilledButton("Close", on_click=lambda _e: page.pop_dialog()),
        ]
        mandatory = False

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Row(
                controls=[
                    ft.Icon(icon, size=20, color=theme.primary()),
                    ft.Text(title_text, size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
                ],
                spacing=tokens.SPACE_SM,
            ),
            content=body,
            actions=actions,
            modal=mandatory,
        )
    )


def _update_actions(page: ft.Page, data: dict) -> list[ft.Control]:
    buttons: list[ft.Control] = []
    is_android = bool(getattr(page, "platform", None)) and page.platform.is_mobile()
    # The feed omitting playstore_url must not silently hide the Play button
    # — fall back to the shipped listing URL (same rule as github_url).
    play_url = data.get("playstore_url") or PLAY_STORE_URL
    github_url = data.get("github_url") or GITHUB_RELEASES_URL

    if is_android and play_url:
        buttons.append(
            ft.FilledButton(
                "Google Play",
                icon=ft.Icons.SHOP_ROUNDED,
                on_click=lambda _e: _launch(page, play_url),
            )
        )
    buttons.append(
        ft.OutlinedButton(
            "Release page",
            icon=ft.Icons.DOWNLOAD_ROUNDED,
            on_click=lambda _e: _launch(page, github_url),
        )
    )
    if not data.get("mandatory"):
        buttons.append(ft.TextButton("Later", on_click=lambda _e: page.pop_dialog()))
    return buttons


async def _check_again(page: ft.Page) -> None:
    """Re-check live; morph the dialog when the feed moved."""
    from services.update_service import check_for_update

    try:
        page.pop_dialog()
    except Exception as exc:
        logger.debug("re-check with no dialog open: %s", exc)
    result = await check_for_update()
    if result:
        show_update_dialog(page, result)
    else:
        page.show_dialog(ft.SnackBar(ft.Text(f"{APP_NAME} v{APP_VERSION} is up to date")))
