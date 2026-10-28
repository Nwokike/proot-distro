from __future__ import annotations

import threading
from types import SimpleNamespace

import flet as ft
import pytest

from app_controller import AppController
from components.install_progress_modal import show_install_progress_modal
from core.state import state


@pytest.fixture(autouse=True)
def _reset_install_state():
    state.installing = None
    state.install_stage = ""
    state.install_logs = []
    state.install_completed = False
    state.install_dialog_minimized = False
    yield
    state.installing = None
    state.install_stage = ""
    state.install_logs = []
    state.install_dialog_minimized = False


def test_install_modal_registers_its_dialog(fake_page):
    show_install_progress_modal(fake_page, "debian:bookworm")

    assert fake_page._install_dialog is fake_page.dialogs[-1]
    assert isinstance(fake_page._install_dialog, ft.AlertDialog)


@pytest.mark.asyncio
async def test_install_progress_refreshes_the_open_dialog(fake_page):
    dialog_updated = threading.Event()

    class UpdateControl:
        def __init__(self):
            self.value = ""
            self.controls = []
            self.update_count = 0

        def update(self):
            self.update_count += 1

    class DialogControl:
        open = True

        def update(self):
            dialog_updated.set()

    stage_control = UpdateControl()
    logs_control = UpdateControl()
    fake_page._install_dialog = DialogControl()
    fake_page._install_stage_text = stage_control
    fake_page._install_logs_column = logs_control

    class ProotStub:
        PULL_LIMIT_COPY = "pull limit reached"

        @staticmethod
        def busy_locks():
            return []

        @staticmethod
        def install(_image, _name, on_line):
            on_line(" unpacking image ")
            if not dialog_updated.wait(timeout=2):
                raise RuntimeError("progress callback did not update the dialog")
            return SimpleNamespace(ok=False)

        @staticmethod
        def is_pull_limit(_outcome):
            return False

        @staticmethod
        def friendly_job_error(_outcome):
            return "install failed"

    controller = object.__new__(AppController)
    controller.page = fake_page
    controller.proot = ProotStub()
    controller.show_snack = lambda _message: None

    async def refresh_containers():
        return None

    controller.refresh_containers = refresh_containers

    await controller.install_distro("debian:bookworm", "debian")

    assert stage_control.value == "unpacking image"
    assert [line.value for line in logs_control.controls] == ["unpacking image"]
    assert stage_control.update_count == 1
    assert logs_control.update_count == 1


@pytest.mark.asyncio
async def test_open_session_logs_and_reraises_the_original_error(caplog):
    error = RuntimeError("session startup failed")

    class SessionManagerStub:
        async def open(self, _container):
            raise error

    snacks = []
    controller = object.__new__(AppController)
    controller.session_manager = SessionManagerStub()
    controller.show_snack = snacks.append

    with pytest.raises(RuntimeError, match="session startup failed") as raised:
        await controller.open_session("debian")

    assert raised.value is error
    assert state.session_error == "could not open debian: session startup failed"
    assert snacks == [state.session_error]
    assert any(record.exc_info for record in caplog.records)
