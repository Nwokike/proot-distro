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
    """One shell: the process, its scrollback, and its status.

    `key` is the unique session id (`debian`, `debian#2`, …) — several shells
    may run on the same container (tmux-style), so entries are keyed by id,
    not by container name.
    """

    def __init__(self, key: str, container: str):
        self.key = key
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

    def _new_key(self, container: str) -> str:
        """A free session id for this container (debian, debian#2, …)."""
        key = container
        n = 2
        while key in self.entries:
            key = f"{container}#{n}"
            n += 1
        return key

    async def open(self, container: str) -> SessionEntry:
        """Open a NEW shell on the container (multiple per container allowed)."""
        loop = asyncio.get_running_loop()
        with self._lock:
            if len(self.entries) >= MAX_CONCURRENT_SESSIONS:
                raise RuntimeError(
                    f"{MAX_CONCURRENT_SESSIONS} shells are already open — close one first"
                )
            key = self._new_key(container)
            entry = SessionEntry(key, container)
            self.entries[key] = entry

            env, argv = session_service.session_argv(container)

            def _on_bytes(data: bytes) -> None:
                entry.feed(data)
                mt = entry.mt
                if mt is not None:
                    loop.call_soon_threadsafe(mt.send_bytes, data)

            def _record_exit(returncode: int | None) -> None:
                # The guest shell exited (e.g. the user typed `exit`): close the
                # tab cleanly — drop the entry, and switch to the next open
                # shell (or leave the terminal screen if none). Other tabs stay
                # alive and reactive. Never mutate observables from the reader
                # thread: everything here runs on the loop via _on_exit.
                with self._lock:
                    self.entries.pop(entry.key, None)
                    session.stop()
                    remaining = [
                        k for k, e in self.entries.items() if e.ready or e.session is not None
                    ]
                entry.ready = False
                entry.session = None
                entry.error = f"shell exited ({returncode})"
                from core.state import state

                if state.active_session == entry.key:
                    # Next open shell keeps the user in the terminal; none → exit.
                    state.active_session = remaining[0] if remaining else None

            def _on_exit(returncode: int | None) -> None:
                loop.call_soon_threadsafe(_record_exit, returncode)

            session = session_service.ProotSession(argv, env, _on_bytes, _on_exit)
            session.start()
            entry.session = session
            entry.ready = True
            entry.error = ""
            return entry

    def close(self, key: str) -> None:
        with self._lock:
            entry = self.entries.pop(key, None)
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
            keys = list(self.entries.keys())
        for key in keys:
            self.close(key)

    def set_title(self, key: str, title: str) -> None:
        with self._lock:
            entry = self.entries.get(key)
            if entry is not None and title:
                entry.title = title
