"""Session manager — one live guest shell per container, kept across screens.

CollabShell's TerminalEntry pattern: the session process and its scrollback
live on an observable entry, so rebuilding the terminal widget (tab switch,
theme flip) never kills the shell — the buffer replays on mount.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from typing import Any

import flet as ft

from services import session_service

# No artificial concurrency cap: upstream proot-distro has none — the OS
# (fd/memory limits) is the only bound, and we wrap it one-to-one.
# Scrollback is a replay-buffer memory bound only: a BYTE budget (2 MiB per
# shell) instead of a chunk count — chunk counts depend on how the PTY
# happened to split reads, so the old 10 000-chunk deque could hold ~40 MB.
SCROLLBACK_BYTES = 2 * 1024 * 1024
# PTY bytes are coalesced into one widget write per flush: fewer bridge
# messages and fewer (larger) scrollback chunks. 16 ms ≈ one frame.
FLUSH_INTERVAL = 0.016
FLUSH_BYTES = 64 * 1024
REPLAY_FRAME = 256 * 1024


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
        self.scrollback: deque[bytes] = deque()
        self._scrollback_bytes = 0
        self.ready = False
        self.error = ""
        self.session: Any = None
        self.mt: Any = None
        self.wired = False
        # The page loop that currently owns this shell's terminal widget —
        # updated on every re-wire (the app can be reopened in the same
        # process while the FGS keeps it alive).
        self.loop: Any = None
        # Coalescing buffer: reader-thread writers append here; one flush sends
        # everything as a single send_bytes (and one scrollback chunk).
        self._pending = bytearray()
        self._pending_since = 0.0
        self._pending_lock = threading.Lock()
        self._closed = False
        self._replaying = False
        # Trailing flush: a burst that ends mid-window must still reach the
        # widget, so a light ticker flushes anything older than FLUSH_INTERVAL.
        threading.Thread(target=self._flush_ticker, daemon=True).start()

    # ── output path ─────────────────────────────────────────────────────

    def feed(self, data: bytes) -> None:
        """Append PTY bytes (ANY thread). Flushes on size, else the ticker."""
        with self._pending_lock:
            if not self._pending:
                self._pending_since = time.monotonic()
            self._pending += data
            ready = len(self._pending) >= FLUSH_BYTES
        if ready:
            self.flush()

    def flush(self, send: bool = True) -> None:
        """Send everything buffered as ONE widget write + ONE scrollback chunk.

        `send=False` only moves the buffer into the scrollback (used by replay:
        the widget is about to be handed the whole buffer anyway)."""
        with self._pending_lock:
            if not self._pending or self._closed:
                return
            data = bytes(self._pending)
            self._pending.clear()
        self._store_scrollback(data)
        if not send or self._replaying:
            return
        mt = self.mt
        if mt is None:
            return
        # Use the CURRENT page loop (the app may have been reopened in this
        # process while the foreground service kept it alive).
        target = self.loop
        if target is None:
            return
        try:
            target.call_soon_threadsafe(mt.send_bytes, data)
        except RuntimeError:
            pass  # page loop gone (backgrounded/destroyed) — scrollback still fed

    def _flush_ticker(self) -> None:
        while not self._closed:
            time.sleep(FLUSH_INTERVAL * 3)
            with self._pending_lock:
                due = bool(self._pending) and (
                    time.monotonic() - self._pending_since >= FLUSH_INTERVAL
                )
            if due:
                self.flush()

    def _store_scrollback(self, data: bytes) -> None:
        self.scrollback.append(data)
        self._scrollback_bytes += len(data)
        while self._scrollback_bytes > SCROLLBACK_BYTES and len(self.scrollback) > 1:
            self._scrollback_bytes -= len(self.scrollback.popleft())

    def replay(self, send_bytes) -> None:
        """Replay the scrollback in ≤256 KiB frames — one send per chunk made a
        mount cost thousands of bridge messages (the tab-switch freeze)."""
        # Hold live sends while replaying: a reader-thread flush queued during
        # the mount would otherwise paint the same bytes twice.
        self._replaying = True
        try:
            self.flush(send=False)
            chunks = list(self.scrollback)
        finally:
            self._replaying = False
        batch = bytearray()
        for chunk in chunks:
            batch += chunk
            if len(batch) >= REPLAY_FRAME:
                send_bytes(bytes(batch))
                batch.clear()
        if batch:
            send_bytes(bytes(batch))

    def close(self) -> None:
        self.flush()  # never drop the final chunk
        self._closed = True


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

    async def open(
        self,
        container: str,
        options: dict | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> SessionEntry:
        """Open a NEW shell on the container (multiple per container allowed).

        `options` carries the upstream login options from the "Shell with
        options…" dialog (user/work_dir/env/bind/shared_*); None = the plain
        `pd login <c>` interactive shell, exactly as before. `extra_env` is the
        transient overlay (e.g. a running display's DISPLAY/XAUTHORITY): applied
        with setdefault so an explicit `--env DISPLAY=…` from the dialog wins."""
        loop = asyncio.get_running_loop()
        with self._lock:
            key = self._new_key(container)
            entry = SessionEntry(key, container)
            entry.loop = loop  # default owner until a terminal widget re-wires it
            self.entries[key] = entry

            if options:
                env, argv = session_service.session_argv_with_options(container, options)
            else:
                env, argv = session_service.session_argv(container)
            for env_key, env_value in (extra_env or {}).items():
                env.setdefault(env_key, env_value)

            def _on_bytes(data: bytes) -> None:
                # Coalesced: SessionEntry batches PTY bytes into one widget
                # write per flush (see FLUSH_INTERVAL).
                entry.feed(data)

            def _record_exit(returncode: int | None) -> None:
                # The guest shell exited (e.g. the user typed `exit`): close the
                # tab cleanly — drop the entry, and switch to the next open
                # shell (or leave the terminal screen if none). Other tabs stay
                # alive and reactive. Never mutate observables from the reader
                # thread: everything here runs on the loop via _on_exit.
                with self._lock:
                    self.entries.pop(entry.key, None)
                    entry.close()
                    session.stop()
                    remaining = [
                        k for k, e in self.entries.items() if e.ready or e.session is not None
                    ]
                try:
                    entry.ready = False
                    entry.session = None
                    entry.error = f"shell exited ({returncode})"
                    from core.state import state

                    if state.active_session == entry.key:
                        # Next open shell keeps the user in the terminal; none → exit.
                        state.active_session = remaining[0] if remaining else None
                except RuntimeError:
                    # No page is associated (app in background) — the observable
                    # values were still set; only the notify path needs a page.
                    pass

            def _on_exit(returncode: int | None) -> None:
                # Same loop discipline as _on_bytes: prefer the CURRENT page
                # loop (the app may have been reopened in this process while
                # the foreground service kept it alive) and swallow a dead
                # loop — the byte path already did; the exit path missed it
                # and stranded the tab + FGS on reopen (device audit
                # 2026-11-13).
                target = entry.loop or loop
                try:
                    target.call_soon_threadsafe(_record_exit, returncode)
                except RuntimeError:
                    pass

            session = session_service.ProotSession(argv, env, _on_bytes, _on_exit)
            try:
                session.start()
            except Exception:
                # Never leave a ghost entry (no process, ready=False): it would
                # show as a tab chip and count as a live shell in the FGS.
                self.entries.pop(key, None)
                raise
            entry.session = session
            entry.ready = True
            entry.error = ""
            return entry

    def close(self, key: str) -> None:
        with self._lock:
            entry = self.entries.pop(key, None)
            if entry is None:
                return
            entry.flush()  # last chunk reaches the scrollback
            entry.close()  # stops the flush ticker (it holds the entry alive)
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


_SHARED: SessionManager | None = None


def shared_manager() -> SessionManager:
    """The process-wide session registry.

    The foreground service keeps the PROCESS alive when the activity is
    destroyed, so a module-level singleton is what makes "tap the
    notification → back to my shell" work: the ProotSession processes and
    their scrollback survive, and a reopened app re-attaches to them.
    """
    global _SHARED
    if _SHARED is None:
        _SHARED = SessionManager()
    return _SHARED
