"""Sessions — argv from upstream, PTY spawn, one-shot capture.

Split into argv/pty/run submodules; re-exported here so
`from services import session_service` keeps working (tests also reach
`session_service.os` / `session_service.subprocess` for monkeypatching).
"""

import os
import subprocess

from services import proot_service

from .argv import (
    _ASSIGNMENT_RE,
    _HOST_ESSENTIALS,
    Argv,
    Env,
    _harden_session,
    _parse_proot_cmd_line,
    run_argv,
    session_argv,
)
from .pty import ProotSession
from .run import run_capture

__all__ = [
    "_ASSIGNMENT_RE",
    "_HOST_ESSENTIALS",
    "Argv",
    "Env",
    "ProotSession",
    "_harden_session",
    "_parse_proot_cmd_line",
    "os",
    "proot_service",
    "run_argv",
    "run_capture",
    "session_argv",
    "subprocess",
]
