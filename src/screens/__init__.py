"""Views: onboarding, the distro manager, settings, and the terminal."""

from screens.files import FilesView
from screens.onboarding_view import OnboardingView
from screens.session_selector_view import SessionSelectorView
from screens.terminal_view import TerminalView
from screens.views import DistroView, SettingsView, licenses_view

__all__ = [
    "DistroView",
    "FilesView",
    "OnboardingView",
    "SessionSelectorView",
    "SettingsView",
    "TerminalView",
    "licenses_view",
]
