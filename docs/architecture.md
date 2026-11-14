# Architecture (1.2.0)

The app is a rootless Linux container host for Android, built with Flet 1.1
(Python 3.14) and `proot-distro`.

```
Android app process
├─ Flet UI + controllers            src/screens, src/controller_actions
├─ proot-distro (host Python)       src/services/proot_service (sole importer)
├─ PTY sessions                     src/services/session_service + session_manager
└─ display stack (in-process)
   ├─ Xvnc            opt/lib/<abi>/libXvnc.so   X server + VNC server
   ├─ PulseAudio      opt/lib/<abi>/libpulseaudio.so + module-*.so
   ├─ RFB↔WS bridge   services/desk_service/stream_server.py (aiohttp)
   └─ viewer          vendored upstream noVNC 1.7.0 (served verbatim)
```

Key decisions:

- **Xvnc runs in the app**, not in the guest. A container needs no X packages for
  a single app; a desktop session brings its own packages only for the DE.
- **The guest connects over shared loopback**: `DISPLAY=127.0.0.1:N`,
  `XAUTHORITY=/tmp/x11/xauth-N`, `PULSE_SERVER=127.0.0.1:4713`. Every new shell
  opened while a display runs inherits that environment.
- **One session per `container:display`**, several displays per container are
  allowed. The stream server binds an ephemeral port and gates the viewer with a
  per-session access code carried in the noVNC `path` setting.
- **X11 only.** Xvnc is an X11 server: Wayland-only apps cannot render. This is
  stated in onboarding and Help rather than implied.
- **Everything device-dependent is opt-in**: RFB loopback binding, view-only,
  audio rates, spinners… the defaults are friendly, the full upstream option
  surface stays reachable in Display defaults.

## Native payloads

Four wheels built by `scripts/` and pinned in `pyproject.toml`:

| Wheel | Contents | Doc |
|---|---|---|
| `flet-proot` | proot + talloc + libandroid-shmem | [native-payloads/proot.md](native-payloads/proot.md) |
| `flet-xvnc` | Xvnc + xkbcomp + ELF closure + xkb data + Latin bitmap fonts | [native-payloads/xvnc.md](native-payloads/xvnc.md) |
| `flet-pulseaudio` | PulseAudio + Android audio modules + closure | [native-payloads/pulseaudio.md](native-payloads/pulseaudio.md) |
| `flet-qemu` | QEMU user-mode emulators (4 non-host arches) + closure | [native-payloads/qemu.md](native-payloads/qemu.md) |

noVNC is vendored by `scripts/fetch_novnc.py`:
[native-payloads/novnc.md](native-payloads/novnc.md).

## Packaging rules

- Android only allows `execve` from the APK's native-library dir (W^X): every
  executable payload ships as `lib*.so` and is reached through a symlink.
- AGP only packages `lib*.so` names, so versioned sonames are rewritten in place
  at build time (same-or-shorter, NUL-padded).
- `split_per_abi = true`, `legacy_packaging = true` (keeps the .so files
  deflated).
- The APK payload budget is enforced in CI (56 MiB arm64, ≤120 bitmap fonts).
