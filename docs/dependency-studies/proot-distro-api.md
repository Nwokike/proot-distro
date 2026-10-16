# proot-distro 5.10.0 — Exhaustive API Reference (integration bible)

> Installed source: `.venv/Lib/site-packages/proot_distro` (v5.10.0).
> Companion contract summary: `docs/reference/dep-proot-distro.md` (terse contract).
> This document is the exhaustive companion. Every claim verified against installed
> source (`file:line`) unless marked **unverified**.
> Context: `docs/roadmap.md`, `docs/decisions.md` (D-001 wrap-never-fork, D-010 flet 1.0.4).
> Project rule: Flet Android app wraps proot-distro in-process on Android (grp shimmed);
> **no patching of upstream** — steer via public config surface only.

---

## 1. Identity

| Item | Value | Source |
|---|---|---|
| Package | `proot-distro` **5.10.0** | `proot_distro-5.10.0.dist-info/METADATA` (`Version: 5.10.0`) |
| License | **GPL-3.0-only** (`License-Expression: GPL-3.0-only`, `License-File: LICENSE`) | METADATA head, `dist-info/licenses/LICENSE` |
| Summary | "PRoot-Distro is a lightweight rootless Linux container management utility built around proot." | METADATA |
| Requires-Python | `>=3.9` | METADATA |
| Runtime deps | **Zero** (only `pytest>=7; extra == "test"` test extra) | METADATA `Requires-Dist` |
| Author | Termux (@sylirre) | `constants.py:31` |
| Program names | `PROGRAM_NAME='proot-distro'`, `CANONICAL_PROGRAM_NAME='PRoot-Distro'` | `constants.py:32-33` |
| Entry points | `pd = proot_distro.cli:main`, `proot-distro = proot_distro.cli:main` | `dist-info/entry_points.txt` |
| `__init__.py` | 25 lines, exports nothing; docstring names `cli.main` as public entry | `__init__.py:1-25` |
| Size | **1.4 MiB** package dir; **93** RECORD entries; **77** `*.py` files | `du`, `RECORD` (93 lines), `find *.py \| wc -l` (=77) |
| Completions | `_proot-distro`, `proot-distro.bash`, `proot-distro.fish` | `completions/` |
| Top-level modules | `__init__`, `arch`, `atomic`, `cli`, `compress`, `constants`, `dirfd`, `execenv`, `guestfile`, `l2s`, `locking`, `message`, `names`, `parser`, `paths`, `progress`, `session`, `shm`, `statedir`, `sysdata` (19) | dir listing |
| `commands/` | `__init__`, `backup`, `build`, `clear_cache`, `copy`, `install`, `install_local`, `kill`, `list`, `ps`, `push`, `remove`, `rename`, `reset`, `restore`, `run`, `search`, `sync` + `login/` (8 files) + `help/` (3 files) | dir listing |
| `helpers/` | `__init__`, `build_cache`, `dockerfile`, `download`, `layer_diff`, `oci_writer`, `rootfs`, `tar_extract` + `build_engine/` (11 files) + `docker/` (9 files) | dir listing |
| CLI commands (18) | install, remove, rename, reset, login, list, backup, restore, clear-cache, copy, sync, run, build, push, ps, kill, search, help | `cli.py:64-84` (`_COMMAND_HANDLERS`) |

---

## 2. Complete module-by-module API inventory

Conventions used below: `command_* (args)` all take a single argparse namespace
(see `parser.py:161-415` `build_parser`) and return `None`, exiting via
`crit_error` + `sys.exit(1)` on error. `rootfs_fd` means a pinned directory
file descriptor (dirfd convention, §3.7), **not** a path.

### 2.1 Top level

#### `__init__.py` (25 lines) — package doc only, no exports.
- Public entry is `proot_distro.cli.main` (`__init__.py:22-25`).

#### `cli.py` (345 lines) — process entry, dispatch, global guards.
- `main() -> None` (`cli.py:246`) — parse, refuse nested proot, ensure proot, dispatch handler; `sys.exit(0/1)` paths (`cli.py:271,275,301` = help/usage exits 0; `cli.py:114,145,151,166,175,227,292,318,326,343` = error exits 1).
- `ensure_proot_installed() -> None` (`cli.py:122`) — verify proot usable; TTY-only offer to install on Termux.
- `_ensure_proot_available(first_canonical: str) -> None` (`cli.py:178`) — startup probe; exempts build/push/kill/ps/search.
- `_refuse_nested_proot() -> None` (`cli.py:90`) — TracerPid check; always runs before any command.
- `_dispatch_help(raw_args) -> bool` (`cli.py:197`); `_reject_unknown_command(raw_args) -> None` (`cli.py:213`); `_split_separator(canonical, raw_args, args)` (`cli.py:230`) — sets `args.login_cmd` / `args.run_args` from tokens after `--`.
- `_sigquit_to_keyboard_interrupt(signum, _frame)` (`cli.py:86`) — installed as SIGQUIT handler (`cli.py:258`: `signal.signal(signal.SIGQUIT, ...)`).
- `_COMMAND_HANDLERS` dict (`cli.py:64`) — the 18 canonical names above.

#### `parser.py` (417 lines) — argparse surface (the stable CLI contract).
- `build_parser() -> _PdArgumentParser` (`parser.py:161`).
- `required_args_for(canonical: str, args) -> list` (`parser.py:87`) — required-arg table.
- `REQUIRED_ARGS` (`parser.py:66`) — install→image_ref; remove→target; rename→orig_name+new_name; reset/login/backup/run→container_name; copy/sync→source+destination; push→image_ref; search→query.
- `ALIAS_TO_CANONICAL` (`parser.py:103`) — `add/i/in/ins→install`, `rm→remove`, `sh→login`, `li/ls→list`, `bak/bkp→backup`, `clear/cl→clear-cache`, `cp→copy`, `s/se→search`, `h/he/hel→help`.
- `_PdArgumentParser.errors(self, message: str) -> None` (`parser.py:49`) — parse error → own message + `sys.exit(1)` (`parser.py:60`).
- `_add_login_or_run_common(p)` (`parser.py:116`) — shared login/run flags: `-u/--user` (default `root`); `-P/--redirect-ports` (+ `--fix-low-ports` alias on login); `--isolated`/`--minimal` (mutually exclusive, Termux only); `--shared-home`/`--termux-home` (same dest), `--shared-tmp`, `--shared-x11`; `-b/--bind` append; `--no-link2symlink/--no-sysvipc/--no-kill-on-exit` (Termux only); `--emulator PATH`; `--kernel STRING`; `--hostname STRING`; `-w/--work-dir PATH`; `-e/--env VAR=VALUE` append; `-d/--detach`.
- Per-command builders: `_install` (`parser.py:194`: `image_ref?`, `-n/--name/--override-alias→custom_container_name`, `-a/--architecture→override_arch`, `--allow-insecure`); `_search` (`parser.py:217`); `_remove` (`parser.py:229`); `_rename` (`parser.py:245`); `_reset` (`parser.py:254`); `_login` (`parser.py:262`: `container_name?`, common flags, `--get-proot-cmd`, `login_cmd*`, `-h/--help`); `_list` (`parser.py:272`); `_backup` (`parser.py:280`); `_restore` (`parser.py:298`); `_clear_cache` (`parser.py:308`); `_copy` (`parser.py:321`); `_sync` (`parser.py:334`); `_build` (`parser.py:347`); `_push` (`parser.py:381`); `_run` (`parser.py:395`); `_ps` (`parser.py:404`); `_kill` (`parser.py:411`).

#### `constants.py` (123 lines) — import-time env contract + paths. MUST set env before first import.
- `PROGRAM_AUTHOR`, `PROGRAM_NAME`, `CANONICAL_PROGRAM_NAME` (`constants.py:31-33`).
- `TERMUX_APP_PACKAGE = os.environ.get("TERMUX_APP__PACKAGE_NAME", "com.termux")` (`constants.py:47`).
- `TERMUX_HOME = os.environ.get("TERMUX__HOME", f"/data/data/{PKG}/files/home")` (`constants.py:48`).
- `TERMUX_PREFIX = os.environ.get("TERMUX__PREFIX", f"/data/data/{PKG}/files/usr")` (`constants.py:51`).
- `_detect_termux() -> bool` (`constants.py:55`) — True when ≥2 of: android-ish platform / `/system/build.prop` or `/data/app` exists; `TERMUX_APP__APP_VERSION_NAME` or `TERMUX_VERSION` set; `TERMUX_PREFIX` R+X accessible.
- `IS_TERMUX: bool` (`constants.py:68`) — computed once at import.
- `RUNTIME_DIR`, `BASE_CACHE_DIR` (`constants.py:80-88`) — Termux: `$PREFIX/var/lib/proot-distro` + `cache` under it; else `$XDG_DATA_HOME/proot-distro` and `$XDG_CACHE_HOME/proot-distro` (fallback `~/.local/share`, `~/.cache`).
- `CONTAINERS_DIR` (`constants.py:89`), `SESSIONS_DIR` (`constants.py:92`), `LEGACY_ROOTFS_DIR` (`constants.py:95`), `LAYER_CACHE_DIR` (`constants.py:98`), `MANIFEST_CACHE_DIR` (`constants.py:99`).
- `DEFAULT_PRIMARY_NS='8.8.8.8'`, `DEFAULT_SECONDARY_NS='8.8.4.4'` (`constants.py:105-106`).
- `DEFAULT_PATH_ENV` (`constants.py:109/115`) — Termux appends `$PREFIX/bin:/system/bin:/system/xbin` to the standard sbin/bin/games list.
- `DEFAULT_FAKE_KERNEL_RELEASE='6.17.0-PRoot-Distro'` (`constants.py:120`),
  `DEFAULT_FAKE_KERNEL_VERSION='#1 SMP PREEMPT_DYNAMIC Fri, 10 Oct 2025 00:00:00 +0000'`
  (`constants.py:121-123`).

#### `arch.py` (315 lines) — CPU arch + proot/emulator resolution
- `get_device_cpu_arch() -> str` (`arch.py:41`) — `uname -m`; collapses
  armv7l/armv8l to `arm`.
- `supports_32bit() -> bool` (`arch.py:53`) — x86_64/amd64 gives True; aarch64/arm64
  runs a `personality(PER_LINUX32)` probe via ctypes (False on exception); anything
  else gives True.
- `_elf_arch(ident) -> str` (`arch.py:98`); `_ELF_MACHINE_MAP` (`arch.py:84`:
  3=i686, 40=arm, 62=x86_64, 183=aarch64, 243=riscv64); `_ELF_HEADER_BYTES=20`
  (`arch.py:95`).
- `detect_installed_arch(container_name_or_rootfs: str, *, rootfs_fd=None) -> str`
  (`arch.py:116`) — ELF-header probe of an installed container's shell binaries.
- `_KNOWN_ARCHS` (`arch.py:163`); `_DOCKER_TO_PROOT` (`arch.py:167`: arm64=aarch64,
  arm/v7+arm=arm, 386=i686, amd64=x86_64, riscv64=riscv64).
- `normalize_arch(arch: str)` (`arch.py:177`) — native, bare Docker, or
  `linux/`-prefixed platform string gives the canonical name, or **None** when
  unrecognised.
- `ARCH_UNAME_M` (`arch.py:195` — aarch64=aarch64, arm=armv7l, i686=i686,
  x86_64=x86_64, riscv64=riscv64) — feeds the `--kernel-release` uname spoof.
- `_QEMU_BIN_NAMES` (`arch.py:204`), `_QEMU_PKGS` (`arch.py:212`).
- `get_proot_bin() -> str` (`arch.py:221`) — `PD_PROOT_BIN` validated (must exist +
  be executable, returned absolute), else `shutil.which("proot")` absolutised; never
  a bare name (the docstring documents the image-controlled-PATH exec hole this
  prevents); `sys.exit(1)` on failure (`arch.py:248,253`).
- `get_emulator_args(dist_arch: str, device_arch: str, emulator_override: str = '') -> list`
  (`arch.py:257`) — `[]` when native (including arm-on-aarch64 with 32-bit support and
  i686-on-x86_64); otherwise `-q <absolute qemu>` plus whichever of these Android binds
  exist: `/apex`, `/linkerconfig/ld.config.txt`, `$PREFIX`, `/system`, `/vendor`,
  `/plat_property_contexts`, `/property_contexts`. Exits 1 on a bad override, an
  unsupported arch, or a missing qemu (`arch.py:281,297,304`).

#### `atomic.py` (264 lines) — crash-safe state writes
- `atomic_replace(path: str, *, suffix: str = '.tmp')` contextmanager (`atomic.py:93`)
  — yields an open fd on a tmp sibling; renames on success.
- `atomic_write(path: str, mode: str = 'wb', *, suffix: str = '.tmp', **kwargs)`
  contextmanager (`atomic.py:131`) — atomic_replace with the descriptor already
  wrapped in a file object.
- `publish_file(src_path: str, dest_path: str) -> None` (`atomic.py:145`).
- Internals: `_state_location` (`atomic.py:78`), `_close_quietly` (`atomic.py:179`),
  `_replace_at` (`atomic.py:187`), `_publish_at` (`atomic.py:210`),
  `_replace_by_name` (`atomic.py:243`).

#### `compress.py` (176 lines) — zstd capability gate (roadmap parking-lot O-7)
- `ZSTD_AVAILABLE` (`compress.py:62`), `ZSTD_MAGIC` (`compress.py:65`),
  `ZSTD_LEVEL=10` (`compress.py:75`).
- `unsupported_msg(subject: str) -> str` (`compress.py:87`);
  `unavailable_msg(subject: str) -> str` (`compress.py:96`).
- `header_is_zstd(header: bytes) -> bool` (`compress.py:105`);
  `file_is_zstd(path: str) -> bool` (`compress.py:110`).
- `require_read_support(path: str, subject: str = '') -> None` (`compress.py:123`)
  — raises `RuntimeError` when a zstd archive cannot be read (`compress.py:132`).
- `require_read_support_fd(fd: int, subject: str) -> None` (`compress.py:137`)
  — raises `RuntimeError` (`compress.py:149`).
- `require_write_support() -> None` (`compress.py:152`) — raises `RuntimeError`
  (`compress.py:155`).
- `open_tar_writer(output_path, fileobj=None, level: int = ZSTD_LEVEL)`
  contextmanager (`compress.py:159`).

#### `dirfd.py` (1361 lines) — the descriptor-pinning convention (largest core module)
- Open/pin: `is_refusal(exc) -> bool` (`dirfd.py:102`), `temp_name(name, suffix)`
  (`dirfd.py:107`), `opendir(path) -> int` (`dirfd.py:135`),
  `opendir_at(dir_fd, name) -> int` (`dirfd.py:140`),
  `reopendir(fd, name='') -> int` (`dirfd.py:145`),
  `open_file_at(dir_fd, name, flags, mode=0o644)` (`dirfd.py:157`),
  `open_regular_at(dir_fd, name, flags, mode=0o644)` (`dirfd.py:162`),
  `open_new_at(dir_fd, name, mode=0o644, *, readable=False)` (`dirfd.py:188`),
  `makedirs_under/makedirs_at/opendir_under/descend_at`
  (`dirfd.py:218,252,280,316`), `unlink_quietly` (`dirfd.py:366`),
  `listdir_at -> list` (`dirfd.py:378`), `lstat_at` (`dirfd.py:384`),
  `exists_at -> bool` (`dirfd.py:389`).
- Metadata: `copy_metadata(src_fd, dst_fd, src_st=None)` (`dirfd.py:416`),
  `set_times_at` (`dirfd.py:435`), `make_writable` (`dirfd.py:469`),
  `chmod_at(dir_fd, name, mode, *, only_dir=False, single_link=False) -> bool`
  (`dirfd.py:478`).
- Content copy (sparse-aware): `copy_data` (`dirfd.py:631`),
  `copy_file_at(..., *, replace=False)` (`dirfd.py:660`),
  `copy_symlink_at(..., *, replace=False)` (`dirfd.py:728`).
- Tree walk/copy: `Levels` class (`dirfd.py:801`), `MAX_OPEN_LEVELS=64`
  (`dirfd.py:792`), `count_tree_at -> int` (`dirfd.py:937`),
  `copy_tree_at(src_dir_fd, dst_dir_fd, *, rel='', merge=False, on_entry=None, on_skip=None, on_error=None)`
  (`dirfd.py:982`).
- Removal: `rmtree_at(dir_fd, name, *, force=False, on_error=None, on_remove=None) -> bool`
  (`dirfd.py:1177`), `remove_tree(path, *, on_error=None, on_remove=None) -> bool`
  (`dirfd.py:1314`).
- Constants: `_O_RD_DIR` (`dirfd.py:73`), `_O_PATH_ANY/_O_PATH_DIR`
  (`dirfd.py:78-79`), `REFUSED` (`dirfd.py:82`), `TMP_SUFFIX='. ~pd_copy'`
  (`dirfd.py:87`), `NAME_MAX=255` (`dirfd.py:90`).

#### `execenv.py` (123 lines) — exec-safety env rules
- `IDENTITY_ENV_KEYS=('PD_CONTAINER','PD_IMAGE','PD_IMAGE_ID','container')`
  (`execenv.py:72`); `CONTAINER_MARKER='proot-distro'` (`execenv.py:73`);
  `MAX_ENV_STRING_BYTES=32*4096` (`execenv.py:81`);
  `_HOST_EXEC_PREFIXES=('LD_','PROOT_')` (`execenv.py:60`).
- `is_host_exec_var(key: str) -> bool` (`execenv.py:85`) — LD_\*/PROOT_\* affect the
  host-side exec; image/Dockerfile values in that namespace are refused.
- `is_exportable(key: str, value: str) -> bool` (`execenv.py:96`) — False on NUL,
  unencodable code points, or length at/over MAX (each used to be a traceback or E2BIG).
- `__all__` (`execenv.py:120`).

#### `guestfile.py` (402 lines) — safe guest-tree reads (l2s-aware, capped)
- `open_guest_file(rootfs_dir, guest_path, *, root_fd=None)` (`guestfile.py:297`)
  — text handle (decode errors replaced) or None.
- `read_guest_bytes(rootfs_dir, guest_path, size, *, root_fd=None)`
  (`guestfile.py:315`) — first *size* bytes or None (the ELF-probe reader).
- `read_guest_file(rootfs_dir, guest_path, *, root_fd=None)` (`guestfile.py:356`);
  `read_capped(fh)` (`guestfile.py:347`); `guest_file_exists(...) -> bool`
  (`guestfile.py:373`).
- `MAX_ID_FILE_BYTES=1<<20` (`guestfile.py:77`); `_MAX_SYMLINK_HOPS=40`,
  `_MAX_PATH_COMPONENTS=4096` (`guestfile.py:63,70`).
- `__all__` (`guestfile.py:396`).

#### `l2s.py` (269 lines) — link2symlink stand-ins + rename rewrite
- `resolve_l2s_target(symlink_full, target, rootfs)` (`l2s.py:56`);
  `open_l2s_backing(rootfs, l2s_path, *, rootfs_fd=None)` (`l2s.py:116`);
  `rewrite_l2s_targets(rootfs_fd, rootfs, old_prefix)` (`l2s.py:163`);
  `_rewrite_walk` (`l2s.py:214`); `_rewrite_link` (`l2s.py:256`).
- A SIGINT/SIGQUIT warn-and-continue guard wraps the critical section
  (`l2s.py:195-211`).
- `_L2S_NAME_PREFIXES=('.proot.l2s.','.l2s.')` (`l2s.py:53`).

#### `locking.py` (764 lines) — flock-based container/build locks
- `LOCKS_DIR=RUNTIME_DIR/locks` (`locking.py:92`); `_BUILD_LOCKS_DIR`
  (`locking.py:93`); `_held_exclusive: set` (`locking.py:103`).
- `container_lock_path(name: str) -> str` (`locking.py:106`);
  `_build_lock_path(image_ref, arch)` (`locking.py:111`).
- `_locks_dir_fd(parts, create=False)` (`locking.py:133`);
  `_read_locks_dir_fd(parts)` (`locking.py:188`); `_open_lock_subdir(...)`
  (`locking.py:216`); `_lock_info_at(...)` (`locking.py:247`);
  `_lock_is_held_at(...)` (`locking.py:284`); `_probe_locks_dir(parts, held)`
  (`locking.py:324`); `busy_locks() -> list` (`locking.py:346`) — every lock held
  by another process as `(lock_path, hint)`.
- Exceptions: `_HostileLockPath` (`locking.py:369`), `_LockPathDenied`
  (`locking.py:376`), `LockStateUnknown` (`locking.py:388`).
- `_open_lock_file(...)` (`locking.py:398`);
  `open_lock_file_at(dir_fd, name, path='')` (`locking.py:435`);
  `_is_planted/_is_denied/_drop_planted` (`locking.py:466,478,483`).
- `_FlockBase` (`locking.py:507`): `__init__(exclusive, command, inheritable)`,
  `lock_path`, `holder_hint`, `blocked_detail`, `acquireself -> bool`,
  `disown()`, `release()`, `__enter__/__exit__`.
- `ContainerLock(_FlockBase)` (`locking.py:707`,
  `__init__(name, exclusive, command='', inheritable=False)`);
  `BuildLock(_FlockBase)` (`locking.py:739`,
  `__init__(image_ref, arch, command='build')`).

#### `message.py` (290 lines) — stderr UI (never patch)
- `C` colour dict (`message.py:113`, built by `_init_colors` at `message.py:107`):
  colours only when `sys.stderr.isatty() and not PD_FORCE_NO_COLORS`
  (`message.py:108`).
- `tty_safe_for_writes() -> bool` (`message.py:116`);
  `terminal_width(default=80) -> int` (`message.py:151`).
- `_quiet=False` (`message.py:168`); `set_quiet(value: bool)` (`message.py:171`);
  `is_quiet() -> bool` (`message.py:182`).
- `msg(*args)` (`message.py:187`); `log_info(text)` (`message.py:210`,
  quiet-suppressed); `log_error(text)` (`message.py:217`); `warn(text)`
  (`message.py:222`); `crit_error(text)` (`message.py:227`, caller then sys.exit(1)).
- `quote_path(text: str) -> str` (`message.py:242`);
  `quote_error(exc: BaseException) -> str` (`message.py:279`).

#### `names.py` (62 lines) — container-name gate
- `is_valid_name(name: str) -> bool` (`names.py:48`);
  `require_valid_name(name, kind='container name') -> None` (`names.py:53`, exits 1
  at `names.py:62`).
- `_NAME_RE='^[A-Za-z0-9][A-Za-z0-9_.-]*\\Z'` (`names.py:40`);
  `NAME_RULE_HINT` (`names.py:42`).

#### `paths.py` (874 lines) — on-disk layout API (M3 safe surface)
- `container_dir(name) -> str` (`paths.py:93`); `container_rootfs(name) -> str`
  (`paths.py:98`); `container_manifest(name) -> str` (`paths.py:103`).
- `_open_container_path(path, name, create)` (`paths.py:108`);
  `open_container_dir(name, *, create=False) -> int` (`paths.py:137`);
  `open_container_rootfs(name, *, create=False) -> int` (`paths.py:142`);
  `open_container_pair(name, *, create=False)` (`paths.py:147`) — returns
  `(container_fd, rootfs_fd)`.
- `container_is_installed(name) -> bool` (`paths.py:192`);
  `container_entry_lstat(name)` (`paths.py:209`); `_has_rootfs(root_fd, name)`
  (`paths.py:242`); `installed_container_names() -> list` (`paths.py:257`, sorted).
- `open_container_manifest(name)` (`paths.py:292`) — returns `(fd, stat)`;
  `read_container_manifest(name) -> dict` (`paths.py:320`);
  `manifest_image_config(data) -> dict` (`paths.py:346`);
  `container_image_config(name) -> dict` (`paths.py:365`);
  `container_image_origin(name) -> tuple` (`paths.py:380`) — `(image_ref, arch)`.
- `container_from_spec(spec)` (`paths.py:408`);
  `resolve_container_path(spec, *, deref_leaf=True) -> str` (`paths.py:523`);
  `refuse_src_dest_overlap(...)` (`paths.py:609`, exits on overlap);
  `resolve_container_child(spec, resolved, child, ...)` (`paths.py:663`).
- `PinnedPath` (`paths.py:701`: `path/dir_fd/leaf` slots at `paths.py:713-720`);
  `pin_path(spec, resolved, *, inside=False, create=False)` contextmanager
  (`paths.py:771`); `container_locks_for_spec_pair(src_spec, dst_spec, command)`
  (`paths.py:852`).

#### `progress.py` (146 lines) — TTY-gated bars (never patch)
- `fmt_size(n_bytes: int) -> str` (`progress.py:43` — B/KiB/MiB/GiB);
  `ByteCounter` (`progress.py:54`); `progress_active() -> bool` (`progress.py:80`,
  stderr-is-tty and not quiet);
  `draw_bytes_bar(done, total=0, *, label='', noun='processed')`
  (`progress.py:85`);
  `draw_count_bar(done, total, *, label='', unit='files')` (`progress.py:118`);
  `clear_bar()` (`progress.py:141`); `REDRAW_THRESHOLD_BYTES=262144`
  (`progress.py:40`).

#### `session.py` (509 lines) — live-session registry (ps/kill/facade feed)
- `SESSION_KINDS=('login','run')` (`session.py:88`);
  `_FLAG_FIELDS=('isolated','minimal','detach')` (`session.py:93`).
- `register_session(*, container, kind, command_argv, user, isolated=False, minimal=False, detach=False)`
  (`session.py:115`) — must be called by the process that immediately execs (so
  `os.getpid()` already equals the future proot PID); returns the locked,
  inheritable fd (keep referenced until exec) or None. Best-effort: never blocks
  a login.
- Record shape written as `<pid>.json` (`session.py:141-208`):
  `{pid, container, kind, command, user, start_time, isolated, minimal, detach}`.
- `active_sessions()` (`session.py:210`) — validated live records, pruning dead ones.
- `_record_pid` (`session.py:257`); `_validate_record` (`session.py:277`);
  `_read_record` (`session.py:342`); `session_file(pid)` (`session.py:367`);
  `session_is_live(pid)` (`session.py:376`); `session_holders(pid)`
  (`session.py:392`).
- `__all__` (`session.py:508`).

#### `shm.py` (118 lines) — Android shm/tmp setup
- `SHM_DIR_NAME='shm'` (`shm.py:61`); `SHM_DIR_MODE=0o1777` (1023) (`shm.py:65`);
  `GUEST_TMP_MODE=0o1777` (`shm.py:69`).
- `shm_dir(rootfs) -> str` (`shm.py:72`);
  `make_shm_dir(rootfs, *, container_fd=None)` (`shm.py:77`);
  `make_guest_tmp(rootfs, *, rootfs_fd=None)` (`shm.py:100`).
- `__all__` (`shm.py:118`).

#### `statedir.py` (265 lines) — trust-root guard for state writes
- `STATE_ROOTS=(RUNTIME_DIR, BASE_CACHE_DIR)` sorted by length
  (`statedir.py:62`); `MAX_STATE_JSON_BYTES=16MiB` (`statedir.py:77`).
- `read_state_file(fd, *, limit=MAX) -> bytes` (`statedir.py:82`);
  `split_state_path(path)` (`statedir.py:114`); `is_state_path(path) -> bool`
  (`statedir.py:142`); `open_state_dir(path, *, create=False) -> int`
  (`statedir.py:156`); `open_state_parent(path, *, create=False)`
  (`statedir.py:218`); `remove_state_tree(path, *, on_error=None, on_remove=None) -> bool`
  (`statedir.py:232`).

#### `sysdata.py` (641 lines) — fake /proc + /sys stubs for Android
- `host_cpu_ids() -> list` (`sysdata.py:103`); `fake_stat(cpus) -> str`
  (`sysdata.py:135`); `fake_uptime(cpus) -> str` (`sysdata.py:150`); `_FAKE_VMSTAT`
  (`sysdata.py:160`); `_FAKE_VERSION` (`sysdata.py:341`); `_FAKE_ENTRIES` table
  (`sysdata.py:352`).
- `sysdata_dir(rootfs) -> str` (`sysdata.py:368`);
  `setup_fake_sysdata(rootfs, *, container_fd=None)` (`sysdata.py:527`);
  `fake_sysdata_bindings(rootfs, *, container_fd=None) -> list`
  (`sysdata.py:604`).

### 2.2 `commands/` — one handler per CLI verb

#### `commands/install.py` (420 lines) — install from image / URL / local archive
- `command_install(args) -> None` (`install.py:138`) — namespace fields read:
  `image_ref`, `custom_container_name`, `override_arch`, `allow_insecure`
  (`install.py:140-188`). Flow: empty-name check → `require_valid_name` →
  `get_device_cpu_arch` + `normalize_arch` (exit 1 on unknown) → local/URL/image
  classification → `parse_reference` pre-validation (`InvalidReference` →
  crit+exit) → `_resolve_install_name` → `ContainerLock(exclusive)` →
  `_run_install`.
- `_is_local_path(ref) -> bool` (`install.py:74`); `_is_url(ref) -> bool`
  (`install.py:85`); `_derive_local_name(path) -> str` (`install.py:90`);
  `_cache_temp_file(prefix) -> str` (`install.py:107`).
- `_resolve_install_name(image_ref, local_path, url, custom_container_name)`
  (`install.py:192`) — exits on unresolvable names (`install.py:199,210,216,223`).
- `_run_install(install_name: str, image_ref: str, local_path, url, dist_arch: str, allow_insecure: bool = False) -> None`
  (`install.py:237`) — **called with the container lock already held**. Refuses
  existing containers (exit 1, `install.py:251-269`); `open_container_pair(create=True)`
  keeps both fds for the whole extraction (`install.py:305`); local→
  `install_from_local_file`, URL→`download_file` to cache temp then
  `install_from_local_file`, else `pull_image(image_ref, rootfs_fd, dist_arch,
  insecure=allow_insecure)` (`install.py:310-326`); writes `manifest.json` when
  metadata is not None (plain tarballs yield None, no manifest —
  `install.py:328-344`); then etc fixups via pinned `etc_fd` (`open_etc`,
  `write_resolv_conf_at`, `write_hosts_at`, `register_android_ids_at` —
  `install.py:357-379`) and `setup_fake_sysdata` (`install.py:381`).
  Failure map: `KeyboardInterrupt` → cleanup + exit 1 (`install.py:383-386`);
  `(EOFError, OSError, tarfile.TarError, RuntimeError)` → cleanup + exit 1
  (`install.py:387` + tail); bare `Exception` → cleanup + re-raise path
  (**unverified** exact tail lines — see §7).
- `_is_regular_at(dir_fd, name) -> bool` (`install.py:228`).
- `_ARCHIVE_EXTS` (`install.py:67` — 15 extensions incl. `.oci.tar*` variants).

#### `commands/install_local.py` (533 lines) — local archive / OCI layout install
- `install_from_local_file(archive_path: str, rootfs_fd: int, dist_arch: str)`
  (`install_local.py:486`) — **returns a metadata dict
  `{manifest, image_config, image_ref, arch}` for OCI images (a superset of
  `pull_image`'s return), or `None` for plain tarballs** (docstring,
  `install_local.py:486-502`). zstd gate first (`require_read_support`,
  `install_local.py:504`); streaming probe of ≤500 member headers
  (`install_local.py:509-518`); OCI branch indexes members and calls
  `_extract_oci` (`install_local.py:520-531`); else `detect_strip_count` +
  `extract_plain_tar` (`install_local.py:533-535`).
- `detect_strip_count(member_names: list) -> int` (`install_local.py:101`);
  `extract_plain_tar(archive_path, strip, rootfs_fd)` (`install_local.py:122`).
- OCI internals: `_oci_blob_path` (`install_local.py:137`), `_oci_open_member`
  (`install_local.py:150`), `_oci_read_capped` (`install_local.py:166`),
  `_oci_json_object` (`install_local.py:187`), `_oci_digest`
  (`install_local.py:211`), `_oci_read_json` (`install_local.py:228`),
  `_oci_read_blob_json` (`install_local.py:236`), `_oci_find_manifest_entry`
  (`install_local.py:249`), `_oci_cache_layer` (`install_local.py:299`),
  `_extract_oci` (`install_local.py:349`), `_index_oci_members`
  (`install_local.py:457`).
- Guards: `_BLOB_CHUNK=1MiB` (`install_local.py:57`),
  `_MAX_JSON_BYTES=16MiB` (`install_local.py:67`),
  `_MAX_OCI_MEMBERS=16384` (`install_local.py:77`),
  `_OCI_INDEX_NAME='index.json'` (`install_local.py:84`),
  `_OCI_BLOB_RE` (`install_local.py:85`), `_ROOTFS_DIRS` frozenset of 20
  (`install_local.py:93`).

#### `commands/login/__init__.py` (670 lines) — interactive shell (NEVER in-process)
- `command_login(args) -> None` (`login/__init__.py:81`) → `_command_login_inner`
  (`login/__init__.py:312`: `migrate_legacy_rootfs`, `open_container_pair`
  kept open, `FileNotFoundError` → crit+exit 1 at `login/__init__.py:324`) →
  `_login_with_rootfs(container_name, args, lock, container_fd, rootfs_fd)`
  (`login/__init__.py:336`).
- `_detect_dist_type(rootfs, rootfs_fd=None) -> str` (`login/__init__.py:98`) —
  `'termux'` iff the rootfs is a Termux installation.
- `_resolve_login_user(rootfs, container_name, user_arg, rootfs_fd=None) -> dict`
  (`login/__init__.py:118`).
- `_build_termux_env(container_name, extra_env, minimal, isolated)`
  (`login/__init__.py:202`); `_build_normal_env(container_name, login_user,
  login_home, extra_env, minimal, isolated)` (`login/__init__.py:243`).
- `_check_shell_available(rootfs, login_shell, container_name, rootfs_fd=None)`
  (`login/__init__.py:290`).
- `_login_with_rootfs` tail (verified `login/__init__.py:336-602` region): resolves
  `user/kernel/hostname/work_dir/redirect_ports/isolated/minimal/shared_home/
  shared_tmp/shared_x11/no_*` (Termux-only triple)/`bind/env/login_cmd` from the
  namespace; builds `inner` (termux: `$PREFIX/bin/login`, else
  `login_shell [-l | -c shlex.join(login_cmd)]`; `run` mode bypasses via
  `args._run_inner`); filters PATH components; resolves `child_env` user `--env`
  overrides; sets/clears `PROOT_L2S_DIR`; drops `LD_PRELOAD`
  (`login/__init__.py:336-470` region, exact line for each getattr **unverified**
  — see §7); `get_proot_bin()` absolute (`login/__init__.py:469` region);
  `--get-proot-cmd` prints the path-form command + mismatch warning and returns
  WITHOUT execing (`login/__init__.py:469-551` region); otherwise
  `register_session(kind='run' if run_inner else 'login')`, `--detach` →
  `spawn_detached` + `lock.disown()`, else `_exec_proot` (execvpe — the process
  becomes proot; `login/__init__.py:551-602` region).
- `_print_command(text: str)` (`login/__init__.py:603`) — stdout-as-bytes writer.
- `_exec_proot(proot_bin, proot_args, child_env, rootfs_fd: int)`
  (`login/__init__.py:628`) — `os.fchdir(rootfs_fd)` then `os.execvpe`; OSError/
  ValueError → crit+exit 1.
- Host TERM passthrough: `host_term = os.environ.get("TERM", "")`
  (`login/__init__.py:234`), `env["TERM"] = ... or "xterm-256color"`
  (`login/__init__.py:283`); COLORTERM likewise (`login/__init__.py:237,284`).
- `__all__ = ('command_login',)` (`login/__init__.py:670`).

#### `commands/login/proot_cmd.py` (311 lines) — argv assembly (fragile: isolate)
- `build_proot_args(*, proot_bin, rootfs, login_wd, rootfs_arg=None, container_fd=None, rootfs_fd=None, login_uid, login_gid, login_home, emu_args, need_emu, target_arch, hostname, kernel_release, dist_type, minimal, isolated, no_link2symlink, no_sysvipc, no_kill_on_exit, use_shared_home, shared_tmp, shared_x11, custom_binds, redirect_ports, inner)`
  (`proot_cmd.py:55`) — **all keyword-only** (27 params, verified from the def).
  **Exact argv order** (verified `proot_cmd.py:97-128`):
  1. `[proot_bin] + list(emu_args)`.
  2. `_add_proot_extensions` output (Termux only; no-ops entirely when
     `not IS_TERMUX` — `proot_cmd.py:137-138`).
  3. `--change-id=uid:gid` when `dist_type != "termux"`.
  4. `--rootfs=<rootfs_arg or rootfs>`, `--cwd=<login_wd>`,
     `--bind=/dev --bind=/proc --bind=/sys`.
  5. Non-minimal binds (`_add_non_minimal_binds`) when `not minimal`.
  6. `_add_custom_binds` (user `--bind`, overlap detection), then `-p` when
     `redirect_ports`.
  7. `inner` appended last.
- `_add_proot_extensions(args, *, target_arch, hostname, kernel_release,
  dist_type, minimal, no_link2symlink, no_sysvipc, no_kill_on_exit)`
  (`proot_cmd.py:130`) — emits `--kill-on-exit` (or warn when disabled),
  `--link2symlink` (non-termux only), `--sysvipc` (unless minimal),
  `--kernel-release=\Linux\<host>\<release>\<fake-ver>\<uname-m>\localdomain\-1\`
  (unless minimal), always `-L` (`proot_cmd.py:130-159`, verified).
- `_add_non_minimal_binds(...)` (`proot_cmd.py:161`) — Termux-dev binds
  (non-termux guests), Dalvik/storage/app binds (default mode only),
  system binds (not isolated, or when emulating), termux-guest cache dir,
  `--bind=$HOME:...` variants for shared-home, `$PREFIX/tmp:/tmp` and X11 for
  shared-tmp/x11 (all Termux-gated; verified `proot_cmd.py:161-217`).
- `_add_termux_dev_binds` (`proot_cmd.py:219`), `_add_dalvik_cache_binds`
  (`proot_cmd.py:246`), `_add_termux_app_binds` (`proot_cmd.py:264`),
  `_add_custom_binds(args, custom_binds)` (`proot_cmd.py:278`, exits on bad input
  per `build_proot_args` docstring).
- `rootfs` vs `rootfs_arg` (docstring, `proot_cmd.py:63-96`): the real exec passes
  `"."` after fchdir into the pinned rootfs (inode, not name);
  `--get-proot-cmd` passes the path explicitly with a printed mismatch warning.

#### `commands/login/bindings.py` (84 lines)
- `storage_bindings() -> list` (`bindings.py:35`) — `--bind` args for Android
  shared storage. `system_bindings() -> list` (`bindings.py:58`) — `--bind` args
  for Android system paths reachable by the guest.

#### `commands/login/detach.py` (179 lines) — background sessions
- `spawn_detached(proot_bin, proot_args, child_env, *, register_kwargs, rootfs_fd=None)`
  (`detach.py:58`) — double-fork daemon (setsid, pipe-reported PID, stdio to
  /dev/null); returns daemon PID or None; grandchild chdirs into `rootfs_fd`,
  calls `register_session(**register_kwargs)`, then execvpe (exec refusal is
  reported back through the pipe). Foreground never returns inside forked children.
- `_redirect_std_to_devnull()` (`detach.py:163`); `_safe_close(fd)`
  (`detach.py:172`); `__all__` (`detach.py:179`).

#### `commands/login/env.py` (320 lines) — guest env construction
- `ANDROID_HOST_ENV_VARS` 9-tuple (`env.py:62`); `IMAGE_ENV_BLOCKED` frozenset
  (`env.py:83` = host vars + identity keys + `MOZ_FAKE_NO_SANDBOX, PULSE_SERVER,
  TERM, COLORTERM`); `_PROFILE_INJECT_SKIP` (`env.py:96`); `_VALID_ENV_KEY_RE`
  (`env.py:50`); `_PROFILE_SNIPPET='termux-profile.sh'` (`env.py:53`).
- `read_manifest_env(container_name: str) -> list` (`env.py:104`) — image Env
  entries from manifest.json, `[]` when absent/invalid.
- `image_env_pairs(container_name: str)` (`env.py:119`) — `(key, value)` pairs an
  image's Env may contribute; `identity_env_pairs(container_name: str)`
  (`env.py:148`) — PD_CONTAINER/PD_IMAGE/PD_IMAGE_ID + `container=proot-distro`.
- `inject_termux_profile(rootfs: str, env: dict, *, rootfs_fd=None, termux_path=True) -> None`
  (`env.py:179`); `_open_profile_d(rootfs, rootfs_fd=None)` (`env.py:225`);
  `_write_profile_snippet(profile_fd, env, termux_path)` (`env.py:258`).

#### `commands/login/migrate.py` (107 lines) — legacy layout migration
- `migrate_legacy_rootfs(container_name: str) -> None` (`migrate.py:66`) — move
  `installed-rootfs/<name>` to `containers/<name>/rootfs`.
- `_legacy_dir_fd(container_name: str)` (`migrate.py:40`).

#### `commands/login/passwd.py` (113 lines) — guest user/group lookup
- `passwd_available(rootfs, *, root_fd=None) -> bool` (`passwd.py:60`);
  `shell_available(rootfs, guest_path, *, root_fd=None) -> bool` (`passwd.py:65`);
  `read_passwd_entry(rootfs, user, *, root_fd=None) -> list` (`passwd.py:70`);
  `passwd_field(parts, field_index) -> str` (`passwd.py:83`);
  `find_passwd_by_uid(rootfs, uid, *, root_fd=None) -> tuple` (`passwd.py:90`) —
  `(home, shell, primary_gid)` or `('','','')`;
  `read_group_gid(rootfs, group, *, root_fd=None) -> str` (`passwd.py:98`).
- `__all__` (`passwd.py:106`).

#### `commands/login/quoting.py` (45 lines) — `--get-proot-cmd` quoting
- `dq(s: str) -> str` (`quoting.py:35`) — POSIX double-quote only when needed.
- `_SAFE_CHARS` (`quoting.py:27`).

#### `commands/list.py` (272 lines) — containers + cached images
- `command_list(args) -> None` (`list.py:55`); `_list_containers(quiet: bool)`
  (`list.py:69`); `_list_images(quiet: bool)` (`list.py:107`).
- `_render_table(rows, widths)` (`list.py:176`); `_render_stacked(rows)`
  (`list.py:195`); `image_display_ref(image: dict) -> str` (`list.py:204`);
  `image_identifier(image: dict) -> str` (`list.py:217`);
  `_fmt_created(image, now)` (`list.py:222`); `_created_epoch(image) -> float`
  (`list.py:228`); `_fmt_age(seconds: float) -> str` (`list.py:262`).
- `_IMAGE_HEADERS=('IMAGE','ARCH','ID','SIZE','CREATED')` (`list.py:44`);
  `_TIMESTAMP_RE` (`list.py:49`); `_AGE_UNITS` (`list.py:252`).
- `__all__ = ('command_list',)` (`list.py:272`).

#### `commands/remove.py` (469 lines) — delete container or cached image
- `command_remove(args) -> None` (`remove.py:108`); `_remove_container(args)`
  (`remove.py:126`); `_remove_image(args)` (`remove.py:174`).
- `_resolve_images(identifier, arch) -> list` (`remove.py:203`);
  `_image_locks(identifier, targets) -> list` (`remove.py:244`);
  `_delete_images(targets, verbose)` (`remove.py:266`);
  `_unlink_targets(manifest_fd, layer_fd, targets, verbose) -> tuple`
  (`remove.py:318`) — `(failed, reclaimed)`;
  `_containers_from_images(targets) -> list` (`remove.py:374`);
  `_report_no_match(identifier, arch)` (`remove.py:395`).
- `_remove_path(path, on_remove=None) -> bool` (`remove.py:75`);
  `_MIN_ID_PREFIX=4` (`remove.py:72`).

#### `commands/rename.py` (115 lines) — rename + l2s rewrite
- `command_rename(args) -> None` (`rename.py:50`); `_do_rename(orig, new)`
  (`rename.py:85`) — renames the container directory and rewrites l2s symlinks
  (via `l2s.rewrite_l2s_targets`).

#### `commands/reset.py` (101 lines) — wipe + reinstall from cache
- `command_reset(args) -> None` (`reset.py:44`) — wipes the rootfs and reinstalls
  from the cached image manifest (offline-capable when layers are cached).

#### `commands/backup.py` (652 lines) — container to tar
- `command_backup(args) -> None` (`backup.py:451`) — namespace fields:
  `container_name`, `output`, `compression`, `verbose` (`backup.py:454-456`).
- `_run_backup(container_fd, rootfs_fd, container_name, rootfs_dir, manifest_path, output_path, compression, verbose)`
  (`backup.py:532`).
- `_compression_mode(filename) -> str` (`backup.py:103`);
  `_COMPRESS_EXTS` 10-tuple (`backup.py:76`); `_UNSUPPORTED_EXTS`
  (`backup.py:91`: `.tar.lz4`, `.tar.lz`); `_COMPRESSION_ARG_MAP`
  (`backup.py:94`: gzip/bzip2/xz/zstd/none).
- `_listing/_walk_tree/_each_entry` (`backup.py:123,131,203`);
  `_ReadCounter` (`backup.py:236`); `_strip_owner` (`backup.py:256`);
  `_add_path(...)` (`backup.py:264`); `_relax_permissions/_fix_permissions`
  (`backup.py:386,439`).

#### `commands/restore.py` (786 lines) — tar back to container
- `command_restore(args) -> None` (`restore.py:441`) — namespace fields: `archive`,
  `verbose` (`restore.py:458-459`). Destroys data (help warns — `pages.py` TOP_COMMANDS).
- `_detect_compression(header: bytes) -> str` (`restore.py:107`);
  `_MAGIC_COMPRESS` (`restore.py:85`); `_LEGACY_PREFIX='installed-rootfs'`
  (`restore.py:94`); `_MAX_MANIFEST_BYTES=16MiB` (`restore.py:104`).
- `_clear_existing_rootfs(root_fd)` (`restore.py:119`);
  `_remove_existing(dir_fd, name, member)` (`restore.py:160`);
  `_dest_path(member_name) -> tuple` (`restore.py:184`);
  `_is_rootfs_dest(parts) -> bool` (`restore.py:246`); `_Destinations` class
  (`restore.py:259`); `_write_directory/_write_regular/_write_hardlink`
  (`restore.py:372,391,416`); `_rootfs_is_a_directory(root_fd) -> bool`
  (`restore.py:774`).

#### `commands/clear_cache.py` (504 lines) — cache maintenance
- `command_clear_cache(args) -> None` (`clear_cache.py:225`) — empties
  BASE_CACHE_DIR, or sweeps layers for `--orphan`/`--build-cache`
  (`clear_cache.py:227-228`: `build_cache`, `orphan`, `verbose` namespace fields).
- `_tree_size(root_fd) -> int` (`clear_cache.py:168`);
  `_referenced_blob_names(with_build_index) -> set` (`clear_cache.py:300`);
  `_drop_build_index(verbose) -> tuple` (`clear_cache.py:341`);
  `_collect_orphans(dir_fd, keep) -> tuple` (`clear_cache.py:387`);
  `_sweep_layers(args, drop_build_index)` (`clear_cache.py:416`);
  `_remove_orphans(...)` (`clear_cache.py:466`).
- `_opendir_relaxing/_relax_cache_root/_open_cache_root`
  (`clear_cache.py:92,117,146`); `_open_layer_cache` (`clear_cache.py:366`).

#### `commands/copy.py` (389 lines) — host<->guest file copy/move
- `command_copy(args) -> None` (`copy.py:63`) — namespace: `verbose`, `move`,
  `recursive` (`copy.py:67-69`); exits 1 on bad specs
  (`copy.py:255,263,273,277,285,295,373,379,387`).
- `_do_copy(src, dest, verbose, move_mode, recursive)` (`copy.py:242`);
  `_copy_tree_pinned(src_pin, dest_pin, verbose, dest_display, *, merge=False)`
  (`copy.py:82`); `_move_pinned(src_pin, dest_pin, verbose=False)`
  (`copy.py:183`); `_opendir_pinned(pin)` (`copy.py:77`).

#### `commands/sync.py` (1101 lines) — directory mirroring (largest command)
- `command_sync(args) -> None` (`sync.py:881`) — namespace: `verbose`, `checksum`,
  `delete` (`sync.py:885-887`).
- `_Ctx` class (`sync.py:89`: `saw/note_failure/shown/src_shown/progress`);
  `_do_sync(src, dest, verbose, use_checksum, delete)` (`sync.py:895`);
  `_sync_single(src_pin, dest_pin, ctx)` (`sync.py:1008`);
  `_sync_directory(src_pin, dest_pin, ctx, delete)` (`sync.py:1062`);
  `_prune(dst_fd, ctx)` (`sync.py:1084`).
- Entry ops: `_needs_update` (`sync.py:190`), `_sync_dir` (`sync.py:237`),
  `_apply_dir_metadata` (`sync.py:274`), `_sync_symlink` (`sync.py:291`),
  `_refresh_file_metadata` (`sync.py:330`), `_sync_file` (`sync.py:380`),
  `_mirror_entries/_mirror_at` (`sync.py:554,663`), `_TMP_SUFFIX='. ~pd_sync'`
  (`sync.py:86`).

#### `commands/run.py` (152 lines) — image Entrypoint/Cmd executor
- `command_run(args) -> None` (`run.py:112`) — reads `container_name`, `run_args`,
  `work_dir` from the namespace; `require_valid_name`; refuse uninstalled;
  `_read_image_config` → Entrypoint/Cmd shape-check (`_string_list` exits on
  non-list — `run.py:72`); `run_args` replace Cmd but append to Entrypoint;
  error when neither Entrypoint/Cmd nor `--` args (`run.py:132`);
  WorkingDir→`args.work_dir` fallback `/` (`_working_dir`, `run.py:95`); then sets
  `args._run_inner = inner; args.login_cmd = []` and delegates to
  `command_login(args)` (`run.py:148-152`).
- `_read_image_config(container_name) -> dict` (`run.py:51`).

#### `commands/build.py` (475 lines) — Dockerfile → OCI image (no daemon)
- `command_build(args)` (`build.py:93`) — namespace fields: `path` (default `.`),
  `dockerfile`, `tags`, `build_args`, `override_arch`, `target_stage`,
  `emulator`, `outputs`, `install_as`, `no_cache`, `verbose`, `quiet`
  (`build.py:96-122`).
- `_read_dockerfile(dockerfile)` (`build.py:75`);
  `_make_build_tmp()` (`build.py:363`); `_fallback_build_tmp()` (`build.py:408`);
  `_parse_build_args(raw)` (`build.py:422`); `_derive_tag_from_path(build_dir,
  dockerfile)` (`build.py:434`); `_install_as_container(install_name, image_ref,
  target_arch, quiet)` (`build.py:464`).

#### `commands/push.py` (136 lines) — push built image to registry
- `command_push(args)` (`push.py:49`) — namespace: `image_ref`, `override_arch`,
  `quiet`, `allow_insecure` (`push.py:51-54`); `Network error` path at
  `push.py:113`.

#### `commands/ps.py` (137 lines) — active sessions table
- `command_ps(args) -> None` (`ps.py:50`); `_fmt_uptime(seconds) -> str`
  (`ps.py:117` — `0m44s/1h04m/2d03h` style); `_fmt_command(command) -> str`
  (`ps.py:127`); `_HEADERS=('PID','CONTAINER','TYPE','USER','UPTIME','COMMAND')`
  (`ps.py:46`); `__all__` (`ps.py:137`).

#### `commands/kill.py` (495 lines) — signal session trees
- `command_kill(args) -> None` (`kill.py:88`) — namespace: `target`, `all`,
  `signal` (`kill.py:90-92`); default SIGTERM (`kill.py:94`); nothing-live →
  info exit (`kill.py:109`); escalate to SIGKILL (`kill.py:249`); SIGQUIT the
  container roots (`kill.py:264`).
- `_select_sessions/_is_pid_token/_no_match_message` (`kill.py:116,129,140`);
  `_tracked_sessions/_session_roots/_forest_roots/_live_roots`
  (`kill.py:149,170,199,208`); `_teardown/_escalate/_drained/_wait_for_drain/
  _report/_survivors` (`kill.py:224,252,273,289,304,326`);
  `_signal_pass/_read_pid_ppid/_collect_tree/_is_alive`
  (`kill.py:335,359,386,411`); `_proot_comm_names/_root_is_proot`
  (`kill.py:429,444`); `_parse_signal/_signal_label/_fail`
  (`kill.py:454,475,483`).
- `_NON_TERMINATING_SIGNALS` (`kill.py:73`); `_GRACE_SECONDS=2.0`
  (`kill.py:84`); `_POLL_INTERVAL=0.05` (`kill.py:85`).

#### `commands/search.py` (252 lines) — Docker Hub search UI
- `command_search(args) -> None` (`search.py:65`); `_parse_limit(raw) -> int`
  (`search.py:112`); `_render(results, total)` (`search.py:141`);
  `_render_table/_render_stacked` (`search.py:182,209`); `_plural/_fit`
  (`search.py:223,228`); `_fmt_count(number) -> str` (`search.py:244` —
  `13.3B` style); `Network error` path at `search.py:91`.
- `_HEADERS=('NAME','DESCRIPTION','STARS','PULLS','OFFICIAL')` (`search.py:52`);
  `_OFFICIAL_MARK='[OK]'` (`search.py:62`); `__all__` (`search.py:252`).

#### `commands/help/` — help pages + renderer
- `command_help(args=None) -> None` (`help/__init__.py:52`);
  `HELP_COMMANDS={name: _make_help_fn(name) for name in HELP_PAGES}`
  (`help/__init__.py:49`); `__all__` (`help/__init__.py:167`).
- `HELP_PAGES` dict (`help/pages.py:43` — per-command `usage/summary/...`);
  `TOP_COMMANDS` 18-row index (`help/pages.py:1059`);
  `_IDENTITY_NOTE` guest-env note (`help/pages.py:33`).
- `render_page(page: dict)` (`help/render.py:290`); `term_width()`,
  `NARROW_BREAKPOINT=60` (`help/render.py:50,107`); section/paragraph/usage/
  aliases/options/commands/shell/bullets/footer blocks (`help/render.py:90-277`).

### 2.3 `helpers/` — pull/push/build machinery

#### `helpers/docker/refs.py` (375 lines) — reference grammar (M3 safe surface)
- `class InvalidReference(RuntimeError)` (`refs.py:110`).
- `class Reference(NamedTuple)` (`refs.py:122`): fields `registry/repo/tag/digest`
  (`refs.py:128-131`); `name()` (`refs.py:134`); `canonical()`
  (`refs.py:139`); `manifest_ref()` (`refs.py:151`).
- `parse_reference(ref: str) -> Reference` (`refs.py:179`) — Docker grammar,
  raises `InvalidReference`; `parse_tag_reference(ref)` (`refs.py:245`) — no
  digest; `is_repository_path(name) -> bool` (`refs.py:260`);
  `parse_image_ref(image_ref) -> tuple` (`refs.py:302`) — `(registry, repo, tag)`,
  **never raises**; `canonical_ref(image_ref) -> str` (`refs.py:327`);
  `with_explicit_tag(image_ref) -> str` (`refs.py:350` — append `:latest`);
  `derive_alias(image_ref) -> str` (`refs.py:362`).
- `ARCH_TO_DOCKER` (`refs.py:55`); `DOCKER_TO_ARCH` (`refs.py:64`);
  grammar regexes (`refs.py:73-97`); `NAME_MAX=255` (`refs.py:102`).

#### `helpers/docker/pull.py` (692 lines) — registry pull (core of install)
- `pull_image(image_ref: str, rootfs_fd: int, arch: str, insecure: bool = False) -> dict`
  (`pull.py:435`) — **parameters**: registry/image reference string; pinned rootfs
  descriptor (NOT a path — `pull.py:435-444` docstring); proot-distro arch name;
  insecure flag (Docker Hub stays verified-HTTPS regardless —
  `pull.py:487-489`). **Returns** `{"manifest": ..., "image_config": ...}`
  (`pull.py:474-476`); caller persists into `containers/<name>/manifest.json`.
  **Raises** `RuntimeError` (incl. `InvalidReference`, which subclasses it —
  `pull.py:478-481`): untrusted-cert/HTTP-only registry without
  `--allow-insecure`, `"<digest> is not recorded"` (`pull.py:518`),
  `"Network error: ..."` (`pull.py:578,610,680`). Cached manifests with all
  blobs present + re-hashed install fully offline; digest-pinned refs re-verify
  the whole chain even from cache (`_cached_pin`, `pull.py:495`).
- `_manifest_body/_parse_manifest/_get_manifest/_is_index/_entry_platform/
  _pick_platform/_child_digest/_resolve_pinned/_resolve_single_manifest`
  (`pull.py:96,143,154,162,167,185,226,251,280`);
  `_download_config/_parse_config/_fetch_config_blob/_config_digest`
  (`pull.py:310,350,364,392`); `_usable_cached_layers/_close_all`
  (`pull.py:399,426`); `_cached_pin` (`pull.py:495`);
  `_pull_layers(image_ref, rootfs_fd, arch, insecure, manifest, image_config,
  ref, usable)` (`pull.py:535`).
- `_MANIFEST_LIST_TYPES` (`pull.py:83`); `_ACCEPT_HEADER` (`pull.py:88`).

#### `helpers/docker/cache.py` (884 lines) — manifest + layer cache
- `validate_digest(digest: str) -> str` (`cache.py:99`); `manifest_layers(manifest,
  image_ref) -> list` (`cache.py:112`); `layer_cache_name/layer_cache_path`
  (`cache.py:161,175`); `manifest_cache_key/manifest_cache_name/
  manifest_cache_path` (`cache.py:183,191,196`);
  `open_manifest_cache_dir/open_layer_cache_dir -> int` (`cache.py:203,217`)
  (raise OSError).
- `save_manifest_cache(image_ref, arch, manifest, repo, image_config,
  documents=None) -> str` (`cache.py:256`);
  `annotate_manifest_cache(image_ref, arch)` (`cache.py:292`);
  `load_manifest_cache(image_ref, arch)` (`cache.py:328`);
  `load_manifest_documents(image_ref, arch) -> dict` (`cache.py:344`);
  `manifest_config_digest(manifest) -> str` (`cache.py:377`);
  `split_digest(digest) -> tuple` (`cache.py:404`);
  `data_matches_digest/fd_matches_digest/require_data_digest`
  (`cache.py:422,444,428`); `blob_present(digest) -> bool` (`cache.py:497`);
  `open_verified_layer(digest, *, evict=True)` (`cache.py:515`);
  `open_required_layer(digest, *, what='Layer blob') -> int` (`cache.py:561`);
  `referenced_blob_digests()` (`cache.py:717`); `image_cache_entry(image_ref,
  arch)` (`cache.py:809`); `iter_cached_images() -> list` (`cache.py:845` —
  one record per cached image sorted by ref then arch; **M3 safe surface**).

#### `helpers/docker/transport.py` (601 lines) — registry HTTP + auth
- `REGISTRY_URL='https://registry-1.docker.io'` (`transport.py:82`);
  `AUTH_URL='https://auth.docker.io/token'` (`transport.py:83`);
  `MAX_METADATA_BYTES=16MiB` (`transport.py:93`).
- `get_auth_token(repo, registry='', actions='pull', insecure=False) -> tuple`
  (`transport.py:478`) — base URL + Bearer token;
  `env_basic_auth() -> str` (`transport.py:404`) — Basic header from
  `PD_DOCKER_AUTH` (`transport.py:355`: `PD_DOCKER_AUTH=username:password`).
- `same_auth_origin(from_url, to_url) -> bool` (`transport.py:103`);
  `AuthStrippingRedirectHandler` (`transport.py:138`);
  `opener(insecure=False)` / `auth_opener` (`transport.py:180,190`);
  `registry_base_url(registry, insecure=False)` (`transport.py:304`);
  `insecure_for(registry, insecure) -> bool` (`transport.py:285`);
  `auth_denied_msg/push_denied_msg` (`transport.py:353,367`);
  `auth_note(prefix_space=True)` (`transport.py:596`).
- `decode_json_object(body, what) -> dict` (`transport.py:260`, raises
  RuntimeError); `_parse_bearer_challenge` (`transport.py:388`).

#### `helpers/docker/layers.py` (144 lines) — blob fetch + apply
- `download_blob(repo, digest, token, base, insecure=False) -> int`
  (`layers.py:44`) — downloads to layer cache, returns open descriptor.
- `apply_layer(layer_fd, rootfs_fd, *, digest='')` (`layers.py:122`) — whiteout-
  aware tar apply into the pinned tree.

#### `helpers/docker/media.py` (51 lines) — media-type constants
- `OCI_MANIFEST_MEDIA/OCI_CONFIG_MEDIA/OCI_LAYER_MEDIA/OCI_INDEX_MEDIA`
  (`media.py:41-44`); `DOCKER_MANIFEST_LIST_MEDIA/DOCKER_MANIFEST_MEDIA`
  (`media.py:46,49`); `canonical_json(obj) -> bytes` (`media.py:30`).

#### `helpers/docker/search.py` (254 lines) — Hub search backend
- `search_images(query: str, limit: int = SEARCH_DEFAULT_LIMIT) -> tuple`
  (`search.py:191`) — returns `(results, total)`; `SEARCH_URL`
  (`search.py:68`), `SEARCH_PAGE_MAX=100` (`search.py:72`),
  `SEARCH_DEFAULT_LIMIT=25` (`search.py:75`), `SEARCH_LIMIT_MAX=1000`
  (`search.py:79`), `_TIMEOUT=30.0` (`search.py:83`).
- `_count/_normalize/_fetch_page` (`search.py:87,105,142`).

#### `helpers/docker/push.py` (493 lines) — registry push
- `push_image(image_ref: str, arch: str, insecure: bool = False) -> dict`
  (`push.py:322`) — pushes the manifest-cache-resolved image to its registry.
- `_upload_timeout/_resolve_upload_url/_headers_for/_blob_exists`
  (`push.py:78,91,104,122`); `_ProgressReader` (`push.py:145`);
  `_upload_blob_bytes/_upload_blob_fd` (`push.py:180,229`);
  `_put_manifest(...) -> str` (`push.py:285`); `_strip_private_keys`
  (`push.py:312`); `_COMMIT_RATE=1MiB` (`push.py:75`).

#### `helpers/docker/__init__.py` (149 lines) — re-export facade
- `__all__` (`docker/__init__.py:100-149`, verified full list): ARCH_TO_DOCKER,
  AuthStrippingRedirectHandler, DOCKER_TO_ARCH, InvalidReference, Reference,
  SEARCH_DEFAULT_LIMIT/SEARCH_LIMIT_MAX/SEARCH_PAGE_MAX, annotate_manifest_cache,
  apply_layer, data_matches_digest, auth_denied_msg, auth_note, auth_opener,
  canonical_ref, derive_alias, download_blob, env_basic_auth, get_auth_token,
  image_cache_entry, insecure_for, insecure_registry_msg, iter_cached_images,
  layer_cache_name, blob_present, layer_cache_path, load_manifest_cache,
  manifest_cache_path, manifest_config_digest, open_layer_cache_dir,
  open_manifest_cache_dir, parse_image_ref, parse_reference, parse_tag_reference,
  pull_image, push_denied_msg, push_image, referenced_blob_digests,
  registry_base_url, same_auth_origin, require_data_digest, open_required_layer,
  save_manifest_cache, search_images, split_digest, validate_digest,
  open_verified_layer, with_explicit_tag.

#### `helpers/download.py` (630 lines) — HTTP with policy (all sync: off-thread)
- `NETWORK_TIMEOUT=120.0` (`download.py:108`); `NETWORK_ERRORS`
  (`download.py:85`); `download_file(url, dest, max_retries=5, retry_delay=5,
  insecure=False)` (`download.py:553`); `retry_http(operation, *, what,
  max_retries=5, retry_delay=5)` (`download.py:512`);
  `sha256_file(path) -> str` (`download.py:539`).
- `IncompleteResponse/InvalidRequest/RedirectRefused` (`download.py:116,172,220`);
  `RedirectPolicyHandler` (`download.py:292`); `check_redirect(from_url,
  location, *, allow_plaintext=False)` (`download.py:242`);
  `http_opener(*, insecure=False, redirect=None)` (`download.py:373`);
  `insecure_ssl_context()` (`download.py:410`);
  `is_cert_verification_error/is_plaintext_http_tls_error/is_retryable_http_error`
  (`download.py:424,465,481`); `certificate_error_msg(target)`
  (`download.py:441`); `declared_length/require_complete_body/new_request`
  (`download.py:134,143,191`).
- `__all__` (`download.py:52`).

#### `helpers/tar_extract.py` (661 lines) — safe tar apply
- `extract_tar_to_rootfs(archive_path, rootfs_fd, *, strip=0,
  handle_whiteouts=False)` (`tar_extract.py:105`);
  `extract_tar_fd_to_rootfs(fd, rootfs_fd, *, strip=0, handle_whiteouts=False,
  subject='archive', expected_sha256='')` (`tar_extract.py:177`).
- `safe_resolve_parts(root, parts, *, root_fd=None)` (`tar_extract.py:558`);
  `safe_resolve_parts_at(root_fd, parts)` (`tar_extract.py:544`);
  `_is_whiteout/_apply_whiteout` (`tar_extract.py:444,449`).
- `_HashingReader` (`tar_extract.py:137`); `_Parents` (`tar_extract.py:235`).

#### `helpers/rootfs.py` (293 lines) — guest etc fixups
- `open_etc(root_fd) -> int|None` (`rootfs.py:60`); `write_resolv_conf(rootfs, *,
  root_fd=None)` (`rootfs.py:209`); `write_resolv_conf_at(etc_fd)`
  (`rootfs.py:204`); `write_hosts` / `write_hosts_at` (`rootfs.py:225,220`);
  `register_android_ids_at(etc_fd)` (`rootfs.py:241`).
- `_RESOLV_CONF` (8.8.8.8 + 8.8.4.4 — `rootfs.py:190`); `_HOSTS`
  (`rootfs.py:194`); `_ID_FILE_MODE` (`rootfs.py:55`).

#### `helpers/dockerfile.py` (510 lines) — Dockerfile parser
- `parse_dockerfile(text: str)` (`dockerfile.py:73`) — returns
  `(directives, instructions)`; `class DockerfileSyntaxError(Exception)`
  (`dockerfile.py:65`).
- `expand_vars(text, env)` (`dockerfile.py:439`); `_INSTRUCTIONS` 18-set
  (`dockerfile.py:38`); `_HEREDOC_INSTRUCTIONS` (`dockerfile.py:45`);
  `_DIRECTIVES` (`dockerfile.py:50`); `MAX_DOCKERFILE_BYTES=16MiB`
  (`dockerfile.py:62`).

#### `helpers/build_cache.py` (314 lines) — RUN-step cache index
- `lookup(recipe_hash)` (`build_cache.py:157`);
  `record(recipe_hash, layer_digest, diff_id, size, image_config_patch=None)`
  (`build_cache.py:241`); `compute_recipe_hash(parent_layer_digest, instr,
  extra_inputs='')` (`build_cache.py:288`);
  `recorded_layer_digests()` (`build_cache.py:165`);
  `index_path()` (`build_cache.py:199`); `discard_index()` (`build_cache.py:204`).
- `_INDEX_PATH=BASE_CACHE_DIR/build_cache_index.json` (`build_cache.py:43`).

#### `helpers/build_engine/` (11 files) — Dockerfile execution engine
- `__init__.py` (`build_engine/__init__.py:42`): exports `BuildEngine`,
  `BuildError`, `PROOT_REQUIRED_INSTRUCTIONS`, `Stage`, `needs_proot`.
- `constants.py`: `PREDEFINED_ARGS` (`constants.py:30`), `EXPANDS_VARS`
  (`constants.py:41`), `PROOT_REQUIRED_INSTRUCTIONS={'RUN'}`
  (`constants.py:47`), `needs_proot(instructions) -> bool` (`constants.py:53`).
- `errors.py`: `class BuildError(Exception)` (`errors.py:22`).
- `engine.py`: `class BuildEngine` (`engine.py:214`,
  `__init__(build_dir, tmp_root, target_arch_pd, user_build_args, target_stage,
  verbose, quiet, no_cache, emulator, tmp_root_fd=None)` at `engine.py:224`;
  `run/close/_do_from/_pull_base_image/_target` etc.
  (`engine.py:591,306,503,660,718`)).
- `stage.py`: `class Stage` (`stage.py:50`,
  `__init__(index, name, rootfs_dir, target_arch_pd, *, dir_fd=None,
  rootfs_fd=None)` at `stage.py:89`).
- `handlers.py`: `do_arg/do_env/do_label/do_maintainer/do_user/do_workdir/
  do_cmd/do_entrypoint/do_expose/do_volume/do_stopsignal/do_shell/do_healthcheck/
  do_onbuild` (`handlers.py:48-356`); `HANDLERS` dispatch dict (`handlers.py:373`).
- `parsing.py`: `split_arg/split_operands/parse_chmod/parse_kv_list/to_argv/
  looks_like_url/is_tar_header` (`parsing.py:30,43,67,91,116,128,137`).
- `copy_step.py`: `do_copy/do_add` (`copy_step.py:308,313`);
  `_materialise_files` (`copy_step.py:920`).
- `run_step.py`: `do_run(engine, instr)` (`run_step.py:82`); `_exec_proot`
  (`run_step.py:228` — subprocess.Popen, NOT os.exec: build-safe in-process);
  subreaper/stray-reaping machinery (`run_step.py:435-632`); TERM passthrough
  (`run_step.py:692-693`).
- `dockerignore.py`: `load_dockerignore/is_ignored/simple_glob`
  (`dockerignore.py:32,48,80`).
- `users.py`: `resolve_id/resolve_chown/resolve_user_for_proot`
  (`users.py:35,72,88`).

#### `helpers/layer_diff.py` (771 lines) — RUN-step layer packing
- `snapshot(rootfs, *, rootfs_fd=None)` (`layer_diff.py:247`);
  `diff_snapshots(before, after)` (`layer_diff.py:344`) — `(added, modified,
  deleted)`; `write_layer_tar(rootfs, paths_to_pack, deleted, out_path,
  opaque_dirs=(), *, rootfs_fd=None)` (`layer_diff.py:480`);
  `write_files_layer(file_map, out_path)` (`layer_diff.py:558`);
  `layer_path_parts(arcname)` (`layer_diff.py:536`).

#### `helpers/oci_writer.py` (283 lines) — manifest/config/archive writer
- `build_manifest_and_config(image_config, layers, arch_name)`
  (`oci_writer.py:57`); `store_in_cache(image_ref, arch_name_pd, manifest,
  image_config)` (`oci_writer.py:112`); `write_oci_archive(out_path, manifest,
  image_config, image_ref)` (`oci_writer.py:155`).
- `_TAR_MODES` (`oci_writer.py:139` — `.tar/.oci.tar/.tar.gz/.tgz/
  .oci.tar.gz/.tar.bz2/.tbz2/.tar.xz/.txz/.oci.tar.xz`; note: no zstd here —
  **unverified** whether intentional, see §7).

---

## 3. Contracts & data

### 3.1 Environment variables (every `os.environ`/`getenv` read, verified by grep)

| Variable | Read at | Semantics |
|---|---|---|
| `TERMUX_APP__PACKAGE_NAME` | `constants.py:47` | Overrides the Android package id (default `com.termux`); feeds TERMUX_HOME/PREFIX defaults |
| `TERMUX__HOME` | `constants.py:48` | Termux home override |
| `TERMUX__PREFIX` | `constants.py:51` | Termux prefix override |
| `TERMUX_APP__APP_VERSION_NAME` | `constants.py:61` | Termux-detection indicator #2a |
| `TERMUX_VERSION` | `constants.py:62` | Termux-detection indicator #2b |
| `XDG_DATA_HOME` | `constants.py:79` | Non-Termux runtime root (fallback `~/.local/share`) |
| `XDG_CACHE_HOME` | `constants.py:82` | Non-Termux cache root (fallback `~/.cache`) |
| `PD_PROOT_BIN` | `arch.py:229` (via `os.environ.get("PD_PROOT_BIN")`) | Absolute proot binary path; validated executable |
| `PD_DOCKER_AUTH` | `transport.py:355` (`os.environ.get("PD_DOCKER_AUTH")`) | `username:password` Basic auth for private registries |
| `PD_FORCE_NO_COLORS` | `message.py:108` | Disables ANSI colours even on a TTY |
| `TERM` | `login/__init__.py:234,283`; `run_step.py:692` | Host TERM forwarded into guest (`or "xterm-256color"`); also build RUN steps |
| `COLORTERM` | `login/__init__.py:237,284`; `run_step.py:693` | Same passthrough treatment as TERM |
| `COLUMNS` | `help/render.py:63` (`os.environ.get("COLUMNS","0")`) | Help width fallback chain (tty → stdout/stdin → COLUMNS) |
| `container_name:path` specs | `paths.py` resolvers (NOT env) | `name:path` addressing for copy/sync |

Guest-visible env (written INTO the container, not read from host): `PD_CONTAINER`,
`PD_IMAGE`, `PD_IMAGE_ID`, `container=proot-distro` (`execenv.py:72`,
`help/pages.py:33` `_IDENTITY_NOTE`); blocked-from-image list `IMAGE_ENV_BLOCKED`
(`env.py:83`); host-exec namespace `LD_*`/`PROOT_*` refused from image values
(`execenv.py:60,85`).

### 3.2 On-disk layout (all paths + file formats)

```
<RUNTIME_DIR>/                                   # $PREFIX/var/lib/proot-distro (Termux)
                                                # or $XDG_DATA_HOME/proot-distro (generic)
  containers/<name>/                            # CONTAINERS_DIR (constants.py:89)
    rootfs/                                     # the guest tree
    manifest.json                               # {image_ref, arch, manifest, image_config}
                                                #   keys verified install.py:327-334
    shm/                                        # SHM_DIR_NAME (shm.py:61)
    sysdata/                                    # fake /proc|/sys stubs (sysdata.py:368)
    .l2s                                        # link2symlink marker (unverified exact name — §7)
  sessions/<pid>.json                           # SESSIONS_DIR (constants.py:92)
                                                # {pid,container,kind,command,user,start_time,
                                                #  isolated,minimal,detach} (session.py:141-208)
  locks/                                        # LOCKS_DIR (locking.py:92)
    <container>.lock                            # container_lock_path (locking.py:106)
    build/                                      # _BUILD_LOCKS_DIR (locking.py:93)
  installed-rootfs/                             # LEGACY_ROOTFS_DIR (constants.py:95, migrate-only)
<BASE_CACHE_DIR>/                               # .../cache (Termux) or $XDG_CACHE_HOME/...
  oci_layers/<sha256-hex>                       # LAYER_CACHE_DIR (constants.py:98)
  oci_manifests/<key>                           # MANIFEST_CACHE_DIR (constants.py:99)
  build_cache_index.json                        # _INDEX_PATH (build_cache.py:43)
```

- `manifest.json` shape: `{"image_ref": str, "arch": str, "manifest": {...OCI...},
  "image_config": {...}}` written with `indent=2` via `atomic_write`
  (`install.py:327-344`); **absent for plain-tarballs installs** (metadata None).
  Read back by `read_container_manifest` (`paths.py:320`),
  `container_image_config` (`paths.py:365`), `container_image_origin`
  (`paths.py:380`), and `run._read_image_config` (`run.py:51`).
- Session files: `<pid>.json` + `. <pid>.<rand>.tmp` staging name
  (`session.py:141-208`); liveness = exclusive flock held by a live process
  (`session.py:392-456`).
- OCI caches: layer blobs keyed by digest filename (`cache.py:161-175`),
  manifest entries keyed by `(image_ref, arch)` (`cache.py:183-196`).
- `.l2s` marker: referenced in the dep summary as `containers/<name>/{rootfs,
  manifest.json,shm,.l2s}`; exact on-disk filename conventions live in `l2s.py`
  (`_L2S_NAME_PREFIXES`, `l2s.py:53`) — marker filename itself **unverified** (§7).

### 3.3 Exit-code / SystemExit behaviour map
- 164 `sys.exit` call sites package-wide (verified `grep -c`). Rule: `0` only for
  help/usage output (`cli.py:271,275,301`); **every error path exits 1**.
- `command_*` handlers never return error values — they print + exit. In-process
  callers (spike `_install`, M3 facade) must catch `SystemExit` AND `RuntimeError`
  (dep summary §Failure modes; install tail catches
  `(EOFError, OSError, tarfile.TarError, RuntimeError)` + cleanup —
  `install.py:383-399` region).
- `parser.errors` → exit 1 (`parser.py:60`); `require_valid_name` → exit 1
  (`names.py:62`); `get_proot_bin`/emulator failures → exit 1
  (`arch.py:248,253,281,297,304`); missing container on login → exit 1
  (`login/__init__.py:324`); `_exec_proot` refusal → exit 1
  (`login/__init__.py:628-670` region); `copy` bad specs → exit 1 (9 sites);
  `clear_cache` failures → exit 1 (8 sites).

### 3.4 Exception types
- `InvalidReference(RuntimeError)` (`refs.py:110`) — Docker-grammar rejection;
  `pull_image` documents it as its promised failure type (`pull.py:478-481`).
- `RuntimeError` messages (verified strings): `"Cannot download {url}: ..."`
  (`download.py:607,628,630`); `"Network error: ..."`
  (`pull.py:578,610,680`, `search.py:91`, `push.py:113`);
  `"<digest> is not recorded"` (`pull.py:518`);
  `"Malformed digest: ..."` (`cache.py:108`);
  zstd unsupported/unavailable (`compress.py:132,149,155`).
- `BuildError(Exception)` (`build_engine/errors.py:22`) — every engine/handler
  failure (`engine.py`, `parsing.py:56,84,106`, `run_step.py:141,329,339,345`).
- `DockerfileSyntaxError(Exception)` (`dockerfile.py:65`).
- `LockStateUnknown` (`locking.py:388`); `_HostileLockPath` (`locking.py:369`);
  `_LockPathDenied` (`locking.py:376`).
- `IncompleteResponse/InvalidRequest/RedirectRefused` (all
  `http.client.HTTPException` subclasses — `download.py:116,172,220`).
- `ValueError` for bad backup compression (`backup.py:115,119`); `OSError`
  pass-throughs in copy/sync/dirfd paths.

### 3.5 Signal handling
- CLI installs SIGQUIT→KeyboardInterrupt (`cli.py:86,258`).
- `l2s` critical section warns-and-continues on SIGINT/SIGQUIT (`l2s.py:195-211`).
- `kill` defaults SIGTERM (`kill.py:94`), escalates SIGKILL (`kill.py:249`),
  SIGQUITs container roots (`kill.py:264`); non-terminating set
  (`kill.py:73`); grace 2.0 s / poll 0.05 s (`kill.py:84-85`).
- Build RUN steps: subreaper + stray-reap, SIGTERM→SIGKILL on leftovers
  (`run_step.py:435-632`).
- `detach.spawn_detached`: setsid + double fork; stdio to /dev/null
  (`detach.py:58-162`).

### 3.6 Progress behaviour (no callbacks — capture, don't patch)
- `progress_active()` = stderr-is-tty AND not quiet (`progress.py:80`);
  `draw_bytes_bar/draw_count_bar/clear_bar` (`progress.py:85,118,141`);
  `REDRAW_THRESHOLD_BYTES=262144` (`progress.py:40`).
- `log_info` suppressed under `--quiet`/`set_quiet`; `log_error` always shows
  (`message.py:210-217`). Colours die with `PD_FORCE_NO_COLORS` or non-TTY
  (`message.py:108`). **Do not monkeypatch `draw_bytes_bar`** (roadmap M3 §92).

### 3.7 dirfd / statedir conventions
- Every security-sensitive path is opened as a descriptor and held across the
  operation: install keeps `(container_fd, rootfs_fd)` from `open_container_pair`
  through extraction (`install.py:305`); login chdirs into `rootfs_fd` and execs
  with `--rootfs=.` so proot resolves the guest root by inode, not name
  (`login/__init__.py:628-670` region docstring); `pull_image` takes `rootfs_fd`,
  never a path (`pull.py:435-444` docstring); etc fixups go through one pinned
  `etc_fd` (`install.py:357-379`).
- `statedir` trust roots (`statedir.py:62`); `remove_state_tree` for cleanup
  (`statedir.py:232`); `atomic_write` for every JSON write
  (`atomic.py:131`, `install.py:338-340`).

---

## 4. How this project uses it today + fullest-utilization map

### 4.1 Current use (verified in-repo)
- **Spike G2/G4 in-process `command_install`** (`m0-spike/src/main.py:136-168`
  `_install`): lazy-imports `proot_distro.commands.install.command_install` AFTER
  env setup, builds a `SimpleNamespace(image_ref, custom_container_name,
  override_arch=None, allow_insecure=False)`, wraps the call in
  `redirect_stdout+redirect_stderr`, catches `SystemExit` (reads `.code`) and
  bare `Exception`. Import failure (e.g. `os.O_DIRECTORY` missing on Windows) is
  reported as "Linux-only — this gate runs on the Android device".
- **Env-before-import bootstrap** (`m0-spike/src/main.py:47` region + `proot_probe`
  per roadmap M3 §90): `TERMUX__PREFIX/HOME`, `TERMUX_APP__PACKAGE_NAME`,
  `XDG_DATA_HOME/XDG_CACHE_HOME`, `PD_PROOT_BIN` set before any proot_distro import.
- **Own proot spawn, not `command_login`** (`m0-spike/src/main.py:170-215`
  `guest_argv`/`proot_extensions`): hand-built argv (`libproot.so -0 <ext> -r
  <rootfs> -b /dev -b /proc -b /sys -w / ...`) mirroring
  `_add_proot_extensions` incl. `--kill-on-exit --link2symlink --sysvipc -L`,
  motivated by the on-device dpkg `link()`/SELinux finding quoted in the docstring.
- **Planned (roadmap M3 §89-101)**: `services/proot_service.py` sole-importer
  facade (lazy gate, `asyncio.to_thread`, plain-data returns); install via
  in-process `_run_install` vs public-CLI spawn (decision deferred to M3 plan
  mode); progress via stderr capture; login argv via `--get-proot-cmd` recipe or
  `build_proot_args` re-implementation; sessions via our own proot spawn
  (M4, `ProotSession` shaped like CollabShell's `ColabTerminalClient`).
- **Planned probes** (`core/proot_probe.py`, M3 §98): binary/loader presence, arch
  support, rootfs writability before screens start.

### 4.2 Presently-unused APIs → concrete milestone usage

| Unused API | What it unlocks | Milestone proposal (per roadmap) |
|---|---|---|
| `command_build` + `helpers/build_engine/*` + `dockerfile.parse_dockerfile` + `build_cache.*` | **On-device image bakery**: user picks packages → app generates a Dockerfile → `command_build` produces a bootable OCI image → `_install_as_container` materialises it. No daemon, no root — Termux cannot do this in-app. | M3 stretch / M4: "Remix this container" screen; RUN steps reuse the proven subprocess (not exec) path (`run_step.py:228`) so they are facade-safe |
| `command_push` + `docker/push.push_image` | **Share remixes**: push the built image to GHCR/Docker Hub from the phone (auth via `PD_DOCKER_AUTH`). Community image distribution without a desktop. | M4/M5: publish flow behind the certified-catalog gate |
| `command_backup` / `command_restore` | **Snapshots**: one-tap `.tar.*` snapshot to app storage / SAF; restore wipes + reinstates (offline, no re-download). Compression map `backup.py:94` offers gz/bz2/xz/zstd/none. | M3: container-actions menu (backup/restore alongside open/stop/reset/remove) |
| `command_sync` + `command_copy` | **Host↔guest file bridge**: `copy` for single files, `sync` (checksum + `--delete` pruning) for project folders; `name:path` specs + overlap refusal come free (`paths.py:523,609`). | M3 settings/storage screen; M4 structured-mode artifact export |
| `command_ps` + `session.active_sessions/session_is_live` | **Session manager**: live-session list (PID/container/type/user/uptime/command) feeding the M4 session screen + keep-alive refcount rule. | M4: sessions survive screen switches; reuse the exact record shape (`session.py:141-208`) |
| `command_kill` | **Hung-session rescue**: SIGTERM→SIGKILL escalation with grace (`kill.py:84-94,249`) wired to a "Force stop" button; `--all` for storage-cleanup flows. | M4 session screen; M3 container actions |
| `command_search` + `docker/search.search_images` | **In-app image browser**: Hub search with stars/pulls/official table (`search.py:52-62`) → one-tap install of arbitrary OCI refs (roadmap §37 "arbitrary OCI refs"). | M3 distro-list screen (certified + custom ref + search tab) |
| `command_rename` | **Container aliases**: rename + automatic l2s rewrite (`rename.py:85`, `l2s.py:163`). | M3 container actions |
| `command_reset` | **Factory reset**: wipe + offline reinstall from cached layers (`reset.py:44`) — the "Reinstall" path the `_run_install` refusal message already advertises (`install.py:264-266`). | M3 container actions |
| `command_remove --image` + `remove._resolve_images/_delete_images` | **Storage manager**: per-image size + orphan-layer accounting (`remove.py:266-318`, `clear_cache.py:387-466`) → "free X MB" UI. | M3 settings (storage) |
| `command_list --image` + `docker/cache.iter_cached_images` | **Offline catalog**: cached-image table (IMAGE/ARCH/ID/SIZE/CREATED — `list.py:44`) drives first-boot offline rootfs choice (roadmap §101). | M3 install flow |
| `command_run` | **One-shot structured exec**: image Entrypoint/Cmd + `--` args inside proot — the exact primitive the M4 structured "command → outputs" mode needs (roadmap §1c, §107), without reimplementing login. | M4 dual-mode: structured cells via `run`, console via login argv |
| `login --detach` + `detach.spawn_detached` | **Background services**: daemons (sshd, web servers) surviving screen switches; PID reported back, session registered (`detach.py:58`). | M4 keep-alive services (refcount rule) |
| `login --get-proot-cmd` detail | **Spawn recipe source**: path-pinned printable argv + explicit mismatch warning (`login/__init__.py:469-551` region) — parse or re-implement preamble per M3 §93/§97. | M3 facade, M4 spawn |
| `session.register_session` semantics | **Don't call it from the facade**: it must run in the process that immediately execs (PID identity — `session.py:115-140`). Our `ProotSession` owns the PID; upstream registry is read via `active_sessions`, never written. | M4 (read-only integration) |
| `arch.detect_installed_arch/normalize_arch/get_emulator_args` | **Probe-gating** (`core/proot_probe.py`): installed-arch detection, Docker↔proot arch translation, qemu-need computation for the M0-gate-4 cross-arch story. | M3 probe; M0-gate-4 follow-up |
| `guestfile.*` + `passwd.*` | **Image introspection**: read guest `/etc/os-release`, passwd entries, shells without starting a session — powers distro-detail screens + `_resolve_login_user` parity. | M3 distro list |
| `paths.*` (safe surface) | **Facade foundation**: `installed_container_names`, `container_is_installed`, `container_rootfs`, `container_image_origin`, `resolve_container_path` — the update-safe query layer (roadmap M3 §94). | M3 service facade |
| `progress.fmt_size` + `message`/`progress` capture | **Install UX**: human sizes + stage-line capture (`redirect_stderr`) → stage-level + indeterminate UI (roadmap M3 §96). | M3 install flow |
| `sysdata`/`shm`/`rootfs` helpers | **Android correctness**: fake /proc|/sys stubs, shm store, resolv.conf/hosts fixups are already applied by install (`install.py:357-381`); reuse `fake_sysdata_bindings`/`make_shm_dir` if the facade ever assembles argv by hand. | M3/M4 spawn hardening |
| `locking.ContainerLock/busy_locks` | **Concurrency UI**: `busy_locks()` (`locking.py:346`) → "install already in progress" states; hold `ContainerLock` around facade mutations. | M3 facade |
| `atomic.*` + `statedir.*` | **Facade state**: crash-safe JSON for our own service state (install queue, session roster) using the same tmp+rename pattern. | M3 facade |

### 4.3 How this dependency makes our app significantly better than Termux's proot-distro
(Owner principle: "the only way we beat Termux is by utilizing every dependency
to the fullest." Every differentiator below is a package API Termux's own
`proot-distro` CLI exposes but its UX never productises — our app does.)

1. **Zero-Termux operation.** Termux's flow assumes the Termux app (prefix binds,
   `$PREFIX/bin` bridges, Termux-mode proot flags). We run `IS_TERMUX=False`
   generic mode on app-private XDG dirs with `PD_PROOT_BIN` pointing at our
   bundled `libproot.so` — no Termux layer at all (roadmap §10, §35-36). The env
   contract (`constants.py:47-86`) is what makes this a config choice, not a fork.
2. **In-app image search → one-tap install.** Termux users type `pd search` /
   `pd install` by hand. We wire `search_images` (`search.py:191`) +
   `pull_image` (`pull.py:435`, offline-capable cache chain) into a graphical
   catalog: certified map + arbitrary OCI refs (roadmap §37).
3. **Snapshots as a first-class feature.** `backup`/`restore` exist in Termux's
   CLI but have no UI; our container-actions menu makes them one tap (M3), with
   compression choice (`backup.py:94`) and offline restore (`restore.py:441`).
4. **Session manager, not `ps` output.** `active_sessions` + `command_ps` fields
   (PID/container/type/user/uptime/command — `ps.py:46`) become a live session
   screen with force-stop via `command_kill` escalation (`kill.py:249`) — Termux
   leaves users to `ps`/`kill` by hand.
5. **Structured command mode.** Termux is console-only. `command_run`
   (Entrypoint/Cmd + `--` args — `run.py:112-152`) gives us the one-shot exec
   primitive for the CollabShell-style cell pipeline (roadmap §1c, §107):
   interactive console AND notebook-style command→outputs in one app.
6. **On-device image bakery.** `command_build` + the full Dockerfile engine
   (`build_engine/*`, `dockerfile.py`, `layer_diff.py`, `oci_writer.py`) has no
   Termux-app equivalent workflow; we turn it into "Remix this container" and
   `command_push` (`push.py:49`) publishes the result — a phone that builds AND
   ships OCI images.
7. **Storage transparency.** Termux hides `oci_layers/oci_manifests` growth; our
   settings screen exposes per-image size + orphan reclamation (`remove.py:266-318`,
   `clear_cache.py:387-466`, `iter_cached_images` at `cache.py:845`).
8. **Safe-by-default concurrency.** `ContainerLock` + `busy_locks()`
   (`locking.py:346,707`) drive "already installing" UI states instead of the
   CLI's fail-and-retry.
9. **Probe-gated UX.** `arch.*` + `get_proot_bin` + `get_emulator_args` power
   `core/proot_probe.py` (roadmap M3 §98): the app refuses to start broken flows
   (missing binary, unsupported arch, unwritable rootfs) where Termux surfaces
   raw tracebacks/exit-1s.
10. **Ad-monetised, Play-distributed.** Out of scope for the package but decisive
    for the product: `flet-ads` + Play/F-Droid distribution (roadmap M5/M6) around
    a container engine Termux never monetised — funded development of the
    differentiators above.

---

## 5. Update-safety index (5.x bumps)

### 5.1 Stable-contract (build on freely; re-verify by running the suite)
- **Env contract** (`constants.py:47-86`): var names, defaults, import-time
  semantics; `IS_TERMUX` 2-of-3 rule (`constants.py:55-68`).
- **On-disk layout** (§3.2): `containers/<name>/{rootfs,manifest.json}`,
  `sessions/*.json` shape, `locks/`, `oci_layers/`, `oci_manifests/`.
- **Pure helpers**: `docker/refs.*` (`parse_reference`, `derive_alias`,
  `canonical_ref`, `with_explicit_tag`), `docker/cache.iter_cached_images`,
  `docker/search.search_images`, `paths.installed_container_names/
  container_is_installed/container_rootfs/container_image_origin/
  resolve_container_path`, `arch.get_device_cpu_arch/normalize_arch/
  detect_installed_arch/get_emulator_args/get_proot_bin`,
  `progress.fmt_size`, `message`/`progress` read paths, `guestfile.*`,
  `names.*`, `execenv.*`, `compress.require_*` gates.
- **CLI grammar**: command names + aliases (`cli.py:64-84`, `parser.py:103-110`)
  and the login/run shared flags (`parser.py:116-160`) — the public contract the
  app shells out to.

### 5.2 Internal / fragile (isolate behind ONE wrapper — the M3 facade)
- `command_*` handler internals: argparse-namespace field reads
  (`getattr(args, ...)` chains), `sys.exit(1)`-on-error discipline, in-process
  side effects (`os.execvpe` in login, `os.fchdir`, flock inheritance).
- `build_proot_args` (27 keyword-only params + exact argv order —
  `proot_cmd.py:55-128`): any flag addition/reorder breaks hand-rolled argv.
- `_run_install` / `_login_with_rootfs` (underscore = no stability promise).
- `ContainerLock` / `BuildLock` acquisition semantics (`locking.py:507-754`).
- The `rootfs_fd` descriptor convention (`pull_image`, `install_from_local_file`,
  `open_container_pair`): signature shape, not just names.
- `register_session` PID-identity requirement (`session.py:115-140`) — misuse
  corrupts the session registry.
- `run_step._exec_proot` subprocess plumbing and subreaper logic
  (`run_step.py:228-632`).

### 5.3 Re-verify list for every 5.x bump
1. `constants.py` (new env vars? new paths? changed `IS_TERMUX` rule? changed
   fake-kernel strings?).
2. `commands/login/proot_cmd.py::build_proot_args` (new kwargs? reordered argv?
   new Termux-only branches?).
3. `parser.py` (new flags → new namespace fields the facade must supply; new
   commands/aliases for `_COMMAND_HANDLERS` parity).
4. `session.py` record shape (new fields break `active_sessions` consumers).
5. `install.py` manifest.json keys (`install.py:327-334`).
6. `docker/cache.py` cache key/entry shapes.
7. `cli.py` probe exemptions + new `sys.exit` paths.
8. Diff-study ritual per D-010 (docs/dependency-studies diffs) before bumping
   the floor.

---

## 6. Verification

- Signatures above come from an AST walk of all 77 installed `*.py` files plus
  targeted `sed` reads of every function body cited; `file:line` refs point at
  the installed 5.10.0 tree.
- Counts: 77 py files (`find`), 93 RECORD lines, 1.4 MiB (`du`), 164 `sys.exit`
  sites (`grep -c`), 18 commands (`_COMMAND_HANDLERS`), 13 login/run shared-flag
  groups (`parser.py:116-160`).
- Behavioural claims (offline pull chain, fchdir+`--rootfs=.` inode pinning,
  double-fork detach, subreaper RUN steps) are quoted from the modules'
  own docstrings/comments, not inferred.

## 7. Explicitly unverified items (do NOT rely on without checking)

1. `commands/build.py` parser flags (`parser.py:347-380` `_build`): namespace
   field names beyond the `getattr` list in §2.2-build (`path, dockerfile,
   tags, build_args, override_arch, target_stage, emulator, outputs,
   install_as, no_cache, verbose, quiet`) — verify against `parser.py:347-380`
   before constructing the namespace in-process.
2. `_login_with_rootfs` per-`getattr` line numbers (`login/__init__.py:336-602`
   region cited as a range): each attribute default verified by grep, exact lines
   not pinned — re-pin when writing the M3 facade.
3. `_exec_proot` / get-proot-cmd / detach-call exact lines likewise cited as
   regions within `login/__init__.py:460-670`.
4. `install.py` bare-`Exception` tail after `(EOFError, OSError, tarfile.TarError,
   RuntimeError)`: cleanup + re-raise shape assumed from the `except` head at
   `install.py:387` — read `install.py:380-420` before copying the pattern.
5. `.l2s` marker filename under `containers/<name>/` (dep summary lists `.l2s`;
   `l2s.py` verifies only the `('.proot.l2s.','.l2s.')` symlink prefixes at
   `l2s.py:53`) — confirm on a real install before the facade asserts it.
6. `oci_writer._TAR_MODES` lacking zstd (`oci_writer.py:139`): factual (no `.zst`
   key in the map) but intent (omission vs upstream TODO) unconfirmed.
7. `helpers/docker/__init__.py` re-export behaves as `__all__` states
   (`docker/__init__.py:100-149` verified textually); live-import equality
   (e.g. `docker.pull_image is pull.pull_image`) **unverified** — trivially
   checkable with the venv python on Linux/Android (import fails on Windows:
   POSIX dir-fd APIs — cf. `m0-spike/src/main.py` import guard).
8. Windows introspection: per the task brief, `...\ .venv\Scripts\python.exe -c`
   cannot import POSIX modules — all claims above are source reads, which is
   why exact `file:line` refs are given instead of `inspect.signature` output.



