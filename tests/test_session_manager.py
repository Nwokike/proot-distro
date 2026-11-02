"""Session manager state and event-loop delivery tests."""

import pytest
from session_support import GOLDEN_CMD

from services import session_service


def test_session_manager_keys_entries_by_unique_session_id(monkeypatch):
    """Multiple shells may run on one container — keyed by session id."""
    from services import session_manager as sm

    manager = sm.SessionManager()
    with manager._lock:
        assert manager._new_key("debian") == "debian"
        manager.entries["debian"] = sm.SessionEntry("debian", "debian")
        assert manager._new_key("debian") == "debian#2"
        manager.entries["debian#2"] = sm.SessionEntry("debian#2", "debian")
        assert manager._new_key("debian") == "debian#3"
        assert manager._new_key("ubuntu") == "ubuntu"


async def test_session_manager_caps_concurrent_sessions():
    from services import session_manager as sm

    manager = sm.SessionManager()
    with manager._lock:
        for index in range(sm.MAX_CONCURRENT_SESSIONS):
            key = f"c{index}"
            manager.entries[key] = sm.SessionEntry(key, key)
    with pytest.raises(RuntimeError):
        await manager.open("one-too-many")


def test_session_entry_replay_sends_the_buffer_in_order():
    from services import session_manager as sm

    entry = sm.SessionEntry("debian", "debian")
    entry.feed(b"a")
    entry.feed(b"b")
    sent: list[bytes] = []
    entry.replay(sent.append)
    assert sent == [b"a", b"b"]


class _StubTerminal:
    """Records send_bytes calls — an explicit stub, not a MagicMock (a mock
    accepts any call, so it cannot prove the wiring exists)."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)


class _FakeSession:
    def __init__(self, argv, env, on_bytes, on_exit) -> None:
        self.argv, self.env = argv, env
        self._on_bytes, self._on_exit = on_bytes, on_exit
        self.alive = True

    def start(self) -> None:
        self._on_bytes(b"prompt $ ")

    def stop(self) -> None:
        self.alive = False
        self._on_exit(0)


async def test_live_output_is_forwarded_to_the_terminal(monkeypatch):
    import asyncio

    """PTY bytes must reach the mounted terminal AND the scrollback deque —
    without the live send_bytes call the screen renders nothing after mount."""
    from services import session_manager as sm

    monkeypatch.setattr(session_service, "ProotSession", _FakeSession)
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )

    manager = sm.SessionManager()
    entry = await manager.open("debian")
    stub = _StubTerminal()
    entry.mt = stub

    # The pre-mount byte (emitted by start() before entry.mt existed)
    # reaches the screen only via replay; post-mount bytes are forwarded
    # live — that distinction is exactly what this test pins.
    entry.replay(stub.send_bytes)
    assert stub.sent == [b"prompt $ "]

    # Post-mount PTY output (the reader thread's callback): live delivery.
    entry.session._on_bytes(b"hello\n")
    assert stub.sent == [b"prompt $ "]
    await asyncio.sleep(0)
    assert stub.sent == [b"prompt $ ", b"hello\n"]
    assert list(entry.scrollback) == [b"prompt $ ", b"hello\n"]


async def test_session_exit_updates_observable_entry_on_event_loop(monkeypatch):
    import asyncio
    import threading

    from services import session_manager as sm

    monkeypatch.setattr(session_service, "ProotSession", _FakeSession)
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )

    manager = sm.SessionManager()
    entry = await manager.open("debian")
    worker = threading.Thread(target=entry.session._on_exit, args=(7,))
    worker.start()
    worker.join()

    assert entry.ready is True
    await asyncio.sleep(0)
    assert entry.ready is False
    assert entry.session is None
    assert entry.error == "shell exited (7)"


async def test_live_output_without_a_terminal_only_feeds_scrollback(monkeypatch):
    """Before mount (mt is None) bytes must not crash — replay covers them."""
    from services import session_manager as sm

    monkeypatch.setattr(session_service, "ProotSession", _FakeSession)
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )

    manager = sm.SessionManager()
    entry = await manager.open("debian")
    entry.session._on_bytes(b"early\n")  # mt is None here
    assert list(entry.scrollback) == [b"prompt $ ", b"early\n"]


async def test_session_manager_opens_second_shell_on_same_container(monkeypatch):
    """Multi-shell: open() on a container that already has a live shell starts a
    SECOND shell (tmux-style) under a new session id — the first stays alive."""
    from services import session_manager as sm

    monkeypatch.setattr(session_service, "ProotSession", _FakeSession)
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )

    manager = sm.SessionManager()
    first = await manager.open("debian")
    second = await manager.open("debian")
    assert second is not first
    assert first.key == "debian" and second.key == "debian#2"
    assert first.session.alive is True and second.session.alive is True
    assert first.ready is True and second.ready is True
    assert set(manager.entries) == {"debian", "debian#2"}
