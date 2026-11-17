"""The only module allowed to import proot_distro (sole-importer facade).

Split into submodules for maintainability; this __init__ re-exports the whole
public surface so `from services import proot_service` and every
`proot_service.<name>` reference keep working unchanged.
"""

from services.proot_namespaces import (
    _ns_backup,
    _ns_build,
    _ns_clear_cache,
    _ns_copy,
    _ns_install,
    _ns_kill,
    _ns_login_get_proot_cmd,
    _ns_push,
    _ns_remove,
    _ns_rename,
    _ns_reset,
    _ns_restore,
    _ns_run,
    _ns_sync,
)

from . import _core as _core_module
from ._capabilities import arch_choices, guest_capabilities, host_arch
from ._commands import (
    _call_get_proot_cmd,
    fake_sysdata_bindings,
    get_proot_cmd,
    get_proot_cmd_with_options,
    run_command_argv,
    setup_fake_sysdata,
)
from ._core import (
    Outcome,
    _imp,
    _run_command,
    available,
    bootstrap,
)
from ._guard import ProotUnavailable, _no_process_exit
from ._ops import (
    PULL_LIMIT_COPY,
    backup_container,
    build_image,
    clear_cache,
    copy_path,
    friendly_job_error,
    install,
    is_pull_limit,
    kill_session,
    push_image,
    remove_cached_image,
    remove_container,
    rename_container,
    reset_container,
    restore_container,
    sync_path,
)
from ._queries import (
    active_sessions,
    busy_locks,
    cached_images,
    container_rootfs,
    container_users,
    guest_desktop_apps,
    guest_path_exists,
    inspect_container,
    list_containers,
    search_images,
    storage_bytes,
    storage_detail,
    storage_split,
)


def __getattr__(name: str):
    # Live-forward mutable module state (tests monkeypatch these).
    if name == "_BOOTSTRAPPED":
        return _core_module._BOOTSTRAPPED
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "PULL_LIMIT_COPY",
    "Outcome",
    "ProotUnavailable",
    "_call_get_proot_cmd",
    "_imp",
    "_no_process_exit",
    "_ns_backup",
    "_ns_build",
    "_ns_clear_cache",
    "_ns_copy",
    "_ns_install",
    "_ns_kill",
    "_ns_login_get_proot_cmd",
    "_ns_push",
    "_ns_remove",
    "_ns_rename",
    "_ns_reset",
    "_ns_restore",
    "_ns_run",
    "_ns_sync",
    "_run_command",
    "active_sessions",
    "arch_choices",
    "available",
    "backup_container",
    "bootstrap",
    "build_image",
    "busy_locks",
    "cached_images",
    "clear_cache",
    "container_rootfs",
    "container_users",
    "copy_path",
    "fake_sysdata_bindings",
    "friendly_job_error",
    "get_proot_cmd",
    "get_proot_cmd_with_options",
    "guest_capabilities",
    "guest_desktop_apps",
    "guest_path_exists",
    "host_arch",
    "inspect_container",
    "install",
    "is_pull_limit",
    "kill_session",
    "list_containers",
    "push_image",
    "remove_cached_image",
    "remove_container",
    "rename_container",
    "reset_container",
    "restore_container",
    "run_command_argv",
    "search_images",
    "setup_fake_sysdata",
    "storage_bytes",
    "storage_detail",
    "storage_split",
    "sync_path",
]
