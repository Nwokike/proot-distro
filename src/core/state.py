"""Observable state — every mutation re-renders subscribed views."""

from __future__ import annotations

import flet as ft


@ft.observable
class AppState:
    # Probe / environment
    probe_passed: bool = False
    probe_summary: str = ""
    probe_running: bool = False
    # Why data is missing/empty when it is — failures are shown, never swallowed.
    data_note: str = ""

    # Distro screen
    containers: list = None  # list[dict] — installed containers
    installing: str | None = None  # what's installing (blocks a second install)
    install_stage: str = ""
    busy_note: str = ""  # e.g. upstream reports another install holding the lock
    search_status: str = ""
    search_results: list = None  # list[dict] — Docker Hub hits

    # Settings & Storage
    storage_bytes: int = 0
    cached_count: int = 0
    cached_images: list = None  # list[dict] — cached OCI images
    busy_locks: list = None  # list[str] — locks held by active operations
    cache_busy: bool = False
    docker_token: str = ""
    theme_mode: str = "system"  # "system" | "light" | "dark"
    theme_revision: int = 0  # bumped on every theme flip (re-render signal)

    # Distro screen hints card (CollabShell-style; dismissible)
    hints_dismissed: bool = False
    apt_note_dismissed: bool = False
    terminal_fullscreen: bool = False

    # First run: the onboarding deck shows until it is dismissed once.
    onboarding_done: bool = False

    # Ads: the UMP consent verdict — banners and interstitials gate on it,
    # so the first render can never request an ad before consent resolves.
    can_request_ads: bool = False

    # Update feed (M5): the version chip flips when the feed is ahead.
    update_available: bool = False
    update_data: dict | None = None

    # Terminal sessions (M4): the container whose shell is open, or None.
    active_session: str | None = None
    session_error: str = ""

    def __init__(self):
        self.containers = []
        self.search_results = []
        self.cached_images = []
        self.busy_locks = []


state = AppState()
