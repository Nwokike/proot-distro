# src/screens/terminal_view.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/screens/terminal_view.py` · `src/services/session_manager.py` · `src/services/session_service.py` · `src/app_controller.py` · `src/app_shell.py` · `src/core/state.py` · `.venv/lib/python3.14/site-packages/flet_terminal/mobile_terminal.py` · `.venv/lib/python3.14/site-packages/flet_terminal/terminal.py` · `.venv/lib/python3.14/site-packages/flet_terminal/themes.py` · `.venv/lib/python3.14/site-packages/flet/controls/context.py` · `.venv/lib/python3.14/site-packages/flet/controls/alignment.py` · `.venv/lib/python3.14/site-packages/flet/controls/padding.py` · `docs/dependency-studies/flet-terminal.md` · `docs/decisions.md` D-017
**Date:** 2026-10-24

---

## What it does / how the app uses it

`terminal_view.py` defines two `@ft.component` views that together implement the Terminal tab. `SessionSelectorView` lists open shells and installable containers; `TerminalView` wraps a `MobileTerminal` widget for one live container shell. The design follows CollabShell's `TerminalEntry` pattern: the `MobileTerminal` instance and its wiring are stored on `SessionEntry` (not on the component) so that tab switches and theme flips survive without killing the PTY. On `on_mount` it clears pending queued writes then replays the scrollback buffer. It wires both input paths (`set_on_bytes` for the binary DataChannel, `on_data` for the soft-keyboard string path), handles PTY resize via `TIOCSWINSZ`, and updates the terminal color palette on `state.theme_revision` changes.

---

## Findings

### F1 · P0 · Live PTY output never reaches the terminal display

- **Where:** `src/services/session_manager.py:69-70` and `src/screens/terminal_view.py:96-98`
- **What:** `SessionManager.open()` registers `_on_bytes` as the PTY read callback. That callback calls only `entry.feed(data)`, which appends bytes to the scrollback deque. It never calls `entry.mt.send_bytes(data)`. The `MobileTerminal.send_bytes` path — which is the only live path from Python to the Dart xterm canvas — is called only inside `_on_mount` via `entry.replay(mt.send_bytes)`. The terminal is therefore blank during a live session; it shows output only when the Dart view is (re)created (tab switch, rotate) and the full scrollback is replayed.
- **Evidence:**
  - `session_manager.py:69-70`: `def _on_bytes(data: bytes) -> None: entry.feed(data)` — no call to `entry.mt`.
  - `session_manager.py:38-39`: `def feed(self, data: bytes) -> None: self.scrollback.append(data)` — no forwarding.
  - `terminal_view.py:96-98`: `def _on_mount(_e): mt.clear_pending(); entry.replay(mt.send_bytes)` — only replay, no live hook.
  - Exhaustive grep for `send_bytes` in `src/`: only two occurrences — `session_manager.py:43` (inside `replay`) and the replay call at `terminal_view.py:98`. No live call.
  - `mobile_terminal.py:245-246`: `def send_bytes(self, payload: bytes): self._terminal.send_bytes(payload)` — confirmed correct API for Python-to-Dart output.
  - `dep-flet-terminal.md:12`: "app→screen `write()/write_async()/send_bytes()` (fast path = DataChannel)".
- **Fix:** In `session_manager.py`, change `_on_bytes` to forward live bytes to `entry.mt` when it exists:
  ```python
  def _on_bytes(data: bytes) -> None:
      entry.feed(data)
      if entry.mt is not None:
          entry.mt.send_bytes(data)
  ```
  `entry.mt` is `None` before `TerminalView` first renders (bytes in that window are stored and replayed by `on_mount` — correct). After `TerminalView` assigns `entry.mt`, all subsequent PTY output flows live.
- **Risk if ignored:** The terminal is completely blank during a live session. Users see no shell output. The app is unusable as a terminal emulator.

---

### F2 · P1 · `show_search=True` at construction forces search bar open on every mount

- **Where:** `src/screens/terminal_view.py:71`
- **What:** `MobileTerminal` is constructed with `show_search=True`. `mobile_terminal.py:64` sets `self._search_bar.visible = bool(show_search)` at construction time, so the search bar is open by default every time a new session is opened. Once the user closes it by tapping the "X" button (`TerminalSearchBar.on_close`), there is no button, shortcut, or action in `TerminalView`'s UI to re-open it. CollabShell initialises with `show_search=False` and provides a search toggle in the session FAB menu.
- **Evidence:**
  - `terminal_view.py:71`: `show_search=True`
  - `mobile_terminal.py:60-64`: search bar visible state set directly from constructor arg; `self._search_bar.visible = bool(show_search)`.
  - The `quick_strip` at `terminal_view.py:169-175` and the header at lines 134-167 contain no search-toggle action.
- **Fix:** Set `show_search=False` in the constructor. If search is wanted, add a toggle button to the header or quick strip, calling `mt.toggle_search()` (`mobile_terminal.py:149-154`).
- **Risk if ignored:** Search bar consumes vertical space by default, and once dismissed it cannot be reopened without restarting the session.

---

### F3 · P1 · `bottom_inset` extracted from `on_resize` is always 0; keyboard-inset padding is dead code

- **Where:** `src/screens/terminal_view.py:88`, `terminal_view.py:93-94`, `terminal_view.py:226-228`
- **What:** `_on_resize` extracts `bottom = int(data.get("bottom_inset", 0) or 0)` from the resize JSON payload, stores it in the `inset` state variable, and conditionally wraps the body in `ft.Container(padding=ft.Padding.only(bottom=inset))`. The Dart `onResize` handler emits exactly `{"cols": width, "rows": height}` — `bottom_inset` is never present. The study and the Dart source agree; `viewInsets.bottom` is handled inside the Dart widget itself (`flet_terminal.dart:495,512-530`). `inset` is permanently 0; the padding branch at line 226 never executes.
- **Evidence:**
  - `docs/dependency-studies/flet-terminal.md:89`: `on_resize | JSON {"cols": int, "rows": int} (pixel dims deliberately dropped)`.
  - `docs/dependency-studies/flet-terminal.md:244`: "keyboard `viewInsets.bottom` padding" is applied inside `build` on the Dart side.
  - `docs/dependency-studies/flet-terminal.md:248`: "Events emitted: … resize{cols,rows}" — no `bottom_inset` field listed.
  - `terminal_view.py:88`: `bottom = int(data.get("bottom_inset", 0) or 0)` — default always used.
- **Fix:** Remove the `bottom_inset` extraction from `_on_resize`, remove the `inset` / `set_inset` state variable, and remove the conditional `ft.Container` wrapper at lines 226-228. The Dart side already handles the soft-keyboard inset.
- **Risk if ignored:** Dead UI code and false confidence. A test (`tests/test_terminal_wiring.py`) reportedly covers this by feeding a self-constructed dict with `"bottom_inset": 42`, masking the mismatch.

---

### F4 · P2 · `_toggle_fullscreen` double-writes: both `state.terminal_fullscreen` and local `use_state` trigger separate re-renders

- **Where:** `src/screens/terminal_view.py:130-132`
- **What:**
  ```python
  def _toggle_fullscreen(_e) -> None:
      state.terminal_fullscreen = not fullscreen
      set_fullscreen(not fullscreen)
  ```
  Both mutations fire independently. `state.terminal_fullscreen` is an `@ft.observable` field; writing it triggers a re-render of every component subscribed to `state` (via `ft.use_state(state)` at line 63). `set_fullscreen` triggers a second re-render from the local hook. The component renders twice per toggle.
- **Evidence:**
  - `terminal_view.py:63`: `_st, _ = ft.use_state(state)` — subscribes to all state changes.
  - `terminal_view.py:130-132`: both mutations in the same handler.
  - `core/state.py:36`: `terminal_fullscreen: bool = False` — observable field.
- **Fix:** Drive the component only from one source. If `state.terminal_fullscreen` is needed for cross-session persistence, remove the `use_state(False)` local variable and read `state.terminal_fullscreen` directly at line 66 (the component already re-renders on `state` changes). Remove `set_fullscreen` entirely. The toggle then becomes `state.terminal_fullscreen = not state.terminal_fullscreen`.
- **Risk if ignored:** One spurious extra render per fullscreen toggle; minor but violates the single-source-of-truth principle.

---

### F5 · P2 · `show_settings=False` hides the only in-widget theme/font/cursor picker, leaving no UI to change terminal settings

- **Where:** `src/screens/terminal_view.py:72`
- **What:** `show_settings=False` removes the settings cog from the extra-keys bar. `mobile_terminal.py:27-103` shows the settings menu is the only built-in path to change theme, cursor style, blink, and font size from within the terminal. `terminal_view.py` provides no alternative UI for any of those options. The theme *palette* is updated via `_apply_theme` → `mt.set_theme`, but cursor, blink, font size, and search toggle have no UI.
- **Evidence:**
  - `terminal_view.py:72`: `show_settings=False`.
  - `mobile_terminal.py:77-102`: settings menu built only when `show_settings=True`; includes theme, cursor, blink, zoom, search toggle.
  - `terminal_view.py:114-128`, `169-175`, `134-167`: header and quick strip contain no settings controls.
- **Fix:** Either set `show_settings=True` (simplest) or add explicit controls for at least font size and cursor style to the header row. If `show_settings` remains False, document the omission explicitly.
- **Risk if ignored:** Power users and accessibility users cannot change font size, cursor, or blink.

---

### F6 · P2 · `note_dismissed` initialized from `state.apt_note_dismissed` once; dismissal sets both but only local state drives render, creating stale UI on re-entry

- **Where:** `src/screens/terminal_view.py:65`, `terminal_view.py:213-217`
- **What:** `note_dismissed, set_note_dismissed = ft.use_state(state.apt_note_dismissed)` initializes local state from the observable at the component's first render. If the component unmounts and remounts (e.g., leaving and re-entering a session), `ft.use_state` reinitializes from `state.apt_note_dismissed` again — which is `True` after dismissal, so the note stays hidden. This part is correct. However, the "Got it" handler (lines 213-217) calls both `setattr(state, "apt_note_dismissed", True)` and `set_note_dismissed(True)`, producing two re-renders, the same double-write pattern as F4.
- **Evidence:**
  - `terminal_view.py:65`: `note_dismissed, set_note_dismissed = ft.use_state(state.apt_note_dismissed)`.
  - `terminal_view.py:213-217`: both `setattr(state, ...)` and `set_note_dismissed(True)` called.
  - `core/state.py:35`: `apt_note_dismissed: bool = False` — observable.
- **Fix:** Same as F4 — read `state.apt_note_dismissed` directly (no local `use_state`), update only the observable. The component's `ft.use_state(state)` subscription at line 63 already drives re-renders on state changes.
- **Risk if ignored:** Extra render on dismiss; minor.

---

### F7 · P2 · `contextlib.suppress(Exception)` in `_apply_theme` silently swallows all theme-switch errors

- **Where:** `src/screens/terminal_view.py:119-120`
- **What:**
  ```python
  with contextlib.suppress(Exception):
      mt.set_theme(name)
  ```
  `mt.set_theme` (`mobile_terminal.py:156-165`) calls `get_theme(theme_name)` which returns `None` for unknown names, in which case the `if preset:` guard skips the update silently. The `contextlib.suppress(Exception)` adds a second suppression layer. If `name` were ever invalid or `control_update` raised, the failure would be invisible.
- **Evidence:**
  - `terminal_view.py:117-120`: `_apply_theme` body.
  - `mobile_terminal.py:156-166`: `set_theme` with `if preset:` guard already handles unknown names.
- **Fix:** Remove `contextlib.suppress(Exception)`; the inner `if preset:` guard is sufficient. If truly needed, narrow to `contextlib.suppress(RuntimeError)` (the renderer-not-set error that can occur if the effect fires before mount).
- **Risk if ignored:** Silent theme failures are undetectable during development.

---

### F8 · P3 · `SessionSelectorView` accesses `page._controller` and `controller.session_manager` internals directly

- **Where:** `src/screens/terminal_view.py:237-238`
- **What:**
  ```python
  controller = getattr(page, "_controller", None)
  manager = getattr(controller, "session_manager", None)
  ```
  This pattern reaches through a private monkeypatched attribute into the controller's internals. The swarm's `app_shell.py` audit (F3) already flagged `page._controller` as an architecture violation. The session list (`manager.entries`) should be exposed through the observable `state` or through `ControllerMethodsCtx` rather than by direct attribute walk.
- **Evidence:**
  - `terminal_view.py:237-238`: double `getattr` chain.
  - `app_controller.py:84`: `self.page._controller = self` — injection point.
  - D-017 §3 mandates observable state for cross-component data.
- **Fix:** Expose `manager.entries` through a `state.open_sessions` list updated in the controller whenever sessions open or close; `SessionSelectorView` reads state only.
- **Risk if ignored:** Fragile coupling; `app_shell.py` F3 already documents the architecture violation. Keeping the pattern in two places makes refactoring harder.

---

## Verified-good list

- **`MobileTerminal` constructed inside `@ft.component` render** (`terminal_view.py:68-78`): the `entry.mt is None` guard ensures construction happens exactly once per entry, always during a component render. `dep-flet-terminal.md:36` confirms construction outside a render tree raises `RuntimeError`; this guard prevents that.
- **`set_on_bytes` wiring direction** (`terminal_view.py:105`): `mt.set_on_bytes(lambda payload: _write(entry, payload))` correctly registers the callback for bytes arriving FROM Dart (keyboard input) → `os.write` to PTY master. `mobile_terminal.py:337-338`; `terminal.py:123-127`.
- **`on_data` wiring direction** (`terminal_view.py:106-108`): handles the soft-keyboard string path, encodes to UTF-8 and calls `_write`. `terminal.py:48`; D-017 §4.
- **`entry.wired` guard** (`terminal_view.py:81`): prevents re-registering handlers on re-renders of the same component instance while `entry.mt` persists. Handlers on a persistent object need be set only once.
- **`on_mount` replay sequence** (`terminal_view.py:96-98`): `mt.clear_pending()` drops stale queued writes from before this mount, then `entry.replay(mt.send_bytes)` replays all scrollback. This is the correct order regardless of whether `data_channel_open` fires before or after `on_mount`, because `send_bytes` queues internally if the channel is not ready. `terminal.py:129-140`; `mobile_terminal.py:415-418`.
- **Theme name lookup** (`terminal_view.py:34`, `75`): `BUILTIN_THEMES.get(_theme_name())` with `_theme_name()` returning `"Colab Light"` or `"JetBrains Dark"` — both verified present in `themes.py:9-66`.
- **`_theme_name()` for `set_theme` call** (`terminal_view.py:120`): `mt.set_theme(name)` accepts a string name and calls `get_theme(name)` internally. `mobile_terminal.py:156-165`; `themes.py:69-73`.
- **`ft.context.page`** (`terminal_view.py:61`): `context.py:46-69` confirms `ft.context.page` raises `RuntimeError` if accessed outside a running app; safe inside `@ft.component`.
- **`page.show_dialog` / `page.pop_dialog`** (`terminal_view.py:47,52,55`): `base_page.py:402,427`.
- **`ft.Padding.symmetric` / `ft.Padding.only`** (`terminal_view.py:174,227`): both are `@classmethod`s on `Padding`. `padding.py:46,54`.
- **`ft.Alignment.TOP_LEFT`** (`terminal_view.py:192`): `alignment.py:87-89`, confirmed as `AlignmentProperty(-1.0, -1.0)`.
- **All `ft.Icons` used**: `FULLSCREEN` (68845), `FULLSCREEN_EXIT` (68846), `ARROW_BACK` (65957), `TERMINAL` (73289), `CLOSE` (66945), `INFO` (69374), `APPS` (65937), `INVENTORY_2_OUTLINED` (69446) — all present in `material/icons.json`.
- **`ft.FontWeight.BOLD`, `ft.ScrollMode.AUTO`, `ft.CrossAxisAlignment.CENTER`**: all verified present in installed flet 1.0.4.
- **`ft.use_effect` signature** (`terminal_view.py:122`): `use_effect(setup, dependencies, cleanup=None)` — `use_effect.py:42-46`. Called as `ft.use_effect(_apply_theme, [state.theme_revision])` — correct.
- **`auto_focus=False`** (`terminal_view.py:76`): correct; avoids popping the soft keyboard on open, matching CollabShell/example guidance per `dep-flet-terminal.md`.
- **Banner placement** (`terminal_view.py:181-182`, D-017 §7): ad is inserted at `controls[0]`, header at `controls[1]` (then shifted to `[2]` when the apt note is visible), so the header always separates the ad from the terminal. Matches D-017 §7.
- **`except OSError, ValueError:` in `session_service.py:123`**: Python 3.14 parses the comma form as `except (OSError, ValueError):` (verified via `ast.unparse`; runtime test catches both types). Functionally correct though stylistically Python-2-era; not a bug.
- **`_confirm_close` uses `ft.AlertDialog`** with `title`, `content`, `actions`: all three fields verified in `alert_dialog.py:43,57,64`.

---

## Unverified

- **`on_resize` payload on 0.4.0 Dart side**: the study was written against 0.3.9 Dart source. The installed Python wheel is 0.4.0 but no Dart source is available in `.venv` to confirm `{"cols","rows"}` format has not changed. Both the 0.3.9 study (`:89`) and the 0.4.0 Python `on_resize` property declaration (`terminal.py:49`) are consistent with this format; the F3 finding is high-confidence but the Dart source for 0.4.0 is UNVERIFIED.
- **`on_mount` Dart firing frequency**: the study says `on_mount` fires "whenever the Dart xterm view is (re)created". Whether it fires on every tab switch (requiring `clear_pending + replay` each time) or only on the first creation is UNVERIFIED from the Python source alone; the replay logic is correct in either case.
- **`ft.SnackBar(ft.Text(message))` constructor**: `SnackBar.content` is typed `Annotated[Control, ...]`; `ft.Text` is a `Control`. Functionally correct but the Annotated constraint metadata was not fully inspected.
- **Race between PTY start and `entry.mt` assignment**: `app_controller.open_session` starts the PTY in a thread (`asyncio.to_thread`) then sets `state.active_session`; `TerminalView` renders on the next event-loop turn and assigns `entry.mt`. Bytes emitted before that assignment go to scrollback only and are replayed on `on_mount` — this is the intended pattern, but the exact timing guarantee is UNVERIFIED.
