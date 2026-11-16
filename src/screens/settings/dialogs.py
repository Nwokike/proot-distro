"""Settings dialogs as module-level functions (moved out of SettingsView).

Each takes its dependencies explicitly (page / state bits / callbacks) so the
component in __init__.py stays a thin assembly of cards + rows.
"""

from __future__ import annotations

import contextlib

import flet as ft

from core import theme, tokens
from core.constants import APP_NAME, APP_VERSION
from core.state import state
from screens.license_view import licenses_view

_TERMINAL_DISPLAY_LINES = 500


def open_debugging_output(page: ft.Page) -> None:
    """The full diagnostic log (Settings shows the last 20 lines inline): app
    logs in a green on-dark monospace box, with Copy / Clear / Close."""
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

        async def _do_copy():
            clipboard = getattr(page, "clipboard", None)
            if clipboard is None:
                return
            await clipboard.set("\n".join(in_memory_log_handler.get_logs()))
            show_snack(page, "Logs copied to clipboard")

        page.run_task(_do_copy)

    def _clear_logs(_e):
        # Reopen the dialog so the log re-renders fresh (the house guard
        # forbids imperative control mutations in screens/).
        in_memory_log_handler.clear_logs()
        with contextlib.suppress(Exception):
            page.pop_dialog()
        open_debugging_output(page)

    terminal_dlg = ft.AlertDialog(
        modal=False,
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.TERMINAL_ROUNDED, color=theme.primary(), size=tokens.ICON_MD),
                ft.Text(
                    "Debugging output",
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
                        "App diagnostics: sessions, installs, ads, errors.",
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
                        height=tokens.DIALOG_LOG_HEIGHT,
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
    from components.ui import changelog_rows

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"What's New in {APP_NAME} v{APP_VERSION}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=changelog_rows(APP_VERSION),
                spacing=tokens.SPACE_SM,
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


def open_probe_dialog(page: ft.Page, probe_passed: bool, probe_summary: str, check_probe) -> None:
    async def _force_check_probe() -> None:
        # The explicit "check" always re-probes (bootstrap_env is memoized).
        await check_probe(True)

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
                        probe_summary or "Environment probe passed.",
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
                    on_click=lambda _e: (page.pop_dialog(), page.run_task(_force_check_probe)),
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


def confirm_exit(page: ft.Page, on_yes) -> None:
    """Exit kills every shell and display, so it asks first."""

    def _yes(_e) -> None:
        page.pop_dialog()
        on_yes()

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Exit the app?", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                "Every shell and display session stops. Container files stay on this device.",
                size=tokens.FONT_SM,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton("Exit", on_click=_yes),
            ],
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


def confirm_simple(page: ft.Page, title: str, body: str, label: str, on_yes) -> None:
    """A one-step destructive confirmation (sweep/build-cache parity)."""

    def _yes(_e) -> None:
        page.pop_dialog()
        on_yes()

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(title, size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Text(body, size=tokens.FONT_SM),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton("Clear" if label == "Clear" else label, on_click=_yes),
            ],
        )
    )
