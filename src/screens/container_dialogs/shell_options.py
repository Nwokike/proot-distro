"""The shell login-option sheet."""

from __future__ import annotations

import flet as ft

from core import theme, tokens
from core.constants import GUEST_HOME


def ask_shell_options(page: ft.Page, methods, container: str) -> None:
    """The upstream login options we wrap one-to-one (user/work-dir/env/bind/
    shared homes/tmp, low-port fixing, isolated mode) — opened from the menu;
    the card keeps exactly three inline items."""
    user = ft.TextField(
        label="User (-u)",
        value="root",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    work_dir = ft.TextField(
        label="Work dir (-w)",
        hint_text=GUEST_HOME,
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    env = ft.TextField(
        label="Env (-e VAR=VALUE)",
        hint_text="one per line",
        text_size=tokens.FONT_SM,
        multiline=True,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    bind = ft.TextField(
        label="Bind (-b PATH[:PATH])",
        hint_text="one per line",
        text_size=tokens.FONT_SM,
        multiline=True,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    shared_tmp = ft.Switch(label="Shared tmp (--shared-tmp)", value=False)
    shared_home = ft.Switch(label="Shared home (--shared-home)", value=False)
    fix_low_ports = ft.Switch(label="Fix low ports (--fix-low-ports)", value=False)
    isolated = ft.Switch(label="Isolated (--isolated)", value=False)
    emulator = ft.TextField(
        # Upstream treats --emulator as a QEMU BINARY PATH (not a flag).
        label="Emulator (--emulator PATH)",
        hint_text="/path/to/qemu-<arch> — needed only for foreign-arch images",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    hostname = ft.TextField(
        label="Hostname (--hostname)",
        hint_text="guest hostname",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )
    kernel = ft.TextField(
        label="Kernel release (--kernel)",
        hint_text="uname -r string",
        text_size=tokens.FONT_SM,
        height=tokens.CONTROL_INPUT,
        border=ft.OutlineInputBorder(
            border_radius=tokens.RADIUS_MD, side=ft.BorderSide(1, theme.surface_alt())
        ),
    )

    def _save(_e) -> None:
        from services.session_service.login_options import parse_env_bind

        env_lines, bind_lines, error = parse_env_bind(env.value, bind.value)
        if error:
            methods.show_snack(error)
            return
        page.pop_dialog()
        opts = {
            "user": (user.value or "").strip() or "root",
            "work_dir": (work_dir.value or "").strip() or None,
            "env": env_lines,
            "bind": bind_lines,
            "shared_tmp": bool(shared_tmp.value),
            "shared_home": bool(shared_home.value),
            "fix_low_ports": bool(fix_low_ports.value),
            "isolated": bool(isolated.value),
            "emulator": (emulator.value or "").strip() or None,
            "hostname": (hostname.value or "").strip() or None,
            "kernel": (kernel.value or "").strip() or None,
        }
        page.run_task(methods.open_session_with_options, container, opts)

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Shell options — {container}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=[
                    user,
                    work_dir,
                    env,
                    bind,
                    hostname,
                    kernel,
                    emulator,
                    shared_tmp,
                    shared_home,
                    fix_low_ports,
                    isolated,
                ],
                tight=True,
                spacing=tokens.SPACE_XS,
                scroll=ft.ScrollMode.AUTO,
                width=tokens.DIALOG_WIDTH,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                ft.FilledButton(
                    "Open shell",
                    on_click=_save,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=tokens.RADIUS_PILL)
                    ),
                ),
            ],
        )
    )
