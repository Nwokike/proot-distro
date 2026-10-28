"""Output capture used by the proot-distro command facade."""

from __future__ import annotations

import io


class _LineTee(io.TextIOBase):
    """A stderr stand-in that forwards each line to `on_line` as it is
    written AND keeps the text for the final Outcome.

    stdlib capture only — this is exactly `redirect_stderr` with a live hook,
    not a patch of anything upstream."""

    def __init__(self, on_line):
        self._on_line = on_line
        self._buf = io.StringIO()

    def write(self, data: str) -> int:
        self._buf.write(data)
        if data.strip():
            for line in data.splitlines():
                if line.strip():
                    self._on_line(line)
        return len(data)

    def flush(self) -> None:  # pragma: no cover - trivial
        return None

    def getvalue(self) -> str:
        return self._buf.getvalue()


class _CapturedStdout:
    """sys.stdout stand-in carrying the `.buffer` upstream's printer writes to.

    login/__init__.py prints `--get-proot-cmd` output via
    `sys.stdout.buffer.write(...)`; io.StringIO has no `.buffer`, which made
    the previous capture raise AttributeError on every session open.
    """

    def __init__(self) -> None:
        self.buffer = io.BytesIO()

    def write(self, data: str) -> int:  # upstream writes through .buffer
        return self.buffer.write(data.encode("utf-8", errors="replace"))

    def flush(self) -> None:  # pragma: no cover - trivial
        return None

    @property
    def value(self) -> str:
        return self.buffer.getvalue().decode("utf-8", errors="replace")
