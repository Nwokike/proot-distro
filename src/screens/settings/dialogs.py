"""Settings dialogs as module-level functions (moved out of SettingsView).

Each takes its dependencies explicitly (page / state bits / callbacks) so the
component in __init__.py stays a thin assembly of cards + rows.
"""

from __future__ import annotations

import contextlib
import os

import flet as ft

from core import theme, tokens
from core.changelog import notes_for
from core.constants import APP_NAME, APP_VERSION
from core.state import state
from screens.license_view import licenses_view

_TERMINAL_DISPLAY_LINES = 500


def open_live_activity_terminal(page: ft.Page) -> None:
    """The diagnostic terminal (Sherlock pattern): live app logs in a green
    on-dark monospace box, with Copy / Clear / Close."""
    from core.logger_handler import in_memory_log_handler
    from core.shared_services import launch_url  # noqa: F401  (parity import)

    with contextlib.suppress(Exception):
        page.pop_dialog()

    logs_list = in_memory_log_handler.get_logs()[-_TERMINAL_DISPLAY_LINES:]
    log_text = ft.Text(
        value="\n".join(logs_list)
        if logs_list
        else "No activity recorded yet.\nApp logs will appear here.",
        size=tokens.FONT_XS,
        font_family=tokens.MONO_FONT,
        color=theme.ok(),
        selectable=True,
    )

    def _copy_logs(_e):
        from components.snack import show_snack
        from core.shared_services import shared_url_launcher  # noqa: F401

        async def _do_copy():
            import flet as ft  # local: Clipboard service

            cb = ft.Clipboard()
            page.services.append(cb)
            await cb.set("\n".join(in_memory_log_handler.get_logs()))
            show_snack(page, "Logs copied to clipboard")

        page.run_task(_do_copy)

    def _clear_logs(_e):
        # Reopen the dialog so the terminal re-renders fresh (the house guard
        # forbids imperative control mutations in screens/).
        in_memory_log_handler.clear_logs()
        with contextlib.suppress(Exception):
            page.pop_dialog()
        open_live_activity_terminal(page)

    terminal_dlg = ft.AlertDialog(
        modal=False,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.primary(), size=tokens.ICON_MD),
                ft.Text(
                    "Live Activity Terminal",
                    size=tokens.FONT_MD,
                    weight=ft.FontWeight.BOLD,
                    color=theme.primary(),
                    expand=True,
                ),
            ],
            spacing=tokens.SPACE_SM,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        "Real-time app diagnostics: sessions, installs, ads, errors.",
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                    ),
                    ft.Container(height=tokens.SPACE_XS),
                    ft.Container(
                        content=ft.Column(
                            controls=[log_text],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        bgcolor=theme.TRANSPARENT,
                        border=ft.Border.all(
                            1,
                            ft.Colors.with_opacity(tokens.OPACITY_LIGHT, theme.text()),
                        ),
                        border_radius=tokens.RADIUS_SM,
                        padding=tokens.SPACE_MD,
                        height=260,
                    ),
                ],
                spacing=0,
            ),
            width=tokens.DIALOG_WIDTH_LG,
        ),
        actions=[
            ft.TextButton("Copy Logs", icon=ft.Icons.COPY_ROUNDED, on_click=_copy_logs),
            ft.TextButton("Clear", icon=ft.Icons.DELETE_SWEEP_ROUNDED, on_click=_clear_logs),
            ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(terminal_dlg)


def open_changelog(page: ft.Page) -> None:
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"What's New in {APP_NAME} v{APP_VERSION}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=[ft.Text(notes_for(APP_VERSION), size=tokens.FONT_SM)],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
        )
    )


def show_storage_dialog(page: ft.Page, detail: dict) -> None:
    roots = detail.get("roots", {})
    rows: list[ft.Control] = [
        ft.Text(
            "Flet app-storage roots",
            size=tokens.FONT_SM,
            weight=ft.FontWeight.BOLD,
            color=theme.text(),
        ),
        ft.Text(
            f"data:   {roots.get('data', '?')}",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
            selectable=True,
        ),
        ft.Text(
            f"cache:  {roots.get('cache', '?')}",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
            selectable=True,
        ),
        ft.Text(
            f"temp:   {roots.get('temp', '?')}",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
            selectable=True,
        ),
        ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
        ft.Text(
            "proot-distro areas",
            size=tokens.FONT_SM,
            weight=ft.FontWeight.BOLD,
            color=theme.text(),
        ),
    ]
    from screens.formatting import format_size as _fmt_size

    for key, label in (
        ("containers", "containers/"),
        ("locks", "locks/"),
        ("sessions", "sessions/"),
        ("oci_layers", "cache oci_layers/"),
        ("oci_manifests", "cache oci_manifests/"),
        ("build_index", "build_cache_index.json"),
        ("temp_exports", "temp exports/"),
    ):
        area = detail.get(key) or {}
        rows.append(
            ft.Text(
                f"{label}  {_fmt_size(area.get('bytes', 0))} · {area.get('count', 0)} file(s)",
                size=tokens.FONT_XS,
                color=theme.text_dim(),
                selectable=True,
            )
        )
    busy = detail.get("busy_locks") or []
    rows.append(ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()))
    rows.append(
        ft.Text(
            "Busy locks: " + (", ".join(busy) if busy else "none"),
            size=tokens.FONT_XS,
            color=theme.warn() if busy else theme.text_dim(),
            selectable=True,
        )
    )
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Storage Layout", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=rows, spacing=tokens.SPACE_XS, tight=True, scroll=ft.ScrollMode.AUTO
            ),
            actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
        )
    )


def open_storage_detail(page: ft.Page, methods) -> None:
    """Refresh state.storage_detail, then show the layout dialog."""

    async def _load() -> None:
        await methods.refresh_storage_detail()
        show_storage_dialog(page, state.storage_detail or {})

    page.run_task(_load)


def open_env_dialog(page: ft.Page) -> None:
    def _row(k: str, v: str) -> ft.Control:
        return ft.Text(f"{k} = {v}", size=tokens.FONT_XS, color=theme.text_dim(), selectable=True)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Environment", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[
                    _row("PD_PROOT_BIN", os.environ.get("PD_PROOT_BIN", "(unset)")),
                    _row(
                        "FLET_APP_STORAGE_DATA", os.environ.get("FLET_APP_STORAGE_DATA", "(unset)")
                    ),
                    _row(
                        "FLET_APP_STORAGE_CACHE",
                        os.environ.get("FLET_APP_STORAGE_CACHE", "(unset)"),
                    ),
                    _row(
                        "FLET_APP_STORAGE_TEMP", os.environ.get("FLET_APP_STORAGE_TEMP", "(unset)")
                    ),
                    _row("PD_FORCE_NO_COLORS", os.environ.get("PD_FORCE_NO_COLORS", "(unset)")),
                    _row(
                        "PD_DOCKER_AUTH",
                        "(set — see Registry Authentication)"
                        if os.environ.get("PD_DOCKER_AUTH")
                        else "(unset)",
                    ),
                ],
                spacing=tokens.SPACE_XS,
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
        )
    )


def open_probe_dialog(page: ft.Page, probe_passed: bool, probe_summary: str, check_probe) -> None:
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                "System Environment Probe", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
            ),
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"Probe status: {'PASSED' if probe_passed else 'WARNING'}",
                        size=tokens.FONT_SM,
                        weight=ft.FontWeight.BOLD,
                        color=theme.ok() if probe_passed else theme.warn(),
                    ),
                    ft.Text(
                        probe_summary or "Payload verified and 16 KiB page alignment confirmed.",
                        size=tokens.FONT_XS,
                        color=theme.text_dim(),
                    ),
                ],
                tight=True,
                spacing=tokens.SPACE_SM,
            ),
            actions=[
                ft.TextButton(
                    "Re-check",
                    on_click=lambda _e: (page.pop_dialog(), page.run_task(check_probe)),
                ),
                ft.TextButton("Close", on_click=lambda _e: page.pop_dialog()),
            ],
        )
    )


def open_licenses(page: ft.Page) -> None:
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Open-Source Licenses", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=licenses_view(),
            actions=[ft.TextButton("Close", on_click=lambda _e: page.pop_dialog())],
        )
    )


def confirm_clear_cache(page: ft.Page, on_yes) -> None:
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                "Clear cached downloads?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
            ),
            content=ft.Text(
                "Removes downloaded OCI image layers. Installed containers "
                "continue working without interruption.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Clear",
                    on_click=lambda _e: (page.pop_dialog(), on_yes()),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )


def confirm_remove_cached(page: ft.Page, identifier: str, on_yes) -> None:
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Remove cached image {identifier}?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD
            ),
            content=ft.Text(
                f"Removes the cached layers for {identifier}. Installed containers remain operational.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Remove",
                    on_click=lambda _e: (page.pop_dialog(), on_yes()),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL),
                        bgcolor=theme.warn(),
                    ),
                ),
            ],
        )
    )
