"""Open-source license notices and bundled license texts."""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path

import flet as ft

from core import theme, tokens
from core.constants import APP_NAME, APP_VERSION

_LICENSES_DIR = Path(__file__).resolve().parent.parent / "LICENSES"
_NATIVE_LICENSES = {
    "proot": "GPL-2.0",
    "libtalloc": "GPL-3.0",
    "libandroid-shmem": "BSD-3-Clause",
}
_PY_DISTS = (
    "proot-distro",
    "flet",
    "flet-ads",
    "flet-terminal",
    "msgpack",
    "anyio",
    "httpx",
    "httpcore",
    "h11",
    "idna",
    "certifi",
    "typing-extensions",
    "oauthlib",
    "repath",
    "six",
)
_TEXT_FILES = (
    ("GPL-2.0.txt", "GPL-2.0"),
    ("GPL-3.0.txt", "GPL-3.0"),
    ("Apache-2.0.txt", "Apache-2.0"),
    ("MIT.txt", "MIT"),
    ("BSD-3-Clause.txt", "BSD-3-Clause"),
    ("MPL-2.0.txt", "MPL-2.0"),
    ("PSF-2.0.txt", "PSF-2.0"),
)


def _dist_license(dist: str) -> tuple[str, str]:
    try:
        meta = importlib_metadata.metadata(dist)
    except Exception:
        return ("", "")
    version = meta.get("Version", "")
    lic = meta.get("License-Expression") or meta.get("License") or ""
    return (version, lic)


def licenses_view() -> ft.Control:
    rows: list[ft.Control] = [
        ft.Text(
            f"{APP_NAME} v{APP_VERSION} incorporates open-source components "
            "licensed under free and copyleft licenses.",
            size=tokens.FONT_SM,
        ),
        ft.Divider(),
        ft.Text("GPL §6(b) Source Code Offer", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Source code offer (GPL-2.0 §3(b) / GPL-3.0 §6(b)). The complete "
            "machine-readable Corresponding Source for the GPL-licensed "
            "components above — including this application — is available "
            "at https://github.com/Nwokike/proot-distro and will remain "
            "available for at least three (3) years from the date of each "
            "release. Upstream: github.com/termux/proot, "
            "github.com/termux/proot-distro, github.com/termux/termux-packages "
            "(build recipes), talloc.samba.org.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
            selectable=True,
        ),
        ft.Divider(),
        ft.Text(
            "Debian is a registered trademark owned by Software in the "
            "Public Interest, Inc. This app is not affiliated with, "
            "endorsed by, or sponsored by the Debian project.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Text(
            "Ubuntu and Canonical are registered trademarks of Canonical "
            "Ltd. This app is not affiliated with, endorsed by, or "
            "sponsored by Canonical.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Text(
            "Alpine Linux is a registered trademark of the Alpine Linux "
            "Foundation. This app is not affiliated with, endorsed by, or "
            "sponsored by the Alpine Linux project.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Text(
            "This is an unofficial Flet-based Android client. It is not "
            "affiliated with, endorsed by, or sponsored by the Termux "
            "project or the PRoot-Distro project.",
            size=tokens.FONT_XS,
            color=theme.text_dim(),
        ),
        ft.Divider(),
        ft.Text("Native Payload Components", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD),
    ]
    for pkg, lic in _NATIVE_LICENSES.items():
        rows.append(
            ft.ListTile(
                title=ft.Text(pkg, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"License: {lic}", size=tokens.FONT_XS, color=theme.text_dim()),
            )
        )
    rows.append(ft.Divider())
    rows.append(ft.Text("Python Dependencies", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD))
    for dist in _PY_DISTS:
        ver, lic = _dist_license(dist)
        rows.append(
            ft.ListTile(
                title=ft.Text(
                    f"{dist} {ver}".strip(), size=tokens.FONT_SM, weight=ft.FontWeight.BOLD
                ),
                subtitle=ft.Text(
                    f"License: {lic or 'See license text'}",
                    size=tokens.FONT_XS,
                    color=theme.text_dim(),
                ),
            )
        )
    rows.append(ft.Divider())
    rows.append(ft.Text("License Texts", size=tokens.FONT_MD, weight=ft.FontWeight.BOLD))
    for fname, label in _TEXT_FILES:
        path = _LICENSES_DIR / fname
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else "(text missing)"
        )
        rows.append(
            ft.ExpansionTile(
                title=ft.Text(label, size=tokens.FONT_SM, weight=ft.FontWeight.BOLD),
                controls=[
                    ft.Container(
                        content=ft.Text(text, size=tokens.FONT_XS, font_family="JetBrains Mono"),
                        padding=tokens.SPACE_SM,
                    )
                ],
            )
        )
    return ft.Column(controls=rows, scroll=ft.ScrollMode.AUTO, expand=True)
