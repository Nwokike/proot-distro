"""Identity + distribution constants.

The version truth lives here (the app's own copy — pyproject.toml does not
ship inside the APK), and CI checks it against pyproject + the workflow
(the house's release-identity guard).
"""

from __future__ import annotations

APP_NAME = "Proot Distro X11"
APP_VERSION = "1.2.0"
APP_BUILD_NUMBER = 4

REPO_OWNER = "Nwokike"
REPO_NAME = "proot-distro"
GITHUB_RELEASES_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
UPDATE_CONFIG_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/version.json"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=ng.kiri.prootdistro"
PRIVACY_POLICY_URL = "https://kiri.ng/privacy"
TERMS_OF_SERVICE_URL = "https://kiri.ng/terms"

STORAGE_ONBOARDING_DONE = "proot_onboarding_done"

# ── Preferences (SharedPreferences keys) ────────────────────────────────────
PREF_THEME_MODE = "theme_mode"
PREF_DOCKER_TOKEN = "docker_token"  # noqa: S105 - a preference key, not a secret
PREF_DISPLAY_SETTINGS = "display_settings"
PREF_TERMINAL_SETTINGS = "terminal_settings"
PREF_UPDATE_CHECKED_AT = "update_checked_at"

# ── Android notifications ───────────────────────────────────────────────────
NOTIFICATION_ICON = "ic_stat_prootdistro"
NOTIFICATION_ID_FGS = 1
NOTIFICATION_ID_INSTALL = 2100
NOTIFICATION_ACTION_EXIT = "exit"
NOTIFICATION_CHANNEL_SESSIONS = "sessions"
NOTIFICATION_CHANNEL_SESSIONS_NAME = "Sessions"
NOTIFICATION_CHANNEL_INSTALLS = "installs"
NOTIFICATION_CHANNEL_INSTALLS_NAME = "Installs"

# ── Banner ad slots (one name per surface; tests assert these) ──────────────
AD_SLOT_NO_CONTAINERS = "no-containers"
AD_SLOT_SEARCH_EMPTY = "search-empty"
AD_SLOT_CONTAINERS = "containers-1"
AD_SLOT_FILES = "files-1"
AD_SLOT_FILES_EMPTY = "files-empty"
AD_SLOT_TERMINAL = "terminal-1"
AD_SLOT_DISPLAY = "display-1"
AD_SLOT_BUILD = "build-1"
AD_SLOT_SETTINGS_1 = "settings-1"
AD_SLOT_SETTINGS_2 = "settings-2"
AD_EVERY_ROWS = 5  # banner cadence in long lists (owner rule)

# ── Guest paths ────────────────────────────────────────────────────────────
GUEST_HOME = "/root"
GUEST_X11_DIR = "/tmp/x11"  # noqa: S108 - guest rootfs path

# ── Archive formats (one map: the dialog, the name check and the backup use it)
COMPRESS_EXT = {
    "gzip": ".tar.gz",
    "bzip2": ".tar.bz2",
    "xz": ".tar.xz",
    "zstd": ".tar.zst",
    "none": ".tar",
}
ARCHIVE_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst", ".tar")

# ── Upstream choices surfaced by both the install and build screens ────────
UPSTREAM_ARCH_CHOICES = (
    "host",  # sentinel: keep the host's architecture
    "aarch64",
    "arm",
    "i686",
    "riscv64",
    "x86_64",
    "linux/arm64",
    "linux/arm/v7",
    "linux/amd64",
    "linux/386",
    "linux/riscv64",
)
APP_PRESETS = (
    ("Terminal", "xterm"),
    ("Files", "thunar"),
    ("Browser", "firefox"),
    ("Text editor", "mousepad"),
    ("Image editor", "gimp"),
    ("Office", "libreoffice"),
    ("VS Code", "code"),
)
SEARCH_LIMIT_DEFAULT = 25
UPDATE_CHECK_INTERVAL_SEC = 6 * 3600.0
LOW_BATTERY_PCT = 20
BATTERY_SAVER_DISPLAY = {"fps": 15, "quality": 60, "compression": 4}
