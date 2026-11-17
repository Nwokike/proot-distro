"""Structure guards — the M6 rules, enforced instead of remembered.

- no source file over 500 lines (split into a package instead),
- no raw `ft.Colors.*` outside core/theme.py,
- no stale architecture names (Xpra/Xvfb/TermuxDesk) in src/,
- every split package keeps a facade module re-exporting its entry points.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

MAX_LINES = 500
# Any raw ft.Colors.<CONSTANT> in app code (function calls like
# ft.Colors.with_opacity are token-driven and allowed).
RAW_COLOR_RE = re.compile(r"ft\.Colors\.[A-Z][A-Z_]*\b")


def _sources() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_source_file_exceeds_500_lines():
    over = []
    for path in _sources():
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > MAX_LINES:
            over.append(f"{path.relative_to(ROOT)}: {count}")
    assert not over, "split these files into packages:\n" + "\n".join(over)


def test_raw_colors_live_in_the_theme_only():
    offenders = []
    for path in _sources():
        if path.name == "theme.py" and path.parent.name == "core":
            continue
        text = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{path.relative_to(ROOT)}: {match}" for match in RAW_COLOR_RE.findall(text)
        )
    assert not offenders, "use theme.* aliases:\n" + "\n".join(offenders)


def test_no_stale_architecture_names():
    stale = ("Xpra", "Xvfb", "TermuxDesk", "LocalhostRunTunnel", "tunnel.py")
    hits = []
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        hits.extend(f"{path.relative_to(ROOT)}: {name}" for name in stale if name in text)
    assert not hits, "\n".join(hits)


def test_split_packages_keep_public_facades():
    """The modules that were split must still re-export their entry points."""
    checks = {
        "screens/display_launcher.py": ("show_display_sheet",),
        "screens/container_actions.py": ("ask_shell_options", "container_menu_items"),
        "controller_actions/display_actions.py": ("DisplayActions",),
        "controller_actions/session_actions.py": ("SessionActions",),
        "services/desk_service/manager.py": ("DeskManager", "shared_manager"),
        "services/desk_service/xvnc_runtime.py": ("xvnc_command", "write_pulse_config"),
    }
    for rel, names in checks.items():
        text = (SRC / rel).read_text(encoding="utf-8")
        for name in names:
            assert name in text, f"{rel} no longer exports {name}"


def test_dead_scaffolding_stays_deleted():
    """The dead install-log trio and the write-only state fields must not
    come back (the trio referenced a function that never existed)."""
    src = (SRC / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    pkg = SRC / "screens" / "display_sheets"
    text = src + "\n".join(p.read_text(encoding="utf-8") for p in pkg.glob("*.py"))
    for gone in ("_install_log_box", "repaint_install_log", "_register_install_box"):
        assert gone not in text, gone
    state_src = (SRC / "core" / "state.py").read_text(encoding="utf-8")
    for gone in ("apt_note_dismissed", "finished_ok", "display_logs", "busy_locks"):
        assert gone not in state_src, gone


def test_shared_helpers_have_real_consumers():
    """core.layout and the banner/page helpers must be used by the screens."""
    users = [
        SRC / "screens" / "settings" / "__init__.py",
        SRC / "screens" / "build_view.py",
        SRC / "screens" / "distro" / "__init__.py",
        SRC / "screens" / "display_launcher.py",
    ]
    text = "\n".join(p.read_text(encoding="utf-8") for p in users)
    assert "layout.is_narrow" in text or "layout.is_mobile_layout" in text
    assert "pooled_banner_ad(" in (SRC / "screens" / "files" / "__init__.py").read_text(
        encoding="utf-8"
    )
    # page_tail keeps a real consumer (the terminal session picker).
    assert "page_tail(" in (SRC / "screens" / "session_selector_view.py").read_text(
        encoding="utf-8"
    )
    assert "styles.pill_button_style()" in (SRC / "screens" / "build_view.py").read_text(
        encoding="utf-8"
    )


def test_every_declared_dependency_is_in_the_third_party_notice():
    """The generated notice must name every dependency the app declares."""
    import re
    import tomllib

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    doc = (ROOT / "THIRD-PARTY-SOURCES.md").read_text(encoding="utf-8")
    declared = list(pyproject["project"]["dependencies"])
    declared += list(pyproject["tool"]["flet"]["android"]["dependencies"])
    for dep in declared:
        name = re.split(r"[<>=!~ ]", dep)[0].strip()
        assert name in doc, f"{name} is missing from THIRD-PARTY-SOURCES.md"
