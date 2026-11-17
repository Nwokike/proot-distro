"""Diagnostics text and the share/copy/report actions for the Help sheet.

Split out of the Help package's __init__ (file-size rule). The report path is
the important one: reproduce the problem, copy the diagnostics, open GitHub
Issues and paste (device feedback 2026-11-17: "how do I report this?").
"""

from __future__ import annotations

from core import tokens
from core.constants import APP_BUILD_NUMBER, APP_NAME, APP_VERSION, GITHUB_ISSUES_URL
from core.logger_handler import MemoryLogHandler
from core.state import state


def diagnostics_text() -> str:
    lines = [
        f"{APP_NAME} {APP_VERSION} (build {APP_BUILD_NUMBER})",
        f"probe: passed={state.probe_passed} · {state.probe_summary or 'n/a'}",
        f"orientation: {state.device_orientation} · keyboard inset: {state.keyboard_inset:.0f} px",
        "recent logs:",
    ]
    lines.extend(MemoryLogHandler.get_logs()[-tokens.DIAGNOSTIC_LOG_TAIL :])
    return "\n".join(lines)


def copy_diagnostics(page, methods=None) -> None:
    clipboard = getattr(page, "clipboard", None)
    if clipboard is None:
        return
    page.run_task(clipboard.set, diagnostics_text())
    if methods is not None:
        methods.show_snack("diagnostics copied to clipboard")


def share_diagnostics(page) -> None:
    share = getattr(page, "share", None)
    if share is None:
        return
    page.run_task(share.share_text, diagnostics_text(), title=f"{APP_NAME} diagnostics")


def report_problem(page, methods=None) -> None:
    """Copy the diagnostics, then open GitHub Issues: paste and send."""
    from core import shared_services

    clipboard = getattr(page, "clipboard", None)
    if clipboard is not None:
        page.run_task(clipboard.set, diagnostics_text())
    page.run_task(shared_services.launch_url, GITHUB_ISSUES_URL, page)
    if methods is not None:
        methods.show_snack("diagnostics copied. Paste them into the new GitHub issue")
