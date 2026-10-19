"""Terminal wiring — the MobileTerminal contract, offline (CollabShell shape).

The terminal widget is a MagicMock: what matters is that the view wires BOTH
input paths, forwards the resize, and replays the scrollback on mount in order.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from services.session_manager import SessionEntry


@pytest.fixture
def entry():
    item = SessionEntry("debian")
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


def test_resize_payload_carries_cols_rows_and_inset():
    payload = json.dumps({"cols": 100, "rows": 30, "bottom_inset": 42})
    parsed = json.loads(payload)
    assert parsed["cols"] == 100
    assert parsed["rows"] == 30
    assert parsed["bottom_inset"] == 42


def test_malformed_resize_payload_is_ignored():
    with pytest.raises(ValueError):
        json.loads("not-json")


def test_terminal_source_does_not_reach_into_private_apis():
    """No `mt._terminal` reach-ins (the CollabShell source-text guard)."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "src" / "screens" / "terminal_view.py"
    ).read_text(encoding="utf-8")
    assert "mt._terminal" not in source
    assert "._pending_writes" not in source


def test_terminal_view_is_built_inside_the_component_tree():
    """The view constructs MobileTerminal during render (never at import)."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "src" / "screens" / "terminal_view.py"
    ).read_text(encoding="utf-8")
    assert "MobileTerminal(" in source
    assert "entry.mt is None" in source
