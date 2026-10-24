# src/core/styles.py — audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** `src/core/styles.py` (161 lines) · `src/components/ui.py` · `src/core/theme.py` · `src/core/tokens.py` · `docs/reference/house-ui-design.md` · `src/screens/terminal_view.py` · `src/screens/views.py` · installed `flet==1.0.4` at `.venv/lib/python3.14/site-packages/flet/` · DDGS `src/core/styles.py` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/styles.py` defines six house widget factories used across screens: `glass_card` (`:14`), `section_header` (`:25`), `status_dot` (`:59`), `chip` (`:69`), `empty_state` (`:101`), `loading_state` (`:146`). `components/ui.py` re-exports `glass_card` as `card`, `section_header`, and `empty_state` (with argument reordering); `status_dot` is imported directly in `screens/terminal_view.py:19` and called at `terminal_view.py:259`. `chip` and `loading_state` are defined but have no call sites in `src/` (grep returns only their definitions). All color resolution goes through `core/theme.py` (`glass_bg`, `glass_border`, `primary`, `text`, `text_dim`, `AppColors.OK`) and sizing through `core/tokens.py`.

---

## Findings

### F1 · P2 · `status_dot` OK color is dark-theme green with 1.49:1 contrast on light backgrounds
- **Where:** `src/core/styles.py:65` (`bgcolor=theme.AppColors.OK if is_running else theme.text_dim()`) · `src/core/theme.py:32` (`OK = "#A6E3A1"`) · `.venv/lib/python3.14/site-packages/flet/controls/colors.py:110`
- **What:** `AppColors.OK` is a single Catppuccin green used in both themes. Measured contrast of `#A6E3A1` against the light glass/background (`#FFFFFF`/`#F4F4F8`) is ~1.49:1, below the 3:1 expected for non-text UI components in light mode; in dark mode it is ~11.0:1. The idle branch (`theme.text_dim()`) is fine in both themes (~6.5:1 light).
- **Evidence:** Local computation: `#A6E3A1` vs `#FFFFFF` = 1.49; vs `#1E1E2E` = 11.03. `theme.text_dim()` light = `#5C5C6E` = 6.54 vs white. No `ok()` resolver exists in `src/core/theme.py` (only `glass_bg`/`glass_border`/`primary`/`text`/`text_dim`).
- **Fix / opportunity:** Add a theme-aware `ok()` resolver to `src/core/theme.py` (e.g. `LIGHT_OK = "#40A02B"`, `DARK_OK = "#A6E3A1"`) mirroring `primary()`/`text()`, and use `theme.ok()` in `status_dot`. No new dependency.
- **Risk if ignored:** Live status dots are nearly invisible in light mode, so users cannot tell running vs idle containers.

### F2 · P3 · `glass_card` default padding (`SPACE_MD = 10`) is below the house 12–16 range
- **Where:** `src/core/styles.py:14` (`padding: int | ft.Padding = tokens.SPACE_MD`) · `src/core/tokens.py:11` (`SPACE_MD = 10`) · `docs/reference/house-ui-design.md:51` (card padding 12–16)
- **What:** The house spec calls for card padding 12–16px; the default is 10px. Not a crash, but inconsistent with the documented house language and with `hints_card`/`probe_banner` which use `SPACE_MD`/`SPACE_SM`.
- **Evidence:** `tokens.SPACE_MD = 10`, `SPACE_LG = 14`, `SPACE_XL = 16` (`src/core/tokens.py:11-13`); house doc §4 "padding 12–16".
- **Fix / opportunity:** Change the default to `tokens.SPACE_LG` (14) or add a `CARD_PADDING` token. Callers passing explicit padding are unaffected.
- **Risk if ignored:** Slightly cramped cards; visual inconsistency only.

### F3 · P3 · `section_header` title size (`FONT_SM = 10`) is smaller than the house section-header range
- **Where:** `src/core/styles.py:29` (`size=tokens.FONT_SM`) · `src/core/tokens.py:28` (`FONT_SM = 10`) · `docs/reference/house-ui-design.md:54` (section header title BOLD; ffmpeg uses `FONT_XL = 20`)
- **What:** The house reference describes section headers as bold uppercase primary labels; other apps in the study use 14–20px. Here the header is 10px. Combined with `letter_spacing=1` this reads as a caption rather than a section title. May be intentional (dense mobile UI) but is not documented.
- **Evidence:** `tokens.FONT_SM = 10`, `FONT_LG = 14`, `FONT_XL = 18` (`src/core/tokens.py:28,30,31`); house doc §4.
- **Fix / opportunity:** Either document the 10px choice or bump to `tokens.FONT_MD`/`FONT_LG`. Verify call sites (`screens/views.py:314,363,432,457,491,517`, `screens/terminal_view.py:276,308`) still fit after change.
- **Risk if ignored:** Section grouping is visually weak; low functional impact.

### F4 · P3 · `chip` uses `RADIUS_SM = 8` although docstring calls it a "pill"
- **Where:** `src/core/styles.py:75` (docstring "tinted pill") · `src/core/styles.py:94` (`border_radius=tokens.RADIUS_SM`) · `src/core/tokens.py:19` (`RADIUS_SM = 8`) · `src/core/tokens.py:23` (`RADIUS_PILL = 999`)
- **What:** A pill shape requires `RADIUS_PILL`; `RADIUS_SM = 8` produces a rounded rectangle. The house reference (`house-ui-design.md` §4) uses pill Containers with `RADIUS_XS = 4` or Material `ft.Chip`. The current shape is a "rounded chip", not a pill, contradicting the docstring.
- **Evidence:** `tokens.RADIUS_SM = 8`, `tokens.RADIUS_PILL = 999` (`src/core/tokens.py:19,23`); `chip` returns `border_radius=tokens.RADIUS_SM` (`styles.py:94`).
- **Fix / opportunity:** Either change to `tokens.RADIUS_PILL` (true pill) and update docstring, or rename the docstring to "rounded chip". Since `chip` is unused in `src/`, the change is low-risk but should be validated if/when it is adopted.
- **Risk if ignored:** Documentation/code mismatch; future callers get an unexpected shape.

### F5 · P3 · `loading_state` does not theme its spinner and always expands
- **Where:** `src/core/styles.py:151` (`ft.ProgressRing(width=28, height=28)`) · `src/core/styles.py:159` (`expand=True`) · `src/core/theme.py:91-92` (`primary()`)
- **What:** The `ProgressRing` is created without `color=`, so it relies on the Material theme's primary rather than `theme.primary()` (which resolves per light/dark). `expand=True` on the outer `Container` can cause the loading state to fill/claim space in non-flex parents; the house loading state (CollabShell) is a plain centered spinner. `loading_state` is currently unused, so this is latent.
- **Evidence:** `ft.ProgressRing` signature accepts `color` (`.venv/.../progress_ring.py:13`+); no `color` passed at `styles.py:151`. `expand=True` at `styles.py:159`.
- **Fix / opportunity:** Pass `color=theme.primary()` and drop `expand=True` (or make it a parameter) so the state behaves as a normal block. Keep the 28px size per house spec (`house-ui-design.md` §5).
- **Risk if ignored:** Inconsistent spinner color in light mode and potential layout surprises when the function is adopted.

### F6 · P3 · `chip` and `loading_state` are defined but unused (dead code)
- **Where:** `src/core/styles.py:69` (`chip`) · `src/core/styles.py:146` (`loading_state`) · `src/components/ui.py` (no re-export of either)
- **What:** Grep across `src/` finds no callers of `chip` or `loading_state` (only their definitions and the `components/ui.py` wrappers, which do not wrap them). This is not a bug per se, but they are unaudited-by-usage surface that can drift; `loading_state` in particular carries the latent issues in F5.
- **Evidence:** `grep -rn "chip\b\|loading_state" src/` returns only definitions (plus `version_chip`/`hints_card` unrelated). `components/__init__.py:3` exports only `card, empty_state, hints_card, probe_banner, section_header`.
- **Fix / opportunity:** Either wire them into a screen (e.g. loading state in `views.py`) or remove them to keep the house API minimal. If kept, add tests.
- **Risk if ignored:** Dead code accumulates untested drift.

### F7 · UNVERIFIED · `empty_state` icon backdrop radius relies on `tokens.ICON_EMPTY = 48` for a 96×96 box
- **Where:** `src/core/styles.py:107` (`size=tokens.ICON_EMPTY`) · `src/core/styles.py:110-111` (`width/height=tokens.EMPTY_ICON_SIZE`) · `src/core/styles.py:112` (`border_radius=tokens.ICON_EMPTY`) · `src/core/tokens.py:43-44,49-50`
- **What:** The 96×96 backdrop uses `border_radius = ICON_EMPTY = 48`, producing a circle. This works only because the two token values happen to be half/double. If either token changes independently, the shape breaks (e.g. non-circular backdrop). Not a current bug, but a coupling smell.
- **Evidence:** `tokens.ICON_EMPTY = 48`, `tokens.EMPTY_ICON_SIZE = 96` (`src/core/tokens.py:43,50`). `border_radius=tokens.ICON_EMPTY` (`styles.py:112`).
- **Fix / opportunity:** Introduce `EMPTY_ICON_RADIUS = tokens.EMPTY_ICON_SIZE // 2` (or use `EMPTY_ICON_SIZE // 2` inline) so the radius tracks the box size.
- **Risk if ignored:** Future token edits can silently de-circle the backdrop.

---

## Missed capabilities (dependency audits only)

N/A — this is an app-component audit, not a dependency audit. No new packages proposed (D-003). Note: `ft.Container` already supports `visible`/`opacity` and `ft.ProgressRing` supports `color`; both are used elsewhere in the codebase; no dependency capability is missing.

---

## Verified-good list

1. **All Flet 1.0.4 APIs used exist with matching signatures:** `ft.Container` (`controls/material/container.py:39`), `ft.Row` (`controls/core/row.py:14`), `ft.Column` (`controls/core/column.py:14`), `ft.Text` (`controls/core/text.py:222`), `ft.Icon` (`controls/core/icon.py:13`), `ft.ProgressRing` (`controls/material/progress_ring.py:13`), `ft.Border.all` (`controls/border.py:204`), `ft.Padding`/`ft.Padding.symmetric` (`controls/padding.py:13,46`), `ft.Margin` (`controls/margin.py:10`), `ft.Alignment.CENTER` (`controls/alignment.py:33`), `ft.Colors.with_opacity` (`controls/colors.py:110`), `ft.TextStyle(letter_spacing=...)` (`controls/text_style.py:332`), `ft.FontWeight` (`controls/types.py:165`), `ft.MainAxisAlignment`/`ft.CrossAxisAlignment`/`ft.TextAlign`.
2. **`ft.Row(tight=True, spacing=...)` and `ft.Container(expand=True)`** are valid in 1.0.4 (`controls/core/row.py:71`, `container.py`).
3. **No imperative widget mutation** in `styles.py` (no `.value =`, `page.update()`, `.controls.append/clear`) — D-015 compliant.
4. **Theme-aware surfaces:** `glass_card` uses `theme.glass_bg()`/`theme.glass_border()` (`styles.py:20-21`), which resolve per theme (`theme.py:127-132`), so cards follow light/dark switches.
5. **`empty_state` structure matches the house spec** (icon in 96×96 tinted circle, title `FONT_XL`/W_600, message `FONT_MD` muted with `MESSAGE_MAX_WIDTH=320`, centered column) — `house-ui-design.md` §5.
6. **`status_dot` idle branch** uses `theme.text_dim()`, which is theme-aware and has adequate contrast in both themes.
7. **`chip` active/inactive text and tint opacity** (`0.12`/`0.05` via `ft.Colors.with_opacity`) follow the house chip recipe (`house-ui-design.md` §4).
8. **Runtime smoke test passed:** all six factories instantiate under `.venv` Python with `flet==1.0.4` (import + construction of every function returned `Container` with no exception).

---

## Unverified

1. Whether `ft.Container()` with no content collapses to zero height in a `Column` (relevant to any future "dismissed" usage of these factories) — labeled `UNVERIFIED` (not exercised here).
2. Whether `theme.AppColors.OK` should be moved to a theme-aware resolver is a design decision; the contrast numbers above are computed, but the product's acceptable threshold for status dots (decorative vs. informative) is not specified in `docs/decisions.md` — labeled `UNVERIFIED`.
3. Whether 10px section headers are intentional for this app's density (no decision-doc entry) — labeled `UNVERIFIED`; inferred from code only.