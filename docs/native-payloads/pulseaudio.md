# flet-pulseaudio — PulseAudio payload

| | |
|---|---|
| Upstream | PulseAudio 17.0-5 (Termux `pulseaudio`, main repo) |
| Builder | `scripts/build_flet_pulseaudio_wheel.py` |
| App pin | `flet-pulseaudio==17.0` |
| Ships | `libpulseaudio.so`, 8 `module-*.so`, the core/PA closure, 10 codec libs, `data/pulse/` |

## Why it runs in the app

Android's audio stack (AAudio / OpenSL ES) is not available to guest apps; the
app-side daemon opens the device sinks and serves guest clients over loopback
TCP (`127.0.0.1:4713`).

## Modules and options

Loaded by the generated `default.pa` (`services/desk_service/pulse.py`):

| Module | Options exposed |
|---|---|
| `module-aaudio-sink` | `latency=`, `pm=` (performance mode), `rate=`, `no_close_hack` |
| `module-null-sink` | fallback sink |
| `module-sles-source` | mic: `rate=`, `format=`, `channels=` |
| `module-native-protocol-tcp` | port 4713, loopback only |

Daemon flags: `--disable-shm`-class behaviour is default under proot, and the
resampler is selectable (`--resample-method`, e.g. `speex-float-1`, `soxr-hq`).
Bundled but not loaded: `module-sles-sink`, `module-always-sink`,
`module-pipe-sink/source` (kept as real fallbacks/abilities).

## Update procedure

1. Bump `PA_VERSION` and the `_PINNED_SOURCES` pins (14 packages + shas).
2. Update `pyproject.toml` (`flet-pulseaudio==<version>`).
3. Regenerate: `uv run python scripts/build_flet_pulseaudio_wheel.py --out wheels`.
4. Verify: `tests/test_xvnc_runtime.py` covers `write_pulse_config` and the
   daemon argv (mic/rate/format/channels/latency/resampler).
5. Device-check: speaker audio, mic recording, no `Denied access` lines.
