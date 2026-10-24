"""Identity + distribution constants.

The version truth lives here (the app's own copy — pyproject.toml does not
ship inside the APK), and CI checks it against pyproject + the workflow
(the house's release-identity guard).
"""

from __future__ import annotations

APP_NAME = "Proot Distro"
APP_VERSION = "1.0.0"
APP_BUILD_NUMBER = 1

REPO_OWNER = "Nwokike"
REPO_NAME = "proot-distro"
GITHUB_RELEASES_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/latest"
UPDATE_CONFIG_URL = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/version.json"
PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=ng.kiri.prootdistro"
PRIVACY_POLICY_URL = "https://github.com/Nwokike/proot-distro/blob/main/PRIVACY.md"
TERMS_OF_SERVICE_URL = "https://github.com/Nwokike/proot-distro/blob/main/PRIVACY.md"

STORAGE_ONBOARDING_DONE = "proot_onboarding_done"
STORAGE_HINTS_DISMISSED = "proot_hints_dismissed"
