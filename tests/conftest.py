"""Shared fixtures — a minimal page stand-in for controller-branch tests."""

from __future__ import annotations

from typing import Any

import pytest


class FakePage:
    """Enough of ft.Page for the controller branch — no client needed."""

    def __init__(self) -> None:
        self.services: list[Any] = []
        self.dialogs: list[Any] = []
        self.tasks: list[tuple[Any, tuple, dict]] = []
        self._next_loop = None
        self._render_calls: list[Any] = []
        self.on_disconnect = None
        self.on_close = None

    @property
    def loop(self):
        if self._next_loop is None:
            import asyncio

            try:
                self._next_loop = asyncio.get_running_loop()
            except RuntimeError:
                self._next_loop = asyncio.new_event_loop()
        return self._next_loop

    def render(self, component, *args, **kwargs):
        self._render_calls.append((component, args, kwargs))

    def run_task(self, handler, *args, **kwargs):
        """Record the scheduled work; tests drive coroutines themselves."""
        self.tasks.append((handler, args, kwargs))
        return handler(*args, **kwargs)

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)

    def pop_dialog(self):
        return self.dialogs.pop() if self.dialogs else None

    def update(self, *_controls) -> None:
        return None


@pytest.fixture
def fake_page():
    return FakePage()


@pytest.fixture
def platform_windows(monkeypatch):
    """Pretend desktop (no nativeLibraryDir) — the default for unit tests."""
    monkeypatch.delenv("ANDROID_NATIVE_LIBRARY_DIR", raising=False)
