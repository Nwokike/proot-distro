# flet-terminal 0.3.9 — exhaustive API reference

**Package:** `flet-terminal` 0.3.9 · **Owner:** Onyeka Nwokike · **Companion:** `docs/reference/dep-flet-terminal.md` (integration study + M1 blueprint — this doc is the API-exhaustive companion; it does not repeat the blueprint, it proves every claim against source).
**Context:** `docs/roadmap.md` (M1 refactor 0.3.x → 0.4.0, M4 terminal integration), `docs/decisions.md` (D-010: flet stays 1.0.4).
**Owner requirement:** every API exposed, documented exhaustively — one-to-one, everything exposed.
**Anti-hallucination rule (owner-mandated):** every signature below was verified against the installed source (`file:line`) or live introspection with `...\.venv\Scripts\python.exe`. Anything not verifiable is labeled **unverified** — nothing is guessed.

**Sources inspected:**
- Installed wheel: `/home/maikel/.zcode/workspace/default/proot-distro-flet/.venv/Lib/site-packages/flet_terminal/` (`__init__.py`, `terminal.py` 405 L, `mobile_terminal.py` 445 L, `extra_keys.py` 397 L, `search_bar.py` 158 L, `themes.py` 74 L, `tokens.py` 32 L, `frozen_support.py` 106 L)
- Bundled Dart: `...\.venv\Lib\site-packages\flutter\flet_terminal\` (`lib/flet_terminal.dart`, `lib/src/extension.dart`, `lib/src/flet_terminal.dart` 594 L, `pubspec.yaml`, `CHANGELOG.md`, `LICENSE`, `README.md`)
- Metadata: `...\.venv\Lib\site-packages\flet_terminal-0.3.9.dist-info\{METADATA,RECORD,WHEEL}`
- Repo clone (docs/changelog/example): `/home/maikel/.zcode/workspace/default/flet-terminal/` (`pyproject.toml`, `LICENSE`, `main.py`, `examples/flet_terminal_example/src/{app.py:264,main.py:29,pty_service.py:173,ui_helpers.py:106}`)
- Live introspection: `inspect.signature` dumps for all exports (see §6).

---

## 1. Identity

| Field | Value | Evidence |
|---|---|---|
| Distribution name | `flet-terminal` | `METADATA:2` (`Name: flet-terminal`) |
| Version | `0.3.9` | `METADATA:3`; `pyproject.toml:3`; Dart `pubspec.yaml:3` (all three agree — no drift at 0.3.9) |
| Summary | `Native GPU-accelerated Terminal control for Flet using xterm.dart` | `METADATA:4`; `pyproject.toml:4` |
| Author | Onyeka Nwokike `<nwokikeonyeka@gmail.com>` | `METADATA:5`; `pyproject.toml:7-9` |
| `Requires-Dist` | `flet>=1.0.1` (exactly one entry, no extras) | `METADATA:11`; `pyproject.toml:10-12` |
| `Requires-Python` | `>=3.14` (stricter than flet's `>=3.10` — M1 widens to `>=3.10`) | `METADATA:9`; `pyproject.toml:6` |
| License metadata | **NONE in the wheel.** `METADATA` has no `License:` / `License-File:` field; `pyproject.toml:22-23` sets `[tool.setuptools] license-files = []` explicitly. The license *text* exists only as `LICENSE` at the repo root (MIT, `Copyright (c) 2026 Onyeka Nwokike`, verified first 5 lines) and `flutter/flet_terminal/LICENSE` (MIT, same holder). M1 adds `license = "MIT"` + `license-files = ["LICENSE"]`. | `METADATA` full read (11 lines, no license); dist-info listing (`INSTALLER,METADATA,RECORD,REQUESTED,WHEEL,top_level.txt` — no LICENSE); `pyproject.toml:23` |
| Project URLs (order) | `Repository, Homepage, Issues` → all `https://github.com/Nwokike/flet-terminal[/issues]` | `METADATA:6-8`; `pyproject.toml:14-17` (M1 reorders to Homepage/Repository/Issues per house standard) |
| Wheel tag | `py3-none-any`, `Root-Is-Purelib: true`, built by `setuptools 84.0.0` | `WHEEL` full read (4 lines) |
| Top-level import | `flet_terminal` (+ `flutter` namespace dir for the Dart payload) | `top_level.txt` |

### Wheel contents (exact, from `RECORD`)

Python modules (8 files under `flet_terminal/`):
`__init__.py`, `extra_keys.py`, `frozen_support.py`, `mobile_terminal.py`, `search_bar.py`, `terminal.py`, `themes.py`, `tokens.py`.

Flutter payload (7 files under `flutter/flet_terminal/`):
`CHANGELOG.md`, `LICENSE`, `README.md`, `lib/flet_terminal.dart`, `lib/src/extension.dart`, `lib/src/flet_terminal.dart`, `pubspec.yaml`.

Shipped by the glob in `pyproject.toml:19-20`:
```toml
[tool.setuptools.package-data]
"flutter.flet_terminal" = ["**/*"]
```
The `**/*` glob is why Dart `README.md`/`CHANGELOG.md`/tests ship inside the wheel — M1 narrows to `["pubspec.yaml", "lib/**"]`. No `tokens.py` exclusion issue: `tokens.py` is a real runtime import (`extra_keys.py:12-20`), not dead code.

---

## 2. Complete Python API

Root package `__init__.py:1-18`. Exactly 8 names exported, verified by live introspection (`m.__all__`):

```python
from flet_terminal.extra_keys import DEFAULT_EXTRA_KEYS, ExtraKeysBar   # __init__.py:3
from flet_terminal.mobile_terminal import MobileTerminal                 # __init__.py:4
from flet_terminal.search_bar import TerminalSearchBar                   # __init__.py:5
from flet_terminal.terminal import ShortcutEvent, Terminal               # __init__.py:6
from flet_terminal.themes import BUILTIN_THEMES, get_theme              # __init__.py:7
__all__ = ["BUILTIN_THEMES","DEFAULT_EXTRA_KEYS","ExtraKeysBar","MobileTerminal",
           "ShortcutEvent","Terminal","TerminalSearchBar","get_theme"]   # __init__.py:9-18
```

NOT exported from root (import by full path): `ModifierState`, `ModifierKey` (`extra_keys.py`), `thaw`, `control_update` (`frozen_support.py`, `__all__` there), all `tokens.py` constants. The wheel README's `from flet_terminal.frozen_support import thaw` path is correct and verified.

### 2.1 `Terminal` — `@control("FletTerminal") class Terminal(ft.LayoutControl)` (`terminal.py:27-405`)

Control type string `"FletTerminal"` (`terminal.py:27`) is the unversioned wire contract matched by Dart `extension.dart:10` (`case "FletTerminal"`). Because it subclasses `ft.LayoutControl`, the generated `__init__` also accepts the full inherited layout surface (verified in the introspected signature: `expand`, `expand_loose`, `col`, `opacity`, `tooltip`, `badge`, `visible`, `disabled`, `rtl`, `width/height/left/top/right/bottom`, `align`, `margin`, `rotate/scale/offset/flip/transform`, `aspect_ratio`, `animate_*`, `size_change_interval`, `on_size_change`, `on_animation_end`, plus `data/key/ref`). Only the terminal's own 10 props + 10 events are tabulated below; the rest is stock flet 1.0.4 `LayoutControl`.

#### Every property (type / default / doc)

| # | Property | Type | Default | Source | Notes |
|---|---|---|---|---|---|
| 1 | `scrollback` | `int \| None` | `10000` | `terminal.py:34` | Max scrollback lines; read once on Dart `initState` as `getInt("scrollback", 10000)` → `qt.Terminal(maxLines:)` (`flet_terminal.dart:103-104`). Changing it post-mount does **not** resize the ring buffer (**unverified** whether xterm honors a later change — no Dart update path reads it in `build`). |
| 2 | `font_family` | `str \| None` | `"JetBrains Mono"` | `terminal.py:35` | Passed as `TerminalStyle(fontFamily:)` (`flet_terminal.dart:429,432`). **Not bundled on Android — fallback is OS-dependent (unverified which font actually renders on-device); M4 must verify or ship the font.** |
| 3 | `font_size` | `float \| None` | `11.0` | `terminal.py:36` | `TerminalStyle(fontSize:)` (`flet_terminal.dart:430,433`). Live-zoomable via `MobileTerminal.zoom_*`. NOTE: wheel README table says `13.0` — stale; source default is `11.0` (changed in 0.2.2, `CHANGELOG.md:17`). |
| 4 | `cursor_blink` | `bool \| None` | `True` | `terminal.py:37` | Real Dart-side `Timer.periodic(530ms)` toggling `cursorVisibleMode` (`flet_terminal.dart:559-575`). Synced per-`build` via `_syncedBlink` (`flet_terminal.dart:450-453`). |
| 5 | `cursor_style` | `str \| None` | `"block"` | `terminal.py:38` | `"block"` → `TerminalCursorType.block`; `"underline"` → underline; `"bar"`/`"verticalBar"` → verticalBar; anything else → block (`flet_terminal.dart:437-441`). Wheel README claim "only block supported" is **stale** — all three parse today. |
| 6 | `theme` | `dict[str, Any] \| None` | `None` | `terminal.py:39` | ANSI palette dict; `None` → `TerminalThemes.defaultTheme` (`flet_terminal.dart:376-377`). `MobileTerminal` defaults it to `BUILTIN_THEMES["JetBrains Dark"]` (`mobile_terminal.py:49`). See §2.5 for keys. |
| 7 | `read_only` | `bool \| None` | `False` | `terminal.py:40` | → `TerminalView(readOnly:)` (`flet_terminal.dart:455,469`); disables canvas keyboard input, DataChannel output still renders. |
| 8 | `auto_focus` | `bool \| None` | `True` | `terminal.py:41` | → `TerminalView(autofocus:)` (`flet_terminal.dart:454,468`). |
| 9 | `ctrl_active` | `bool \| None` | `False` | `terminal.py:44` | Sticky CTRL, synced bidirectionally: Python→Dart as prop, Dart→Python via `updateProperties({ctrl_active:false,...}, python:true)` + `modifier_reset` event (`flet_terminal.dart:138-144`). |
| 10 | `alt_active` | `bool \| None` | `False` | `terminal.py:45` | Same bidirectional sync as `ctrl_active`. |

#### Every event (payload shapes — Dart `triggerEvent` call sites)

| # | Handler attr | Declared type | Fired from Dart | `e.data` payload | Source |
|---|---|---|---|---|---|
| 1 | `on_data` | `ft.ControlEventHandler \| None` | `TerminalView.onOutput` fallback (no DataChannel) + `paste`/secondary-tap fallback | `str` — processed terminal input text | `terminal.py:48`; `flet_terminal.dart:150,260,489` |
| 2 | `on_resize` | same | `_terminal.onResize` | JSON `{"cols": int, "rows": int}` (pixel dims deliberately dropped) | `terminal.py:49`; `flet_terminal.dart:165-172` |
| 3 | `on_modifier_reset` | same | after sticky CTRL/ALT consumed a keystroke | `""` (empty string) | `terminal.py:50`; `flet_terminal.dart:144` |
| 4 | `on_title_change` | same | `_terminal.onTitleChange` (OSC 0 / OSC 2) | `str` title | `terminal.py:51`; `flet_terminal.dart:155-157` |
| 5 | `on_bell` | same | `_terminal.onBell` (`\a`/`0x07`) | `""` | `terminal.py:52`; `flet_terminal.dart:160-162` |
| 6 | `on_selection_change` | same | (a) debounced controller listener (150 ms) → `{"has_selection": bool, "text": str}`; (b) `search` method → `{"query","found","count","index"}` | JSON string, two shapes — consumers must branch on `"found" in data` (as `mobile_terminal.py:118` does) | `terminal.py:53`; `flet_terminal.dart:206-224,350-368` |
| 7 | `on_copy` | same | secondary-tap with selection (Dart clipboard path) + programmatic `MobileTerminal.copy_selection_async` via `_trigger_event("copy", text)` | `str` selected text | `terminal.py:54`; `flet_terminal.dart:480`; `mobile_terminal.py:317` |
| 8 | `on_mount` | same | `initState` — fired on **every** Dart view (re)creation (tab switches, remounts) | `""` | `terminal.py:55`; `flet_terminal.dart:101` |
| 9 | `on_shortcut` | `ft.EventHandler[ShortcutEvent] \| None` | `_handleShortcutKey` — ONLY when a handler is set (`hasEventHandler("shortcut")` gate), else keys flow untouched | `{"shortcut": "<machine-name>"}` → typed `ShortcutEvent.shortcut` | `terminal.py:56`; `flet_terminal.dart:64-94` |
| 10 | `on_data_channel_open` | `ft.EventHandler[DataChannelOpenEvent] \| None` | `didChangeDependencies` after `openDataChannel()` | `{"channel_name": "pty", "channel_id": int}` | `terminal.py:59`; `flet_terminal.dart:197-200` |

Internal plumbing (not app-facing but load-bearing): `init()` (`terminal.py:61-70`) creates `_lock`, `_channel=None`, `_on_bytes_handler=None`, default `_handle_data_channel_open`, `_on_unmount_callback=None`, `_pending_writes=[]`, `_dart_ready=False`, `_channel_ready=False`. `before_event()` (`terminal.py:72-74`) and `did_mount()` (`terminal.py:105-108`) both call `_mark_dart_ready()` — the drain trigger.

#### Every method (signatures + sync/async + queueing semantics)

Queue model: `_pending_writes: list[(task_fn, args)]` guarded by `threading.Lock`. `_mark_dart_ready()` (`terminal.py:76-103`) sets `_dart_ready=True`, swaps the queue, and for each entry: re-queues if no `page`/not ready, or if `task_fn is send_bytes` and channel not ready; runs coroutine fns via `page.run_task`, **calls sync fns directly** (the 0.3.9 fix — Flet 1.0 `run_task` rejects sync callables, previously re-queued forever; `CHANGELOG.md:4`); on `Exception` re-queues with `logger.debug`. `will_unmount()` (`terminal.py:141-151`) sets `_dart_ready=False`, clears the queue, fires `_on_unmount_callback`.

| Method | Signature | Sync/Async | Transport | Queue when not ready | Source |
|---|---|---|---|---|---|
| `set_on_bytes` | `(self, handler)` | sync, immediate | local only — stores `_on_bytes_handler`, attaches to live channel via `channel.on_bytes(handler)` | never queued (local registration) | `terminal.py:117-121` |
| `send_bytes` | `(self, payload: bytes)` | sync, immediate | `DataChannel.send(payload)` (binary fast path) | queues `(send_bytes,(payload,))`; also re-queued on `Exception` | `terminal.py:123-134` |
| `send_input` | `(self, payload: bytes)` | sync, immediate | local loopback — calls `_on_bytes_handler(payload)` directly, **bypasses Dart entirely** (virtual-key path) | dropped silently if no handler (no queue) | `terminal.py:136-140` |
| `write_async` | `(self, data: str \| bytes)` | `async` | channel fast path if ready (str→utf-8 `errors="ignore"`); else `_invoke_method("write",{"data": str})` | queues `(write_async,(data,))` on no-page/not-ready/`RuntimeError` (both before AND after the invoke attempt) | `terminal.py:153-179` |
| `write` | `(self, data: str \| bytes)` | sync wrapper | channel fast path if ready; else `page.run_task(write_async, data)` | queues `(write_async,(data,))` — note: queues the **async** variant | `terminal.py:181-199` |
| `clear_async` | `(self)` | `async` | `_invoke_method("clear")` (no channel path — clears scrollback+buffer Dart-side) | queues `(clear_async,None)` | `terminal.py:201-216` |
| `clear` | `(self)` | sync → `page.run_task(clear_async)` | same | queues `(clear_async,None)` | `terminal.py:218-228` |
| `focus_async` | `(self)` | `async` | `_invoke_method("focus")` → `_focusNode.requestFocus()` | queues `(focus_async,None)` | `terminal.py:230-245` |
| `focus` | `(self)` | sync → `page.run_task(focus_async)` | same | queues `(focus_async,None)` | `terminal.py:247-257` |
| `search_async` | `(self, query: str, start: int = 0, direction: str = "next")` | `async` | `_invoke_method("search",{"query","start","direction"})`; Dart selects match, reports count via `on_selection_change` | queues `(search_async,(query,start,direction))` | `terminal.py:259-288` |
| `search` | same params | sync → `page.run_task(search_async, query, start, direction)` | same | queues `(search_async,(query,start,direction))` | `terminal.py:290-304` |
| `clear_selection_async` | `(self)` | `async` | `_invoke_method("clear_selection")` | queues `(clear_selection_async,None)` | `terminal.py:306-321` |
| `clear_selection` | `(self)` | sync wrapper | same | queues async variant | `terminal.py:323-333` |
| `select_all_async` | `(self)` | `async` | `_invoke_method("select_all")` (line-mode anchor span) | queues `(select_all_async,None)` | `terminal.py:335-350` |
| `select_all` | `(self)` | sync wrapper | same | queues async variant | `terminal.py:352-362` |
| `get_selection_async` | `(self) -> str \| None` | `async` **request/response** | `_invoke_method("get_selection")` → Dart returns `""` when nothing selected; Python maps falsy → `None` | **NEVER queued — returns `None` when not ready; callers retry after mount** (docstring `terminal.py:364-368` says so explicitly) | `terminal.py:364-375` |
| `paste_async` | `(self)` | `async` | `_invoke_method("paste")` — clipboard read happens **Dart-side**, fed to PTY via channel/`data` event | queues `(paste_async,None)` | `terminal.py:377-392` |
| `paste` | `(self)` | sync wrapper | same | queues async variant | `terminal.py:394-404` |

No `query()` method exists (the brief's "query/start/direction" = `search()` params). No `direction()` method. No spawn/pty/exit API anywhere — verified by full `dir()` + source read.

### 2.2 `MobileTerminal` — `class MobileTerminal(ft.Column)` (`mobile_terminal.py:22-444`)

High-level composite. Constructor signature verified live:
`__init__(self, show_extra_keys=True, show_search=False, show_settings=True, scrollback=10000, font_family="JetBrains Mono", font_size=11.0, cursor_blink=True, cursor_style="block", theme=None, read_only=False, auto_focus=True, extra_keys=None, expand=True)` (`mobile_terminal.py:25-40`).

Composition (`mobile_terminal.py:41-108`): `super().__init__(expand=expand, spacing=0)`; inner `Terminal(..., theme or BUILTIN_THEMES["JetBrains Dark"], expand=True)`; `TerminalSearchBar(on_search=self._terminal.search, on_close=lambda: self.toggle_search())` created **upfront, hidden by default** (comment `mobile_terminal.py:56-59`: lazy injection after first render never reaches the client — visibility flip diffs cleanly); routes `terminal.on_selection_change = self._internal_on_selection_change` (search-counter router + user-handler fan-out, `mobile_terminal.py:110-127`, branches on `"found" in data`); optional `ExtraKeysBar(on_send_payload=terminal.send_input, on_modifier_change=self._on_modifier_change, ...)` with zoom callbacks assigned post-construction (`_on_zoom_in/out/reset`, `mobile_terminal.py:90-92`) and settings-menu state seeded (`current_font_size/default_font_size/active_cursor/active_blink/active_search/active_theme`, `mobile_terminal.py:93-102`); `self.controls = [terminal, search_bar] + ([keys_bar] if present)`.

Every member (methods verified by `inspect.signature` dump):

| Member | Kind / signature | Semantics | Source |
|---|---|---|---|
| `show_search` | get/set `bool` property | Getter reads `search_bar.visible`; setter `thaw`s bar, sets `visible`, `control_update(bar)`, mirrors `keys_bar.active_search` + `update_settings_menu()` | `mobile_terminal.py:135-147` |
| `toggle_search()` | `()` | `show_search = not show_search` (+ redundant keys-bar mirror) | `mobile_terminal.py:149-154` |
| `set_theme(theme_name: str)` | `()` | `get_theme(name)`; no-op on unknown name; `thaw`+assign+`control_update`; mirrors `keys_bar.active_theme` | `mobile_terminal.py:156-165` |
| `set_cursor_style(style: str)` | `()` | `thaw` assign `cursor_style` + update; mirrors menu | `mobile_terminal.py:167-174` |
| `toggle_cursor_blink()` | `()` | flips `terminal.cursor_blink` under `thaw`; mirrors `active_blink` | `mobile_terminal.py:176-183` |
| `zoom_in(step=1.0)` | `()` | `font_size + step`, `thaw`+update, mirrors `current_font_size` | `mobile_terminal.py:185-194` |
| `zoom_out(step=1.0)` | `()` | `- step`, floored at `6.0px` (`max(6.0, …)`), no-op at/below 6.0 | `mobile_terminal.py:196-206` |
| `reset_zoom()` | `()` | restores `_default_font_size` captured at construction | `mobile_terminal.py:208-215` |
| `ctrl_active` / `alt_active` | get/set `bool` props | Getter `terminal.* or False`; setter `thaw`s terminal, `control_update`, then `keys_bar.ctrl/alt_active = val` + `refresh_buttons()` — **LATENT BUG: `ExtraKeysBar.refresh_buttons` does not exist** (verified: absent from `dir(ExtraKeysBar)`; only `reset_modifiers`/`update_settings_menu`). Setting `mt.ctrl_active` outside a tree raises the renderer `RuntimeError` first (verified live); inside a tree it would raise `AttributeError`. **M1 must-fix.** | `mobile_terminal.py:219-243` |
| `send_bytes(payload: bytes)` | forward | `terminal.send_bytes` | `mobile_terminal.py:245-246` |
| `font_size` / `cursor_blink` / `cursor_style` | read-only props | `terminal.font_size or default`, `bool(...)`, `... or "block"` | `mobile_terminal.py:248-261` |
| `theme_name` | read-only `str \| None` | exact-dict match across `BUILTIN_THEMES` (`all(cur.get(k)==v ...)`); `None` for custom themes | `mobile_terminal.py:263-270` |
| `send_input(payload)` / `write(data)` / `clear()` / `focus()` / `search(q,start,direction)` / `clear_selection()` / `select_all()` | forwards | straight to `Terminal` sync methods | `mobile_terminal.py:272-291` |
| `get_selection_async() -> str \| None` | `async` forward | `terminal.get_selection_async()` | `mobile_terminal.py:293-294` |
| `copy_selection_async() -> bool` | `async` | `get_selection_async()` → `None/""` returns `False`; else **one shared `ft.Clipboard()`** (`_clipboard` cached — 0.3.9 fix, `CHANGELOG.md:5`) `await clipboard.set(text)`; `terminal.clear_selection()`; `await terminal._trigger_event("copy", text)` (private API use). `False` on clipboard failure. | `mobile_terminal.py:296-320` |
| `copy_selection()` | sync → `page.run_task(copy_selection_async)` | no-op when `page` is `None`; `RuntimeError` → debug log | `mobile_terminal.py:322-329` |
| `paste_async()` / `paste()` | forward | `terminal.paste_async/paste` | `mobile_terminal.py:331-335` |
| `set_on_bytes(handler)` | forward | `terminal.set_on_bytes` | `mobile_terminal.py:337-338` |
| `on_data/on_resize/on_title_change/on_bell/on_mount/on_copy/on_shortcut` | get/set props | Getter returns `terminal.*`; setter `thaw`s terminal then assigns (prop-write on frozen control) | `mobile_terminal.py:340-444` (each pair) |
| `on_selection_change` | get/set with router preservation | Getter returns **user** handler (not terminal's); setter stores `_user_on_selection_change`, keeps `_internal_on_selection_change` installed so the search counter keeps working | `mobile_terminal.py:378-391` |
| `ready` | read-only `bool` | `terminal._dart_ready and terminal._channel_ready` — public readiness probe (new 0.3.9) | `mobile_terminal.py:404-407` |
| `pending_count` | read-only `int` | `len(terminal._pending_writes)` under lock | `mobile_terminal.py:409-413` |
| `clear_pending()` | `() -> None` | drops queued writes under lock | `mobile_terminal.py:415-418` |
| `flush()` | `() -> None` | re-runs `_mark_dart_ready()` (idempotent, safe anywhere) | `mobile_terminal.py:420-422` |
| `set_on_unmount(callback)` | `(callback) -> None` | stores `terminal._on_unmount_callback` (fired in `will_unmount`, exceptions logged not raised) | `mobile_terminal.py:424-426` |

### 2.3 `ExtraKeysBar` + `DEFAULT_EXTRA_KEYS` + `ModifierState`/`ModifierKey` (`extra_keys.py:1-397`)

`__all__ = ["DEFAULT_EXTRA_KEYS", "ExtraKeysBar"]` (`extra_keys.py:24`) — `ModifierState`/`ModifierKey` importable but not root-exported.

`@ft.observable @dataclass class ModifierState: ctrl: bool = False; alt: bool = False` (`extra_keys.py:32-38`). Reactive store: buttons subscribe via `use_state` so CTRL/ALT lights repaint without imperative `update()` (comment `extra_keys.py:27-31`).

`@ft.component def ModifierKey(state: ModifierState, label: str, on_toggle: Callable[[], None])` (`extra_keys.py:51-67`): subscribes `st, _ = ft.use_state(state)`, reads `getattr(st, label.lower())`, renders `ft.Button(BOLD 11px, h28, active/inactive style, on_click=toggle)`.

`DEFAULT_EXTRA_KEYS: list[tuple[str, bytes | None]]` (`extra_keys.py:70-84`) — all 13 entries, `None` payload = sticky modifier:

| # | Label | Bytes | Meaning |
|---|---|---|---|
| 1 | `ESC` | `\x1b` | escape |
| 2 | `TAB` | `\x09` (`\t`) | tab |
| 3 | `CTRL` | `None` | sticky CTRL toggle |
| 4 | `ALT` | `None` | sticky ALT toggle (prefixes `\x1b`) |
| 5 | `↑` | `\x1b[A` | cursor up (SS3/CSI) |
| 6 | `↓` | `\x1b[B` | cursor down |
| 7 | `←` | `\x1b[D` | cursor left |
| 8 | `→` | `\x1b[C` | cursor right |
| 9 | `-` | `-` | literal (phone keyboards bury it) |
| 10 | `/` | `/` | literal path separator |
| 11 | `\|` | `\|` | literal pipe |
| 12 | `~` | `~` | literal (home dir) |
| 13 | `^` | `^` | literal caret |

`class ExtraKeysBar(ft.Container)` (`extra_keys.py:87-397`). Constructor verified live: `(on_send_payload, on_modifier_change, show_settings=True, on_set_theme=None, on_set_cursor=None, on_toggle_blink=None, on_toggle_search=None, on_copy=None, on_paste=None, on_select_all=None, on_clear=None, keys=None)` (`extra_keys.py:90-104`). Container styling: `padding=Padding(4,1,4,1)`, `bgcolor="#181825"` (`extra_keys.py:178-182`); keys row `ft.Row(spacing=SPACE_XS=2, scroll=AUTO, expand=True)`; collapse toggle `IconButton(ARROW_DROP_UP/DOWN, 20)`; collapsed view is a full-width clickable `Container("Click anywhere to show keys", ink=True)`.

Modifier application `_send_payload` (`extra_keys.py:368-381`): CTRL + single byte `a-z` → `code-96`, `A-Z` → `code-64` (consumes CTRL, notifies); ALT → prefix `\x1b` (consumes ALT, notifies); then `on_send_payload(payload)`. Dart-side `onOutput` applies the identical transform for hardware keys (`flet_terminal.dart:120-137`) — both paths converge. `reset_modifiers()` (`extra_keys.py:362-366`) clears both + notifies (wired to Dart `modifier_reset` via `mobile_terminal.py:87-89`). Settings menu (`extra_keys.py:203-313`): Clipboard header + Copy/Paste/SelectAll/Clear; Theme Presets (exactly the 4 `BUILTIN_THEMES` names with `checked=`); Font Size/Zoom (Zoom In/Out/Reset with live `default_font_size`); Toggle Options (Cursor Blink, Search Bar with `checked=`). `update_settings_menu()` (`extra_keys.py:315-320`) rebuilds items under `thaw`. State fields and defaults: `active_theme="JetBrains Dark"`, `active_cursor="block"`, `active_blink=True`, `active_search=True`, `current/default_font_size=11.0`, `_on_zoom_in/out/reset=None` (assigned by `MobileTerminal`), `_collapsed=False`.

### 2.4 `TerminalSearchBar` — `class TerminalSearchBar(ft.Container)` (`search_bar.py:18-158`)

Constructor verified: `(on_search: Callable[[str,int,str], None], on_close: Callable[[],None] | None = None)` (`search_bar.py:30-34`). Layout: `Row[TextField(hint"Search buffer…",h28,text11,expand,padding h8,bg #1E1E2E,border OutlineInputBorder #45475A, on_change=live, on_submit=next), counter Text("",10,#A6ADC8,hidden), prev/next/close IconButtons(14px)]`, container padding `(2,1,2,1)`.
`do_search(direction="next", reset=False)` (`search_bar.py:119-133`): empty query → no-op; fresh query/reset → `start=0`; `prev` → `start=max(last_index,0)`; `next` → `last_index+1`. `report_result(found,count,index)` (`search_bar.py:135-145`): sets `count/last_index`, counter text `"{count} found"` or `"No matches"`, visible=True, all under `thaw`+`control_update`. Live path `_handle_text_change` (`search_bar.py:98-117`): 350 ms debounce via `page.run_task(_delayed_search)` with generation counter; empty query returns without clearing (counter keeps last state — quirk to know). `_handle_close` (`search_bar.py:147-158`): cancels debounce, clears field/counter/state, fires `on_close`.

### 2.5 `BUILTIN_THEMES` + `get_theme` (`themes.py:1-74`)

`__all__ = ["BUILTIN_THEMES","get_theme"]` (`themes.py:7`). Four presets, each exactly 12 keys (`background,foreground,cursor,selection,black,red,green,yellow,blue,magenta,cyan,white`; `themes.py:9-66`):

| Key | Dracula | JetBrains Dark (default) | Matrix Green | Colab Light |
|---|---|---|---|---|
| background | `#1E1F29` | `#1E1E2E` | `#0D1117` | `#FFFFFF` |
| foreground | `#F8F8F2` | `#CDD6F4` | `#00FF66` | `#1F2430` |
| cursor | `#FF79C6` | `#F5E0DC` | `#00FF66` | `#F97316` |
| selection | `#44475A` | `#585B70` | `#163320` | `#D6E4F0` |
| black | `#21222C` | `#45475A` | `#0D1117` | `#1F2430` |
| red | `#FF5555` | `#F38BA8` | `#FF5555` | `#D93025` |
| green | `#50FA7B` | `#A6E3A1` | `#00FF66` | `#188038` |
| yellow | `#F1FA8C` | `#F9E2AF` | `#FFFF00` | `#B26A00` |
| blue | `#BD93F9` | `#89B4FA` | `#0088FF` | `#1A73E8` |
| magenta | `#FF79C6` | `#F5C2E7` | `#FF00FF` | `#C2185B` |
| cyan | `#8BE9FD` | `#94E2D5` | `#00FFFF` | `#00838F` |
| white | `#F8F8F2` | `#BAC2DE` | `#FFFFFF` | `#E8EAED` |

`get_theme(theme_name: str | None) -> dict | None` (`themes.py:69-73`): falsy → `None`; else `BUILTIN_THEMES.get(name)` (unknown name → `None`, so `MobileTerminal.set_theme` silently no-ops). Dart accepts extra keys the Python themes never send: `brightBlack…brightWhite`, `searchHitBackground(Current)`, `searchHitForeground` fall back to `TerminalThemes.defaultTheme` (`flet_terminal.dart:413-424`); `selection`/`searchHit*` 6-digit hex gets `0x66` alpha OR'd (`flet_terminal.dart:387-389`).

### 2.6 `ShortcutEvent` (`terminal.py:16-24`)

```python
@dataclass
class ShortcutEvent(ft.Event["Terminal"]):  # terminal.py:17
    shortcut: str = ""  # terminal.py:23, e.g. "new_terminal"
```
Introspected inherited fields: `name, control, shortcut, data`. Full machine-name set is Dart-owned (17 values, §3): `new_terminal, close_terminal, toggle_search, clear, copy, paste, zoom_in, zoom_out, zoom_reset, switch_terminal_1…9, prev_terminal, next_terminal, help`.

### 2.7 Exported constants (`tokens.py:1-32`)

`__all__` 10 names (`tokens.py:5-16`), values verified live: `SPACE_XS=2`, `SPACE_SM=4`, `SPACE_MD=8`, `BTN_HEIGHT=28`, `BTN_FONT_SIZE=11`, `COLOR_ACTIVE_BG="#8BE9FD"`, `COLOR_ACTIVE_FG="#1E1E1E"`, `COLOR_INACTIVE_BG="#313244"`, `COLOR_INACTIVE_FG="#CDD6F4"`, `COLOR_BORDER="#45475A"`. Only a subset is consumed (`extra_keys.py:12-20` imports 6); `SPACE_SM/SPACE_MD/COLOR_BORDER` are currently unused reserves.

### 2.8 `frozen_support` — `thaw` + `control_update` (`frozen_support.py:1-106`)

`__all__ = ["control_update","thaw"]` (`frozen_support.py:12`). `thaw(control)` contextmanager (`frozen_support.py:15-37`): deletes `_frozen` if present, yields, restores — the same dance flet performs internally (`_before_update_safe`); `None`-safe. `control_update(control)` (`frozen_support.py:68-105`): raises `RuntimeError` if still frozen (caller must wrap assignment AND call together); resolves the page via `_patch_page` — first `flet.context.page` (session context var), then `control.page` parent-chain walk (`frozen_support.py:40-65`, needed because the 1.0 reconciler drops `_parent` weakrefs on re-render and `Control.update()` then raises "must be added to the page first"); emits via `page.session.patch_control(control)` keyed on the stable logical id (works while hidden/detached); no-page → warning log, change stays local until next render; patch failure → exception log. Every `MobileTerminal`/`ExtraKeysBar`/`TerminalSearchBar` mutation uses `thaw`+`control_update` — consumers never wrap.

---

## 3. Complete Dart/Flutter surface

Files: `lib/flet_terminal.dart` (barrel, re-exports `Extension`), `lib/src/extension.dart` (16 L: `Extension extends FletExtension`, `createWidget` matches `control.type == "FletTerminal"` → `FletTerminalControl`), `lib/src/flet_terminal.dart` (594 L, the whole widget).

**Widget behaviors** (`_FletTerminalControlState`): owns `qt.Terminal(maxLines: scrollback)`, `TerminalController`, `FocusNode`, `ScrollController`, `DataChannel?`, blink `Timer?`, selection-debounce `Timer?`, `_pinnedToBottom=true`. `initState` (`:98-173`): registers `_handleMethodCall`, fires `mount`, syncs blink, wires scroll listener, selection listener, `onOutput` (sticky-modifier transform + channel-or-`data`), `onTitleChange`, `onBell`, `onResize`. `didChangeDependencies` (`:176-204`): lazily opens ONE `DataChannel`, streams bytes → `_terminal.write(utf8.decode(bytes, allowMalformed:true))` with pinned-only auto-follow, fires `data_channel_open{channel_name:"pty",channel_id}`. `build` (`:443-544`): parses theme/style/cursor/blink/autofocus/readOnly; `MediaQuery` mobile check (`width<600` → `deleteDetection=true`, `keyboardType=text`); `TerminalView` with `onKeyEvent=_handleShortcutKey`, `onSecondaryTapUp` copy-or-paste; `LayoutControl→RepaintBoundary→LayoutBuilder` with unbounded-constraint guards (fallback 800×500, keyboard `viewInsets.bottom` padding, pinned-only snap). `dispose` (`:577-592`): cancels timers/subscription, closes channel, removes listeners, disposes nodes.

**Method-call handlers** (`_handleMethodCall`, `:236-373`): `write{data}` (guarded `mounted`), `clear` (clearScrollback+clear), `focus` (requestFocus), `clear_selection`, `get_selection` ("" when none), `paste` (Dart `Clipboard.getData` → channel or `data` event), `select_all` (line-mode anchor span `(0,height-viewHeight)→(viewWidth,height-1)`), `search{query,start,direction}` (case-insensitive full count, next-at-or-after+wrap / prev-strictly-before+wrap, newline-split offset→grid, line-mode select, `selection_change{query,found,count,index}`). Unknown names → `return null` (silent no-op).

**Events emitted:** `mount("")`, `data_channel_open{channel_name:"pty",channel_id}`, `data(str)`, `resize{cols,rows}`, `title_change(str)`, `bell("")`, `selection_change` (two shapes, §2.1), `copy(str)`, `shortcut{shortcut}`, `modifier_reset("")`. `ctrl/alt_active` prop sync via `updateProperties(..., dart:true, python:true, notify:true)`.

**DataChannel framing ("pty"):** label is transport naming only — the channel carries raw terminal I/O bytes (`utf8.encode` Python→Dart, `utf8.decode(allowMalformed:true)` Dart→screen). No PTY, no process, no `dart:io`/`Process` import anywhere (verified: imports are `dart:async,convert,typed_data` + flet/material/services + xterm).

**Cursor blink:** `Timer.periodic(530ms)` toggling `setCursorVisibleMode` + `notifyListeners()` (upstream xterm 4.0.0 has no blink; comment `:552-558`).

**Shortcuts** (consumed pre-PTY via `onKeyEvent`, `KeyDownEvent` only, active only with handler): `Ctrl/Cmd+Shift+T/W/F/L/C/V/=/-/0/1-9` → `new_terminal/close_terminal/toggle_search/clear/copy/paste/zoom_in/zoom_out/zoom_reset/switch_terminal_1-9`; `Ctrl/Cmd+PageUp/PageDown` → `prev/next_terminal`; bare `F1` → `help`.

**Search:** byte-exact algorithm above; match surfaced as a selection (xterm has no find engine — highlight = `selection` theme color).

**Mobile specifics:** `isMobile = width<600`; `deleteDetection=isMobile`; `keyboardType=text`; bottom-inset padding only when it doesn't swallow the view; sticky-bottom `_pinnedToBottom` (40px epsilon) stops yanking scrolled-up users; long-press/drag selection forwarded (debounced 150 ms); secondary-tap = copy-if-selection-else-paste.

**Pubspec** (`pubspec.yaml`, all 20 lines): `name: flet_terminal`, `description: Flet native Terminal control using xterm.dart`, `version: 0.3.9`, `publish_to: none`, `sdk '>=3.3.0 <4.0.0'`, `flutter ">=3.10.0"`, deps `flet: ^1.0.0` (must stay — tracks the client baked by `flet build`), `flutter/sdk`, `xterm: ^4.0.0`; dev `flutter_test`, `flutter_lints: ^3.0.0`. Exact resolved xterm version in our build is **unverified** (no lockfile ships in the wheel).

---

## 4. Integration contract

Companion `dep-flet-terminal.md` holds the M1 blueprint; here is the exact byte-flow map.

**App → terminal (output):** `write()/write_async()/send_bytes(bytes)` → DataChannel fast path when `_dart_ready and _channel_ready` (str encoded utf-8 `errors="ignore"`), else `_invoke_method("write")` fallback (`write` only) or `_pending_writes` queue. Dart appends to the xterm buffer + pinned auto-scroll.

**Terminal → app (input):** hardware keys → `onOutput` (CTRL a-z→1-26 / ALT ESC-prefix, modifier reset event) → live channel `send(bytes)` or `data` event fallback → host `set_on_bytes(handler)` (e.g. example `pty.write`, `app.py:75`). Virtual keys → `ExtraKeysBar._send_payload` → `terminal.send_input` → **direct `_on_bytes_handler` call, never touches Dart**. Clipboard paste (method or secondary-tap) → Dart `Clipboard.getData` → channel or `data` event.

**Mount/replay:** `did_mount` + `before_event` + `data_channel_open` all converge on `_mark_dart_ready()` which drains `_pending_writes` in order (sync fns called directly, async via `page.run_task`). `MobileTerminal.ready/pending_count/clear_pending/flush` expose this (0.3.9). `will_unmount` clears the queue and fires `set_on_unmount` callbacks. Scrollback replay across remounts is the host's job: re-`write()` the buffer on `on_mount` (CollabShell pattern per companion doc).

**Renderer-context requirement (verified reproduction 2026-10-16):** `MobileTerminal()` outside an `@ft.component` render tree raises `RuntimeError: No current renderer is set. Call via Renderer.render(...) or Renderer.with_context(...)` (raised at `flet/components/utils.py:31`; its `@ft.component` children `ModifierKey` instantiate eagerly in `__init__`). Reproduced live: plain `Terminal()` constructs fine; `MobileTerminal()` raises; inside `with Renderer().with_context():` it constructs fine. Same failure hit on-device in the M0 spike (placeholder showed this error). Workaround today: construct inside a component tree (example `app.py:97-102` `use_state` factory) or the `Renderer().with_context()` throwaway (wheel README §"Imperative Construction"). M1 must fix (defer/guard composition) or document + contract-test per companion §36-39. **Our M3 AppShell is component-based, so it consumes `MobileTerminal` exactly as the example does.**

**Known gaps (verified absences):** no spawn/pty/exit API (Dart imports prove it; channel "pty" is a label); no `set_size` method — resize is an **event only**, the host performs `TIOCSWINSZ` itself (example `pty_service.py:107-119`); `get_selection_async` is the sole non-queueable method; `font_family` Android fallback **unverified**; `scrollback` post-mount changes have no Dart update path (**unverified** effect).

---

## 5. Fullest-utilization — every currently-unused capability and how M1+ uses it

Our app has no terminal screen yet, so *everything* is currently unused. Below is the capability → milestone mapping so M1+ leaves nothing on the table (owner principle: the only way we beat Termux is by utilizing every dependency to the fullest).

| Capability (today-unused) | M1 package work | App use (milestone) |
|---|---|---|
| `DEFAULT_EXTRA_KEYS` + custom `keys=` layout | keep + contract-test the 13 byte sequences | M4: per-distro layouts (add `Ctrl`, `Alt` combos, `|`/`~` already present are apt/pkg essentials); M4 also adds long-press hints |
| Sticky CTRL/ALT (`ctrl_active/alt_active`, `ModifierState`, `reset_modifiers`) | fix `refresh_buttons` `AttributeError` (§2.2); expose modifier state events | M4: the core phone-keyboard story — Termux's extra-keys row is the bar to beat; ours is reactive + collapsible |
| 4 `BUILTIN_THEMES` + `set_theme`/`get_theme`/`theme_name` | keep names stable (CollabShell pins them); add contrast audit | M3/M4: per-distro theme (e.g. Matrix for Alpine, Dracula default), Colab Light follows app `ThemeMode`; settings persist |
| `TerminalSearchBar` + `search/query/start/direction` + `report_result` counter | keep; add empty-query-clears-counter quirk fix | M4: man-page/log search; bargaining chip Termux lacks in-proot search UI |
| `get_selection_async` + `copy_selection(_async)` + `on_copy` + `select_all/clear_selection` | keep; harden clipboard-permission path | M4: structured-mode output capture (command→outputs), copy error output to bug reports; M6: license-text copy |
| `on_shortcut` (17 combos) + `ShortcutEvent` | keep gate (no handler = no swallow); document | M4: multi-session tabs (`new/close/switch/prev/next_terminal`), `toggle_search`, zoom — Termux has no host-shortcut bus |
| `on_title_change` (OSC 0/2) | keep | M4: show guest `user@host:cwd` in AppBar; session-switcher labels |
| `on_bell` | keep | M4: `apt install` completion ping → snackbar (respects silent mode; default OFF per O-5) |
| `on_resize{cols,rows}` | keep payload shape frozen by contract test | M0→M4: `TIOCSWINSZ` forward to proot PTY (example `pty_service.resize` is the template; our `ProotSession.set_size`) |
| `zoom_in/out/reset`, `show_search`, cursor controls | keep | M4: accessibility (font floor 6.0 already), pager-friendly `read_only` mode for structured output |
| `read_only` + `auto_focus` | keep | M4: read-only log view; focus management with stdin-hook dialog (CollabShell `stdin_hook.py` pattern, roadmap §1c) |
| `ready/pending_count/clear_pending/flush/set_on_unmount/on_mount` | new 0.3.9 — add contract tests | M4: reconnect/scrollback-replay, tab-switch session keep-alive, no ANR on rotation |
| `thaw/control_update` | keep; document as the sanctioned pattern | M3: all imperative session updates inside component AppShell |
| `tokens.py` reserves (`SPACE_SM/MD`, `COLOR_BORDER`) | keep for M1 UI polish | M1: settings-menu spacing/borders in the house-standard README demo |
| Bright/search-hit theme keys (Dart-only today) | expose in a 5th theme or docs | M4: visible search highlight tuning (`selection` color doubles as match highlight) |

---

## 6. Verification

**Refs:** installed wheel + `RECORD` (file list), `METADATA` (11 lines), `WHEEL` (4 lines), `pyproject.toml` (33 lines), `pubspec.yaml` (20 lines), `CHANGELOG.md` (0.3.9/0.3.8/0.2.x entries), example `app.py` (component-tree construction `:97-102`, bundle wiring `:47-77`, `pty.resize :35-44`, POSIX `openpty`+`Popen`+`TIOCSWINSZ` `:121-152`), companion `docs/reference/dep-flet-terminal.md`, `docs/roadmap.md` M1/M4, `docs/decisions.md` D-010.

**Method:** `Read` of every shipped `.py`/`.dart`/config file + two live `python.exe -c` introspection runs (`inspect.signature` for all 8 root exports, `ModifierKey`, `ExtraKeysBar`, `MobileTerminal` mutators, `TerminalSearchBar`, `get_theme`, `thaw/control_update`, token values) + one live renderer-context reproduction (three constructions + setter).

**Marking unknowns (unverified):** exact resolved `xterm` version in a built client (range `^4.0.0` only); DataChannel throughput/"thousands of lines" README claims (no benchmark in repo); Android `JetBrains Mono` fallback font rendering; Android 10+ clipboard permission behavior for `paste_async`/secondary-tap; effect of post-mount `scrollback` changes; `on_size_change`/`animate_*` inherited props interaction with the terminal view (stock flet, not exercised); Windows `winpty` path in the example (no Windows run here).

**Confirmed defects for M1 (both verified, not suspected):** (1) `MobileTerminal` outside a component tree raises `RuntimeError` (reproduced live + on-device); (2) `MobileTerminal.ctrl_active/alt_active` setters call nonexistent `ExtraKeysBar.refresh_buttons` (`mobile_terminal.py:230,243` vs `dir(ExtraKeysBar)` — no such attr), a latent `AttributeError` once (1) is fixed.

---

## 7. How this dependency makes our app significantly better than Termux's proot-distro

Termux ships a capable terminal emulator bolted onto a package-manager UX from 2015. Our edge is not the container engine (proot is proot) — it is that **every terminal-UI capability below is a first-class, tested package API** our M4 session screen gets for free, while Termux users get none of it:

1. **Virtual extra-keys bar with sticky modifiers** (`DEFAULT_EXTRA_KEYS`, `ModifierState`, §2.3): ESC/TAB/arrows/`-|/~^` plus reactive CTRL/ALT toggles and a collapsible row — Termux's extra-keys row is static configuration; ours is emprative, per-distro, and collapses to a one-line affordance.
2. **Four built-in themes + live switching** (§2.5): per-distro identity and a real light mode (Colab Light) — Termux offers color schemes as manual imports.
3. **In-scrollback search with match counter and stepping** (§2.4 + `search` method): `man`/`apt` log search with `N found` feedback — Termux has no integrated buffer search UI.
4. **Programmatic selection/clipboard** (`select_all`, `get_selection_async`, `copy_selection`, `paste`, `on_copy`): one-tap copy of command output for bug reports / structured-mode capture — Termux copy is long-press-only.
5. **Title + bell events** (`on_title_change`, `on_bell`): live `user@host:cwd` AppBar titles and build-finished pings — Termux exposes neither to the app layer.
6. **Host shortcut bus** (`on_shortcut`, 17 combos): multi-session tab management (`new/close/switch/prev/next`) and zoom/search without touching the PTY — Termux has no shortcut API for its own UI.
7. **Zoom + cursor + search-bar controls as API** (`zoom_in/out/reset`, `toggle_search`, `set_cursor_style`, blink): accessibility story (6px floor, real blink) Termux can't match without fork changes.
8. **Declarative-safe mutations** (`thaw`/`control_update`, §2.8): session UI survives rotations, tab switches, and backgrounding via `ready/flush/on_mount` replay — Termux sessions die with the Activity; ours are designed to persist across screen switches (roadmap M4).
9. **View-only purity as an asset**: the package never spawns — *our* `ProotSession` owns the proot child (Python-side PTY, O-3 closed), so the UI stays a pure renderer. Termux entangles emulation and process management; we test each side separately (`pytest` offline + CI APK on-device).
