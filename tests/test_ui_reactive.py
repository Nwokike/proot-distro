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
    src = (ROOT / "src" / "screens.py").read_text(encoding="utf-8")
    for pattern in (
        r"\.value\s*=",
        r"page\.update\(",
        r"\.controls\.(append|clear|extend)\(",
        r"\.controls\s*=\s*\[",
    ):
        assert not re.search(pattern, src), f"imperative mutation in screens.py: {pattern}"


def _walk(control):
    yield control
    for child in getattr(control, "controls", []) or []:
        yield from _walk(child)
