"""Guest D-Bus notifications → Android notifications (best effort).

Guest apps (Electron, browsers, GTK/Qt apps) publish to
`org.freedesktop.Notifications` on the per-display session bus. Instead of
shipping a notification daemon, the display script starts `dbus-monitor`
watching that interface and writes to `/tmp/x11/notify-<display>.log`; the
manager tails it and forwards each `Notify` call to Android through the app's
notification service (owner request 2026-11-17: guest notifications should
feel native).

This is deliberately best-effort and side-effect free: no daemon is installed,
nothing is required in the guest, and a missing `dbus-monitor` simply means no
forwarding. Only the five leading Notify arguments are parsed (app name,
replaces id, icon, summary, body) — enough to build a native notification.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

NOTIFY_LOG_NAME = "notify-{display}.log"
_METHOD_MARK = "member=Notify"


class NotifyStreamParser:
    """Turn dbus-monitor's text stream into (app, summary, body) triples.

    dbus-monitor prints a `method call … member=Notify` header followed by one
    line per argument. The first five arguments of Notify are, in order:
    app name (string), replaces id (uint32), app icon (string), summary
    (string), body (string). Anything after them (actions, hints, timeout) is
    ignored.
    """

    def __init__(self) -> None:
        self._active = False
        self._args: list[object] = []

    def feed_line(self, line: str) -> tuple[str, str, str] | None:
        stripped = line.strip()
        if "method call" in line and _METHOD_MARK in line:
            self._active = True
            self._args = []
            return None
        if not self._active or not stripped:
            return None
        value = _parse_arg(stripped)
        if value is _SKIP:
            return None
        self._args.append(value)
        if len(self._args) < 5:
            return None
        self._active = False
        app = _as_text(self._args[0])
        summary = _as_text(self._args[3])
        body = _as_text(self._args[4])
        self._args = []
        if not summary and not body:
            return None
        return app, summary, body


_SKIP = object()


def _parse_arg(line: str) -> object:
    if line.startswith("string "):
        return _unquote(line[len("string ") :])
    if line.startswith("uint32 "):
        try:
            return int(line[len("uint32 ") :].strip())
        except ValueError:
            return _SKIP
    if line.startswith(("array ", "struct {", "variant ", "int32 ", "boolean ")):
        # An unexpected shape means the block is not a Notify we understand.
        return _SKIP
    return _SKIP


def _unquote(raw: str) -> str:
    """dbus-monitor prints C-style quoted strings (\\" \\\\ \\n …)."""
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
            out.append(mapping.get(nxt, nxt))
            index += 2
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _as_text(value: object) -> str:
    return str(value) if isinstance(value, str) else ""
