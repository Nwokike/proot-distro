"""Container actions — public facade.

The dialogs live in screens/container_dialogs/; this module re-exports them.
"""

from __future__ import annotations

from .container_dialogs.archive import ask_backup, ask_run
from .container_dialogs.confirm import ask_remove, ask_rename, ask_reset, browse_files
from .container_dialogs.menu import container_menu_items
from .container_dialogs.path_ops import ask_copy, ask_sync
from .container_dialogs.shell_options import ask_shell_options

__all__ = [
    "ask_backup",
    "ask_copy",
    "ask_remove",
    "ask_rename",
    "ask_reset",
    "ask_run",
    "ask_shell_options",
    "ask_sync",
    "browse_files",
    "container_menu_items",
]
