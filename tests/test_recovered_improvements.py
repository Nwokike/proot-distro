from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

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


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("clear_cache", ()),
        ("clear_orphan_layers", ()),
        ("remove_cached_image", ("sha256:abc",)),
        ("copy_path", ("/source", "/destination")),
        ("sync_path", ("/source", "/destination")),
        ("kill_all_sessions", ()),
        ("kill_session", ("123",)),
    ],
)
@pytest.mark.asyncio
async def test_maintenance_actions_do_not_trigger_interstitials(method_name, args):
    class ProotStub:
        def clear_cache(self, orphan=False):
            return SimpleNamespace(ok=True)

        def remove_cached_image(self, _identifier):
            return SimpleNamespace(ok=True)

        def copy_path(self, _source, _destination):
            return SimpleNamespace(ok=True)

        def sync_path(self, _source, _destination, _checksum, _delete):
            return SimpleNamespace(ok=True)

        def kill_session(self, _pid, _all=False):
            return SimpleNamespace(ok=True)

        @staticmethod
        def friendly_job_error(_outcome):
            return "operation failed"

    controller = object.__new__(AppController)
    controller.proot = ProotStub()
    controller.ad_service = SimpleNamespace(show_interstitial=AsyncMock())
    controller.show_snack = lambda _message: None
    controller.refresh_containers = AsyncMock()
    state.cache_busy = False

    await getattr(controller, method_name)(*args)

    controller.ad_service.show_interstitial.assert_not_awaited()

    state.cache_busy = False


@pytest.mark.asyncio
async def test_distro_search_does_not_interrupt_with_interstitial():
    class ProotStub:
        @staticmethod
        def search_images(_query):
            return []

    controller = object.__new__(AppController)
    controller.proot = ProotStub()
    controller.ad_service = SimpleNamespace(show_interstitial=AsyncMock())

    await controller.search_distro("alpine")

    controller.ad_service.show_interstitial.assert_not_awaited()


@pytest.mark.parametrize("succeeded", [True, False])
@pytest.mark.asyncio
async def test_container_rename_shows_interstitial_only_after_success(succeeded):
    class ProotStub:
        @staticmethod
        def rename_container(_original, _new):
            return SimpleNamespace(ok=succeeded)

        @staticmethod
        def friendly_job_error(_outcome):
            return "rename failed"

    controller = object.__new__(AppController)
    controller.proot = ProotStub()
    controller.ad_service = SimpleNamespace(show_interstitial=AsyncMock())
    controller.show_snack = lambda _message: None
    controller.refresh_containers = AsyncMock()

    await controller.rename_container("old", "new")

    if succeeded:
        controller.ad_service.show_interstitial.assert_awaited_once()
    else:
        controller.ad_service.show_interstitial.assert_not_awaited()
