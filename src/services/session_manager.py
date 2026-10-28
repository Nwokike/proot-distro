"""Session manager — one live guest shell per container, kept across screens.

CollabShell's TerminalEntry pattern: the session process and its scrollback
live on an observable entry, so rebuilding the terminal widget (tab switch,
theme flip) never kills the shell — the buffer replays on mount.
"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from typing import Any

import flet as ft

from services import session_service

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
        self._lock = threading.RLock()

    def entry(self, container: str) -> SessionEntry:
        with self._lock:
            entry = self.entries.get(container)
            if entry is None:
                if len(self.entries) >= MAX_CONCURRENT_SESSIONS:
                    raise RuntimeError(
                        f"{MAX_CONCURRENT_SESSIONS} shells are already open — close one first"
                    )
                entry = SessionEntry(container)
                self.entries[container] = entry
            return entry

    async def open(self, container: str) -> SessionEntry:
        loop = asyncio.get_running_loop()
        with self._lock:
            entry = self.entry(container)
            if entry.session is not None:
                if entry.session.alive:
                    return entry
                # Previous session died — stop cleanly before replacing.
                entry.session.stop()
                entry.session = None
                entry.ready = False

            env, argv = session_service.session_argv(container)

            def _on_bytes(data: bytes) -> None:
                entry.feed(data)
                mt = entry.mt
                if mt is not None:
                    loop.call_soon_threadsafe(mt.send_bytes, data)

            def _record_exit(returncode: int | None) -> None:
                entry.ready = False
                entry.session = None
                entry.error = f"shell exited ({returncode})"

            def _on_exit(returncode: int | None) -> None:
                loop.call_soon_threadsafe(_record_exit, returncode)

            session = session_service.ProotSession(argv, env, _on_bytes, _on_exit)
            session.start()
            entry.session = session
            entry.ready = True
            entry.error = ""
            return entry

    def close(self, container: str) -> None:
        with self._lock:
            entry = self.entries.pop(container, None)
            if entry is None:
                return
            entry.ready = False
            session, entry.session = entry.session, None
            if session is not None:
                session.stop()
            entry.wired = False
            entry.mt = None

    def close_all(self) -> None:
        with self._lock:
            containers = list(self.entries.keys())
        for container in containers:
            self.close(container)

    def set_title(self, container: str, title: str) -> None:
        with self._lock:
            entry = self.entries.get(container)
            if entry is not None and title:
                entry.title = title
