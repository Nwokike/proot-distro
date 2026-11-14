"""Spawn helper and the daemon health probe."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def spawn(argv: list[str], env: dict[str, str]) -> subprocess.Popen:
    """One payload process in its own group (the desk manager kills groups)."""
    return subprocess.Popen(  # noqa: S603 - our own pinned payload binaries
        argv,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
        start_new_session=True,
    )
