"""Views: onboarding, the distro manager, display/desktop, build, settings, terminal."""

from screens.build_view import BuildView
from screens.desktop import DesktopView
from screens.display_view import DisplayView
from screens.files import FilesView
from screens.onboarding_view import OnboardingView
from screens.session_selector_view import SessionSelectorView
from screens.terminal import TerminalView
from screens.views import DistroView, SettingsView, licenses_view

__all__ = [
    "BuildView",
    "DesktopView",
    "DisplayView",
    "DistroView",
    "FilesView",
    "OnboardingView",
    "SessionSelectorView",
    "SettingsView",
    "TerminalView",
    "licenses_view",
]
