"""Argparse namespaces matching proot-distro's public command parsers."""

from __future__ import annotations

from types import SimpleNamespace


def _ns_install(image: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        image_ref=image,
        custom_container_name=name,
        override_arch=None,
        allow_insecure=False,
    )


def _ns_remove(name: str) -> SimpleNamespace:
    # Verified: _remove defines target/--image/--architecture/-v/-q.
    return SimpleNamespace(
        target=name,
        image=False,
        override_arch=None,
        verbose=False,
        quiet=False,
    )


def _ns_reset(name: str) -> SimpleNamespace:
    # Verified: _reset defines container_name/-q.
    return SimpleNamespace(
        container_name=name,
        verbose=False,
        quiet=False,
    )


def _ns_rename(orig: str, new: str) -> SimpleNamespace:
    return SimpleNamespace(orig_name=orig, new_name=new)


def _ns_backup(container: str, output: str, compression: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        container_name=container,
        output=output,
        compression=compression,
        verbose=False,
        quiet=False,
    )


def _ns_restore(archive: str) -> SimpleNamespace:
    return SimpleNamespace(archive=archive, verbose=False)


def _ns_copy(
    source: str, destination: str, move: bool = False, recursive: bool = True
) -> SimpleNamespace:
    return SimpleNamespace(
        source=source,
        destination=destination,
        verbose=False,
        quiet=False,
        move=move,
        recursive=recursive,
    )


def _ns_kill(target: str, all_sessions: bool = False, signal: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(target=target, all=all_sessions, signal=signal)


def _ns_clear_cache(orphan: bool = False, build_cache: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        orphan=orphan,
        build_cache=build_cache,
        verbose=False,
        quiet=False,
    )


def _ns_sync(
    source: str, destination: str, checksum: bool = True, delete: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        source=source,
        destination=destination,
        checksum=checksum,
        delete=delete,
        verbose=False,
        quiet=False,
    )


def _ns_run(container: str, run_args: list[str], work_dir: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        container_name=container,
        run_args=run_args,
        work_dir=work_dir,
        user="root",
        redirect_ports=False,
        shared_home=False,
        shared_tmp=False,
        shared_x11=False,
        bind=[],
        emulator=None,
        kernel=None,
        hostname=None,
        env=[],
        detach=False,
        get_proot_cmd=False,
    )


def _ns_remove_image(identifier: str) -> SimpleNamespace:
    # Verified: remove.py defines target/--image/--architecture/-v/-q; --image
    # targets a cached image rather than a container.
    return SimpleNamespace(
        target=identifier,
        image=True,
        override_arch=None,
        verbose=False,
        quiet=False,
    )


def _ns_login_get_proot_cmd(container: str) -> SimpleNamespace:
    # Verified against parser.py:116-160 (_add_login_or_run_common) + :262
    # (_login): every field _login_with_rootfs reads from the namespace.
    return SimpleNamespace(
        container_name=container,
        user="root",
        redirect_ports=False,
        fix_low_ports=False,
        isolated=False,
        minimal=False,
        shared_home=False,
        termux_home=False,
        shared_tmp=False,
        shared_x11=False,
        bind=[],
        no_link2symlink=False,
        no_sysvipc=False,
        no_kill_on_exit=False,
        emulator="",
        kernel="",
        hostname="",
        work_dir="",
        env=[],
        detach=False,
        get_proot_cmd=True,
        login_cmd=[],
    )
