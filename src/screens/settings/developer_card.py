"""Settings -> Developer tools card with the inline debugging output."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from screens.settings_components import _setting_row, _settings_card


def build_developer_card(
    st,
    *,
    narrow: bool = False,
    lines: list[str],
    env_value: str,
    on_build,
    on_probe,
    on_environment,
    on_copy,
    on_clear,
    on_full_log,
    on_report=None,
) -> ft.Control:
    """Rows carry their live value; the log tail is the value of Debugging
    output, not a button that hides it behind a dialog."""
    debug_box = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "\n".join(lines) if lines else "No activity recorded yet.",
                    size=tokens.FONT_XXS,
                    font_family=tokens.MONO_FONT,
                    color=theme.ok() if lines else theme.text_dim(),
                    selectable=True,
                ),
                ft.Row(
                    controls=[
                        ft.TextButton("Copy", icon=ft.Icons.COPY_ROUNDED, on_click=on_copy),
                        *(
                            [
                                ft.TextButton(
                                    "Report",
                                    icon=ft.Icons.BUG_REPORT_ROUNDED,
                                    tooltip="Copy the log and open GitHub Issues",
                                    on_click=on_report,
                                )
                            ]
                            if on_report is not None
                            else []
                        ),
                        ft.TextButton(
                            "Clear", icon=ft.Icons.DELETE_SWEEP_ROUNDED, on_click=on_clear
                        ),
                        ft.TextButton(
                            "Full log",
                            icon=ft.Icons.OPEN_IN_FULL_ROUNDED,
                            on_click=on_full_log,
                        ),
                    ],
                    spacing=tokens.SPACE_XS,
                ),
            ],
            spacing=tokens.SPACE_XS,
            tight=True,
        ),
        bgcolor=ft.Colors.with_opacity(tokens.OPACITY_SUBTLE, theme.text()),
        border=ft.Border.all(tokens.HAIRLINE, theme.glass_border()),
        border_radius=tokens.RADIUS_SM,
        padding=tokens.SPACE_MD,
    )

    return _settings_card(
        [
            _setting_row(
                ft.Icons.BUILD_ROUNDED,
                "Build & push",
                "Dockerfile images: build stages, tags, outputs and registry push",
                value="stages · tags · push",
                on_tap=on_build,
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
                if st.probe_passed
                else ft.Icons.WARNING_ROUNDED,
                "Environment Probe",
                st.probe_summary or "Native library directory and proot payload ready",
                value="passed" if st.probe_passed else "check",
                on_tap=on_probe,
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            # CollabShell's row shape (execution_section.py): icon, title +
            # italic live summary, one Manage button.
            _setting_row(
                ft.Icons.TUNE_ROUNDED,
                "Default environment",
                "Injected into every new shell and display",
                ft.FilledButton(
                    "Manage",
                    on_click=on_environment,
                    height=tokens.CONTROL_SM,
                ),
                value=env_value,
                stacked=narrow,
            ),
            ft.Divider(height=tokens.HAIRLINE, color=theme.glass_border()),
            _setting_row(
                ft.Icons.NEWSPAPER_ROUNDED,
                "Debugging output",
                "Last 20 app log lines: sessions, installs, ads, errors",
            ),
            ft.Container(
                content=debug_box,
                padding=ft.Padding(tokens.SPACE_LG, 0, tokens.SPACE_LG, tokens.SPACE_MD),
            ),
        ]
    )
