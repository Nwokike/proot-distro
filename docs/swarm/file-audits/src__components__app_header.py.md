# src/components/app_header.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/components/app_header.py` (127 lines) · `src/screens/views.py` (usage lines 312, 431, 449) · `src/screens/terminal_view.py` (usage lines 14, 114) · `tests/test_ui_reactive.py` (lines 87-96) · `docs/reference/house-ui-design.md` · `CollabShell/src/app_shell.py:518-546` · `DDGS/src/components/app_header.py` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/components/app_header.py` provides three public pieces: `theme_button(on_cycle)` (lines 18-32), `version_chip(page)` (lines 35-86) with helper `_open_update_dialog` (lines 89-95), and `AppHeader(title, on_cycle_theme, page)` (lines 98-126). `AppHeader` builds a slim `Container` with a `Row`: bold title left, an expanding spacer, then a right cluster of `version_chip` + `theme_button`. It is used by `screens/views.py:312` (Distros) and `:431` (Settings); `theme_button` is also used directly in `screens/views.py:449` and `screens/terminal_view.py:114`. No `@ft.component` decorator: it is a plain builder that reads `core.state.state` at construction time.

---

## Findings

### F1 · P2 · Scrollable header Row also contains an expanded spacer (conflicting layout)
- **Where:** `src/components/app_header.py:102` (`ft.Row(...)`), `:110` (`ft.Container(expand=True)`), `:122` (`scroll=ft.ScrollMode.AUTO`) · compare `CollabShell/src/app_shell.py:519-541` (no `scroll`, spacer retained) and `DDGS/src/components/app_header.py:237-255` (`scroll=ft.ScrollMode.AUTO`, two nested rows, `alignment=SPACE_BETWEEN`, no expanded child inside the scrollable row).
- **What:** The outer `Row` is both horizontally scrollable and contains a child with `expand=True`. In Flutter/Flet, an `Expanded`/`expand` child inside a scrollable flex is not a meaningful layout and is either ignored or raises at layout time. The code mixes two house patterns (CollabShell's spacer row and DDGS's scrollable row) instead of picking one.
- **Evidence:** `.venv/lib/python3.14/site-packages/flet/controls/core/row.py:14` (`class Row(LayoutControl, ScrollableControl, AdaptiveControl)`); `scroll` is inherited from `ScrollableControl`. CollabShell `app_shell.py:519-541` has no `scroll=` and keeps `ft.Container(expand=True)`; DDGS `app_header.py:237-255` has `scroll=ft.ScrollMode.AUTO` with no `expand=True` child.
- **Fix / opportunity:** Adopt one pattern. To keep horizontal scroll (house rule, DDGS docstring: "header must scroll horizontally instead of clipping controls"), drop the expanded spacer and use two nested rows with `alignment=ft.MainAxisAlignment.SPACE_BETWEEN` exactly as DDGS does. Otherwise remove `scroll=` to match CollabShell.
- **Risk if ignored:** On narrow phones the header either clips its right cluster or lays out incorrectly; UNVERIFIED at runtime (no layout test exercises it).

### F2 · P3 · Header padding is hardcoded instead of using house tokens
- **Where:** `src/components/app_header.py:125` (`padding=ft.Padding.symmetric(horizontal=12, vertical=8)`) · compare `CollabShell/src/app_shell.py:542-544` (`ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM)` = 14/6/10/6) · `src/core/tokens.py:5-16`.
- **What:** The vertical/horizontal padding (12/8) does not match the CollabShell reference (14/6/10/6) or any token; it is an ad-hoc value, so the header is slightly taller/wider than the house standard and inconsistent with `CollabShell`.
- **Evidence:** `src/core/tokens.py:9-12` (`SPACE_XS=4, SPACE_SM=6, SPACE_MD=10, SPACE_LG=14`); `CollabShell/src/app_shell.py:542-544`.
- **Fix / opportunity:** Replace with `ft.Padding(tokens.SPACE_LG, tokens.SPACE_SM, tokens.SPACE_MD, tokens.SPACE_SM)` (or `ft.Padding.symmetric` using token values) to match CollabShell exactly.
- **Risk if ignored:** Cosmetic drift from the house header height; low user impact.

### F3 · P3 · Docstring advertises help/version slots that do not exist
- **Where:** `src/components/app_header.py:3-4` ("theme cycle now, help/version slots built in") · `src/components/app_header.py:111-118` (right cluster contains only `version_chip` and `theme_button`) · compare `CollabShell/src/app_shell.py:528-536` (history `IconButton`, version chip, help button, theme button).
- **What:** The module docstring claims "help/version slots built in", but the implementation exposes no help button and no history button (CollabShell's header has both, history visible only on the home tab). The public surface is smaller than documented.
- **Evidence:** `src/components/app_header.py:101-126`; `CollabShell/src/app_shell.py:528-536` (`ft.IconButton(icon=ft.Icons.HISTORY_ROUNDED, ..., visible=state.current_tab == 0)` and `build_help_button(page, "global")`).
- **Fix / opportunity:** Either extend `AppHeader` with optional `show_history`/`on_help` parameters (keeping the default minimal) or correct the docstring. No help-button helper exists in this repo (`grep -rn "build_help_button" src` returns nothing), so adding help would require a new component.
- **Risk if ignored:** Callers expecting a help affordance from the docstring get nothing; documentation drift.

### F4 · P3 · `theme_button` has no local state mirror for same-frame icon flip
- **Where:** `src/components/app_header.py:18-32` (`theme_button` reads `state.theme_mode` at construction) · `docs/reference/house-ui-design.md` §6 ("ktv's lesson: the theme IconButton needs a LOCAL `use_state` mirror so the icon flips in the same frame as the theme").
- **What:** `theme_button` is a plain function reading the observable at build time and relying on the parent component to re-render. The house design notes a known regression class where the icon lags the theme flip unless a local `use_state` mirror is used. `terminal_view.py:114` calls it inside a component that subscribes via `ft.use_state(state)`, so it works today, but standalone/external callers would not get same-frame updates.
- **Evidence:** `src/components/app_header.py:19-22`; `src/screens/terminal_view.py:63` (`_st, _ = ft.use_state(state)`); `src/screens/views.py:75` and `:387` (`st, _ = ft.use_state(state)`).
- **Fix / opportunity:** Keep as-is if all callers stay inside subscribed components; otherwise convert `theme_button` to a `@ft.component` with a local `use_state(state.theme_mode)` mirror per the ktv lesson. This is an API change for callers, so decide deliberately.
- **Risk if ignored:** Possible one-frame stale icon on theme toggle in any future caller that is not subscribed to `state`.

### F5 · P3 · Redundant inner import of the already-imported state singleton
- **Where:** `src/components/app_header.py:15` (`from core.state import state`) · `src/components/app_header.py:37` (`from core.state import state as core_state`) inside `version_chip`.
- **What:** `version_chip` re-imports the same singleton under a new name. Functionally harmless, but it obscures the single import and makes the two references (`state` at module level, `core_state` inside) look like different objects.
- **Evidence:** `src/components/app_header.py:15,37`.
- **Fix / opportunity:** Use the module-level `state` directly (`state.update_available`, `state.update_data`) and drop the inner import.
- **Risk if ignored:** Low; readability only.

### F6 · P2 · `version_chip` reads global state but `AppHeader` does not subscribe
- **Where:** `src/components/app_header.py:35-86` (`version_chip` reads `core_state.update_available`/`update_data`) · `src/components/app_header.py:98-126` (`AppHeader` is not `@ft.component` and calls no `ft.use_state`).
- **What:** The chip's update pill depends on `state.update_available`. Because `AppHeader` itself is not a component, it only rebuilds when its parent component re-renders. Parents `DistroView`/`SettingsView` do subscribe (`ft.use_state(state)`), so it works today, but the dependency is implicit. If the update feed lands while a parent is not subscribed (or `AppHeader` is reused in a non-subscribed context), the chip stays stale.
- **Evidence:** `src/screens/views.py:75` and `:387` (`st, _ = ft.use_state(state)`); `src/components/app_header.py:98` (no decorator).
- **Fix / opportunity:** Document the subscription contract, or make `AppHeader`/`version_chip` accept the state (or the already-resolved `update_available`/`update_data`) as arguments so the data flow is explicit. Minimal change: keep builders, but note that callers must subscribe to `state`.
- **Risk if ignored:** Stale version chip if an update is detected outside a subscribed render.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-component audit, not a dependency audit. No new packages proposed (D-003).

---

## Verified-good list

1. **All Flet 1.0.4 APIs used exist with matching signatures:** `ft.Container` (`.venv/.../controls/material/container.py:39`), `ft.Row` (`.venv/.../controls/core/row.py:14`), `ft.Text` (`.venv/.../controls/core/text.py:222`), `ft.IconButton` (`.venv/.../controls/material/icon_button.py:24`), `ft.FontWeight.BOLD` (`.venv/.../controls/types.py:165`), `ft.CrossAxisAlignment.CENTER` (`.venv/.../controls/types.py:388`), `ft.MainAxisAlignment.SPACE_BETWEEN` (`.venv/.../controls/types.py:...`), `ft.ScrollMode.AUTO` (`.venv/.../controls/scrollable_control.py`), `ft.Padding`/`ft.Padding.symmetric` (`.venv/.../controls/padding.py:13,46`), `ft.Border.all` (`.venv/.../controls/border.py:173,204`), `ft.Colors.with_opacity` (`.venv/.../controls/colors.py:110`), `ft.Icons.LIGHT_MODE_ROUNDED`/`DARK_MODE_ROUNDED`/`BRIGHTNESS_AUTO_ROUNDED` (verified importable).
2. **`ft.Padding(10, 4, 10, 4)` positional call is valid** — maps to `left, top, right, bottom` (`.venv/.../controls/padding.py:13`); verified by construction.
3. **`ft.Border.all(1.5, theme.primary())` positional call is valid** — `width, color` (`.venv/.../controls/border.py:204-209`).
4. **`ink=True` on `Container` is a real property** (`.venv/.../controls/material/container.py:109`).
5. **`theme_button` icon mapping matches the test contract** — `tests/test_ui_reactive.py:87-96` passes for `system`/`light`/`dark`.
6. **No imperative control mutation** (D-015): no `.value =`, `page.update()`, or `.controls.append/clear` in the file.
7. **Version chip morphs correctly** between `v{APP_VERSION}` and `Update: {label} Available!` with notification dot, matching CollabShell `app_shell.py:461-516` and DDGS `app_header.py:27-106`.
8. **`_open_update_dialog(page)` guards `page is None`** (line 90-91) and delegates to `components/update_dialog.show_update_dialog` whose signature `(page, update_data)` matches (verified `src/components/update_dialog.py:36`).
9. **bgcolor uses `theme.surface()`**, which resolves per light/dark (`.venv`-independent, `src/core/theme.py:75-78`); consistent with house per-theme component surfaces (`house-ui-design.md` §6).
10. **Title uses `tokens.FONT_LG` (14) + `ft.FontWeight.BOLD` + `theme.text()`**, matching CollabShell's tab-name styling (`app_shell.py:521-525`).

---

## Unverified

1. Whether a scrollable `Row` with an `expand=True` child raises or is silently ignored at layout time (F1) — not exercised by any test; labeled `UNVERIFIED`.
2. Whether `theme_button`'s icon flips in the same frame under a real theme toggle on device (F4) — house notes the regression class but this app's observable-driven path is not covered by a runtime test; labeled `UNVERIFIED`.
3. Whether persisting the version chip's update state across restarts is intended (no decision doc entry) — inferred from CollabShell/DDGS parity; labeled `UNVERIFIED`.
4. Whether `ft.Colors.SURFACE` (CollabShell) and `theme.surface()` (this app) render identically in both themes — not measured; labeled `UNVERIFIED`.