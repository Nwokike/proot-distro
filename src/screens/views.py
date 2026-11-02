"""Compatibility exports for the distro and settings screens."""

from screens.build_view import BuildView
from screens.distro import DistroView
from screens.license_view import licenses_view
from screens.settings import SettingsView

__all__ = ["BuildView", "DistroView", "SettingsView", "licenses_view"]
