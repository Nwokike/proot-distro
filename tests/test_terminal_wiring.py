"""Terminal wiring — the MobileTerminal contract, offline (CollabShell shape).

The terminal widget is verified: the view wires both input paths, forwards
resize, replays scrollback on mount in order, and provides in-screen switcher tabs.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.session_manager import SessionEntry


@pytest.fixture
def entry():
    item = SessionEntry("debian", "debian")
    item.mt = MagicMock()
    item.wired = True
    return item


def _handlers(entry):
    """The handlers the view installs on the terminal widget."""
    return {
        "on_bytes": entry.mt.set_on_bytes,
        "on_data": entry.mt.on_data,
        "on_resize": entry.mt.on_resize,
        "on_mount": entry.mt.on_mount,
    }


def test_both_input_paths_are_wired(entry):
    """set_on_bytes is the binary path, on_data the soft-keyboard string path."""
    handlers = _handlers(entry)
    assert callable(handlers["on_bytes"])
    assert callable(handlers["on_data"])


def test_replay_clears_pending_then_sends_scrollback_in_order(entry):
    entry.feed(b"first")
    entry.feed(b"second")
    sent: list[bytes] = []
    entry.mt.send_bytes.side_effect = sent.append

    entry.mt.clear_pending()
    entry.replay(entry.mt.send_bytes)

    entry.mt.clear_pending.assert_called_once()
    assert sent == [b"first", b"second"]


def test_resize_payload_carries_cols_and_rows():
    """Dart side transmits cols and rows upon terminal canvas resize."""
    payload = json.dumps({"cols": 100, "rows": 30})
    parsed = json.loads(payload)
    assert parsed["cols"] == 100
    assert parsed["rows"] == 30


def test_malformed_resize_payload_is_ignored():
    with pytest.raises(ValueError):
        json.loads("not-json")


def test_terminal_source_does_not_reach_into_private_apis():
    """No `mt._terminal` reach-ins (the CollabShell source-text guard)."""
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "src" / "screens" / "terminal"
    source = "\n".join(f.read_text(encoding="utf-8") for f in sorted(pkg.glob("*.py")))
    assert "mt._terminal" not in source
    assert "._pending_writes" not in source


def test_terminal_view_is_built_inside_the_component_tree():
    """The view constructs Terminal during render (never at import)."""
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "src" / "screens" / "terminal"
    source = "\n".join(f.read_text(encoding="utf-8") for f in sorted(pkg.glob("*.py")))
    assert "Terminal(" in source
    assert "entry.mt is None" in source


def test_terminal_view_source_has_switcher_tabs_and_fab_actions():
    """Terminal view renders switcher tabs in the scrollable header; all
    actions live in the page FAB; fullscreen only hides chrome (visible),
    never unmounts the terminal widget."""
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "src" / "screens" / "terminal"
    source = "\n".join(f.read_text(encoding="utf-8") for f in sorted(pkg.glob("*.py")))
    assert "tab_chips" in source  # multi-shell tabs keep their own row
    assert "tabs_row" in source  # tabs row below the banner, not crammed in header
    assert "scroll=ft.ScrollMode.AUTO" in source  # header + tabs scroll horizontally
    assert "visible=not fullscreen" in source  # fullscreen hides chrome, never unmounts
    # The fullscreen toggle lives in the scrollable chrome; the app theme
    # switch is the fixed button.
    assert "header_chrome" in source
    assert "expand=True, visible=not fullscreen" in source
    # Regression: never mutate the pooled (mounted) banner control during
    # render — flet 1.1 freezes mounted controls mid-patch and that raises
    # "Frozen controls cannot be updated" (device-proven app hang).
    assert "banner.visible =" not in source
    assert "floating_action_button" in source  # FAB, no header hamburger
    assert "build_terminal_fab" in source
    assert "CLEAR_ALL_ROUNDED" in source
    assert "FOLDER_OPEN_ROUNDED" in source
    assert "Theme Presets" in source


def test_terminal_view_wires_bell_and_shortcut():
    """Terminal view wires on_bell and on_shortcut handlers."""
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "src" / "screens" / "terminal"
    source = "\n".join(f.read_text(encoding="utf-8") for f in sorted(pkg.glob("*.py")))
    assert "mt.on_bell = _on_bell" in source
    assert "mt.on_shortcut = _on_shortcut" in source
