# src/screens/views.py — audit

**Verdict:** BUG
**Confidence:** high
**Scope:** `src/screens/views.py` (26702 bytes compiled; 694 source lines) · `src/components/app_header.py` · `src/components/banner_ad.py` · `src/components/brand_hero.py` · `src/components/ui.py` · `src/core/state.py` · `src/core/theme.py` · `src/core/styles.py` · `src/core/tokens.py` · `src/app_controller.py` · `src/state/controller_ctx.py` · `src/app_shell.py` · `docs/decisions.md` (D-015, D-017) · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · **Date:** 2026-10-24

---

## What it does / how the app uses it

`src/screens/views.py` defines three public symbols: `DistroView()` and `SettingsView()` (`@ft.component` components) and `licenses_view()` (plain function). `DistroView` is the distro manager: a brand hero, an `AppHeader`, an install form (image-ref text field + optional name + Install/Search buttons), Docker Hub search results, an installing progress line, a containers section with per-container rows (open shell / reset / remove / more-actions popup), and a pooled banner ad. `SettingsView` is the settings screen: appearance/theme, storage, Docker Hub token, and about (licenses/privacy/probe). `licenses_view()` builds the open-source-licenses dialog content rendered inside `SettingsView._licenses` via `page.show_dialog`.

State subscription: both components call `st, _ = ft.use_state(state)` where `state` is the `@ft.observable` `AppState` singleton. `use_state` (`.venv/.../flet/components/hooks/use_state.py:48`) attaches an `ObservableSubscription` when the value is an `Observable` (use_state.py:90-91), so every `state.<field>` write triggers a re-render. Handlers only write state or call `ControllerMethodsCtx` methods (page.run_task) — no imperative widget mutation, consistent with D-015. `ft.use_context(ControllerMethodsCtx)` (use_context.py:84) resolves the controller methods bundle published by `AppController.init` (`app_controller.py:85`).

`licenses_view()` is deliberately a plain function (not `@ft.component`) because it is built inside a dialog handler; calling a component from a handler raises `RuntimeError: No current renderer is set` (D-015 ruling #2). It reads native provenance from the `flet_proot` wheel manifest and PyPI dist metadata, plus the scrollable `LICENSES/` texts (§3.3 compliance contract from D-015 §5).

Every Flet API used in views.py was verified present in flet 1.0.4: `ft.use_state` (use_state.py:48), `ft.use_context` (use_context.py:84), `ft.context.page` (controls/context.py:46), `ft.Page.run_task` (controls/page.py:929), `ft.Page.show_dialog`/`pop_dialog` (controls/base_page.py:402/427), `ft.Column` with `scroll=ft.ScrollMode.AUTO` (controls/core/column.py; types.py:692), `ft.Container`/`ft.Row`/`ft.Text`/`ft.TextField`/`ft.Button`/`ft.TextButton`/`ft.IconButton`/`ft.Icon`/`ft.Image`/`ft.AlertDialog`/`ft.ListTile`/`ft.Divider`/`ft.ExpansionTile`/`ft.PopupMenuButton`/`ft.PopupMenuItem` (all present in controls/material and controls/core), `ft.FontWeight.BOLD` (types.py:175), `ft.CrossAxisAlignment.CENTER` (types.py:404), `ft.MainAxisAlignment.SPACE_BETWEEN` (types.py:370), `ft.TextAlign.CENTER`, `ft.Text(selectable=...)`/`no_wrap=...` (controls/core/text.py:309/316), `ft.Colors.WHITE`/`with_opacity` (controls/colors.py:64,110), `ft.Icons.*` (controls/material/icons.py uses `_missing_` so any name resolves; icons.json backs it). `ft.AppHeader`/`build_brand_hero`/`pooled_banner_ad`/`section_header`/etc. are app-defined, not Flet APIs.

---

## Findings

### F1 · P0 · `src/LICENSES/` is missing — no license texts ship, compliance contract broken
- **Where:** `src/screens/views.py:20` (`_LICENSES_DIR = Path(__file__).resolve().parent.parent / "LICENSES"` → `src/LICENSES`), `:627-628` (`path = _LICENSES_DIR / fname; body = path.read_text(...)[:6000] if path.is_file() else "(text missing)"`); `docs/decisions.md` D-015 §5 (§3.3 content contract: "the scrollable `LICENSES/` texts"); `tests/test_ui_reactive.py:175-198` (`test_license_texts_are_present_and_shipped`).
- **What:** `src/LICENSES/` does not exist in the repo (confirmed: `find` returns no `LICENSES` dir; `ls src/LICENSES` fails). The only license texts on disk are under `docs/requests/mobile-forge-recipe-flet-proot/licenses/` (BSD-3-Clause, GPL-2.0, GPL-3.0) — not the seven `_TEXT_FILES` views.py expects, and not at `src/LICENSES`. Consequently every `licenses_view()` ExpansionTile body is `"(text missing)"` and the app ships no GPL/Apache/MIT/BSD/MPL/PSF text.
- **Evidence:** `uv run pytest tests/test_ui_reactive.py::test_license_texts_are_present_and_shipped` → `AssertionError: src/LICENSES is missing — the texts would not ship`. `test_licenses_view_carries_real_text` also fails: `'(text missing)' is contained in ...`.
- **Fix / opportunity:** Create `src/LICENSES/` with the seven `.txt` files (GPL-2.0.txt, GPL-3.0.txt, Apache-2.0.txt, MIT.txt, BSD-3-Clause.txt, MPL-2.0.txt, PSF-2.0.txt), matching the repo's notices files byte-for-byte (per the test), so `path.is_file()` is True and real text ships. Do not hardcode license text in Python (honors the no-hardcoded-data rule).
- **Risk if ignored:** GPL §3(b)/§6(b) source-offer contract is not honoured (incomplete/missing license text); the two license tests fail on every CI run; the About/licenses dialog shows "(text missing)" to users.

### F2 · P2 · License texts hard-truncated to 6000 characters
- **Where:** `src/screens/views.py:628` (`body = path.read_text(encoding="utf-8")[:6000] if path.is_file() else "(text missing)"`).
- **What:** GPL-3.0 is ~34 KB and GPL-2.0 ~18 KB; slicing at 6000 chars cuts both midsentence. The §3.3 contract promises "full texts below". Truncated licenses ship as the authoritative text.
- **Evidence:** views.py:628 literal `[:6000]`. GPL-3.0.txt in `docs/requests/.../licenses/` is ~34 KB (far above 6000).
- **Fix / opportunity:** Remove the `[:6000]` cap and render full text (the `ft.Text` inside a scrollable `ft.Column` with `scroll=ft.ScrollMode.AUTO` at views.py:693 already handles overflow). If a cap is required for memory, make it a named constant and document it; otherwise ship complete texts.
- **Risk if ignored:** Users see truncated legal text; compliance §3.3 "full texts" claim is false.

### F3 · P1 · Header is inside the scrollable body and scrolls away (order/position wrong)
- **Where:** `src/screens/views.py:310-315` (`controls = [build_brand_hero(...), AppHeader("Distros", ...), hints_card(...), section_header("Install")]`), `:379` (`return ft.Column(controls=controls, spacing=4, expand=True, scroll=ft.ScrollMode.AUTO)`); `src/app_shell.py:63-77` (shell renders only body + NavigationBar, no header); reference: `docs/swarm/design-parity/01-header-home.md` F1/F2 and CollabShell `app_shell.py:569-579` (fixed header bar outside the scroll).
- **What:** In `DistroView`, `AppHeader` is control index 1 inside the same `ft.Column` that has `scroll=ft.ScrollMode.AUTO`. When the user scrolls the container/search lists, the header (tab title, version chip, theme toggle) scrolls off-screen. The render order is also inverted vs CollabShell: brand hero renders *above* the header (`views.py:311` before `:312`), whereas CollabShell is fixed header bar → scroll body → brand hero first inside body. `SettingsView` places `AppHeader` first with no hero (`views.py:431`), so the two screens disagree about composition. `SessionSelectorView` (Terminal tab, defined in `src/screens/terminal_view.py:232`, re-exported via `src/screens/__init__.py:4`) has no header at all — headless.
- **Evidence:** views.py:310-315 and :379 quoted above. CollabShell reference: header_bar is a direct child of the top-level Column outside the scrolling screen container (`app_shell.py:570-574`).
- **Fix / opportunity:** Lift `AppHeader` to shell level in `src/app_shell.py` (fixed chrome above `ft.Container(content=body, expand=True)`), wrap shell in `ft.SafeArea`, derive the title from `_TABS[active_tab][0]`, and remove `AppHeader` from `DistroView` (`views.py:312`) and `SettingsView` (`views.py:431`). `build_brand_hero` then naturally becomes the first control of `DistroView`'s scroll column, matching CollabShell.
- **Risk if ignored:** On long container/search lists the user loses the tab title, version/update chip, and theme toggle; header placement is inconsistent across tabs; deviates from the house CollabShell pattern (D-017 §5).

### F4 · P2 · Bottom spacer uses literal `88` instead of `tokens.NAV_BAR_CLEARANCE`
- **Where:** `src/screens/views.py:378` (`controls.append(ft.Container(height=88))`); `src/core/tokens.py:54` (`NAV_BAR_CLEARANCE = 88`).
- **What:** The navigation-bar clearance spacer is a hardcoded literal `88` even though `tokens.py` defines `NAV_BAR_CLEARANCE = 88` for exactly this purpose. Minor maintenance drift; if the token changes, the spacer stalls.
- **Evidence:** views.py:378 vs tokens.py:54.
- **Fix / opportunity:** Replace `ft.Container(height=88)` with `ft.Container(height=tokens.NAV_BAR_CLEARANCE)`.
- **Risk if ignored:** Token/spacer drift; purely polish (P3-level), raised to P2 because it contradicts the house "use tokens, not literals" standard evident in `design-parity/01-header-home.md` F7.

### F5 · P2 · Numerous hardcoded literal sizes bypass design tokens
- **Where:** `src/screens/views.py` throughout: `height=40` (text fields/buttons :86, :325, :341, :345), `width=150` (name field :333), `text_size=12`/`:size=12`/`:size=11`/`:size=10` (many), `padding=4`/`:padding=4` (`_container_row` :306, `_hit_row` card), `border_radius=8` (:307), `height=32` (buttons :292-295), `spacing=2` (:347), `spacing=4` (cards :350, :379).
- **What:** `src/core/tokens.py` defines a full scale (`SPACE_XS=4`, `SPACE_SM=6`, `SPACE_MD=10`, `FONT_SM=10`, `FONT_MD=12`, `FONT_LG=14`, `RADIUS_SM=8`, `ICON_SM=16`, etc.) but views.py uses literals everywhere. Per `design-parity/04-ddgs-and-collabshell-personal.md` F4/F7, the type floor (8-10pt) is below the house legibility floor and spacing is cramped vs the 8-point grid used by DDGS/CollabShell.
- **Evidence:** views.py:86-91 (`height=40, text_size=12`), :333 (`width=150`), :306-307 (`padding=4, border_radius=8`), :347 (`spacing=2`), :378 (`height=88`). tokens.py:6-33 defines the scale.
- **Fix / opportunity:** Replace literals with tokens (e.g. `tokens.SPACE_MD` for card padding, `tokens.FONT_SM`/`FONT_MD` for body text, `tokens.RADIUS_SM` for radius). Consider raising the type floor per design-parity F4 (minimum 11-12pt for user-facing text).
- **Risk if ignored:** Visual inconsistency with CollabShell/DDGS house baseline; cramped, sub-legible text on small phone viewports. Polish/UX defect.

### F6 · P3 · `st.search_results[:12]` caps search hits at 12 with no overflow signal
- **Where:** `src/screens/views.py:346` (`controls=[_hit_row(hit) for hit in st.search_results[:12]]`).
- **What:** Docker Hub search results are silently capped at 12 rows. If the registry returns more, the user sees no "…and N more" indicator. UNVERIFIED whether the cap is intentional (Docker Hub pagination) or an accidental truncation.
- **Evidence:** views.py:346 literal `[:12]`.
- **Fix / opportunity:** Either document the cap as intentional (page-size) or render all results and add an overflow hint when `len(st.search_results) > 12`.
- **Risk if ignored:** Users may believe search returned only 12 results when more exist. Low impact.

### F7 · P3 · Progress text uses `theme.AppColors.ACCENT` (`#89B4FA`) which may be low-contrast on light theme
- **Where:** `src/screens/views.py:361` (`ft.Text(progress, size=11, color=theme.AppColors.ACCENT)`).
- **What:** `AppColors.ACCENT = "#89B4FA"` (core/theme.py:31). On the light theme (`LIGHT_BG = "#F4F4F8"`), bright blue on near-white is low contrast for an installing/progress status line.
- **Evidence:** views.py:361; theme.py:10 (`LIGHT_BG`), :31 (`ACCENT = "#89B4FA"`).
- **Fix / opportunity:** Use `theme.text_dim()` or `theme.primary()` for the progress line so it meets contrast on both modes.
- **Risk if ignored:** Installing status hard to read in light mode. Polish.

### F8 · P2 · `ft.Button` (not TextButton/FilledButton) used for primary "Open shell" action
- **Where:** `src/screens/views.py:289-295` (`ft.Button("Open shell", on_click=..., height=32)`, `:294` Reset, `:295` Remove).
- **What:** `ft.Button` is the generic material Button (verified exists at controls/material/button.py:26). The house pattern (DDGS) uses a pill `FilledButton` for primary actions (height ≥ 44) and `TextButton`/`OutlinedButton` for secondary. Default-height `ft.Button` rows read as secondary actions, not the primary "open shell" entry point.
- **Evidence:** views.py:289-295; design-parity/04 F13 (primary action = centered pill FilledButton).
- **Fix / opportunity:** Make "Open shell" a `ft.FilledButton` (pill, height ≥ 44) and keep Reset/Remove as `TextButton`, matching the house primary-action convention.
- **Risk if ignored:** Primary action not visually distinguished; UX polish defect.

### F9 · P2 · `DistroView` and `SettingsView` disagree on header/hero composition (inconsistent screen chrome)
- **Where:** `src/screens/views.py:310-315` (DistroView: hero → AppHeader → hints → sections) vs `:429-432` (SettingsView: AppHeader first, no hero).
- **What:** DistroView leads with the brand hero then the header; SettingsView leads with the header and no hero. There is no single composition rule across screens. (Related to F3 — see design-parity/04 F3.)
- **Evidence:** views.py:310-315 vs :429-432.
- **Fix / opportunity:** Resolved by lifting `AppHeader` to shell level (F3 fix); then DistroView = hero → hints → sections, SettingsView = hints/sections with no duplicate header.
- **Risk if ignored:** Inconsistent chrome across tabs; the "nonsense" composition the owner flagged in design-parity/04 F3.

### F10 · P3 · `SettingsView` `token` local state is not subscribed to `state.docker_token` updates from elsewhere
- **Where:** `src/screens/views.py:390` (`token, set_token = ft.use_state(st.docker_token)`), `:504` (`on_change=lambda e: set_token(e.control.value)`), `:492-515` (Docker Hub card).
- **What:** `token` is seeded once from `st.docker_token` at first render and thereafter lives in local `use_state`. If `state.docker_token` is changed by another path (e.g. prefs restore in `app_controller.py:_restore_prefs` line 127 sets `state.docker_token = token`), the Settings text field does not update because `use_state` only seeds on mount and the component does not read `st.docker_token` again or subscribe to it. `ft.use_state(state)` subscribes to the *observable object* but `token` is a plain string copy, not a live binding.
- **Evidence:** views.py:390, :504; app_controller.py:123-127 (`state.docker_token = token`).
- **Fix / opportunity:** Read `st.docker_token` directly at render (or reset local state when `st.docker_token` changes via a `use_effect` on `st.docker_token`), so the field reflects the persisted value. Note: this only matters if Settings is re-rendered after an external token change; since `use_state(state)` triggers re-render on any state change but `token` is a stale copy, the field shows stale data.
- **Risk if ignored:** Settings Docker Hub token field can show a stale value after a prefs restore or external change. UNVERIFIED whether any external path mutates `docker_token` after Settings mounts (only `_restore_prefs` and `set_docker_token`, both go through Settings itself).

---

## Verified-good list

- **State subscription works:** `ft.use_state(state)` attaches an `ObservableSubscription` (use_state.py:90-91) so `DistroView`/`SettingsView` re-render on every `state.<field>` mutation. Verified by `tests/test_ui_reactive.py::test_state_changes_rerender_without_frozen_errors` (passes).
- **No imperative widget mutation:** `tests/test_ui_reactive.py::test_screens_contain_no_imperative_mutation` passes — no `.value =`, `page.update()`, `.controls.append`, or `.controls = [...]` in `src/screens/`. Compliant with D-015.
- **`licenses_view()` plain function is correct:** called inside a dialog handler (`views.py:422`), avoiding the "No current renderer" `RuntimeError` (D-015 ruling #2).
- **All Flet 1.0.4 APIs used exist:** `use_state`, `use_context`, `context.page`, `Page.run_task` (page.py:929), `Page.show_dialog`/`pop_dialog` (base_page.py:402/427), `Column`/`ScrollMode.AUTO` (types.py:692), `Container`/`Row`/`Text`/`TextField`/`Button`/`TextButton`/`IconButton`/`Icon`/`Image`/`AlertDialog`/`ListTile`/`Divider`/`ExpansionTile`/`PopupMenuButton`/`PopupMenuItem`, `FontWeight.BOLD` (types.py:175), `Colors.WHITE`/`with_opacity` (colors.py:64/110), `Icons.*` (valid via `_missing_`). No hallucinated API.
- **A9 consent dialog content correct:** `views.py:93-130` carries the image ref, the "size unknown until the registry responds" disclosure, typical-size estimates (Alpine ~8 MB / Debian ~30 MB / Ubuntu ~75 MB), and the "download starts only after you tap Install" line — matching D-015 §4.
- **`page.show_dialog`/`pop_dialog` usage correct:** dialogs are opened with `show_dialog` and closed with `pop_dialog` in handlers; no double-open `RuntimeError` path observed.
- **`ft.ExpansionTile(title=..., controls=[...])`, `ft.Divider()`, `ft.Text(selectable=...)` all valid** in flet 1.0.4 (expansion_tile.py:53, divider.py:13, text.py:309).
- **`ft.PopupMenuItem(content=ft.Text(...), on_click=...)` valid** (popup_menu_button.py:46/94).

---

## Unverified

- Whether `src/LICENSES/` contents must match `docs/requests/.../licenses/` byte-for-byte (the test asserts this against `root / "LICENSES"` which also doesn't exist — the repo's notices file location is UNVERIFIED).
- Whether `state.docker_token` is ever mutated outside Settings after mount (only `_restore_prefs` and `set_docker_token` write it — both occur before/during Settings use; F10 impact UNVERIFIED).
- Whether the 12-result search cap (`views.py:346`) is an intentional page size (F6).
- Device-level rendering of the hero/header order and the scroll-away behavior (static analysis only; design-parity/01-header-home.md F1/F2 labels live pixel snapshot as UNVERIFIED).
- Whether `AppHeader` is read from `page._controller` anywhere (not in views.py; controller_ctx pattern is used instead).

---

## Summary

`src/screens/views.py` is architecturally sound (state-driven, no imperative mutation, correct context usage, all Flet 1.0.4 APIs valid) but ships a **P0 compliance defect**: `src/LICENSES/` is missing so no license texts ship and `[:6000]` truncates what little would render (F1/F2), failing two tests and breaking the D-015 §3.3 contract. **P1**: the header lives inside the scrollable column and renders after the hero, scrolling away and diverging from the CollabShell fixed-header pattern (F3). **P2**: literal `88` nav spacer instead of `tokens.NAV_BAR_CLEARANCE` (F4), widespread literal sizes bypassing the design-token scale (F5), 12-result search cap with no overflow signal (F6), low-contrast ACCENT progress text (F7), generic `ft.Button` for the primary "Open shell" action (F8), and inconsistent hero/header composition across DistroView vs SettingsView (F9). A staleness risk on the Docker Hub token field is UNVERIFIED (F10).

The single most important finding: **F1** — `src/LICENSES/` is missing, license texts do not ship, and two tests fail (`test_license_texts_are_present_and_shipped`, `test_licenses_view_carries_real_text`), violating the GPL §3(b)/§6(b) source-offer contract.
