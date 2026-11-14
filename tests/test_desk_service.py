"""desk_service — the Option-D wrap contract (Xvnc + PulseAudio in-app, noVNC
viewer): guest script, runtime, stream server, manager, provision — plus the
v1.1.0 UI-structure pins (card 3-item, grouped menu, files banner).
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest
from session_support import GOLDEN_CMD

from core.state import state
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
    "desk_ready": True,  # apps ALWAYS run — the display is in the app now
    "dbus": False,
    "desktops": {"xfce": False, "lxqt": False, "mate": False, "icewm": False, "openbox": False},
}


# ── guest script (script.py) — exports + session only, Xvnc is in-app ───────


def test_guest_script_exports_the_app_side_display():
    src = desk_script.build_guest_script(port=9999, geometry="1600x900", display=3)
    # The guest connects over the SHARED loopback to Xvnc's X port — no unix
    # socket exists (Xvnc runs -nolisten unix; there is no /tmp/.X11-unix).
    assert "export DISPLAY=127.0.0.1:3" in src
    # The auth file is written by the app into the rootfs (no xauth binary).
    assert 'export XAUTHORITY="/tmp/x11/xauth-3"' in src
    # The app-side PulseAudio daemon serves guest audio over loopback.
    assert "export PULSE_SERVER=127.0.0.1:4713" in src
    # Nothing X-related runs in the guest anymore.
    assert "Xvfb" not in src
    assert "xauth " not in src
    assert "xclip" not in src


def test_guest_script_runs_the_desktop_via_dbus():
    src = desk_script.build_guest_script(port=9999, desktop_env="xfce")
    assert "dbus-run-session -- startxfce4" in src


def test_guest_script_has_no_python_left():
    src = desk_script.build_guest_script(port=9999, desktop_env="xfce", tunnel=True)
    assert "python3" not in src
    assert "termux_desk" not in src
    assert "auth.json" not in src


def test_guest_script_warns_when_the_cookie_file_is_missing():
    src = desk_script.build_guest_script(port=9999)
    assert '[ -f "$XAUTHORITY" ]' in src
    assert "warning: the display auth file is missing" in src


def test_guest_script_tunnel_is_upstreams_exact_ssh_line():
    plain = desk_script.build_guest_script(port=9999, display=2)
    tunneled = desk_script.build_guest_script(port=9999, display=2, tunnel=True)
    assert "ssh" not in plain
    assert (
        "ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30"
        " -R 80:localhost:9999 nokey@localhost.run" in tunneled
    )
    assert "/tmp/x11/tunnel-2.log" in tunneled


def test_tunnel_url_regex_is_upstreams_pattern():
    sample = "Warning: Permanently added. \n  https://random-name-123.lhr.life connected\n"
    match = desk_script.TUNNEL_URL_RE.search(sample)
    assert match and match.group(1) == "https://random-name-123.lhr.life"


def test_guest_script_app_mode_replaces_the_desktop():
    desktop = desk_script.build_guest_script(port=9999, desktop_env="xfce")
    assert "dbus-run-session -- startxfce4" in desktop
    app = desk_script.build_guest_script(port=9999, app_command="python3 app.py --flag 'x'")
    # A display-scoped session bus is started first; dbus-run-session is only
    # the fallback when no bus is available (so later shells share it).
    assert 'DBUS_SESSION_BUS_ADDRESS="unix:path=/tmp/x11/bus-0"' in app
    assert "dbus-run-session -- sh -c" in app
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


def test_guest_script_waits_on_the_session_not_an_x_server():
    """The session owns the script: when the app or the desktop exits, the
    guest tree exits and the manager marks the display ERROR."""
    src = desk_script.build_guest_script(port=9999)
    assert 'wait "$SESSION_PID"' in src
    assert "XVFB_PID" not in src


# ── provision (provision.py) — the guest needs dbus + ssh only ───────────────


def test_every_package_manager_gets_dbus_ssh_and_nothing_x():
    for pm, packages in desk_provision._BASE_PACKAGES.items():
        assert any(p.startswith("openssh") for p in packages), f"{pm} misses openssh"
        assert any("dbus" in p for p in packages), f"{pm} misses the session bus"
        # The X stack lives in the app now — the guest installs none of it.
        assert not any("xvfb" in p or "xauth" in p or "xclip" in p for p in packages), (
            f"{pm} still installs the guest X stack"
        )
        assert not any(p.startswith(("py3-", "python3-", "python-")) for p in packages), (
            f"{pm} still installs guest python"
        )
        # The base stays MINIMAL — the desktop-only extras live in _DESKTOP_EXTRAS:
        # without an icon theme + pixbuf + mime DB, GTK cannot load images and
        # xfce4-panel aborts (device-proven 2026-11-10). Apps don't need them.
        assert "adwaita-icon-theme" not in packages, f"{pm} base is not minimal"
        extras = desk_provision._DESKTOP_EXTRAS[pm]
        assert "adwaita-icon-theme" in extras, f"{pm} extras miss an icon theme"
        assert "shared-mime-info" in extras, f"{pm} extras miss the mime database"
        assert any("pixbuf" in p or "rsvg" in p for p in extras), f"{pm} extras miss image loaders"


def test_fedora_xfce_ships_xfsettingsd():
    """xfce4-session launches xfsettingsd; Fedora's xfce4-settings package was
    missing from the list and the session degraded to a bare WM on a black root."""
    assert "xfce4-settings" in desk_provision._DESKTOP_PACKAGES["dnf"]["xfce"]


def test_alpine_install_script_is_minimal_for_apps():
    src = desk_provision.install_script(ALPINE_CAPS, "xfce")
    for package in ("dbus", "dbus-x11", "openssh-client"):
        assert package in src
    for gone in ("xvfb", "xauth", "xclip"):
        assert gone not in src
    assert "apk add --no-cache" in src


def test_unsupported_container_names_the_reason():
    caps = {"os": {"distro_id": "mystery", "distro_like": "", "version_id": "", "pretty_name": ""}}
    assert desk_provision.unsupported_reason(caps) is not None
    assert desk_provision.package_manager_for(ALPINE_CAPS) == "apk"


# ── manager (manager.py) — in-app Xvnc, stream server, RFB wait ──────────────


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
    guest_dir = containers / "debian" / "rootfs" / "tmp" / "x11"
    guest_dir.mkdir(parents=True)
    (guest_dir / "tunnel-1.log").write_text(
        "debug1: Connection to localhost.run\nhttps://neat-word-42.lhr.life is up\n"
    )
    monkeypatch.setattr(desk_manager.storage_paths, "containers_dir", lambda: containers)

    assert desk_manager._read_tunnel_url("debian", 1) == "https://neat-word-42.lhr.life"
    assert desk_manager._read_tunnel_url("debian", 2) == ""  # no log yet — never a crash


def _stub_runtime(monkeypatch):
    """The runtime bits _spawn touches — payloads and cookie writes are
    Android-only, so tests stub the module the manager calls through."""
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "write_xauth_file",
        lambda cookie, display, path: path,
    )
    monkeypatch.setattr(desk_manager.xvnc_runtime, "ensure_xkb_dir", lambda: Path("/tmp/xkb"))
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "xvnc_command",
        lambda display, geometry, xauth, xkb, **kw: (["/bin/true", f":{display}"], {}),
    )
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "pulseaudio_command",
        lambda **kw: (["/bin/true"], {}),
    )
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "spawn",
        lambda argv, env: type("P", (), {"pid": 7, "stdout": None, "poll": lambda self: None})(),
    )


def test_spawn_passes_the_wrap_surface_into_the_script_builder(monkeypatch):
    built = {}
    manager = desk_manager.DeskManager()
    _stub_runtime(monkeypatch)
    monkeypatch.setattr(manager, "_ensure_pulseaudio", lambda **kw: None)
    monkeypatch.setattr(
        desk_manager, "build_guest_script", lambda **kw: built.update(kw) or "script"
    )
    monkeypatch.setattr(
        desk_manager,
        "_write_guest_script",
        lambda c, s, d: f"/tmp/x11/run-display-{d}.sh",
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
    # Xvnc spawned as its own process group beside the guest tree.
    assert session2._xvnc_process is not None
    assert session2._process is not None


def test_wait_xvnc_honors_stopping_as_a_quiet_cancel():
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    session.status = desk_manager.DeskStatus.STOPPING
    session._xvnc_process = type("P", (), {"poll": lambda self: 1})()
    manager._wait_xvnc(session, 0.5)  # must return silently, no ERROR
    assert session.status is desk_manager.DeskStatus.STOPPING
    assert session.error == ""


def test_wait_xvnc_fails_on_dead_x_server(monkeypatch):
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    session.status = desk_manager.DeskStatus.STARTING
    session._xvnc_process = type("P", (), {"poll": lambda self: 1, "returncode": 1})()
    monkeypatch.setattr(desk_manager, "_tcp_open", lambda port: False)
    manager._wait_xvnc(session, 0.5)
    assert session.status is desk_manager.DeskStatus.ERROR
    assert "exited" in session.error


def test_read_logs_marks_a_post_ready_crash_as_error():
    import io

    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    session.status = desk_manager.DeskStatus.RUNNING
    process = type("P", (), {"stdout": io.BytesIO(b""), "poll": lambda self: 1, "returncode": 1})()
    manager._read_logs(session, process, "guest")
    assert session.status is desk_manager.DeskStatus.ERROR
    assert "exited" in session.error


def test_read_logs_tags_xvnc_lines_and_marks_their_crash():
    import io

    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    session.status = desk_manager.DeskStatus.RUNNING
    process = type("P", (), {"stdout": io.BytesIO(b""), "poll": lambda self: 1, "returncode": 1})()
    manager._read_logs(session, process, "xvnc")
    assert session.status is desk_manager.DeskStatus.ERROR
    assert "X server" in session.error


class _FakeServer:
    """The stream server's surface as the manager drives it."""

    def __init__(self, host, port, rfb_port, code, quality=6, compression=2, **_kw):
        self.host = host
        self.port = port
        self.rfb_port = rfb_port
        self.code = code
        self.quality = quality
        self.compression = compression
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    def local_url(self):
        return f"http://127.0.0.1:{self.port}/novnc/vnc.html?code={self.code}"

    async def stop(self):
        self.stopped = True


def _stub_server(monkeypatch, manager, server_class):
    monkeypatch.setattr(desk_manager.stream_server, "DisplayStreamServer", server_class)
    monkeypatch.setattr(
        manager, "_spawn", lambda s: setattr(s, "status", desk_manager.DeskStatus.STARTING)
    )
    monkeypatch.setattr(manager, "_wait_xvnc", lambda s, t: None)


async def test_start_runs_the_server_in_process_and_stop_closes_it(monkeypatch):

    manager = desk_manager.DeskManager()
    created: list[_FakeServer] = []

    class _RecordingServer(_FakeServer):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            created.append(self)

    _stub_server(monkeypatch, manager, _RecordingServer)

    session = await manager.start("debian", display=0)

    assert created and created[-1].started
    # RFB port pairs with the display: :0 → 5900.
    assert created[-1].rfb_port == 5900
    assert len(created[-1].code) == 6
    assert session.server is created[-1]
    assert session.code == created[-1].code
    assert session.url == (
        f"http://127.0.0.1:{session.port}/novnc/vnc.html?code={created[-1].code}"
    )
    assert session.status is desk_manager.DeskStatus.RUNNING

    await manager.stop(session.key)
    assert created[-1].stopped
    assert session.server is None
    assert session.status is desk_manager.DeskStatus.IDLE


async def test_start_picks_the_lowest_free_display_globally(monkeypatch):

    manager = desk_manager.DeskManager()
    _stub_server(monkeypatch, manager, _FakeServer)

    # Display numbers are GLOBAL: Xvnc binds TCP 6000+N on the host network
    # namespace proot shares, so a second container must not reuse :0.
    s0 = await manager.start("debian", display=0)
    s1 = await manager.start("debian")
    s2 = await manager.start("alpine")
    assert (s0.display, s1.display, s2.display) == (0, 1, 2)
    assert s1.key == "debian:1"
    assert s2.key == "alpine:2"
    # Already-RUNNING key returns the existing session without starting again.
    again = await manager.start("debian", display=1)
    assert again is s1


async def test_start_failure_leaves_an_error_session_and_kills_the_groups(monkeypatch):
    """A readiness failure must never surface as RUNNING (device
    2026-11-13: the user got a "running" dead surface with the error wiped).
    start() re-checks the ERROR status, kills both process groups and
    raises; the session stays listable as failed."""
    manager = desk_manager.DeskManager()
    _stub_server(monkeypatch, manager, _FakeServer)
    killed: list[str] = []

    def _failing_wait(session, timeout):
        manager._fail(session, "the X server exited", session.log_tail)

    monkeypatch.setattr(manager, "_wait_xvnc", _failing_wait)
    monkeypatch.setattr(manager, "_kill_session", lambda s: killed.append(s.key))

    with pytest.raises(RuntimeError, match="the X server exited"):
        await manager.start("debian", display=0)

    assert killed == ["debian:0"]
    session = manager.get("debian:0")
    assert session is not None and session.status is desk_manager.DeskStatus.ERROR
    assert manager.failed() == [session]
    assert manager.visible() == []


def test_failed_rows_survive_until_dismissed():
    """ERROR is a visible state: failed() lists it (the Display tab renders
    Logs/Retry/Dismiss from it) while the running rows exclude it."""
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    session.status = desk_manager.DeskStatus.ERROR
    session.error = "the X server exited (code 1)"
    manager._sessions[session.key] = session

    assert manager.failed() == [session]
    assert manager.visible() == []
    session.status = desk_manager.DeskStatus.IDLE
    assert manager.failed() == []


def test_fail_closes_the_log_handle():
    """An ERROR session must not keep the log file pinned open (it used to
    leak until the user happened to press Stop)."""
    import io

    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0")
    closed = []

    class _Handle(io.BytesIO):
        def close(self):
            closed.append(True)
            super().close()

    session._log_file = _Handle()
    manager._fail(session, "the X server exited", deque(["boom"]))
    assert closed == [True]
    assert session._log_file is None


def test_display_logs_live_in_the_durable_data_root():
    """Upstream clear-cache empties the CACHE root — crash logs must live in
    the data root or "clear cached downloads" destroys the only evidence."""
    src = (ROOT / "src" / "services" / "desk_service" / "manager.py").read_text(encoding="utf-8")
    assert 'data_root() / "display-logs"' in src
    assert 'cache_root() / "display-logs"' not in src


def test_guest_display_env_only_for_running_displays():
    """A new shell inherits DISPLAY/XAUTHORITY only from a RUNNING display —
    STARTING/STOPPING/ERROR point nowhere, and no display means a plain shell."""
    manager = desk_manager.DeskManager()
    assert manager.guest_display_env("debian") == {}
    starting = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    starting.status = desk_manager.DeskStatus.STARTING
    manager._sessions[starting.key] = starting
    assert manager.guest_display_env("debian") == {}


def test_guest_display_env_prefers_desktop_then_lowest_display():
    """Deterministic pick (desktop-mode first, then lowest display) so a
    container with several displays still exports consistent values."""
    manager = desk_manager.DeskManager()

    def _cookie(display: int) -> None:
        path = desk_manager.xvnc_runtime.guest_cookie_path("debian", display)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"cookie")

    app_session = desk_manager.DeskSession(container="debian", key="debian:2", display=2)
    app_session.mode = "app"
    app_session.status = desk_manager.DeskStatus.RUNNING
    desktop_hi = desk_manager.DeskSession(container="debian", key="debian:1", display=1)
    desktop_hi.status = desk_manager.DeskStatus.RUNNING
    manager._sessions.update({s.key: s for s in (app_session, desktop_hi)})
    _cookie(1)
    _cookie(2)

    env = manager.guest_display_env("debian")
    assert env["DISPLAY"] == "127.0.0.1:1"  # desktop wins over the app display
    assert env["XAUTHORITY"] == "/tmp/x11/xauth-1"
    assert env["DBUS_SESSION_BUS_ADDRESS"] == "unix:path=/tmp/x11/bus-1"
    assert "PULSE_SERVER" not in env  # no daemon running in this test

    desktop_lo = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    desktop_lo.status = desk_manager.DeskStatus.RUNNING
    manager._sessions[desktop_lo.key] = desktop_lo
    _cookie(0)
    assert manager.guest_display_env("debian")["DISPLAY"] == "127.0.0.1:0"

    # Missing auth file → no env at all (XAUTHORITY would fail anyway).
    (desk_manager.xvnc_runtime.guest_cookie_path("debian", 0)).unlink()
    assert manager.guest_display_env("debian")["DISPLAY"] == "127.0.0.1:1"


def test_the_clipboard_bridge_is_gone_vnc_carries_it():
    """RFB's clipboard channel moves text BOTH ways (ServerCutText) — the old
    proot'd xclip bridge (and its W^X execve workaround) is deleted, and the
    clipboard UI is upstream's own (app/ui.js clipboard pane + paste)."""
    src = (ROOT / "src" / "services" / "desk_service" / "manager.py").read_text(encoding="utf-8")
    assert "_install_clipboard_bridge" not in src
    assert "xclip" not in src
    ui = (ROOT / "src" / "services" / "desk_service" / "novnc" / "app" / "ui.js").read_text(
        encoding="utf-8"
    )
    assert "clipboardPasteFrom" in ui
    assert "noVNC_clipboard_text" in ui


def test_guest_log_reaches_the_diagnostic_terminal_and_no_debug_paint():
    """Every guest + Xvnc log line flows into the diagnostic terminal (the
    level a technical user needs) — and the debug machinery is gone: no red
    root paint, no window-tree dump, nothing painted into the user's session."""
    src = (ROOT / "src" / "services" / "desk_service" / "manager.py").read_text(encoding="utf-8")
    assert 'logger.info("display[%s][%s] %s", session.key, kind, text)' in src
    assert "_x_diagnostic" not in src
    assert "_diagnose_later" not in src
    assert "fill_rectangle" not in src


# ── manager process paths — cleanup, audio daemon, group teardown ───────────


def _fake_process(poll_result=None, returncode=0):
    return type(
        "P",
        (),
        {"pid": 111, "stdout": None, "poll": lambda self: poll_result, "returncode": returncode},
    )()


def test_spawn_failure_kills_what_already_started(monkeypatch):
    """The guest Popen raising must not leak the X server or the audio daemon
    that _spawn already started."""
    manager = desk_manager.DeskManager()
    _stub_runtime(monkeypatch)
    killed = []

    monkeypatch.setattr(desk_manager.xvnc_runtime, "spawn", _fake_process)
    monkeypatch.setattr(
        manager,
        "_kill_session",
        lambda session: killed.append(
            [attr for attr in ("_process", "_xvnc_process") if getattr(session, attr) is not None]
        ),
    )
    monkeypatch.setattr(
        desk_manager.session_service, "command_argv", lambda **kw: ({}, ["/bin/sh", "x"])
    )
    monkeypatch.setattr(
        desk_manager.subprocess, "Popen", lambda *a, **kw: (_ for _ in ()).throw(OSError("boom"))
    )

    session = desk_manager.DeskSession(container="debian", key="debian:0", display=0, port=1)
    with pytest.raises(OSError):
        manager._spawn(session)
    assert killed and killed[0] == ["_xvnc_process"]  # Xvnc started, guest did not


def test_ensure_pulseaudio_spawns_once_and_tolerates_probe_failure(monkeypatch):
    manager = desk_manager.DeskManager()
    spawned = []
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "pulseaudio_command",
        lambda **kw: (["/bin/true"], {}),
    )
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "spawn",
        lambda argv, env: (
            spawned.append(argv[0])
            or type("P", (), {"pid": 9, "stdout": None, "poll": lambda self: None})()
        ),
    )
    monkeypatch.setattr(desk_manager.xvnc_runtime, "probe_pulseaudio", lambda: False)
    monkeypatch.setattr(desk_manager.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        desk_manager.threading,
        "Thread",
        lambda *a, **kw: type("T", (), {"start": lambda self: None})(),
    )

    manager._ensure_pulseaudio()
    manager._ensure_pulseaudio()
    assert spawned == ["/bin/true"]  # the daemon is a singleton — no double spawn
    assert manager._pulse_process is not None  # probe failure only warns

    # a daemon that cannot even spawn leaves audio disabled, never raises
    monkeypatch.setattr(
        desk_manager.xvnc_runtime,
        "spawn",
        lambda argv, env: (_ for _ in ()).throw(RuntimeError("payload missing")),
    )
    manager._pulse_process = None
    manager._ensure_pulseaudio()
    assert manager._pulse_process is None


def test_read_pulse_logs_clears_the_handle_when_the_daemon_dies():
    import io

    manager = desk_manager.DeskManager()
    process = type("P", (), {"stdout": io.BytesIO(b""), "poll": lambda self: 1, "returncode": 3})()
    manager._pulse_process = process
    manager._read_pulse_logs(process)
    assert manager._pulse_process is None


async def test_stop_stops_pulseaudio_with_the_last_session(monkeypatch):
    manager = desk_manager.DeskManager()
    _stub_server(monkeypatch, manager, _FakeServer)
    stopped = []
    monkeypatch.setattr(manager, "_stop_pulseaudio", lambda: stopped.append(True))

    session = await manager.start("debian", display=0)
    await manager.stop(session.key)
    assert stopped == [True]  # last session gone → the audio daemon goes too

    stopped.clear()
    other = await manager.start("alpine", display=1)
    await manager.start("alpine", display=2)
    await manager.stop(other.key)
    assert stopped == []  # a display still runs → the daemon stays


def test_stop_sync_sigterms_both_process_groups(monkeypatch):
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    signaled = []

    class _P:
        def __init__(self, pid: int) -> None:
            self.pid = pid
            self.poll_result = None  # still running

        def poll(self):
            return self.poll_result

        def wait(self, timeout):
            signaled.append("waited")
            return 0

    process = _P(42)
    xvnc = _P(43)
    session._process = process
    session._xvnc_process = xvnc
    monkeypatch.setattr(desk_manager.os, "killpg", lambda pid, sig: signaled.append((pid, sig)))
    manager._stop_sync(session)
    # both groups received SIGTERM (15) and were waited on
    assert signaled.count((42, 15)) == 1
    assert signaled.count((43, 15)) == 1
    assert session._process is None and session._xvnc_process is None
    assert session.status is desk_manager.DeskStatus.IDLE


def test_wait_xvnc_times_out_when_the_port_never_opens(monkeypatch):
    manager = desk_manager.DeskManager()
    session = desk_manager.DeskSession(container="debian", key="debian:0", display=0)
    session.status = desk_manager.DeskStatus.STARTING
    session._xvnc_process = _fake_process(poll_result=None)
    monkeypatch.setattr(desk_manager, "_tcp_open", lambda port: False)
    monkeypatch.setattr(desk_manager.time, "sleep", lambda s: None)
    manager._wait_xvnc(session, 0.5)
    assert session.status is desk_manager.DeskStatus.ERROR
    assert "timed out" in session.error


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


def test_desktop_view_adds_no_viewer_js_bridges():
    """The viewer IS upstream noVNC verbatim — its own toolbar carries the
    extra keys, the soft-keyboard path and the clipboard pane. The app view
    must add NO JavaScript bridges and no duplicated key strip (our old page
    had no editable element, so the Android IME could never open)."""
    src = (ROOT / "src" / "screens" / "desktop" / "__init__.py").read_text(encoding="utf-8")
    for gone in (
        "window.sendKeySym",
        "window.pasteText",
        "_KEYSYMS",
        "press_js",
        "paste_js",
        "keyboard_strip",
        "_run_js",
    ):
        assert gone not in src, gone
    # The toolbar keeps the app-level actions.
    for kept in ("Reload", "Share", "Logs", "Stop", "FULLSCREEN"):
        assert kept in src
    # Upstream's page carries the mobile keyboard mechanism we rely on.
    ui = (ROOT / "src" / "services" / "desk_service" / "novnc" / "app" / "ui.js").read_text(
        encoding="utf-8"
    )
    assert "noVNC_keyboardinput" in ui
    assert "showVirtualKeyboard" in ui


# ── UI structure pins ────────────────────────────────────────────────────────


def test_container_card_has_exactly_three_inline_actions():
    src = (ROOT / "src" / "screens" / "container_card.py").read_text(encoding="utf-8")
    assert "btn_reset" not in src
    assert "btn_remove" not in src
    assert '"Open shell"' in src
    assert "FilledTonalButton(" in src
    # The display runs in the app — the card ALWAYS opens one (app-first).
    assert '"Open display"' in src
    assert '"Install display support"' not in src


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

    class _R:
        def __init__(self, key: str) -> None:
            self.key = key
            self.container = key.split(":")[0]

    def running(self) -> list:
        return [self._R(key) for key in self._keys]

    # STARTING sessions hold the FGS too (a display takes up to 60s to come
    # up — backgrounding during that window used to kill the start).
    def starting(self) -> list:
        return []

    def visible(self) -> list:
        return self.running()


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


def test_the_mic_recorder_is_mounted_per_page_session():
    """A Flet Service registers with the page AT CONSTRUCTION: the recorder
    must be built in _mount_services (which runs on every init). Building it
    in __init__ leaves a dead registration after a warm reopen — the FGS
    keeps the process alive, main() constructs a fresh controller, and
    has_permission() failed silently (device audit 2026-11-13)."""
    src = (ROOT / "src" / "app_controller.py").read_text(encoding="utf-8")
    before_init = src.split("async def init(self)")[0]
    assert "flet_audio_recorder" not in before_init
    mount_region = src.split("def _mount_services")[1].split("async def _restore_prefs")[0]
    assert "far.AudioRecorder()" in mount_region


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
    """The two sections a display IS — GUI application (first) and Desktop
    (one app alone on :N) — with the starting card driven by observable state."""
    src = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    assert '"Desktop"' in src
    assert '"GUI application"' in src
    # The starting card reads display_status (observable), not manager state.
    assert 'st.display_status == "starting"' in src


def test_display_tab_running_section_is_mode_agnostic():
    """Running displays (desktop OR single app) surface in ONE 'Running'
    section — not split into 'Desktops'/'Apps' — and the per-container
    desktop action is right-aligned via the expanding details column
    (matching distro screen)."""
    src = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    assert '"Running"' in src
    assert '"Desktops"' not in src
    assert '"Apps"' not in src
    assert "controls=[name_text, distro_text]" in src


def test_display_stop_is_reactive_with_stopping_spinner():
    """Stop presses refresh immediately: the manager fires on_sessions_changed
    on every transition, the controller bumps state.display_sessions_rev, and
    the Display tab lists STOPPING sessions with a 'stopping…' spinner."""
    view_src = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    assert "manager.visible()" in view_src
    assert "st.display_sessions_rev" in view_src
    assert "DeskStatus.STOPPING" in view_src
    assert "stopping…" in view_src
    mgr_src = (ROOT / "src" / "services" / "desk_service" / "manager.py").read_text(
        encoding="utf-8"
    )
    assert "on_sessions_changed" in mgr_src
    assert "def visible(" in mgr_src
    assert mgr_src.count("_notify_changed()") >= 4
    ctrl_src = (ROOT / "src" / "app_controller.py").read_text(encoding="utf-8")
    assert "on_sessions_changed = self._bump_display_sessions" in ctrl_src
    state_src = (ROOT / "src" / "core" / "state.py").read_text(encoding="utf-8")
    assert "display_sessions_rev" in state_src


def test_desktop_fullscreen_has_visible_exit_fab():
    """Fullscreen hides the toolbar, so a floating exit button must stay
    visible (house rule), and a warm reopen never lands in fullscreen."""
    src = (ROOT / "src" / "screens" / "desktop" / "__init__.py").read_text(encoding="utf-8")
    assert "ft.FloatingActionButton(" in src
    assert "FULLSCREEN_EXIT_ROUNDED" in src
    assert "if not st.display_fullscreen:" in src
    assert "right=tokens.SPACE_MD" in src
    assert "kb_field" not in src  # bulky TextField input row removed
    # The custom key strip is GONE — upstream's viewer toolbar owns the keys.
    assert "keyboard_strip" not in src
    ctrl_src = (ROOT / "src" / "app_controller.py").read_text(encoding="utf-8")
    assert "state.display_fullscreen = False" in ctrl_src


def test_install_chunk_path_uses_run_task_not_raw_threadsafe():
    """Chunk callbacks must go through page.run_task so ft.context.page
    resolves (a raw call_soon_threadsafe notify raised RuntimeError — the
    99x log spam) — with no error swallowing."""
    src = (ROOT / "src" / "controller_actions" / "display_actions.py").read_text(encoding="utf-8")
    assert "self.page.run_task(_apply)" in src
    assert "call_soon_threadsafe(_apply)" not in src
    assert "_notify_install" in src and "notifications.show(id=2100" in src
    state_src = (ROOT / "src" / "core" / "state.py").read_text(encoding="utf-8")
    assert "def append(" in state_src.split("class DisplayProgress")[1]
    assert "except RuntimeError:" not in state_src
    shell_src = (ROOT / "src" / "app_shell.py").read_text(encoding="utf-8")
    assert "prog.is_running" in shell_src  # global install strip on all tabs


def test_xvnc_wheel_uses_underscore_android_platform_tags():
    """The wheel platform tag must be the underscore form pip accepts
    (android_24_arm64_v8a) — the dash form is silently skipped. All payload
    libs end in .so (never .so.8) so AGP bundles them into lib/<abi>/."""
    src = (ROOT / "scripts" / "build_flet_xvnc_wheel.py").read_text(encoding="utf-8")
    assert '"platform": "arm64_v8a"' in src
    assert '"platform": "x86_64"' in src
    assert "android_24_{spec['platform']}" in src
    # the payload rename keeps sonames matching the shipped lib*.so names
    assert "_soname_rewrites" in src
    pa_src = (ROOT / "scripts" / "build_flet_pulseaudio_wheel.py").read_text(encoding="utf-8")
    assert '"platform": "arm64_v8a"' in pa_src
    assert "module-aaudio-sink.so" in pa_src  # the Android audio modules ship


def test_novnc_is_vendored_verbatim_with_provenance():
    """The viewer IS upstream noVNC (pinned 1.7.0) vendored verbatim — vnc.html
    + app/ + core/ + vendor/ — served by the stream server, no CDN, no npm at
    build time. Deployment defaults ride upstream's own defaults.json."""
    import json

    novnc = ROOT / "src" / "services" / "desk_service" / "novnc"
    provenance = (novnc / "PROVENANCE").read_text(encoding="utf-8")
    assert "noVNC 1.7.0" in provenance
    assert "sha256" in provenance
    assert (novnc / "core" / "rfb.js").is_file()
    page = (novnc / "vnc.html").read_text(encoding="utf-8")
    assert "app/ui.js" in page  # upstream's page, unmodified
    assert (novnc / "app" / "ui.js").is_file()
    assert (novnc / "vendor" / "pako").is_dir()
    assert not (novnc / "index.html").exists()  # our hand-rolled page is gone
    defaults = json.loads((novnc / "defaults.json").read_text(encoding="utf-8"))
    assert defaults["resize"] == "remote"  # the desktop follows the phone screen
    assert defaults["reconnect"] is True


def test_stream_server_gates_both_the_page_and_the_websocket():
    """The 6-char access code gates the ENTRY page (which forwards to upstream
    vnc.html) and the RFB WebSocket itself (LAN + tunnel clients)."""
    src = (ROOT / "src" / "services" / "desk_service" / "stream_server.py").read_text(
        encoding="utf-8"
    )
    assert 'request.query.get("code", "") != self.code' in src
    assert "4401" in src
    assert "HTTPFound" in src  # `/` forwards to the upstream viewer
    assert "open_connection" in src  # the transparent RFB byte pump
    assert "send_bytes" in src


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


def test_glycin_bwrap_gets_fake_overflow_ids():
    """bwrap (glycin's image loader) reads /proc/sys/kernel/overflowuid|gid to set
    up its uid map; Android blocks both. Without the fake stubs every GTK image
    load fails and the XFCE panel aborts — the desktop stays black."""
    src = (ROOT / "src" / "services" / "session_service" / "argv.py").read_text(encoding="utf-8")
    assert "overflowuid" in src and "overflowgid" in src
    assert ":/proc/sys/kernel/{name}" in src
    assert 'write_text("65534\\n"' in src


def test_launcher_is_app_first_with_display_and_advanced_options():
    """The launcher leads with the app command (not the desktop), exposes an
    explicit display number, and keeps the full option set collapsed by default
    so non-technical users get a simple Start."""
    src = (ROOT / "src" / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    assert 'mode = {"value": "app"}' in src
    assert '"App"' in src and '"Desktop"' in src
    assert "ft.Dropdown(" in src and 'label="Display"' in src
    assert "def _collect_options(" in src
    assert '"fix_low_ports"' in src and '"shared_home"' in src
    assert "Advanced options" in src
    # the advanced section is collapsed by default
    assert "visible=False" in src


def test_display_toolbar_has_terminal_not_paste_and_inline_output_panel():
    """The toolbar's clipboard-paste shortcut is replaced by a terminal for the
    container, and the guest log is an inline collapsible panel (not a new tab)."""
    src = (ROOT / "src" / "screens" / "desktop" / "__init__.py").read_text(encoding="utf-8")
    assert "TERMINAL_ROUNDED" in src
    assert "CONTENT_PASTE_GO_ROUNDED" not in src
    assert "log_open" in src and "EXPAND_LESS_ROUNDED" in src
    assert "output_panel" in src
    state_src = (ROOT / "src" / "core" / "state.py").read_text(encoding="utf-8")
    assert "display_log_rev" in state_src


def test_settings_offer_custom_values_and_portrait():
    src = (ROOT / "src" / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    assert "_CUSTOM" in src
    assert '("portrait", "Portrait")' in src
    # RFB has no fps knob — quality + compression are the real knobs now.
    assert '"FPS"' not in src
    assert '"Compression"' in src


def test_naming_says_open_display_and_install_display_support():
    launcher = (ROOT / "src" / "screens" / "display_launcher.py").read_text(encoding="utf-8")
    card = (ROOT / "src" / "screens" / "container_card.py").read_text(encoding="utf-8")
    view = (ROOT / "src" / "screens" / "display_view.py").read_text(encoding="utf-8")
    # The install CELL keeps its name; cards always open a display (the app
    # path needs nothing installed).
    assert '"Install display support"' in launcher
    assert '"Open display"' in card and '"Open display"' in view
    assert "Install desktop" not in launcher + card + view


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
    assert "compression" in DEFAULT_DISPLAY_SETTINGS


async def test_mic_grant_asks_the_controller_recorder():
    """The recorder lives on the CONTROLLER (the page has no such attribute).
    Reading it from the page made the whole grant path dead code — the mic
    module then fails with 'Failed to initialize OpenSL ES: error 9'."""
    from controller_actions.display_actions import DisplayActions

    class _Recorder:
        asked = False

        async def has_permission(self) -> bool:
            self.asked = True
            return True

    holder = DisplayActions()
    holder.mic_recorder = _Recorder()
    await holder._ensure_mic_permission()
    assert holder.mic_recorder.asked


def test_bare_display_spawns_xvnc_without_a_guest_tree(monkeypatch, tmp_path):
    """The terminal's "Start X display" starts ONLY the X server — the caller's
    existing shell gets the env injected, so no guest session is spawned."""
    manager = desk_manager.DeskManager()
    _stub_runtime(monkeypatch)
    monkeypatch.setattr(manager, "_ensure_pulseaudio", lambda **kw: None)
    session = desk_manager.DeskSession(
        container="debian", key="debian:0", display=0, mode="display"
    )
    manager._spawn(session)
    assert session._xvnc_process is not None
    assert session._process is None  # no guest tree for a bare display
    assert session.pid is None
    env_file = (
        desk_manager.storage_paths.containers_dir() / "debian" / "rootfs" / "tmp" / "x11" / "env"
    )
    assert env_file.is_file()
    assert "export DISPLAY=127.0.0.1:0" in env_file.read_text(encoding="utf-8")


async def test_start_x_display_injects_the_env_into_the_live_shell():
    """One tap from the terminal: a bare display starts and the exports are
    written INTO the running shell's PTY (no tab switch, no new shell)."""
    from app_controller import AppController

    class _Sess:
        def __init__(self):
            self.writes: list[bytes] = []

        def write(self, data: bytes) -> None:
            self.writes.append(data)

    class _Entry:
        container = "debian"
        key = "debian"

        def __init__(self):
            self.session = _Sess()

    class _Manager:
        def __init__(self):
            self.started = None

        async def start(self, container, **kw):
            self.started = kw
            return type("S", (), {"display": 3})()

        def guest_display_env(self, container):
            return {
                "DISPLAY": "127.0.0.1:3",
                "XAUTHORITY": "/tmp/x11/xauth-3",
            }

    entry = _Entry()
    controller = object.__new__(AppController)
    controller.page = type("P", (), {"width": 800, "height": 600})()
    controller.session_manager = type("M", (), {"entries": {"debian": entry}})()
    controller.desk_manager = _Manager()
    snacks = []
    controller.show_snack = snacks.append

    await controller.start_x_display("debian")

    assert controller.desk_manager.started["bare"] is True
    written = b"".join(entry.session.writes).decode()
    assert "export DISPLAY=127.0.0.1:3" in written
    assert "export XAUTHORITY=/tmp/x11/xauth-3" in written
    assert snacks and "attached to this shell" in snacks[-1]
