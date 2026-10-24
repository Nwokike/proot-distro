# 03 · Design System — design-parity audit

**Verdict:** MIXED
**Confidence:** high
**Scope:** Reference (CollabShell): `src/core/tokens.py`, `src/core/styles.py`, `src/core/theme.py`, `src/core/notifications.py`, `src/components/brand_header.py`, `src/components/version_dialog.py`, `src/components/session_card.py`, `src/components/credit_pill.py`, `src/screens/home/cards.py`, `src/screens/home/__init__.py`, `src/screens/onboarding/{__init__,slides}.py`, `src/screens/settings/{__init__,preferences_section,data_section,behavior_section,about_section}.py`, `src/screens/session/layout.py`, `src/screens/session/terminal_panel.py`, `src/app_shell.py`, `src/main.py` · Ours: `src/core/tokens.py`, `src/core/styles.py`, `src/core/theme.py`, `src/core/state.py`, `src/components/ui.py`, `src/components/app_header.py`, `src/components/brand_hero.py`, `src/components/update_dialog.py`, `src/components/banner_ad.py`, `src/screens/views.py`, `src/screens/onboarding_view.py`, `src/screens/terminal_view.py`, `src/app_shell.py`, `src/app_controller.py` · **Date:** 2026-10-22

Ground truth: `.venv/Lib/site-packages/` — flet **1.0.4** (`flet-1.0.4.dist-info/METADATA:4`), Python **3.14.7** (`.venv/Scripts/python.exe --version`), flet-terminal **0.4.0**.

---

## What it does / how the app uses it

Both apps are Flet 1.0.4, state-driven (`@ft.observable AppState` → `@ft.component` views), and both use a `tokens.py` (pure constants) + `theme.py` (palette + resolution) + `styles.py` (widget factories) split. CollabShell is the *reference* design system (amber/Colab brand, `Outfit` typeface, `adaptive_glass_bg()` surfaces, `ft.Colors.PRIMARY` semantic tokens). Ours is the *audit target* (Catppuccin-derived blue, `theme.primary()` explicit-hex surfaces, house `glass_card`/`section_header`/`empty_state`/`status_dot`).

The **scale** (spacing, radii, type sizes, icon sizes) is a byte-for-byte match. The **semantics** (palette, type family, uppercase/letter-spacing, icon style, surface resolution, SYSTEM handling, feedback) have drifted substantially. This report quantifies that drift token by token.

---

## Token gap table

### Color palette — surfaces, text tiers, accent, borders, glass

| Token | CollabShell value / file:line | Ours value / file:line | Verdict |
|---|---|---|---|
| Light page bg | `#FFFFFF` — `core/theme.py:12` | `#F4F4F8` — `core/theme.py:10` (`LIGHT_BG`) | **DRIFT** — different brand family (Colab amber vs terminal-native blue). Intentional per `theme.py:9` ("Terminal-native brand"). Not a defect, but a documented divergence. |
| Light surface (header/navbar) | `#F3F4F6` (`LIGHT_SURFACE`) — `core/theme.py:13`; applied `surface_container_highest` — `core/theme.py:167` | `#FFFFFF` (`LIGHT_SURFACE`) — `core/theme.py:11`; applied `surface` — `core/theme.py:110` | **DRIFT (P2)** — see F2 |
| Dark page bg | `#1E1E2E` — `core/theme.py:21` | `#121218` — `core/theme.py:17` | DRIFT (intentional) |
| Dark surface | `#16161F` — `core/theme.py:22` | `#1E1E2E` — `core/theme.py:18` | DRIFT (intentional) |
| Light text | `#1E293B` — `core/theme.py:14` | `#1E1E2E` — `core/theme.py:13` | ≈ equivalent luminance (contrast 16.40 on glass) |
| Light text-dim tier | `#475569` — `core/theme.py:15` | `#5C5C6E` — `core/theme.py:14` | ≈ equivalent (contrast 5.96 vs 7.58) |
| Dark text | `#F8F8F2` — `core/theme.py:23` | `#CDD6F4` — `core/theme.py:20` | ≈ equivalent (11.34 on glass) |
| Dark text-dim tier | `#8B8FA3` — `core/theme.py:26` | `#A6ADC8` — `core/theme.py:21` | ≈ equivalent (8.38) |
| Accent / primary (light) | `#D87607` — `core/theme.py:18` | `#1E66F5` — `core/theme.py:15` | DRIFT (intentional) |
| Accent / primary (dark) | `#E58514` — `core/theme.py:24` | `#89B4FA` — `core/theme.py:22` | DRIFT (intentional) |
| `primary_container` | `#BA6200` — `core/theme.py:17`, set at `theme.py:155` | **unset** — `core/theme.py:99-106` | **GAP (P2)** — see F3 |
| `secondary`/`tertiary` + containers | all four set — `theme.py:132-136` | **all unset** — `core/theme.py:99-106` | **GAP (P2)** — see F3 |
| `on_primary`/`on_secondary`/`on_tertiary` | set — `theme.py:141-143` | **unset** — `core/theme.py:99-106` | **GAP (P2)** — see F3 |
| `outline` | `#E2E8F0` (light) / `#2D2D3F` (dark) — `theme.py:34-35`, applied `theme.py:145,168` | `on_surface_variant_c` (= text-dim) — `core/theme.py:105` | **GAP (P2)** — outline is a *border* role, not a *text* role |
| `error` in scheme | `#EF5350` — `theme.py:32`, applied `theme.py:140,163` | `#F38BA8` (the `WARN` pink) — `core/theme.py:31`, applied `core/theme.py:104` | **GAP (P2)** — see F4 |
| Light glass card bg | `#F1F5F9` — `core/theme.py:60` | `#FFFFFF` — `core/theme.py:25` | **GAP (P1)** — see F1 |
| Light glass border | `#E2E8F0` — `core/theme.py:61` | `#E4E4EA` — `core/theme.py:26` | ≈ equivalent (contrast 1.27 on white vs Collab's 1.16 on `#F1F5F9`) |
| Dark glass card bg | `#26263A` — `core/theme.py:62` | `#1E1E2E` — `core/theme.py:27` | **GAP (P1)** — see F1 |
| Dark glass border | `#2D2D3F` — `core/theme.py:63` | `#313244` — `core/theme.py:28` | ≈ equivalent |
| Divider | `#E2E8F0` / `#2D2D3F` — `theme.py:34-35` | folded into `outline` — `core/theme.py:105` | GAP (P2), see F3 |
| Success | `#4CAF50` — `theme.py:30` | `#A6E3A1` (`OK`) — `core/theme.py:32` | **GAP (P1)** — see F5 |
| Warning | `#FF9800` — `theme.py:31` | `#F38BA8` (`WARN`) — `core/theme.py:31` | **GAP (P1)** — see F5 |
| Error (semantic) | `#EF5350` — `theme.py:32` | **no dedicated error color**; `WARN` doubles as error | **GAP (P1)** — see F5 |
| Info | `#42A5F5` — `theme.py:33` | none | GAP (P3) — no info surface today |
| Hardware badge set | CPU/GPU/TPU/FREE/PAID — `theme.py:38-42` | none (no hardware concept) | N/A — domain difference |
| Terminal palette | 8 tokens — `theme.py:45-52` | `TERMINAL_BG = "#0D0D0D"` — `core/theme.py:33` | **DRIFT (P2)** — see F6 |

### Typography scale

| Token | CollabShell value / file:line | Ours value / file:line | Verdict |
|---|---|---|---|
| `FONT_XXS` … `FONT_HERO` | 8/9/10/12/14/18/22/30 — `core/tokens.py:28-35` | 8/9/10/12/14/18/22/30 — `core/tokens.py:26-33` | **PARITY** — exact match, all 8 sizes |
| Font family (app) | `"Outfit"` — `core/theme.py:147,170`; registered `page.fonts` — `main.py:163-170` | **none** — `core/theme.py:108-124` builds `ft.Theme` with no `font_family`; `src/assets/` has only `icon.png`/`icon.svg` | **GAP (P1)** — see F7 |
| Mono font (terminal/code) | `"RobotoMono"` — `components/ansi_parser.py:90,189`, `screens/session/script_view.py:178` | `"JetBrains Mono"` — `screens/terminal_view.py:74` | DRIFT (P3) — different mono, both bundled |
| Section header casing | **not uppercased** — `core/styles.py:12-27` takes `text` verbatim | `.upper()` applied — `core/styles.py:28` | **GAP (P2)** — see F8 |
| Section header weight | `W_700` — `core/styles.py:17` | `BOLD` (= `w700`) — `core/styles.py:30` | ≈ equivalent (`.venv/.../types.py:175-177`) |
| Section header letter-spacing | `1` — `core/styles.py:19` | `1` — `core/styles.py:32` | **PARITY** |
| Section header color | `ft.Colors.PRIMARY` (theme-resolved) — `core/styles.py:18` | `theme.primary()` (explicit hex) — `core/styles.py:31` | ≈ equivalent, different mechanism (see F9) |
| Off-scale sizes | `size=13` in 4 places — `components/version_dialog.py:145,147,170,171`; `size=11` ×2 — `app_shell.py:479,507` | `size=11`/`12`/`13` in 60 places — e.g. `screens/views.py:112,277,282` | **GAP (P2)** — see F10 |

### Spacing, padding, radii, borders, elevation

| Token | CollabShell value / file:line | Ours value / file:line | Verdict |
|---|---|---|---|
| `SPACE_MICRO…SPACE_XXXL` | 1/2/2/4/6/10/14/16/22/32 — `core/tokens.py:16-25` | 1/2/2/4/6/10/14/16/22/32 — `core/tokens.py:6-15` | **PARITY** — exact match, all 10 steps |
| `SPACE_NONE` | `0` — `core/tokens.py:15` | implicit (no constant) | GAP (P3) |
| `RADIUS_XS…RADIUS_PILL` | 4/8/12/16/24/999 — `core/tokens.py:38-43` | 4/8/12/16/24/999 — `core/tokens.py:18-23` | **PARITY** — exact match |
| `DIVIDER_THICKNESS` | `1` — `core/tokens.py:75` | implicit literal `1` — `core/styles.py:21` | ≈ equivalent (P3) |
| `DIALOG_WIDTH` / `DIALOG_WIDTH_LG` | `300` / `400` — `core/tokens.py:65-66` | `380` / `300` (min) — `core/tokens.py:56-57` | **GAP (P2)** — see F11 |
| `WINDOW_MIN_WIDTH` / `_HEIGHT` | `360` / `600` — `core/tokens.py:77-78` | **unset** — no `page.window` write anywhere (`grep` over `src/` returns nothing) | **GAP (P2)** — see F12 |
| `HEIGHT_SEPARATOR` | `16` — `core/tokens.py:74` | none | GAP (P3) |
| `SPINNER_SM…XL` | 20/24/28/32 — `core/tokens.py:69-72` | hardcoded `28` — `core/styles.py:151` | GAP (P3) |
| Elevation / shadow | none (flat + 1px hairline) — `core/styles.py:89` | none — `core/styles.py:21` | **PARITY** — both flat; Flet `BoxShadow` exists (`.venv/.../controls/material/box_shadow.py`) but neither uses it |

### Icon sizes and opacity

| Token | CollabShell value / file:line | Ours value / file:line | Verdict |
|---|---|---|---|
| `ICON_MICRO…ICON_XXL` | 12/14/16/20/24/32/48 — `core/tokens.py:46-52` | 12/14/16/20/24/32/48 — `core/tokens.py:36-42` | **PARITY** — exact match, all 7 |
| Hero icon | `ICON_XXXL = 80`, `HERO_ICON_SIZE = 72` — `core/tokens.py:53-54` | `ICON_HERO = 64` (unused), `HERO_ICON_SIZE = 96` — `core/tokens.py:43,49` | **GAP (P2)** — see F13 |
| Empty-state icon | n/a (no shared factory) | `ICON_EMPTY = 48`, `EMPTY_ICON_SIZE = 96` — `core/tokens.py:44,50` | ≈ Sherlock house pattern (96 backdrop), matches `docs/reference/house-ui-design.md:66` |
| Status dot | `ICON_SM - 6` = **10** — `core/styles.py:217-218` | `STATUS_DOT = 12` — `core/tokens.py:51` | GAP (P3) — both in the 10–14 house band (`house-ui-design.md:60`) |
| `OPACITY_SUBTLE` | `0.02` — `core/tokens.py:84` | `0.05` — `core/tokens.py:60` | GAP (P3) |
| `OPACITY_CONTAINER` / `OPACITY_ACCENT` | `0.05` / `0.10` — `core/tokens.py:85-86` | `OPACITY_LIGHT = 0.08` / `OPACITY_MEDIUM = 0.12` — `core/tokens.py:61-62` | ≈ equivalent |
| `OPACITY_CARD` | `0.12` — `core/tokens.py:87` | `OPACITY_MEDIUM = 0.12` — `core/tokens.py:62` | **PARITY** (value) |
| `OPACITY_STRONG` | n/a | `0.20` — `core/tokens.py:63` | GAP (P3), unused |
| Chip padding | `SPACE_SM, SPACE_XXS` (6, 2) — `core/styles.py:182-184` | `CHIP_PADDING_H = 10`, `CHIP_PADDING_V = 4` — `core/tokens.py:52-53` | DRIFT (P3) |

### Unused tokens in ours (dead system surface)

`ICON_BACKDROP` (`core/tokens.py:47`), `ICON_HERO` (`:43`), `ICON_XXL`/`ICON_XL`/`ICON_MD` (`:42,41,39`), `NAV_BAR_CLEARANCE` (`:54`), `OPACITY_SUBTLE` (`:60`), `OPACITY_STRONG` (`:63`), `SPACE_MICRO` (`:6`), `SPACE_NANO` (`:7`) — all **0 references** in `src/` (verified by grep). `styles.chip` (`core/styles.py:69`) and `styles.loading_state` (`core/styles.py:146`) are also **0 call sites**. Contrast: CollabShell's `SPACE_NANO` and `OPACITY_ACCENT` *are* used (`screens/home/cards.py:73`, `screens/session/layout.py:140`).

---

## Component pattern table

| Pattern | CollabShell file:line | Ours file:line | Verdict |
|---|---|---|---|
| Glass card (hairline + radius) | `core/styles.py:76-91` (bg `adaptive_glass_bg()`, border `adaptive_glass_border()`, `RADIUS_LG`, pad 14/10) | `core/styles.py:14-22` (bg `theme.glass_bg()`, border `theme.glass_border()`, `RADIUS_LG`, pad 10) | ≈ shape parity; **bg value GAP (F1)**; padding 10 vs 14/10 |
| Section header | `core/styles.py:12-27` | `core/styles.py:25-56` | ≈ parity; **uppercase GAP (F8)** |
| Section header w/ right action | inline — `screens/home/__init__.py:371-384` (title + refresh IconButton) | `core/styles.py:44-56` (label + action, `SPACE_BETWEEN`) | **PARITY** — ours has the better abstraction, but **no call site passes `action`** (`grep` → 0) |
| Status dot | `core/styles.py:212-221` (10px, `RADIUS_PILL`) | `core/styles.py:59-67` (12px, `RADIUS_PILL`) | ≈ parity (P3) |
| Empty state (tinted circle + title + msg) | none shared (per-screen) | `core/styles.py:101-143` | **PARITY (ours)** — matches `house-ui-design.md:66` (Sherlock 96×96 backdrop) |
| Loading state | `ProgressRing` 28 — `house-ui-design.md:67` | `core/styles.py:146-160` (`ProgressRing` 28) | **PARITY** — but no call site |
| Pill badge (colored, white text) | `core/styles.py:161-185` (`RADIUS_XS`, `FONT_XXS` W_700 white) | n/a | N/A — no hardware badges |
| Status chip (tinted pill) | `core/styles.py:188-209` | `core/styles.py:69-98` (`chip()`, unused) | ≈ pattern exists, unexercised |
| Version chip (header) | `app_shell.py:463-521` | `components/app_header.py:35-86` | ≈ parity — identical padding `(10,4,10,4)`, radius `10`, `ink=True`; **font size 11 vs `FONT_SM`=10** |
| Update pill (bordered, dot) | `app_shell.py:463-500` (`with_opacity(0.15)`, `Border.all(1.5)`) | `components/app_header.py:42-71` (identical values) | **PARITY** — near byte-identical |
| Header bar (title left, actions right) | `app_shell.py:522-548` (pad `SPACE_LG/SM/MD/SM`, `bgcolor=ft.Colors.SURFACE`) | `components/app_header.py:98-126` (pad `12/8` literal, `bgcolor=theme.surface()`) | ≈ parity; **pad literals GAP (F10)** |
| Theme button | `app_shell.py:300-330` (`icon_size=ICON_SM`=16) | `components/app_header.py:18-32` (`icon_size=18` literal) | DRIFT (P3) — 18 vs 16 |
| Brand hero (icon + tagline) | `components/brand_header.py:6-42` (80px icon, tagline `FONT_SM`) | `components/brand_hero.py:32-62` (96px literal, tagline `size=12` literal) | **GAP (P2)** — see F13 |
| Update/version dialog | `components/version_dialog.py:121-202` (icon 24, title `BOLD` + `font_family="Outfit"`, actions `END`) | `components/update_dialog.py:40-120` (icon 20, title `FONT_LG`, no `actions_alignment`) | ≈ parity; **font family GAP (F7)** |
| Dialog action buttons | `version_dialog.py:76-118` (`FilledButton` + `OutlinedButton` + `TextButton`, all `font_family="Outfit"`) | `update_dialog.py:101-146` (`TextButton` + `FilledButton` in up-to-date mode — **order inverted** vs CollabShell's `OutlinedButton`+`TextButton`) | GAP (P3) — action order/weight differs |
| Notification (floating snackbar) | `core/notifications.py:14-51` — `behavior=FLOATING`, explicit `bgcolor`, `show_close_icon=True`, `duration=3000` | `app_controller.py:289-291` — `page.show_dialog(ft.SnackBar(ft.Text(message)))` | **GAP (P1)** — see F14 |
| Onboarding deck | `screens/onboarding/__init__.py:23-225` (3 slides, `SafeArea`, nav row with Back + dots + Next) | `screens/onboarding_view.py:37-141` (3 slides, no `SafeArea`, dots row + single button) | ≈ parity; **no Back button, no SafeArea (F12)** |
| Onboarding dot indicator | `screens/onboarding/__init__.py:161-172` (10/6 × 6px, **`animate=Animation(200, EASE_IN_OUT)`**) | `screens/onboarding_view.py:108-113` (24/8 × 8px, **no animation**) | **GAP (P3)** — see F15 |
| Onboarding slide content | `screens/onboarding/slides.py:12-42` (`feature_row`: 56px icon badge + title + subtitle) | `screens/onboarding_view.py:15-34` (icon field present but **never read** — slide 1 has `"icon": None`; only the brand image renders) | **GAP (P3)** — per-slide icon is dead data |
| Onboarding swipe | `screens/onboarding/__init__.py:134-139` (velocity ±200) | `screens/onboarding_view.py:55-60` (velocity ±200) | **PARITY** |
| Onboarding CTA | `slides.py:210-229` (width 300, height 46, `W_600` label) | `screens/onboarding_view.py:120-125` (width 220, height 52, default label) | DRIFT (P3) |
| Settings section composition | `screens/settings/__init__.py:80-109` (13 sections, per-section try/except → error card) | `screens/views.py:429-559` (4 sections, no try/except) | ≈ parity for a 4-section app; **error-card isolation GAP (P2)** — see F16 |
| Settings appearance selector | `screens/settings/preferences_section.py:26-66` (3 icon+label cards, `animate=Animation(150, EASE_OUT)`, `expand=True`) | `screens/views.py:441-452` (one text row + theme button) | **GAP (P2)** — see F17 |
| Settings glass card | `screens/settings/data_section.py:71-112` (`glass_card` + `Margin(SPACE_LG, SPACE_XS, …)`) | `screens/views.py:433-456` (`card()` with **no margin**) | GAP (P2) — cards run edge-to-edge |
| Setting tile (icon + title + tip) | `core/styles.py:30-73` + `screens/settings/data_section.py:74-104` | none | GAP (P3) |
| Terminal toolbar button style | `screens/session/terminal_panel.py:68-73` (`ButtonStyle(padding=2, visual_density=COMPACT)`) | none — `grep` for `VisualDensity\|ButtonStyle` over `src/` returns nothing | GAP (P3) |
| Terminal theme follows app | `screens/session/terminal_panel.py:79` → `"Colab Light"` / `"JetBrains Dark"` | `screens/terminal_view.py:34` → `"Colab Light"` / `"JetBrains Dark"` | **PARITY** — exact |
| Terminal replay on mount | `screens/session/terminal_panel.py` (scrollback replay) | `screens/terminal_view.py:96-98` (`entry.replay(mt.send_bytes)`) | **PARITY** |
| Terminal keyboard inset | `screens/session/terminal_panel.py` | `screens/terminal_view.py:83-94, 226-227` | **PARITY** |
| Banner ad (mobile-only, glass wrap) | `core/styles.py:108-158` | `components/banner_ad.py:44-79` | ≈ parity (ours pools instances) |
| Icon style (rounded family) | 257/273 = **94%** `_ROUNDED` | 11/29 = **38%** `_ROUNDED` | **GAP (P2)** — see F18 |
| `SafeArea` wrapper | `app_shell.py:571-579`, `334`, `381`, `429` | none — `grep` over `src/` returns nothing | **GAP (P2)** — see F12 |
| Responsive / max-width content | none (no breakpoints in either app) | none | **PARITY** — both are phone-first full-bleed; see "Responsive behavior" below |
| `ft.use_effect` theme repaint | `screens/session/terminal_panel.py:810` | `screens/terminal_view.py:122` | **PARITY** |

---

## Findings

### F1 · P1 · Glass card surface equals the header/navbar surface in dark mode — cards lose their elevation

- **Where:** ours `core/theme.py:18,27` (`DARK_SURFACE = DARK_GLASS_BG = "#1E1E2E"`), `core/theme.py:20` (`DARK_TEXT = "#CDD6F4"`), `app_shell.py:65,72` (`bgcolor=theme.bg()` / `theme.surface()`), `core/styles.py:19-21`
- **What:** In dark mode the page body background is `#121218`, the header bar and NavigationBar are `#1E1E2E` (`app_header.py:124`, `app_shell.py:72`), and every glass card is *also* `#1E1E2E` (`core/styles.py:20` → `theme.glass_bg()`). CollabShell deliberately separates these: card `#26263A` on body `#1E1E2E` on header `#16161F`. The CollabShell comment at `core/theme.py:54-59` says exactly why — *"Explicit per-mode values so cards never rely on M3 tokens the custom Colab ColorScheme doesn't set (surface_container_low would fall back to the Material default and wash out). These replace the old with_opacity(0.05, ON_SURFACE) pattern that read as near-invisible in light mode."*
- **Evidence:** `core/theme.py:18,27` → both `DARK_SURFACE` and `DARK_GLASS_BG` are the literal `#1E1E2E`. `core/styles.py:20` calls `theme.glass_bg()`. Contrast of card vs. body: `#1E1E2E` on `#121218` = **1.30**; the card is separated from the body only by a `#313244` 1px hairline (contrast 1.30). In CollabShell the same pair is `#26263A` on `#1E1E2E` = **1.51** with a `#2D2D3F` hairline.
- **Fix / opportunity:** In `core/theme.py`, split the two roles: keep `DARK_SURFACE = "#1E1E2E"` for chrome, set `DARK_GLASS_BG = "#26263A"` (CollabShell's exact value) so cards read as raised, and set `DARK_GLASS_BORDER = "#2D2D3F"`. In light mode keep `LIGHT_GLASS_BG = "#FFFFFF"` but note `LIGHT_BG = "#F4F4F8"` already provides the separation.
- **Risk if ignored:** In dark mode every card is a flat block separated only by a hairline; the "glass" surface language does not exist. This is the single largest visual divergence from the reference.

### F2 · P1 · Light-mode `surface` and `surface_alt` invert the reference hierarchy

- **Where:** ours `core/theme.py:11-12` (`LIGHT_SURFACE = "#FFFFFF"`, `LIGHT_SURFACE_ALT = "#EDEDF2"`), `core/theme.py:110` (scheme `surface=LIGHT_SURFACE`), `app_header.py:124` (`bgcolor=theme.surface()`), `app_shell.py:72` (`bgcolor=theme.surface()`), `views.py:88,337,502` (`BorderSide(1, theme.surface_alt())`)
- **What:** In light mode the header bar and the NavigationBar are `#FFFFFF` — *brighter* than the `#F4F4F8` page body — and the glass cards are also `#FFFFFF`. So the chrome and the cards are the same color, and the body is the odd one out. CollabShell inverts this: body `#FFFFFF`, chrome `#F3F4F6`, card `#F1F5F9` — chrome recedes, cards sit between chrome and body.
- **Evidence:** `app_header.py:124` `bgcolor=theme.surface()` → `#FFFFFF`; `core/styles.py:20` `theme.glass_bg()` → `#FFFFFF`. The only difference between the header band and a card is a 1px `#E4E4EA` rule (contrast 1.27 on white).
- **Fix / opportunity:** In `core/theme.py`, set `LIGHT_SURFACE = "#EDEDF2"` (the current `LIGHT_SURFACE_ALT`) so the chrome recedes, and rename/re-point `surface_alt()` for input borders (or add `LIGHT_BORDER = "#D8D8E0"` for the `OutlineInputBorder` at `views.py:88,337,502`, whose current `#EDEDF2` border has contrast **1.17** against the `#FFFFFF` card — effectively invisible).
- **Risk if ignored:** Light mode reads as a flat white page: no chrome band, no card elevation, and text-field borders that are invisible at arm's length.

### F3 · P2 · ColorScheme sets only 6 of 46 roles; `primary_container`, `secondary`, `tertiary` and `on_primary` are unset

- **Where:** ours `core/theme.py:98-106` (the `scheme()` factory) vs CollabShell `core/theme.py:129-171`
- **What:** `ft.ColorScheme` has **46** fields (verified: `dataclasses.fields(ft.ColorScheme)` → 46). Ours sets 6: `primary`, `surface`, `on_surface`, `on_surface_variant`, `error`, `outline`. CollabShell sets 15. The unset roles fall back to Flutter's Material defaults, so any control that reads `primary_container` (FilledButton's container, `Chip`, `MenuAnchor`) renders in a color that belongs to neither the light nor the dark house palette.
- **Evidence:** `.venv/.../controls/theme.py:145` `class ColorScheme` (decorated `@value`); `.venv/.../controls/theme.py:154` `primary: Optional[ColorValue] = None`. Probe output: `OUR light scheme set fields: {'primary','error','surface','on_surface','on_surface_variant','outline'}` vs `COLLAB light scheme set fields: 15 roles`.
- **Fix / opportunity:** In `core/theme.py:98-106`, extend `scheme()` to also take and set `primary_container`, `secondary`, `secondary_container`, `tertiary`, `tertiary_container`, `on_primary`, `on_secondary`, `on_tertiary`, `surface_container_highest`, `outline_variant`, `error_container`, `on_error`. Use the house palette: light `primary_container = "#1A4FC4"` (darker blue), dark `primary_container = "#1E3A6B"`; `on_primary = "#FFFFFF"` in light, `on_primary = "#121218"` in dark.
- **Risk if ignored:** Buttons and menus that read the container roles show off-palette Material colors, which is exactly the "system drift" this audit exists to catch.

### F4 · P2 · `error` in the ColorScheme is the pink warning color

- **Where:** ours `core/theme.py:31` (`WARN = "#F38BA8"`), `core/theme.py:104` (`error=AppColors.WARN`)
- **What:** The scheme's `error` role — which drives Flet's built-in validation text and error input borders — is set to the Catppuccin *pink* `#F38BA8`, which in this palette is already the *warning* color. CollabShell separates them: `ERROR = "#EF5350"` (red) vs `WARNING = "#FF9800"` (orange).
- **Evidence:** `core/theme.py:31` defines only `WARN`; `core/theme.py:104` `error=AppColors.WARN`. Contrast of `#F38BA8` on the light glass `#FFFFFF` is **2.32** — below WCAG AA (4.5) for body text. CollabShell's `ERROR #EF5350` on white is **3.49**, also low but semantically correct and used only on icons/labels.
- **Fix / opportunity:** Add `ERROR = "#F20D5E"`-class dark red to `AppColors` in `core/theme.py` (Catppuccin Mocha red is `#F38BA8` for the *surface* red — the text-tier red is `#F38BA8` too, so a deeper `#E64553` is the right pick), map `error=AppColors.ERROR`, and keep `WARN` for warnings. Add `success` handling for `ft.Switch`/checkmarks.
- **Risk if ignored:** An input in an error state shows pink, which this app's own UI reads as "warning"; users cannot distinguish "invalid" from "caution".

### F5 · P1 · Semantic colors are theme-independent — the light-mode text tiers fail contrast

- **Where:** ours `core/theme.py:30-32` (`ACCENT = "#89B4FA"`, `WARN = "#F38BA8"`, `OK = "#A6E3A1"`) — a single fixed set for both modes; used at `core/styles.py:65` (`status_dot` bgcolor), `components/ui.py:30-31,36`, `screens/views.py:361,375,472`, `screens/terminal_view.py:148,204,256,322`
- **What:** `OK`, `WARN`, `ACCENT` are Catppuccin *dark-mode* pastels and are used unchanged on the light background. Contrast on the light glass `#FFFFFF`: `OK #A6E3A1` = **1.49**, `WARN #F38BA8` = **2.32**, `ACCENT #89B4FA` = **2.11**. All are far below WCAG AA 4.5:1 for the 9–12 px text they are applied to (`screens/terminal_view.py:148` renders `"live"` at `size=10`).
- **Evidence:** `core/theme.py:32` `OK = "#A6E3A1"`; `core/styles.py:65` `bgcolor=theme.AppColors.OK if is_running else theme.text_dim()`; `screens/terminal_view.py:148` `color=theme.AppColors.OK if entry.ready else theme.text_dim()` at `size=10`. Computed ratios: `OK`/white **1.49**, `WARN`/white **2.32**, `ACCENT`/white **2.11**.
- **Fix / opportunity:** Make the semantic colors mode-aware, mirroring CollabShell's `AppColors` (`core/theme.py:30-42`) plus the adaptive-resolution pattern (`core/theme.py:112-123`). In `core/theme.py`, add `LIGHT_OK = "#2E7D32"`, `LIGHT_WARN = "#B26A00"`, `LIGHT_ACCENT = "#1A4FC4"` and `DARK_OK = "#A6E3A1"`, `DARK_WARN = "#F38BA8"`, `DARK_ACCENT = "#89B4FA"`, then expose `theme.ok()`, `theme.warn()`, `theme.accent()` alongside the existing `theme.primary()`/`theme.text_dim()` and route the 12 call sites through them. CollabShell's equivalent light-mode contrast is *also* low (`SUCCESS #4CAF50` on white = 2.78), so this is a case where the reference should be improved rather than copied — the house rule to adopt is "adaptive, not fixed".
- **Risk if ignored:** In light mode, the live-session indicator, the error/warning notes, and the install-progress line are effectively invisible. This is owner-visible.

### F6 · P2 · Terminal background is a fixed `#0D0D0D`, ignoring the app theme

- **Where:** ours `core/theme.py:33` (`TERMINAL_BG = "#0D0D0D"`); CollabShell `core/theme.py:45-52` (8 terminal tokens, incl. `TERMINAL_BG = "#0D0D0A"` light-side and `LOG_TERMINAL_BG = "#0D0D0D"`)
- **What:** CollabShell keeps the terminal's own palette separate from the app surface but *does* switch the terminal theme with the app mode (`"Colab Light"` vs `"JetBrains Dark"`). Ours does switch the flet_terminal theme (`screens/terminal_view.py:33-34`) — that part is parity — but `TERMINAL_BG` is defined and never used (0 call sites, verified by grep), so the token is dead and the app has no declared terminal-surface color.
- **Fix / opportunity:** Either delete `TERMINAL_BG` from `core/theme.py:33` or bind it: use it for the quick-command strip / terminal chrome container in `screens/terminal_view.py:169-175` so the terminal panel's surroundings match the active flet_terminal theme.
- **Risk if ignored:** Low (dead token), but it signals an unfinished terminal-surface decision.

### F7 · P1 · No font family — the app falls back to the platform default instead of the house "Outfit"

- **Where:** ours `core/theme.py:108-124` (`build_theme()` constructs `ft.Theme(color_scheme=…)` with **no** `font_family`), `core/theme.py:95-124`; no `page.fonts` assignment anywhere in `src/` (grep over `src/` for `font_family` returns exactly one hit, `screens/terminal_view.py:74` = `"JetBrains Mono"`). Reference: CollabShell `core/theme.py:147,170` (`font_family="Outfit"` in both themes) + `main.py:163-170` (`page.fonts = {"Outfit": "assets/fonts/Outfit-Regular.ttf", "RobotoMono": …}` + `page.theme.font_family = "Outfit"`).
- **What:** `ft.Theme.font_family` defaults to `None` (`.venv/.../controls/theme.py:3293-3296`), which means "use the platform default". Every `ft.Text` in the app therefore renders in Roboto (Android) / SF (iOS), not the house typeface. The house reference document records this as the shared standard: `docs/reference/house-ui-design.md:38-40` — *"In screens: `ft.Icon` with rounded Material names, sized from tokens … Brand SVGs … tinted `color`"*, and the whole reference stack is "Outfit".
- **Evidence:** `core/theme.py:108-115` — `light = ft.Theme(color_scheme=scheme(...))`, no `font_family`. `src/assets/` contains only `icon.png` and `icon.svg` (verified by `ls -R src/assets`) — **no `fonts/` directory**, so there is nothing to register even if `font_family` were set. CollabShell ships `src/assets/fonts/{Outfit-Regular,Outfit-Bold,Outfit-Light,Outfit-Medium,Outfit-SemiBold,RobotoMono-Regular,RobotoMono-Bold}.ttf` (verified by `ls`).
- **Fix / opportunity:** Either (a) adopt Outfit: add `src/assets/fonts/Outfit-{Regular,Bold,Medium,SemiBold}.ttf` from the CollabShell tree, set `page.fonts = {"Outfit": "assets/fonts/Outfit-Regular.ttf", …}` in `src/app_controller.py:init()` (before `theme.build_theme()` at `app_controller.py:53`), and set `font_family="Outfit"` on both themes in `core/theme.py:108-124`; or (b) consciously decide to stay on the platform font and record that as a house deviation in `docs/reference/house-ui-design.md`. Option (a) is the parity route; the fonts are already vendored in the sibling repo and are SIL Open Font License.
- **Risk if ignored:** The app does not match the reference's typography at all — the single most visible design-system divergence. **Note the dependency freeze (D-003) is not violated: this is a static asset, not a new package.**

### F8 · P2 · Section headers are uppercased in ours but not in the reference

- **Where:** ours `core/styles.py:28` (`title.upper()`); reference `core/styles.py:12-27` (text passed verbatim)
- **What:** CollabShell's `section_header(text)` renders the string as given; its callers pass already-uppercase strings (`screens/settings/preferences_section.py:70` `section_header("APPEARANCE")`, `data_section.py:70` `section_header("DATA & STORAGE")`, `about_section.py:51` `section_header("ABOUT")`). Ours applies `.upper()` *inside* the factory, so the capitalization is a property of the component rather than of the content. The rendered output is identical for the reference's own call sites.
- **Evidence:** `core/styles.py:28` `title.upper()`; `core/styles.py:31` `color=theme.primary()`; `core/styles.py:32` `style=ft.TextStyle(letter_spacing=1)`. Our call sites (`views.py:314,432,457,491,517`) pass mixed case ("Install", "Appearance"), and `.upper()` normalizes them.
- **Fix / opportunity:** Functionally equivalent — no user-visible defect. For architectural cleanliness, move the casing to the call sites (matching CollabShell's contract) so the factory stays a pure renderer and a future non-uppercase label (e.g. "Docker Hub") is not silently re-cased. Low priority.
- **Risk if ignored:** None user-visible. Recorded so the synthesis does not "fix" a non-bug.

### F9 · P2 · Two competing sources of truth for the accent color

- **Where:** ours `core/styles.py:31` (`theme.primary()`), `core/theme.py:91-92` (`primary()` reads `AppColors.LIGHT_PRIMARY`/`DARK_PRIMARY` directly); reference `core/theme.py:174-192` (`brand_color(page)` reads the color back **out of the live theme's** `color_scheme.primary`, with `AppColors.DARK_PRIMARY` only as the no-page fallback) and `core/styles.py:18` (`ft.Colors.PRIMARY` — a *scheme-resolved* token).
- **What:** CollabShell's `brand_color` docstring states the rule explicitly: *"`AppColors` has no plain `PRIMARY` … the theme is what actually decides which one is current — so anything that wants 'brand' must read it back rather than hard-code a hex or fall back to `ft.Colors.PRIMARY` (a Material blue that is not our brand)."* Ours bypasses the live theme and re-derives from `AppColors`, which means the `ft.Theme` object and the `theme.primary()` helper can disagree if either is edited.
- **Evidence:** `core/theme.py:91-92` `return AppColors.LIGHT_PRIMARY if is_light_theme() else AppColors.DARK_PRIMARY`. `core/theme.py:110,119` set `primary=` to the same constants, so they agree *today* — the risk is divergence tomorrow.
- **Fix / opportunity:** In `core/theme.py`, add a `brand_color()` that reads `page.theme.color_scheme.primary` (mirroring `CollabShell/src/core/theme.py:174-192`) and have `primary()` delegate to it, with the `DARK_PRIMARY` fallback. Single source of truth, no behavior change.
- **Risk if ignored:** Latent. A future palette edit to one path silently desyncs the accent from the theme.

### F10 · P2 · Sixty hardcoded font sizes and literal spacing/padding bypass the token scale

- **Where:** ours `screens/views.py:85,107,112,119,153,156,193,211,212,243,263,277,282,298,334,344,361,375,406,464,471,484,499,509,522,…` (60 `size=<int>` hits total), `views.py:123,158,225,286,347,350,365,379,488,514,550,556,644,691` (literal `spacing=`), `components/app_header.py:61,64,80` (`spacing=6`, `Padding(10,4,10,4)`, `border_radius=10`), `components/brand_hero.py:37-38,51` (literal `96`, `size=12`), `components/ui.py:30-31,56` (literal `14`), `screens/terminal_view.py:138,143,144,147,152,157,188,256,295` (literal `18`, `16`, `13`, `10`)
- **What:** The token scale is fully populated and matches the reference exactly, but the screens largely do not use it: `size=11` and `size=13` are not on the scale at all (the scale is 8/9/10/12/14/18/22/30), and the reference itself only uses `11`/`13` in 6 places (`components/version_dialog.py:145,147,170,171`; `app_shell.py:479,507`) — ours uses them 60 times.
- **Evidence:** grep counts: ours `size=[0-9]` → **60**; CollabShell → **6** (`size=11` ×2, `size=12` ×2, `size=13` ×4). Ours `spacing=[0-9]` → 24 literals across `src/`; the reference has 58 literals but every one of them lands *on* the scale (1/2/4/6/10/14/16/22/32).
- **Fix / opportunity:** Replace the literal sizes with the nearest scale token (`11 → FONT_SM` (10) or `FONT_MD` (12); `13 → FONT_MD` (12) or `FONT_LG` (14)) across `src/screens/views.py`, `src/screens/terminal_view.py`, `src/components/app_header.py`, `src/components/brand_hero.py`. Keep the reference's own exceptions only where the reference has them (`version_dialog.py` `size=13`).
- **Risk if ignored:** The scale is decorative — it cannot enforce anything, so a later token change will not propagate. This is the mechanism behind F13 and F18.

### F11 · P2 · Dialog width model differs: fixed 380 vs the reference's 300/400 pair with a 360 content column

- **Where:** ours `core/tokens.py:56-57` (`DIALOG_WIDTH = 380`, `DIALOG_MIN_WIDTH = 300`), `components/update_dialog.py:29-37` (`_dialog_width` clamps to `page.width - 48`); reference `core/tokens.py:65-67` (`DIALOG_WIDTH = 300`, `DIALOG_WIDTH_LG = 400`, `DIALOG_HEIGHT_LG = 480`), `components/version_dialog.py:155,179` (markdown column `width=360`)
- **What:** Ours is *better* than the reference on responsiveness (it actually measures `page.width` — verified that `ft.Page` has `width`/`height` fields), but it ships one width for both dialog modes. The reference distinguishes a narrow 300 dialog from a 400 large one, and its markdown body is a fixed 360 column.
- **Evidence:** `components/update_dialog.py:33` `except TypeError, ValueError:` — valid only under Python ≥ 3.14's PEP 758 (verified: `python.exe --version` → 3.14.7; `py_compile` → exit 0). The `.py-version` file pins `3.14` (verified: `.python-version` = `3.14`), so this is fine, but it is version-sensitive code — a reader on 3.13 would see a syntax error.
- **Fix / opportunity:** Keep the responsive clamp, but adopt the reference's two-tier idea: `DIALOG_WIDTH = 300` for the up-to-date mode and `DIALOG_WIDTH_LG = 400` for the release-notes mode, and set the markdown column to the clamped width (already done at `update_dialog.py:73,94`).
- **Risk if ignored:** Minor. The release-notes dialog at 380 on a 360 dp phone clamps to 312 — the markdown is legible but cramped.

### F12 · P2 · No `SafeArea`, no window minimum size, and `page.padding`/`page.spacing` never set

- **Where:** ours — `grep` over `src/` for `SafeArea|page.window|page.padding|page.spacing|window.min` returns **nothing**. Reference: `app_shell.py:571-579` (`return ft.SafeArea(content=ft.Column(…), expand=True)`), `app_shell.py:334,381,429` (SafeArea on every subview), `main.py:173-176` (`page.window.min_width = tokens.WINDOW_MIN_WIDTH` / `min_height`; `page.padding = 0`; `page.spacing = 0`), `core/tokens.py:77-78` (`WINDOW_MIN_WIDTH = 360`, `WINDOW_MIN_HEIGHT = 600`).
- **What:** Ours' onboarding deck (`screens/onboarding_view.py:62-141`) and every screen sit under the raw page without a safe-area inset, so on a device with a notch/status bar the top of the brand hero and the header bar can be occluded. The reference wraps its *entire* shell in `ft.SafeArea` and also wraps each subview.
- **Evidence:** `ft.SafeArea` exists in the installed Flet: `.venv/.../controls/core/safe_area.py:14` `class SafeArea(LayoutControl, AdaptiveControl)` with `content` at `:29`. CollabShell `app_shell.py:571` and `main.py:173-176` are the reference sites. Ours has neither.
- **Fix / opportunity:** In `src/app_shell.py:63-77`, wrap the outer `ft.Column` in `ft.SafeArea(content=…, expand=True)`; in `src/app_controller.py:init()` set `page.padding = 0`, `page.spacing = 0`, and `page.window.min_width = 360` / `min_height = 600` (add `WINDOW_MIN_WIDTH`/`WINDOW_MIN_HEIGHT` to `src/core/tokens.py` to match `core/tokens.py:77-78`).
- **Risk if ignored:** On notched Android devices the header title, the theme button and the version chip can be partially hidden under the status bar; the desktop window opens at an arbitrary small size.

### F13 · P2 · Brand hero icon is 96 px, not the reference's 72/80

- **Where:** ours `components/brand_hero.py:37-38` (literal `width=96, height=96`); `core/tokens.py:49` (`HERO_ICON_SIZE = 96`), `core/tokens.py:43` (`ICON_HERO = 64`, **unused**). Reference: `components/brand_header.py:12-17` (`width=tokens.ICON_XXXL, height=tokens.ICON_XXXL` = **80**), `core/tokens.py:53-54` (`ICON_XXXL = 80`, `HERO_ICON_SIZE = 72`).
- **What:** Two different hero sizes inside one app: the home hero renders at 96 (`components/brand_hero.py:37`) while the onboarding hero renders at `tokens.HERO_ICON_SIZE` = 96 (`screens/onboarding_view.py:78-79`) — same value, but only by coincidence, since one is a literal and the other a token. The reference is 80 on the home hero and 72 in Settings/About.
- **Evidence:** `components/brand_hero.py:37-38` `width=96,` / `height=96,`; `core/tokens.py:49` `HERO_ICON_SIZE = 96`; `core/tokens.py:43` `ICON_HERO = 64` (0 call sites). Reference `components/brand_header.py:14-15` `width=tokens.ICON_XXXL` = 80.
- **Fix / opportunity:** Set `HERO_ICON_SIZE = 80` and `ICON_HERO = 80` in `src/core/tokens.py`; replace the literals in `components/brand_hero.py:37-38` with `tokens.HERO_ICON_SIZE`. The onboarding hero (`screens/onboarding_view.py:78`) then follows automatically.
- **Risk if ignored:** The brand mark is 20% larger than the reference; two sizes for one glyph is a design-system smell even though they currently agree.

### F14 · P1 · Snackbars are bare and inherit the theme surface — the "no bgcolor" black-on-black trap

- **Where:** ours `app_controller.py:289-291` (`page.show_dialog(ft.SnackBar(ft.Text(message)))`), `components/update_dialog.py:161` (same bare form). Reference: `core/notifications.py:14-51`.
- **What:** CollabShell carries an explicit warning about exactly this: *"Never leave bgcolor None: the SnackBar then falls back to the theme's inverseSurface while ON_SURFACE text stays same-tone, producing black-on-black (light mode) / white-on-white (dark)."* Ours sets no `bgcolor` and no text color, so the outcome depends entirely on the client-side default and the active `ColorScheme` — and our scheme does not set `inverse_surface` or `on_inverse_surface` at all (F3), so the fallback is whatever Flutter's M3 seed produces, which our `build_theme()` never controls (`core/theme.py:98-106` sets no `color_scheme_seed`).
- **Evidence:** `app_controller.py:290-291`:
  ```python
  with contextlib.suppress(Exception):
      self.page.show_dialog(ft.SnackBar(ft.Text(message)))
  ```
  Reference `core/notifications.py:36` `bgcolor = AppColors.DARK_BG` (the deliberate non-None default), `:43` `behavior=ft.SnackBarBehavior.FLOATING`, `:42` `show_close_icon=True`, `:45` `duration=3000`. `.venv/.../controls/material/snack_bar.py:179-190` confirms `behavior` defaults to `SnackBarBehavior.FIXED` when unset;
- **Fix / opportunity:** Add `src/core/notifications.py` with a `show_notification(page, message, is_error=False, is_warning=False, is_success=False)` that mirrors `CollabShell/src/core/notifications.py:14-51`: explicit `bgcolor` (never `None`), `color=ft.Colors.WHITE`, `behavior=ft.SnackBarBehavior.FLOATING`, `show_close_icon=True`, `duration=3000`. Route `app_controller.py:289` and `update_dialog.py:161` through it. `SnackBarBehavior.FLOATING` also matters here because this app *has* a `NavigationBar` (`app_shell.py:66`) — a FIXED snackbar can be occluded by it.
- **Risk if ignored:** Snackbars are the app's only transient feedback channel (18 call sites via `show_snack`) and their legibility is undefined. This is the highest-risk low-effort fix in the audit.

### F15 · P3 · Onboarding dot indicator has no animation and a different geometry

- **Where:** ours `screens/onboarding_view.py:108-113` (dot `width=24 if active else 8`, `height=8`, no `animate`); reference `screens/onboarding/__init__.py:161-172` (dot `width=10 if active else 6`, `height=6`, `animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT)`).
- **What:** The reference animates the active-dot width, which is what makes the deck feel like a carousel. Ours snaps. The geometry also differs (24×8 vs 10×6).
- **Evidence:** `screens/onboarding_view.py:109-110` `width=24 if i == index else 8,` / `height=8,`. Reference `screens/onboarding/__init__.py:163-169`. `ft.Animation` and `ft.AnimationCurve` exist in the installed Flet (verified: `hasattr(ft,'Animation') == True`, `hasattr(ft,'AnimationCurve') == True`).
- **Fix / opportunity:** In `screens/onboarding_view.py:108-113`, add `animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT)` and align the geometry to `width=10 if i == index else 6, height=6`.
- **Risk if ignored:** Cosmetic only.

### F16 · P2 · Settings sections have no per-section error isolation

- **Where:** ours `screens/views.py:429-559` (one flat `ft.Column` of 4 cards, no try/except); reference `screens/settings/__init__.py:80-109`.
- **What:** The reference wraps every section builder in `try/except` and substitutes an error card, with a documented rationale at `screens/settings/__init__.py:64-79`: *"A raise inside a section builder does NOT stay inside the section: it unwinds through this component's body … The scheduler task dies there, every later update is silently dropped, and the screen stops changing … and nothing is logged."* Ours builds all four sections inline in one `Column`; a raise in any one of them takes down the whole Settings screen with no log.
- **Evidence:** `screens/views.py:429-430` `return ft.Column(controls=[AppHeader(...), section_header("Appearance"), card(...), …])` — no try/except anywhere in the function (verified by reading `views.py:385-559`).
- **Fix / opportunity:** Extract the four sections into builder functions (`build_appearance_section`, `build_storage_section`, `build_docker_section`, `build_about_section`) in a new `src/screens/settings_sections.py`, and iterate a `sections` tuple inside a `try/except` per entry, mirroring `CollabShell/src/screens/settings/__init__.py:96-102` and its `_section_error` helper (`:27-54`). Keep the state-driven contract: builders take `(page, st, methods)`.
- **Risk if ignored:** A single failing section silently freezes the entire Settings tab — the exact failure the reference documents.

### F17 · P2 · Theme selection is a text row, not the reference's three-card selector

- **Where:** ours `screens/views.py:441-452` (`ft.Text(f"Theme: {mode_label}")` + `theme_button(...)`); reference `screens/settings/preferences_section.py:26-66` (three icon+label cards: Light / Dark / System, each `expand=True`, the selected one with a `PRIMARY` border + `with_opacity(0.10, PRIMARY)` bg, `animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT)`).
- **What:** Ours cycles through three modes via one button, so the user cannot *see* which mode is available or jump directly to one. The reference shows all three at once with the active one highlighted. The reference's `_select` also writes the choice to storage; ours does the same via `set_theme_mode` (`app_controller.py:260-268`), so only the *presentation* differs.
- **Evidence:** `screens/views.py:427` `mode_label = {"system": "System", "light": "Light", "dark": "Dark"}[st.theme_mode]`; `screens/views.py:441-452` renders one text row. Reference `screens/settings/preferences_section.py:74-81` builds the three `_card(...)` calls.
- **Fix / opportunity:** In the new settings sections module (F16), render the reference's three-card selector and call `methods.set_theme_mode("light"|"dark"|"system")` directly. Note the ordering hazard from `docs/reference/house-ui-design.md:73-75` — *"ktv's lesson: the theme IconButton needs a LOCAL `use_state` mirror so the icon flips in the same frame as the theme (a 2.3.0 regression fix)"* — our `theme_button` reads `state.theme_mode` directly (`components/app_header.py:19-22`), which is an observable read and therefore re-renders correctly, but the three-card selector should read `st.theme_mode` the same way.
- **Risk if ignored:** The user cannot see or directly choose the theme; they must tap-and-cycle and remember the order.

### F18 · P2 · Icon style is mixed: 38 % rounded vs the reference's 94 %

- **Where:** ours — 11/29 icon references carry `_ROUNDED` (`components/app_header.py:20,22` are rounded; `terminal_view.py:138` `ARROW_BACK`, `:151` `CLOSE`, `:157` `FULLSCREEN`/`FULLSCREEN_EXIT`, `:295` `APPS`, `:143` `TERMINAL`, `views.py:297` `MORE_VERT`, `app_shell.py:25-27` `APPS`/`TERMINAL`/`SETTINGS`, `components/ui.py:56` `INFO_OUTLINE` are not). Reference: 257/273 `_ROUNDED`.
- **What:** The house reference states the rule: *"In screens: `ft.Icon` with rounded Material names, sized from tokens"* (`docs/reference/house-ui-design.md:38-39`). Ours mixes families — `TERMINAL` (sharp) next to `TERMINAL_ROUNDED` (rounded) in the same app, `INFO` next to `INFO_OUTLINE` next to `INFO_OUTLINE_ROUNDED`.
- **Evidence:** grep counts — ours `_ROUNDED` **11** of **29** total; reference `_ROUNDED` **257** of **273**. Ours non-rounded set: `TERMINAL`×4, `INVENTORY_2_OUTLINED`×2, `FULLSCREEN_EXIT`×2, `APPS`×2, `SETTINGS`, `MORE_VERT`, `INFO_OUTLINE`, `INFO`, `INBOX`, `FULLSCREEN`, `CLOSE`, `ARROW_BACK`. Reference non-rounded set (16 total): `DESCRIPTION_OUTLINED`×2, `AUTO_AWESOME_OUTLINED`×2, and 12 one-offs (`ZOOM_IN`, `RADIO_BUTTON_UNCHECKED`, …) — all *semantically* outline, none a sharp-filled glyph.
- **Fix / opportunity:** Normalize every sharp-filled glyph to its `_ROUNDED` sibling in `src/app_shell.py:25-27`, `src/screens/terminal_view.py:138,143,151,157,256,295`, `src/screens/views.py:297`, `src/components/ui.py:30,56`, `src/components/app_header.py` — all verified to exist in the installed Flet (`TERMINAL_ROUNDED`, `APPS_ROUNDED`, `MORE_VERT_ROUNDED`, `CLOSE_ROUNDED`, `ARROW_BACK_ROUNDED`, `FULLSCREEN_ROUNDED`, `FULLSCREEN_EXIT_ROUNDED`, `SETTINGS_ROUNDED`, `INFO_ROUNDED`, `INFO_OUTLINE_ROUNDED`, `INBOX_OUTLINED` → all `hasattr(ft.Icons, …) == True`).
- **Risk if ignored:** Mixed glyph weights in the same chrome; visually the app does not read as one product.

---

## Responsive behavior

**Both apps are phone-first and full-bleed; neither implements breakpoints.** Verified:

- Reference: `grep -rn "max_width|MAX_WIDTH|responsive|breakpoint" src/` over CollabShell returns only 14 hits, **all** fixed pixel widths inside dialogs and panels (`components/env_dialog.py:159` `width=420`, `components/model_picker.py:121` `width=380`, `components/version_dialog.py:155,179` `width=360`, `components/shortcuts_help.py:117` `width=400`, `screens/onboarding/slides.py:203,217,244,256` `width=360/300`, `screens/files/__init__.py:325` `width=440`, `screens/session/terminal_panel.py:771` `width=440`, `screens/assistant_history.py:137` `width=420`). No `ft.ResponsiveRow`, no breakpoint constants, no `max_width` anywhere.
- Ours: `grep -rn "max_width|MAX_WIDTH|responsive|breakpoint"` over `src/` returns exactly **one** hit — `src/core/tokens.py:55` `MESSAGE_MAX_WIDTH = 320` — used at `core/styles.py:132` and `screens/onboarding_view.py:97,133`.
- The house reference's only responsive guidance is `docs/reference/house-ui-design.md:29-30`: *"ffmpeg home: section header → `ResponsiveRow` tool grid (`col={"xs":12,"sm":6,"md":4,"lg":3,"xl":2}`)"* — a pattern from a **different** app in the house, not from CollabShell.

**Verdict: PARITY on the absence of breakpoints.** Both apps would stretch the same way on a tablet. Ours is marginally *better* in one place: `components/update_dialog.py:29-37` actually measures `page.width` and clamps (`min(DIALOG_WIDTH, max(DIALOG_MIN_WIDTH, page_width - 48))`) — the reference hard-codes 360/300. Note `ft.Page.width`/`.height` are real fields (verified via `dataclasses.fields(ft.Page)`).

**Both apps center their content** where it matters: ours `screens/onboarding_view.py:97,133` (`width=tokens.MESSAGE_MAX_WIDTH` on a centered `Column`), `core/styles.py:132` (empty-state message), `screens/onboarding_view.py:100-101` (`horizontal_alignment=CENTER`). Reference: `screens/onboarding/slides.py:203,217,244,256` (`width=360/300` inside a `horizontal_alignment=CENTER` column).

**Divergence (P3):** Neither app centers *page* content on a wide screen — a 1200 dp tablet stretches the Distros/Settings columns edge-to-edge. CollabShell accepts this; ours does too. Not a finding against either, but if parity is the goal, note that the reference's `screens/onboarding/slides.py:203` `width=360` is the one place it constrains width for readability, and ours' `MESSAGE_MAX_WIDTH = 320` is its analogue.

---

## Animations / transitions and interaction feedback

| Concern | CollabShell | Ours | Verdict |
|---|---|---|---|
| Theme-color transition | none (colors snap) | none | **PARITY** |
| Onboarding dot animation | `Animation(200, EASE_IN_OUT)` — `screens/onboarding/__init__.py:169` | none — `screens/onboarding_view.py:108-113` | **GAP (P3)** — F15 |
| Settings card select animation | `Animation(150, EASE_OUT)` — `screens/settings/preferences_section.py:63` | none | GAP (P3) — F17 |
| Hover / press feedback | `ink=True` on tappable containers — `core/styles.py:83`, `screens/home/cards.py:37`, `app_shell.py:498,513` | `ink=True` on the version chip — `components/app_header.py:68,83`, `views.py:161` | ≈ parity, but ours sets `ink=True` on only 3 controls vs the reference's 4+; the container rows at `views.py:272-308` and `terminal_view.py:249-273,289-305` have **no** `ink` |
| Button height | not fixed — `ft.Button` default | fixed `height=32` / `height=40` — `views.py:292,294,295` (32) and `views.py:86,325,335,341,500` (40); `terminal_view.py` buttons unset | DRIFT (P3) |
| Compact toolbar buttons | `ButtonStyle(padding=2, visual_density=COMPACT)` — `screens/session/terminal_panel.py:68-73` | none | GAP (P3) |
| SnackBar feedback | floating, colored, close icon, 3 s — `core/notifications.py:39-47` | bare — `app_controller.py:290-291` | **GAP (P1)** — F14 |
| Dialog dismissal | `page.pop_dialog()` after the URL launch — `components/version_dialog.py:40-46` | `page.pop_dialog()` before the launch — `components/update_dialog.py:152-156` | ≈ parity (ours pops first, then launches — arguably better) |
| Dialog modal/barrier | `modal=bool(data.get("mandatory"))` — `components/version_dialog.py:190` | `modal=mandatory` — `components/update_dialog.py:118` | **PARITY** |
| Progress / loading | `ProgressRing` 28 — `house-ui-design.md:67` | `ProgressRing` 28 — `core/styles.py:151` | **PARITY** (value), but no call site |
| Terminal theme repaint on toggle | `ft.use_effect(_apply_app_theme, [app_state.theme_mode, app_state.theme_revision])` — `screens/session/terminal_panel.py:810` | `ft.use_effect(_apply_theme, [state.theme_revision])` — `screens/terminal_view.py:122` | **PARITY** |
| Press feedback on list rows | `ink=True` — `screens/home/cards.py:37` | `ink=True` — `views.py:161` only | GAP (P3) |

---

## Unification plan

Ordered by severity. Every step is state-driven (no imperative widget mutation) and touches only the files in scope.

**Step 1 — P1 · Snackbar feedback channel.** New file `src/core/notifications.py`, mirroring `CollabShell/src/core/notifications.py:14-51`:
```python
def show_notification(page, message, *, is_error=False, is_warning=False,
                      is_success=False, persist=False) -> None:
    bgcolor = (AppColors.ERROR if is_error else
               AppColors.WARN  if is_warning else
               AppColors.OK    if is_success else AppColors.DARK_BG)
    page.show_dialog(ft.SnackBar(
        content=ft.Text(message, color=ft.Colors.WHITE),
        bgcolor=bgcolor,
        show_close_icon=True,
        behavior=ft.SnackBarBehavior.FLOATING,
        dismiss_direction=ft.DismissDirection.HORIZONTAL,
        duration=None if persist else 3000,
        open=True))
```
Call sites: `src/app_controller.py:289-291` → `show_notification(page, message)`; `src/components/update_dialog.py:161` → same.

**Step 2 — P1 · Adaptive semantic colors.** In `src/core/theme.py`, split `AppColors` into per-mode pairs (CollabShell's pattern at `core/theme.py:12-35` + `core/theme.py:112-123`):
```python
LIGHT_OK, LIGHT_WARN, LIGHT_ACCENT = "#2E7D32", "#B26A00", "#1A4FC4"
DARK_OK,  DARK_WARN,  DARK_ACCENT  = "#A6E3A1", "#F38BA8", "#89B4FA"
ERROR = "#E64553"
```
Add `ok()`, `warn()`, `accent()` resolvers next to `primary()` (`core/theme.py:91-92`). Re-point: `src/core/styles.py:65`, `src/components/ui.py:30-31,36`, `src/screens/views.py:361,375,472`, `src/screens/terminal_view.py:148,204,256,322`.

**Step 3 — P1 · Glass surface separation.** In `src/core/theme.py:18,27`, set `DARK_GLASS_BG = "#26263A"` and `DARK_GLASS_BORDER = "#2D2D3F"` (CollabShell's exact values at `core/theme.py:62-63`). In light mode set `LIGHT_SURFACE = "#EDEDF2"` (`core/theme.py:11`) so the chrome recedes, and add `LIGHT_BORDER = "#D8D8E0"` for the `OutlineInputBorder` calls at `src/screens/views.py:88,337,502` (contrast 1.17 → ~1.4+ and visible).

**Step 4 — P1 · Font family.** Copy `Outfit-{Regular,Bold,Medium,SemiBold}.ttf` from `CollabShell/src/assets/fonts/` into a new `src/assets/fonts/`. In `src/app_controller.py:init()` (before line 53) set `self.page.fonts = {"Outfit": "assets/fonts/Outfit-Regular.ttf"}`; in `src/core/theme.py:108-124` set `font_family="Outfit"` on both `ft.Theme`s. Static assets — no new package (D-003 respected).

**Step 5 — P2 · Complete the ColorScheme.** Extend `scheme()` in `src/core/theme.py:98-106` to take and set `primary_container`, `secondary`, `secondary_container`, `tertiary`, `tertiary_container`, `on_primary`, `on_secondary`, `on_tertiary`, `surface_container_highest`, `outline_variant`, `error_container`, `on_error`. Light: `primary_container="#1A4FC4"`, `surface_container_highest=LIGHT_SURFACE`, `outline="#E4E4EA"`. Dark: `primary_container="#1E3A6B"`, `surface_container_highest=DARK_SURFACE`, `outline="#313244"`. Set `error=AppColors.ERROR` (not `WARN`).

**Step 6 — P2 · SafeArea + window minimums.** In `src/app_shell.py:63-77`, wrap the outer column: `ft.SafeArea(content=ft.Column(...), expand=True)`. In `src/app_controller.py:init()`, add `page.padding = 0`, `page.spacing = 0`, `page.window.min_width = 360`, `page.window.min_height = 600`; add `WINDOW_MIN_WIDTH`/`WINDOW_MIN_HEIGHT` to `src/core/tokens.py`.

**Step 7 — P2 · Icon-family normalization.** In `src/app_shell.py:25-27`, `src/screens/terminal_view.py:138,143,151,157,256,295`, `src/screens/views.py:297`, `src/components/ui.py:30,56`, replace sharp/outline glyphs with their `_ROUNDED` siblings (all verified present in flet 1.0.4).

**Step 8 — P2 · Settings composition.** New file `src/screens/settings_sections.py` with `build_appearance_section(page, st, methods)`, `build_storage_section`, `build_docker_section`, `build_about_section` — each returning a `Column` of `section_header(...)` + `card(...)`, matching `CollabShell/src/screens/settings/data_section.py:68-115`. In `src/screens/views.py:429-559`, iterate a `sections` tuple inside a per-section `try/except` that substitutes an error card (mirror `CollabShell/src/screens/settings/__init__.py:27-54,96-102`). The Appearance section renders the reference's three-card Light/Dark/System selector (`CollabShell/src/screens/settings/preferences_section.py:26-66`) calling `methods.set_theme_mode(...)`.

**Step 9 — P2 · Token discipline.** In `src/screens/views.py`, `src/screens/terminal_view.py`, `src/components/app_header.py`, `src/components/brand_hero.py`: replace the 60 literal `size=<int>` values with scale tokens (11 → `FONT_SM`/`FONT_MD`, 13 → `FONT_MD`/`FONT_LG`); replace literal `spacing=`/`padding=` with `tokens.SPACE_*`; replace `components/brand_hero.py:37-38` literals with `tokens.HERO_ICON_SIZE`; set `HERO_ICON_SIZE = 80` and `ICON_HERO = 80` in `src/core/tokens.py` (matching `CollabShell/src/core/tokens.py:53-54`). Delete the 8 unreferenced tokens (`ICON_BACKDROP`, `ICON_XXL`, `ICON_XL`, `ICON_MD`, `NAV_BAR_CLEARANCE`, `OPACITY_SUBTLE`, `OPACITY_STRONG`, `SPACE_MICRO`, `SPACE_NANO`) or wire them.

**Step 10 — P3 · Animation + polish.** Add `animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT)` to the onboarding dots (`src/screens/onboarding_view.py:108-113`) and `ft.Animation(150, ft.AnimationCurve.EASE_OUT)` to the new settings selector cards. Add `ink=True` to the container rows at `src/screens/views.py:272-308` and `src/screens/terminal_view.py:249-273,289-305`. Add a `build_brand_header`/`HERO_ICON_SIZE` alignment.

**Not recommended:** adopting CollabShell's *amber* palette. The blue accent is a deliberate, documented brand choice (`src/core/theme.py:9` "Terminal-native brand: Catppuccin-derived dark, clean light") and the contrast math is *better* (light primary 4.48 vs CollabShell's 3.22 on white). Unifying the palette would be a brand regression.

---

## Verified-good list

Checked and correct — the synthesis should not re-open these.

1. **Spacing scale is an exact match.** All 10 steps identical: `CollabShell/src/core/tokens.py:16-25` vs `src/core/tokens.py:6-15` (1/2/2/4/6/10/14/16/22/32).
2. **Radii scale is an exact match.** All 6 identical: `CollabShell/src/core/tokens.py:38-43` vs `src/core/tokens.py:18-23` (4/8/12/16/24/999).
3. **Typography size scale is an exact match.** All 8 identical: `CollabShell/src/core/tokens.py:28-35` vs `src/core/tokens.py:26-33` (8/9/10/12/14/18/22/30).
4. **Icon size scale is an exact match** for the 7 shared steps: `CollabShell/src/core/tokens.py:46-52` vs `src/core/tokens.py:36-42` (12/14/16/20/24/32/48).
5. **`OPACITY_CARD` = `0.12` matches** — `CollabShell/src/core/tokens.py:87` vs `src/core/tokens.py:62`.
6. **Header-bar structure is correct**: title left (bold, `FONT_LG`), spacer, action cluster right, `bgcolor=surface`, `padding` symmetric — `src/components/app_header.py:98-126` matches `CollabShell/src/app_shell.py:522-548`. No `ft.AppBar` anywhere in either.
7. **The "Update" version pill is near byte-identical** between the two: padding `(10,4,10,4)`, `border_radius=10`, `with_opacity(0.15, primary)`, `Border.all(1.5, primary)`, `ink=True`, 6×6 dot — `src/components/app_header.py:42-71` vs `CollabShell/src/app_shell.py:463-500`.
8. **The plain version chip matches**: same padding/radius/`ink`/`tooltip` copy, `with_opacity(0.08, dim)` — `src/components/app_header.py:72-86` vs `CollabShell/src/app_shell.py:502-521`.
9. **Section-header geometry and letter-spacing match**: `letter_spacing=1`, `FONT_SM`, padding `(SPACE_LG, SPACE_LG, SPACE_MD, SPACE_XS)` — `src/core/styles.py:25-43` vs `CollabShell/src/core/styles.py:12-27`. (Only the `.upper()` differs — F8.)
10. **Glass-card geometry matches**: `RADIUS_LG`, 1px hairline, `adaptive_glass_bg()`/`theme.glass_bg()` — `src/core/styles.py:14-22` vs `CollabShell/src/core/styles.py:76-91`. (Only the color values differ — F1/F2.)
11. **Empty-state pattern is correct and matches the house doc**: 96×96 tinted circle + 48px icon + title `FONT_XL` `W_600` + message `FONT_MD` dim, max width 320 — `src/core/styles.py:101-143` matches `docs/reference/house-ui-design.md:66` (Sherlock's 96×96 backdrop).
12. **Loading-state spinner size matches the reference's 28** — `src/core/styles.py:151` vs `docs/reference/house-ui-design.md:67`.
13. **Status dot is in the house 10–14 px band** with `RADIUS_PILL` — `src/core/styles.py:59-67` (12 px) vs `CollabShell/src/core/styles.py:212-221` (10 px); band per `docs/reference/house-ui-design.md:60`.
14. **Terminal theme name mapping is identical**: `"Colab Light"` / `"JetBrains Dark"` — `src/screens/terminal_view.py:34` vs `CollabShell/src/screens/session/terminal_panel.py:79`; both names exist in flet_terminal 0.4.0 (verified: `BUILTIN_THEMES.keys()` → `['Dracula','JetBrains Dark','Matrix Green','Colab Light']`).
15. **Terminal scrollback replay on mount matches** — `src/screens/terminal_view.py:96-98` (`entry.replay(mt.send_bytes)`).
16. **Terminal keyboard-inset handling matches** — `src/screens/terminal_view.py:83-94,226-227`.
17. **Terminal theme repaint uses `ft.use_effect` on the observable revision** — `src/screens/terminal_view.py:122` vs `CollabShell/src/screens/session/terminal_panel.py:810`.
18. **Update-dialog structure is correct**: two modes, `ft.Markdown(selectable=True, extension_set=GITHUB_WEB)`, `mandatory` → `modal=True`, `page.pop_dialog()` then launch — `src/components/update_dialog.py:40-146` vs `CollabShell/src/components/version_dialog.py:121-202`.
19. **Launch-URL allowlist is stronger than the reference** (the reference launches any URL: `CollabShell/src/components/version_dialog.py:29-37`; ours gates through `is_allowed_launch_url` at `src/components/update_dialog.py:23-26`).
20. **Theme cycling order is defined in exactly one place** — `src/app_controller.py:35` `_THEME_ORDER = ("light","dark","system")`, consumed by both the header button and the Settings row (`src/components/app_header.py:31`, `src/screens/views.py:449`), so they cannot diverge.
21. **The `theme_revision` re-render signal is correct.** `src/core/theme.py:52` reads `state.theme_revision` to subscribe, and `src/core/state.py:31` documents it as the re-render signal — the same mechanism as `CollabShell/src/core/theme.py:90-93`.
22. **`ft.use_state` correctly subscribes to observables.** `src/core/state.py:8` `@ft.observable class AppState`; `src/screens/views.py:75` `st, _ = ft.use_state(state)` — flet attaches the observable subscription in `use_state` (`.venv/.../flet/components/hooks/use_state.py:84-93`).
23. **The SYSTEM-mode resolver does read `platform_brightness`** — `src/core/theme.py:67-68` — and `ft.Page.platform_brightness` is a real read-only field (`.venv/.../flet/controls/page.py:571`).
24. **The dialog-width clamp is genuinely responsive** — `src/components/update_dialog.py:29-37` measures `page.width`; `ft.Page.width` is a real field (verified via `dataclasses.fields(ft.Page)`).
25. **`except TypeError, ValueError:` is valid Python 3.14** (PEP 758, unparenthesized except groups). Verified: `python.exe --version` → 3.14.7; `python -m py_compile src/components/update_dialog.py` → exit 0. `.python-version` pins `3.14`.
26. **Onboarding swipe threshold matches exactly** (±200 px) — `src/screens/onboarding_view.py:56-59` vs `CollabShell/src/screens/onboarding/__init__.py:134-139`.
27. **Brand hero tinting behavior matches**: white-tint on dark, artwork colors on light — `src/components/brand_hero.py:42` vs `src/screens/onboarding_view.py:81`.
28. **Banner ads are mobile-only and collapsed to 0×0 otherwise** — `src/components/banner_ad.py:57-60` vs `CollabShell/src/core/styles.py:113-119`.
29. **The app uses no imperative widget mutation for the audited surfaces** — every color is resolved at build time through `theme.*()` helpers, consistent with D-015.
30. **Both apps are phone-first with no breakpoints** — verified by grep over both trees; neither implements `ft.ResponsiveRow` or a breakpoint constant. Parity.
31. **Both apps are flat by design** — no `BoxShadow`/`elevation` in either (`grep` for `shadow` over both `src/` trees returns only prose matches). Parity.

---

## Unverified

- **Whether the Flutter client actually resolves `ft.Colors.PRIMARY` / `ON_SURFACE_VARIANT` against `ColorScheme.primary` / `on_surface_variant`.** The Dart client is not shipped in `.venv/Lib/site-packages/` (no `.dart` files found), so the token→scheme mapping could not be read. This underpins F9's severity assessment (the reference's `ft.Colors.PRIMARY` usage depends on it). The Python-side `Colors.PRIMARY = "primary"` string is confirmed at `.venv/.../flet/controls/colors.py:136`, but the client-side substitution is not.
- **Whether `ft.Colors.with_opacity(opacity, ft.Colors.ON_SURFACE)` (a semantic token, not a hex) composites correctly on the client.** CollabShell uses this pattern ~200 times (`core/styles.py:56,229`, `screens/home/cards.py:22`, …); ours never does (all our `with_opacity` calls take a concrete hex or `theme.*()` result — `src/core/styles.py:96,108,113,130`). Whether the client resolves `onsurface,0.5` against the active scheme is not verifiable from the Python package.
- **The rendered result of the F2 / F3 / F5 changes** — no screenshot or emulator run was performed; contrast ratios were computed arithmetically from the hex values, and the *relative* elevation argument in F1/F2 is derived from the ratio math, not from pixels.
- **Whether `page.platform_brightness` is populated before the first render on Android.** `ft.Page.platform_brightness` defaults to `None` (`.venv/.../flet/controls/page.py:571`) and the Dart client must push it; if it arrives after the first render, our resolver's fallback (`return brightness == ft.Brightness.LIGHT` → `False`, `src/core/theme.py:68`) yields **dark** while CollabShell's (`return True`, `CollabShell/src/core/theme.py:109`) yields **light** — a visible one-frame flip in the opposite direction. The fallback asymmetry is verified in isolation but the arrival timing is not.
- **No `on_platform_brightness_change` handler is registered in ours** (`grep` over `src/` → 0 hits; the reference registers one at `CollabShell/src/main.py:221-229` that bumps `theme_revision`). Consequence — in SYSTEM mode, a runtime OS light/dark flip will not bump `state.theme_revision`, so components that cache a resolved color at build time will not re-render. This is a **finding** (folded into F12's fix list) but its user-visible magnitude on a given device is unverified.
- **CollabShell's `main.py` font-registration path** (`assets/fonts/Outfit-Regular.ttf`) was read but the license file for the Outfit font was not located in the CollabShell tree, so the redistribution terms are assumed (SIL OFL) but **not proven from this repo**.
