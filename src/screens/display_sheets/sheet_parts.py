"""Building blocks of the display sheet (kept out of launcher_sheet.py).

`launcher_sheet.py` owns the sheet's state and repaint; these are pure
builders: the install cell's placeholder text, one pill of the App | Desktop
switch, the shared "Run as / advanced" block, and the preset row and form.
"""

from __future__ import annotations

import flet as ft

from components.ui import house_field, pill_dropdown
from core import theme, tokens
from core.state import state
from screens.display_sheets.common import _set_setting


def install_cell_placeholder(container: str) -> str:
    """The install cell's starting text when no package manager is known.

    Every distro cannot have a recipe, but every one can still grow a desktop —
    so the cell starts as a commented skeleton the user completes instead of
    disappearing (owner ruling 2026-11-15)."""
    return (
        f"# No supported package manager was detected in {container}.\n"
        "# Paste the install command for this distro below, then Run.\n"
        "# It needs: a session (e.g. xfce4-session), a window manager,\n"
        "# a panel, a terminal, xterm and an icon theme.\n"
        "# The display server (Xvnc) and the viewer already ship with the app.\n"
    )


def mode_pill(label: str, icon: ft.IconData, active: bool, on_click) -> ft.Container:
    """One pill of the Desktop | App switch (Home's Install | Search track)."""
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(
                    icon,
                    size=tokens.ICON_SM,
                    color=theme.WHITE if active else theme.text_dim(),
                ),
                ft.Text(
                    label,
                    size=tokens.FONT_SM,
                    weight=ft.FontWeight.BOLD,
                    color=theme.WHITE if active else theme.text_dim(),
                ),
            ],
            spacing=tokens.SPACE_XS,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=theme.primary() if active else theme.TRANSPARENT,
        border_radius=tokens.RADIUS_SM,
        padding=ft.Padding(tokens.SPACE_MD, tokens.SPACE_XS, tokens.SPACE_MD, tokens.SPACE_XS),
        ink=True,
        expand=True,
        alignment=ft.Alignment.CENTER,
        on_click=on_click,
    )


def settings_pill(
    key: str, label: str, icon: ft.IconData, choices: tuple[tuple[str, str], ...]
) -> ft.Control:
    """A display setting as a house pill; a saved custom value stays selectable."""
    current = str((state.display_settings or {}).get(key, choices[0][0]))
    values = [value for value, _text in choices]
    if current not in values:
        values.append(current)
    return pill_dropdown(
        label,
        icon,
        values,
        current,
        lambda value, k=key: _set_setting(k, value),
        tooltip=label,
        labels=dict(choices),
    )


def add_display_options(display_no: dict) -> list[ft.Control]:
    """The display/viewer options, identical in BOTH modes of the sheet."""
    from services.desk_service import manager as desk_manager

    from .common import _switch_row

    numbers = range(desk_manager.MAX_DISPLAY_NUMBER + 1)
    return [
        ft.Text("Display options", size=tokens.FONT_XS, color=theme.text_dim()),
        ft.Row(
            controls=[
                pill_dropdown(
                    "Display",
                    ft.Icons.TAG_ROUNDED,
                    [str(n) for n in numbers],
                    str(display_no["value"]),
                    lambda value: display_no.__setitem__("value", int(value or 0)),
                    tooltip="Display number (:N), the key of this session",
                    labels={str(n): f":{n}" for n in numbers},
                ),
                settings_pill(
                    "quality",
                    "Quality",
                    ft.Icons.HIGH_QUALITY_ROUNDED,
                    (("50", "50"), ("70", "70"), ("85", "85"), ("95", "95")),
                ),
                settings_pill(
                    "compression",
                    "Compression",
                    ft.Icons.COMPRESS_ROUNDED,
                    (("2", "Fast"), ("6", "Balanced"), ("9", "Smallest")),
                ),
            ],
            spacing=tokens.SPACE_SM,
            wrap=True,
        ),
        ft.Row(
            controls=[
                settings_pill(
                    "geometry",
                    "Resolution",
                    ft.Icons.ASPECT_RATIO_ROUNDED,
                    (
                        ("auto", "Match this phone"),
                        ("1280x720", "1280 x 720"),
                        ("1600x900", "1600 x 900"),
                        ("1920x1080", "1920 x 1080"),
                    ),
                ),
                settings_pill(
                    "resize",
                    "Fit",
                    ft.Icons.FIT_SCREEN_ROUNDED,
                    (
                        ("scale", "Fit the whole desktop"),
                        ("remote", "Remote resize"),
                        ("off", "Actual size"),
                    ),
                ),
                settings_pill(
                    "orientation",
                    "Full screen",
                    ft.Icons.SCREEN_LOCK_LANDSCAPE_ROUNDED,
                    (
                        ("landscape", "Landscape"),
                        ("portrait", "Portrait"),
                        ("auto", "System"),
                    ),
                ),
            ],
            spacing=tokens.SPACE_SM,
            wrap=True,
        ),
        ft.Row(
            controls=[
                _switch_row("LAN: open to Wi-Fi devices", "lan", False),
                _switch_row("Public tunnel: localhost.run", "tunnel", False),
            ],
            spacing=tokens.SPACE_MD,
            wrap=True,
        ),
        ft.Text(
            "LAN binds the server to the phone's Wi-Fi address; the tunnel "
            "publishes a public *.lhr.life URL. Both are protected by the "
            "access code. Share it only with your own devices.",
            size=tokens.FONT_XXS,
            color=theme.text_dim(),
        ),
    ]


def run_as_block(fields: dict) -> ft.Control:
    """The login/run options (upstream `pd login` flags) — shared by both modes."""

    def _field(key: str, label: str, hint: str = "", multiline: bool = False) -> ft.TextField:
        tf = house_field(label=label, hint=hint, multiline=multiline, text_size=tokens.FONT_XS)
        fields[key] = tf
        return tf

    def _toggle(key: str, label: str) -> ft.Control:
        sw = ft.Switch(value=False, scale=tokens.SWITCH_SCALE)
        fields[key] = sw
        return ft.Row(
            controls=[ft.Text(label, size=tokens.FONT_XS, color=theme.text()), sw],
            spacing=tokens.SPACE_XXS,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    fields["user"] = house_field(
        label="User (-u)",
        hint="root",
        text_size=tokens.FONT_XS,
        dense=True,
    )
    return ft.ExpansionTile(
        title=ft.Text("Run as / advanced", size=tokens.FONT_SM, weight=ft.FontWeight.W_600),
        subtitle=ft.Text(
            "User, work dir, env, binds, hostname, kernel, emulator and isolation, "
            "as proot-distro login flags applied to this display.",
            size=tokens.FONT_XXS,
            color=theme.text_dim(),
        ),
        expanded=False,
        controls=[
            fields["user"],
            _field("work_dir", "Work dir (-w)", "/root"),
            _field("env", "Env (-e VAR=VALUE)", "one per line", multiline=True),
            _field("bind", "Bind (-b HOST[:GUEST])", "one per line", multiline=True),
            _field("hostname", "Hostname (--hostname)", "guest hostname"),
            _field("kernel", "Kernel release (--kernel)", "uname -r string"),
            _field("emulator", "Emulator (--emulator PATH)", "qemu-user path (foreign arch)"),
            _toggle("shared_tmp", "Shared tmp"),
            _toggle("shared_home", "Shared home"),
            _toggle("isolated", "Isolated"),
            _toggle("fix_low_ports", "Fix low ports"),
        ],
    )


def preset_tile(preset: dict, on_run, on_delete) -> ft.Control:
    """One saved preset: tap to start it, dustbin to forget it."""
    return ft.ListTile(
        leading=ft.Icon(ft.Icons.BOOKMARK_ROUNDED, color=theme.primary()),
        title=ft.Text(
            str(preset.get("name", "")),
            size=tokens.FONT_SM,
            weight=ft.FontWeight.W_600,
        ),
        subtitle=ft.Text(
            str(preset.get("cmd", "")),
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        on_click=on_run,
        trailing=ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_size=tokens.ICON_SM,
            tooltip="Delete preset",
            on_click=on_delete,
        ),
    )


def new_preset_dialog(page: ft.Page, methods, container: str, default_cmd: str, on_saved) -> None:
    """The preset form: what to run, what to call it, and its own options."""
    name_field = house_field(label="Display name", hint="e.g. My editor")
    cmd_field = house_field(label="Command", hint="e.g. gvim ~/notes.txt", value=default_cmd)
    work_field = house_field(label="Work dir (optional)", hint="/root")
    env_field = house_field(label="Env (optional)", hint="one KEY=VALUE per line", multiline=True)

    async def _save(_ev=None) -> None:
        page.pop_dialog()
        env_lines = [line.strip() for line in (env_field.value or "").splitlines() if line.strip()]
        await methods.save_app_preset(
            {
                "name": name_field.value or "",
                "cmd": cmd_field.value or "",
                "container": container,
                "work_dir": work_field.value or "",
                "env": env_lines,
            }
        )
        on_saved()

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("New preset", size=tokens.FONT_LG, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                controls=[name_field, cmd_field, work_field, env_field],
                spacing=tokens.SPACE_XS,
                tight=True,
                width=min(tokens.DIALOG_WIDTH, 420),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _ev: page.pop_dialog()),
                ft.FilledButton("Save", on_click=lambda _ev: page.run_task(_save)),
            ],
        )
    )
