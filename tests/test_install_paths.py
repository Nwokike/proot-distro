"""Behavioural guards for the paths the retroactive audit found dead.

These are the exact regressions fix 12 introduced and the suite missed: a
staticmethod that took `self`, a missing @staticmethod on a channel helper, a
state field deleted while still read, and a positional arg that landed in
`work_dir` instead of `timeout`.
"""

from __future__ import annotations

import asyncio

from app_controller import AppController
from core.state import state


def test_install_channel_is_static_and_notifications_actually_fire(monkeypatch):
    calls: list[dict] = []

    class Notifications:
        async def show(self, **kw):
            calls.append(kw)

    controller = object.__new__(AppController)
    controller.notifications = Notifications()
    controller._ensure_notification_permission = _async_none
    # A plain helper must not need an instance to be callable.
    channel = AppController._install_channel()
    assert channel is not None

    asyncio.run(controller._notify_install("Installing", "debian…", ongoing=True))
    assert calls, "notifications.show was never reached"
    assert calls[0]["options"].progress.indeterminate is True


async def _async_none(*_a, **_kw) -> None:
    return None


def test_cancel_install_display_is_a_bound_method_that_stops_the_session(monkeypatch):
    stopped: list[bool] = []

    class Session:
        def stop(self) -> None:
            stopped.append(True)

    controller = object.__new__(AppController)
    controller._install_session = Session()
    controller.show_snack = lambda _m: None
    # Called exactly like the UI does it: no arguments.
    asyncio.run(controller.cancel_install_display())
    assert stopped == [True]


def test_desktop_install_stream_does_not_touch_a_removed_state_field():

    from _src_text import module_text

    src = module_text("controller_actions/display_install.py", "controller_actions")
    assert "display_install_logs" not in src
    assert "display_installing" not in src
    assert not hasattr(state, "display_install_logs")


def test_guest_has_ssh_passes_a_timeout_not_a_work_dir(monkeypatch):
    captured: dict = {}

    def fake_capture(container, command, work_dir=None, timeout=None, on_chunk=None, options=None):
        captured.update(work_dir=work_dir, timeout=timeout)
        return {"ok": True}

    import services.session_service as session_service

    monkeypatch.setattr(session_service, "command_capture", fake_capture)
    controller = object.__new__(AppController)
    assert asyncio.run(controller._guest_has_ssh("debian")) is True
    assert captured["work_dir"] is None
    assert captured["timeout"] == 15.0
