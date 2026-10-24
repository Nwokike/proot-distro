# src/screens/onboarding_view.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/screens/onboarding_view.py` · `src/app_controller.py` · `src/app_shell.py` · `src/core/state.py` · `src/core/constants.py` · `src/core/tokens.py` · `src/core/theme.py` · `src/components/brand_hero.py` · `src/state/controller_ctx.py` · `CollabShell/src/screens/onboarding/__init__.py` · `CollabShell/src/screens/onboarding/slides.py` · `DDGS/src/screens/onboarding_screen.py` · **Date:** 2026-10-24

## What it does / how the app uses it

`OnboardingView` is a `@ft.component` that renders a three-slide first-run deck. It is gated by `state.onboarding_done` in `AppShell` (`src/app_shell.py:50-51`). Local state (`ft.use_state`) tracks the active slide index. Swiping left/right or pressing Next/Skip calls `methods.finish_onboarding` (an `async` controller method) via `page.run_task`. Persistence is handled by `AppController._restore_onboarding` / `finish_onboarding` using `SharedPreferences` with the key `proot_onboarding_done` (`src/core/constants.py:22`). The component is pure-function / state-driven — no imperative widget mutation — satisfying D-015.

---

## Findings

### F1 · P2 · `_SLIDES` icon field is dead data — the per-slide icon is never rendered

- **Where:** `src/screens/onboarding_view.py:17,23,29` (field definition) vs `:76-81` (render block)
- **What:** Each `_SLIDES` dict carries an `"icon"` key (`None`, `ft.Icons.DOWNLOAD_ROUNDED`, `ft.Icons.TERMINAL_ROUNDED`). The render block unconditionally renders `ft.Image(src=app_icon_svg(), …)` on every slide. `slide["icon"]` is referenced nowhere in the render. Slides 2 and 3 show the same SVG brand icon instead of the Material icons intended to distinguish the slides visually.
- **Evidence:**
  - `_SLIDES` keys: `src/screens/onboarding_view.py:17` (`"icon": None`), `:23` (`ft.Icons.DOWNLOAD_ROUNDED`), `:29` (`ft.Icons.TERMINAL_ROUNDED`).
  - Render: `:76` `ft.Image(src=app_icon_svg(), width=tokens.HERO_ICON_SIZE, …)` — no conditional on `slide["icon"]`.
  - `ft.Icons.DOWNLOAD_ROUNDED` and `ft.Icons.TERMINAL_ROUNDED` both exist: `.venv/lib/python3.14/site-packages/flet/controls/material/icons.json:1` (python3 confirmed `True True`).
  - CollabShell slides.py branches on slide index to show different icons/content per slide (`CollabShell/src/screens/onboarding/slides.py:45-131`).
- **Fix / opportunity:** Either (a) implement the intended per-slide variation — slide 1 keeps the SVG brand hero, slides 2-3 render `ft.Icon(slide["icon"], …)` inside a styled container (same pattern as `CollabShell/src/screens/onboarding/slides.py:78-81` and `DDGS/src/screens/onboarding_screen.py:71-78`); or (b) remove the `"icon"` key from `_SLIDES` if a uniform brand-hero-only design is intentional.
- **Risk if ignored:** Slides 2 and 3 are visually indistinguishable at the icon level; onboarding conveys no per-feature iconography despite data being defined for it.

---

### F2 · P2 · `GestureDetector` has no `expand` — swipe dead zone covers most of the screen

- **Where:** `src/screens/onboarding_view.py:72-104`
- **What:** The `ft.GestureDetector` wraps the slide `Column` but carries no `expand=True`. Its hit-testable area is limited to the intrinsic size of the inner `Column` (roughly image height 96 px + spacer 16 + title ~36 + spacer 6 + body text ~56 = ~210 px). The region above the Skip row spacer and the large flex `Container(expand=True)` below (`:105`) do not forward drag events, so a user swiping anywhere outside the content column cannot navigate slides.
- **Evidence:**
  - `:72` `ft.GestureDetector(on_horizontal_drag_end=_swipe, content=ft.Column(…))` — no `expand` argument.
  - `ft.GestureDetector` inherits `expand` from `LayoutControl` → `Control` (`expand: Annotated[…]` at `.venv/lib/python3.14/site-packages/flet/controls/control.py:21`).
  - CollabShell reference: `CollabShell/src/screens/onboarding/__init__.py:205-213` — `slide_area = ft.GestureDetector(…, expand=True)` wrapping a `Container(expand=True)`.
  - DDGS reference: `DDGS/src/screens/onboarding_screen.py:181-188` — `ft.GestureDetector(content=ft.Container(…, expand=True), …)`.
- **Fix / opportunity:** Add `expand=True` to the `GestureDetector` (`:72`) so the entire slide area, including whitespace, captures horizontal drag events, matching both reference codebases.
- **Risk if ignored:** On a phone, users who swipe in the natural "full screen swipe" motion will frequently miss the narrow hit zone. Swipe navigation appears non-functional.

---

### F3 · P3 · Dot indicators have no size-change animation

- **Where:** `src/screens/onboarding_view.py:107-118`
- **What:** The progress dots grow/shrink (`width=24 if i == index else 8`) on slide change, but the `Container` carrying each dot has no `animate=` property. The transition is a hard jump, not a smooth animation. Both reference codebases animate the dots.
- **Evidence:**
  - `:108-113`: `ft.Container(width=24 if i == index else 8, height=8, …)` — no `animate` field.
  - `ft.Container.animate` exists: `.venv/lib/python3.14/site-packages/flet/controls/material/container.py:126` `animate: Optional[AnimationValue] = None`.
  - `ft.Animation` exists: `.venv/lib/python3.14/site-packages/flet/controls/animation.py:233` `class Animation`.
  - CollabShell: `CollabShell/src/screens/onboarding/__init__.py:169` `animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT)`.
  - DDGS: `DDGS/src/screens/onboarding_screen.py:114` `animate=ft.Animation(200, "easeOut")`.
- **Fix / opportunity:** Add `animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT)` to each dot `Container`. Zero code-architecture impact.
- **Risk if ignored:** Dot transition is visually jarring — standard polish gap on a first-impression screen.

---

### F4 · P2 · `ft.Image` missing `error_content` — blank 96×96 box if asset lookup fails

- **Where:** `src/screens/onboarding_view.py:76-82`
- **What:** `app_icon_svg()` returns `b""` (empty bytes) when none of its three path candidates resolve (`src/components/brand_hero.py:22-27`). The `ft.Image` widget in the onboarding view has no `error_content` fallback. An empty-bytes src will render as a blank 96×96 space. `brand_hero.build_brand_hero()` — the companion function in the same module — correctly sets `error_content=ft.Icon(ft.Icons.TERMINAL, size=64)` (`:43`), making this a copy-paste omission.
- **Evidence:**
  - `:76-82`: `ft.Image(src=app_icon_svg(), width=tokens.HERO_ICON_SIZE, height=tokens.HERO_ICON_SIZE, fit=ft.BoxFit.CONTAIN, color=…)` — no `error_content`.
  - `src/components/brand_hero.py:43`: `error_content=ft.Icon(ft.Icons.TERMINAL, size=64)` present.
  - `ft.Image.error_content: Optional[Control]` at `.venv/lib/python3.14/site-packages/flet/controls/core/image.py:46`.
  - `app_icon_svg()` fallback: `src/components/brand_hero.py:27` `return b""`.
- **Fix / opportunity:** Add `error_content=ft.Icon(ft.Icons.TERMINAL, size=64)` to the `ft.Image` at `:76`, matching `brand_hero.py:43`. Single-line change.
- **Risk if ignored:** On a fresh install or asset-misconfiguration build, the first-run screen shows a blank hero zone. The icon size is 96×96 so the gap is prominent.

---

### F5 · P2 · No `ft.SafeArea` — content may render under status bar / notch on Android

- **Where:** `src/screens/onboarding_view.py:62`
- **What:** The onboarding root is `ft.Container(expand=True, …)`. On Android, the system status bar and bottom navigation bar sit in safe-area insets that Flet respects via `ft.SafeArea`. Without it, the top spacer (`ft.Container(height=tokens.SPACE_XXL)` = 22 px, `:65`) may place the Skip button directly under a tall status bar (typically 24–48 dp), and the disclaimer text near the bottom (`:127-134`) may be obscured by Android's gesture navigation bar.
- **Evidence:**
  - `:62-141`: top-level `ft.Container(expand=True)` with no `SafeArea` wrapper.
  - `ft.SafeArea` exists: `.venv/lib/python3.14/site-packages/flet/controls/core/safe_area.py` (confirmed via `__init__.py:191`).
  - CollabShell: `CollabShell/src/screens/onboarding/__init__.py:215` `return ft.SafeArea(content=ft.Column(…), expand=True)`.
  - DDGS: `DDGS/src/screens/onboarding_screen.py:166` uses a plain `ft.Container` (same gap — not used as a positive example).
- **Fix / opportunity:** Wrap the return in `ft.SafeArea(content=<existing Container>, expand=True)`. Minimal change; matches the CollabShell reference pattern.
- **Risk if ignored:** On devices with tall status bars or display cutouts (notch/punch-hole), the Skip button or brand icon may be partially obscured on the very first screen users see.

---

### F6 · P3 · `ft.Image` has no `semantics_label` — screen-reader users get no icon description

- **Where:** `src/screens/onboarding_view.py:76-82`
- **What:** The hero image has `color` set but no `semantics_label`. Screen-reader users (TalkBack on Android) receive no description for the 96×96 icon.
- **Evidence:**
  - `:76-82`: `ft.Image(src=app_icon_svg(), …)` — no `semantics_label` argument.
  - `ft.Image.semantics_label: Optional[str]` at `.venv/lib/python3.14/site-packages/flet/controls/core/image.py:88`.
- **Fix / opportunity:** Add `semantics_label="Proot Distro app icon"` to the `ft.Image` at `:76`.
- **Risk if ignored:** Accessibility gap on a prominent first-run screen. Play Store accessibility policy violation risk for users relying on TalkBack.

---

### F7 · P3 · `getattr(e, "primary_velocity", 0)` is a redundant guard — the attribute always exists

- **Where:** `src/screens/onboarding_view.py:56`
- **What:** The swipe handler reads `velocity = getattr(e, "primary_velocity", 0) or 0`. Because `e` is always a `DragEndEvent` dataclass instance, `primary_velocity` is always present (defaulting to `None` per the field definition, not `AttributeError`). The `getattr` fallback of `0` can never be reached; the `or 0` correctly handles `None`. The code is safe but misleadingly defensive.
- **Evidence:**
  - `:56`: `velocity = getattr(e, "primary_velocity", 0) or 0`.
  - `DragEndEvent.primary_velocity: Optional[float] = field(default=None, …)` at `.venv/lib/python3.14/site-packages/flet/controls/events.py:314-315`.
  - CollabShell reference: `CollabShell/src/screens/onboarding/__init__.py:135` uses `v = e.primary_velocity or 0` directly.
  - DDGS reference: `DDGS/src/screens/onboarding_screen.py:132` uses `if e.primary_velocity is not None:`.
- **Fix / opportunity:** Simplify to `velocity = e.primary_velocity or 0` (CollabShell pattern), eliminating the misleading `getattr` fallback.
- **Risk if ignored:** None at runtime. Cosmetic: the `getattr` reads as if `DragEndEvent` might not carry the field, confusing future readers.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-code audit, not a dependency audit.

---

## Verified-good list

- **`@ft.component` / `ft.use_state` / `ft.use_context` / `ft.context.page`**: all confirmed present in `.venv/lib/python3.14/site-packages/flet/__init__.py:15-32,120-122`.
- **`ft.GestureDetector(on_horizontal_drag_end=…)`**: property confirmed at `.venv/…/flet/controls/core/gesture_detector.py:401`.
- **`DragEndEvent.primary_velocity: Optional[float]`**: confirmed at `.venv/…/flet/controls/events.py:314-315`.
- **`ft.Icons.DOWNLOAD_ROUNDED`, `ft.Icons.TERMINAL_ROUNDED`**: both present in `icons.json` (python3 confirmed `True True`).
- **`ft.Image(src=Union[str, bytes], color=Optional[ColorValue], fit=BoxFit, width, height)`**: all fields confirmed at `.venv/…/flet/controls/core/image.py:19,36,67,73`.
- **`ft.BoxFit.CONTAIN`**: confirmed at `.venv/…/flet/__init__.py:100` and `flet/controls/box.py`.
- **`ft.Colors.WHITE`**: `Colors.WHITE = "white"` at `.venv/…/flet/controls/colors.py:469`.
- **`ft.FontWeight.BOLD`**: `FontWeight.BOLD = "bold"` at `.venv/…/flet/controls/types.py:175`.
- **`ft.TextAlign.CENTER`**: `TextAlign.CENTER` confirmed at `.venv/…/flet/controls/types.py:662`.
- **`ft.MainAxisAlignment.CENTER`** and **`ft.CrossAxisAlignment.CENTER`**: both at `.venv/…/flet/controls/types.py:365,404`.
- **`ft.FilledButton(content=str, width, height, on_click)`**: `FilledButton` extends `Button(LayoutControl, …)`; `content: Optional[StrOrControl]` at `.venv/…/flet/controls/material/button.py:40`; `width/height` via `LayoutControl` at `.venv/…/flet/controls/layout_control.py:66,71`.
- **`ft.TextButton(…, visible=bool)`**: `visible: bool = True` at `.venv/…/flet/controls/control.py:106`.
- **`ft.Container(expand=True, bgcolor, border_radius, height, width)`**: all confirmed at `.venv/…/flet/controls/material/container.py:45,69,91`; `expand` via `Control:21`.
- **`ft.Row(alignment=MainAxisAlignment.CENTER, spacing)`** and **`ft.Column(horizontal_alignment=CENTER, spacing, spacing=0)`**: confirmed at `.venv/…/flet/controls/core/row.py:45,61` and `column.py:38,43,48`.
- **`page.run_task(handler)`**: requires coroutine function — confirmed at `.venv/…/flet/controls/page.py:929`; `finish_onboarding` is `async def` at `src/app_controller.py:303`; default `_noop_async` at `src/state/controller_ctx.py:19`.
- **`STORAGE_ONBOARDING_DONE = "proot_onboarding_done"`** at `src/core/constants.py:22`; read and written consistently in `app_controller.py:298-307`.
- **`state.onboarding_done`** gating in `app_shell.py:50-51`: architecturally correct — `AppShell` branches before constructing any main-app views.
- **Token usage**: all tokens consumed (`SPACE_XXL`, `SPACE_XL`, `SPACE_SM`, `SPACE_XS`, `FONT_HERO`, `FONT_LG`, `FONT_XS`, `HERO_ICON_SIZE`, `MESSAGE_MAX_WIDTH`, `RADIUS_PILL`) confirmed present in `src/core/tokens.py`.
- **`theme.is_light_theme()`, `theme.text()`, `theme.text_dim()`, `theme.primary()`, `theme.surface_alt()`, `theme.bg()`**: all defined in `src/core/theme.py`; read at render time so theme switches re-render correctly (D-015 compliant).
- **Architecture compliance**: no imperative widget mutation; handlers only write state or call controller methods via `page.run_task`; `@ft.component` not called from event handlers (D-015 §2 satisfied — no dialog construction inside handlers).
- **`app_icon_svg()` import**: confirmed in `src/components/brand_hero.py:17-27`; returns `bytes`.

---

## Unverified

- **Whether `ft.Image(src=b"")` (empty bytes) triggers `error_content` or simply renders blank**: the Image source code does not show the Dart-side handling. The `error_content` omission (F4) is a real risk regardless.
- **`ft.SafeArea` inset behavior on Android**: the Flet 1.0.4 Python wrapper exists and is the correct solution (F5), but exact Android inset pixel values depend on device/firmware.
- **Whether `ft.Container(animate=…)` on dots requires a re-render cycle to animate**: in the declarative model each re-render rebuilds the `Container`; animation triggers on property change detected by the Dart side. Expected to work per the CollabShell precedent, but not device-tested.
