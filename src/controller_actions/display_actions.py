"""Display (X11) session actions: probe, start/stop, provision, view routing.

The DeskManager (desk_service) owns the guest processes — one per session key
`container:display`, so a container can run several displays at once (a desktop
on :0 plus single apps on :1, :2…). This mixin owns the UI state and the FGS
ref-count shared with the terminal actions. fps/depth/quality/geometry map to
Xvnc and noVNC settings, `lan` to the bind host, `tunnel` to our guest ssh
forward; fullscreen locks orientation and keeps the screen awake through the
shared Wakelock service and `set_allowed_device_orientations`.
"""

from __future__ import annotations

import logging

from .display_common import _auto_geometry, _tail_file_lines, invalidate_display_support  # noqa: F401
from .display_install import DisplayInstallMixin
from .display_logs import DisplayLogsMixin
from .display_probe import DisplayProbeMixin
from .display_session import DisplaySessionMixin

logger = logging.getLogger(__name__)


class DisplayActions(
    DisplayProbeMixin,
    DisplaySessionMixin,
    DisplayInstallMixin,
    DisplayLogsMixin,
):
    """The display actions, assembled from their focused mixins."""
