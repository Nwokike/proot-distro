"""Mutating operations: install/remove/reset/backup/restore/copy/sync/cache/kill/build/push."""

from __future__ import annotations

import logging

from services.proot_namespaces import (
    _ns_backup,
    _ns_build,
    _ns_clear_cache,
    _ns_copy,
    _ns_install,
    _ns_kill,
    _ns_push,
    _ns_remove,
    _ns_rename,
    _ns_reset,
    _ns_restore,
    _ns_sync,
)

from ._core import Outcome, _imp, _run_command

logger = logging.getLogger(__name__)


def install(
    image: str,
    name: str,
    on_line=None,
    *,
    override_arch: str | None = None,
    allow_insecure: bool = False,
) -> Outcome:
    """Install `image` as `name`, forwarding upstream stage lines live.

    `image` is any reference upstream accepts (debian:bookworm,
    alpine@sha256:…, ./path.tar.gz, https://…). Empty name → upstream derives.
    `override_arch` is a proot-distro arch (aarch64, x86_64, …) or Docker
    platform string; `allow_insecure` permits HTTP/untrusted-TLS custom registries.
    """
    return _run_command(
        "proot_distro.commands.install",
        "command_install",
        _ns_install(
            image, name or None, override_arch=override_arch, allow_insecure=allow_insecure
        ),
        on_line=on_line,
    )


def remove_container(name: str, *, verbose: bool = False, quiet: bool = False) -> Outcome:
    return _run_command(
        "proot_distro.commands.remove",
        "command_remove",
        _ns_remove(name, verbose=verbose, quiet=quiet),
    )


def reset_container(name: str, *, quiet: bool = False) -> Outcome:
    return _run_command(
        "proot_distro.commands.reset",
        "command_reset",
        _ns_reset(name, quiet=quiet),
    )


def remove_cached_image(
    identifier: str,
    *,
    override_arch: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> Outcome:
    """Delete one cached image's layers (storage reclaim; containers stay).

    `identifier` is a reference, an image-ID prefix (≥4 chars), or a cache key.
    """
    return _run_command(
        "proot_distro.commands.remove",
        "command_remove",
        _ns_remove(
            identifier, image=True, override_arch=override_arch, verbose=verbose, quiet=quiet
        ),
    )


def _ensure_build_engine_env() -> None:
    """Make RUN steps executable on Android.

    Upstream's build engine constructs the child environment for RUN from
    scratch (no os.environ inheritance), and the proot it shells out to is an
    UNBUNDLED-LOADER build: without PROOT_LOADER / LD_LIBRARY_PATH /
    PROOT_TMP_DIR it cannot start. Our session layer injects those three for
    every PTY session; the build path has no equivalent — so wrap the engine's
    env builder and add exactly those keys (the same contract, nothing else)."""
    import os

    try:
        module = _imp("proot_distro.helpers.build_engine.run_step")
    except Exception as exc:
        logger.debug("build engine env adapter unavailable: %r", exc)
        return
    original = getattr(module, "_build_child_env", None)
    if original is None or getattr(original, "_kiri_host_env", False):
        return

    def _build_child_env(engine, stage):
        env = original(engine, stage)
        for key in ("PROOT_LOADER", "LD_LIBRARY_PATH", "PROOT_TMP_DIR"):
            value = os.environ.get(key)
            if value and key not in env:
                env[key] = value
        return env

    _build_child_env._kiri_host_env = True  # type: ignore[attr-defined]
    module._build_child_env = _build_child_env


def build_image(
    path: str = ".",
    *,
    dockerfile: str | None = None,
    tags: list[str] | None = None,
    build_args: list[str] | None = None,
    override_arch: str | None = None,
    target_stage: str | None = None,
    emulator: str | None = None,
    outputs: list[str] | None = None,
    install_as: str | None = None,
    no_cache: bool = False,
    verbose: bool = False,
    quiet: bool = False,
    on_line=None,
) -> Outcome:
    """Build an OCI image from a Dockerfile (upstream's full build engine).

    RUN steps execute under proot against the stage rootfs. That needs the
    bundled proot's host environment (see `_ensure_build_engine_env`) — without
    it every RUN fails before executing. `on_line` streams the engine's stage
    lines live."""
    _ensure_build_engine_env()
    return _run_command(
        "proot_distro.commands.build",
        "command_build",
        _ns_build(
            path=path,
            dockerfile=dockerfile,
            tags=tags,
            build_args=build_args,
            override_arch=override_arch,
            target_stage=target_stage,
            emulator=emulator,
            outputs=outputs,
            install_as=install_as,
            no_cache=no_cache,
            verbose=verbose,
            quiet=quiet,
        ),
        on_line=on_line,
    )


def push_image(
    image_ref: str,
    *,
    override_arch: str | None = None,
    allow_insecure: bool = False,
    quiet: bool = False,
    on_line=None,
) -> Outcome:
    """Push a locally built image to its registry (PD_DOCKER_AUTH for private)."""
    return _run_command(
        "proot_distro.commands.push",
        "command_push",
        _ns_push(
            image_ref, override_arch=override_arch, allow_insecure=allow_insecure, quiet=quiet
        ),
        on_line=on_line,
    )


def rename_container(orig: str, new: str) -> Outcome:
    """Rename a container (upstream also rewrites its l2s symlinks)."""
    return _run_command(
        "proot_distro.commands.rename",
        "command_rename",
        _ns_rename(orig, new),
    )


def backup_container(
    container: str,
    output: str,
    compression: str | None = None,
    *,
    verbose: bool = False,
    quiet: bool = False,
) -> Outcome:
    """Write a container's tree to a tar archive (compression: gzip/bzip2/xz/zstd/none)."""
    return _run_command(
        "proot_distro.commands.backup",
        "command_backup",
        _ns_backup(container, output, compression, verbose=verbose, quiet=quiet),
    )


def restore_container(archive: str, *, verbose: bool = False, quiet: bool = False) -> Outcome:
    """Restore a container tree from a tar archive (destroys the target)."""
    return _run_command(
        "proot_distro.commands.restore",
        "command_restore",
        _ns_restore(archive, verbose=verbose, quiet=quiet),
    )


def copy_path(
    source: str,
    destination: str,
    move: bool = False,
    *,
    recursive: bool = True,
    verbose: bool = False,
    quiet: bool = False,
) -> Outcome:
    """Copy (or move) a path between containers / host ('name:/path')."""
    return _run_command(
        "proot_distro.commands.copy",
        "command_copy",
        _ns_copy(source, destination, move=move, recursive=recursive, verbose=verbose, quiet=quiet),
    )


def sync_path(
    source: str,
    destination: str,
    checksum: bool = True,
    delete: bool = False,
    *,
    verbose: bool = False,
    quiet: bool = False,
) -> Outcome:
    """Synchronize directories between containers / host with checksum and pruning."""
    return _run_command(
        "proot_distro.commands.sync",
        "command_sync",
        _ns_sync(
            source, destination, checksum=checksum, delete=delete, verbose=verbose, quiet=quiet
        ),
    )


def clear_cache(
    orphan: bool = False,
    build_cache: bool = False,
    *,
    verbose: bool = False,
    quiet: bool = False,
) -> Outcome:
    """Clear download cache, sweep orphan layer blobs, or drop the build cache."""
    return _run_command(
        "proot_distro.commands.clear_cache",
        "command_clear_cache",
        _ns_clear_cache(orphan=orphan, build_cache=build_cache, verbose=verbose, quiet=quiet),
    )


def kill_session(
    target: str | None = None, all_sessions: bool = False, signal: str | None = None
) -> Outcome:
    """Stop running session(s): `signal` is a name/number (default SIGTERM);
    upstream escalates SIGTERM→SIGQUIT→SIGKILL for stubborn guests.
    `target=None` + `all_sessions=True` is upstream's --all: the target must
    be ABSENT (None), not an empty string — upstream fails
    "a target cannot be combined with --all." on any non-None target."""
    return _run_command(
        "proot_distro.commands.kill",
        "command_kill",
        _ns_kill(target, all_sessions, signal=signal),
    )


def friendly_job_error(outcome: Outcome) -> str:
    """Translate an Outcome into one honest, actionable line."""
    detail = (outcome.detail or "").strip()
    if not detail:
        detail = (
            outcome.output.strip().splitlines()[-1] if outcome.output.strip() else "unknown error"
        )
    tail = outcome.output.strip().splitlines()[-3:]
    return f"{detail}" + (f" — {tail[-1]}" if tail and tail[-1] != detail else "")


PULL_LIMIT_COPY = (
    "Docker Hub pull limit reached. This is a Docker Hub rate limit, not an app "
    "error — wait a few hours and retry, or add an optional Docker Hub token in "
    "Settings to raise your limit."
)

_LIMIT_MARKERS = (
    "toomanyrequests",
    "rate limit",
    "too many requests",
    "429",
    "pull rate",
)


def is_pull_limit(outcome: Outcome) -> bool:
    """True when upstream's failure is Docker Hub's pull limit."""
    haystack = (outcome.detail + "\n" + outcome.output).lower()
    return any(marker in haystack for marker in _LIMIT_MARKERS)
