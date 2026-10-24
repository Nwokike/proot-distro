# tests/test_terminal_wiring.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** tests/test_terminal_wiring.py · src/screens/terminal_view.py · .venv/lib/python3.14/site-packages/flet_terminal/ (0.4.0) · src/services/session_manager.py · src/services/session_service.py · src/core/state.py · **Date:** 2026-10-24

## What it does / how the app uses it

`tests/test_terminal_wiring.py` asserts the contract that `TerminalView` wires both input paths (binary `set_on_bytes` and soft-keyboard string `on_data`), forwards resize, and replays scrollback on mount. It builds a `SessionEntry` whose `mt` is a `unittest.mock.MagicMock` (tests/test_terminal_wiring.py:20), so every handler assertion runs against a mock, not the real `MobileTerminal`. The real `TerminalView` (src/screens/terminal_view.py:60-228) constructs `MobileTerminal` lazily at render (terminal_view.py:68-79), wires `set_on_bytes`/`on_data`/`on_resize`/`on_mount`/`on_title_change` once per session (terminal_view.py:105-112), and `_on_mount` calls `mt.clear_pending()` then `entry.replay(mt.send_bytes)` (terminal_view.py:96-98). The app's `SessionEntry.replay` iterates the scrollback deque calling `send_bytes` per chunk (src/services/session_manager.py:41-43); `_write` forwards to `ProotSession.write` → `os.write(master_fd, ...)` (src/services/session_service.py:136-140); resize forwards to `ProotSession.resize` → `TIOCSWINSZ` (src/services/session_service.py:142-150).

## Findings

### F1 · P0 · MobileTerminal MagicMock hides the missing live send_bytes wiring (known P0)
- **Where:** tests/test_terminal_wiring.py:17-22 (fixture builds `item.mt = MagicMock()`); tests/test_terminal_wiring.py:46 (`entry.mt.send_bytes.side_effect = sent.append`); src/screens/terminal_view.py:98 (`entry.replay(mt.send_bytes)`), terminal_view.py:105 (`mt.set_on_bytes(...)`).
- **What:** The fixture replaces `MobileTerminal` with a `MagicMock`, so `send_bytes` is a no-op that records calls but never touches the Dart channel/PTY. Consequently the test cannot detect whether the real live `send_bytes` → `DataChannel.send` → PTY path is broken. The real wiring exists in `TerminalView` (terminal_view.py:105-108, 96-98) and `MobileTerminal.send_bytes` forwards to `Terminal.send_bytes` which queues to `_pending_writes` until the channel is ready (.venv/.../mobile_terminal.py:245-246; .venv/.../terminal.py:129-140), but the test asserts nothing against that live path. This is the acknowledged P0: the mock hides whether live `send_bytes` actually reaches the shell.
- **Evidence:** `entry.mt = MagicMock()` at tests/test_terminal_wiring.py:20 makes every attribute auto-existent and callable; `send_bytes.side_effect = sent.append` at :46 records into a Python list instead of sending to the PTY. All 6 tests pass (verified by run) despite exercising only the mock.
- **Fix / opportunity:** Add a live-path test using a real `MobileTerminal` (or a stub capturing `send_bytes` → channel) that mounts it on a page and confirms bytes reach `ProotSession.write`/channel, wired to `entry.replay` on mount. Keep architecture: do not modify `terminal_view.py`; only extend the test file (read-only on app code, but the test file itself is the audit subject — this finding is reported, not fixed here per read-only rule).
- **Risk if ignored:** A regression that breaks the live `send_bytes` channel/PTY path passes the suite silently; shells appear wired but never receive input on device.

### F2 · P1 · `test_both_input_paths_are_wired` is vacuous against MagicMock
- **Where:** tests/test_terminal_wiring.py:35-39 (`assert callable(handlers["on_bytes"])` / `callable(handlers["on_data"])`).
- **What:** With `entry.mt = MagicMock()`, `entry.mt.set_on_bytes` and `entry.mt.on_data` are auto-created Mock attributes that are always `callable`, regardless of whether `TerminalView` ever calls them. The real `MobileTerminal` does expose both (`.venv/.../mobile_terminal.py:337-338` `set_on_bytes`, :342-349 `on_data` setter), and `TerminalView` assigns both (terminal_view.py:105-108), but the test does not verify the assignment actually happened on a real widget — it would pass even if `terminal_view.py` never called `set_on_bytes`/`on_data`.
- **Evidence:** `MagicMock` attribute access always returns a callable Mock; tests/test_terminal_wiring.py:38-39 assert only `callable(...)`, which is trivially True for a Mock.
- **Fix / opportunity:** Assert that `terminal_view.py` source references `set_on_bytes` and `on_data` assignments (already true at terminal_view.py:105,106-108), or drive a real/stub `MobileTerminal` and confirm the handlers were assigned and invoked. The existing private-API guard (tests/test_terminal_wiring.py:68-77) is a good model for source-based assertions.
- **Risk if ignored:** Silent coverage collapse; input-path wiring bugs are not caught by this test.

### F3 · P1 · Replay-on-mount only tests `SessionEntry.replay`, not the `mt.on_mount` trigger
- **Where:** tests/test_terminal_wiring.py:42-52 (`test_replay_clears_pending_then_sends_scrollback_in_order`); src/screens/terminal_view.py:96-98 (`_on_mount`), terminal_view.py:110 (`mt.on_mount = _on_mount`).
- **What:** The test calls `entry.mt.clear_pending()` and `entry.replay(entry.mt.send_bytes)` directly (tests/test_terminal_wiring.py:48-49), exercising `SessionEntry.clear_pending`/`replay` against the MagicMock. It never fires `mt.on_mount`, so it does not confirm that mount triggers `clear_pending` + `replay` in order on the real widget. `_on_mount` is wired at terminal_view.py:110 but untested as a trigger.
- **Evidence:** tests/test_terminal_wiring.py:46-49 use `entry.mt.send_bytes` as the send target and assert `clear_pending.assert_called_once()` and `sent == [...]`; no `entry.mt.on_mount(...)` invocation exists in the test.
- **Fix / opportunity:** Add a test that calls `entry.mt.on_mount(None)` on a stub capturing `clear_pending` call order and `send_bytes` sequence, confirming `clear_pending` precedes replay and chunks arrive in scrollback order.
- **Risk if ignored:** On tab switch/remount, scrollback may not replay (CollabShell pattern depends on mount firing), leaving the terminal buffer empty.

### F4 · P1 · Resize tests assert JSON parsing, not the `_on_resize` handler wiring
- **Where:** tests/test_terminal_wiring.py:55-60 (`test_resize_payload_carries_cols_rows_and_inset`), :63-65 (`test_malformed_resize_payload_is_ignored`); src/screens/terminal_view.py:83-94 (`_on_resize`), terminal_view.py:109 (`mt.on_resize = _on_resize`).
- **What:** Both tests parse hardcoded JSON strings with `json.loads`; neither invokes `_on_resize` nor asserts that `mt.on_resize` is assigned or that `entry.session.resize(cols, rows)` / `set_inset(bottom)` fire. The real `_on_resize` catches `ValueError` (terminal_view.py:89-90) but `int(data.get(...))` can also raise `TypeError` if `data` is not a dict — UNVERIFIED whether that's handled.
- **Evidence:** tests/test_terminal_wiring.py:56-60 and :64-65 call `json.loads` directly; no reference to `entry.mt.on_resize`, `_on_resize`, `entry.session.resize`, or `set_inset`.
- **Fix / opportunity:** Drive `entry.mt.on_resize(event)` with a fake `e.data` JSON payload and assert `entry.session.resize` called with parsed cols/rows and `set_inset` called; add a malformed-payload case that asserts no crash/no resize call.
- **Risk if ignored:** Resize/keyboard-inset wiring bugs go undetected; terminal geometry may be wrong after soft-keyboard show.

### F5 · P2 · Search capability exists in flet-terminal 0.4.0 and is enabled, but untested
- **Where:** src/screens/terminal_view.py:71 (`show_search=True`); .venv/.../mobile_terminal.py:60-63 (`TerminalSearchBar` wired `on_search=self._terminal.search`), :284-285 (`MobileTerminal.search`); .venv/.../terminal.py:296-306 (`Terminal.search`); .venv/.../search_bar.py:18-157 (`TerminalSearchBar` live search + stepping).
- **What:** `MobileTerminal` exposes `search` (mobile_terminal.py:284-285) and `Terminal` exposes `search` (terminal.py:296-306); `show_search=True` in the view (terminal_view.py:71) creates the search bar. The test file has zero search coverage. `BUILTIN_THEMES` includes "Colab Light" and "JetBrains Dark" (`.venv/.../themes.py:52-65, 24-37`), matching `_theme_name()` (terminal_view.py:33-34). Version drift: the dependency study documents flet-terminal 0.3.9 (`docs/dependency-studies/flet-terminal.md:1`) but the installed wheel is 0.4.0 (`.venv/.../flet_terminal/__init__.py:9`), and pyproject.toml pins `>=0.4.0` — all APIs relied on were spot-verified against 0.4.0 source.
- **Evidence:** No search-related assertion anywhere in tests/test_terminal_wiring.py (grep found none).
- **Fix / opportunity:** Add a test driving `mt.search(query)` and asserting `Terminal.search` is invoked; or assert `show_search=True` present in source. Low cost since the dependency is frozen and already shipped.
- **Risk if ignored:** Search feature (a headline MobileTerminal capability) ships with no regression coverage.

### F6 · P2 · Full-screen toggle exists in state/view but is untested
- **Where:** src/core/state.py:36 (`terminal_fullscreen: bool = False`); src/screens/terminal_view.py:66 (`fullscreen, set_fullscreen = ft.use_state(state.terminal_fullscreen)`), :130-132 (`_toggle_fullscreen`), :178-197 (chrome/ad/quick_strip gated on `fullscreen`).
- **What:** `_toggle_fullscreen` flips `state.terminal_fullscreen` and local state; the view conditionally omits the banner ad/header chrome/quick strip in full-screen mode. The test file has zero full-screen coverage.
- **Evidence:** No full-screen assertion anywhere in tests/test_terminal_wiring.py.
- **Fix / opportunity:** Add a test calling `_toggle_fullscreen` (or simulating the IconButton `on_click`) and asserting `state.terminal_fullscreen` toggles and `set_fullscreen` called. Requires a page/context; may be UNVERIFIED without a renderer.
- **Risk if ignored:** Full-screen UX regression (ad/chrome not hidden) undetected.

### F7 · P3 · Assertion quality is thin; some tests assert JSON/stdlib, not view behavior
- **Where:** tests/test_terminal_wiring.py:55-65 (resize tests assert `json.loads`), :79-87 (`test_terminal_view_is_built_inside_the_component_tree` asserts substring `"MobileTerminal(" in source` and `"entry.mt is None" in source`).
- **What:** Substring source checks are brittle (a rename breaks them without a real behavior change) and weak (presence of a string ≠ correct wiring). `test_terminal_source_does_not_reach_into_private_apis` (terminal_view.py:68-77) is a good, meaningful guard: it confirms no `mt._terminal` / `._pending_writes` reach-ins, and the real `MobileTerminal` does encapsulate `_terminal` (mobile_terminal.py:43) and `_pending_writes` lives on `Terminal` (terminal.py:68) — the view correctly avoids both.
- **Evidence:** tests/test_terminal_wiring.py:72-75 reads terminal_view.py source; :75 asserts `"mt._terminal" not in source` and :76 asserts `"._pending_writes" not in source` — both hold (verified by reading terminal_view.py).
- **Fix / opportunity:** Replace brittle substring checks with behavior-driven assertions on a real/stub widget; keep the private-API guard (it is verified-good).
- **Risk if ignored:** Tests give false confidence; refactors that preserve strings but break wiring pass.

## Missed capabilities (dependency audits only)
N/A — this is a test/view wiring audit, not a dependency audit. (flet-terminal 0.4.0 capabilities already enumerated in F5; all APIs spot-verified against installed source.)

## Verified-good list
- `src/screens/terminal_view.py` wires both input paths: `set_on_bytes` (terminal_view.py:105) → `_write` → `ProotSession.write` (session_service.py:136-140); `on_data` (terminal_view.py:106-108) → `_write` with UTF-8 encode.
- `src/screens/terminal_view.py` wires resize via `mt.on_resize = _on_resize` (terminal_view.py:109) → `entry.session.resize(cols, rows)` (terminal_view.py:91-92) → `ProotSession.resize`/`TIOCSWINSZ` (session_service.py:142-150); inset applied via `set_inset(bottom)` (terminal_view.py:93-94).
- `src/screens/terminal_view.py` wires replay-on-mount: `mt.on_mount = _on_mount` (terminal_view.py:110) → `mt.clear_pending()` + `entry.replay(mt.send_bytes)` (terminal_view.py:97-98).
- `src/screens/terminal_view.py` enables search (`show_search=True`, terminal_view.py:71) and `MobileTerminal.search`/`Terminal.search` exist in flet-terminal 0.4.0 (mobile_terminal.py:284-285; terminal.py:296-306).
- `src/screens/terminal_view.py` implements full-screen toggle (`_toggle_fullscreen`, terminal_view.py:130-132) gated on `state.terminal_fullscreen` (state.py:36).
- `src/screens/terminal_view.py` constructs `MobileTerminal` lazily at render (terminal_view.py:68-79), not at import; `entry.mt is None` guard at terminal_view.py:68.
- The private-API guard `test_terminal_source_does_not_reach_into_private_apis` (tests/test_terminal_wiring.py:68-77) is valid: view avoids `mt._terminal` and `._pending_writes`.
- All 6 tests pass under pytest 9.1.1 / Python 3.14.9 / flet 1.0.4 (verified by run).

## Unverified
- Whether the live `send_bytes` → `DataChannel` → PTY path actually delivers bytes on device (mock hides it; P0, F1).
- Whether `int(data.get(...))` in `_on_resize` can raise `TypeError`/`AttributeError` for non-dict `e.data` (only `ValueError` caught at terminal_view.py:89-90).
- End-to-end search (needs Dart/client renderer; F5).
- End-to-end full-screen visual behavior (needs renderer; F6).
- Behavior of `MobileTerminal` constructor/full widget tree without a Flet page context (read-only, not executed).
