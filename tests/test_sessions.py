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

# Upstream prints the command wrapped with backslash-newline continuations
# (its _print_command joins them). The parser must fold them — shlex would
# otherwise turn the escaped newline into a literal "n" token.
GOLDEN_CMD_WRAPPED = (
    'env -i TERM="xterm-256color" HOME="/root" '
    + chr(92)
    + chr(10)
    + '  "/data/data/ng.kiri.prootdistro/files/usr/lib/libproot.so" '
    + chr(92)
    + chr(10)
    + "  --change-id=0:0 --rootfs=. /bin/bash -l"
    + chr(10)
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


def test_session_argv_handles_upstreams_wrapped_output(monkeypatch):
    """The real --get-proot-cmd format is backslash-newline wrapped."""
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD_WRAPPED
    )
    for key in session_service._HOST_ESSENTIALS:
        monkeypatch.delenv(key, raising=False)
    env, argv = session_service.session_argv("debian")
    assert env["TERM"] == "xterm-256color"
    assert "n" not in argv
    assert argv[0].endswith("libproot.so")
    assert argv[-2:] == ["/bin/bash", "-l"]


# ── live output forwarding (the P0: bytes only ever reached the deque) ────────


class _StubTerminal:
    """Records send_bytes calls — an explicit stub, not a MagicMock (a mock
    accepts any call, so it cannot prove the wiring exists)."""

    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send_bytes(self, data: bytes) -> None:
        self.sent.append(data)


class _FakeSession:
    def __init__(self, argv, env, on_bytes, on_exit) -> None:
        self.argv, self.env = argv, env
        self._on_bytes, self._on_exit = on_bytes, on_exit
        self.alive = True

    def start(self) -> None:
        self._on_bytes(b"prompt $ ")

    def stop(self) -> None:
        self.alive = False
        self._on_exit(0)


def test_live_output_is_forwarded_to_the_terminal(monkeypatch):
    """PTY bytes must reach the mounted terminal AND the scrollback deque —
    without the live send_bytes call the screen renders nothing after mount."""
    from services import session_manager as sm

    monkeypatch.setattr(session_service, "ProotSession", _FakeSession)
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )
    manager = sm.SessionManager()
    entry = manager.open("debian")
    stub = _StubTerminal()
    entry.mt = stub

    # The pre-mount byte (emitted by start() before entry.mt existed)
    # reaches the screen only via replay; post-mount bytes are forwarded
    # live — that distinction is exactly what this test pins.
    entry.replay(stub.send_bytes)
    assert stub.sent == [b"prompt $ "]

    # Post-mount PTY output (the reader thread's callback): live delivery.
    entry.session._on_bytes(b"hello\n")
    assert stub.sent == [b"prompt $ ", b"hello\n"]
    assert list(entry.scrollback) == [b"prompt $ ", b"hello\n"]


def test_live_output_without_a_terminal_only_feeds_scrollback(monkeypatch):
    """Before mount (mt is None) bytes must not crash — replay covers them."""
    from services import session_manager as sm

    monkeypatch.setattr(session_service, "ProotSession", _FakeSession)
    monkeypatch.setattr(
        session_service.proot_service, "get_proot_cmd", lambda container: GOLDEN_CMD
    )
    manager = sm.SessionManager()
    entry = manager.open("debian")
    entry.session._on_bytes(b"early\n")  # mt is None here
    assert list(entry.scrollback) == [b"prompt $ ", b"early\n"]


# ── the real --get-proot-cmd path (unmocked; catches both original bugs) ─────


def _hermetic_proot_distro(monkeypatch, tmp_path):
    """Fresh proot_distro bound to a tmp state tree.

    Upstream reads XDG_* at import time, so the modules are purged and the
    env set BEFORE the lazy import inside get_proot_cmd runs. Test-side
    relocation only — the app itself never patches upstream.
    """
    import sys

    root = tmp_path / "pd-root"
    # Match what proot_service.bootstrap() will export: XDG_DATA_HOME =
    # <support>/.local/share, containers under <that>/proot-distro/containers.
    data_home = root / ".local" / "share"
    (data_home / "proot-distro" / "containers").mkdir(parents=True)
    (root / ".local" / "cache").mkdir(parents=True)
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(root))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(root / ".local" / "cache"))
    fake_proot = tmp_path / "libproot.so"
    fake_proot.write_bytes(b"#!/bin/sh\nexit 0\n")
    fake_proot.chmod(0o755)
    monkeypatch.setenv("PD_PROOT_BIN", str(fake_proot))

    purged = [
        name for name in sys.modules if name == "proot_distro" or name.startswith("proot_distro.")
    ]
    for name in purged:
        monkeypatch.delitem(sys.modules, name)
    return root, fake_proot


def test_get_proot_cmd_runs_the_real_upstream_path(monkeypatch, tmp_path):
    """End-to-end through upstream's command_login — no golden-string mock.

    Catches the two historical breaks: running cli.main() off the main
    thread (SIGQUIT handler) and capturing into io.StringIO (no .buffer,
    which upstream's printer writes to).
    """
    import shutil
    import sys

    if sys.platform == "win32":
        pytest.skip("POSIX-only integration path")

    root, fake_proot = _hermetic_proot_distro(monkeypatch, tmp_path)
    from services import proot_service

    # A fake installed container: real ELF shell (the arch probe reads its
    # header), a passwd entry, a home dir.
    rootfs = root / ".local" / "share" / "proot-distro" / "containers" / "demo" / "rootfs"
    (rootfs / "bin").mkdir(parents=True)
    (rootfs / "etc").mkdir()
    (rootfs / "root").mkdir()
    shutil.copy2("/bin/sh", rootfs / "bin" / "sh")
    (rootfs / "bin" / "sh").chmod(0o755)
    (rootfs / "etc" / "passwd").write_text("root:x:0:0:root:/root:/bin/sh\n")

    line = proot_service.get_proot_cmd("demo")
    # Upstream wraps with backslash-newline continuations (same shape as
    # GOLDEN_CMD_WRAPPED); fold them before asserting.
    folded = line.replace("\\\n", " ")
    assert folded.lstrip().startswith("env")
    assert "-i" in folded
    assert str(fake_proot) in folded
    assert folded.rstrip().endswith("-l")  # the login shell, not a bare sh


def test_get_proot_cmd_reports_a_missing_container(monkeypatch, tmp_path):
    import sys

    if sys.platform == "win32":
        pytest.skip("POSIX-only integration path")

    _hermetic_proot_distro(monkeypatch, tmp_path)
    from services import proot_service

    with pytest.raises(RuntimeError):
        proot_service.get_proot_cmd("no-such-container")
