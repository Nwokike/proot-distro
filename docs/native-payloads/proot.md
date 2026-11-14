# flet-proot — PRoot payload

| | |
|---|---|
| Upstream | Termux PRoot 5.1.107.102, libtalloc 2.5.0, libandroid-shmem 0.7 |
| Builder | `scripts/build_flet_proot_wheel.py` |
| App pin | `flet-proot==5.1.107.102` |
| Ships | `libproot.so`, `libproot-loader.so`, `libtalloc.so`, `libandroid-shmem.so` |

## Why

`proot-distro` orchestrates containers by printing/spawning a `proot` command
line; the binary must be executable from the APK (W^X), hence a jniLib named
`libproot.so` plus the loader. `PROOT_LOADER`, `PD_PROOT_BIN` and
`LD_LIBRARY_PATH` are set by `core/proot_probe.py` before any `proot_distro`
import.

## Options the app relies on

`--rootfs`, `--cwd`, `--bind`, `--kernel-release`, `--kill-on-exit`,
`--link2symlink`, `--sysvipc`, `-L`, `-q <emulator>` (QEMU), `-p` (low ports).
`--shared-tmp`, `--shared-home`, `--isolated`, hostname/kernel are implemented
in `services/session_service/argv.py` because upstream gates them on Termux.

## Update procedure

1. Bump the three `.deb` pins (version + sha256) and the wheel version.
2. Update `pyproject.toml` (`flet-proot==<proot version>`).
3. Regenerate: `uv run python scripts/build_flet_proot_wheel.py --out wheels`.
4. Verify: `tests/test_core.py` (payload staging, 16 KiB alignment) and
   `tests/test_get_proot_cmd.py`.
5. Device-check: a shell opens, `uname -m` matches the container architecture,
   dpkg installs work (L2S).
