# 01 · Header + Home — design-parity audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** Reference (CollabShell): `src/app_shell.py:518-546` (esp. 439-579), `src/components/brand_header.py:6-42`, `src/screens/home/__init__.py:321-406` · Ours: `src/app_shell.py:57-74` (and 41-78), `src/screens/views.py:311-379` (and 73-445), `src/components/app_header.py:98-126` (and 1-127), `src/components/brand_hero.py:32-62` (and 1-63), `src/screens/terminal_view.py:230-326` · **Date:** 2026-10-23

Ground truth: `.venv/lib/python3.14/site-packages/` — flet **1.0.4** (`flet-1.0.4.dist-info/METADATA:4`), Python **3.14.9**.

---

## What it does / how the app uses it

Both applications implement a state-driven `@ft.component` architecture (Flet 1.0.4). CollabShell strictly separates persistent chrome from scrolling viewport content:
- **CollabShell:** At the shell level (`CollabShell/src/app_shell.py:569-579`), a **fixed header bar** (`:518-546`) is rendered outside the screen container inside a `SafeArea`. The **centered brand hero** (`CollabShell/src/components/brand_header.py:6-42`) is rendered as the first item *inside* the Home screen's scrollable column (`CollabShell/src/screens/home/__init__.py:321-323`). As a result, the header bar stays pinned at the top while the body (starting with the hero) scrolls beneath it.
- **Ours:** At the shell level (`src/app_shell.py:63-77`), no header bar exists — the shell returns only `body` and `NavigationBar`. In `DistroView` (`src/screens/views.py:310-315`), the **brand hero is placed first, followed by `AppHeader`**, and both reside *inside* the scrollable `ft.Column` (`:379`). The header scrolls out of view when scrolling down. Furthermore, `SessionSelectorView` (`src/screens/terminal_view.py:232-325`) omits `AppHeader` entirely, leaving the Terminal tab headless.

---

## Findings

### F1 · P1 · Header is inside the scroll body, not fixed above it (scrolls away)

- **Where:** 
  - Ours: `src/screens/views.py:310-315`, `src/screens/views.py:379`, `src/app_shell.py:63-77`
  - Reference (CollabShell): `src/app_shell.py:518-546`, `src/app_shell.py:569-579`
- **What:** In CollabShell, `header_bar` is instantiated at shell level and placed as a direct child of the top-level Column (`CollabShell/src/app_shell.py:570-574`) alongside `ft.Container(content=screen, expand=True)`. The screen container handles scrolling, while `header_bar` remains fixed. In our codebase, `src/app_shell.py:63-77` does not render any header; instead, `AppHeader` is placed at index 1 of `controls` in `DistroView` (`src/screens/views.py:312`) and inside `SettingsView` (`src/screens/views.py:431`). Because `DistroView` returns `ft.Column(controls=controls, ..., scroll=ft.ScrollMode.AUTO)` (`src/screens/views.py:379`), `AppHeader` scrolls off-screen when the user scrolls down the distro or container lists.
- **Evidence:** 
  Ours `src/screens/views.py:310-315`:
  ```python
  controls: list[ft.Control] = [
      build_brand_hero("Linux on Android — no root, no Termux"),
      AppHeader("Distros", lambda: page.run_task(methods.cycle_theme_mode), page=page),
      hints_card(st.hints_dismissed, lambda _e: setattr(state, "hints_dismissed", True)),
      section_header("Install"),
  ]
  ```
  Ours `src/screens/views.py:379`:
  ```python
  return ft.Column(controls=controls, spacing=4, expand=True, scroll=ft.ScrollMode.AUTO)
  ```
  Ours `src/app_shell.py:63-77`:
  ```python
  return ft.Column(
      controls=[
          ft.Container(content=body, expand=True, bgcolor=theme.bg()),
          ft.NavigationBar(...),
      ],
      spacing=0,
      expand=True,
  )
  ```
  CollabShell `src/app_shell.py:569-579`:
  ```python
  return ft.SafeArea(
      content=ft.Column(
          controls=[
              header_bar,
              ft.Container(content=screen, expand=True),
          ],
          spacing=0,
          expand=True,
      ),
      expand=True,
  )
  ```
- **Fix / opportunity:** Lift `AppHeader` to shell level in `src/app_shell.py:63-77`, placing it above `ft.Container(content=body, expand=True)` inside the Column. Remove `AppHeader` from `DistroView` (`src/screens/views.py:312`) and `SettingsView` (`src/screens/views.py:431`).
- **Risk if ignored:** When browsing long container or search lists, the user loses access to the tab title, version info, update notifications, and the theme toggle.

---

### F2 · P1 · Render order inverted: hero before header inside scroll column

- **Where:** 
  - Ours: `src/screens/views.py:311-312`
  - Reference (CollabShell): `src/app_shell.py:572`, `src/screens/home/__init__.py:321-324`
- **What:** In CollabShell, the render hierarchy is:
  1. `header_bar` (shell level, fixed chrome, `app_shell.py:572`)
  2. `screen` (body container, `app_shell.py:573`)
  3. `build_brand_header()` (centered hero as control 0 of scroll column, `home/__init__.py:323`)
  In our application, `build_brand_hero` is rendered at control index 0 (`src/screens/views.py:311`) and `AppHeader` is rendered at control index 1 (`:312`). Visually, the brand hero graphic appears *above* the window title bar.
- **Evidence:**
  Ours `src/screens/views.py:311-312`:
  ```python
  controls: list[ft.Control] = [
      build_brand_hero("Linux on Android — no root, no Termux"),
      AppHeader("Distros", lambda: page.run_task(methods.cycle_theme_mode), page=page),
  ```
  CollabShell `src/screens/home/__init__.py:321-324`:
  ```python
  return ft.Column(
      controls=[
          build_brand_header(),
          offline_banner,
  ```
  CollabShell `src/app_shell.py:572`:
  ```python
  controls=[
      header_bar,
      ft.Container(content=screen, expand=True),
  ]
  ```
- **Fix / opportunity:** Lifting `AppHeader` to shell level (F1) naturally restores the reference render hierarchy: Fixed Header Bar -> Scroll Body -> Centered Brand Hero at top of content.
- **Risk if ignored:** The visual hierarchy is backwards; the brand mark dominates the top of the viewport above the title bar, conflicting with house design standards and CollabShell.

---

### F3 · P2 · Missing header on Terminal tab and title handling across tabs

- **Where:** 
  - Ours: `src/screens/terminal_view.py:232-325`, `src/app_shell.py:24-28`, `src/app_shell.py:56-62`
  - Reference (CollabShell): `src/app_shell.py:26`, `src/app_shell.py:521-526`
- **What:** CollabShell derives the header title dynamically from `_TAB_NAMES[state.current_tab]` (`src/app_shell.py:522`), guaranteeing that all tabs ("Home", "Notebooks", "Terminal", "Files", "Settings") render consistent top chrome. In our app:
  - `DistroView` hardcodes `AppHeader("Distros", ...)` (`src/screens/views.py:312`).
  - `SettingsView` hardcodes `AppHeader("Settings", ...)` (`src/screens/views.py:431`).
  - `SessionSelectorView` (`src/screens/terminal_view.py:232-325`) contains **no `AppHeader` at all**.
  When the user taps the Terminal tab (`TAB_TERMINAL = 1`), the screen is headless: no title, no version chip, and no theme toggle button.
- **Evidence:**
  CollabShell `src/app_shell.py:521-526`:
  ```python
  ft.Text(
      _TAB_NAMES[state.current_tab],
      size=tokens.FONT_LG,
      weight=ft.FontWeight.BOLD,
      color=ft.Colors.ON_SURFACE,
  )
  ```
  Ours `src/screens/terminal_view.py:240, 325`:
  ```python
  sections: list[ft.Control] = []
  ...
  return ft.Column(controls=sections, spacing=4, expand=True, scroll=ft.ScrollMode.AUTO)
  ```
  (No `AppHeader` call anywhere in `SessionSelectorView`).
- **Fix / opportunity:** In `src/app_shell.py`, derive the title from `_TABS[active_tab][0]` (`"Distros"`, `"Terminal"`, `"Settings"`). When an active session exists (`entry is not None`), `TerminalView` already renders its own contextual session header (`src/screens/terminal_view.py:134-167`), so suppress the shell header bar only while `entry is not None` (mirroring CollabShell's `active_subview` gating at `app_shell.py:375`).
- **Risk if ignored:** The Terminal selector screen has broken UX consistency and lacks theme switching or version inspection.

---

### F4 · P2 · Header contents differ and unwanted horizontal scroll on header Row

- **Where:** 
  - Ours: `src/components/app_header.py:101-123`
  - Reference (CollabShell): `src/app_shell.py:518-546`
- **What:**
  1. **Action cluster:** CollabShell header right cluster includes: (a) History `IconButton` (visible on tab 0, `app_shell.py:528-534`), (b) version chip (`:535`), (c) help button `build_help_button(page, "global")` (`:536`), and (d) theme button (`:537`). Ours contains only `version_chip(page)` and `theme_button(on_cycle_theme)` (`src/components/app_header.py:111-118`). History and Help do not exist in `src/` (UNVERIFIED whether proot-distro will implement them; see Unverified).
  2. **Row scroll & alignment:** Ours sets `scroll=ft.ScrollMode.AUTO` on the header `ft.Row` (`src/components/app_header.py:122`). A header bar should never be horizontally scrollable; overflow indicates layout bugs. Ours also pairs `alignment=ft.MainAxisAlignment.SPACE_BETWEEN` with an explicit `ft.Container(expand=True)` spacer (`:110, 120`), creating redundant expansion logic.
- **Evidence:**
  Ours `src/components/app_header.py:102-123`:
  ```python
  content=ft.Row(
      controls=[
          ft.Text(title, size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, color=theme.text()),
          ft.Container(expand=True),
          ft.Row(
              controls=[version_chip(page), theme_button(on_cycle_theme)],
              spacing=tokens.SPACE_XS,
              vertical_alignment=ft.CrossAxisAlignment.CENTER,
          ),
      ],
      alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
      vertical_alignment=ft.CrossAxisAlignment.CENTER,
      scroll=ft.ScrollMode.AUTO,
  )
  ```
  CollabShell `src/app_shell.py:519-541`:
  ```python
  content=ft.Row(
      controls=[
          ft.Text(_TAB_NAMES[state.current_tab], size=tokens.FONT_LG, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
          ft.Container(expand=True),
          ft.IconButton(icon=ft.Icons.HISTORY_ROUNDED, ..., visible=state.current_tab == 0),
          _build_version_chip(),
          build_help_button(page, "global"),
          theme_btn,
      ],
      vertical_alignment=ft.CrossAxisAlignment.CENTER,
      spacing=tokens.SPACE_XS,
  )
  ```
- **Fix / opportunity:** Remove `scroll=ft.ScrollMode.AUTO` from `src/components/app_header.py:122`. Remove redundant `alignment=ft.MainAxisAlignment.SPACE_BETWEEN` and rely on `ft.Container(expand=True)`. Flatten the nested `Row` into a single Row matching CollabShell.
- **Risk if ignored:** Accidental horizontal drag gestures can scroll the header bar horizontally on small screens.

---

### F5 · P2 · Spacing and padding token drift (Header and Brand Hero)

- **Where:** 
  - Ours: `src/components/app_header.py:125`, `src/components/brand_hero.py:37-38, 50, 59, 61`
  - Reference (CollabShell): `src/app_shell.py:542-544`, `src/components/brand_header.py:11, 14-15, 23, 26, 34, 40`
- **What:**
  1. **Header Padding:** CollabShell uses asymmetric tokens: `ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM)` = `(14, 6, 10, 6)`. Ours uses hardcoded literal integers: `ft.Padding.symmetric(horizontal=12, vertical=8)`.
  2. **Hero Icon Size:** CollabShell uses `tokens.ICON_XXXL` = 80 (`brand_header.py:14-15`, `tokens.py:53`). Ours uses literal `96` (`brand_hero.py:37-38`). While `src/core/tokens.py:49` defines `HERO_ICON_SIZE = 96`, 96 is 20% larger than CollabShell's 80 and takes excessive vertical screen real estate.
  3. **Hero Tagline Typography:** CollabShell uses `size=tokens.FONT_SM` (= 10) (`brand_header.py:26`). Ours uses hardcoded literal `size=12` (`brand_hero.py:50`).
  4. **Hero Vertical Spacing:** CollabShell separates elements with explicit spacer containers: top spacer `tokens.SPACE_LG` (= 14), intermediate spacer `tokens.SPACE_SM` (= 6), bottom spacer `tokens.SPACE_XL` (= 16) (`brand_header.py:11, 23, 34`). Ours uses `ft.Padding.only(top=16, bottom=8)` and Column `spacing=8` (`brand_hero.py:59, 61`).
- **Evidence:**
  CollabShell `src/app_shell.py:542-544`:
  ```python
  padding=ft.Padding(
      tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM
  )
  ```
  Ours `src/components/app_header.py:125`:
  ```python
  padding=ft.Padding.symmetric(horizontal=12, vertical=8),
  ```
  CollabShell `src/components/brand_header.py:11-34`:
  ```python
  ft.Container(height=tokens.SPACE_LG),  # 14
  ft.Image(..., width=tokens.ICON_XXXL, height=tokens.ICON_XXXL),  # 80
  ...
  ft.Container(height=tokens.SPACE_SM),  # 6
  ft.Text(..., size=tokens.FONT_SM),     # 10
  ...
  ft.Container(height=tokens.SPACE_XL),  # 16
  ```
  Ours `src/components/brand_hero.py:37-61`:
  ```python
  ft.Image(..., width=96, height=96),
  ft.Text(tagline, size=12, ...),
  ...
  content=ft.Column(..., spacing=8),
  padding=ft.Padding.only(top=16, bottom=8),
  ```
- **Fix / opportunity:**
  - In `app_header.py:125`, use `ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM)`.
  - In `brand_hero.py`, adopt tokenized layout: icon dimensions 80 (`tokens.ICON_XXXL`), tagline `tokens.FONT_SM`, top clearance `tokens.SPACE_LG`, bottom clearance `tokens.SPACE_XL`.
- **Risk if ignored:** Visual inconsistency and crowding on small mobile viewports.

---

### F6 · P2 · Shell lacks SafeArea wrapper

- **Where:** 
  - Ours: `src/app_shell.py:63-77`
  - Reference (CollabShell): `src/app_shell.py:569-579`
- **What:** CollabShell wraps its top-level layout in `ft.SafeArea(content=..., expand=True)` (`CollabShell/src/app_shell.py:569-579`). Our `AppShell` returns a bare `ft.Column` (`src/app_shell.py:63`).
- **Evidence:**
  Ours `src/app_shell.py:63`:
  ```python
  return ft.Column(
      controls=[
          ft.Container(content=body, expand=True, bgcolor=theme.bg()),
          ft.NavigationBar(...),
      ],
      spacing=0,
      expand=True,
  )
  ```
  CollabShell `src/app_shell.py:569-579`:
  ```python
  return ft.SafeArea(
      content=ft.Column(
          controls=[
              header_bar,
              ft.Container(content=screen, expand=True),
          ],
          spacing=0,
          expand=True,
      ),
      expand=True,
  )
  ```
- **Fix / opportunity:** Wrap the outer `ft.Column` in `ft.SafeArea(content=..., expand=True)`.
- **Risk if ignored:** On Android devices with display cutouts, notches, or status bars, the top header bar collides directly with system indicators.

---

### F7 · P3 · Home / Distro section order rhythm and bottom spacer literal

- **Where:** 
  - Ours: `src/screens/views.py:310-379`
  - Reference (CollabShell): `src/screens/home/__init__.py:321-406`
- **What:**
  1. **Section rhythm:** CollabShell follows a disciplined layout rhythm:
     Hero -> Status/account chips -> Quick actions card -> Active sessions -> Content/cards -> Bottom spacer.
     Ours mixes header into the body and presents:
     Hero -> `AppHeader` -> `hints_card` -> Install section header -> `probe_banner` (if failed) -> Install card -> Progress indicator -> Containers section header -> Container rows/empty state -> Data note -> Pooled banner ad -> Bottom spacer.
  2. **Bottom spacer:** CollabShell references `ft.Container(height=tokens.ICON_XXXL)` (= 80, `home/__init__.py:401`). Ours hardcodes literal `ft.Container(height=88)` (`src/screens/views.py:378`) despite having `NAV_BAR_CLEARANCE = 88` defined in `src/core/tokens.py:54`.
- **Evidence:**
  CollabShell `src/screens/home/__init__.py:401`:
  ```python
  ft.Container(height=tokens.ICON_XXXL),
  ```
  Ours `src/screens/views.py:378`:
  ```python
  controls.append(ft.Container(height=88))
  ```
  Ours `src/core/tokens.py:54`:
  ```python
  NAV_BAR_CLEARANCE = 88
  ```
- **Fix / opportunity:** Use `ft.Container(height=tokens.NAV_BAR_CLEARANCE)` in `src/screens/views.py:378`. After removing `AppHeader` (F1), DistroView's order becomes: Brand Hero -> Hints Card -> Install Section -> Containers Section -> Ad -> Nav Clearance Spacer.
- **Risk if ignored:** Minor maintenance drift; literal integer bypassing design tokens.

---

## Parity matrix

| Concern | Reference (CollabShell) | Ours (proot-distro-flet) | Verdict |
|---|---|---|---|
| **Header placement** | Fixed at shell level (`app_shell.py:572`) | Inside scrollable column (`views.py:312`) | **GAP (P1)** F1 |
| **Scroll persistence** | Header stays fixed; body scrolls (`app_shell.py:570-577`) | Header scrolls off-screen with body (`views.py:379`) | **GAP (P1)** F1 |
| **Render hierarchy** | Header Bar -> Body -> Brand Hero (`app_shell.py:572`, `home/__init__.py:323`) | Brand Hero -> Header Bar -> Content (`views.py:311-312`) | **GAP (P1)** F2 |
| **Tab title derivation** | Dynamic `_TAB_NAMES[state.current_tab]` (`app_shell.py:522`) | Hardcoded per view (`views.py:312, 431`) | **GAP (P2)** F3 |
| **Terminal tab header** | Full header present on Terminal tab (`app_shell.py:522`) | Header completely missing (`terminal_view.py:240-325`) | **GAP (P2)** F3 |
| **Header right cluster** | History + Version chip + Help + Theme (`app_shell.py:528-537`) | Version chip + Theme toggle only (`app_header.py:111-118`) | **GAP (P2)** F4 |
| **Header Row scroll** | No scroll (`app_shell.py:519`) | `scroll=ft.ScrollMode.AUTO` (`app_header.py:122`) | **GAP (P2)** F4 |
| **Header padding** | Tokenized `(14, 6, 10, 6)` (`app_shell.py:542-544`) | Literal symmetric `(12, 8)` (`app_header.py:125`) | **GAP (P2)** F5 |
| **Hero icon dimensions** | 80 px (`tokens.ICON_XXXL`, `brand_header.py:14-15`) | 96 px (`brand_hero.py:37-38`, `tokens.py:49`) | **GAP (P2)** F5 |
| **Hero tagline type** | `tokens.FONT_SM` (10 px) (`brand_header.py:26`) | Literal `12` px (`brand_hero.py:50`) | **GAP (P2)** F5 |
| **Hero vertical rhythm** | Token spacers: top 14, mid 6, bot 16 (`brand_header.py:11,23,34`) | Literal padding (top 16, bot 8) + spacing 8 (`brand_hero.py:59,61`) | **GAP (P2)** F5 |
| **Hero icon source** | `icon.png` raster image (`brand_header.py:13`) | SVG bytes with theme tinting (`brand_hero.py:36-42`) | **PARITY (Intentional)** |
| **SafeArea wrapper** | `ft.SafeArea` at shell root (`app_shell.py:569`) | None (`app_shell.py:63`) | **GAP (P2)** F6 |
| **Bottom spacer token** | `tokens.ICON_XXXL` (= 80) (`home/__init__.py:401`) | Hardcoded literal `88` (`views.py:378`) | **GAP (P3)** F7 |
| **Bottom nav placement** | Shell level (`app_shell.py:155-162`) | Shell level (`app_shell.py:66-73`) | **PARITY** |

---

## ASCII trees

### Reference (CollabShell)
Fixed header bar outside; hero is the first element inside the scroll body:
```
AppShell (src/app_shell.py:43)
└─ ft.SafeArea (src/app_shell.py:569)
   └─ ft.Column [spacing=0, expand=True] (src/app_shell.py:570)
      ├─ header_bar (src/app_shell.py:518-546)  <-- FIXED CHROME (never scrolls)
      │  └─ ft.Row [spacing=SPACE_XS, padding=(14,6,10,6)]
      │     ├─ ft.Text(_TAB_NAMES[state.current_tab])
      │     ├─ ft.Container(expand=True)
      │     ├─ ft.IconButton(HISTORY, visible=tab==0)
      │     ├─ _build_version_chip()
      │     ├─ build_help_button()
      │     └─ theme_btn
      └─ ft.Container [expand=True] (src/app_shell.py:573)
         └─ HomeScreen (src/screens/home/__init__.py:321)
            └─ ft.Column [spacing=0, scroll=AUTO, expand=True] (src/screens/home/__init__.py:403-406)
               ├─ build_brand_header() (src/components/brand_header.py:6-42)  <-- HERO INSIDE BODY
               │  └─ ft.Column [center, spacing=0]
               │     ├─ spacer(SPACE_LG=14)
               │     ├─ ft.Image(ICON_XXXL=80)
               │     ├─ spacer(SPACE_SM=6)
               │     ├─ ft.Text(tagline, FONT_SM=10)
               │     └─ spacer(SPACE_XL=16)
               ├─ offline_banner
               ├─ auth_status_chip
               ├─ balance_chip
               ├─ credit_pill_row
               ├─ quick_actions (glass_card)
               ├─ active_sessions
               ├─ banner_ad
               ├─ features_section
               ├─ banner_ad
               ├─ how_it_works
               └─ ft.Container(height=ICON_XXXL=80)  <-- bottom spacer
```

### Ours (proot-distro-flet) — CURRENT
Header missing from shell; hero and header both placed inside scroll column:
```
AppShell (src/app_shell.py:41)
└─ ft.Column [spacing=0, expand=True] (src/app_shell.py:63)  <-- NO SafeArea
   ├─ ft.Container [content=body, expand=True] (src/app_shell.py:65)
   │  └─ DistroView (src/screens/views.py:73)
   │     └─ ft.Column [spacing=4, scroll=AUTO, expand=True] (src/screens/views.py:379)
   │        ├─ build_brand_hero(...) (src/screens/views.py:311)  <-- HERO RENDERED BEFORE HEADER
   │        │  └─ ft.Container [padding=(t=16, b=8)]
   │        │     └─ ft.Column [center, spacing=8]
   │        │        ├─ ft.Image(SVG, 96x96)
   │        │        └─ ft.Text(tagline, size=12)
   │        ├─ AppHeader("Distros", ...) (src/screens/views.py:312)  <-- HEADER INSIDE SCROLL BODY (scrolls away!)
   │        │  └─ ft.Row [alignment=SPACE_BETWEEN, scroll=AUTO]
   │        │     ├─ ft.Text("Distros")
   │        │     ├─ ft.Container(expand=True)
   │        │     └─ ft.Row: [version_chip, theme_button]
   │        ├─ hints_card(...)
   │        ├─ section_header("Install")
   │        ├─ probe_banner (conditional)
   │        ├─ card (install form & search)
   │        ├─ progress text
   │        ├─ section_header("Containers")
   │        ├─ container rows / empty_state
   │        ├─ data_note
   │        ├─ pooled_banner_ad(...)
   │        └─ ft.Container(height=88)  <-- literal 88
   └─ ft.NavigationBar (src/app_shell.py:66-73)
```

---

## Migration plan (state-driven, no imperative widget mutation)

The migration requires zero imperative mutation and strictly adheres to Decision D-015:

1. **Lift Header to Shell Level (`src/app_shell.py:57-77`):**
   - In `AppShell`, when `entry is None` (dashboard views: Distro, Terminal selector, Settings), construct `AppHeader` at shell level above `ft.Container(content=body, expand=True)`.
   - Pass the tab title dynamically derived from `_TABS[active_tab][0]`.
   - Wire the theme cycle handler via `lambda: page.run_task(methods.cycle_theme_mode)`.
   - Wrap the shell `Column` in `ft.SafeArea(expand=True)` (`.venv/.../flet/controls/core/safe_area.py:14`).

2. **Remove In-View Headers (`src/screens/views.py:312, 431`):**
   - Remove `AppHeader("Distros", ...)` from `DistroView` (`src/screens/views.py:312`).
   - Remove `AppHeader("Settings", ...)` from `SettingsView` (`src/screens/views.py:431`).
   - `build_brand_hero` naturally becomes the first control in `DistroView`'s scroll column, matching CollabShell's `build_brand_header()` placement.
   - `SessionSelectorView` (`src/screens/terminal_view.py:232`) automatically gains the persistent shell header without modifying `terminal_view.py`.

3. **Normalize `AppHeader` Layout (`src/components/app_header.py:98-126`):**
   - Remove `scroll=ft.ScrollMode.AUTO` from `ft.Row` (`src/components/app_header.py:122`).
   - Remove `alignment=ft.MainAxisAlignment.SPACE_BETWEEN` (`:120`); rely on `ft.Container(expand=True)` (`:110`).
   - Replace literal padding `ft.Padding.symmetric(horizontal=12, vertical=8)` with token padding `ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM)` (`:125`).
   - Flatten controls into a single Row.

4. **Align Brand Hero Geometry (`src/components/brand_hero.py:32-62`):**
   - Adjust icon dimensions to 80 px (`tokens.ICON_XXXL`) or verify whether 96 px is a deliberate brand requirement.
   - Set tagline `size=tokens.FONT_SM` (= 10) instead of literal `12`.
   - Replace literal padding/spacing with token spacers: top `tokens.SPACE_LG` (= 14), intermediate `tokens.SPACE_SM` (= 6), bottom `tokens.SPACE_XL` (= 16).

5. **Tokenize Bottom Spacer (`src/screens/views.py:378`):**
   - Replace `ft.Container(height=88)` with `ft.Container(height=tokens.NAV_BAR_CLEARANCE)` from `core.tokens:54`.

---

## Verified-good list

1. **Shell-level NavigationBar:** Both apps mount the primary `NavigationBar` at shell level (`src/app_shell.py:66-73` vs `CollabShell/src/app_shell.py:155-162`).
2. **Pure functional header builder:** `AppHeader` in `src/components/app_header.py:98-126` is a pure function returning an immutable control tree, in full compliance with D-015.
3. **Version / Update pill parity:** `version_chip` in `src/components/app_header.py:35-86` replicates CollabShell's `_build_version_chip` (`CollabShell/src/app_shell.py:461-516`), including update badge detection, accent pill background, and changelog dialog trigger.
4. **Hero centering:** Both apps center the brand hero via `horizontal_alignment=ft.CrossAxisAlignment.CENTER` (`src/components/brand_hero.py:58` vs `CollabShell/src/components/brand_header.py:39`).
5. **Theme-adaptive SVG rendering:** `brand_hero.py:42` properly inverts icon colors based on active theme mode (`ft.Colors.WHITE` in dark mode, artwork source in light mode).

---

## Unverified

- **History and Help actions:** CollabShell includes `ft.Icons.HISTORY_ROUNDED` and `build_help_button` in `header_bar`. No history store or help dialog exists in `proot-distro-flet` (`src/`); UNVERIFIED whether product requirements call for these slots.
- **Client-side evaluation of `ft.Colors.ON_SURFACE` vs `theme.text()`:** CollabShell uses Flutter theme tokens (`ft.Colors.ON_SURFACE`), while ours uses precomputed hex values (`theme.text()`). UNVERIFIED whether `ft.Colors.ON_SURFACE` dynamically updates without a full page refresh in Flet 1.0.4 on Android.
- **Rendered pixel snapshot of the reordered layout:** No live Android emulator run was performed; line-level layout analysis is verified via static code inspection. Label: UNVERIFIED.
