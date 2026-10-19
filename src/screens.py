"""Screens — distro manager and settings, as state-driven component views.

These views never mutate their own controls (that is what "Frozen controls
cannot be updated" was). Every display value is read from the observable
`core.state.state` during render; user actions only write state or call
controller methods. Local text inputs hold their transient values in
`use_state` so they survive re-renders.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from pathlib import Path

import flet as ft

from components import card, empty_state, hints_card, probe_banner, section_header
from core import theme
from core.state import state
from state.controller_ctx import ControllerMethodsCtx

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
    ("BSD-3-Clause.txt", "BSD-3-Clause"),
)


def _fmt_size(n: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GiB"


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


# ── distro manager ───────────────────────────────────────────────────────────


@ft.component
def DistroView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    query, set_query = ft.use_state("")
    name, set_name = ft.use_state("")

    def _field() -> ft.TextField:
        return ft.TextField(
            hint_text="docker image ref (e.g. debian:bookworm)",
            value=query,
            text_size=12,
            height=40,
            expand=True,
            border=ft.OutlineInputBorder(side=ft.BorderSide(1, theme.surface_alt())),
            on_change=lambda e: set_query(e.control.value),
            on_submit=lambda _e: _consent_install(),
        )

    def _consent_install() -> None:
        image = query.strip()
        if not image or st.installing:
            return

        def _confirm(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.install_distro, image, name.strip())

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Download and install"),
                content=ft.Column(
                    controls=[
                        ft.Text(image, size=12, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            "Download size is not known until the registry responds. "
                            "Typical base images: Alpine ~8 MB, Debian ~30 MB, "
                            "Ubuntu ~75 MB — an estimate, not a measurement.",
                            size=11,
                            color=theme.text_dim(),
                        ),
                        ft.Text(
                            "The download starts only after you tap Install. "
                            "Package downloads inside the container happen only "
                            "when you run commands.",
                            size=11,
                            color=theme.text_dim(),
                        ),
                    ],
                    spacing=4,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.TextButton("Install", on_click=_confirm),
                ],
            )
        )

    def _search() -> None:
        q = query.strip()
        if q:
            page.run_task(methods.search_distro, q)

    def _hit_row(hit: dict) -> ft.Control:
        label = hit.get("name", "?")
        stars = _fmt_count(hit.get("stars", 0))
        pulls = _fmt_count(hit.get("pulls", 0))
        official = " [official]" if hit.get("official") else ""
        desc = (hit.get("description") or "")[:80]

        def _pick(_e) -> None:
            set_query(label)
            set_name(label.split(":")[0].split("/")[-1])

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        f"{label}{official}  ★{stars} ⤓{pulls}",
                        size=12,
                        color=theme.text(),
                    ),
                    ft.Text(desc, size=10, color=theme.text_dim()),
                ],
                spacing=0,
            ),
            on_click=_pick,
            ink=True,
            padding=4,
        )

    def _container_row(row: dict) -> ft.Control:
        cname = row.get("name", "?")

        def _remove(_e) -> None:
            def _yes(_e) -> None:
                page.pop_dialog()
                page.run_task(methods.remove_container, cname)

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(f"Remove {cname}?"),
                    content=ft.Text(
                        "The container's files are deleted. Cached downloads stay.",
                        size=12,
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                        ft.TextButton("Remove", on_click=_yes),
                    ],
                )
            )

        def _reset(_e) -> None:
            def _yes(_e) -> None:
                page.pop_dialog()
                page.run_task(methods.reset_container, cname)

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(f"Reset {cname}?"),
                    content=ft.Text(
                        "The container is wiped and reinstalled from the cached "
                        "image — no re-download when the layers are cached.",
                        size=12,
                    ),
                    actions=[
                        ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                        ft.TextButton("Reset", on_click=_yes),
                    ],
                )
            )

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Column(
                        controls=[
                            ft.Text(cname, size=13, weight=ft.FontWeight.BOLD, color=theme.text()),
                            ft.Text(
                                f"{row.get('image', '')} · "
                                f"{_fmt_size(row.get('size_bytes', 0))} · "
                                f"{row.get('arch', '')}",
                                size=11,
                                color=theme.text_dim(),
                            ),
                        ],
                        spacing=0,
                        expand=True,
                    ),
                    ft.Button("Reset", on_click=_reset, height=32),
                    ft.Button("Remove", on_click=_remove, height=32),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=theme.surface(),
            padding=4,
            border_radius=8,
        )

    controls: list[ft.Control] = [
        hints_card(st.hints_dismissed, lambda _e: setattr(state, "hints_dismissed", True)),
        section_header("Install", "Any Docker image — search, or type a reference"),
    ]
    if not st.probe_passed:
        controls.append(probe_banner(st.probe_summary))
    controls.append(
        card(
            ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            _field(),
                            ft.Button("Install", on_click=lambda _e: _consent_install(), height=40),
                        ]
                    ),
                    ft.Row(
                        controls=[
                            ft.TextField(
                                hint_text="name (optional)",
                                value=name,
                                width=150,
                                text_size=12,
                                height=40,
                                border=ft.OutlineInputBorder(
                                    side=ft.BorderSide(1, theme.surface_alt())
                                ),
                                on_change=lambda e: set_name(e.control.value),
                            ),
                            ft.Button("Search", on_click=lambda _e: _search(), height=40),
                        ]
                    ),
                    ft.Text(st.search_status, size=11, color=theme.text_dim()),
                    ft.Column(
                        controls=[_hit_row(hit) for hit in st.search_results[:12]],
                        spacing=2,
                    ),
                ],
                spacing=4,
            )
        )
    )

    if st.installing:
        progress = f"installing {st.installing} — {st.install_stage}"
    elif st.busy_note:
        progress = st.busy_note
    else:
        progress = ""
    controls.append(ft.Text(progress, size=11, color=theme.AppColors.ACCENT))

    controls.append(section_header("Containers", ""))
    if st.containers:
        controls.append(ft.Column(controls=[_container_row(r) for r in st.containers], spacing=4))
    else:
        controls.append(empty_state("No containers yet", "Install any Docker image to begin."))

    return ft.Column(controls=controls, spacing=4, expand=True, scroll=ft.ScrollMode.AUTO)


# ── settings ─────────────────────────────────────────────────────────────────


@ft.component
def SettingsView() -> ft.Control:
    st, _ = ft.use_state(state)
    methods = ft.use_context(ControllerMethodsCtx)
    page = ft.context.page
    token, set_token = ft.use_state(st.docker_token)

    def _cycle_theme() -> None:
        # The one cycle definition lives in the controller (the header button
        # calls the same method) so the two entry points cannot diverge.
        page.run_task(methods.cycle_theme_mode)

    def _save_token() -> None:
        page.run_task(methods.set_docker_token, token)

    def _clear_cache() -> None:
        def _yes(_e) -> None:
            page.pop_dialog()
            page.run_task(methods.clear_cache)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Clear cached downloads?"),
                content=ft.Text(
                    "Removes the downloaded image layers. Installed containers "
                    "keep working; a later reinstall re-downloads.",
                    size=12,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda _e: page.pop_dialog()),
                    ft.TextButton("Clear", on_click=_yes),
                ],
            )
        )

    def _licenses(_e) -> None:
        def _close(_e) -> None:
            page.pop_dialog()

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("Open-source licenses"),
                content=licenses_view(),
                actions=[ft.TextButton("Close", on_click=_close)],
            )
        )

    mode_label = {"system": "System", "light": "Light", "dark": "Dark"}[st.theme_mode]

    return ft.Column(
        controls=[
            hints_card(st.hints_dismissed, lambda _e: setattr(state, "hints_dismissed", True)),
            section_header("Appearance", "Theme follows the system unless you pick one"),
            card(
                ft.Row(
                    controls=[
                        ft.Text(f"Theme: {mode_label}", size=12, color=theme.text()),
                        ft.TextButton("Change", on_click=lambda _e: _cycle_theme()),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            ),
            section_header("Storage", "Proot state lives in this app's private files"),
            card(
                ft.Column(
                    controls=[
                        ft.Text(
                            f"containers + cache: {_fmt_size(st.storage_bytes)}"
                            + (f" · {st.cached_count} cached image(s)" if st.cached_count else ""),
                            size=12,
                            color=theme.text_dim(),
                        ),
                        ft.TextButton("Clear cached downloads", on_click=lambda _e: _clear_cache()),
                        ft.Text(
                            "Package downloads happen inside your container, from "
                            "the distro's own mirrors, only when you run a command "
                            "or tap an update action.",
                            size=10,
                            color=theme.text_dim(),
                        ),
                    ],
                    spacing=4,
                )
            ),
            section_header("Docker Hub", "Optional — a token raises your pull limits"),
            card(
                ft.Column(
                    controls=[
                        ft.TextField(
                            hint_text="Docker Hub token (optional)",
                            value=token,
                            password=True,
                            text_size=12,
                            height=40,
                            border=ft.OutlineInputBorder(
                                side=ft.BorderSide(1, theme.surface_alt())
                            ),
                            on_change=lambda e: set_token(e.control.value),
                        ),
                        ft.Text(
                            "Stored on this device only. It lifts you from the "
                            "anonymous pull limit to your account's limit.",
                            size=10,
                            color=theme.text_dim(),
                        ),
                        ft.TextButton("Save token", on_click=lambda _e: _save_token()),
                    ],
                    spacing=4,
                )
            ),
            section_header("About", ""),
            card(
                ft.Column(
                    controls=[
                        ft.ListTile(
                            title=ft.Text("Open-source licenses", size=13),
                            on_click=_licenses,
                        ),
                        ft.Text(
                            "Unofficial Flet-based Android client. Not affiliated "
                            "with the Termux project.",
                            size=10,
                            color=theme.text_dim(),
                        ),
                        ft.Text(
                            f"Runtime probe: {st.probe_summary or '—'}",
                            size=10,
                            color=theme.text_dim(),
                        ),
                        ft.TextButton(
                            "Re-check probe",
                            on_click=lambda _e: page.run_task(methods.check_probe),
                        ),
                    ],
                    spacing=2,
                )
            ),
        ],
        spacing=4,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )


# ── licenses (compliance §3.3 content contract) ──────────────────────────────


def _dist_license(dist: str) -> tuple[str, str]:
    try:
        meta = importlib_metadata.metadata(dist)
    except Exception:
        return ("", "")
    version = meta.get("Version", "")
    lic = meta.get("License-Expression") or meta.get("License") or ""
    return (version, lic)


def _native_entries() -> list[dict]:
    """Native payload provenance from the flet_proot wheel manifest (no hardcoding)."""
    entries: list[dict] = []
    try:
        import flet_proot  # type: ignore[import-not-found]

        version = getattr(flet_proot, "VERSION", "")
        for src in getattr(flet_proot, "SOURCES", []) or []:
            if not isinstance(src, dict):
                continue
            package = src.get("package", "?")
            entries.append(
                {
                    "component": package,
                    "version": str(src.get("version", "")),
                    "license": _NATIVE_LICENSES.get(package, ""),
                    "source": src.get("url", ""),
                    "via": f"flet-proot {version}",
                }
            )
    except Exception:
        pass
    return entries


def _py_entries() -> list[dict]:
    entries = []
    for dist in _PY_DISTS:
        version, lic = _dist_license(dist)
        if version:
            entries.append({"component": dist, "version": version, "license": lic, "source": ""})
    return entries


def licenses_view() -> ft.Control:
    """Licenses screen content (compliance §3.3). Plain function: it is also
    built inside dialog handlers, where a @ft.component would raise."""
    entries = _native_entries() + _py_entries()
    rows = [
        ft.Text(
            f"• {e['component']} {e['version']}"
            + (f" ({e['license']})" if e.get("license") else "")
            + (f" — {e['source']}" if e.get("source") else ""),
            size=11,
            color=theme.text(),
            selectable=True,
        )
        for e in entries
    ]

    texts = []
    for fname, label in _TEXT_FILES:
        path = _LICENSES_DIR / fname
        body = path.read_text(encoding="utf-8")[:6000] if path.is_file() else "(text missing)"
        texts.append(
            ft.ExpansionTile(
                title=ft.Text(label, size=13),
                controls=[ft.Container(content=ft.Text(body, size=9, selectable=True), padding=8)],
            )
        )

    return ft.Column(
        controls=[
            ft.Text(
                "This app includes third-party software. Full texts below; "
                "the same texts ship in the repository's LICENSES/ directory.",
                size=11,
                color=theme.text_dim(),
            ),
            ft.Column(controls=rows, spacing=2),
            ft.Divider(),
            ft.Text(
                "Source code offer (GPL-2.0 §3(b) / GPL-3.0 §6(b)). The complete "
                "machine-readable Corresponding Source for the GPL-licensed "
                "components above — including this application — is available "
                "at https://github.com/Nwokike/proot-distro and will remain "
                "available for at least three (3) years from the date of each "
                "release. Upstream: github.com/termux/proot, "
                "github.com/termux/proot-distro, github.com/termux/termux-packages "
                "(build recipes), talloc.samba.org.",
                size=10,
                color=theme.text_dim(),
                selectable=True,
            ),
            ft.Divider(),
            ft.Text(
                "Debian is a registered trademark owned by Software in the "
                "Public Interest, Inc. This app is not affiliated with, "
                "endorsed by, or sponsored by the Debian project.",
                size=10,
                color=theme.text_dim(),
            ),
            ft.Text(
                "Ubuntu and Canonical are registered trademarks of Canonical "
                "Ltd. This app is not affiliated with, endorsed by, or "
                "sponsored by Canonical.",
                size=10,
                color=theme.text_dim(),
            ),
            ft.Divider(),
            *texts,
        ],
        spacing=4,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
