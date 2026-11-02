"""One-shot PTY capture for `proot-distro run`."""

from __future__ import annotations

import threading

from .argv import run_argv
from .pty import ProotSession


def run_capture(
    container: str,
    run_args: list[str],
    work_dir: str | None = None,
    timeout: float = 120.0,
    on_chunk=None,
) -> dict:
    """Run a one-shot command inside a container on a PTY and capture its output.

    `on_chunk(bytes)` is called live as output arrives. Returns plain data for
    the UI: {"ok", "returncode", "output", "timed_out"}.
    """
    env, argv = run_argv(container, run_args, work_dir)
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
