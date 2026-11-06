"""desk_service — the termux-desk wrap contract (script, manager, provision)
plus the v1.1.0 UI-structure pins (card 3-item, grouped menu, files banner).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import termux_desk
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
    "desk_ready": False,
    "dbus": False,
    "x_server": False,
    "desktops": {"xfce": False, "lxqt": False, "mate": False, "icewm": False, "openbox": False},
}


# ── guest script (script.py) — Xvfb + session only, server is in-app ────────


def test_guest_script_starts_xvfb_listening_on_tcp():
    src = desk_script.build_guest_script(port=9999, geometry="1600x900")
    assert "Xvfb :0" in src
    assert "1600x900x24" in src
    # Modern Xservers default to -nolisten tcp; without the explicit flag the
    # host server's TCP probe is refused for the whole readiness window.
    assert "-listen tcp" in src
    assert "-nolisten tcp" not in src


def test_guest_script_runs_the_desktop_via_dbus():
    src = desk_script.build_guest_script(port=9999, desktop_env="xfce")
    assert "dbus-run-session -- startxfce4" in src


def test_guest_script_has_no_python_left():
    src = desk_script.build_guest_script(port=9999, desktop_env="xfce", tunnel=True)
    assert "python3" not in src
    assert "termux_desk" not in src
    assert "auth.json" not in src


def test_guest_script_installs_the_xauth_cookie():
    cookie = "ab" * 16
    src = desk_script.build_guest_script(port=9999, display=3, xauth_cookie=cookie)
    assert 'xauth -f /tmp/termux-desk/xauth-3 add "127.0.0.1:3" .' in src
    assert "localhost:3" in src
    assert cookie in src
    assert 'XVFB_AUTH="-auth /tmp/termux-desk/xauth-3"' in src
    assert "Xvfb :3 $XVFB_AUTH -listen tcp -screen 0" in src


def test_guest_script_without_cookie_runs_xvfb_bare():
    src = desk_script.build_guest_script(port=9999)
    assert "xauth" not in src
    assert "-auth" not in src


def test_guest_script_tunnel_is_upstreams_exact_ssh_line():
    plain = desk_script.build_guest_script(port=9999, display=2)
    tunneled = desk_script.build_guest_script(port=9999, display=2, tunnel=True)
    assert "ssh" not in plain
    assert (
        "ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30"
        " -R 80:localhost:9999 nokey@localhost.run" in tunneled
    )
    assert "/tmp/termux-desk/tunnel-2.log" in tunneled


def test_tunnel_url_regex_is_upstreams_pattern():
    sample = "Warning: Permanently added. \n  https://random-name-123.lhr.life connected\n"
    match = desk_script.TUNNEL_URL_RE.search(sample)
    assert match and match.group(1) == "https://random-name-123.lhr.life"


def test_guest_script_app_mode_replaces_the_desktop():
    desktop = desk_script.build_guest_script(port=9999, desktop_env="xfce")
    assert "dbus-run-session -- startxfce4" in desktop
    app = desk_script.build_guest_script(port=9999, app_command="python3 app.py --flag 'x'")
    assert "dbus-run-session" not in app
    assert "sh -c 'python3 app.py --flag '\"'\"'x'\"'\"''" in app  # shlex-quoted command
    assert "startxfce4" not in app


def test_guest_script_rejects_unsafe_values():
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, geometry="999; rm -rf /")
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, geometry="1280x")
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, display=100)
    with pytest.raises(ValueError):
        desk_script.build_guest_script(port=9999, xauth_cookie="zz; rm -rf /")
    assert desk_script.is_valid_geometry("1280x720")
    assert not desk_script.is_valid_geometry("1280")


# ── provision (provision.py) — no guest python at all ────────────────────────


def test_every_package_manager_gets_ssh_and_xauth_and_no_python():
    for pm, packages in desk_provision._BASE_PACKAGES.items():
        assert any(p.startswith("openssh") for p in packages), f"{pm} misses openssh"
        assert any("xauth" in p for p in packages), f"{pm} misses xauth"
        assert not any(p.startswith(("py3-", "python3-", "python-")) for p in packages), (
            f"{pm} still installs guest python"
        )


def test_alpine_install_script_carries_the_whole_stack():
    src = desk_provision.install_script(ALPINE_CAPS, "xfce")
    for package in ("xvfb", "xauth", "xclip", "openssh-client"):
        assert package in src
    assert "apk add --no-cache" in src


def test_unsupported_container_names_the_reason():
    caps = {"os": {"distro_id": "mystery", "distro_like": "", "version_id": "", "pretty_name": ""}}
    assert desk_provision.unsupported_reason(caps) is not None
    assert desk_provision.package_manager_for(ALPINE_CAPS) == "apk"


# ── manager (manager.py) — in-process server, Xvfb TCP wait, shim ───────────


def test_session_key_format_and_shared_singleton():
    assert desk_manager.session_key("debian", 0) == "debian:0"
    assert desk_manager.session_key("debian", 12) == "debian:12"
    assert desk_manager.shared_manager() is desk_manager.shared_manager()


def test_desk_session_carries_the_full_wrap_surface():
    session = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    assert session.geometry == "1280x720"
    assert session.host == "127.0.0.1"
    assert session.tunnel is False
    assert session.tunnel_url == ""
    assert session.mode == "desktop"
    assert session.server is None
    assert desk_manager._local_ip() == "" or isinstance(desk_manager._local_ip(), str)


def test_xauth_cookie_is_stable_hex():
    first = desk_manager.xauth_cookie()
    assert len(first) == 32
    assert all(c in "0123456789abcdef" for c in first)
    assert desk_manager.xauth_cookie() == first  # app-global: one value forever


def test_read_tunnel_url_applies_upstreams_regex(monkeypatch, tmp_path):
    containers = tmp_path / "containers"
    guest_dir = containers / "debian" / "rootfs" / "tmp" / "termux-desk"
    guest_dir.mkdir(parents=True)
    (guest_dir / "tunnel-1.log").write_text(
        "debug1: Connection to localhost.run\nhttps://neat-word-42.lhr.life is up\n"
    )
    monkeypatch.setattr(desk_manager.storage_paths, "containers_dir", lambda: containers)

    assert desk_manager._read_tunnel_url("debian", 1) == "https://neat-word-42.lhr.life"
    assert desk_manager._read_tunnel_url("debian", 2) == ""  # no log yet — never a crash


def test_spawn_passes_the_wrap_surface_into_the_script_builder(monkeypatch):
    built = {}
    manager = desk_manager.DeskManager()
    monkeypatch.setattr(
        desk_manager, "build_guest_script", lambda **kw: built.update(kw) or "script"
    )
    monkeypatch.setattr(
        desk_manager,
        "_write_guest_script",
        lambda c, s, d: f"/tmp/termux-desk/run-display-{d}.sh",
    )
    monkeypatch.setattr(
        desk_manager.session_service, "command_argv", lambda **kw: ({}, ["/bin/sh", "x"])
    )
    monkeypatch.setattr(
        desk_manager.subprocess,
        "Popen",
        lambda *a, **kw: type("P", (), {"pid": 123, "stdout": None, "poll": lambda self: None})(),
    )
    session = desk_manager.DeskSession(container="debian", key="debian:2", display=2, port=12345)
    manager._spawn(session)
    assert built["geometry"] == "1280x720"
    assert built["port"] == 12345
    assert built["tunnel"] is False
    assert built["display"] == 2
    assert built["app_command"] is None
    assert built["xauth_cookie"] == desk_manager.xauth_cookie()
    session2 = desk_manager.DeskSession(
        container="debian",
        key="debian:3",
        display=3,
        port=12346,
        mode="app",
        app_command="firefox",
        geometry="1600x900",
        tunnel=True,
    )
    manager._spawn(session2)
    assert built["geometry"] == "1600x900"
    assert built["tunnel"] is True
    assert built["app_command"] == "firefox"


def test_wait_xvfb_honors_stopping_as_a_quiet_cancel():
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    session.status = desk_manager.DeskStatus.STOPPING
    session._process = type("P", (), {"poll": lambda self: 1})()
    manager._wait_xvfb(session, 0.5)  # must return silently, no ERROR
    assert session.status is desk_manager.DeskStatus.STOPPING
    assert session.error == ""


def test_wait_xvfb_fails_on_dead_process(monkeypatch):
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    session.status = desk_manager.DeskStatus.STARTING
    session._process = type("P", (), {"poll": lambda self: 1, "returncode": 1})()
    monkeypatch.setattr(desk_manager, "_tcp_open", lambda port: False)
    manager._wait_xvfb(session, 0.5)
    assert session.status is desk_manager.DeskStatus.ERROR
    assert "exited" in session.error


def test_read_logs_marks_a_post_ready_crash_as_error():
    import io

    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    session.status = desk_manager.DeskStatus.RUNNING
    session._process = type(
        "P", (), {"stdout": io.BytesIO(b""), "poll": lambda self: 1, "returncode": 1}
    )()
    manager._read_logs(session)
    assert session.status is desk_manager.DeskStatus.ERROR
    assert "exited" in session.error


class _FakeServer:
    def __init__(self, host, port, display=None, fps=12.0, quality=70):
        self.host = host
        self.port = port
        self.display = display
        self.started = False
        self.stopped = False
        self._auth_code = "A3F8K2"

    async def start(self):
        self.started = True

    @property
    def local_url(self):
        return f"http://127.0.0.1:{self.port}/"

    async def stop(self):
        self.stopped = True


async def test_start_runs_the_server_in_process_and_stop_closes_it(monkeypatch):

    manager = desk_manager.DeskManager()
    created: list[_FakeServer] = []

    class _RecordingServer(_FakeServer):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            created.append(self)

    monkeypatch.setattr(termux_desk, "TermuxDeskServer", _RecordingServer)
    monkeypatch.setattr(
        manager, "_spawn", lambda s: setattr(s, "status", desk_manager.DeskStatus.STARTING)
    )
    monkeypatch.setattr(manager, "_wait_xvfb", lambda s, t: None)
    monkeypatch.setattr(desk_manager, "_ensure_clipboard_shim", lambda c, d: None)
    monkeypatch.setattr(
        desk_manager.session_service, "command_argv", lambda *a, **kw: ({}, ["/bin/sh", "x"])
    )

    session = await manager.start("debian", display=0)

    assert created and created[-1].started
    assert created[-1].display == "127.0.0.1:0"
    assert session.server is created[-1]
    assert session.code == "A3F8K2"
    assert session.url == f"http://127.0.0.1:{session.port}/"
    assert session.status is desk_manager.DeskStatus.RUNNING

    await manager.stop(session.key)
    assert created[-1].stopped
    assert session.server is None
    assert session.status is desk_manager.DeskStatus.IDLE


async def test_start_picks_the_lowest_free_display_per_container(monkeypatch):

    manager = desk_manager.DeskManager()
    monkeypatch.setattr(termux_desk, "TermuxDeskServer", _FakeServer)
    monkeypatch.setattr(
        manager, "_spawn", lambda s: setattr(s, "status", desk_manager.DeskStatus.STARTING)
    )
    monkeypatch.setattr(manager, "_wait_xvfb", lambda s, t: None)
    monkeypatch.setattr(desk_manager, "_ensure_clipboard_shim", lambda c, d: None)
    monkeypatch.setattr(
        desk_manager.session_service, "command_argv", lambda *a, **kw: ({}, ["/bin/sh", "x"])
    )

    # :0 taken → next start gets :1; another container is independent (:0).
    s0 = await manager.start("debian", display=0)
    s1 = await manager.start("debian")
    s2 = await manager.start("alpine")
    assert (s0.display, s1.display, s2.display) == (0, 1, 0)
    assert s1.key == "debian:1"
    # Already-RUNNING key returns the existing session without starting again.
    again = await manager.start("debian", display=1)
    assert again is s1


async def test_clipboard_shim_writes_dispatcher_exec_and_registry(monkeypatch, tmp_path):
    shim_calls: list[tuple[str, int]] = []

    def _fake_shim(container: str, display: int) -> None:
        shim_calls.append((container, display))

    manager = desk_manager.DeskManager()
    monkeypatch.setattr(
        manager, "_spawn", lambda s: setattr(s, "status", desk_manager.DeskStatus.STARTING)
    )
    monkeypatch.setattr(manager, "_wait_xvfb", lambda s, t: None)

    monkeypatch.setattr(termux_desk, "TermuxDeskServer", _FakeServer)
    monkeypatch.setattr(desk_manager, "_ensure_clipboard_shim", _fake_shim)

    session = manager._sessions.get("debian:0") or None
    assert session is None  # nothing registered before start
    started = await manager.start("debian", display=0)
    assert shim_calls == [("debian", 0)]
    assert started.key == "debian:0"


def test_clipboard_shim_files_are_generated(monkeypatch, tmp_path):
    monkeypatch.setattr(desk_manager.storage_paths, "cache_root", lambda: tmp_path / "cache")
    monkeypatch.setattr(
        desk_manager.session_service,
        "command_argv",
        lambda *a, **kw: (
            {"LD_LIBRARY_PATH": "/x/y"},
            ["/bin/proot", "--rootfs=/x", "/usr/bin/xclip"],
        ),
    )
    monkeypatch.setattr(Path, "chmod", lambda self, mode: None)

    desk_manager._ensure_clipboard_shim("debian", 0)

    shim_dir = tmp_path / "cache" / "xclip-shim"
    dispatcher = (shim_dir / "xclip").read_text(encoding="utf-8")
    exec_script = (shim_dir / "exec-debian.sh").read_text(encoding="utf-8")
    registry = (shim_dir / "registry").read_text(encoding="utf-8")
    assert 'awk -v n="$D"' in dispatcher  # DISPLAY → container lookup
    assert "$PDX_XCLIP_REGISTRY" in dispatcher
    assert "/usr/bin/xclip" in exec_script
    assert "LD_LIBRARY_PATH=/x/y" in exec_script
    assert registry.strip() == "0 debian"


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
    assert '"Install desktop"' in src


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
    def __init__(self, keys: list[str]) -> None:
        self._keys = keys

    def running(self) -> list:
        class _R:
            def __init__(self, key: str) -> None:
                self.key = key
                self.container = key.split(":")[0]

        return [_R(key) for key in self._keys]


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
    sa.desk_manager = _StubDesk(["debian:0"])
    await sa._update_fgs()
    assert started[-1] == "Display running: debian:0"

    sa.desk_manager = _StubDesk(["debian:0", "debian:1", "alpine:0"])
    await sa._update_fgs()
    assert started[-1] == "3 displays running: alpine:0, debian:0, debian:1"

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
        "TUNNEL_URL_RE",
        "build_guest_script",
        "install",
        "session_key",
        "shared_manager",
        "DESKTOP_ENVIRONMENTS",
    ):
        assert hasattr(desk_service, name)
    assert not hasattr(desk_service, "vendor_termux_desk")  # vendoring is gone


# ── M1 terminal + M2 UI pins ─────────────────────────────────────────────────


def test_terminal_view_is_keyed_by_session():
    """The switch-bug fix: TerminalView must receive key=entry.key so the
    reconciler remounts the MobileTerminal instead of patching in place."""
    src = (ROOT / "src" / "app_shell.py").read_text(encoding="utf-8")
    assert "TerminalView(entry, key=entry.key)" in src


def test_selector_has_a_new_shell_plus():
    src = (ROOT / "src" / "screens" / "session_selector_view.py").read_text(encoding="utf-8")
    assert (
        'section_header(\n                        "Open shells",\n                        action=ft.IconButton('
        in src
    )


def test_fab_has_copy_full_output_and_no_select_all():
    """Native select_all only reaches the rendered viewport on device — the
    option is removed (owner ruling); Copy Full Output strips escape noise."""
    src = (ROOT / "src" / "screens" / "terminal" / "menu.py").read_text(encoding="utf-8")
    assert '"Copy Full Output"' in src
    assert "entry.scrollback" in src
    assert "strip_ansi" in src
    assert '"Select All"' not in src


def test_display_tab_has_a_new_display_plus():
    src = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    assert "show_new_display_sheet" in src
    assert "ADD_ROUNDED" in src


def test_display_tab_groups_desktop_and_single_app():
    """The two sections a display IS — Desktop (per-container) and Single App
    (one app alone on :N) — with the starting card driven by observable state."""
    src = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    assert '"Desktop"' in src
    assert '"Single App"' in src
    # The starting card reads display_status (observable), not manager state.
    assert 'st.display_status == "starting"' in src


def test_distro_banner_between_install_and_containers():
    """One banner between the install area and the Containers header; none
    inside the container list; search keeps its empty-state banner."""
    src = (ROOT / "src" / "screens" / "distro" / "__init__.py").read_text(encoding="utf-8")
    banner = src.index('pooled_banner_ad("containers-1", page)')
    header = src.index('section_header("Containers")')
    assert banner < header
    assert '"containers-empty"' not in src
    assert '"search-empty"' in src
    # Search bar: no leading icon; the trailing action is the mode icon.
    assert "bar_leading=" not in src
    assert "ft.Icons.SEARCH_ROUNDED," in src


def test_app_sheet_launches_single_app_displays():
    """The custom command must reach start_display as app_command (was dropped)."""
    src = (ROOT / "src" / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    assert "methods.start_display, container, None, cmd.strip(), None" in src
    assert "asyncio.gather" in src  # probes run in parallel now


def test_settings_offer_custom_values_and_portrait():
    src = (ROOT / "src" / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    assert "_CUSTOM" in src
    assert '("portrait", "Portrait")' in src


def test_naming_says_install_desktop():
    src = (ROOT / "src" / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    card = (ROOT / "src" / "screens" / "container_card.py").read_text(encoding="utf-8")
    assert '"Install desktop",' in src
    assert '"Install desktop"' in card
    assert "Install display support" not in src + card


def test_cache_invalidation_on_remove_reset_rename():
    distro = (ROOT / "src" / "controller_actions" / "distro_actions.py").read_text(encoding="utf-8")
    cont = (ROOT / "src" / "controller_actions" / "container_actions.py").read_text(
        encoding="utf-8"
    )
    assert distro.count("invalidate_display_support(name)") == 2  # remove + reset
    assert "invalidate_display_support(orig)" in cont  # rename


def test_display_settings_single_default_source():
    from core.state import DEFAULT_DISPLAY_SETTINGS

    src = (ROOT / "src" / "controller_actions" / "display_actions.py").read_text(encoding="utf-8")
    assert "DEFAULT_DISPLAY_SETTINGS" in src
    assert DEFAULT_DISPLAY_SETTINGS["orientation"] == "landscape"
