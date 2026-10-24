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
    from core import tokens
    from core.state import state

    svg = app_icon_svg()
    assert b"<svg" in svg[:256]  # the real brand asset, not a placeholder

    state.theme_mode = "dark"
    dark = build_brand_hero("Linux on Android — no root, no Termux")
    assert isinstance(dark, ft.Container)
    images = [c for c in _walk(dark) if isinstance(c, ft.Image)]
    assert images, "brand hero must contain an Image"
    icon = images[0]
    assert icon.color == ft.Colors.WHITE
    assert icon.width == tokens.HERO_ICON_SIZE  # CollabShell's ICON_XXXL (80px)

    state.theme_mode = "light"
    light = build_brand_hero()
    images_light = [c for c in _walk(light) if isinstance(c, ft.Image)]
    assert images_light[0].color is None  # artwork keeps its own colors on light


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


# ── shell subscription + dialog wiring regressions (swarm P0s) ──────────────


def test_app_shell_subscribes_to_the_observable_state():
    """The exact regression of commit 4ad4593: AppShell read state without
    use_state(state), so onboarding dead-ended and shell open/close never
    re-rendered. Observable reactivity is subscription-based, not read-based
    (flet/components/observable.py) — the hook must stay."""
    root = Path(__file__).resolve().parents[1]
    source = (root / "src" / "app_shell.py").read_text(encoding="utf-8")
    assert "ft.use_state(state)" in source, "AppShell must subscribe: st, _ = ft.use_state(state)"
    # And it must actually read through the subscription handle.
    assert "st.onboarding_done" in source
    assert "st.active_session" in source


def test_update_dialog_recheck_button_schedules_the_coroutine():
    """The Check-for-Updates button must run_task the coroutine — a sync
    lambda returning it is silently discarded by Flet (the old dead button)."""
    import inspect
    import types

    from components import update_dialog

    scheduled: list[tuple[object, tuple]] = []

    class _Page:
        web = False
        platform = types.SimpleNamespace(is_mobile=lambda: False)

        def show_dialog(self, dialog):
            self.dialog = dialog

        def pop_dialog(self):
            return None

        def run_task(self, handler, *args):
            scheduled.append((handler, args))

    page = _Page()
    update_dialog.show_update_dialog(page, None)
    actions = list(getattr(page.dialog, "actions", []))
    recheck = next(b for b in actions if getattr(b, "content", "") == "Check for Updates")
    recheck.on_click(None)
    assert scheduled, "the button must page.run_task(...) — not call the coroutine"
    handler, _args = scheduled[0]
    assert inspect.iscoroutinefunction(handler)


# ── CollabShell design-parity guards (Milestone R2) ──────────────────────────


def test_shell_renders_header_outside_scroll_and_in_safe_area():
    """Header must be fixed at shell level inside SafeArea, never inside view scroll columns."""
    source = (ROOT / "src" / "app_shell.py").read_text(encoding="utf-8")
    assert "ft.SafeArea(" in source
    assert "AppHeader(" in source
    # Must derive title from active tab
    assert "_TABS[active_tab]" in source


def test_views_contain_no_app_header():
    """In-view AppHeader calls caused header inversion and scrolling away; must remain removed."""
    source = (ROOT / "src" / "screens" / "views.py").read_text(encoding="utf-8")
    assert "AppHeader(" not in source


def test_navigation_bar_hidden_during_session():
    """NavigationBar must step aside while a session is open or in full screen."""
    source = (ROOT / "src" / "app_shell.py").read_text(encoding="utf-8")
    assert "if entry is None and not fullscreen:" in source


def test_quick_commands_end_with_newline():
    """Quick commands must append newline so tapping them executes immediately."""
    from screens import terminal_view

    for label, cmd in terminal_view._QUICK_COMMANDS:
        if label.strip() in ("ls", "top", "clear", "exit"):
            assert cmd.endswith("\n"), f"{label!r} command must end with newline"


def test_tokens_enforce_legibility_floor():
    """No user-facing typography token below 11pt (house legibility floor)."""
    from core import tokens

    for name in dir(tokens):
        if name.startswith("FONT_"):
            val = getattr(tokens, name)
            if isinstance(val, (int, float)):
                assert val >= 11, f"token {name}={val} is below the 11pt legibility floor"


def test_theme_provides_readable_status_colors_and_outfit_family():
    from core import theme

    assert theme.FONT_FAMILY == "Outfit"
    assert "Outfit" in theme.FONT_FILES
    assert theme.ok().startswith("#")
    assert theme.warn().startswith("#")
    assert theme.accent().startswith("#")
