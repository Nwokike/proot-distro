# src/app_shell.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/app_shell.py` (all 78 lines) · `tests/test_ui_reactive.py` · `src/screens/views.py` · `src/screens/terminal_view.py` · `src/components/app_header.py` · `src/core/theme.py` · `src/core/state.py` · `src/state/controller_ctx.py` · `src/app_controller.py` · `docs/reference/house-ui-design.md` · `docs/decisions.md` (D-015, D-016, D-017) · `CollabShell/src/app_shell.py` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/app_shell.py` defines the root component `AppShell()` (`:41-77`), which is mounted by `AppController.mount_page()` via `page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))` (`src/app_controller.py:85`). It acts as the single navigation orchestrator for the application:
1. Intercepts first-run onboarding (`state.onboarding_done`, returning `OnboardingView()`).
2. Detects open container sessions (`state.active_session`, intending to return `TerminalView(entry)`).
3. Drives a 3-tab bottom `ft.NavigationBar` (`Distros` → `DistroView`, `Terminal` → `SessionSelectorView`, `Settings` → `SettingsView`).
4. Wraps view content in a full-bleed `ft.Container` styled with `theme.bg()` and `theme.surface()`.

---

## Findings

### F1 · P0 · `AppShell` does not subscribe to the observable `state` — onboarding never dismisses and terminal sessions never open or close
- **Where:** `src/app_shell.py:42-55` (`AppShell` component body; `:44` `ft.use_state(TAB_DISTRO)`, `:50` `if not state.onboarding_done:`, `:35` `container = state.active_session`) · `.venv/lib/python3.14/site-packages/flet/components/observable.py:165-176, 204-219` · `.venv/lib/python3.14/site-packages/flet/components/hooks/use_state.py:90-91` · `.venv/lib/python3.14/site-packages/flet/components/component.py:207-220, 234-248` · `src/app_controller.py:304, 410, 413`
- **What:** In Flet 1.0.4, `@ft.observable` notifies only explicitly registered subscribers. A component registers a subscription strictly via: (1) `ft.use_state(<observable>)` (`hooks/use_state.py:90-91`), (2) `ft.use_context` where the context holds an `Observable` (`hooks/use_context.py:106-107`), or (3) passing an `Observable` as a component parameter (`component.py:234-248`). `AppShell` does none of the three. Reading `state.onboarding_done` or `state.active_session` performs standard Python attribute reads; `Observable` defines `__setattr__` and `__delattr__` (`observable.py:204-219`), but has no `__getattr__` interception. When `Observable._notify` triggers (`observable.py:165-176`), `AppShell` is not in `__listeners` and is never re-rendered.
- **Evidence:** Commit `4ad4593` removed `_st, _ = ft.use_state(state)` with message `"AppShell: drop the redundant ft.use_state(state) — AppState is @ft.observable and already re-renders subscribers"`. When `finish_onboarding()` sets `state.onboarding_done = True` (`src/app_controller.py:304`), `AppShell` never re-renders; `OnboardingView()` stays on screen indefinitely. Similarly, when `open_session()` sets `state.active_session = container` (`src/app_controller.py:410`), `AppShell` never switches to `TerminalView`. When `leave_session()` sets `state.active_session = None` (`:413`), `AppShell` never leaves the terminal view.
- **Fix:** Restore the observable subscription at `src/app_shell.py:44`:
  ```python
  _st, _ = ft.use_state(state)
  ```
- **Risk if ignored:** Catastrophic failure on launch: users cannot exit onboarding without killing and restarting the app, and terminal sessions cannot be opened or exited reactively.

---

### F2 · P1 · Rendered order is logo then header; missing shell-level header violates D-017 and CollabShell layout
- **Where:** `src/app_shell.py:63-77` · `src/screens/views.py:311-312, 379, 431` · `docs/decisions.md:108-111` (D-017 §5) · `docs/reference/house-ui-design.md:8-19` · `CollabShell/src/app_shell.py:518-546, 569-577`
- **What:** The owner reported that the rendered layout places the brand logo above the header. In `src/app_shell.py:63-77`, `AppShell` contains zero header chrome. Instead, `DistroView` in `src/screens/views.py:311-312` renders:
  ```python
  controls: list[ft.Control] = [
      build_brand_hero("Linux on Android — no root, no Termux"),
      AppHeader("Distros", lambda: page.run_task(methods.cycle_theme_mode), page=page),
      ...
  ]
  ```
  This renders the hero logo *above* the header bar, and places both inside the scrollable body column (`views.py:379`), causing the header to scroll off-screen. In CollabShell (`CollabShell/src/app_shell.py:518-546, 572`) and D-017 §5, `AppHeader` is fixed shell-level chrome placed directly in `AppShell` above `body`, with the tab title left and the action cluster right, while `build_brand_hero` lives exclusively as the top item in the scrollable home body.
- **Evidence:** `AppHeader` (`src/components/app_header.py:98-126`) is defined but never imported or rendered in `src/app_shell.py`. `SettingsView` (`views.py:431`) renders its own `AppHeader`, while `TerminalView` (`src/screens/terminal_view.py:134-167`) creates a third ad-hoc header.
- **Fix:** Move `AppHeader` into `src/app_shell.py`. Derive the title from `active_tab` (`("Distros", "Terminal", "Settings")`), wire `methods.cycle_theme_mode`, and place `AppHeader` as the first child of `AppShell`'s Column above the body `Container`. Remove `AppHeader` calls from `DistroView` (`views.py:312`) and `SettingsView` (`views.py:431`).
- **Risk if ignored:** Upside-down visual hierarchy on the home tab, scrolling headers that disappear, and three incompatible header models across tabs.

---

### F3 · P1 · Architecture violation: monkeypatching `page._controller` and reaching into `session_manager` internals
- **Where:** `src/app_shell.py:31-39, 45` · `src/app_controller.py:84` · `src/state/controller_ctx.py:24-61`
- **What:** D-015 and BRIEF.md Rule 4 specify constructor injection and public context consumption via `ControllerMethodsCtx`. `src/app_controller.py:84` introduces an imperative monkeypatch: `self.page._controller = self`. `src/app_shell.py:45` consumes this via `controller = getattr(page, "_controller", None)`, and `_session_entry()` (`:31-39`) reaches directly into `controller.session_manager.entries.get(container)`.
- **Evidence:**
  ```python
  # src/app_shell.py:31-38
  def _session_entry(controller) -> object | None:
      if controller is None:
          return None
      manager = getattr(controller, "session_manager", None)
      container = state.active_session
      if manager is None or not container:
          return None
      return manager.entries.get(container)
  ```
  `AppShell` bypasses `methods = ft.use_context(ControllerMethodsCtx)` entirely. When `AppShell` is tested in isolation or rendered outside `AppController`, `_controller` is absent, causing session entry resolution to fail silently.
- **Fix:** Consume `methods = ft.use_context(ControllerMethodsCtx)` in `AppShell`. Expose session entry lookup through the controller methods or pass session objects via state, and delete `self.page._controller = self` from `src/app_controller.py:84`.
- **Risk if ignored:** Tight hidden coupling between UI shell and controller internals; breaks unit testability and violates house architecture rules.

---

### F4 · P1 · Session override traps tab navigation, shows NavigationBar during sessions, and ignores `terminal_fullscreen`
- **Where:** `src/app_shell.py:53-73` · `src/core/state.py:36` (`terminal_fullscreen`) · `src/screens/terminal_view.py:130-132, 178-194` · `CollabShell/src/app_shell.py:126-138, 427-437`
- **What:** `src/app_shell.py:1-4` claims: `"CollabShell's shape: tabs on the bottom bar, the session takes over the screen with a back button."` In reality:
  1. In CollabShell (`CollabShell/src/app_shell.py:130-134, 427-437`), when an active session is open, `NavigationBar` is hidden (`page.views[0].navigation_bar = None`) and the session view occupies the full screen. In `src/app_shell.py:64-74`, `AppShell` unconditionally renders `ft.NavigationBar` below the terminal session.
  2. If the user taps a `NavigationBar` tab while a session is open, `_on_change` updates `active_tab`, but `if entry is not None: body = TerminalView(entry)` (`:54-55`) takes precedence. The tab highlight shifts, but the view does not change. When the session is later closed, the app abruptly switches to the tab clicked earlier.
  3. When `state.terminal_fullscreen` is toggled (`src/screens/terminal_view.py:131`), `TerminalView` hides its banner and header, but `AppShell` continues rendering the bottom `NavigationBar`, defeating full-screen mode.
- **Evidence:** `src/app_shell.py:63-74` contains no conditional check on `entry` or `state.terminal_fullscreen` around `ft.NavigationBar`.
- **Fix:** When `entry is not None`: omit `NavigationBar` from the rendered controls (or set its visibility to `False`), allowing `TerminalView` to take over the screen. When in full-screen mode (`state.terminal_fullscreen`), omit shell chrome.
- **Risk if ignored:** Cluttered terminal viewport on mobile devices (80px wasted), broken full-screen mode, and incoherent tab selection state.

---

### F5 · P2 · Missing `SafeArea` exposes top chrome and navigation bar to mobile display insets and cutouts
- **Where:** `src/app_shell.py:63-77` · `.venv/lib/python3.14/site-packages/flet/controls/core/safe_area.py:13-72` · `CollabShell/src/app_shell.py:569-579` · `docs/swarm/design-parity/04-ddgs-and-collabshell-personal.md:140`
- **What:** `AppShell` returns a bare `ft.Column` without wrapping it in `ft.SafeArea`.
- **Evidence:** CollabShell wraps the outer column in `ft.SafeArea(content=ft.Column(...), expand=True)` (`CollabShell/src/app_shell.py:569-579`). In Flet 1.0.4, `SafeArea` handles top status bars, display cutouts/notches, and bottom system gesture bars (`safe_area.py:13-72`).
- **Fix:** Wrap the shell's top-level Column in `ft.SafeArea(content=..., expand=True)`.
- **Risk if ignored:** On Android target devices, top header buttons clip beneath the status bar/camera notch, and navigation destinations collide with system navigation pill/gestures.

---

### F6 · P2 · NavigationBar lacks house styling, indicator colors, and relies on fragile `int(e.data)`
- **Where:** `src/app_shell.py:47-48, 66-73` · `.venv/lib/python3.14/site-packages/flet/controls/material/navigation_bar.py:24-45, 107-212` · `.venv/lib/python3.14/site-packages/flet/controls/control_event.py:124-149` · `CollabShell/src/app_shell.py:140-162`
- **What:**
  1. `indicator_color` is omitted. House specification (`CollabShell/src/app_shell.py:160`, `docs/swarm/design-parity/04-ddgs-and-collabshell-personal.md:140-143`) requires `indicator_color=ft.Colors.with_opacity(0.12, theme.primary())`.
  2. `label_behavior` is omitted. CollabShell explicitly sets `label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW` (`navigation_bar.py:24`).
  3. `_on_change(e)` parses `set_active_tab(int(e.data))` (`src/app_shell.py:48`). In Flet 1.0.4, `e.control` is typed `NavigationBar` (`control_event.py:124`) and `e.control.selected_index` provides the typed `int` directly (`navigation_bar.py:139`). Parsing `int(e.data)` raises `ValueError` if `e.data` is missing or malformed in synthetic test events.
  4. Destinations in `_TABS` (`:24-28`) do not define `selected_icon` variants (`navigation_bar.py:71-76, 84-88`).
- **Evidence:** `src/app_shell.py:47-48, 66-73`.
- **Fix:**
  ```python
  def _on_change(e):
      set_active_tab(e.control.selected_index)

  ft.NavigationBar(
      destinations=[...],
      selected_index=active_tab,
      on_change=_on_change,
      bgcolor=theme.surface(),
      indicator_color=ft.Colors.with_opacity(0.12, theme.primary()),
      label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
  )
  ```
- **Risk if ignored:** Diverges from house visual design; potential runtime exceptions on unformatted event payloads.

---

### F7 · P2 · Theme switching leaves `AppShell` container and `NavigationBar` background stuck on old palette
- **Where:** `src/app_shell.py:65, 72` · `src/core/theme.py:46-53, 71-76` · `src/core/state.py:30-31`
- **What:** `src/core/theme.py:46-53` carries a false comment asserting that reading `_state.theme_revision` registers a reactive subscription (`"Reads state.theme_mode/theme_revision so callers subscribe and re-render on theme switch"`). As proven in F1, attribute reads on `@ft.observable` do not subscribe callers. Because `AppShell` does not subscribe to `state`, `theme.bg()` (`:65`) and `theme.surface()` (`:72`) are resolved once during mount and never re-evaluated when the theme changes.
- **Evidence:** When `methods.cycle_theme_mode()` runs (`src/app_controller.py:130`: `state.theme_revision += 1`), inner views that have `ft.use_state(state)` re-render with light/dark colors, but `AppShell`'s `Container(bgcolor=theme.bg())` and `NavigationBar(bgcolor=theme.surface())` remain frozen in their initial colors.
- **Fix:** Subscribing `AppShell` to `state` via `_st, _ = ft.use_state(state)` (F1) ensures the component re-renders and re-evaluates `theme.bg()` and `theme.surface()` on every theme revision.
- **Risk if ignored:** Visually fractured interface where inner content is light but outer shell and bottom bar are dark (or vice versa).

---

### F8 · P3 · View controls are instantiated without explicit keys, risking component reconciliation defects
- **Where:** `src/app_shell.py:54-61` · `.venv/lib/python3.14/site-packages/flet/components/component.py:151-165` · `CollabShell/src/app_shell.py:551, 555, 559, 563, 567`
- **What:** In `src/app_shell.py:54-61`, views are instantiated as bare components: `DistroView()`, `SessionSelectorView()`, `SettingsView()`. In Flet 1.0.4 declarative reconciliation, components without explicit keys rely entirely on positional matching. CollabShell explicitly attaches keys (`key=ft.ValueKey("distro_tab")`, `key=ft.ValueKey("terminal_tab")`, `key=ft.ValueKey("settings_tab")`).
- **Fix:** Pass `key=ft.ValueKey("distros")`, `key=ft.ValueKey("terminal")`, and `key=ft.ValueKey("settings")` to the respective views.
- **Risk if ignored:** Potential hook state retention or misplaced reconciliation across tab transitions.

---

### F9 · P3 · `tests/test_ui_reactive.py` assertion is a no-op that masked `AppShell` runtime defects
- **Where:** `tests/test_ui_reactive.py:43-45, 48-56` · `.venv/lib/python3.14/site-packages/flet/components/component.py:140-165, 170-205` · `.venv/lib/python3.14/site-packages/flet/controls/context.py:62-69`
- **What:** `tests/test_ui_reactive.py:43-45` defines:
  ```python
  def _render(fn) -> object:
      with Renderer().with_context():
          return Renderer().render_component(fn, (), {})
  ```
  `Renderer().render_component()` only instantiates the `Component` wrapper; it does *not* invoke `Component.before_update()` or evaluate the component body. Line 53 (`assert _render(app_shell.AppShell) is not None`) passes trivially without executing `AppShell()`. If actually evaluated outside an active page context, `page = ft.context.page` (`src/app_shell.py:43`) raises:
  `RuntimeError: The context is not associated with any page. Make sure you are accessing ft.context.page inside a Flet app callback.` (`controls/context.py:64`).
- **Evidence:** Running `Renderer().render_component(app_shell.AppShell, (), {}).before_update()` immediately raises `RuntimeError`. The test never asserted re-rendering or tested component body evaluation, which allowed the removal of `ft.use_state(state)` to pass CI unnoticed.
- **Fix:** Update test harness to mock `ft.context.page` and call `before_update()` or test through a simulated session page render to verify true reactive updates on state mutations.
- **Risk if ignored:** CI regression tests remain blind to missing subscriptions and component crashes.

---

## Verified Flet 1.0.4 API Reference

Every Flet API used in `src/app_shell.py` was spot-checked against `.venv/lib/python3.14/site-packages/flet/`:

| API in `src/app_shell.py` | Installed Source Location (`.venv/lib/python3.14/site-packages/flet/`) | Status | Notes |
|---|---|---|---|
| `@ft.component` (`:41`) | `components/component_decorator.py:10` | Verified | Decorator wrapping function into `Component` factory |
| `ft.Control` (`:42`) | `controls/control.py:13` | Verified | Base control type annotation |
| `ft.context.page` (`:43`) | `controls/context.py:46-69` | Verified | Property on `Context`; raises `RuntimeError` if outside page callback (`:64`) |
| `ft.use_state` (`:44`) | `components/hooks/use_state.py:48-118` | Verified | Hook attaching `ObservableSubscription` only if argument is `Observable` (`:90-91`) |
| `ft.Column` (`:63`) | `controls/core/column.py:13` | Verified | Accepts `controls`, `spacing=0`, `expand=True` |
| `ft.Container` (`:65`) | `controls/material/container.py:38` | Verified | Accepts `content`, `expand=True`, `bgcolor` |
| `ft.NavigationBar` (`:66`) | `controls/material/navigation_bar.py:107` | Verified | Accepts `destinations`, `selected_index`, `on_change`, `bgcolor` |
| `ft.NavigationBarDestination` (`:68`) | `controls/material/navigation_bar.py:48` | Verified | Accepts `icon`, `label`, `selected_icon` |
| `ft.Icons.APPS` (`:25`) | `controls/material/icons.py:30` | Verified | `_IconsProxy` resolves `"apps"` |
| `ft.Icons.TERMINAL` (`:26`) | `controls/material/icons.py:30` | Verified | `_IconsProxy` resolves `"terminal"` |
| `ft.Icons.SETTINGS` (`:27`) | `controls/material/icons.py:30` | Verified | `_IconsProxy` resolves `"settings"` |
| `ft.SafeArea` (proposed) | `controls/core/safe_area.py:13` | Verified | Accepts `content`, `expand=True` |
| `ft.NavigationBarLabelBehavior` (proposed) | `controls/material/navigation_bar.py:24` | Verified | Enum member `ALWAYS_SHOW` (`:27`) |

---

## Verified-good list

1. **Dependency constraints respected:** Uses only stock `flet==1.0.4` controls without external packages or custom shims (honoring D-003 and BRIEF rules).
2. **Tab indexing aligns with views:** `TAB_DISTRO = 0`, `TAB_TERMINAL = 1`, `TAB_SETTINGS = 2` matches the 3-destination order in `_TABS`.
3. **No imperative control mutations in `src/app_shell.py`:** Does not mutate `.value`, `.controls`, or call `page.update()` imperatively, complying with D-015 declarative principles.
4. **Valid Flet control parameters:** All constructor arguments passed to `ft.Column`, `ft.Container`, `ft.NavigationBar`, and `ft.NavigationBarDestination` exist and match signatures in `flet==1.0.4`.

---

## Unverified

1. **Active session tab coordination:** Whether closing or leaving a terminal session should return to `TAB_DISTRO` or `TAB_TERMINAL` — not explicitly specified in `docs/decisions.md` (label: `UNVERIFIED`).
2. **History and help actions on header:** Whether `methods.open_history` and global help modals should be wired to `AppHeader` in this milestone or deferred to M5 (label: `UNVERIFIED`).
3. **Hardware display insets under Android 15 edge-to-edge:** The exact pixel insets of `SafeArea` on physical Android 15 devices with system bar enforcement (label: `UNVERIFIED`).
