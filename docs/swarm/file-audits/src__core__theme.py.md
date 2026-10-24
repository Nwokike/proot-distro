# src/core/theme.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/core/theme.py` (133 lines) · `src/main.py` · `src/app_shell.py` · `src/app_controller.py` (theme-related) · `src/core/state.py` · `src/core/styles.py` · `src/components/*.py` · `docs/reference/house-ui-design.md` · `CollabShell/src/core/theme.py` · `DDGS/src/core/theme.py` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/theme.py` defines the `AppColors` palette constants (light/dark/glass/semantic), a `_page()` resolver over `ft.context.page`, an `is_light_theme(page=None)` effective-mode resolver, per-token accessor functions (`bg`, `surface`, `surface_alt`, `text`, `text_dim`, `primary`, `glass_bg`, `glass_border`), and `build_theme()` returning a `(light_theme, dark_theme)` tuple installed by `AppController.init` (`src/app_controller.py:53-54`). `AppShell` and components consume these helpers at render time (`src/app_shell.py:65,72`; `src/core/styles.py:20-21`).

---

## Findings

### F1 · P1 · `is_light_theme` does not subscribe callers; its "read for subscription" claim is false
- **Where:** `src/core/theme.py:43-68` (`:51-52` reads `_state.theme_mode` / `_state.theme_revision`) · `.venv/lib/python3.14/site-packages/flet/components/component.py:244-265` (`_attach_observable_subscription` only when an `Observable` is a component param or `use_state` value) · `.venv/lib/python3.14/site-packages/flet/components/hooks/use_state.py:88-91` · `.venv/lib/python3.14/site-packages/flet/components/observable.py` (no `__getattr__` defined; only `__setattr__`/`__delattr__` at `:204-219`)
- **What:** The docstring says reading `state.theme_mode`/`theme_revision` makes callers "subscribe and re-render on theme switch", but in Flet 1.0.4 an `Observable` only notifies components that registered via `ft.use_state(observable)` or received the observable as a parameter. A plain attribute read inside a helper creates no subscription, so components relying on `theme.*()` helpers will not re-render on a theme flip unless they separately subscribe (e.g. `terminal_view.py:122` uses `ft.use_effect(_apply_theme, [state.theme_revision])`).
- **Evidence:** `observable.py` defines `__setattr__` (`:204`) and `__delattr__` (`:218`) but no `__getattr__`; `component.py:244-265` attaches subscriptions only for `Observable` instances passed as params/`use_state` values.
- **Fix / opportunity:** Either correct the docstring and require callers to subscribe (`ft.use_state(state)` or `ft.use_effect(..., [state.theme_revision])`), or expose a small `use_theme()` hook. Do not claim implicit subscription.
- **Risk if ignored:** Theme toggles may leave stale colors in views that do not independently subscribe.

### F2 · P2 · Glass surfaces are identical to base surfaces, so glass cards have no elevation
- **Where:** `src/core/theme.py:25-28` (`LIGHT_GLASS_BG = "#FFFFFF"` == `LIGHT_SURFACE` `:11`; `DARK_GLASS_BG = "#1E1E2E"` == `DARK_SURFACE` `:18`) and `:127-132` (`glass_bg`/`glass_border`) · compare `CollabShell/src/core/theme.py:60-63` (`LIGHT_GLASS_BG = "#F1F5F9"`, `DARK_GLASS_BG = "#26263A"`) and `DDGS/src/core/theme.py:105-109` (`with_opacity` glass)
- **What:** The house glass treatment (`src/core/styles.py:14-21` `glass_card`) resolves to the same color as the page background/surface, so cards do not read as raised. Peers use a distinct raised surface.
- **Evidence:** `AppColors.LIGHT_GLASS_BG` `src/core/theme.py:25` equals `AppColors.LIGHT_SURFACE` `src/core/theme.py:11` (`#FFFFFF`); dark likewise.
- **Fix / opportunity:** Adopt raised glass values consistent with `CollabShell` (`#F1F5F9` / `#26263A`) or `DDGS` opacity-based glass.
- **Risk if ignored:** Flat UI, loss of card hierarchy.

### F3 · P2 · `SYSTEM` mode defaults to dark when platform brightness is not yet reported
- **Where:** `src/core/theme.py:59-68` (`return brightness == ft.Brightness.LIGHT`, so `None` → `False`) · compare `CollabShell/src/core/theme.py:104-109` (returns `True` on unknown) and `DDGS/src/core/theme.py:99-109` (returns `True` on unknown)
- **What:** During early startup (before the client reports `platform_brightness`), `is_light_theme()` returns `False` (dark), even on a light-OS host. Both peer implementations default to light on unknown brightness.
- **Evidence:** `src/core/theme.py:68` `return brightness == ft.Brightness.LIGHT`; `platform_brightness` defaults to `None` (`.venv/.../flet/controls/page.py:571`).
- **Fix / opportunity:** Match peers: `if brightness is None: return True` (or make the default explicit/configurable).
- **Risk if ignored:** Flash of dark theme on light systems at launch.

### F4 · P3 · `glass_bg()` / `glass_border()` do not accept a `page` argument, unlike peers and `is_light_theme`
- **Where:** `src/core/theme.py:127-132` (no `page` param) · compare `CollabShell/src/core/theme.py:112-123` and `DDGS/src/core/theme.py:112-123` (`adaptive_glass_bg(page)` / `adaptive_glass_border(page)`)
- **What:** The helpers always resolve via `ft.context.page`, which raises `RuntimeError` outside a running session (`.venv/.../flet/controls/context.py:136-143`) and cannot target a specific page.
- **Fix / opportunity:** Add an optional `page: ft.Page | None = None` parameter forwarded to `is_light_theme(page)`, matching the peer API.
- **Risk if ignored:** Harder to test/use in background tasks; API drift from house peers.

### F5 · P3 · `build_theme` ColorScheme omits most Material 3 container/on-* roles
- **Where:** `src/core/theme.py:98-124` (`scheme(...)` sets only `primary`, `surface`, `on_surface`, `on_surface_variant`, `error`, `outline`) · compare `DDGS/src/core/theme.py:203-248` (full scheme)
- **What:** Components or framework controls relying on `surface_container*`, `on_primary`, `primary_container`, etc. fall back to Flutter defaults instead of the app palette.
- **Fix / opportunity:** Expand `scheme()` to populate the roles used by the app (or accept that explicit per-theme colors are used everywhere). Low priority if all surfaces are explicit.
- **Risk if ignored:** Inconsistent Material-default colors in third-party/Flet controls.

### F6 · P3 · `surface_alt()` is used as a border color in `banner_ad.py:86`
- **Where:** `src/components/banner_ad.py:86` (`border=ft.Border.all(1, theme.surface_alt())`) · `src/core/theme.py:79-80`
- **What:** A "surface alt" fill token is reused as a border color; peers have a dedicated border token. Not a crash, but a semantic drift.
- **Fix / opportunity:** Add a `border()`/`outline()` token or reuse `glass_border()` for borders.
- **Risk if ignored:** Subtle visual inconsistency.

---

## Missed capabilities (dependency audits only)
N/A (this is an app file audit, not a dependency audit).

## Verified-good list
- `ft.context.page` resolver with `RuntimeError` guard exists and behaves as used (`.venv/.../flet/controls/context.py:136-143`).
- `ft.ThemeMode.SYSTEM/LIGHT/DARK` and `ft.Brightness.LIGHT/DARK` exist with the expected enum values (`.venv/.../flet/controls/types.py:860-884`).
- `ft.Theme(color_scheme=...)` and `ft.ColorScheme(...)` accept the fields used (`.venv/.../flet/controls/theme.py:145-...` and `:3281`).
- `build_theme()` is called once at boot and assigned to `page.theme`/`page.dark_theme` (`src/app_controller.py:53-54`).
- Light/dark palette contrast ratios are acceptable: `LIGHT_TEXT_DIM` on `LIGHT_SURFACE` ≈ 6.54:1; `DARK_TEXT` on `DARK_BG` ≈ 12.9:1 (computed).
- `ft.observable` state fields `theme_mode`/`theme_revision` exist (`src/core/state.py:30-31`).

## Unverified
- Whether any component besides `terminal_view` subscribes to `state.theme_revision`; a full grep was not exhaustively cross-checked against every screen. UNVERIFIED for screens not read in full.
- Whether `platform_brightness` is ever `None` at first render on the target Android host. UNVERIFIED (no device run performed).