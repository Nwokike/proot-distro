"""PTY process lifecycle and error propagation tests."""

from pathlib import Path

import pytest

from services import session_service


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


def test_session_spawn_uses_the_device_proven_popen_path(monkeypatch):
    """Sessions spawn via subprocess.Popen on the PTY slave with preexec_fn
    (setsid + TIOCSCTTY) — the M0-spike-proven shape (git@f99c198). The
    Android python-build has NO os.posix_spawn (D-028), so Popen is the only
    working path on device; the source must not reference posix_spawn."""
    import pty

    monkeypatch.setattr(pty, "openpty", lambda: (101, 102))
    monkeypatch.setattr("os.close", lambda fd: None)
    monkeypatch.setattr("os.read", lambda fd, n: b"")

    captured = {}

    class _PopenStub(_FakeProcess):
        pid = 4242

        def __init__(self, argv, **kwargs):
            super().__init__()
            captured["argv"] = argv
            captured["kwargs"] = kwargs

    monkeypatch.setattr(session_service.subprocess, "Popen", _PopenStub)

    session = session_service.ProotSession(["/bin/true"], {"A": "1"}, lambda _b: None)
    session.start()
    assert session._process is not None and session._process.pid == 4242
    assert captured["argv"] == ["/bin/true"]
    kw = captured["kwargs"]
    assert kw["stdin"] == 102 and kw["stdout"] == 102 and kw["stderr"] == 102
    assert kw["close_fds"] is True
    assert callable(kw["preexec_fn"])
    assert kw["env"] == {"A": "1"}
    assert session._master_fd == 101
    session.stop()

    pkg = Path(__file__).resolve().parents[1] / "src" / "services" / "session_service"
    src = "\n".join(p.read_text(encoding="utf-8") for p in sorted(pkg.glob("*.py")))
    assert "os.posix_spawn(" not in src, (
        "session_service must not call os.posix_spawn — absent on Android python-build"
    )


def test_session_pty_roundtrip():
    """Real spawn through Popen: /bin/cat echoes the PTY, SIGTERM ends it."""
    import signal
    import time

    received: list[bytes] = []
    session = session_service.ProotSession(["/bin/cat"], {}, received.append)
    session.start()
    try:
        session.write(b"hello-pty\n")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(b"hello-pty" in c for c in received):
            time.sleep(0.02)
        assert any(b"hello-pty" in c for c in received), "no PTY echo back"
        assert session.alive
        session.send_signal(signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and session.alive:
            time.sleep(0.02)
        assert not session.alive, "SIGTERM via killpg did not end the session"
    finally:
        session.stop()


def test_session_write_surfaces_pty_errors(monkeypatch):
    session = session_service.ProotSession(["/bin/true"], {}, lambda _b: None)
    session._master_fd = 9

    def fail_write(*_args):
        raise OSError("PTY write failed")

    monkeypatch.setattr(session_service.os, "write", fail_write)

    with pytest.raises(OSError, match="PTY write failed"):
        session.write(b"input")


def test_session_resize_surfaces_pty_errors(monkeypatch):
    import fcntl

    session = session_service.ProotSession(["/bin/true"], {}, lambda _b: None)
    session._master_fd = 9

    def fail_ioctl(*_args):
        raise OSError("TIOCSWINSZ failed")

    monkeypatch.setattr(fcntl, "ioctl", fail_ioctl)

    with pytest.raises(OSError, match="TIOCSWINSZ failed"):
        session.resize(80, 24)


def test_proot_session_writes_complete_payload_in_chunks(monkeypatch):
    """write() must loop until all bytes are written even on partial writes."""
    written_chunks: list[bytes] = []

    def _fake_write(fd, buf):
        # Simulate partial write consuming max 2 bytes per call
        chunk = buf[:2]
        written_chunks.append(chunk)
        return len(chunk)

    monkeypatch.setattr("os.write", _fake_write)
    session = session_service.ProotSession(["/bin/sh"], {}, lambda _b: None)
    session._master_fd = 999  # simulate started session
    session.write(b"hello")
    assert b"".join(written_chunks) == b"hello"
    assert len(written_chunks) == 3  # b"he", b"ll", b"o"


def test_proot_session_stop_escalates_to_kill(monkeypatch):
    """When terminate() does not stop the process within 2s, kill() must be called."""

    class _StubProcess:
        def __init__(self):
            self.terminated = False
            self.killed = False
            self._waits = 0

        def poll(self):
            return -9 if self.killed else None

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def wait(self, timeout=None):
            self._waits += 1
            if self._waits == 1:
                import subprocess

                raise subprocess.TimeoutExpired(["proc"], timeout)
            return -9

    proc = _StubProcess()
    session = session_service.ProotSession(["/bin/sh"], {}, lambda _b: None)
    session._process = proc
    session._master_fd = 999

    closed_fds: list[int] = []
    monkeypatch.setattr("os.close", closed_fds.append)

    session.stop()
    assert proc.terminated is True
    assert proc.killed is True
    assert 999 in closed_fds
    assert session.returncode == -9


def test_proot_session_start_prevents_fd_leak_on_spawn_failure(monkeypatch):
    """If Popen fails, both master and slave fds must be closed immediately."""
    import pty

    closed_fds: list[int] = []
    monkeypatch.setattr(pty, "openpty", lambda: (101, 102))
    monkeypatch.setattr("os.close", closed_fds.append)

    def _failing_spawn(*_args, **_kwargs):
        raise OSError("spawn failed: out of memory")

    monkeypatch.setattr(session_service.subprocess, "Popen", _failing_spawn)

    session = session_service.ProotSession(["/bin/sh"], {}, lambda _b: None)
    with pytest.raises(OSError, match="spawn failed"):
        session.start()

    assert 101 in closed_fds, "master_fd was leaked on spawn failure"
    assert 102 in closed_fds, "slave_fd was leaked on spawn failure"
    assert session._master_fd is None
    assert session._process is None
