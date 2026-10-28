"""Sessions — the real login-shell argv from upstream, and the PTY that runs it.

`session_argv` asks upstream itself: `proot-distro login <c> --get-proot-cmd`
prints the complete `env -i … <proot args> …` line and exits 0. We run it
in-process (on Android `sys.executable` is the Flutter host, so a subprocess
is impossible — M0 G1b) and parse that one public output. Nothing about the
argv is reimplemented or hardcoded, so an upstream bump flows through.

`ProotSession` is the PTY port of the flet-terminal example: openpty + Popen
on the slave fd with controlling TTY (`TIOCSCTTY`), a blocking read thread that
hands bytes to `on_bytes`, and TIOCSWINSZ resize.
"""

from __future__ import annotations

import errno
import logging
import os
import platform
import re
import shlex
import struct
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from services import proot_service

logger = logging.getLogger(__name__)

Env = dict[str, str]
Argv = list[str]

_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Proot's own host-side essentials. Upstream's printed env is a clean `env -i`
# set (it inherits only Android system vars, and only on Termux), so the loader
# paths our probe staged would be dropped. The M0 spike merged them the same
# way; without them proot cannot find libtalloc/libandroid-shmem or its loader.
_HOST_ESSENTIALS = ("LD_LIBRARY_PATH", "PROOT_LOADER", "PROOT_TMP_DIR")


def _harden_session(env: Env, argv: Argv, container: str) -> tuple[Env, Argv]:
    """Harden session with the verified Android Termux extensions and bindings from M0 spike."""
    if not argv:
        return env, argv

    # Locate rootfs from --rootfs argument
    rootfs_path: Path | None = None
    for token in argv:
        if token.startswith("--rootfs="):
            raw = token[len("--rootfs=") :]
            if raw != ".":
                rootfs_path = Path(raw)
            break

    # If rootfs was relative or missing, query proot_service storage
    if rootfs_path is None or not rootfs_path.is_dir():
        from core import storage_paths

        candidate = (
            storage_paths.xdg_data_home() / "proot-distro" / "containers" / container / "rootfs"
        )
        if candidate.is_dir():
            rootfs_path = candidate

    # Ensure shm and l2s directories on host filesystem
    shm_bind: str | None = None
    if rootfs_path and rootfs_path.is_dir():
        shm = rootfs_path / "tmp"
        shm.mkdir(parents=True, exist_ok=True)
        os.chmod(shm, 0o1777)  # noqa: S103 - sticky bit required for /dev/shm
        shm_bind = f"--bind={shm}:/dev/shm"

        l2s = rootfs_path / ".l2s"
        l2s.mkdir(parents=True, exist_ok=True)
        env["PROOT_L2S_DIR"] = str(l2s)

    # Hardened Android extensions (device-proven in M0 spike)
    # Only injected before the inner guest command on Android
    inner_idx = len(argv)
    for idx, arg in enumerate(argv[1:], start=1):
        if not arg.startswith("-"):
            inner_idx = idx
            break

    head = argv[:inner_idx]
    tail = argv[inner_idx:]

    def _add_if_missing(flag: str) -> None:
        if flag not in head:
            head.append(flag)

    is_android = bool(os.environ.get("ANDROID_NATIVE_LIBRARY_DIR") or Path("/data/app").exists())
    if is_android:
        _add_if_missing("--kill-on-exit")
        _add_if_missing("--link2symlink")
        _add_if_missing("--sysvipc")
        _add_if_missing("-L")
        _add_if_missing("-0")  # --no-new-privs: prevent privilege escalation on Android

        uname_m = platform.machine() or "aarch64"
        kernel_fake = f"--kernel-release=\\Linux\\localhost\\{platform.release()}\\#1 SMP PREEMPT_DYNAMIC Fri, 10 Oct 2025 00:00:00 +0000\\{uname_m}\\localdomain\\-1\\"
        if not any(a.startswith("--kernel-release=") for a in head):
            head.append(kernel_fake)

        # Standard devices & stdio streams required by proot on Android
        _add_if_missing("--bind=/dev/urandom:/dev/random")
        _add_if_missing("--bind=/proc/self/fd:/dev/fd")
        _add_if_missing("--bind=/proc/self/fd/0:/dev/stdin")
        _add_if_missing("--bind=/proc/self/fd/1:/dev/stdout")
        _add_if_missing("--bind=/proc/self/fd/2:/dev/stderr")

        if shm_bind:
            _add_if_missing(shm_bind)

    env.setdefault("TERM", "xterm-256color")
    env.setdefault("COLORTERM", "truecolor")

    return env, head + tail


def session_argv(container: str) -> tuple[Env, Argv]:
    """The guest session's (env, argv) exactly as upstream builds it, hardened with M0 spike flags."""
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

    env, argv = _harden_session(env, argv, container)
    return env, argv


class ProotSession:
    """One interactive guest shell on a PTY with controlling TTY."""

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

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("session already started")
        import pty

        master_fd, slave_fd = pty.openpty()
        self._slave_fd = slave_fd
        try:
            self._process = subprocess.Popen(  # noqa: S603 - argv from upstream's login
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
                except OSError as exc:
                    if exc.errno == errno.EIO or (
                        exc.errno == errno.EBADF and self._master_fd is None
                    ):
                        break
                    raise
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
        if master_fd is not None:
            os.close(master_fd)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)
            self.returncode = process.poll()
        reader, self._reader = self._reader, None
        if reader is not None and reader.is_alive():
            reader.join(timeout=1.0)
