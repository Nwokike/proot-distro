# Native payloads — index and common contract

Every executable/library the app ships as an Android native payload is built by
one script under `scripts/` and declared under
`[tool.flet.android].dependencies` in `pyproject.toml`.

| Wheel | Version pin | Builder | Doc |
|---|---|---|---|
| `flet-proot` | `5.1.107.102` | `build_flet_proot_wheel.py` | [proot.md](proot.md) |
| `flet-xvnc` | `1.16.2` | `build_flet_xvnc_wheel.py` | [xvnc.md](xvnc.md) |
| `flet-pulseaudio` | `17.0` | `build_flet_pulseaudio_wheel.py` | [pulseaudio.md](pulseaudio.md) |
| `flet-qemu` | `11.1.3` | `build_flet_qemu_wheel.py` | [qemu.md](qemu.md) |
| (vendored) noVNC | `1.7.0` | `fetch_novnc.py` | [novnc.md](novnc.md) |

## Contract

- **Wheel version == the pin in `pyproject.toml`.** CI builds each wheel and the
  app installs that exact version.
- **Payloads ship as `opt/lib/<abi>/lib*.so`.** Android only allows `execve`
  from the APK native-library dir (W^X); AGP only packages `lib*.so`, so
  versioned sonames are rewritten in place at build time (same or shorter,
  NUL-padded).
- **16 KiB PT_LOAD alignment** is checked at build time and again on the built
  APK (`scripts/check_elf_alignment.py`).
- **sha256-pinned sources.** Every `.deb` comes from the Termux pool with a pin;
  a failed download aborts the wheel build.
- **jniLibs-only.** These wheels are never imported on desktop; the runtime
  guards the imports (`flet_xvnc`, `flet_pulseaudio`, `flet_proot`). QEMU is
  found by name on `PATH` through symlinks.
- **License/provenance** is generated into `THIRD-PARTY-SOURCES.md`
  (`scripts/generate_third_party_sources.py`) — do not hand-edit that table.

## Regenerating (local or CI)

```sh
uv run python scripts/build_flet_proot_wheel.py       --out wheels
uv run python scripts/build_flet_xvnc_wheel.py       --out wheels
uv run python scripts/build_flet_pulseaudio_wheel.py --out wheels
uv run python scripts/build_flet_qemu_wheel.py       --out wheels
uv run python scripts/fetch_novnc.py
```

CI does the same in the `apk` and `aab` jobs, then audits the built artifact for
the expected payloads per ABI and enforces the APK payload budget.
