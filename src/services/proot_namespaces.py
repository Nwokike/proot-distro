"""Argparse namespaces matching proot-distro's public command parsers.

Every field is verified against proot_distro/parser.py (see
tests/test_proot_surfaces.py, which checks the namespaces field-for-field
against the real parser). Options the parser gates behind IS_TERMUX
(--isolated/--minimal/--no-*) are absent from our namespaces because the
packaged app runs with IS_TERMUX=False; the app's own Android hardening of the
session argv lives in session_service._harden_session.
"""

from __future__ import annotations

from types import SimpleNamespace


def _ns_install(
    image: str,
    name: str | None,
    override_arch: str | None = None,
    allow_insecure: bool = False,
) -> SimpleNamespace:
    # Verified: _install defines image_ref/-n|--name|--override-alias/-a/--allow-insecure/-q/-h.
    return SimpleNamespace(
        image_ref=image,
        custom_container_name=name,
        override_arch=override_arch,
        allow_insecure=allow_insecure,
    )


def _ns_remove(
    target: str,
    *,
    image: bool = False,
    override_arch: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> SimpleNamespace:
    # Verified: _remove defines target/--image/--architecture/-v/-q.
    return SimpleNamespace(
        target=target,
        image=image,
        override_arch=override_arch,
        verbose=verbose,
        quiet=quiet,
    )


def _ns_reset(name: str, quiet: bool = False) -> SimpleNamespace:
    # Verified: _reset defines container_name/-q.
    return SimpleNamespace(
        container_name=name,
        quiet=quiet,
    )


def _ns_rename(orig: str, new: str) -> SimpleNamespace:
    # Verified: _rename defines orig_name/new_name/-q.
    return SimpleNamespace(orig_name=orig, new_name=new, quiet=False)


def _ns_backup(
    container: str,
    output: str,
    compression: str | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> SimpleNamespace:
    # Verified: _backup defines container_name/-o/--output/-c/--compress/-v/-q.
    return SimpleNamespace(
        container_name=container,
        output=output,
        compression=compression,
        verbose=verbose,
        quiet=quiet,
    )


def _ns_restore(archive: str, verbose: bool = False, quiet: bool = False) -> SimpleNamespace:
    # Verified: _restore defines archive/-v/-q.
    return SimpleNamespace(archive=archive, verbose=verbose, quiet=quiet)


def _ns_copy(
    source: str,
    destination: str,
    *,
    move: bool = False,
    recursive: bool = True,
    verbose: bool = False,
    quiet: bool = False,
) -> SimpleNamespace:
    # Verified: _copy defines source/destination/-v/-q/-m/--move/-r/--recursive.
    return SimpleNamespace(
        source=source,
        destination=destination,
        verbose=verbose,
        quiet=quiet,
        move=move,
        recursive=recursive,
    )


def _ns_kill(target: str, all_sessions: bool = False, signal: str | None = None) -> SimpleNamespace:
    # Verified: _kill defines target/-s/--signal/--all.
    return SimpleNamespace(target=target, all=all_sessions, signal=signal)


def _ns_clear_cache(
    orphan: bool = False,
    build_cache: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> SimpleNamespace:
    # Verified: _clear_cache defines --orphan/--build-cache/-v/-q.
    return SimpleNamespace(
        orphan=orphan,
        build_cache=build_cache,
        verbose=verbose,
        quiet=quiet,
    )


def _ns_sync(
    source: str,
    destination: str,
    checksum: bool = True,
    delete: bool = False,
    verbose: bool = False,
    quiet: bool = False,
) -> SimpleNamespace:
    # Verified: _sync defines source/destination/-v/-q/-c/--checksum/-d/--delete.
    return SimpleNamespace(
        source=source,
        destination=destination,
        checksum=checksum,
        delete=delete,
        verbose=verbose,
        quiet=quiet,
    )


# Fields shared by `login` and `run` (_add_login_or_run_common in parser.py).
# IS_TERMUX-gated fields (isolated/minimal/no_*) are deliberately absent: the
# packaged app runs with IS_TERMUX=False, so the parser never accepts them.
_LOGIN_RUN_COMMON = {
    "user": "root",
    "redirect_ports": False,
    "shared_home": False,
    "shared_tmp": False,
    "shared_x11": False,
    "bind": [],
    "emulator": None,
    "kernel": None,
    "hostname": None,
    "work_dir": None,
    "env": [],
    "detach": False,
}


def _ns_run(
    container: str,
    run_args: list[str],
    work_dir: str | None = None,
    *,
    get_proot_cmd: bool = False,
    **login_opts,
) -> SimpleNamespace:
    # get_proot_cmd must be True for any in-process call: with False, upstream
    # command_run -> command_login ends in os.execvpe and replaces the whole
    # app process. proot_service._run_command refuses the False case outright.
    common = {**_LOGIN_RUN_COMMON, **login_opts}
    if work_dir is not None:
        common["work_dir"] = work_dir
    return SimpleNamespace(
        container_name=container,
        run_args=run_args,
        get_proot_cmd=get_proot_cmd,
        **common,
    )


def _ns_build(
    path: str = ".",
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
) -> SimpleNamespace:
    # Verified: _build defines path/-f|--file/-t|--tag/--build-arg/-a/--target/--emulator/-o|--output/--install-as/--no-cache/-v/-q.
    return SimpleNamespace(
        path=path,
        dockerfile=dockerfile,
        tags=list(tags or []),
        build_args=list(build_args or []),
        override_arch=override_arch,
        target_stage=target_stage,
        emulator=emulator,
        outputs=list(outputs or []),
        install_as=install_as,
        no_cache=no_cache,
        verbose=verbose,
        quiet=quiet,
    )


def _ns_push(
    image_ref: str,
    override_arch: str | None = None,
    allow_insecure: bool = False,
    quiet: bool = False,
) -> SimpleNamespace:
    # Verified: _push defines image_ref/-a/--allow-insecure/-q.
    return SimpleNamespace(
        image_ref=image_ref,
        override_arch=override_arch,
        allow_insecure=allow_insecure,
        quiet=quiet,
    )


def _ns_login_get_proot_cmd(container: str, **login_opts) -> SimpleNamespace:
    """`login <c> --get-proot-cmd` namespace with optional login/run options.

    Verified against parser.py:116-160 (_add_login_or_run_common) + :262
    (_login): every field _login_with_rootfs reads from the namespace.
    get_proot_cmd is always True here — with False, upstream execvpe's the app.
    """
    common = {**_LOGIN_RUN_COMMON, **login_opts}
    return SimpleNamespace(
        container_name=container,
        fix_low_ports=False,
        # IS_TERMUX-gated fields, kept for parser parity; inert when IS_TERMUX=False.
        isolated=False,
        minimal=False,
        termux_home=False,
        no_link2symlink=False,
        no_sysvipc=False,
        no_kill_on_exit=False,
        get_proot_cmd=True,
        login_cmd=[],
        **common,
    )
