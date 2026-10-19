"""Controller bridge — AppController populates, views read via context.

No-op defaults mean a view can always call a method during the first render;
AppController fills the real implementations before `page.render`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import flet as ft


def _noop() -> None:
    return None


async def _noop_async(*_args, **_kwargs) -> None:
    return None


@dataclass
class ControllerMethods:
    # Distro manager
    refresh_containers: Callable[[], Awaitable[None]] = _noop_async
    install_distro: Callable[[str, str], Awaitable[None]] = field(default=_noop_async)
    cancel_install: Callable[[], None] = field(default=_noop)
    remove_container: Callable[[str], Awaitable[None]] = field(default=_noop_async)
    reset_container: Callable[[str], Awaitable[None]] = field(default=_noop_async)
    search_distro: Callable[[str], Awaitable[None]] = field(default=_noop_async)

    # Settings
    clear_cache: Callable[[], Awaitable[None]] = field(default=_noop_async)
    set_docker_token: Callable[[str], Awaitable[None]] = field(default=_noop_async)
    set_theme_mode: Callable[[str], Awaitable[None]] = field(default=_noop_async)
    cycle_theme_mode: Callable[[], Awaitable[None]] = field(default=_noop_async)
    check_probe: Callable[[], Awaitable[None]] = field(default=_noop_async)
    show_privacy_options: Callable[[], Awaitable[None]] = field(default=_noop_async)

    # Shell-level
    show_snack: Callable[[str], None] = field(default=_noop)

    # Container actions
    rename_container: Callable[[str, str], Awaitable[None]] = field(default=_noop_async)
    backup_container: Callable[[str], Awaitable[None]] = field(default=_noop_async)
    restore_container: Callable[[], Awaitable[None]] = field(default=_noop_async)
    copy_path: Callable[[str, str], Awaitable[None]] = field(default=_noop_async)
    list_sessions: Callable[[], Awaitable[None]] = field(default=_noop_async)
    kill_session: Callable[[str], Awaitable[None]] = field(default=_noop_async)

    # Terminal sessions
    open_session: Callable[[str], Awaitable[None]] = field(default=_noop_async)
    leave_session: Callable[[], Awaitable[None]] = field(default=_noop_async)
    close_session: Callable[[str], Awaitable[None]] = field(default=_noop_async)


ControllerMethodsCtx = ft.create_context(ControllerMethods())
