"""Observable state — every mutation re-renders subscribed views."""

from __future__ import annotations

import flet as ft

# The ONE source of display-start defaults (used by state.__init__ and by
# DisplayActions._display_settings — never duplicated). Every key drives a REAL
# server option: fps → Xvnc -FrameRate, depth → -depth, shared_policy →
# -AlwaysShared/-NeverShared, clipboard → -AcceptCutText/-SendCutText,
# disconnect_timeout → -MaxDisconnectionTime, mic/audio_* → the PulseAudio
# module lines. Friendly defaults; all of them adjustable in Advanced.
DEFAULT_DISPLAY_SETTINGS: dict = {
    "fps": 30,  # Xvnc -FrameRate (updates per second sent to the viewer)
    "quality": 70,
    "compression": 2,
    "geometry": "auto",
    "orientation": "landscape",
    "lan": False,
    "tunnel": False,
    "depth": "24",
    "shared_policy": "always",  # always | never ("auto" == always for our viewer)
    "resize": "remote",  # remote | scale | off — how the viewer fits the framebuffer
    "clipboard": True,
    "disconnect_timeout": 0,  # seconds after the last viewer exits; 0 = keep running
    "mic": True,
    "audio_latency_ms": 0,  # 0 = AAudio's own buffer-derived latency
    "audio_pm": 2,  # AAudio performance-mode offset (2 = LOW_LATENCY)
}


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
    install_logs: list = None  # list[str] — live lines from proot-distro install
    install_completed: bool = False
    last_installed: str = ""
    install_dialog_minimized: bool = False
    busy_note: str = ""  # e.g. upstream reports another install holding the lock
    search_status: str = ""
    search_results: list = None  # list[dict] — Docker Hub hits

    # Settings & Storage
    storage_bytes: int = 0
    cached_count: int = 0
    cached_images: list = None  # list[dict] — cached OCI images
    busy_locks: list = None  # list[str] — locks held by active operations
    storage_detail: dict | None = None  # per-area sizes under the Flet storage roots
    cache_busy: bool = False
    docker_token: str = ""
    theme_mode: str = "system"  # "system" | "light" | "dark"
    theme_revision: int = 0  # bumped on every theme flip (re-render signal)

    apt_note_dismissed: bool = False
    terminal_fullscreen: bool = False

    # Run (one-shot command in a container) — result shown in a dialog
    run_busy: str | None = None  # container name while a run is in progress
    run_status: str = ""
    run_output: str = ""
    run_returncode: int | None = None

    # Build (Dockerfile → OCI image) — live stage lines like install
    build_busy: bool = False
    build_stage: str = ""
    build_logs: list = None  # list[str]
    build_result: dict | None = None  # tags/layers/size from the finished build
    push_busy: bool = False
    push_status: str = ""

    # Startup gate (CollabShell / AnimePahe pattern): the shell shows the
    # splash until initial checks and container discovery finish.
    app_ready: bool = False
    startup_stage: str = ""

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

    # Display / X11 (v1.1.0): the container whose display is open, or None.
    active_display: str | None = None
    # Bumped by DeskManager.on_sessions_changed on every session transition so
    # the Display tab re-reads manager.running()/visible() immediately (the
    # Stop button included) instead of waiting for a tab switch.
    display_sessions_rev: int = 0
    # Bumped on every guest log line so the display view's output panel streams
    # live (the log is written from the reader thread, so it goes through
    # page.run_task like the session rev).
    display_log_rev: int = 0
    display_status: str = "idle"  # idle | starting | running | stopping | error
    display_status_text: str = ""
    display_error: str = ""
    display_url: str = ""
    display_fullscreen: bool = False
    display_support: dict | None = None  # per-container caps cache: name -> guest_capabilities
    display_installing: str | None = None  # container currently installing the desktop
    display_logs: list = None  # list[str] — bounded log tail for the active display
    display_install_logs: list = None  # list[str] — live provisioning output
    # Launcher-set options for the NEXT start — the display wrap surface:
    # quality/compression (noVNC knobs; fps kept for the persisted surface),
    # geometry (Xvnc screen, "auto" = device aspect), orientation (fullscreen
    # lock), lan (host 0.0.0.0), tunnel (upstream localhost.run publish).
    display_settings: dict | None = None

    def __init__(self):
        self.containers = []
        self.search_results = []
        self.cached_images = []
        self.busy_locks = []
        self.install_logs = []
        self.build_logs = []
        self.display_support = {}
        self.display_logs = []
        self.display_install_logs = []
        self.display_settings = dict(DEFAULT_DISPLAY_SETTINGS)


state = AppState()


@ft.observable
class DisplayProgress:
    """Dedicated observable model for the desktop-install progress card — the
    CollabShell NotebookCell mechanism copied exactly: a SMALL observable
    object passed as the component's argument (not a field on the global
    AppState), so every mutation re-renders that one card reactively.
    Mutate `logs` by REASSIGNMENT and bump `rev` (CellData.outputs_rev)."""

    def __init__(self):
        self.container: str | None = None
        self.logs: list[str] = []
        self.is_running: bool = False
        self.rev: int = 0
        self.finished_ok: bool | None = None

    def append(self, line: str) -> None:
        clean = line.rstrip()
        if not clean:
            return
        self.logs = [*self.logs[-399:], clean]
        self.rev += 1

    def clear(self, container: str | None = None) -> None:
        self.container = container
        self.logs = []
        self.rev += 1
        self.finished_ok = None

    def set_running(self, flag: bool) -> None:
        self.is_running = bool(flag)

    def finish(self, ok: bool | None) -> None:
        self.is_running = False
        self.finished_ok = ok


display_progress = DisplayProgress()
