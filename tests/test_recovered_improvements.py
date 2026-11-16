from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import flet as ft
import pytest
from _src_text import module_text

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
        def install(_image, _name, on_line=None, **_kw):
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
async def test_open_session_reports_the_error_without_re_raising(caplog):
    error = RuntimeError("session startup failed")
    # The shell preflight runs before the manager: give the container a shell
    from core import storage_paths

    (storage_paths.containers_dir() / "debian" / "rootfs" / "bin").mkdir(parents=True)
    (storage_paths.containers_dir() / "debian" / "rootfs" / "bin" / "bash").write_text("")

    class SessionManagerStub:
        async def open(self, _container, **kwargs):
            raise error

    snacks = []
    controller = object.__new__(AppController)
    controller.session_manager = SessionManagerStub()
    controller.show_snack = snacks.append

    # An exception escaping a page.run_task handler lands in Flet's future
    # callback and becomes a page-error storm (device 2026-11-15) — the
    # controller reports through the snack and returns instead.
    await controller.open_session("debian")

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
async def test_major_actions_trigger_interstitial(method_name, args):
    """Owner ruling 2026-11-14: EVERY major action shows an interstitial; the
    service owns the one global 60 s cooldown that keeps it from being spam."""

    class ProotStub:
        def clear_cache(self, orphan=False):
            return SimpleNamespace(ok=True)

        def remove_cached_image(self, _identifier):
            return SimpleNamespace(ok=True)

        def copy_path(self, _source, _destination, _move=False, recursive=True):
            return SimpleNamespace(ok=True)

        def sync_path(self, _source, _destination, _checksum, _delete):
            return SimpleNamespace(ok=True)

        def kill_session(self, _pid, _all=False, _signal=None):
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

    controller.ad_service.show_interstitial.assert_awaited()

    state.cache_busy = False


@pytest.mark.asyncio
async def test_distro_search_does_not_interrupt_with_interstitial():
    class ProotStub:
        @staticmethod
        def search_images(_query, _limit=20):
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


@pytest.mark.asyncio
async def test_install_is_refused_offline_with_an_honest_reason():
    controller = object.__new__(AppController)
    snacks: list[str] = []
    controller.show_snack = snacks.append
    state.installing = None
    previous = state.online
    state.online = False
    try:
        await controller.install_distro("alpine:latest", "alpine")
    finally:
        state.online = previous
    assert snacks and "offline" in snacks[0]
    assert state.installing is None


def test_backups_are_delivered_by_path_not_through_memory():
    """`save_file(src_bytes=…)` loads the whole archive into RAM and pushes it
    through the Flet bridge — a multi-GB rootfs OOMs. The archive must be
    copied into a picked folder or shared by path."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1] / "src/controller_actions/container_actions.py"
    ).read_text()
    assert "staging.read_bytes()" not in src  # the OOM path
    assert "src_bytes=" not in src
    assert "ShareFile.from_path" in src
    assert "get_directory_path" in src


def test_restore_asks_for_confirmation_first():
    """Upstream's restore destroys the target rootfs; the trigger must confirm."""

    src = module_text("screens/container_actions.py", "screens/container_dialogs")
    assert "_confirm_restore" in src
    assert "Everything currently in the container is lost." in src


@pytest.mark.asyncio
async def test_battery_saver_lowers_only_factory_display_defaults(monkeypatch):
    from core.state import DEFAULT_DISPLAY_SETTINGS

    class Battery:
        @staticmethod
        async def is_in_battery_save_mode():
            return True

    page = type("P", (), {"battery": Battery()})()
    controller = object.__new__(AppController)
    controller.page = page
    state.display_settings = dict(DEFAULT_DISPLAY_SETTINGS)
    await controller._apply_battery_defaults()
    assert state.display_settings["fps"] == 15
    assert state.display_settings["quality"] == 60

    state.display_settings = {**DEFAULT_DISPLAY_SETTINGS, "fps": 45}
    await controller._apply_battery_defaults()
    assert state.display_settings["fps"] == 45  # a user choice is never overridden
    state.display_settings = dict(DEFAULT_DISPLAY_SETTINGS)
