# dep-flet-terminal.md — flet-terminal 0.3.9 (wheel facts + trio comparison + refactor blueprint)

Verified 2026-10-16 against the INSTALLED wheel (R5 study) and the repo clone `C:\Users\nwoki\.zcode\workspace\default\flet-terminal` + sibling extension repos (trio study). Owner: Onyeka Nwokike; MIT (flutter-side LICENSE only). This file is M1's entire basis.

## Shipped wheel facts (what the app gets)
- `Requires-Dist: flet>=1.0.1`; **`Requires-Python: >=3.14`** (stricter than flet's >=3.10); **NO license metadata in METADATA**.
- Ships `flet_terminal/` (Terminal 404 L, MobileTerminal 444 L, ExtraKeysBar, TerminalSearchBar, themes, `frozen_support.py`) + top-level `flutter/flet_terminal/` (pubspec: `xterm: ^4.0.0`, `flet: ^1.0.0`).
- Unpin you asked for: exact places a flet version appears = root `pyproject.toml:11` (`flet>=1.0.1`), example `pyproject.toml` (`flet>=0.86.3` + stale lock resolving flet 0.86.1), both `uv.lock`s. Dart `flet: ^1.0.0` must stay (tracks the client baked by `flet build`).

## API surface (as shipped)
- `@control("FletTerminal") class Terminal(ft.LayoutControl)`: `scrollback=10000`, `font_family="JetBrains Mono"` (not bundled on Android — verify fallback or ship the font), `font_size=11.0`, `cursor_blink`, `cursor_style`, `theme`, `read_only`, `auto_focus`, sticky `ctrl_active/alt_active`; events `on_data/on_resize/on_modifier_reset/on_title_change/on_bell/on_selection_change/on_copy/on_mount/on_shortcut/data_channel_open`.
- I/O contract only: app→screen `write()/write_async()/send_bytes()` (fast path = "pty"-named DataChannel, queued until `data_channel_open`); screen→app `set_on_bytes(handler)` + `send_input()` for virtual keys. **NO process-spawn API, no pty, no exit events** — the channel label "pty" is transport naming. Dart side is pure `xterm.dart` rendering (no `dart:io`, no `Process`). Mobile-ready rendering (isMobile detection, keyboard inset, long-press copy/paste); desktop example uses posix openpty / winpty.
- `MobileTerminal(ft.Column)` composite: terminal + search bar + extra keys; mutators via `thaw()` + `page.session.patch_control` (`frozen_support.py` runtime workaround on private `_frozen` — documented, load-bearing for declarative users).
- Consumer wiring reference: `app-collabshell.md` (byte flow, scrollback replay on mount, reconnect).

## Trio comparison (owner's three extensions)
- **Most capable**: flet-terminal (0.3.9, in production inside CollabShell).
- **Most house-standard quality**: flet-notifications (≈1800 test lines + Dart tests, flet 0.85/1.0/latest compat matrix, quality gate, sync_versions.py; carries the patcher complication).
- **Cleanest packaging**: flet-yandex-ads (329-line contract suite, bare `flet`, no patcher).
- flet-terminal is currently the weakest on standards: **no tests, no compat matrix, no quality gate, no license metadata, `**/*` package-data glob ships Dart docs/tests into the wheel, README not house-format, stale examples, narrow requires-python, `_frozen` workaround, version floor**.

## Refactor blueprint (M1)
1. `"flet>=1.0.1"` → bare `"flet"` (matches yandex-ads/notifications verbatim) — **AFTER tests + matrix exist**; alternative in plan mode: keep a modest floor (R1 note: drift risk is the unversioned `_c` name + wire shape, not pip metadata; flet has no registration/manifest to break).
2. `requires-python ">=3.14"` → `">=3.10"` (match flet/new packages; README badge moves with it).
3. Add `license = "MIT"` + `license-files = ["LICENSE"]`.
4. URLs order → Homepage/Repository/Issues.
5. Package-data glob → `["pubspec.yaml", "lib/**"]`.
6. Add `pytest>=8.0` to dev; add `tests/` contract suite (yandex-ads pattern: exports, defaults, wire-value assertions, typed-event resolution via `get_event_field_type`; notifications pattern: `json.loads` dual-decode).
7. Add `compat.yml` (flet 0.85.0/1.0.0/latest matrix — scope to versions the 1.0-era APIs support), quality gate in build-all.yml, `sync_versions.py` (Python↔Dart drift), `.fvmrc`.
8. Example cleanup (bare `flet`, drop `[tool.flet.dev_packages]`, keep `[tool.uv.sources]`, relock) + README rewrite to house-extension-standard.
- **Do NOT copy**: notifications' `patcher.py`/`[project.scripts]`; `before_update` platform raises (wrong for a cross-platform terminal).
- Spawn capability rides on M0 gate 4: if Dart-side wins, it becomes a first-class package API (keeping apps pure Python); if Python-side works, package stays view-only.
- Consumers: CollabShell pins 0.3.9 (`MobileTerminal` + `BUILTIN_THEMES`) — ship compatible surface or coordinate the bump.
