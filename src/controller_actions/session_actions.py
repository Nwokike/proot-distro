"""Terminal session actions: list, kill, open/leave/close, one-shot run."""

from __future__ import annotations

import logging

from .session_fgs import SessionFgsMixin
from .session_listing import SessionListingMixin
from .session_open import SessionOpenMixin
from .session_run import SessionRunMixin

logger = logging.getLogger(__name__)


class SessionActions(
    SessionFgsMixin,
    SessionListingMixin,
    SessionOpenMixin,
    SessionRunMixin,
):
    """Shell/session actions, assembled from their focused mixins."""
