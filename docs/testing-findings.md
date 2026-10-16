# Testing findings — how this app gets tested (verified 2026-10-16)

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
