"""PTY process lifecycle and error propagation tests."""

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


def test_session_preexec_surfaces_controlling_tty_errors(monkeypatch):
    import fcntl

    session = session_service.ProotSession(["/bin/true"], {}, lambda _b: None)
    session._slave_fd = 9
    monkeypatch.setattr(session_service.os, "setsid", lambda: None)

    def fail_ioctl(*_args):
        raise OSError("TIOCSCTTY failed")

    monkeypatch.setattr(fcntl, "ioctl", fail_ioctl)

    with pytest.raises(OSError, match="TIOCSCTTY failed"):
        session._preexec()


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


def test_proot_session_start_prevents_fd_leak_on_popen_failure(monkeypatch):
    """If Popen fails, both master and slave fds must be closed immediately."""
    import pty

    closed_fds: list[int] = []
    monkeypatch.setattr(pty, "openpty", lambda: (101, 102))
    monkeypatch.setattr("os.close", closed_fds.append)

    def _failing_popen(*_args, **_kwargs):
        raise OSError("fork failed: out of memory")

    monkeypatch.setattr("subprocess.Popen", _failing_popen)

    session = session_service.ProotSession(["/bin/sh"], {}, lambda _b: None)
    with pytest.raises(OSError, match="fork failed"):
        session.start()

    assert 101 in closed_fds, "master_fd was leaked on Popen failure"
    assert 102 in closed_fds, "slave_fd was leaked on Popen failure"
    assert session._master_fd is None
