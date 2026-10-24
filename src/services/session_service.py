"""Sessions — the real login-shell argv from upstream, and the PTY that runs it.

`session_argv` asks upstream itself: `proot-distro login <c> --get-proot-cmd`
prints the complete `env -i … <proot args> …` line and exits 0. We run it
in-process (on Android `sys.executable` is the Flutter host, so a subprocess
is impossible — M0 G1b) and parse that one public output. Nothing about the
argv is reimplemented or hardcoded, so an upstream bump flows through.

`ProotSession` is the PTY port of the flet-terminal example: openpty + Popen
on the slave fd, a blocking read thread that hands bytes to `on_bytes`, and
TIOCSWINSZ resize.
"""

from __future__ import annotations

import contextlib
import os
import re
import shlex
import struct
import subprocess
import threading
from collections.abc import Callable

from services import proot_service

Env = dict[str, str]
Argv = list[str]

_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Proot's own host-side essentials. Upstream's printed env is a clean `env -i`
# set (it inherits only Android system vars, and only on Termux), so the loader
# paths our probe staged would be dropped. The M0 spike merged them the same
# way; without them proot cannot find libtalloc/libandroid-shmem or its loader.
_HOST_ESSENTIALS = ("LD_LIBRARY_PATH", "PROOT_LOADER", "PROOT_TMP_DIR")


def session_argv(container: str) -> tuple[Env, Argv]:
    """The guest session's (env, argv) exactly as upstream builds it."""
    line = proot_service.get_proot_cmd(container)
    # Upstream prints the command wrapped with backslash-newline continuations;
    # shlex would read the escaped newline as a literal "n", so the
    # continuations are folded into spaces before splitting.
    line = line.replace(chr(92) + "\r\n", " ").replace(chr(92) + "\n", " ")
    tokens = shlex.split(line)
    if not tokens or tokens[0] != "env":
        raise RuntimeError(
            f"unexpected --get-proot-cmd output (expected 'env -i …'): {line[:200]!r}"
        )
    rest = tokens[1:]
    if rest and rest[0] == "-i":
        rest = rest[1:]
    env: Env = {}
    split_at = len(rest)
    for position, token in enumerate(rest):
        if not _ASSIGNMENT_RE.match(token):
            split_at = position
            break
        key, _, value = token.partition("=")
        env[key] = value
    argv = rest[split_at:]
    if not argv:
        raise RuntimeError(f"--get-proot-cmd printed no command: {line[:200]!r}")
    for key in _HOST_ESSENTIALS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env, argv


class ProotSession:
    """One interactive guest shell on a PTY."""

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
        self._process: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self.returncode: int | None = None

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("session already started")
        import pty

        master_fd, slave_fd = pty.openpty()
        try:
            self._process = subprocess.Popen(  # noqa: S603 - argv from upstream's login
                self._argv,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
                start_new_session=True,
                env=self._env,
            )
        except Exception:
            with contextlib.suppress(OSError):
                os.close(slave_fd)
            with contextlib.suppress(OSError):
                os.close(master_fd)
            raise
        os.close(slave_fd)
        self._master_fd = master_fd

        def _read_loop() -> None:
            master_fd = self._master_fd
            if master_fd is None:
                return
            while True:
                process = self._process
                if process is None:
                    break
                try:
                    data = os.read(master_fd, 4096)
                except OSError, ValueError:
                    break
                if data:
                    self._on_bytes(data)
                else:
                    break
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
            try:
                written = os.write(master_fd, payload[offset:])
                if written <= 0:
                    break
                offset += written
            except OSError, ValueError:
                break

    def resize(self, cols: int, rows: int) -> None:
        if self._master_fd is None or cols <= 0 or rows <= 0:
            return
        with contextlib.suppress(Exception):
            import fcntl
            import termios

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)

    def stop(self) -> None:
        process, self._process = self._process, None
        reader, self._reader = self._reader, None
        if self._master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(self._master_fd)
            self._master_fd = None
        if process is not None and process.poll() is None:
            with contextlib.suppress(Exception):
                process.terminate()
            try:
                process.wait(timeout=2.0)
            except Exception:
                with contextlib.suppress(Exception):
                    process.kill()
                with contextlib.suppress(Exception):
                    process.wait(timeout=1.0)
        if process is not None:
            self.returncode = process.poll()
        if reader is not None and reader.is_alive():
            with contextlib.suppress(Exception):
                reader.join(timeout=1.0)

    def __enter__(self) -> ProotSession:
        self.start()
        return self

    def __exit__(self, *_exc) -> None:
        self.stop()
