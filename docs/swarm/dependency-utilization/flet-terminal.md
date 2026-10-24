# flet-terminal utilization — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/screens/terminal_view.py`, `src/services/session_manager.py`, `src/services/session_service.py`, `src/app_controller.py`, `src/app_shell.py`, `src/core/state.py`, `src/core/theme.py`, `src/main.py`, `tests/test_terminal_wiring.py`; installed `flet-term 0.4.0` (`flet_terminal/*.py`, `flutter/flet_terminal/lib/src/flet_terminal.dart`, `METADATA`, `RECORD`) · **Date:** 2026-10-20

## What it does / how the app uses it

One `MobileTerminal` per open container is created lazily inside the `TerminalView` component and kept on the observable `SessionEntry` (`src/screens/terminal_view.py:68-79`, `src/services/session_manager.py:24-36`). The Python side owns the process: `pty.openpty` + `Popen` in `ProotSession` (`src/services/session_service.py:95-134`). The app wires raw input to the PTY through both flet-terminal input paths, forwards `on_resize` to `TIOCSWINSZ`, sets the palette from the app theme, and replays the scrollback deque on every Dart `mount` (`src/screens/terminal_view.py:81-122`). Extra keys (default 13) and the search bar are enabled; the package settings menu is disabled (`show_settings=False`).

## Version drift: study's 0.3.9 vs installed 0.4.0

Every row below was re-checked against the installed wheel; the 0.3.9 study is prior knowledge only.

| Area | Study (0.3.9 claim) | Installed 0.4.0 | Evidence |
|---|---|---|---|
| Version | `0.3.9` | `0.4.0` (and new module constant `__version__`) | `docs/dependency-studies/flet-terminal.md:22`; `.venv/Lib/site-packages/flet_terminal-0.4.0.dist-info/METADATA:3`; `flet_terminal/__init__.py:9` |
| `Requires-Python` | `>=3.14` | `>=3.10` (M1 widening landed) | study:26; `METADATA:20` |
| `Requires-Dist` | `flet>=1.0.1` | `flet` (unpinned) | study:25; `METADATA:23`; `uv.lock:269-271` |
| License metadata | none in wheel | `License: MIT`, `License-File: LICENSE`, shipped `dist-info/licenses/LICENSE` | study:27; `METADATA:6,22`; `flet_terminal-0.4.0.dist-info/RECORD:6` |
| Project URLs | Repository, Homepage, Issues | Homepage, Repository, Issues | study:28; `METADATA:7-9` |
| Dart payload | `**/*` shipped `CHANGELOG.md`, `LICENSE`, `README.md` too | only `lib/flet_terminal.dart`, `lib/src/extension.dart`, `lib/src/flet_terminal.dart`, `pubspec.yaml` | study:32-45; `RECORD:16-19` |
| **`MobileTerminal` construction** | **raises `RuntimeError: No current renderer is set` outside a component tree** | **constructs anywhere; no `@ft.component` remains in the package** | study:274,312; `flet_terminal/extra_keys.py:27-32,45-59`; live: `MobileTerminal()` headless succeeds |
| `refresh_buttons` | absent → `MobileTerminal.ctrl_active/alt_active` setter raised `AttributeError` | present; setters work | study:147,312; `extra_keys.py:179-211`; live: `m.ctrl_active = True` OK |
| Modifier UI | `@ft.observable ModifierState` + `@ft.component ModifierKey` | plain `dataclass ModifierState` + plain `ft.Button`, imperative `refresh_buttons()` | study:169-171; `extra_keys.py:27-59,197-211` |
| `Terminal` props/events/defaults | 10 props, 10 events; scrollback 10000, font 11.0, blink True, block, read_only False, auto_focus True | unchanged | study:71-97; `flet_terminal/terminal.py:34-59` |
| Event payloads | `resize` = `{"cols","rows"}`; title/bell strings; selection two shapes | unchanged (still **no `bottom_inset`**) | study:84-97; `flutter/flet_terminal/lib/src/flet_terminal.dart:165-172` |
| Themes | 4 presets × 12 keys; `get_theme` unknown → None | unchanged | study:200-219; `flet_terminal/themes.py:9-73` |
| Extra keys | 13 `(label, bytes|None)` pairs | unchanged | study:173-189; `extra_keys.py:62-76` |
| `MobileTerminal` defaults | theme falls back to JetBrains Dark | unchanged, plus a new quirk: constructor only seeds `active_theme` if the dict has a `"name"` key, which `BUILTIN_THEMES` never does | `flet_terminal/mobile_terminal.py:49,98-102`; live: `MobileTerminal(theme=BUILTIN_THEMES["Colab Light"])._keys_bar.active_theme == "JetBrains Dark"` |
| Queue/lifecycle | `did_mount`/`before_event` drain; `will_unmount` clears queue | same, with `super()` calls and detached-page-safe `_mark_dart_ready` | study:103,272; `terminal.py:72-113,147-157` |
| Dart half | 594 L, cited behaviors | behaviorally identical at the same locations (593 lines by `wc -l`) | `flet_terminal.dart:42-94,97-173,176-204,236-373,443-544,577-592` |
| `MobileTerminal.on_data_channel_open` | not forwarded | still not forwarded (no accessor) | `mobile_terminal.py:342-444` |

Material consequences for this app: none of the app's assumptions about props/events/themes/extra keys are stale, but the two 0.3.9 "must-fix" defects are gone, so the renderer-context workaround recorded in the docs/tests is obsolete (F8). `Requires-Python >=3.10` is compatible with the app's `>=3.14` (`pyproject.toml:8`); `flet-terminal>=0.4.0` is already locked at 0.4.0 (`pyproject.toml:13`, `uv.lock:267-274`).

## Findings

### F1 · P1 · Live PTY output never reaches the terminal after mount
- **Where:** `src/services/session_manager.py:69-70` (the only PTY output callback only calls `entry.feed`), `src/services/session_manager.py:38-39` (`feed` appends to the deque and nothing else), `src/screens/terminal_view.py:96-98` (the only call to `mt.send_bytes` is the mount replay); `grep -rn "send_bytes" src/` returns no other producer.
- **What:** The reader thread buffers every chunk into `entry.scrollback` but never forwards it to the mounted Dart terminal. The xterm buffer therefore contains only the snapshot replayed during `on_mount`. Output produced after mount — including the echo of everything the user types — is invisible until the user leaves and re-enters the session (which triggers another replay). Input works; display does not update.
- **Evidence:**
  ```
  src/services/session_manager.py:69:        def _on_bytes(data: bytes) -> None:
  src/services/session_manager.py:70:            entry.feed(data)
  src/services/session_manager.py:38:    def feed(self, data: bytes) -> None:
  src/services/session_manager.py:39:        self.scrollback.append(data)
  src/screens/terminal_view.py:96:        def _on_mount(_e) -> None:
  src/screens/terminal_view.py:97:            mt.clear_pending()
  src/screens/terminal_view.py:98:            entry.replay(mt.send_bytes)
  ```
  The upstream example proves the intended path: `on_output=mt.send_bytes` (`/home/maikel/.zcode/workspace/default/flet-terminal/examples/flet_terminal_example/src/app.py:79`) called from the PTY reader thread (`.../pty_service.py:181-182`).
- **Fix / opportunity:** In `_on_bytes`, feed the scrollback **and** forward while the view is mounted, e.g. `entry.feed(data)` then `if entry.mt is not None and entry.mounted: entry.mt.send_bytes(data)`. Set `entry.mounted = True` at the top of `_on_mount` and `False` via `mt.set_on_unmount(...)` (`flet_terminal/mobile_terminal.py:424-426`) so minimized sessions are not queued unbounded and the next mount's full replay covers the gap. `send_bytes` is the package's thread-safe byte path (`terminal.py:129-140`).
- **Risk if ignored:** The terminal is a snapshot viewer: interactive shells appear frozen after the first prompt. This is the app's core M4 feature.

### F2 · P2 · Remount replays into the previous (dead) DataChannel
- **Where:** `.venv/Lib/site-packages/flet_terminal/terminal.py:147-157` (`will_unmount` clears `_dart_ready`/queue but leaves `_channel` and `_channel_ready=True`), `:111-113` (`did_mount` re-marks Dart ready), `:129-140` (`send_bytes` trusts the stale flags); app: `src/screens/terminal_view.py:68-79` reuses the same `entry.mt` across mounts, `src/app_shell.py:53-61` removes it when leaving and re-adds it on resume.
- **What:** On resume, the re-added control's mount replay runs before Dart fires the new `data_channel_open` (`flet_terminal.dart:97-101` fires mount in `initState`, `:176-204` opens the channel in `didChangeDependencies`). Python still holds the old channel object with `_channel_ready=True`, so `entry.replay(mt.send_bytes)` sends to the dead channel; the new channel is only installed when `_handle_data_channel_open` runs (`terminal.py:115-121`). Whether the stale sends are dropped or raise-and-requeue is transport-dependent.
- **Evidence:** `terminal.py:147-157` has no `_channel = None` / `_channel_ready = False`; `terminal.py:132` gates on `self._channel is not None and self._channel_ready and self._dart_ready`. Python-side channel objects are cached per id by Flet and never closed by the package (`flet/data_channel.py:69-72`; `flet_dart_bridge_server.py:239-260`).
- **Fix / opportunity:** Preferred: package fix — reset `_channel = None` and `_channel_ready = False` in `will_unmount` (and close the old channel). App workaround: recreate the composite on each mount (`entry.mt = None; entry.wired = False` in a `ft.use_effect(..., cleanup=...)`) or defer replay until `mt.ready` is true (`mobile_terminal.py:404-407`) so the new channel is bound. Do not simply queue blindly from F1 while unmounted (unbounded `_pending_writes`).
- **Risk if ignored:** Resuming a minimized shell can render a blank or truncated screen; together with F1 the terminal may never repaint.

### F3 · P2 · The search bar can be closed but never reopened
- **Where:** `src/screens/terminal_view.py:70-72` (`show_search=True`, `show_settings=False`), `src/screens/terminal_view.py:105-111` (no `on_shortcut` wiring); `.venv/.../flet_terminal/search_bar.py:75-81,147-158` (close button calls `on_close`), `.venv/.../mobile_terminal.py:149-154` (`toggle_search`); `.venv/.../flet_terminal.dart:72-73` (shortcut gate).
- **What:** The bar is visible from the first render, but its close button hides it; the settings menu that could re-enable it is not built (`show_settings=False`), there is no header control, and `on_shortcut` is unset so `Ctrl+Shift+F` is not consumed/handled. Search is gone for the rest of the session.
- **Evidence:** `mobile_terminal.py:149-154` is the only public toggle; `extra_keys.py:306-312` is the only built-in UI entry point, and it is inside the settings menu suppressed by `show_settings=False`.
- **Fix / opportunity:** Add a header `ft.IconButton(Icons.SEARCH)` calling `mt.toggle_search()` (method is public), or enable `show_settings=True`. For desktop, also handle `on_shortcut == "toggle_search"` (`terminal.py:56`; Dart `flet_terminal.dart:42-62`).
- **Risk if ignored:** A user who closes the bar loses in-buffer search with no recovery path.

### F4 · P2 · "Full screen" leaves the app navigation bar and system chrome visible
- **Where:** `src/screens/terminal_view.py:130-132,177-197`; `src/app_shell.py:63-74` always appends `ft.NavigationBar`; `src/core/state.py:36` (global flag).
- **What:** The toggle only drops the in-view banner/header/quick strip. The bottom `NavigationBar` remains, as does the OS status/navigation chrome; the tooltip promises "hide the chrome and the ad" (`terminal_view.py:159`). The flag is global, so a session reopens full screen after the toggle was left on.
- **Evidence:** `app_shell.py:64-73` has no branch on `state.terminal_fullscreen`; `terminal_view.py:177-197` only edits its own `controls` list.
- **Fix / opportunity:** In `AppShell`, omit the `NavigationBar` when `state.active_session` is set and `state.terminal_fullscreen` is true; keep the exit affordance. If true immersive mode is wanted, verify the mobile `page.window`/platform API before relying on it (UNVERIFIED).
- **Risk if ignored:** The feature does not deliver the screen space it advertises; the exit button overlays the terminal's first row.

### F5 · P3 · `bottom_inset` resize branch is dead; the test that "covers" it is tautological
- **Where:** `src/screens/terminal_view.py:83-94` and `:226-227`; `.venv/.../flutter/flet_terminal/lib/src/flet_terminal.dart:165-172`; `tests/test_terminal_wiring.py:55-60`.
- **What:** 0.4.0's Dart `onResize` emits exactly `{"cols": width, "rows": height}`. `bottom_inset` is never present (the 0.3.9 study's payload table says the same), so `inset` is permanently 0 and the `Padding.only(bottom=inset)` branch never executes. The Dart widget already applies `viewInsets.bottom` padding itself (`flet_terminal.dart:495,512-530`). The test named "resize payload carries cols rows and inset" only round-trips a JSON string it constructed, so it cannot catch the mismatch.
- **Evidence:** Dart handler quote; `terminal_view.py:85-88` `json.loads` + `data.get("bottom_inset", 0)`; test asserts `parsed["bottom_inset"] == 42` on its own literal.
- **Fix / opportunity:** Delete the dead inset branch (and the `inset` state/padding) or replace it with a real keyboard-inset mechanism; rewrite the test to use a captured payload from the Dart side (`{"cols","rows"}`).
- **Risk if ignored:** No runtime impact today, but false confidence and dead UI code around the soft keyboard.

### F6 · P3 · SYSTEM theme changes do not re-theme the terminal
- **Where:** `src/screens/terminal_view.py:116-122`; `src/core/theme.py:39-55`; `src/app_controller.py:130,264`; `.venv/Lib/site-packages/flet/controls/page.py:614-619`.
- **What:** The palette effect depends only on `state.theme_revision`, which is bumped on explicit mode changes and prefs restore. In `"system"` mode, an OS light/dark switch changes `page.platform_brightness` but does not bump `theme_revision`, so neither the app nor the terminal `set_theme` runs; the terminal keeps the previous palette. Flet exposes `Page.on_platform_brightness_change` for this event.
- **Evidence:** `theme.py:46-55` reads `platform_brightness`; only `app_controller.py:130` and `:264` increment `theme_revision`; no `on_platform_brightness_change` assignment in `src/`.
- **Fix / opportunity:** Assign `page.on_platform_brightness_change` in `AppController.init` to bump `state.theme_revision` (and, if desired, reconcile `page.theme_mode`), which re-runs both the app render and the terminal effect. ~5 lines.
- **Risk if ignored:** A terminal left dark on a light system theme (or vice versa) until the user cycles the theme.

### F7 · P3 · Blocking `os.write` runs inside the DataChannel callback thread
- **Where:** `src/screens/terminal_view.py:105-108` → `src/screens/terminal_view.py:37-39` → `src/services/session_service.py:136-140`; `.venv/Lib/site-packages/flet/data_channel.py:58-61`.
- **What:** `DataChannel.on_bytes` runs the handler synchronously on the transport thread and the package's docstring says to push heavy work to a queue/worker. The handler performs a blocking `os.write` to the PTY master. Keystrokes are tiny, but a large paste or a guest process that stops draining its input can fill the PTY buffer and stall the channel.
- **Evidence:** docstring `data_channel.py:58-61`; handler chain above; `session_service.py:139-140` `with contextlib.suppress(OSError): os.write(...)`.
- **Fix / opportunity:** Push input chunks to a dedicated writer thread/queue, or accept the risk explicitly (the upstream example also writes directly, `examples/.../pty_service.py:127-134`).
- **Risk if ignored:** Rare input freezes under backpressure; low likelihood for normal typing.

### F8 · P3 · Docs/tests still encode the removed 0.3.9 renderer-context constraint
- **Where:** `docs/reference/dep-flet-terminal.md:35-39` ("Until then, apps use plain `Terminal`"), `docs/decisions.md:53` ("the same constraint as flet-terminal's `MobileTerminal`"), `docs/dependency-studies/flet.md:322,346`, `tests/test_terminal_wiring.py:79-87` (asserts construction happens in the component tree because of that constraint).
- **What:** Installed 0.4.0 constructs `MobileTerminal` headlessly (verified live: `MobileTerminal()` succeeds; no `@ft.component` in the package), so the landmine is gone. The app's render-time construction is still good practice for control lifecycle reasons, but the stated rationale is false, and "use plain Terminal" would discard the extra keys/search integration.
- **Evidence:** study:274,312 vs `extra_keys.py:27-59`; live construction output in the drift table.
- **Fix / opportunity:** When doc edits are allowed, update those three docs and the test docstring; keep the source guard but re-word it as lifecycle hygiene, not a workaround.
- **Risk if ignored:** Future work avoids `MobileTerminal` (losing the best part of the package) or copies an obsolete workaround.

## Missed capabilities

| Capability | API location (0.4.0) | Proposed integration point | Value / cost |
|---|---|---|---|
| Clipboard: copy selection, select all, paste | `MobileTerminal.copy_selection(_async)`, `get_selection_async`, `select_all`, `paste` at `flet_terminal/mobile_terminal.py:287-335`, `on_copy` at `:428-435`; Dart copy-on-secondary-tap `flet_terminal.dart:474-492` | A header Copy icon calling `page.run_task(mt.copy_selection_async)` (returns bool) plus `mt.on_copy` -> snackbar; or enable the built-in settings menu | High value (copy build errors/logs; long-press copy is not a reliable mobile path), low cost (~10 lines) |
| Search re-open / `toggle_search` | `mobile_terminal.py:135-154`; search engine `flet_terminal.dart:277-370`; shortcut name `toggle_search` at `:46` | Header search icon; optional `on_shortcut` handler on desktop | Medium value, 3 lines (see F3) |
| Bell notification | `MobileTerminal.on_bell` setter `mobile_terminal.py:369-376`; Dart `flet_terminal.dart:159-162` | In the wiring block: `mt.on_bell = lambda e: methods.show_snack("Terminal bell")`, gated behind a user setting (study O-5 says default OFF) | Medium value (apt/pacman completion ping), 2 lines |
| Zoom / cursor style / blink | `zoom_in/zoom_out/reset_zoom` `mobile_terminal.py:185-215`; `set_cursor_style` `:167-174`; `toggle_cursor_blink` `:176-183`; floor 6.0 px in `zoom_out` | Enable `show_settings=True` (one constructor arg) or add two header buttons for font +/- | Medium value (accessibility, small screens), 1 arg or ~8 lines |
| Custom extra-keys layout | Constructor `extra_keys=` `mobile_terminal.py:38`; default list `extra_keys.py:62-76`; payload transform `:377-392` | Pass a per-app list adding `Ctrl+C` (`b"\x03"`), `Ctrl+D` (`b"\x04"`), `Home`/`End` (`\x1b[H`/`\x1b[F`), `PgUp`/`PgDn`, `\\` | High value for proot package work (interrupt, EOF, pager navigation), low cost (one local tuple) |
| Host shortcut bus | `Terminal.on_shortcut` `terminal.py:56`; `ShortcutEvent` `:16-24`; Dart map `flet_terminal.dart:42-94` | Wire `mt.on_shortcut` on desktop for `toggle_search`, `copy`, `paste`, `zoom_in/out`, `clear`; note all 17 combos are swallowed once a handler is installed | Medium value, medium cost (~20 lines; must handle the combos you want) |
| Selection state | `MobileTerminal.on_selection_change` `mobile_terminal.py:378-391`; Dart debounced event `flet_terminal.dart:206-224` | Enable the Copy button only when `has_selection`, or show the selected text | Low/medium value, ~6 lines |
| Cleanup hook | `set_on_unmount` `mobile_terminal.py:424-426`; `will_unmount` `terminal.py:147-157` | Mark the entry unmounted, clear pending writes, optionally recreate the composite | Medium value (fixes/contains F2), ~3 lines |
| Programmatic buffer search | `MobileTerminal.search` `mobile_terminal.py:284-285`; engine `terminal.py:265-310` | "Find selection" action from a long-press or a debug panel | Low value, low cost |
| `read_only` mode | Constructor `mobile_terminal.py:36`; `terminal.py:40` | A log/inspection surface for structured output | Low value for this app |
| Bright / search-hit palette keys | Dart parser `flet_terminal.dart:414-424` accepts `brightBlack`…`brightWhite`, `searchHitBackground(Current)`, `searchHitForeground`; `themes.py:9-66` ships only 12 keys | A custom `theme` dict layered over the built-in preset to make search hits more visible | Low value, low cost |
| Shared settings menu | `show_settings=True` build path `mobile_terminal.py:73-86`; menu items `extra_keys.py:213-323` | One flag unlocks Copy/Paste/Select All/Clear, 4 themes, zoom, cursor blink, search toggle (but see the `active_theme` quirk in the drift table) | High value, 1 constructor arg |

## Verified-good list

- Uses the composite (`MobileTerminal`), not a plain `Terminal`, so extra keys + search + sticky modifiers come for free (`src/screens/terminal_view.py:12,68-78`). No plain `Terminal` construction anywhere in `src/`.
- Both input paths are wired: binary `set_on_bytes` and legacy string `on_data` (`src/screens/terminal_view.py:105-108`), matching the upstream example (`examples/flet_terminal_example/src/app.py:93-94`).
- Resize is event-only and correctly forwarded to `TIOCSWINSZ` (`terminal_view.py:83-92`; `session_service.py:142-150`); payload shape matches 0.4.0 Dart (`flet_terminal.dart:165-172`).
- Scrollback replay is ordered and clears the pre-mount queue first (`terminal_view.py:96-98`; `session_manager.py:41-43`; queue semantics `terminal.py:76-109,129-140`).
- DataChannel binding works whether the handler is registered before or after the channel opens (`terminal.py:115-127`, `:123-127`).
- Theme is set at construction and refreshed on app theme flips via the package's sanctioned `thaw`/`control_update` path (`terminal_view.py:68-78,116-122`; `mobile_terminal.py:156-165`; `frozen_support.py:15-105`). `Colab Light` / `JetBrains Dark` are valid `BUILTIN_THEMES` names (`themes.py:24-37,52-65`).
- Title changes are wired to `entry.title` and the header re-renders because `SessionEntry` is observable (`terminal_view.py:100-111`; `mobile_terminal.py:360-367`; `flet_terminal.dart:155-157`).
- Extra keys and sticky CTRL/ALT are wired inside `MobileTerminal` (`mobile_terminal.py:71-102,129-133`; `extra_keys.py:362-392`).
- `auto_focus=False` avoids popping the soft keyboard on open (`terminal_view.py:76`), matching the CollabShell/example guidance.
- Scrollback memory is bounded (`deque(maxlen=2000)` at `session_manager.py:31`); xterm's ring is 10000 lines (`terminal_view.py:73`; `terminal.py:34`).
- Session teardown stops the process (`session_manager.py:84-93`; `main.py:24-25,31`) and the Dart widget disposes its channel/timers (`flet_terminal.dart:577-592`).
- No private flet-terminal reach-in in the app; the guard at `tests/test_terminal_wiring.py:68-76` holds.
- 0.4.0 API claims used by the app were live-verified: `MobileTerminal` signature, 8 root exports, all forwarded event setters, `ready/pending_count/clear_pending/flush`, headless construction.
- Flet APIs used by the view exist in 1.0.4: `ft.use_effect` (`flet/components/hooks/use_effect.py:42-58`), `ft.use_state` + observable subscription (`.../use_state.py:48-121`), `ft.use_context` (`.../use_context.py:84-108`), `Page.render`, `Page.show_dialog/pop_dialog`, `ControlEvent.data` (`flet/controls/control_event.py:105-127`).

## Unverified

- Exact stale-channel behavior on remount (F2): `dart_bridge.send_bytes` may raise (then `send_bytes` requeues and the new channel drains) or silently drop; not exercised without a built client.
- Whether xterm fires `onResize` on first layout, i.e. whether the guest ever gets a valid initial winsize before the first user-triggered resize. The app does not send an initial `TIOCSWINSZ`.
- Android font fallback for the hard-coded `"JetBrains Mono"` (`terminal.py:35`); the package does not bundle the font.
- Timing of `page.platform_brightness` on first render and whether Flet emits `on_platform_brightness_change` on Android in this build.
- Whether OS-level clipboard paste through the soft keyboard reaches xterm without an explicit `MobileTerminal.paste()` call.
- DataChannel throughput for a full 2000-chunk replay (~8 MiB) on a low-end device; no benchmark was run.
- Whether Flet calls `will_unmount` on every re-used control on all remount paths; the conclusion is based on `flet/messaging/session.py:293-301` plus the app's leave/resume flow, not a live UI run.
- The 0.4.0 wheel was compared to the 0.3.9 *study*, not to a 0.3.9 wheel; Dart-half "unchanged" means every study citation still matches the installed file, not a byte diff.
