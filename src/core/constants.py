"""Identity + distribution constants.

The version truth lives here (the app's own copy — pyproject.toml does not
ship inside the APK), and CI checks it against pyproject + the workflow
(the house's release-identity guard).
"""

from __future__ import annotations

APP_NAME = "Proot Distro X11"
APP_VERSION = "1.2.1"
APP_BUILD_NUMBER = 5

REPO_OWNER = "Nwokike"
REPO_NAME = "proot-distro"
GITHUB_RELEASES_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
UPDATE_CONFIG_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/version.json"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=ng.kiri.prootdistro"
GITHUB_REPO_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}"
GITHUB_ISSUES_URL = f"{GITHUB_REPO_URL}/issues"
PRIVACY_POLICY_URL = "https://kiri.ng/privacy"
TERMS_OF_SERVICE_URL = "https://kiri.ng/terms"
# The owner's About rows are identical in every Kiri app (DDGS/ktv-player):
# Play devices rate on the store, desktop rates on GitHub.
CONTACT_EMAIL = "hello@kiri.ng"
KIRI_APPS_PLAY_URL = "https://play.google.com/store/apps/dev?id=5797833969564243342"
KIRI_APPS_URL = "https://kiri.ng/projects"

STORAGE_ONBOARDING_DONE = "proot_onboarding_done"

# ── Preferences (SharedPreferences keys) ────────────────────────────────────
PREF_THEME_MODE = "theme_mode"
PREF_DOCKER_TOKEN = "docker_token"  # noqa: S105 - a preference key, not a secret
PREF_DISPLAY_SETTINGS = "display_settings"
PREF_TERMINAL_SETTINGS = "terminal_settings"
PREF_UPDATE_CHECKED_AT = "update_checked_at"
PREF_ENV_DEFAULTS = "env_defaults"
# User-made launch presets for the display sheet: name, command, work dir, env.
PREF_APP_PRESETS = "app_presets"

# ── Android notifications ───────────────────────────────────────────────────
NOTIFICATION_ICON = "ic_stat_prootdistro"
NOTIFICATION_ID_FGS = 1
NOTIFICATION_ID_GUEST_BASE = 3000  # guest-app notification ids cycle above this
NOTIFICATION_ACTION_EXIT = "exit"
NOTIFICATION_CHANNEL_SESSIONS = "sessions"
NOTIFICATION_CHANNEL_SESSIONS_NAME = "Sessions"
NOTIFICATION_CHANNEL_GUEST = "guest-apps"
NOTIFICATION_CHANNEL_GUEST_NAME = "Guest apps"

# ── Banner ad slots (one name per surface; tests assert these) ──────────────
AD_SLOT_NO_CONTAINERS = "no-containers"
AD_SLOT_SEARCH_EMPTY = "search-empty"
AD_SLOT_CONTAINERS = "containers-1"
AD_SLOT_INSTALL_LIST = "install-list-1"
AD_SLOT_FILES = "files-1"
AD_SLOT_FILES_EMPTY = "files-empty"
AD_SLOT_TERMINAL = "terminal-1"
AD_SLOT_DISPLAY = "display-1"
AD_SLOT_BUILD = "build-1"
AD_SLOT_SETTINGS_1 = "settings-1"
AD_SLOT_SETTINGS_2 = "settings-2"
AD_SLOT_SETTINGS_3 = "settings-3"
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
