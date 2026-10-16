# Testing findings — how this app gets tested (verified 2026-10-16)

## Run-it-first rule (durable — learned the hard way)
An APK must never be handed over before the app's code has been **executed once**:
1. `tools/check_flet_api.py src/main.py` green (AST guard: every `ft.*` chain verified against the INSTALLED flet; caught `ft.ElevatedButton` and `ft.border.all`, both removed in Flet 1.0 — `ft.Button` / `ft.Border.all` are the 1.0 forms).
2. Local `uv run flet run` smoke passed (main() constructs; extension panes may be absent — that is expected). The owner may also run it.
3. Only then: CI build → device.
The first spike APK crashed on the owner's phone with `module 'flet' has no attribute 'ElevatedButton'` because step 1+2 were skipped. They now run in CI too (lint step of `.github/workflows/m0-spike.yml`).

## House activity-terminal log pattern (use in every device-facing app)
From the owner's examples (flet-notifications / flet-yandex-ads):
```python
TERMINAL_BG = "#0D0D0D"; TERMINAL_TEXT = "#A6E22E"
log_text = ft.Text(value="", font_family="Courier New", size=11, color=TERMINAL_TEXT, selectable=True)
log_col = ft.Column(controls=[log_text], scroll=ft.ScrollMode.AUTO, expand=True)
log_terminal = ft.Container(content=log_col, bgcolor=TERMINAL_BG, padding=12,
    border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),
    border_radius=8, height=340)
# log(): "[%H:%M:%S] " prefix; page.update(log_text); then run_task scroll_to(offset=-1)
```
Fixed-height scroll container is the scroll fix; timestamps make device screenshots self-documenting.

## Desktop-run platform notes (proot spike)
- `nativeLibraryDir` is None on desktop — gates must guard and say so (they do).
- **proot-distro is Linux-only**: `proot_distro/dirfd.py` uses `os.O_DIRECTORY`, so importing it on Windows raises — the spike catches this with a friendly message. Device (Android/Linux) imports fine.
- `os.getuid`/`TracerPid`/`/proc` are POSIX-only — use guarded lookups (done).
- `sys.executable -c` spawn works on desktop (G1b ✓) — still must be re-proven on Android.


## The hard fact: extension widgets never render under `flet run`
Verified against installed `flet-cli` 1.0.4:
- Desktop `flet run` ensures the **prebuilt flet-desktop client** (`run.py:222-232` → `ensure_flet_desktop_package_installed()` + `flet_desktop.open_flet_view`); it compiles nothing.
- `flet run --web/--ios/--android` serve a dev URL and need only `flet-web` (`run.py:229-230`); `--android` prints a QR to the official Flet preview app (`run.py:263-264`, `587-675`).
- `[tool.flet.dev_packages]` exists only in `build_base.py:2578+` — it is a **build**-time setting, not a run-time one.
- Owner's own confirmation, flet-notifications example README: `uv run flet run src/main.py   # desktop preview (no notifications — prebuilt client)`.
→ Third-party extension Dart (flet_terminal, flet_ads) is compiled in only by `flet build`. Under `flet run`, those panes are absent (unknown control type on the client).

## The three-layer testing loop we will use
1. **`uv run pytest` (offline, every change)** — the bulk: proot-distro argv/refs/storage/probe logic, and the `ProotSession` bridge against a fake process + mocked `MobileTerminal`. Template: CollabShell's suite (`reference/app-collabshell.md` §Tests).
2. **`uv run flet run` (fast UI loop)** — all screens/UX except extension panes. Wrap terminal and ads in **platform-availability placeholders** so preview stays useful (ads would otherwise raise on desktop).
   - Note: `flet run` creates `.flet/storage/{data,cache,temp}` and exports `FLET_APP_STORAGE_*` (`run.py:283-320`) — our service storage logic behaves the same locally as in a packaged app.
3. **CI artifacts (device truth)** — every push produces `build-<sha>` prerelease artifacts (house workflow pattern); installing those on the phone is the only gate for terminal/proot/ads behavior. M0's spike APK is the first dedicated device harness.

## Owner-rule notes
- No local `flet build` (release integrity) — the only lever that would show extensions locally is a local desktop build; recorded as open decision O-9 in `decisions.md`.
- For M1 (flet-terminal refactor), the package's own example workflows produce installable artifacts, and CollabShell is the regression consumer to re-verify against.

## M0 evidence protocol (what the spike must record)
Per gate: pass/fail, exact command, output excerpt, device model + Android version, and `adb logcat` excerpts for any SELinux/exec denials. Results go into `docs/m0-checklist.md` (created by M0) with screenshot/log attachments kept in-repo while private.
