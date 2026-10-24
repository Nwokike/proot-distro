# 02 · Terminal — design-parity audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** Reference (CollabShell): `src/app_shell.py:1-579` (esp. 121-170, 375-437), `src/screens/session/__init__.py:1-441`, `src/screens/session/terminal_panel.py:1-981`, `src/screens/session/fab_menu.py:1-216`, `src/screens/session/layout.py:1-154`, `src/screens/session_selector.py:1-94`, `src/components/session_card.py:1-85`, `src/core/tokens.py:1-88`, `src/core/styles.py:1-233` · Ours: `src/screens/terminal_view.py:1-326`, `src/app_shell.py:1-78`, `src/components/banner_ad.py:1-93`, `src/screens/views.py:73-381`, `src/core/tokens.py:1-65`, `src/services/session_manager.py:1-99`, `src/core/state.py:1-55` · **Date:** 2026-10-23

Ground truth: `.venv/lib/python3.14/site-packages/` — flet **1.0.4** (`flet-1.0.4.dist-info/METADATA:4`), `flet-terminal` **0.4.0** (`flet_terminal-0.4.0.dist-info/METADATA:3`), Python **3.14.9** (Linux x86_64).

---

## What it does / how the app uses it

Both applications use `flet_terminal.MobileTerminal` backed by an in-process observable session model (`SessionEntry` / `TerminalEntry`) that decouples running terminal processes from widget tree destruction. Output is captured into ring buffers (`deque(maxlen=2000)`) and replayed upon widget remount (`on_mount`).

However, the hosting architecture, screen chrome, session navigation, and chrome hierarchy diverge sharply:
1. **Shell and Navigation Isolation:** CollabShell treats an active session as a full-screen isolated subview (`active_subview == "session"`), removing the bottom `NavigationBar` entirely via `page.views[0].navigation_bar = None` (`src/app_shell.py:132-133`). Ours embeds `TerminalView` inside the primary `AppShell` column (`src/app_shell.py:53-77`), leaving `NavigationBar` pinned beneath the terminal even in full-screen mode, and creating a routing trap where clicking other tabs does not leave the active session.
2. **Multi-session Tabs:** CollabShell renders a dedicated tab bar (`switcher_box`) directly above the terminal canvas (`src/screens/session/terminal_panel.py:838-894`) allowing users to switch between or open new concurrent terminals with one tap. Ours supports up to 4 concurrent shells in `SessionManager` (`MAX_CONCURRENT_SESSIONS = 4`, `src/services/session_manager.py:20`), but exposes **zero** in-screen tabs; users must back out to `SessionSelectorView` to switch shells.
3. **Screen Chrome & Actions:** CollabShell uses a flat, full-width header bar (`src/screens/session/__init__.py:360-428`) accompanied by a page-level contextual FAB menu (`src/screens/session/fab_menu.py:65-215`) exposing copy, paste, zoom in/out, cursor blink, search toggle, and theme presets. Ours wraps the header in a floating rounded glass card (`src/screens/terminal_view.py:134-167`), has no FAB or action menu, and relies on an ad-hoc bottom row of text buttons (`quick_strip`).
4. **Ad Placement (D-017.7):** CollabShell keeps its terminal screen completely ad-free. Ours adheres to decision D-017.7 (`docs/decisions.md:116-121`), placing `pooled_banner_ad("terminal-1")` at the very top of the screen above the header and far away from extra keys, though an inline apt upgrade note insertion alters the header stacking order.

---

## Findings

### F1 · P1 · Bottom NavigationBar traps user in terminal and breaks tab switching

- **Where:** ours `src/app_shell.py:53-77`; CollabShell `src/app_shell.py:121-135, 427-437`.
- **What:** In CollabShell, entering a session subview sets `state.active_subview = "session"`, which triggers `_sync_navigation_bar()` to set `page.views[0].navigation_bar = None` (`src/app_shell.py:132-133`). The bottom nav is removed while a session is active, freeing vertical space for the shell and keyboard. In ours, `AppShell` always renders `ft.NavigationBar` below `body` (`src/app_shell.py:66-73`). However, in `src/app_shell.py:53-62`, `entry = _session_entry(controller)` is checked *before* `active_tab`. If a session is active (`state.active_session` is set), tapping "Distros" (tab 0) or "Settings" (tab 2) on the bottom bar updates `active_tab`, but `if entry is not None:` evaluates first and forces `body = TerminalView(entry)`. The user is visually trapped in the terminal while the bottom nav destination changes underneath them, and they cannot switch tabs without first discovering and tapping the small Back icon button inside `TerminalView`.
- **Evidence:** ours `src/app_shell.py:53-62`:
  ```python
  entry = _session_entry(controller)
  if entry is not None:
      body = TerminalView(entry)
  elif active_tab == TAB_DISTRO:
      body = DistroView()
  elif active_tab == TAB_TERMINAL:
      body = SessionSelectorView()
  else:
      body = SettingsView()
  ```
  CollabShell `src/app_shell.py:125-134`:
  ```python
  if (
      not state.onboarding_completed
      or state.active_subview is not None
      or state.loading_operation is not None
  ):
      if page.views[0].navigation_bar is not None:
          page.views[0].navigation_bar = None
      return
  ```
- **Fix / opportunity:** Isolate the session view at the shell level. When `state.active_session` is set, hide `NavigationBar` (or omit it from the root column), matching CollabShell. If tabs are intended to remain reachable, `active_tab` must take precedence over `entry`, or navigating to another tab must cleanly leave or park the active session view.
- **Risk if ignored:** Severe user confusion; bottom navigation appears completely unresponsive when a terminal is running.

---

### F2 · P1 · Full-screen mode does not hide the bottom NavigationBar

- **Where:** ours `src/screens/terminal_view.py:178-195` and `src/app_shell.py:63-77`.
- **What:** Tapping the fullscreen button (`_toggle_fullscreen`, `src/screens/terminal_view.py:130-133`) sets `state.terminal_fullscreen = True` and removes `header`, `pooled_banner_ad`, and `quick_strip` from `TerminalView`. However, `TerminalView` is rendered inside `src/app_shell.py:65` where `ft.NavigationBar` is an unconditional sibling control (`src/app_shell.py:66-73`). As a result, "full screen" mode collapses the top header and banner, but leaves the ~80px bottom navigation bar visible on screen, defeating true full-screen terminal usage on mobile.
- **Evidence:** ours `src/screens/terminal_view.py:178-195`:
  ```python
  controls: list[ft.Control] = []
  if not fullscreen:
      controls.append(pooled_banner_ad("terminal-1", page))
      controls.append(header)
  else:
      controls.append(...) # FULLSCREEN_EXIT button
  controls.append(mt)
  ```
  While `src/app_shell.py:63-77` unconditionally returns:
  ```python
  return ft.Column(
      controls=[
          ft.Container(content=body, expand=True, bgcolor=theme.bg()),
          ft.NavigationBar(...),
      ],
      spacing=0, expand=True,
  )
  ```
- **Fix / opportunity:** Read `state.terminal_fullscreen` (or session active state) in `src/app_shell.py:63-77` to hide or omit `ft.NavigationBar` when full screen is active.
- **Risk if ignored:** Wasted screen height (~80px) on mobile; "Full screen" label is deceptive.

---

### F3 · P1 · Dead keyboard-inset handling / nonexistent `bottom_inset` event payload

- **Where:** ours `src/screens/terminal_view.py:84-95, 226-228`; `.venv/lib/python3.14/site-packages/flutter/flet_terminal/lib/src/flet_terminal.dart:165-172`.
- **What:** Ours attempts to handle virtual keyboard insets by extracting `bottom = int(data.get("bottom_inset", 0) or 0)` in `_on_resize` (`src/screens/terminal_view.py:88`) and applying `padding=ft.Padding.only(bottom=inset)` to the body container (`src/screens/terminal_view.py:227`). However, `flet-terminal`'s Dart runtime *never* transmits `"bottom_inset"`: `_terminal.onResize` only encodes `{"cols": width, "rows": height}` (`flet_terminal.dart:168-171`). Because `data.get("bottom_inset", 0)` is always `0`, `inset` is permanently `0`, the padding logic is dead code, and software keyboard insets are never compensated by this mechanism. (A mock test in `tests/test_terminal_wiring.py:55-61` masked this bug by feeding an artificial dictionary with `"bottom_inset": 42`).
- **Evidence:** ours `src/screens/terminal_view.py:88`:
  ```python
  bottom = int(data.get("bottom_inset", 0) or 0)
  ```
  Installed Dart source `.venv/lib/python3.14/site-packages/flutter/flet_terminal/lib/src/flet_terminal.dart:165-172`:
  ```dart
  _terminal.onResize = (width, height, pixelWidth, pixelHeight) {
    widget.control.triggerEvent(
        "resize",
        jsonEncode({
          "cols": width,
          "rows": height,
        }));
  };
  ```
- **Fix / opportunity:** Remove the phantom `bottom_inset` read and container re-padding. Keyboard handling in Flutter is managed at the window/view level (`SafeArea` and page view insets), matching CollabShell `src/screens/session/terminal_panel.py:294-305` which only handles rows and cols.
- **Risk if ignored:** Dead code and false confidence in keyboard inset handling; tests test a non-existent contract.

---

### F4 · P1 · Quick command buttons send raw text without newline execution

- **Where:** ours `src/screens/terminal_view.py:23-30, 124-128`.
- **What:** `_QUICK_COMMANDS` defines `("ls", "ls")`, `("apt update", "apt update")`, `(" top", "top")`, `("clear", "clear")`, `("exit", "exit")`. The handler `_quick` sends `_write(entry, command.encode("utf-8"))` directly to PTY stdin. Because there is no carriage return or newline (`\r` or `\n`), tapping "ls", "clear", or "exit" merely pastes characters into the shell prompt without executing them. The user must manually tap Enter on the virtual extra keys bar. In contrast, CollabShell's actions send control characters (e.g. Ctrl+L `b"\x0c"` for clear at `terminal_panel.py:626`) or CRLF-terminated strings (e.g. `"cd /content\r\n"` at `terminal_panel.py:196`).
- **Evidence:** ours `src/screens/terminal_view.py:124-128`:
  ```python
  def _quick(label: str, command: str) -> ft.Control:
      def _send(_e) -> None:
          _write(entry, command.encode("utf-8"))
      return ft.TextButton(label, on_click=_send)
  ```
- **Fix / opportunity:** Append `\n` to complete executable commands (e.g., `ls\n`, `top\n`, `clear\n`, `exit\n`), or replace the quick strip with proper action buttons/shortcuts sending terminal escape codes (`\x0c` for clear).
- **Risk if ignored:** Broken user expectation; tapping "ls" or "clear" does not perform the action until Enter is tapped.

---

### F5 · P2 · Missing session tabs inside Terminal screen (4 concurrent shells hidden)

- **Where:** CollabShell `src/screens/session/terminal_panel.py:838-894, 952-967`; ours `src/screens/terminal_view.py:60-230` and `src/services/session_manager.py:20`.
- **What:** In CollabShell, multiple terminal instances run concurrently inside the session screen. The `switcher_box` renders tab buttons (`Term 1`, `Term 2`, `+`) with an active indicator, close icon, and an Add button to spin up another shell without leaving the terminal view (`terminal_panel.py:838-894`). In our app, `SessionManager` supports up to 4 concurrent shells (`MAX_CONCURRENT_SESSIONS = 4` in `session_manager.py:20`), but `TerminalView` has **zero** tab buttons. Switching between concurrent shells requires leaving the terminal screen back to `SessionSelectorView` and tapping "Resume" on another container.
- **Evidence:** CollabShell `terminal_panel.py:838-894`:
  ```python
  tab_buttons = []
  for t in ps.terminals:
      is_active = t.id == ps.active_id
      tab_buttons.append(ft.Container(content=ft.Row([ft.Icon(...), ft.Text(f"Term {t.id}"), ft.GestureDetector(...) ...])))
  tab_buttons.append(ft.IconButton(icon=ft.Icons.ADD_ROUNDED, ...))
  ```
  Ours `src/screens/terminal_view.py` renders only the single passed `entry`, with no tab bar.
- **Fix / opportunity:** Add a tab strip above or inside the terminal header in `TerminalView` displaying running entries from `SessionManager.entries`, allowing 1-tap switching between open shells and a `+` button to open another container.
- **Risk if ignored:** Multitasking across containers is awkward and hidden behind multiple navigation transitions.

---

### F6 · P2 · Search bar permanently closed once dismissed (no toggle action/button)

- **Where:** CollabShell `src/screens/session/terminal_panel.py:616-621`, `src/screens/session/fab_menu.py:125-130`; ours `src/screens/terminal_view.py:71`.
- **What:** CollabShell initializes `MobileTerminal` with `show_search=False` (`terminal_panel.py:340`) and provides a `toggle_search` action via the session FAB menu (`fab_menu.py:125-130`) and keyboard shortcut (`terminal_panel.py:559`). In ours, `show_search=True` is hardcoded at mount (`terminal_view.py:71`), so the search bar is forced open on initial render. If the user taps the "X" button on the search bar to dismiss it, there is no action, button, or shortcut anywhere in the UI to re-open it.
- **Evidence:** ours `src/screens/terminal_view.py:71`:
  ```python
  entry.mt = MobileTerminal(
      show_extra_keys=True,
      show_search=True,
      ...
  )
  ```
  No other reference to `toggle_search` or search controls exists in `src/screens/terminal_view.py`.
- **Fix / opportunity:** Set `show_search=False` by default (saving vertical space on mobile), and add a Search icon button (`ft.Icons.SEARCH_ROUNDED`) in the terminal header or actions cluster calling `mt.toggle_search()`.
- **Risk if ignored:** Inability to search terminal history after initial dismissal.

---

### F7 · P2 · Header structure and token styling drift (elevated card vs full-width bar)

- **Where:** CollabShell `src/screens/session/__init__.py:360-428`; ours `src/screens/terminal_view.py:134-167`.
- **What:** CollabShell's session header is a full-width flat container (`bgcolor=ft.Colors.SURFACE`, `padding=Padding(tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_SM)` = 6, 6, 14, 6) containing a rounded back button (`ARROW_BACK_ROUNDED`, size 20 `ICON_MD`), `status_dot` indicator, bold title (`FONT_LG`=14), and a badge rail. Ours wraps the header in `card(...)` (`glass_card`, border-radius 16, glass border, padding 10) floating as a detached card inside a Column with 4px margin. Furthermore, ours uses off-scale literal font and icon sizes: `ARROW_BACK` size 18 (vs `ICON_MD`=20), `size=13` for title (vs `FONT_LG`=14), `size=10` for status text, `CLOSE` size 18, and `FULLSCREEN` size 18.
- **Evidence:** CollabShell `session/__init__.py:424-427`:
  ```python
  padding=ft.Padding(
      tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_SM
  ),
  bgcolor=ft.Colors.SURFACE,
  ```
  Ours `src/screens/terminal_view.py:134-167`:
  ```python
  header = card(
      ft.Row(
          controls=[
              ft.IconButton(icon=ft.Icons.ARROW_BACK, icon_size=18, ...),
              ft.Icon(ft.Icons.TERMINAL, size=16, color=theme.primary()),
              ft.Text(entry.title, size=13, weight=ft.FontWeight.BOLD, expand=True),
              ft.Text("live" if entry.ready else ..., size=10, ...),
              ft.IconButton(icon=ft.Icons.CLOSE, icon_size=18, ...),
              ft.IconButton(icon=..., icon_size=18, ...),
              theme_btn,
          ],
          scroll=ft.ScrollMode.AUTO,
      )
  )
  ```
- **Fix / opportunity:** Convert `header` from an elevated `card()` to a full-width flat header bar with tokenized padding (`Padding(SPACE_SM, SPACE_SM, SPACE_LG, SPACE_SM)`), use `ARROW_BACK_ROUNDED` with `ICON_MD` (20), use `tokens.FONT_LG` (14) for title, and use `status_dot` for status. Remove `scroll=ft.ScrollMode.AUTO` from the primary header row.
- **Risk if ignored:** Visual inconsistency with the house design language; detached card wastes vertical space and clips buttons on narrow viewports.

---

### F8 · P2 · Missing session FAB and context-aware action menu

- **Where:** CollabShell `src/screens/session/fab_menu.py:1-216`, `src/screens/session/__init__.py:147-244`; ours `src/screens/terminal_view.py`.
- **What:** CollabShell anchors a mini FAB (`ft.FloatingActionButton(mini=True, bgcolor=Colors.PRIMARY)`) wrapping a `PopupMenuButton` (`MORE_VERT_ROUNDED`) at the page level. The menu provides rich terminal actions: New Terminal, Copy Selection, Paste, Clear Terminal, Theme Presets (Dracula, JetBrains Dark, Matrix Green, Colab Light), Zoom In/Out/Reset, Cursor Blink toggle, Search Bar toggle, and AI Explain. Ours has no FAB and none of these terminal utility actions except the theme toggle button in the header.
- **Evidence:** CollabShell `session/__init__.py:227` sets `page.views[0].floating_action_button = fab`. Ours has no FAB implementation.
- **Fix / opportunity:** Implement a session FAB or action menu exposing terminal controls (copy, paste, font size / zoom, cursor blink, search toggle).
- **Risk if ignored:** Feature gap vs reference; users lack touch-accessible clipboard, zoom, and display controls.

---

### F9 · P2 · Session selector card geometry and tap target discrepancy

- **Where:** CollabShell `src/components/session_card.py:10-85`, `src/screens/session_selector.py:74-81`; ours `src/screens/terminal_view.py:250-273, 292-305`.
- **What:** In CollabShell, session cards use `adaptive_glass_bg()`, `adaptive_glass_border()`, `tokens.RADIUS_MD` (12), padding `(14, 10, 14, 10)`, and the entire card is clickable (`ink=True`, chevron right). In ours, rows are styled with `bgcolor=theme.surface()`, `padding=4` (overly cramped literal), `border_radius=8` (`RADIUS_SM`), and only the trailing `TextButton("Resume")` or `TextButton("Open shell")` is clickable. Tapping the rest of the row does nothing, creating a tiny tap target on touchscreens.
- **Evidence:** CollabShell `session_card.py:75-84`:
  ```python
  padding=ft.Padding(tokens.SPACE_LG, tokens.SPACE_MD, tokens.SPACE_LG, tokens.SPACE_MD),
  border_radius=tokens.RADIUS_MD,
  bgcolor=adaptive_glass_bg(),
  border=ft.Border.all(1, adaptive_glass_border()),
  on_click=on_click,
  ink=True,
  ```
  Ours `src/screens/terminal_view.py:269-272, 301-304`:
  ```python
  bgcolor=theme.surface(),
  padding=4,
  border_radius=8,
  ```
- **Fix / opportunity:** Upgrade session selector rows to `glass_card` with `on_click` on the entire container, tokenized padding (`tokens.SPACE_MD`), and a trailing chevron or action button.
- **Risk if ignored:** Poor touch UX on mobile due to sub-standard tap target size.

---

### F10 · P2 · Missing Terminal font zoom and cursor blink settings

- **Where:** CollabShell `src/screens/session/terminal_panel.py:590-615, 912-925`; ours `src/screens/terminal_view.py`.
- **What:** CollabShell exposes font zoom controls (`zoom_in`, `zoom_out`, `reset_zoom`) in both the switcher toolbar and FAB menu, modifying `ps.zoom` and calling `mt.zoom_in()`/`zoom_out()`. It also exposes cursor blink toggling (`mt.toggle_cursor_blink()`). Ours exposes neither; font size is fixed and cursor blink cannot be changed.
- **Evidence:** CollabShell `terminal_panel.py:912-925` (`zoom_out_btn`, `zoom_in_btn`); ours `terminal_view.py` has no zoom or blink methods.
- **Fix / opportunity:** Wire `mt.zoom_in()`, `mt.zoom_out()`, and `mt.reset_zoom()` into terminal actions or header buttons.
- **Risk if ignored:** Accessibility issue for users needing larger font size on high-DPI phone screens.

---

### F11 · P3 · Ad-placement order shift with `apt_note` banner insertion

- **Where:** ours `src/screens/terminal_view.py:198-223`; `docs/decisions.md:116-121` (D-017.7).
- **What:** D-017.7 mandates that "the banner on the terminal screen sits ABOVE the app chrome, never next to the input... the app's own header row stays between the ad and the terminal". In our implementation, `pooled_banner_ad` is added at index 0 and `header` at index 1 (`terminal_view.py:181-182`). When `not note_dismissed`, the `apt_note` card is inserted at index 1 (`controls.insert(1, card(...))`). This shifts `header` to index 2, placing the dismissible note between the banner ad and the header. While the ad remains at the very top (above chrome), dismissing the note causes a visual layout jump of the header and terminal.
- **Evidence:** ours `src/screens/terminal_view.py:199-200`: `controls.insert(1, card(...))`.
- **Fix / opportunity:** Keep the apt note below the header (or make it a one-time toast/dialog) so the header stays directly under the ad without layout jumping.
- **Risk if ignored:** Minor layout jump upon dismissing the warning.

---

### F12 · P3 · Terminal status indicator lacks spinner and uses text instead of `status_dot`

- **Where:** CollabShell `src/screens/session/terminal_panel.py:812-831`, `src/screens/session/__init__.py:370-372`; ours `src/screens/terminal_view.py:145-149`.
- **What:** CollabShell uses an animated `ProgressRing(width=14, height=14, stroke_width=2)` when connecting, and a `status_dot(is_running)` in the header. Ours uses static text `"live"` / `"starting…"` with no spinner during connection, and raw error text `entry.error` which overflows on narrow screens.
- **Evidence:** CollabShell `terminal_panel.py:812-817` (`ProgressRing`) and `session/__init__.py:370`; ours `terminal_view.py:145-149`.
- **Fix / opportunity:** Replace raw `"starting…"` text with a `status_dot` + small `ProgressRing` spinner during shell initialization.
- **Risk if ignored:** Sub-par polish during container startup.

---

### F13 · P3 · CollabShell terminal screen is ad-free; our ad is an intentional divergence (D-017.7)

- **Where:** CollabShell `src/screens/session/__init__.py`, `src/screens/session/terminal_panel.py`; ours `src/screens/terminal_view.py:181`.
- **What:** CollabShell keeps its terminal screen completely ad-free. Ours deliberately introduces a banner ad above the app chrome per D-017.7.
- **Evidence:** CollabShell `SessionScreen` has no ad builder; ours `terminal_view.py:181` calls `pooled_banner_ad("terminal-1", page)`.
- **Fix / opportunity:** Maintain D-017.7 compliance while ensuring F11 layout stability.
- **Risk if ignored:** None; intentional divergence documented in D-017.7.

---

## Parity matrix

| Concern | CollabShell | Ours | Verdict |
|---|---|---|---|
| Bottom Nav isolation | Hidden in session (`views[0].navigation_bar = None`, `app_shell.py:133`) | Always rendered; traps tab switching (`app_shell.py:63-77`) | **GAP (P1)** F1 |
| Full-screen mode | Subview isolates screen to `SafeArea` | Hides top chrome but leaves bottom nav (~80px) (`app_shell.py:66`) | **GAP (P1)** F2 |
| Terminal sizing & insets | Handled by Flutter window/`SafeArea`; clean `on_resize` (`terminal_panel.py:294`) | Dead `bottom_inset` handling in `on_resize`; body squeezed (`terminal_view.py:88`) | **GAP (P1)** F3 |
| Quick commands | Virtual keys only; Ctrl+L for clear (`terminal_panel.py:626`) | Ad-hoc `quick_strip` buttons missing `\n` execution (`terminal_view.py:126`) | **GAP (P1)** F4 |
| Session tabs in terminal | `switcher_box` tabs (`Term 1`, `Term 2`, `+`) (`terminal_panel.py:838`) | None; exit to `SessionSelectorView` required (`terminal_view.py:137`) | **GAP (P2)** F5 |
| Search bar control | Hidden initially (`show_search=False`), toggled via FAB/key | `show_search=True` on mount; no re-open toggle if closed (`terminal_view.py:71`) | **GAP (P2)** F6 |
| Header chrome styling | Flat full-width surface, token padding (`session/__init__.py:424`) | Floating glass `card()`, literal sizes (`18`, `13`, `10`) (`terminal_view.py:134`) | **GAP (P2)** F7 |
| Session FAB / actions | Mini FAB with popup menu: copy, paste, zoom, blink, theme, AI | None (`terminal_view.py`) | **GAP (P2)** F8 |
| Session selector cards | Full `glass_card`, `RADIUS_MD`, ink=True, whole card tap | `surface()` box, padding=4, only TextButton tap (`terminal_view.py:270`) | **GAP (P2)** F9 |
| Zoom & blink controls | Switcher buttons + FAB zoom in/out/reset + blink toggle | None; fixed font size 11.0, fixed blink (`terminal_view.py`) | **GAP (P2)** F10 |
| Banner ad placement | Ad-free on terminal screen | Banner placed ABOVE app chrome per D-017.7 (`terminal_view.py:181`) | **INTENTIONAL DIVERGENCE (P3)** F13 |
| Banner & warning stacking | N/A | `apt_note` inserted between ad and header causes jump (`terminal_view.py:199`) | **POLISH (P3)** F11 |
| Loading & status dots | `ProgressRing` + `status_dot` in header & status bar | Plain text `"live"` / `"starting…"` without spinner (`terminal_view.py:146`) | **POLISH (P3)** F12 |
| Scrollback replay on mount | Ring buffer (2000 chunks) replayed via `on_mount` | Ring buffer (2000 chunks) replayed via `on_mount` (`terminal_view.py:96`) | **PARITY** |
| Dual input paths | `set_on_bytes` + `on_data` soft keyboard path | `set_on_bytes` + `on_data` soft keyboard path (`terminal_view.py:105-108`) | **PARITY** |
| Process lifecycle isolation | Processes live on observable entry, not widget | Processes live on `SessionEntry`, survive remounts (`session_manager.py:25`) | **PARITY** |

---

## ASCII control-tree comparison

### Reference (CollabShell) — subview isolation, flat header, in-screen tabs, FAB menu
```
AppShell (app_shell.py:43)
└─ SafeArea (app_shell.py:427)
   └─ SessionScreen (session/__init__.py:25)
      [page.views[0].navigation_bar = None]  (app_shell.py:133)
      [page.views[0].floating_action_button = build_session_fab()] (session/__init__.py:227)
      └─ Column spacing=0 expand (session/__init__.py:430)
         ├─ header_bar (session/__init__.py:360)  <- flat full-width SURFACE container
         │  └─ Row spacing=SPACE_SM:
         │     ├─ IconButton(ARROW_BACK_ROUNDED, size=ICON_MD) (on_back -> close_session)
         │     ├─ status_dot(is_running)
         │     ├─ Text(session_name, size=FONT_LG, weight=W_700, expand=True)
         │     └─ Row (badge rail, scroll=AUTO):
         │        ├─ hardware_badge
         │        ├─ shape_chip
         │        ├─ env_dialog_button (if env_count)
         │        ├─ build_tab_switcher (Notebook vs Terminal pill)
         │        ├─ build_help_button
         │        └─ theme_btn (IconButton)
         └─ content: Stack expand (session/__init__.py:312)
            ├─ NotebookView (visible=active_tab == 0)
            └─ TerminalPanel (visible=active_tab == 1) (terminal_panel.py:383)
               └─ Column spacing=0 expand (terminal_panel.py:969)
                  ├─ status_bar: Container (terminal_panel.py:809)
                  │  └─ Row: ProgressRing(14,14) | Text(status, size=FONT_XS)
                  ├─ switcher_box: Container (terminal_panel.py:927)
                  │  └─ Row:
                  │     ├─ Row scroll=AUTO (tab_buttons):
                  │     │  ├─ Container: Icon | Text("Term 1") | GestureDetector(CLOSE)
                  │     │  ├─ Container: Icon | Text("Term 2") | GestureDetector(CLOSE)
                  │     │  └─ IconButton(ADD_ROUNDED, tooltip="New Terminal")
                  │     ├─ IconButton(SYNC_ROUNDED, tooltip="Reconnect Terminal")
                  │     ├─ IconButton(PALETTE_ROUNDED, tooltip="Cycle Terminal Theme")
                  │     ├─ IconButton(ZOOM_OUT, tooltip="Zoom Out")
                  │     └─ IconButton(ZOOM_IN, tooltip="Zoom In")
                  └─ Stack expand (terminal_panel.py:973)
                     ├─ Container (visible=t.id == active_id):
                     │  └─ _TerminalHost (terminal_panel.py:317)
                     │     └─ MobileTerminal (terminal_panel.py:339)
                     │        ├─ Terminal (expand=True)
                     │        ├─ TerminalSearchBar (visible=False)
                     │        └─ ExtraKeysBar (show_settings=False)
                     └─ Container (hidden siblings)...
```

### Ours — embedded terminal, floating card header, quick strip, trapped bottom nav
```
AppShell (app_shell.py:42)
└─ Column spacing=0 expand (app_shell.py:63)
   ├─ Container(content=body, expand=True, bgcolor=theme.bg()) (app_shell.py:65)
   │  └─ TerminalView (screens/terminal_view.py:60)
   │     └─ Column spacing=4 expand (terminal_view.py:225)
   │        ├─ [if not fullscreen]:
   │        │  ├─ pooled_banner_ad("terminal-1") (Container 320x50) (terminal_view.py:181)
   │        │  ├─ [if not note_dismissed: card(apt_warning_note)] (inserted at index 1!)
   │        │  └─ header: card (glass_card, border_radius=16) (terminal_view.py:134)
   │        │     └─ Row scroll=AUTO:
   │        │        ├─ IconButton(ARROW_BACK, size=18) (leave_session)
   │        │        ├─ Icon(TERMINAL, size=16)
   │        │        ├─ Text(title, size=13, weight=BOLD, expand=True)
   │        │        ├─ Text("live"|"starting…", size=10)
   │        │        ├─ IconButton(CLOSE, size=18) (_confirm_close)
   │        │        ├─ IconButton(FULLSCREEN, size=18) (_toggle_fullscreen)
   │        │        └─ theme_btn (IconButton)
   │        ├─ [if fullscreen]:
   │        │  └─ Container(alignment=TOP_LEFT): IconButton(FULLSCREEN_EXIT, size=16)
   │        ├─ MobileTerminal (terminal_view.py:69)
   │        │  ├─ Terminal (expand=True)
   │        │  ├─ TerminalSearchBar (visible=True by default, no reopen button!)
   │        │  └─ ExtraKeysBar (show_settings=False)
   │        └─ [if not fullscreen]:
   │           └─ quick_strip: Container (terminal_view.py:169)
   │              └─ Row scroll=AUTO:
   │                 ├─ TextButton("ls") (no \n)
   │                 ├─ TextButton("apt update") (no \n)
   │                 ├─ TextButton("apt install …")
   │                 ├─ TextButton(" top") (no \n)
   │                 ├─ TextButton("clear") (no \n)
   │                 └─ TextButton("exit") (no \n)
   └─ NavigationBar (app_shell.py:66)  <- ALWAYS RENDERED! Traps tab navigation & squashes terminal!
```

---

## Migration plan (state-driven, no imperative widget mutation)

1. **P1 · Subview isolation & NavigationBar hiding (F1, F2).** In `src/app_shell.py:53-77`, conditionally omit `NavigationBar` when `entry is not None` or `state.terminal_fullscreen` is True. When leaving the session (`state.active_session = None`), restore the bottom bar. If tab navigation is triggered, allow `active_tab` to change by parking `state.active_session` or honoring the selected tab without trapping.
2. **P1 · Purge dead `bottom_inset` handling (F3).** In `src/screens/terminal_view.py:84-95` and `:226-228`, delete `data.get("bottom_inset", 0)` and the conditional `ft.Container(padding=ft.Padding.only(bottom=inset))` wrapper. Let Flutter's layout engine manage window insets cleanly.
3. **P1 · Fix quick command execution (F4).** In `src/screens/terminal_view.py:23-30, 124-128`, ensure complete commands (`ls`, `clear`, `exit`, `top`) send trailing newlines (`\n`) so they execute immediately upon tap, or replace with standard terminal utility buttons.
4. **P2 · In-screen multi-shell tabs (F5).** Add a shell tab switcher above the terminal in `src/screens/terminal_view.py` reading `manager.entries`, displaying running containers with close icons and an "Add" button to launch another container's shell without leaving the terminal view.
5. **P2 · Search bar toggle action (F6).** Set default `show_search=False` on `MobileTerminal` (`terminal_view.py:71`) and add a search toggle icon button (`ft.Icons.SEARCH_ROUNDED`) in the terminal header calling `mt.toggle_search()`.
6. **P2 · Flatten and tokenize header (F7).** Replace `card(...)` in `src/screens/terminal_view.py:134-167` with a flat full-width `ft.Container` (`bgcolor=theme.surface()`, `padding=Padding(tokens.SPACE_SM, tokens.SPACE_SM, tokens.SPACE_LG, tokens.SPACE_SM)`). Use `ARROW_BACK_ROUNDED` with `tokens.ICON_MD` (20), `tokens.FONT_LG` (14) bold title, and `status_dot` with connecting `ProgressRing`. Remove `scroll=ft.ScrollMode.AUTO` from the primary header row.
7. **P2 · Session actions / FAB menu (F8, F10).** Introduce a page-level session FAB (`build_session_fab`) exposing Zoom In/Out/Reset, Cursor Blink, Copy Selection, Paste, and Clear Terminal.
8. **P2 · Session selector card geometry (F9).** Refactor `SessionSelectorView` rows (`terminal_view.py:250-305`) into full-surface `glass_card`s with `ink=True`, `tokens.RADIUS_MD` (12), tokenized padding, title `tokens.FONT_LG`, trailing chevron or clear action buttons, and full card clickability.
9. **P3 · Stacking order and layout stability (F11).** In `terminal_view.py:177-224`, place the dismissible `apt_note` warning beneath the header rather than inserting it between the ad and the header, preventing layout jumps upon dismissal.

---

## Verified-good list

1. **Dual input paths:** `mt.set_on_bytes` (binary DataChannel) and `mt.on_data` (soft-keyboard string path) are both properly wired in `src/screens/terminal_view.py:105-108`, matching CollabShell `terminal_panel.py:357-360` and preventing lost keystrokes on Android.
2. **Scrollback persistence and replay:** Process output is captured into ring buffers (`deque(maxlen=2000)`) on `SessionEntry` (`src/services/session_manager.py:31`), survive widget remounts, and replay cleanly via `mt.on_mount` (`src/screens/terminal_view.py:96-98`), matching CollabShell `terminal_panel.py:264-284`.
3. **Session process decoupled from UI:** Shell processes are owned by `SessionManager` and survive navigation changes and theme flips (`src/services/session_manager.py:46-99`), matching CollabShell's `TerminalEntry` architecture.
4. **Ad placement (D-017.7):** `pooled_banner_ad` sits at index 0 of the column, strictly above the app chrome and far from the virtual extra keys bar (`src/screens/terminal_view.py:181`), obeying the safety requirement against accidental clicks.
5. **Theme synchronization:** App theme toggles trigger `_apply_theme` via `ft.use_effect` on `state.theme_revision` (`src/screens/terminal_view.py:117-122`), updating the terminal ANSI palette to match light/dark mode.

---

## Unverified

- Exact rendered pixel dimensions and soft-keyboard behavior on physical Android devices — verification was performed against installed Dart/Python sources and unit tests without physical device execution; UNVERIFIED.
- Whether physical hardware keyboards emit `bottom_inset` under any vendor-custom Flutter engine forks; UNVERIFIED (official `flet-terminal` 0.4.0 Dart source confirms standard engine emits only cols/rows).
