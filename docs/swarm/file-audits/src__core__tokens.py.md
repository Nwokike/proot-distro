# src/core/tokens.py — audit

**Verdict:** IMPROVE
**Confidence:** high
**Scope:** `src/core/tokens.py` (65 lines) · `src/core/styles.py` · `src/components/*` (app_header, banner_ad, brand_hero, ui, update_dialog) · `src/screens/onboarding_view.py`, `src/screens/views.py` · `docs/reference/house-ui-design.md` · `DDGS/src/core/tokens.py` · `CollabShell/src/core/tokens.py` · **Date:** 2026-10-23

---

## What it does / how the app uses it

`src/core/tokens.py` is the single house scale for the app: spacing (`SPACE_*`), radii (`RADIUS_*`), type (`FONT_*`), icon sizes (`ICON_*`), component dimensions (`ICON_BACKDROP`, `DIALOG_WIDTH`, …), and opacity (`OPACITY_*`). It is imported as `core.tokens` by `core/styles.py:11`, `components/ui.py:7`, `components/app_header.py:13`, `components/update_dialog.py:12`, `screens/onboarding_view.py`, and `screens/views.py:14`; `styles.py` and `components/ui.py` are the primary consumers (spacing/radii/type flow through `glass_card`, `section_header`, `chip`, `empty_state`, `loading_state`). The file is a verbatim-ish copy of `CollabShell/src/core/tokens.py` (same spacing/type/radii/icon ladders) with a few extra component tokens, while `DDGS/src/core/tokens.py` ships a different, legibility-floored scale.

---

## Findings

### F1 · P1 · Type scale violates the 11pt legibility floor
- **Where:** `src/core/tokens.py:26-28` (`FONT_XXS = 8`, `FONT_XS = 9`, `FONT_SM = 10`) · `DDGS/src/core/tokens.py:3-4` (`# The legibility floor: no user-facing text below 11pt (Apple UI guidance).` / `FONT_XS = 11`) · consumers `src/core/styles.py:29` (section header), `src/core/styles.py:83` (chip label), `src/components/app_header.py:49,75` (version chip), `src/screens/onboarding_view.py:130` (`FONT_XS`), `src/screens/views.py:156,278,375,471,476,531,618,632` (10/11/13 pt literals).
- **What:** Three tokens sit below DDGS's declared 11pt floor and are used for user-facing text (section headers, chips, version chip, onboarding caption). CollabShell shares the same sub-11 values, but the house reference that defines a floor (`DDGS`) forbids them.
- **Evidence:** `grep -rn "FONT_XS\|FONT_XXS" src/` → `src/screens/onboarding_view.py:130` (size=FONT_XS). `DDGS/src/core/tokens.py:3-4`.
- **Fix / opportunity:** Raise `FONT_SM` to 11 (or drop `FONT_XXS`/`FONT_XS` and alias `FONT_SM = 11`), matching DDGS's ladder (`11/12/14/16/18/24/32`), and update the few call sites that rely on 8–10 pt (license body text at `views.py:632` can stay 9 only if explicitly marked non-UI/legal fine print, otherwise raise).
- **Risk if ignored:** Small text fails readability on Android, especially in light theme and for users with larger font scale.

### F2 · P2 · `HERO_ICON_SIZE` is mis-sized vs. the CollabShell reference
- **Where:** `src/core/tokens.py:49` (`HERO_ICON_SIZE = 96`) · `CollabShell/src/core/tokens.py:54` (`HERO_ICON_SIZE = 72`) · consumers `src/screens/onboarding_view.py:78-79` (used as container `width`/`height`), `src/core/styles.py:103-112` (empty state uses `EMPTY_ICON_SIZE = 96` for the backdrop, `ICON_EMPTY = 48` for the glyph).
- **What:** In CollabShell `HERO_ICON_SIZE = 72` is an *icon* glyph size; in proot it is used as a 96×96 *backdrop container* size, while the actual hero icon is `ICON_EMPTY = 48`. The name therefore disagrees with the reference and with its own usage (backdrop vs. glyph).
- **Evidence:** `onboarding_view.py:78-79` `width=tokens.HERO_ICON_SIZE, height=tokens.HERO_ICON_SIZE`; `CollabShell/src/core/tokens.py:54`.
- **Fix / opportunity:** Rename to `HERO_BACKDROP_SIZE = 96` (or `EMPTY_BACKDROP_SIZE`) and keep `HERO_ICON_SIZE = 64`/`72` for a true glyph token, matching `house-ui-design.md` §5 (empty icon 48–64, backdrop 96) and CollabShell's 72. Update `onboarding_view.py:78-79`.
- **Risk if ignored:** Future callers assume `HERO_ICON_SIZE` is a glyph size and render an oversized icon.

### F3 · P2 · `NAV_BAR_CLEARANCE = 88` is defined but never used; the value is hardcoded
- **Where:** `src/core/tokens.py:54` (`NAV_BAR_CLEARANCE = 88`) · `src/screens/views.py:378` and `src/screens/views.py:554` (`ft.Container(height=88)`).
- **What:** The token exists precisely for this purpose (house-ui-design §2 mentions `ft.Container(height=88)` nav-bar clearance) yet both call sites hardcode `88`, so the token is dead and the two cannot drift-proofed.
- **Evidence:** `grep -rn "NAV_BAR_CLEARANCE" src/` → only `src/core/tokens.py:54`.
- **Fix / opportunity:** Replace both `ft.Container(height=88)` with `ft.Container(height=tokens.NAV_BAR_CLEARANCE)` (or remove the token if unused). Same for `HERO_ICON_SIZE`/`EMPTY_ICON_SIZE` duplication.
- **Risk if ignored:** Changing the clearance requires editing two literals; the token gives false confidence.

### F4 · P2 · Twenty tokens are defined but never referenced anywhere in the app
- **Where:** `src/core/tokens.py:6-8,18,20,22,26-27,36-37,39-42,44-45,47-48,54,59-61,63` (see list) · verified by `grep -rn "tokens\.<NAME>" src/` plus direct-name grep.
- **What:** Unused: `SPACE_MICRO`, `SPACE_NANO`, `SPACE_XXS`, `RADIUS_XS`, `RADIUS_MD`, `RADIUS_XL`, `FONT_XXS`, `FONT_XXL`, `ICON_MICRO`, `ICON_SM`, `ICON_MD`, `ICON_LG`, `ICON_XL`, `ICON_XXL`, `ICON_HERO`, `ICON_BACKDROP`, `ICON_CONTAINER`, `NAV_BAR_CLEARANCE` (F3), `OPACITY_SUBTLE`, `OPACITY_STRONG`. (20 of 49 defined tokens.)
- **Evidence:** `python3` set-diff of defined vs. `tokens\.[A-Z_]+` occurrences in `src/` → 20 names with zero matches; direct-name grep also zero.
- **Fix / opportunity:** Either delete the dead tokens or start consuming them (e.g. `RADIUS_MD` for cards, `ICON_MD`/`ICON_LG` in `app_header.py`/`ui.py` where literals `14`/`18`/`20` are used) to reduce drift. Keep only tokens the house actually uses.
- **Risk if ignored:** Dead API surface hides intent; new code picks arbitrary literals instead of tokens.

### F5 · P2 · Duplicate token values create alias confusion
- **Where:** `src/core/tokens.py:6-8` (`SPACE_MICRO = 1`, `SPACE_NANO = 2`, `SPACE_XXS = 2`) · `src/core/tokens.py:42,44` (`ICON_XXL = 48`, `ICON_EMPTY = 48`) · `src/core/tokens.py:49-50` (`HERO_ICON_SIZE = 96`, `EMPTY_ICON_SIZE = 96`).
- **What:** Three pairs (and the 2/2 spacing pair) are byte-identical, so callers cannot tell which is canonical; `SPACE_NANO` and `SPACE_XXS` are indistinguishable.
- **Evidence:** `src/core/tokens.py:7-8,42,44,49-50`.
- **Fix / opportunity:** Collapse duplicates into one canonical name plus aliases (as DDGS does at `DDGS/src/core/tokens.py:34-47` with `SPACE_XXS = 2`, `SPACE_XS = SPACING_XS`, …), or remove the redundant names. Prefer DDGS's alias pattern for compatibility.
- **Risk if ignored:** Silent semantic drift when one alias is changed but not the other.

### F6 · P3 · Components hardcode values that tokens already cover (or should)
- **Where:** `src/core/styles.py:95-96` (`ft.Colors.with_opacity(0.12, tint)` / `0.05` instead of `OPACITY_MEDIUM`/`OPACITY_SUBTLE`) · `src/core/styles.py:151` (`ProgressRing(width=28, height=28)`) · `src/components/app_header.py:29` (`icon_size=18`), `:64-65,:80-81` (`ft.Padding(10,4,10,4)`, `border_radius=10`), `:125` (`ft.Padding.symmetric(horizontal=12, vertical=8)`) · `src/components/app_header.py:66,82` (`with_opacity(0.15, …)` / `0.08`) · `src/components/ui.py:30` (`size=14`), `:36` (`with_opacity(0.10, …)`) · `src/components/brand_hero.py:37-38,50,61` (`width=96,height=96`, `size=12`, `Padding.only(top=16,bottom=8)`) · `src/components/banner_ad.py:64-65,76,83-84` (`320/50`, `padding=8`, `border_radius=12`).
- **What:** Opacity literals (0.10/0.12/0.15) and spacing/radius literals (8/10/12/14/16) bypass the token layer, so the house scale is not actually the single source of truth; `OPACITY_SUBTLE=0.05` exists but `chip` re-literals 0.05.
- **Evidence:** `grep -rn "with_opacity(0\." src/` (above) and the listed lines.
- **Fix / opportunity:** Route these through existing tokens (`OPACITY_SUBTLE`, `OPACITY_LIGHT`, `OPACITY_MEDIUM`, `SPACE_*`, `RADIUS_*`, `ICON_*`); add a `SPINNER_LG = 28` token if the 28 stays (CollabShell has one at `CollabShell/src/core/tokens.py:71`).
- **Risk if ignored:** Token changes do not propagate; visual drift between screens.

### F7 · P3 · Opacity scale is narrower than both references and lacks a 0.10 step
- **Where:** `src/core/tokens.py:59-64` (`0.05/0.08/0.12/0.20/0.50`) · `CollabShell/src/core/tokens.py:84-87` (`0.02/0.05/0.1/0.12`) · house-ui-design §4 (chips tinted `with_opacity(0.08–0.14, color)`).
- **What:** The scale jumps 0.08→0.12 with no 0.10, yet consumers use 0.10 (`ui.py:36`) and 0.15 (`app_header.py:66`), outside the scale entirely. CollabShell documents 0.10; house design allows up to 0.14.
- **Evidence:** `src/core/tokens.py:60-63`; `src/components/ui.py:36`; `src/components/app_header.py:66`.
- **Fix / opportunity:** Add `OPACITY_ACCENT = 0.10` (CollabShell name) and either `OPACITY_EMPHASIS = 0.15` or clamp the update pill to `OPACITY_STRONG = 0.20`; keep the house 0.08–0.14 chip range.
- **Risk if ignored:** Ad-hoc opacity values accumulate; dark/light contrast regressions.

### F8 · P3 · Spacing scale has no 8/12 step that the house design uses
- **Where:** `src/core/tokens.py:5-15` (1,2,2,4,6,10,14,16,22,32) · `DDGS/src/core/tokens.py:12-17` (4,8,16,24,32) · `docs/reference/house-ui-design.md:51` (card padding 12–16) and `:55` (section header `FONT_XL=20`).
- **What:** The proot/CollabShell ladder skips 8 and 12, yet cards use 12–16 (`RADIUS_LG=16` + `SPACE_MD=10` padding) and several components hardcode 8/12 (F6). DDGS's ladder (4,8,16,24,32) has 8 but skips 6/10/14/22.
- **Evidence:** `src/core/tokens.py:5-15`; `DDGS/src/core/tokens.py:12-17`; `house-ui-design.md:51`.
- **Fix / opportunity:** Add `SPACE_SM2 = 8` and `SPACE_MD2 = 12` (or rename to a hybrid ladder) so card padding 12 and icon gaps 8 are expressible without literals; document which reference (CollabShell vs DDGS) wins. This is a design decision, not a code bug.
- **Risk if ignored:** Components keep hardcoding 8/12, defeating the token layer.

### F9 · UNVERIFIED · `RADIUS_PILL = 999` vs. DDGS `BORDER_RADIUS_FULL = 9999`
- **Where:** `src/core/tokens.py:23` (`RADIUS_PILL = 999`) · `DDGS/src/core/tokens.py:22` (`BORDER_RADIUS_FULL = 9999`) · `CollabShell/src/core/tokens.py:43` (`RADIUS_PILL = 999`).
- **What:** Both 999 and 9999 produce a pill in Flet (radius ≥ half the dimension), but it is unverified whether Flet clamps or whether a 999 radius on a very wide control (e.g. `DIALOG_WIDTH = 380`) still pills. CollabShell uses 999; DDGS uses 9999.
- **Evidence:** `src/core/tokens.py:23`; `DDGS/src/core/tokens.py:22`. Flet source not checked for clamping.
- **Fix / opportunity:** Standardize on one value (prefer 9999 to match DDGS's `BORDER_RADIUS_FULL`, or keep 999 for CollabShell parity) and verify against `.venv/lib/python3.14/site-packages/flet/controls/.../container.py`.
- **Risk if ignored:** Cosmetic only; both render as pills in practice (UNVERIFIED).

---

## Missed capabilities (dependency audits only)

N/A — this is a token-scale audit, not a dependency audit. No new packages proposed (D-003).

---

## Verified-good list

1. **Spacing/type/radii/icon ladders match CollabShell exactly** (`src/core/tokens.py:5-43` vs `CollabShell/src/core/tokens.py:15-53`), so the two apps share one house scale; no drift between them.
2. **Empty-state backdrop is correct:** `EMPTY_ICON_SIZE = 96` container with `ICON_EMPTY = 48` glyph and `border_radius = 48` (`src/core/styles.py:103-112`) renders a 96×96 circle with a 48px icon, matching `house-ui-design.md` §5 (backdrop 96, icon 48–64).
3. **Status dot is in range:** `STATUS_DOT = 12` with `RADIUS_PILL` (`src/core/styles.py:59-65`) matches house design §4 (10–14px pill).
4. **`DIALOG_WIDTH = 380` / `DIALOG_MIN_WIDTH = 300`** are consumed correctly by `_dialog_width` (`src/components/update_dialog.py:34-37`) with `min/max` clamping; no overflow.
5. **Opacity constants are used where it matters most:** `empty_state` uses `OPACITY_LIGHT`/`OPACITY_MEDIUM`/`OPACITY_DIM` (`src/core/styles.py:108,113,130`), and `OPACITY_DIM = 0.50` is a sensible muted-text floor.
6. **No Flet API claims in this file** — `tokens.py` is pure Python constants; nothing to verify against `.venv` beyond the consumers (verified-good above).

---

## Unverified

1. Whether Flet clamps `border_radius=999` vs `9999` on wide controls (F9) — not checked against installed source.
2. Whether raising `FONT_SM` to 11 breaks any layout that assumes 10px line height (e.g. `views.py` rows with `spacing=0`/`spacing=2`) — visual, not type-checked.
3. Whether `SPACE_MICRO = 1`/`SPACE_NANO = 2` are intentionally distinct from `SPACE_XXS = 2` (naming intent) — no docs reference; inferred.
4. Whether `ICON_BACKDROP = 44` / `ICON_CONTAINER = 56` correspond to `CollabShell`'s `ICON_CONTAINER_SM = 44` / `CARD_ICON_CONTAINER = 56` (same values, different names) — semantic mapping UNVERIFIED.