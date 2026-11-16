# flet-qemu — QEMU user-mode emulators

| | |
|---|---|
| Upstream | QEMU 11.1.3 (Termux `qemu-user-*` packages) |
| Builder | `scripts/build_flet_qemu_wheel.py` |
| App pin | `flet-qemu==11.1.3` |
| Ships per ABI | arm64 APK: `libqemu-x86_64/i386/arm/riscv64.so`; x86_64 APK: `libqemu-aarch64/i386/arm/riscv64.so` + closure (glib, pcre2, libdw/libelf, lzma, json-c, argp) |

## Why all four arches

Design decision: a phone of either ABI can run containers of any other
architecture (x86_64 images on arm64 phones and vice versa, plus 32-bit and
riscv64). The emulators are found by `proot-distro`'s own
`shutil.which("qemu-<arch>")`; the app symlinks them into `<app>/bin` and
prepends it to `PATH` (`core/proot_probe.py`).

## Runtime notes

- `proot-distro` chooses the emulator automatically for a foreign-arch image and
  emits `-q <absolute path>`; `<app>/bin` is on `PATH` for login and build RUN.
- Legitimate speed knob: `QEMU_TB_SIZE` (e.g. `64M`) via the shell's Environment
  lines. `-one-insn-per-tb` is a diagnostic, not a speed-up.

## Update procedure

1. Bump `QEMU_VERSION`, the package versions and the `_SHA` pins.
2. Update `pyproject.toml` (`flet-qemu==<version>`).
3. Regenerate: `uv run python scripts/build_flet_qemu_wheel.py --out wheels`.
4. Verify: `tests/test_wheel_builders.py` (pins/closure/rewrites) and
   `tests/test_core.py` (`<app>/bin/qemu-*` symlinks + PATH).
5. Device-check: install an amd64 image on an arm64 phone and open a shell.
