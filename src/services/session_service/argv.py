"""Session argv: upstream login/run command lines + Android hardening."""

from __future__ import annotations

import logging
import os
import platform
import re
import shlex
from pathlib import Path

from services import proot_service

logger = logging.getLogger(__name__)


Env = dict[str, str]
Argv = list[str]
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_HOST_ESSENTIALS = ("LD_LIBRARY_PATH", "PROOT_LOADER", "PROOT_TMP_DIR")


def _harden_session(
    env: Env,
    argv: Argv,
    container: str,
    *,
    hostname: str | None = None,
    kernel: str | None = None,
    shared_tmp: bool = False,
    isolated: bool = False,
) -> tuple[Env, Argv]:
    """Harden session with the verified Android Termux extensions and bindings from M0 spike.

    The upstream login options that only work when IS_TERMUX (true on Termux,
    false in this app) are implemented HERE so they stay real for our users:
    `hostname`/`kernel` shape the `--kernel-release` line we own; `shared_tmp`
    binds one app-wide dir to /tmp; `isolated` turns the Android hardening
    binds off (keeping teardown safety)."""
    if not argv:
        return env, argv

    # Locate rootfs from --rootfs argument
    rootfs_path: Path | None = None
    for token in argv:
        if token.startswith("--rootfs="):
            raw = token[len("--rootfs=") :]
            if raw != ".":
                rootfs_path = Path(raw)
            break

    # If rootfs was relative or missing, query proot_service storage
    if rootfs_path is None or not rootfs_path.is_dir():
        from core import storage_paths

        candidate = storage_paths.containers_dir() / container / "rootfs"
        if candidate.is_dir():
            rootfs_path = candidate

    # Ensure shm and l2s directories on host filesystem
    shm_bind: str | None = None
    sysdata_binds: list[str] = []
    if rootfs_path and rootfs_path.is_dir():
        shm = rootfs_path / "tmp"
        shm.mkdir(parents=True, exist_ok=True)
        os.chmod(shm, 0o1777)  # noqa: S103 - sticky bit required for /dev/shm
        shm_bind = f"--bind={shm}:/dev/shm"

        # PROOT_L2S_DIR must be a REAL directory at the RESOLVED path: proot
        # uses the value verbatim (no realpath) while it canonicalizes the
        # rootfs, and an L2S chain written under one Android spelling of the
        # app dir is unresolvable through the other (/data/data vs
        # /data/user/0) — the dpkg ".dpkg-new ENOENT" failure (oonid/pr#35).
        l2s = rootfs_path.resolve() / ".l2s"
        if l2s.is_symlink():
            l2s.unlink()  # a planted symlink would send every chain elsewhere
        l2s.mkdir(parents=True, exist_ok=True)
        env["PROOT_L2S_DIR"] = str(l2s)

        # Fake sysdata stubs: masks /sys/fs/selinux with an empty directory
        # so dpkg/passwd/chage know SELinux is absent rather than failing with
        # ENOENT on Android SELinux transitions.
        proot_service.setup_fake_sysdata(str(rootfs_path))
        sysdata_binds = proot_service.fake_sysdata_bindings(str(rootfs_path))

        # bwrap (used by glycin, gdk-pixbuf's SVG/image loader) sets up its uid
        # map by reading /proc/sys/kernel/overflowuid|gid — Android blocks both
        # the read and the real file, so bwrap exits and every GTK image load
        # fails (device: "Loader process exited early … glycin-svg" → the XFCE
        # panel aborts and the desktop stays black). Stubbing the two files lets
        # bwrap get past the uid-map step; glycin then falls back to running
        # unsandboxed, which is exactly what we want under proot.
        sysdata_dir = rootfs_path / "sysdata"
        sysdata_dir.mkdir(parents=True, exist_ok=True)
        for name in ("overflowuid", "overflowgid"):
            stub = sysdata_dir / name
            if not stub.exists():
                try:
                    stub.write_text("65534\n", encoding="utf-8")
                except OSError:
                    continue
            sysdata_binds.append(f"--bind={stub}:/proc/sys/kernel/{name}")

        # APT reliability: under proot on Android, apt's sandbox user (_apt)
        # cannot read cache archives, and dpkg fsync slows down operations.
        apt_conf_dir = rootfs_path / "etc" / "apt" / "apt.conf.d"
        if apt_conf_dir.is_dir():
            conf_file = apt_conf_dir / "99-proot.conf"
            if not conf_file.exists():
                try:
                    conf_file.write_text(
                        'APT::Sandbox::User "root";\nAcquire::Retries "3";\nDPkg::Lock::Timeout "60";\n',
                        encoding="utf-8",
                    )
                except OSError:
                    pass

    # Hardened Android extensions (device-proven in M0 spike)
    # Only injected before the inner guest command on Android
    inner_idx = len(argv)
    for idx, arg in enumerate(argv[1:], start=1):
        if not arg.startswith("-"):
            inner_idx = idx
            break

    head = argv[:inner_idx]
    tail = argv[inner_idx:]

    def _add_if_missing(flag: str) -> None:
        if flag not in head:
            head.append(flag)

    is_android = bool(os.environ.get("ANDROID_NATIVE_LIBRARY_DIR") or Path("/data/app").exists())
    if is_android:
        uname_m = platform.machine() or "aarch64"

        def _clean(value: str | None, fallback: str) -> str:
            # --kernel-release is a backslash-separated proot string: strip
            # anything that would break it rather than injecting raw input.
            if not value:
                return fallback
            cleaned = str(value).replace("\\", " ").replace("\n", " ").strip()
            return cleaned or fallback

        host = _clean(hostname, "localhost")
        release = _clean(kernel, platform.release() or "unknown")
        kernel_fake = (
            f"--kernel-release=\\Linux\\{host}\\{release}\\#1 SMP PREEMPT_DYNAMIC "
            f"Fri, 10 Oct 2025 00:00:00 +0000\\{uname_m}\\localdomain\\-1\\"
        )
        if not any(a.startswith("--kernel-release=") for a in head):
            head.append(kernel_fake)

        # --isolated (upstream suppresses its Termux binds under this flag) is
        # implemented HERE: our equivalent is dropping the Android convenience
        # binds while keeping teardown safety. A user asking for isolation
        # gets exactly that — fewer host paths visible in the guest.
        if not isolated:
            _add_if_missing("--kill-on-exit")
            _add_if_missing("--link2symlink")
            _add_if_missing("--sysvipc")
            _add_if_missing("-L")
            # Standard devices & stdio streams required by proot on Android
            _add_if_missing("--bind=/dev/urandom:/dev/random")
            _add_if_missing("--bind=/proc/self/fd:/dev/fd")
            _add_if_missing("--bind=/proc/self/fd/0:/dev/stdin")
            _add_if_missing("--bind=/proc/self/fd/1:/dev/stdout")
            _add_if_missing("--bind=/proc/self/fd/2:/dev/stderr")

            if shm_bind:
                _add_if_missing(shm_bind)

            for b in sysdata_binds:
                _add_if_missing(b)
        else:
            # Isolation still needs the session to die with the app.
            _add_if_missing("--kill-on-exit")

        # --shared-tmp (upstream: Termux prefix /tmp → guest /tmp) is real
        # here too: one app-wide host dir, created on demand, shared by every
        # container that opts in.
        if shared_tmp:
            try:
                shared = storage_paths.data_root() / "shared-tmp"
                shared.mkdir(parents=True, exist_ok=True)
                shared.chmod(0o1777)
                _add_if_missing(f"--bind={shared}:/tmp")
            except OSError as exc:
                logger.debug("shared_tmp unavailable: %r", exc)

    env.setdefault("TERM", "xterm-256color")
    env.setdefault("COLORTERM", "truecolor")
    # uv under proot: hardlinking the wheel cache into place can leave paths
    # unreadable through proot's link2symlink parking (observed on device when
    # running uvx: the unpacked METADATA file in uv's archive cache came back
    # ENOENT). Copy mode avoids the link quirk entirely (D-030).
    env.setdefault("UV_LINK_MODE", "copy")

    return env, head + tail


def _parse_proot_cmd_line(line: str) -> tuple[Env, Argv]:
    """Parse upstream's printed `env -i KEY=val … <argv>` line into (env, argv).

    Upstream prints the command wrapped with backslash-newline continuations;
    shlex would read the escaped newline as a literal "n", so the
    continuations are folded into spaces before splitting.
    """
    line = line.replace(chr(92) + "\r\n", " ").replace(chr(92) + "\n", " ")
    tokens = shlex.split(line)
    if not tokens or tokens[0] != "env":
        raise RuntimeError(
            f"unexpected --get-proot-cmd output (expected 'env -i …'): {line[:200]!r}"
        )
    rest = tokens[1:]
    if rest and rest[0] == "-i":
        rest = rest[1:]
    env: Env = {}
    split_at = len(rest)
    for position, token in enumerate(rest):
        if not _ASSIGNMENT_RE.match(token):
            split_at = position
            break
        key, _, value = token.partition("=")
        env[key] = value
    argv = rest[split_at:]
    if not argv:
        raise RuntimeError(f"--get-proot-cmd printed no command: {line[:200]!r}")
    for key in _HOST_ESSENTIALS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    return env, argv


def session_argv(container: str) -> tuple[Env, Argv]:
    """The guest session's (env, argv) exactly as upstream builds it, hardened with M0 spike flags."""
    env, argv = _parse_proot_cmd_line(proot_service.get_proot_cmd(container))
    return _harden_session(env, argv, container)


def session_argv_with_options(container: str, options: dict | None = None) -> tuple[Env, Argv]:
    """(env, argv) for `pd login <c> --get-proot-cmd` with the upstream login
    options the "Shell with options…" dialog wraps one-to-one: user,
    work_dir, env, bind, shared_tmp, shared_home, shared_x11, fix_low_ports
    (→ upstream's redirect_ports destination), isolated, hostname, kernel,
    emulator. Interactive shell: no login_cmd, exactly like `pd login <c>`."""
    opts = options or {}
    login_opts: dict[str, object] = {}
    user = str(opts.get("user") or "root").strip()
    if user and user != "root":
        login_opts["user"] = user
    if opts.get("work_dir"):
        login_opts["work_dir"] = str(opts["work_dir"])
    if opts.get("env"):
        login_opts["env"] = [str(item) for item in opts["env"]]
    if opts.get("bind"):
        login_opts["bind"] = [str(item) for item in opts["bind"]]
    for key in ("shared_tmp", "shared_home", "shared_x11", "isolated"):
        if opts.get(key):
            login_opts[key] = True
    if opts.get("emulator"):
        # upstream treats --emulator as a QEMU BINARY PATH, not a flag
        login_opts["emulator"] = str(opts["emulator"])
    if opts.get("hostname"):
        login_opts["hostname"] = str(opts["hostname"])
    if opts.get("kernel"):
        login_opts["kernel"] = str(opts["kernel"])
    if opts.get("fix_low_ports"):
        login_opts["redirect_ports"] = True
    if opts.get("login_cmd"):
        # The guest command after `--` (display scripts, or an explicit shell
        # fallback when the image has no bash).
        login_opts["login_cmd"] = [str(item) for item in opts["login_cmd"]]
    line = proot_service.get_proot_cmd_with_options(container, **login_opts)
    env, argv = _parse_proot_cmd_line(line)
    return _harden_session(
        env,
        argv,
        container,
        hostname=str(opts.get("hostname") or "") or None,
        kernel=str(opts.get("kernel") or "") or None,
        shared_tmp=bool(opts.get("shared_tmp")),
        isolated=bool(opts.get("isolated")),
    )


def run_argv(container: str, run_args: list[str], work_dir: str | None = None) -> tuple[Env, Argv]:
    """(env, argv) for `proot-distro run <c> -- args` — upstream prints it
    (get_proot_cmd=True, so it never execs in-process), then we harden it."""
    env, argv = _parse_proot_cmd_line(proot_service.run_command_argv(container, run_args, work_dir))
    return _harden_session(env, argv, container)


def command_argv(
    container: str, command: list[str], work_dir: str | None = None
) -> tuple[Env, Argv]:
    """(env, argv) for `proot-distro login <c> -- <command>` — the arbitrary
    guest-command path (probes, installs, the display server). Upstream builds
    `[login_shell, "-c", shlex.join(login_cmd)]` for a non-empty login_cmd and
    skips the interactive-shell check entirely, so the Entrypoint/Cmd refusal
    never applies here. Callers that need shell syntax pass
    `["/bin/sh", "-lc", script]`."""
    if not command or not any(token.strip() for token in command):
        raise ValueError("command must not be empty")
    login_opts: dict[str, object] = {"login_cmd": list(command)}
    if work_dir:
        login_opts["work_dir"] = work_dir
    line = proot_service.get_proot_cmd_with_options(container, **login_opts)
    env, argv = _parse_proot_cmd_line(line)
    return _harden_session(env, argv, container)
