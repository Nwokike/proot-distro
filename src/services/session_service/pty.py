"""ProotSession — one guest process on a PTY (device-proven Popen path, D-028)."""

from __future__ import annotations

import errno
import logging
import os
import signal
import struct
import subprocess
import threading
from collections.abc import Callable

from .argv import Argv, Env

logger = logging.getLogger(__name__)


class ProotSession:
    """One guest process on a PTY with controlling TTY.

    Spawn is the M0-spike-proven shape (git@f99c198, D-016.3/D-023.1, ran
    `apt update` on the owner's phone): `subprocess.Popen` on the slave fd
    with `preexec_fn` doing `os.setsid()` + `TIOCSCTTY`. `os.posix_spawn`
    does NOT exist on the Android python-build ("module 'os' has no
    attribute 'posix_spawn'" on device — D-028), so Popen is the only
    working path there. setsid makes the child its own process-group
    leader, so killpg(pid) remains the job-control path.
    """

    def __init__(
        self,
        argv: Argv,
        env: Env,
        on_bytes: Callable[[bytes], None],
        on_exit: Callable[[int | None], None] | None = None,
    ):
        self._argv = argv
        self._env = env
        self._on_bytes = on_bytes
        self._on_exit = on_exit
        self._master_fd: int | None = None
        self._slave_fd: int | None = None
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self.returncode: int | None = None

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _preexec(self) -> None:
        """Child process setup: own session + controlling TTY (proven in M0 spike-6)."""
        os.setsid()
        if self._slave_fd is not None:
            import fcntl
            import termios

            fcntl.ioctl(self._slave_fd, termios.TIOCSCTTY, 0)

    def send_signal(self, sig: int) -> None:
        """Deliver *sig* to the session's whole process group.

        The child setsids in _preexec, so its pid is its group leader and
        killpg reaches proot and every guest process without touching ours.
        """
        process = self._process
        if process is None or process.poll() is not None:
            return
        self._signal_process_group(process, sig)

    @staticmethod
    def _signal_process_group(process: subprocess.Popen, sig: int) -> None:
        """killpg first; fall back to the single pid when the group is gone.
        stop() uses this directly — it clears _process before signaling, so
        send_signal's None check must not gate it."""
        try:
            os.killpg(process.pid, sig)
        except OSError:
            try:
                os.kill(process.pid, sig)
            except OSError:
                pass

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("session already started")
        import pty

        master_fd, slave_fd = pty.openpty()
        self._slave_fd = slave_fd
        try:
            self._process = subprocess.Popen(  # noqa: S603 - argv from upstream's printed login line
                self._argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                preexec_fn=self._preexec,
                env=self._env,
            )
        except Exception:
            self._slave_fd = None
            try:
                os.close(slave_fd)
            except OSError as exc:
                logger.debug("slave fd already closed: %r", exc)
            try:
                os.close(master_fd)
            except OSError as exc:
                logger.debug("master fd already closed: %r", exc)
            raise
        self._slave_fd = None
        os.close(slave_fd)  # the child holds it as 0/1/2
        self._master_fd = master_fd

        def _read_loop() -> None:
            master_fd = self._master_fd
            if master_fd is None:
                return
            try:
                while True:
                    process = self._process
                    if process is None:
                        break
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError as exc:
                        if exc.errno == errno.EIO or (
                            exc.errno == errno.EBADF and self._master_fd is None
                        ):
                            break
                        raise  # unexpected read error — fall through to the exit path
                    if data:
                        self._on_bytes(data)
                    else:
                        break
            except Exception as exc:
                # An unexpected read failure must not kill the thread silently:
                # without this, returncode/_on_exit never fire and the shell
                # looks alive forever (ghost tab, FGS stuck on).
                logger.warning("pty read loop failed: %r", exc)
            process = self._process
            self.returncode = process.poll() if process else None
            if self._on_exit is not None:
                self._on_exit(self.returncode)

        self._reader = threading.Thread(target=_read_loop, daemon=True)
        self._reader.start()

    def write(self, payload: bytes) -> None:
        master_fd = self._master_fd
        if master_fd is None or not payload:
            return
        total = len(payload)
        offset = 0
        while offset < total:
            written = os.write(master_fd, payload[offset:])
            if written <= 0:
                raise OSError("PTY write returned no bytes")
            offset += written

    def resize(self, cols: int, rows: int) -> None:
        if self._master_fd is None or cols <= 0 or rows <= 0:
            return
        import fcntl
        import termios

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def stop(self) -> None:
        process, self._process = self._process, None
        master_fd, self._master_fd = self._master_fd, None
        # Terminate the guest FIRST: if the fd close raises (raced close),
        # teardown must still happen — never let an EBADF skip the kill.
        # The GROUP signal path (send_signal → killpg) is mandatory here:
        # proot SIG_IGNs SIGTERM, and SIGKILL on the leader alone orphans the
        # whole guest tree ("the whole guest running, reparented to init" —
        # upstream kill.py). Leader-only terminate()/kill() is wrong.
        if process is not None and process.poll() is None:
            self._signal_process_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self._signal_process_group(process, signal.SIGKILL)
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    logger.warning("guest process group refused to die")
            self.returncode = process.poll()
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError as exc:
                logger.debug("master fd already closed: %r", exc)
        reader, self._reader = self._reader, None
        # Thread-safe stop: if stop() runs ON the reader thread itself (guest
        # exit path), joining itself would deadlock the app — skip the join.
        if reader is not None and reader.is_alive() and reader is not threading.current_thread():
            reader.join(timeout=1.0)
