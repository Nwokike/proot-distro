"""Session manager — one live guest shell per container, kept across screens.

CollabShell's TerminalEntry pattern: the session process and its scrollback
live on an observable entry, so rebuilding the terminal widget (tab switch,
theme flip) never kills the shell — the buffer replays on mount.
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Any

import flet as ft

from services import session_service

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SESSIONS = 4
SCROLLBACK_CHUNKS = 2000


@ft.observable
class SessionEntry:
    """One container's shell: the process, its scrollback, and its status."""

    def __init__(self, container: str):
        self.container = container
        self.title = container
        self.scrollback: deque[bytes] = deque(maxlen=SCROLLBACK_CHUNKS)
        self.ready = False
        self.error = ""
        self.session: Any = None
        self.mt: Any = None
        self.wired = False

    def feed(self, data: bytes) -> None:
        self.scrollback.append(data)

    def replay(self, send_bytes) -> None:
        for chunk in list(self.scrollback):
            send_bytes(chunk)


class SessionManager:
    """Opens, closes and switches guest shells; caps concurrency."""

    def __init__(self):
        self.entries: dict[str, SessionEntry] = {}

    def entry(self, container: str) -> SessionEntry:
        entry = self.entries.get(container)
        if entry is None:
            if len(self.entries) >= MAX_CONCURRENT_SESSIONS:
                raise RuntimeError(
                    f"{MAX_CONCURRENT_SESSIONS} shells are already open — close one first"
                )
            entry = SessionEntry(container)
            self.entries[container] = entry
        return entry

    def open(self, container: str) -> SessionEntry:
        entry = self.entry(container)
        if entry.session is not None and entry.session.alive:
            return entry
        env, argv = session_service.session_argv(container)

        def _on_bytes(data: bytes) -> None:
            # Record for replay-on-mount AND forward live — without the
            # send_bytes call the terminal renders nothing after mount (the
            # PTY bytes only ever reached the scrollback deque).
            entry.feed(data)
            mt = entry.mt
            if mt is not None:
                mt.send_bytes(data)

        def _on_exit(returncode: int | None) -> None:
            entry.ready = False
            entry.session = None
            entry.error = f"shell exited ({returncode})"

        session = session_service.ProotSession(argv, env, _on_bytes, _on_exit)
        session.start()
        entry.session = session
        entry.ready = True
        entry.error = ""
        return entry

    def close(self, container: str) -> None:
        entry = self.entries.pop(container, None)
        if entry is None:
            return
        if entry.session is not None:
            entry.session.stop()

    def close_all(self) -> None:
        for container in list(self.entries):
            self.close(container)

    def set_title(self, container: str, title: str) -> None:
        entry = self.entries.get(container)
        if entry is not None and title:
            entry.title = title
