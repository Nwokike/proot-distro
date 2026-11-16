"""The shell login-option sheet.

Every option here is one upstream login flag, and every one is validated
against the CONTAINER before a session is created: the user must exist in its
/etc/passwd (upstream resolves `--user` there and exits 1 otherwise), the work
directory must exist in its rootfs, binds must point at real host paths, and
`--emulator` must be a real QEMU binary. Nothing is offered that cannot run,
and nothing fails as a raw traceback.
"""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from components.ui import house_field, pill_dropdown
from core import theme, tokens
from core.constants import GUEST_HOME
from services import proot_service
from services.session_service.login_options import parse_env_bind


def _field(label: str, hint: str, value: str = "") -> ft.TextField:
    return house_field(label=label, hint=hint, value=value)


def _multiline(label: str, hint: str) -> ft.TextField:
    return house_field(label=label, hint=hint, multiline=True, min_lines=2)


def option_error(container: str, users: list[dict], values: dict) -> str | None:
    """Validate the sheet's values against the container before any proot run.

    Returns a user-facing sentence, or None when every option can work.
    Upstream resolves `--user` in the container's /etc/passwd (exit 1 when the
    name is unknown), chdirs into `--work-dir`, binds host paths as given and
    execs `--emulator` — so each is checked here against the same sources."""
    names = [u["name"] for u in users] or ["root"]
    user = str(values.get("user") or "root").strip()
    name = user.split(":", 1)[0]
    if not name:
        return "enter a user name, a uid, or name:group"
    if not name.isdigit() and name not in names:
        shown = ", ".join(names[:8]) + ("…" if len(names) > 8 else "")
        return f"no user {name!r} in {container}. It defines: {shown}"

    workdir = str(values.get("work_dir") or "").strip()
    if workdir and not proot_service.guest_path_exists(container, workdir):
        return f"work dir {workdir} does not exist in {container}"

    _env_lines, bind_lines, error = parse_env_bind(values.get("env_text"), values.get("bind_text"))
    if error:
        return error
    for line in bind_lines:
        host = line.split(":", 1)[0]
        if not host:
            return f"bind needs a host path: {line}"
        if not Path(host).exists():
            return f"bind source does not exist on this device: {host}"

    emu = str(values.get("emulator") or "").strip()
    if emu and not (Path(emu).is_file() and os.access(emu, os.X_OK)):
        return f"emulator is not an executable file: {emu}"
    return None


def ask_shell_options(page: ft.Page, methods, container: str) -> None:
    """Open the login-option sheet for `container`."""
    users = proot_service.container_users(container)
    names = [u["name"] for u in users]
    if "root" not in names:
        names.insert(0, "root")

    chosen_user = {"value": "root"}
    user_pill = pill_dropdown(
        "User",
        ft.Icons.PERSON_ROUNDED,
        names,
        "root",
        lambda value: chosen_user.update(value=value),
        tooltip="Login user (--user), read from this container's /etc/passwd",
    )
    user_extra = _field("or uid / name:group", "e.g. 1000  or  app:app")

    work_dir = _field("Work dir (-w)", GUEST_HOME)
    env = _multiline("Env (-e VAR=VALUE)", "one per line")
    bind = _multiline("Bind (-b HOST[:GUEST])", "one per line")

    def _toggle(label: str) -> ft.Switch:
        """House toggle: the scaled switch with a compact label in front."""
        sw = ft.Switch(value=False, scale=tokens.SWITCH_SCALE)
        toggle_rows[label] = ft.Row(
            controls=[ft.Text(label, size=tokens.FONT_XS, color=theme.text()), sw],
            spacing=tokens.SPACE_XXS,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return sw

    toggle_rows: dict[str, ft.Control] = {}
    shared_tmp = _toggle("Shared tmp (--shared-tmp)")
    shared_home = _toggle("Shared home (--shared-home)")
    fix_low_ports = _toggle("Fix low ports (--fix-low-ports)")
    isolated = _toggle("Isolated (--isolated)")
    emulator = _field(
        "Emulator (--emulator PATH)",
        "/path/to/qemu-<arch> (foreign-arch images only)",
    )
    hostname = _field("Hostname (--hostname)", "guest hostname")
    kernel = _field("Kernel release (--kernel)", "uname -r string")

    def _save(_e) -> None:
        user = (user_extra.value or "").strip() or chosen_user["value"] or "root"
        values = {
            "user": user,
            "work_dir": (work_dir.value or "").strip(),
            "env_text": env.value,
            "bind_text": bind.value,
            "emulator": (emulator.value or "").strip(),
        }
        problem = option_error(container, users, values)
        if problem:
            methods.show_snack(problem)
            return

        env_lines, bind_lines, _ = parse_env_bind(env.value, bind.value)
        page.pop_dialog()
        page.run_task(
            methods.open_session_with_options,
            container,
            {
                "user": user,
                "work_dir": values["work_dir"] or None,
                "env": env_lines,
                "bind": bind_lines,
                "shared_tmp": bool(shared_tmp.value),
                "shared_home": bool(shared_home.value),
                "fix_low_ports": bool(fix_low_ports.value),
                "isolated": bool(isolated.value),
                "emulator": values["emulator"] or None,
                "hostname": (hostname.value or "").strip() or None,
                "kernel": (kernel.value or "").strip() or None,
            },
        )

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text(
                f"Shell options: {container}",
                size=tokens.FONT_LG,
                weight=ft.FontWeight.BOLD,
            ),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[user_pill, user_extra],
                        spacing=tokens.SPACE_SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    work_dir,
                    env,
                    bind,
                    hostname,
                    kernel,
                    emulator,
                    toggle_rows["Shared tmp (--shared-tmp)"],
                    toggle_rows["Shared home (--shared-home)"],
                    toggle_rows["Fix low ports (--fix-low-ports)"],
                    toggle_rows["Isolated (--isolated)"],
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
