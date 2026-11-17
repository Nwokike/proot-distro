"""Display (X11) session actions: probe, start/stop, view routing.

The DeskManager (desk_service) owns the guest processes — one per session key
`container:display`, so a container can run several displays at once (single
apps on :0, :1, :2…). This mixin owns the UI state and the FGS ref-count shared
with the terminal actions. fps/depth/quality/geometry map to Xvnc and noVNC
settings, `lan` to the bind host, `tunnel` to our guest ssh forward; fullscreen
locks orientation and keeps the screen awake through the shared Wakelock
service and `set_allowed_device_orientations`.
"""

from __future__ import annotations

import logging

from .display_apps import DisplayAppsMixin
from .display_common import _auto_geometry, _tail_file_lines, invalidate_display_support  # noqa: F401
from .display_logs import DisplayLogsMixin
from .display_probe import DisplayProbeMixin
from .display_session import DisplaySessionMixin

logger = logging.getLogger(__name__)


class DisplayActions(
    DisplayAppsMixin,
    DisplayProbeMixin,
    DisplaySessionMixin,
    DisplayLogsMixin,
):
    """The display actions, assembled from their focused mixins."""
