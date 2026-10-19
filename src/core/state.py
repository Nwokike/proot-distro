"""Global reactive state — every mutation re-renders subscribed components.

Views never own display data. They read this object inside `@ft.component`
trees (the `use_state(state)` subscribe pattern) and call controller methods
for user actions; the controller mutates fields here and nothing else. That
is what keeps imperative "frozen control" updates out of the codebase.
"""

from __future__ import annotations

import flet as ft


@ft.observable
class AppState:
    # Probe / environment
    probe_passed: bool = False
    probe_summary: str = ""
    probe_running: bool = False

    # Distro screen
    containers: list = None  # list[dict] — installed containers
    installing: str | None = None  # what's installing (blocks a second install)
    install_stage: str = ""
    busy_note: str = ""  # e.g. upstream reports another install holding the lock
    search_status: str = ""
    search_results: list = None  # list[dict] — Docker Hub hits

    # Settings
    storage_bytes: int = 0
    cached_count: int = 0
    cache_busy: bool = False
    docker_token: str = ""
    theme_mode: str = "system"  # "system" | "light" | "dark"
    theme_revision: int = 0  # bumped on every theme flip (re-render signal)

    # Distro screen hints card (CollabShell-style; dismissible)
    hints_dismissed: bool = False

    def __init__(self):
        self.containers = []
        self.search_results = []


state = AppState()
