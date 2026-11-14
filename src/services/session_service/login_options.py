"""Login/run option parsing shared by the shell dialog and the display sheet.

Both surfaces collect the same upstream options (env lines, bind lines) and
used to validate them with two copies of the same rules; a typo must surface
there, not as a generic failure after a full proot attempt.
"""

from __future__ import annotations

import re

_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_BAD_BIND_CHARS = ("\n", "\r", "\x00")


def lines(value: str | None) -> list[str]:
    """Non-empty, stripped lines from a multiline field."""
    return [line.strip() for line in (value or "").splitlines() if line.strip()]


def parse_env_bind(
    env_text: str | None, bind_text: str | None
) -> tuple[list[str], list[str], str | None]:
    """(env_lines, bind_lines, error) — error is a user-facing sentence."""
    env_lines = lines(env_text)
    for line in env_lines:
        if not _ENV_RE.match(line):
            return [], [], f"bad env line (need VAR=VALUE): {line}"
    bind_lines = lines(bind_text)
    for line in bind_lines:
        if any(char in line for char in _BAD_BIND_CHARS):
            return [], [], f"bad bind line: {line}"
    return env_lines, bind_lines, None
