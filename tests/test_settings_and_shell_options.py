"""Settings rows and shell login options — the two device failures of
2026-11-15: a None trailing control (page-error storm) and `-u <unknown user>`
failing inside proot after the sheet closed."""

from __future__ import annotations

import os
from pathlib import Path

import flet as ft
import pytest

from core import storage_paths
from core.state import state
from screens.container_dialogs.shell_options import option_error
from screens.settings_components import _setting_row


def _walk_controls(control) -> list:
    found = []
    for attr in ("controls", "content"):
        value = getattr(control, attr, None)
        if isinstance(value, list):
            found.extend(value)
        elif value is not None:
            found.append(value)
    return found


def _assert_no_none(control) -> None:
    """A None inside a controls list is the 'Null is not a subtype of Control'
    layout crash (device 2026-11-15: Settings rendered nothing)."""
    assert control is not None
    for child in _walk_controls(control):
        assert child is not None, f"None control inside {type(control).__name__}"
        _assert_no_none(child)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # neither trailing nor value — the row that crashed
        {"value": "24-bit · Q85"},
        {"trailing": ft.TextButton("Go")},
        {"value": "value", "trailing": ft.TextButton("Manage")},
        {"value": "value", "on_tap": lambda _e: None},
        {"trailing": ft.TextButton("Sweep"), "stacked": True},
        {"stacked": True},
    ],
)
def test_setting_row_never_emits_a_none_control(kwargs):
    row = _setting_row(ft.Icons.TUNE_ROUNDED, "Title", "Subtitle", **kwargs)
    _assert_no_none(row)


def _make_container(name: str, passwd: str) -> Path:
    rootfs = storage_paths.containers_dir() / name / "rootfs"
    (rootfs / "etc").mkdir(parents=True)
    (rootfs / "etc" / "passwd").write_text(passwd, encoding="utf-8")
    return rootfs


_PASSWD = (
    "root:x:0:0:root:/root:/bin/bash\n"
    "nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n"
    "app:x:1000:1000::/home/app:/bin/sh\n"
)


def test_container_users_reads_the_real_passwd():
    from services import proot_service

    _make_container("alpine", _PASSWD)
    users = proot_service.container_users("alpine")
    assert [u["name"] for u in users] == ["root", "nobody", "app"]
    assert users[2] == {
        "name": "app",
        "uid": "1000",
        "gid": "1000",
        "home": "/home/app",
        "shell": "/bin/sh",
    }


def test_guest_path_exists_stays_inside_the_rootfs():
    from services import proot_service

    rootfs = _make_container("alpine", _PASSWD)
    (rootfs / "home" / "app").mkdir(parents=True)
    assert proot_service.guest_path_exists("alpine", "/home/app")
    assert proot_service.guest_path_exists("alpine", "/home/app/..")
    assert not proot_service.guest_path_exists("alpine", "/home/missing")
    assert not proot_service.guest_path_exists("alpine", "../../etc")
    assert not proot_service.guest_path_exists("alpine", "relative")


def test_shell_options_reject_an_unknown_user_and_accept_real_ones():
    from services import proot_service

    _make_container("alpine", _PASSWD)
    users = proot_service.container_users("alpine")

    error = option_error("alpine", users, {"user": "kiri"})
    assert error is not None
    assert "no user 'kiri' in alpine" in error
    assert "root" in error and "app" in error

    assert option_error("alpine", users, {"user": "root"}) is None
    assert option_error("alpine", users, {"user": "app"}) is None
    assert option_error("alpine", users, {"user": "1000"}) is None
    assert option_error("alpine", users, {"user": "app:app"}) is None
    # Empty means "root" — the sheet's default user, never an error.
    assert option_error("alpine", users, {"user": ""}) is None


def test_shell_options_validate_workdir_binds_and_emulator(tmp_path):
    from services import proot_service

    rootfs = _make_container("alpine", _PASSWD)
    (rootfs / "srv").mkdir()
    users = proot_service.container_users("alpine")

    assert option_error("alpine", users, {"user": "root", "work_dir": "/srv"}) is None
    assert "does not exist" in option_error("alpine", users, {"user": "root", "work_dir": "/nope"})

    host_dir = tmp_path / "shared"
    host_dir.mkdir()
    assert option_error("alpine", users, {"bind_text": f"{host_dir}:/mnt"}) is None
    assert "does not exist on this device" in option_error(
        "alpine", users, {"bind_text": str(tmp_path / "missing")}
    )
    assert "bad env line" in option_error("alpine", users, {"env_text": "NO_EQUALS"})

    fake_emu = tmp_path / "qemu"
    fake_emu.write_text("#!/bin/sh\n")
    assert "not an executable file" in option_error("alpine", users, {"emulator": str(fake_emu)})
    os.chmod(fake_emu, 0o755)
    assert option_error("alpine", users, {"emulator": str(fake_emu)}) is None


def test_env_summary_counts_saved_defaults():
    from screens.settings.env_dialog import env_rows_summary

    state.env_defaults = None
    assert env_rows_summary() == "No default variables"
    state.env_defaults = {"FOO": "1"}
    assert env_rows_summary() == "1 variable set"
    state.env_defaults = {"FOO": "1", "BAR": "2"}
    assert env_rows_summary() == "2 variables set"


def test_no_text_field_inside_a_wrapping_row():
    """A TextField inside Row(wrap=True) crashes Flutter with
    "type 'WrapParentData' is not a subtype of type 'FlexParentData'"
    (proven 2026-11-15 by rendering one field in a wrap row). Wrap rows carry
    pills and toggles only; a field goes in a non-wrapping row."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src"
    offenders = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "attr", getattr(node.func, "id", ""))
            if name not in ("Row", "Column"):
                continue
            kw = {k.arg: k.value for k in node.keywords if k.arg}
            wrap = kw.get("wrap")
            if not (isinstance(wrap, ast.Constant) and wrap.value is True):
                continue
            controls = kw.get("controls")
            if controls is None:
                continue
            for sub in ast.walk(controls):
                if not isinstance(sub, ast.Call):
                    continue
                fname = getattr(sub.func, "attr", getattr(sub.func, "id", ""))
                if fname in ("TextField", "house_field"):
                    offenders.append(f"{path.relative_to(root)}:{sub.lineno}")
    assert not offenders, f"TextField inside a wrap row: {offenders}"


def test_arch_choices_come_from_upstream_not_a_hardcoded_list():
    """Every architecture spelling offered by Home and Build is one upstream
    accepts: the list is derived from proot_distro.arch and validated through
    normalize_arch (never a second, drifting copy)."""
    from proot_distro import arch as upstream_arch

    from services import proot_service

    choices = proot_service.arch_choices()
    assert choices[0] == "host"  # our "no -a" sentinel
    for name in choices[1:]:
        assert upstream_arch.normalize_arch(name), f"{name} is not upstream-accepted"
    # The native names and the linux/ platform strings both appear.
    for expected in ("aarch64", "x86_64", "linux/arm64", "linux/amd64"):
        assert expected in choices
    # The host default is a real, resolved architecture.
    assert upstream_arch.normalize_arch(proot_service.host_arch())


def test_probe_cache_expires_and_drops(tmp_path):
    """Probed facts live under the regenerable cache root with a TTL."""
    import json
    import time

    from core import probe_cache, storage_paths

    probe_cache.store("caps", "alpine", {"desktops": {"xfce": True}})
    assert probe_cache.load("caps", "alpine") == {"desktops": {"xfce": True}}

    # Expired entries are ignored.
    path = next((storage_paths.cache_root() / "proot-distro" / "probe").glob("caps-*.json"))
    payload = json.loads(path.read_text())
    payload["at"] = time.time() - 7200
    path.write_text(json.dumps(payload))
    assert probe_cache.load("caps", "alpine") is None

    # Dropping removes it for a recreated container.
    probe_cache.store("apps", "alpine", [{"label": "xterm", "cmd": "xterm"}])
    probe_cache.drop("apps", "alpine")
    assert probe_cache.load("apps", "alpine") is None


def test_sweep_temp_removes_only_stale_files(tmp_path):
    import os
    import time

    from core import storage_paths

    exports = storage_paths.exports_root()
    old = exports / "old.tar.gz"
    new = exports / "new.tar.gz"
    old.write_text("x")
    new.write_text("y")
    os.utime(old, (time.time() - 3 * 86400, time.time() - 3 * 86400))
    removed = storage_paths.sweep_temp()
    assert removed >= 1
    assert not old.exists() and new.exists()


def test_prune_display_logs_keeps_newest_generations():
    import os
    import time

    from core import storage_paths

    folder = storage_paths.data_root() / "display-logs"
    folder.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for name, age in (
        ("alpine:0.log", 0),
        ("alpine:0.log.1", 60),
        ("alpine:1.log", 120),
        ("alpine:2.log", 180),
        ("debian:0.log", 0),
        ("debian:0.log.1", 60),
        ("debian:0.log.2", 120),
        ("debian:0.log.3", 180),
    ):
        path = folder / name
        path.write_text("x")
        os.utime(path, (now - age, now - age))
    # Old, beyond the age window.
    stale = folder / "ubuntu:0.log"
    stale.write_text("x")
    os.utime(stale, (now - 30 * 86400, now - 30 * 86400))

    removed = storage_paths.prune_display_logs(keep_per_container=3, keep_days=7)
    assert removed >= 2
    assert not stale.exists()
    debian = sorted(p.name for p in folder.glob("debian:0.log*"))
    assert len(debian) == 3
    assert "debian:0.log.3" not in debian  # oldest generation dropped
    assert (folder / "alpine:0.log").exists()


def test_probe_cache_drop_all_clears_every_entry():
    from core import probe_cache, storage_paths

    probe_cache.store("caps", "alpine", {"ok": True})
    probe_cache.store("apps", "alpine", [{"label": "xterm", "cmd": "xterm"}])
    removed = probe_cache.drop_all()
    assert removed == 2
    assert probe_cache.load("caps", "alpine") is None
    assert not list((storage_paths.cache_root() / "proot-distro" / "probe").glob("*.json"))


@pytest.mark.asyncio
async def test_remove_later_deletes_a_staged_export(tmp_path):
    from screens.files.operations import _remove_later

    staged = tmp_path / "export.tar.gz"
    staged.write_text("x")
    await _remove_later(staged, delay=0)
    assert not staged.exists()
