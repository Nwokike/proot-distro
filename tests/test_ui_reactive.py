"""Offline render contract for the state-driven shell.

Regression cover for the owner-reported "Frozen controls cannot be updated"
RuntimeError: the views must be pure functions of `core.state.state` —
constructing them and re-constructing them after state mutations must never
raise, and the sources must contain no imperative control mutation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("flet")

import flet as ft
from flet.components.component import Renderer

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _fresh_state():
    from core.state import state

    state.containers = []
    state.installing = None
    state.install_stage = ""
    state.busy_note = ""
    state.search_status = ""
    state.search_results = []
    state.storage_bytes = 0
    state.cached_count = 0
    state.probe_passed = True
    state.probe_summary = ""
    state.theme_mode = "dark"
    state.hints_dismissed = False
    yield


def _render(fn) -> object:
    with Renderer().with_context():
        return Renderer().render_component(fn, (), {})


def test_views_construct_in_renderer_context():
    import app_shell
    import screens

    # Component wrappers come back; what matters is no RuntimeError escapes.
    assert _render(app_shell.AppShell) is not None
    assert _render(screens.DistroView) is not None
    assert _render(screens.SettingsView) is not None


def test_brand_hero_builds_and_tints_per_theme():
    """The hero icon lives in the home body (CollabShell pattern)."""
    from components.brand_hero import app_icon_svg, build_brand_hero
    from core.state import state

    svg = app_icon_svg()
    assert b"<svg" in svg[:256]  # the real brand asset, not a placeholder

    state.theme_mode = "dark"
    dark = build_brand_hero("Linux on Android — no root, no Termux")
    assert isinstance(dark, ft.Container)
    icon = dark.content.controls[0]
    assert isinstance(icon, ft.Image) and icon.color == ft.Colors.WHITE
    assert icon.width == 96  # hero-sized, not a toolbar glyph

    state.theme_mode = "light"
    light = build_brand_hero()
    icon = light.content.controls[0]
    assert icon.color is None  # artwork keeps its own colors on light


def test_white_icon_variant_is_gone():
    """The white icon variant was removed by the owner — the README must not
    reference it (no dangling dark-mode asset)."""
    assert not (ROOT / "src" / "assets" / "icon_white.svg").exists()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "icon_white.svg" not in readme


def test_theme_toggle_button_matches_mode():
    from components.app_header import theme_button
    from core.state import state

    state.theme_mode = "system"
    assert theme_button(lambda: None).icon == ft.Icons.BRIGHTNESS_AUTO_ROUNDED
    state.theme_mode = "light"
    assert theme_button(lambda: None).icon == ft.Icons.LIGHT_MODE_ROUNDED
    state.theme_mode = "dark"
    assert theme_button(lambda: None).icon == ft.Icons.DARK_MODE_ROUNDED


def test_state_changes_rerender_without_frozen_errors():
    import screens
    from core.state import state

    state.containers = [
        {"name": "debian", "image": "debian:bookworm", "arch": "aarch64", "size_bytes": 4096}
    ]
    state.installing = "debian"
    state.install_stage = "downloading layers"
    state.search_results = [
        {"name": "ubuntu:24.04", "stars": 10, "pulls": 20, "official": True, "description": "d"}
    ]
    state.search_status = "1 result(s)"
    state.hints_dismissed = True
    assert _render(screens.DistroView) is not None

    state.theme_mode = "light"
    state.storage_bytes = 123456
    state.cached_count = 2
    assert _render(screens.SettingsView) is not None


def test_licenses_view_has_compliance_content():
    import screens

    view = screens.licenses_view()
    assert isinstance(view, ft.Column)
    texts = [t.value for t in _walk(view) if isinstance(t, ft.Text) and isinstance(t.value, str)]
    blob = "\n".join(texts)
    assert "Source code offer" in blob
    assert "GPL-2.0" in blob and "GPL-3.0" in blob
    assert "Software in the Public Interest" in blob  # Debian attribution
    assert "Canonical" in blob  # Ubuntu attribution
    assert "termux/proot" in blob  # upstream source pointers


def test_theme_modes_resolve():
    from core import theme
    from core.state import state

    state.theme_mode = "dark"
    assert theme.is_light_theme() is False
    state.theme_mode = "light"
    assert theme.is_light_theme() is True
    state.theme_mode = "system"
    # No page in this context: terminal-native default (dark).
    assert theme.is_light_theme() is False
    assert theme.bg() == theme.AppColors.DARK_BG

    light, dark = theme.build_theme()
    assert isinstance(light, ft.Theme) and isinstance(dark, ft.Theme)


def test_screens_contain_no_imperative_mutation():
    """The frozen-controls bug class, guarded at source level (house grep style)."""
    for path in sorted((ROOT / "src" / "screens").rglob("*.py")):
        src = path.read_text(encoding="utf-8")
    for pattern in (
        r"\.value\s*=",
        r"page\.update\(",
        r"\.controls\.(append|clear|extend)\(",
        r"\.controls\s*=\s*\[",
    ):
        assert not re.search(pattern, src), f"imperative mutation in screens.py: {pattern}"


def _walk(control):
    """Every control in the tree — Container content counts as a child."""
    yield control
    content = getattr(control, "content", None)
    if (content is not None and hasattr(content, "controls")) or isinstance(content, ft.Control):
        yield from _walk(content)
    for child in getattr(control, "controls", []) or []:
        yield from _walk(child)


def test_license_texts_are_present_and_shipped():
    """The GPL texts must ship with the app and match the repo's notices file."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app_dir = root / "src" / "LICENSES"
    repo_dir = root / "LICENSES"
    assert app_dir.is_dir(), "src/LICENSES is missing — the texts would not ship"
    names = {p.name for p in app_dir.glob("*.txt")}
    assert {
        "GPL-2.0.txt",
        "GPL-3.0.txt",
        "Apache-2.0.txt",
        "MIT.txt",
        "BSD-3-Clause.txt",
        "MPL-2.0.txt",
        "PSF-2.0.txt",
    } <= names
    for path in app_dir.glob("*.txt"):
        assert path.stat().st_size > 500, f"{path.name} looks truncated"
        twin = repo_dir / path.name
        assert twin.is_file(), f"{path.name} missing from the repo notices file"
        assert twin.read_bytes() == path.read_bytes(), f"{path.name} drifted"


def test_licenses_view_carries_real_text():
    """The expansion tiles must hold the actual license text, not a placeholder."""
    import screens

    view = screens.licenses_view()
    bodies = [t.value for t in _walk(view) if isinstance(t, ft.Text) and isinstance(t.value, str)]
    assert "(text missing)" not in "\n".join(bodies)
    assert any("GNU GENERAL PUBLIC LICENSE" in body for body in bodies)
