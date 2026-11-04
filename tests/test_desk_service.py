"""desk_service — the termux-desk wrap contract (script, manager, provision)
plus the v1.1.0 UI-structure pins (card 3-item, grouped menu, files banner).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from session_support import GOLDEN_CMD

from core.state import state
from screens.desktop import auth_js, paste_js, press_js
from services import desk_service, session_service
from services.desk_service import manager as desk_manager
from services.desk_service import provision as desk_provision
from services.desk_service import script as desk_script
from state.controller_ctx import ControllerMethods

ROOT = Path(__file__).resolve().parents[1]

ALPINE_CAPS = {
    "os": {
        "distro_id": "alpine",
        "distro_like": "",
        "version_id": "3.22",
        "pretty_name": "Alpine 3.22",
    },
    "python3": True,
    "python_ver": "3.12",
    "guest_deps": {"aiohttp": False, "PIL": False, "Xlib": False},
    "desk_ready": False,
    "dbus": False,
    "x_server": False,
    "desktops": {"xfce": False, "lxqt": False, "mate": False, "icewm": False, "openbox": False},
}


# ── guest script (script.py) ─────────────────────────────────────────────────


def test_guest_script_starts_xvfb_with_the_requested_geometry():
    src = desk_script.build_guest_script(port=9999, geometry="1600x900")
    assert "Xvfb :0 -screen 0 1600x900x24 -nolisten tcp" in src


def test_guest_script_runs_the_desktop_via_dbus():
    src = desk_script.build_guest_script(port=9999, desktop_env="xfce")
    assert "dbus-run-session -- startxfce4" in src


def test_guest_script_writes_the_access_code_for_the_app():
    src = desk_script.build_guest_script(port=9999)
    assert '"/tmp/termux-desk/auth.json"' in src
    assert '"code": server._auth_code' in src


def test_guest_script_binds_loopback_by_default_and_lan_when_asked():
    default = desk_script.build_guest_script(port=9999)
    assert "host='127.0.0.1'" in default
    lan = desk_script.build_guest_script(port=9999, host="0.0.0.0")
    assert "host='0.0.0.0'" in lan


def test_guest_script_tunnel_thread_only_when_enabled():
    plain = desk_script.build_guest_script(port=9999)
    tunneled = desk_script.build_guest_script(port=9999, tunnel=True)
    # The upstream tunnel call is gated on the flag: `if True:` starts the
    # daemon thread that publishes *.lhr.life; `if False:` leaves it dead.
    assert "if True:" in tunneled
    assert "if False:" in plain
    for marker in (
        "LocalhostRunTunnel",
        '"/tmp/termux-desk/tunnel.json"',
        'json.dump({"url": url}',
    ):
        assert marker in tunneled


def test_guest_script_rejects_unsafe_geometry_and_host():
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, geometry="999; rm -rf /")
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, geometry="1280x")
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, host="192.168.1.5")
    assert desk_script.is_valid_geometry("1280x720")
    assert not desk_script.is_valid_geometry("1280")


# ── provision (provision.py) ─────────────────────────────────────────────────


def test_every_package_manager_gets_ssh_for_the_tunnel():
    for pm, packages in desk_provision._BASE_PACKAGES.items():
        assert any(p.startswith("openssh") for p in packages), f"{pm} misses openssh"


def test_alpine_install_script_carries_the_whole_stack():
    src = desk_provision.install_script(ALPINE_CAPS, "xfce")
    for package in ("xvfb", "xclip", "py3-aiohttp", "py3-pillow", "py3-xlib", "openssh-client"):
        assert package in src
    assert "apk add --no-cache" in src


def test_unsupported_container_names_the_reason():
    caps = {"os": {"distro_id": "mystery", "distro_like": "", "version_id": "", "pretty_name": ""}}
    assert desk_provision.unsupported_reason(caps) is not None
    assert desk_provision.package_manager_for(ALPINE_CAPS) == "apk"


# ── manager reads the guest-written files (manager.py) ───────────────────────


def test_manager_reads_auth_and_tunnel_from_the_guest_rootfs(monkeypatch, tmp_path):
    containers = tmp_path / "containers"
    guest_dir = containers / "debian" / "rootfs" / "tmp" / "termux-desk"
    guest_dir.mkdir(parents=True)
    (guest_dir / "auth.json").write_text(json.dumps({"code": "A3F8K2", "port": 9999}))
    (guest_dir / "tunnel.json").write_text(json.dumps({"url": "https://abc.lhr.life"}))
    monkeypatch.setattr(desk_manager.storage_paths, "containers_dir", lambda: containers)

    assert desk_manager._read_auth("debian")["code"] == "A3F8K2"
    assert desk_manager._read_tunnel("debian")["url"] == "https://abc.lhr.life"
    # Missing files are empty dicts — never a crash (tunnel absence is normal).
    assert desk_manager._read_tunnel("alpine") == {}


def test_desk_session_carries_the_full_wrap_surface():
    session = desk_manager.DeskSession(container="debian")
    assert session.geometry == "1280x720"
    assert session.host == "127.0.0.1"
    assert session.tunnel is False
    assert session.tunnel_url == ""
    assert session.display == 0
    assert desk_manager._local_ip() == "" or isinstance(desk_manager._local_ip(), str)


def test_start_passes_the_wrap_surface_into_the_script_builder(monkeypatch):
    built = {}
    manager = desk_manager.DeskManager()
    monkeypatch.setattr(
        desk_manager, "build_guest_script", lambda **kw: built.update(kw) or "script"
    )
    monkeypatch.setattr(
        desk_manager, "_write_guest_script", lambda c, s: "/tmp/termux-desk/run-display.sh"
    )
    monkeypatch.setattr(
        desk_manager.session_service, "command_argv", lambda **kw: ({}, ["/bin/sh", "x"])
    )
    monkeypatch.setattr(
        desk_manager.subprocess,
        "Popen",
        lambda *a, **kw: type("P", (), {"pid": 123, "stdout": None, "poll": lambda self: None})(),
    )
    session = desk_manager.DeskSession(container="debian")
    manager._spawn(session)
    assert built["geometry"] == "1280x720"
    assert built["host"] == "127.0.0.1"
    assert built["tunnel"] is False
    session2 = desk_manager.DeskSession(
        container="debian", geometry="1600x900", host="0.0.0.0", tunnel=True
    )
    manager._spawn(session2)
    assert built["geometry"] == "1600x900"
    assert built["host"] == "0.0.0.0"
    assert built["tunnel"] is True


# ── shell login options (the 100% proot-distro wrap) ────────────────────────


async def test_session_argv_with_options_threads_upstream_login_options(monkeypatch):
    captured = {}

    def _fake(container, **login_opts):
        captured.update(login_opts)
        return GOLDEN_CMD

    monkeypatch.setattr(session_service.proot_service, "get_proot_cmd_with_options", _fake)

    session_service.session_argv_with_options(
        "debian",
        {
            "user": "root",
            "work_dir": "/root",
            "env": ["FOO=1"],
            "bind": ["/sdcard"],
            "shared_tmp": True,
            "shared_home": False,
            "fix_low_ports": True,
            "isolated": False,
        },
    )

    assert captured.get("work_dir") == "/root"
    assert captured.get("env") == ["FOO=1"]
    assert captured.get("bind") == ["/sdcard"]
    assert captured.get("shared_tmp") is True
    # fix_low_ports maps onto upstream's redirect_ports destination.
    assert captured.get("redirect_ports") is True
    # Defaults are not sent at all.
    assert "user" not in captured
    assert "shared_home" not in captured
    assert "isolated" not in captured


async def test_session_argv_with_options_parses_the_upstream_line(monkeypatch):
    monkeypatch.setattr(
        session_service.proot_service,
        "get_proot_cmd_with_options",
        lambda container, **opts: GOLDEN_CMD,
    )
    env, argv = session_service.session_argv_with_options("debian", {"shared_tmp": True})
    assert env["TERM"] == "xterm-256color"
    assert argv[-2:] == ["/bin/bash", "-l"]


# ── host↔guest bridges (screens/desktop JS builders) ─────────────────────────


def test_desktop_js_builders_drive_the_viewers_public_surface():
    assert "document.querySelector('#authInput')" in auth_js("A3F8K2")
    assert "document.querySelector('#authButton').click();" in auth_js("A3F8K2")
    assert '"A3F8K2"' in auth_js("A3F8K2")
    # keydown AND keyup — the guest sees a full press.
    assert 'new KeyboardEvent("keydown"' in press_js("Escape")
    assert 'new KeyboardEvent("keyup"' in press_js("Escape")
    assert '"Escape"' in press_js("Escape")
    # Paste writes navigator.clipboard then clicks the viewer's own button.
    assert "navigator.clipboard.writeText(" in paste_js("hello")
    assert "document.querySelector('#pasteButton').click());" in paste_js("hello")
    assert '"hello"' in paste_js("hello")


# ── UI structure pins ────────────────────────────────────────────────────────


def test_container_card_has_exactly_three_inline_actions():

    src = (ROOT / "src" / "screens" / "container_card.py").read_text(encoding="utf-8")
    assert "btn_reset" not in src
    assert "btn_remove" not in src
    assert '"Open shell"' in src
    assert "FilledTonalButton(" in src
    assert '"Open display"' in src
    assert '"Set up display"' in src


def test_container_menu_groups_destructive_actions_last():

    src = (ROOT / "src" / "screens" / "container_actions.py").read_text(encoding="utf-8")
    assert '"Shell with options…"' in src
    divider = src.index("ft.PopupMenuItem(content=ft.Divider")
    reset = src.index('"Reset"')
    remove = src.index('"Remove"')
    assert divider < reset < remove
    assert "theme.warn()" in src
    assert "def ask_reset(" in src
    assert "def ask_remove(" in src
    assert "def ask_shell_options(" in src


def test_files_banner_sits_at_the_bottom():

    src = (ROOT / "src" / "screens" / "files" / "__init__.py").read_text(encoding="utf-8")
    file_list = src.index("card(file_list_content")
    banner = src.index('pooled_banner_ad("files-1"')
    clearance = src.index("NAV_BAR_CLEARANCE")
    assert file_list < banner < clearance


def test_controller_ctx_exposes_the_v11_surface():
    methods = ControllerMethods()
    assert callable(methods.share_display)
    assert callable(methods.open_session_with_options)
    settings = state.display_settings or {}
    assert settings.get("geometry") == "auto"
    assert settings.get("orientation") == "landscape"
    assert settings.get("tunnel") is False
    assert settings.get("lan") is False


# ── FGS ref-count (desktops win, then shells, then stop) ────────────────────


class _StubDesk:
    def __init__(self, containers: list[str]) -> None:
        self._containers = containers

    def running(self) -> list:
        class _R:
            def __init__(self, name: str) -> None:
                self.container = name

        return [_R(name) for name in self._containers]


async def test_update_fgs_prefers_desktops_then_shells_then_stops(monkeypatch):
    from controller_actions.session_actions import SessionActions

    sa = SessionActions()
    started: list[str] = []
    stopped: list[bool] = []

    async def _start(label: str) -> None:
        started.append(label)

    async def _stop() -> None:
        stopped.append(True)

    monkeypatch.setattr(sa, "_start_fgs", _start)
    monkeypatch.setattr(sa, "_stop_fgs", _stop)

    sa.session_manager = type("M", (), {"entries": {"shell-a": object()}})()
    sa.desk_manager = _StubDesk(["debian"])
    await sa._update_fgs()
    assert started[-1] == "Display running: debian"

    sa.desk_manager = _StubDesk([])
    await sa._update_fgs()
    assert started[-1] == "Linux session running: shell-a"

    sa.session_manager = type("M", (), {"entries": {}})()
    await sa._update_fgs()
    assert stopped[-1] is True


def test_desk_service_exports_the_full_surface():
    for name in (
        "DeskManager",
        "DeskSession",
        "DeskStatus",
        "build_guest_script",
        "install",
        "vendor_termux_desk",
        "DESKTOP_ENVIRONMENTS",
    ):
        assert hasattr(desk_service, name)
