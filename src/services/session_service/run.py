"""One-shot PTY capture for guest commands: `run` (Entrypoint/Cmd) and `login -- <command>`."""

from __future__ import annotations

import threading

from .argv import Argv, Env, command_argv, run_argv
from .pty import ProotSession


def _capture(argv: Argv, env: Env, timeout: float | None, on_chunk=None) -> dict:
    """Spawn one hardened guest command on a PTY and capture its output.

    `on_chunk(bytes)` is called live as output arrives. `timeout=None` waits
    forever. Returns plain data for the UI:
    {"ok", "returncode", "output", "timed_out"}.
    """
    chunks: list[bytes] = []
    exited = threading.Event()

    def _on_bytes(data: bytes) -> None:
        chunks.append(data)
        if on_chunk is not None:
            on_chunk(data)

    def _on_exit(_rc) -> None:
        exited.set()

    session = ProotSession(argv, env, _on_bytes, _on_exit)
    session.start()
    try:
        finished = exited.wait(timeout)
        return {
            "ok": finished and session.returncode == 0,
            "returncode": session.returncode,
            "output": b"".join(chunks).decode("utf-8", "replace"),
            "timed_out": not finished,
        }
    finally:
        session.stop()


def run_capture(
    container: str,
    run_args: list[str],
    work_dir: str | None = None,
    timeout: float | None = None,
    on_chunk=None,
) -> dict:
    """Run a one-shot command via `proot-distro run` (Entrypoint/Cmd + args).

    `timeout=None` waits forever, exactly like upstream `proot-distro run`.
    """
    env, argv = run_argv(container, run_args, work_dir)
    return _capture(argv, env, timeout, on_chunk)


def command_capture(
    container: str,
    command: list[str],
    work_dir: str | None = None,
    timeout: float | None = 120.0,
    on_chunk=None,
) -> dict:
    """Run a one-shot arbitrary guest command via `login -- <command>`.

    Bounded by default (120s) because probes and installs must not hang the
    UI; pass `timeout=None` for unbounded runs like a desktop session.
    """
    env, argv = command_argv(container, command, work_dir)
    return _capture(argv, env, timeout, on_chunk)
