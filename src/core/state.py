"""Observable state — every mutation re-renders subscribed views."""

from __future__ import annotations

import flet as ft

# The ONE source of display-start defaults (used by state.__init__ and by
# DisplayActions._display_settings — never duplicated). Every key has a real
# consumer, in one of three layers: Xvnc argv (fps → -FrameRate, depth →
# -depth, shared_policy → -AlwaysShared/-NeverShared, clipboard →
# -AcceptCutText/-SendCutText, disconnect_timeout → -MaxDisconnectionTime),
# PulseAudio module lines (mic/audio_*), or the viewer/host layer
# (quality/compression/resize → noVNC settings, orientation → the orientation
# lock, lan/tunnel → the bind host and the guest ssh forward).
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
    "resize": "scale",  # scale | remote | off — scale fits the whole desktop (letterbox)
    "clipboard": True,
    # Raw RFB port gates — OFF by default (the stream server's access code is
    # the viewer gate); the user opts in.
    "restrict_local": False,  # Xvnc -localhost=1 (loopback-only RFB)
    # Remaining real Xvnc 1.16.2 parameters.
    "compare_fb": 2,  # 2 framebuffer compare, 1 region, 0 always send
    "dpi": 0,  # 0 = Xvnc default (96)
    "idle_timeout": 0,  # drop an idle viewer after N s (session stays up)
    "max_connection_time": 0,  # hard cap per viewer connection (s)
    "view_only": False,  # refuse remote input (screenshot-only viewer)
    "max_cut_text": 0,  # clipboard cap in bytes (0 = Xvnc default)
    "disconnect_clients": False,  # a new viewer kicks the others
    # PulseAudio module/daemon options.
    "audio_rate": 0,  # AAudio sink rate (0 = device default)
    "audio_no_close_hack": False,
    "mic_rate": 0,
    "mic_format": "",  # e.g. s16le
    "mic_channels": 0,
    "resample_method": "",  # e.g. speex-float-1 / soxr-hq
    # noVNC client settings.
    "viewer_bell": True,
    "show_dot": False,
    "viewer_logging": "warn",
    "disconnect_timeout": 0,  # seconds after the last viewer exits; 0 = keep running
    # Microphone OFF at start (owner ruling 2026-11-17): the viewer toolbar's mic
    # button is the only source of truth, and it requests the Android grant the
    # moment the user turns it on. A display opened with the mic never prompts.
    "mic": False,
    "forward_guest_notifications": True,  # guest D-Bus notifications → Android
    "audio_latency_ms": 0,  # 0 = AAudio's own buffer-derived latency
    "audio_pm": 2,  # AAudio performance-mode offset (2 = LOW_LATENCY)
}


def _is_online(types) -> bool:
    """True when at least one reported connectivity type is a real network.
    An empty/unknown report counts as online — a missing probe must never block
    an install."""
    if not types:
        return True
    return any(getattr(item, "value", item) not in ("none", "None") for item in types)


# Terminal defaults (Settings -> Terminal): applied to every NEW shell. An
# empty theme means "follow the app mode": Dracula in dark, Colab Light in
# light (owner ruling 2026-11-17). An explicit saved choice always wins.
DEFAULT_TERMINAL_SETTINGS: dict = {
    "theme": "",
    "font_size": 0.0,  # 0 = the widget default
    "cursor_blink": True,
}


@ft.observable
class AppState:
    # Probe / environment
    probe_passed: bool = False
    probe_summary: str = ""
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
    storage_detail: dict | None = None  # per-area sizes under the Flet storage roots
    cache_busy: bool = False
    online: bool = True  # Connectivity service's last known state
    settings_section: str = ""  # "" | "build"
    # Guest defaults the user adds (KEY=VALUE) — injected into new shells and
    # displays; separate from the app's own runtime contract.
    env_defaults: dict = None
    # Split storage so the Settings row can be honest about what lives where.
    storage_containers_bytes: int = 0
    storage_cache_bytes: int = 0
    notifications_enabled: bool | None = None  # None = not probed
    # Guest processes from the last listing (None = never listed). The Settings
    # row shows the count it was told, never a fabricated zero.
    running_sessions: list | None = None
    terminal_settings: dict = None  # DEFAULT_TERMINAL_SETTINGS + saved values
    # Bumped when a shell picks its terminal theme, so the FAB menu rebuilds
    # and its check mark follows the real theme immediately.
    terminal_theme_rev: int = 0
    device_orientation: str = "portrait"  # PageMediaData.orientation
    keyboard_inset: float = 0.0  # PageMediaData.view_insets.bottom (px)
    docker_token: str = ""
    theme_mode: str = "system"  # "system" | "light" | "dark"
    theme_revision: int = 0  # bumped on every theme flip (re-render signal)

    terminal_fullscreen: bool = False

    # Run (one-shot command in a container) — result shown in a dialog
    run_busy: str | None = None  # container name while a run is in progress
    run_status: str = ""
    run_output: str = ""

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

    # Ads: the UMP consent verdict. BANNERS gate on it (their load must wait
    # for consent); interstitials never do — they serve regardless (owner
    # ruling), so an ad always shows for a major action.
    can_request_ads: bool = False

    # Update feed (M5): the version chip flips when the feed is ahead.
    update_available: bool = False
    update_data: dict | None = None

    # Terminal sessions (M4): the container whose shell is open, or None.
    active_session: str | None = None
    session_error: str = ""

    # Display / X11: the container whose display is open, or None.
    active_display: str | None = None
    # Probed preset apps per container ({container: [{label, cmd}, ...]}), so
    # the Display tab can offer real one-tap apps instead of a generic button.
    # None = never probed; {} = probed and nothing found.
    detected_apps: dict | None = None
    # When each container's app scan last ran (monotonic seconds) — the Display
    # tab and the sheet re-probe a container whose stamp is older than their
    # TTL, so a freshly installed app appears without an app restart.
    detected_apps_at: dict | None = None
    # User-made launch presets: [{"name", "cmd", "work_dir", "env"}]. These are
    # the user's own "desktop shortcuts": a name, a command and the login
    # options that belong to it.
    app_presets: list | None = None
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
    # Launcher-set options for the NEXT start — the display wrap surface:
    # quality/compression (noVNC knobs; fps kept for the persisted surface),
    # geometry (Xvnc screen, "auto" = device aspect), orientation (fullscreen
    # lock), lan (host 0.0.0.0), tunnel (our guest ssh reverse forward).
    display_settings: dict | None = None

    def __init__(self):
        self.containers = []
        self.search_results = []
        self.cached_images = []
        self.install_logs = []
        self.build_logs = []
        self.display_support = {}
        self.display_settings = dict(DEFAULT_DISPLAY_SETTINGS)


state = AppState()
