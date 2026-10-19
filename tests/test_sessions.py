"""Session contract: upstream's argv parsing, the PTY wrapper, the manager.

Offline: no device, no network, no proot binary. The argv parser is pinned
against a captured `--get-proot-cmd` line (the format upstream prints), and
the PTY is exercised against a fake process.
"""

from __future__ import annotations

import pytest

from services import session_service

# A captured upstream `--get-proot-cmd` line (env -i assignments, then the
# proot argv, then the login shell). The real output wraps with backslashes;
# shlex handles that.
GOLDEN_CMD = (
    'env -i TERM="xterm-256color" HOME="/root" PATH="/usr/bin:/bin" '
    'LD_LIBRARY_PATH="/data/data/ng.kiri.prootdistro/files/usr/lib" '
    '"/data/data/ng.kiri.prootdistro/files/usr/lib/libproot.so" '
    "--change-id=0:0 --rootfs=. --cwd=/root --bind=/dev --bind=/proc "
    "--bind=/sys /bin/bash -l"
)


def test_session_argv_parses_env_and_command(monkeypatch):
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )
    # The host essentials are merged over the guest env — clear them so the
    # parse is deterministic (CI runners set LD_LIBRARY_PATH themselves).
    for key in session_service._HOST_ESSENTIALS:
        monkeypatch.delenv(key, raising=False)
    env, argv = session_service.session_argv("debian")

    assert env["TERM"] == "xterm-256color"
    assert env["HOME"] == "/root"
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["LD_LIBRARY_PATH"].endswith("/files/usr/lib")
    assert argv[0].endswith("libproot.so")
    assert "--change-id=0:0" in argv
    assert argv[-2:] == ["/bin/bash", "-l"]


def test_session_argv_merges_the_host_essentials(monkeypatch):
    """Proot needs LD_LIBRARY_PATH/PROOT_LOADER; upstream's env is clean."""
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )
    monkeypatch.setenv("LD_LIBRARY_PATH", "/data/data/app/files/usr/lib")
    monkeypatch.setenv("PROOT_LOADER", "/data/data/app/files/usr/lib/libproot-loader.so")
    env, _argv = session_service.session_argv("debian")
    assert env["LD_LIBRARY_PATH"] == "/data/data/app/files/usr/lib"
    assert env["PROOT_LOADER"].endswith("libproot-loader.so")


def test_session_argv_rejects_garbage(monkeypatch):
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: "not-a-command"
    )
    with pytest.raises(RuntimeError):
        session_service.session_argv("debian")


def test_session_argv_rejects_empty_command(monkeypatch):
    monkeypatch.setattr(session_service.proot_service, "get_proot_cmd", lambda c: "env -i")
    with pytest.raises(RuntimeError):
        session_service.session_argv("debian")


class _FakeProcess:
    def __init__(self):
        self.terminated = False
        self.returncode = None

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode


def test_session_write_and_resize_tolerate_a_dead_session():
    received: list[bytes] = []
    session = session_service.ProotSession(["/bin/true"], {}, received.append)
    session.write(b"hello")  # no master fd yet: a no-op, never a crash
    session.resize(80, 24)
    assert received == []


def test_session_stop_is_safe_without_a_process():
    session = session_service.ProotSession(["/bin/true"], {}, lambda _b: None)
    session.stop()
    assert session.alive is False


def test_session_manager_keeps_one_entry_per_container(monkeypatch):
    from services import session_manager as sm

    manager = sm.SessionManager()
    entry = manager.entry("debian")
    assert manager.entry("debian") is entry
    assert "debian" in manager.entries

    other = manager.entry("ubuntu")
    assert other is not entry


def test_session_manager_caps_concurrent_sessions():
    from services import session_manager as sm

    manager = sm.SessionManager()
    for index in range(sm.MAX_CONCURRENT_SESSIONS):
        manager.entry(f"c{index}")
    with pytest.raises(RuntimeError):
        manager.entry("one-too-many")


def test_session_entry_replay_sends_the_buffer_in_order():
    from services import session_manager as sm

    entry = sm.SessionEntry("debian")
    entry.feed(b"a")
    entry.feed(b"b")
    sent: list[bytes] = []
    entry.replay(sent.append)
    assert sent == [b"a", b"b"]
