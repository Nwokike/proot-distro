# Design comparison — our app vs CollabShell vs DDGS (personal audit)

**Date:** 2026-10-20 · **Method:** read the source of all three apps directly; every claim cites `file:line`.
**Primary target:** CollabShell (owner ruling). **Secondary target:** DDGS (modern consumer polish only).
**Verdict:** the owner's complaint is confirmed: our home composition is reversed, our header is inside the scroll, and our typography is materially smaller than the house baseline. DDGS confirms the same diagnosis, but DDGS is not the header model — its logo lives in the header, which is the one thing the owner explicitly does not want.

---

## 1. What actually renders today

### CollabShell (target)

```
SafeArea
└─ Column
   ├─ header_bar                      app_shell.py:518-546   ← FIXED, outside the scroll
   │    title (current tab) · spacer · history · version chip · help · theme
   └─ screen body (scrolls)           app_shell.py:569
        HomeScreen:
        ├─ brand hero (centered logo + tagline)   home/__init__.py:323
        ├─ offline banner / status chips / quick actions
        ├─ sessions header + list
        ├─ banner ad · features · banner ad · how-it-works
        └─ bottom spacer
```

So the order is **header first, logo second** — and the logo is centered in the home body, never in the bar (`components/brand_header.py:6-42`: `horizontal_alignment=CENTER`, no header image).

### DDGS (polish reference)

```
SafeArea                              app_shell.py:185
└─ screen
   └─ scroll Column                   home_screen.py:604-982
      ├─ offline banner               :607
      ├─ AppHeader                    :609   ← FIRST content; small 28px logo ON THE LEFT
      ├─ centered SearchBar           :616-673
      ├─ centered category chips      :674-686
      ├─ centered Search Tools + pill Search button  :688-803
      ├─ recent · banner ad · features · banner ad · how-it-works · privacy
      └─ 80px bottom-nav spacer       :978
NavigationBar is attached to page.views[0] (indicator color, ALWAYS_SHOW)  app_shell.py:67-74
```

DDGS gets the **order** right (header before content) but gets the **brand** wrong for our app: its logo is a 28px tinted image inside the header (`components/app_header.py:171-180`). That is not the CollabShell pattern the owner wants.

### Our app (current)

```
Column                                app_shell.py:57-74
├─ DistroView (scrolls)               views.py:311-379
│   ├─ build_brand_hero(...)          views.py:311   ← LOGO
│   ├─ AppHeader("Distros", ...)      views.py:312   ← HEADER AFTER THE LOGO
│   ├─ hints_card                     views.py:313
│   ├─ section "Install" ...          views.py:314
│   ├─ section "Containers" ...       views.py:363
│   └─ banner ad                      views.py:377
└─ NavigationBar (default styling)    app_shell.py:66-71
```

Settings is different again: `AppHeader` is the first control (`views.py:431`), no hero. So the two screens disagree about where the header belongs.

**The bug is exactly what the owner saw: logo, then header.** And because both live inside the scrolling `Column`, the header scrolls away instead of staying fixed like CollabShell's.

---

## 2. Parity matrix

| # | Element | CollabShell | Ours | Verdict |
|---|---|---|---|---|
| 1 | Header position | outside scroll, `app_shell.py:518-546` + `:569` | inside the screen column, after the hero `views.py:311-312` | **DEVIATION (P1)** |
| 2 | Brand placement | centered in home body, `home/__init__.py:323`, component `brand_header.py:6-42` | centered but *before* the header, `views.py:311`, `brand_hero.py:32-62` | **DEVIATION (P1)** |
| 3 | Header consistency | one bar for every tab, title from `_TAB_NAMES` `app_shell.py:520-523` | re-created per view; Home title "Distros" `views.py:312`, Settings "Settings" `views.py:431` | **DEVIATION (P1)** |
| 4 | Header contents | title · history · version chip · help · theme `app_shell.py:523-545` | title · version chip · theme `app_header.py:101-125` | **MISSING help/history (P2)** |
| 5 | Safe area | `SafeArea` `app_shell.py:569` | none in `app_shell.py` | **MISSING (P2)** |
| 6 | Nav bar styling | `indicator_color`, ALWAYS_SHOW labels `app_shell.py:155-164` | defaults `app_shell.py:66-71` | **DEVIATION (P2)** |
| 7 | Type scale | `FONT_SM=12`, `FONT_MD=14`, `FONT_LG=16`, `FONT_XL=18` | `FONT_XXS=8`, `FONT_XS=9`, `FONT_SM=10`, `FONT_MD=12`, `FONT_LG=14` | **DEVIATION (P1)** |
| 8 | Font family | theme + explicit Outfit (DDGS `theme.py:222,246`; DDGS header `:67`) | none anywhere; platform default | **MISSING (P1)** |
| 9 | Spacing scale | 8/16/24/32 (DDGS `tokens.py:12-16`) | 2/4/6/10/14/16 (`tokens.py:6-15`) | **DEVIATION (P2)** |
| 10 | Glass/card elevation | distinct bg vs surface; opacity glass (DDGS `theme.py:18-24,104-123`, `styles.py:65-78`) | `glass_bg == surface` in both modes (`theme.py:11-13,18-20,26-27,128`) → cards invisible | **BUG (P1)** |
| 11 | Home alignment | hero centered; quick-actions SPACE_AROUND `home/__init__.py:349` | everything left-aligned in a 4px-spaced column `views.py:311-379` | **DEVIATION (P2)** |
| 12 | Search input | DDGS centered `SearchBar` with leading icon + paste `home_screen.py:616-673`; CollabShell search-first pattern | plain `TextField` in a card `views.py:80-109` | **DEVIATION (P2)** |
| 13 | Primary action | DDGS centered pill `FilledButton` `home_screen.py:763-792` | default-height `ft.Button` rows `views.py:326-329` | **DEVIATION (P2)** |
| 14 | Animation | 150ms chips/tools `home_screen.py:151,732-735`; 200ms dots `onboarding_screen.py:114` | none | **MISSING (P3)** |
| 15 | Snackbar | DDGS explicit bgcolor + backstop (`core/snack.py:28-55`; onboarding `:144-149`) | bare `ft.SnackBar(ft.Text(...))` `app_controller.py:290-291` | **BUG (P1)** |
| 16 | Background | DDGS gradient `home_screen.py:988-991`, `theme.py:184-198` | flat `theme.bg()` `views.py` / `app_shell.py:60` | **DEVIATION (P3)** |
| 17 | Section headers | CollabShell uppercase PRIMARY + letter_spacing 1 `home/__init__.py:371-375` | same pattern `styles.py:25-56` | **MATCH** |
| 18 | Onboarding | CollabShell chrome-free centered; DDGS 120px circular icon + animated dots `onboarding_screen.py:70-117` | centered 96px icon, static dots `onboarding_view.py:62-141` | **CLOSE (P3)** |
| 19 | Update chip | same geometry/pattern `app_header.py:35-86` | same | **MATCH** |
| 20 | Theme switching | icon reflects mode; system follows platform | same, plus `theme_revision` subscription `theme.py:43-68` | **MATCH** |

---

## 3. Findings, ranked

### F1 · P1 · The home order is reversed
`views.py:311` renders the hero before `views.py:312` renders the header. CollabShell's header is above the screen body (`app_shell.py:518-546`, body at `:569`) and the hero is the first thing inside the home body (`home/__init__.py:323`). DDGS also puts its header first (`home_screen.py:609`, before the search content).

**Fix:** make the header shell-level chrome and render the hero as the first child of `DistroView`.

### F2 · P1 · The header scrolls away
Our header is inside the scrollable `ft.Column` (`views.py:379` sets `scroll=ft.ScrollMode.AUTO` on the same column that starts at `:311`). CollabShell's bar is outside the screen body, so it stays fixed. DDGS accepts a scrolling header, but DDGS has no separate fixed bar to preserve; we are copying CollabShell.

**Fix:** move `AppHeader` into `AppShell`'s outer `Column`, above `body`, with a per-tab title; leave views header-free.

### F3 · P1 · Two screens, two different header models
Home puts the header after the hero (`views.py:312`); Settings puts it first (`views.py:431`); Terminal has no header at all (`terminal_view.py`). CollabShell has one bar for every tab (`app_shell.py:518-546`). This is the "nonsense" the owner is reacting to: there is no single composition rule.

**Fix:** one header definition in `AppShell`, title derived from the active tab, optional back button when a shell is open.

### F4 · P1 · Type is below the house legibility floor
Our scale starts at `FONT_XXS=8`, `FONT_XS=9`, `FONT_SM=10` (`tokens.py:26-33`). DDGS's floor is 11 (`tokens.py:3-10`: "no user-facing text below 11pt"), with body at 12–14. Many live labels use 9–11: `views.py:295-299` (10/11), `views.py:509` (10), `app_header.py:49,75` (10). On a phone this reads as miniature.

**Fix:** raise the floor. Minimum mapping: `FONT_XXS→11`, `FONT_XS→11`, `FONT_SM→12`, `FONT_MD→14`, `FONT_LG→16`, `FONT_XL→20`, `FONT_XXL→24`, `FONT_HERO→32`. This is the DDGS scale and is close to CollabShell's `FONT_SM=12`/`FONT_MD=14`.

### F5 · P1 · No font family
DDGS applies "Outfit" at the theme level (`theme.py:222,246`) and on every text (`home_screen.py:135` etc.). CollabShell's renderer uses the platform default too, but the owner's house apps use Outfit. Ours sets no `font_family` in `build_theme()` (`theme.py:108-123`) and ships no `src/assets/fonts/`.

**Fix:** ship `Outfit` (Regular/Medium/SemiBold/Bold) under `src/assets/fonts/`, register in the app, set `font_family="Outfit"` on both `ft.Theme`s. Until the font file exists, do not set the name.

### F6 · P1 · Cards have no elevation
`glass_bg()` returns `#FFFFFF` in light (same as `surface()`) and `#1E1E2E` in dark (same as `surface()`) — `theme.py:11-13,18-20,26-27,128`. Every `glass_card` (`styles.py:14-22`) is therefore invisible against the background. DDGS uses distinct backgrounds (`DARK_BG_1 #0F1114` vs `DARK_SURFACE #1A1D22`, `theme.py:18-20`) plus an opacity overlay (`theme.py:104-123`).

**Fix:** darken the dark background to `#0F1114` (or `#121218` with surface `#1E1E2E` already distinct — it is, barely) and set glass to a translucent white/black overlay, not the surface color. Minimum: `DARK_GLASS_BG="#26263A"`, `LIGHT_GLASS_BG="#FFFFFF"` with `LIGHT_BG="#F4F4F8"` (already distinct in light). The dark mismatch is the severe one.

### F7 · P2 · Cramped spacing
Our base step is 2–6px (`tokens.py:6-15`: SM=6, MD=10, LG=14), while DDGS uses 8/16/24 (`tokens.py:12-16`). Combined with 4px column spacing (`views.py:379`) the home reads as a dense form, not a dashboard.

**Fix:** align to the 8-point grid: `SPACE_XS=4, SPACE_SM=8, SPACE_MD=12, SPACE_LG=16, SPACE_XL=24, SPACE_XXL=32`; then audit call sites (many use `tokens.SPACE_MD` for card padding).

### F8 · P2 · Home is not centered / no search-first composition
DDGS centers the search bar, chips, tools and primary action (`home_screen.py:616-673, 681, 738, 794`). CollabShell centers the hero and uses `SPACE_AROUND` for quick actions (`home/__init__.py:349`). Ours is a left-aligned column of cards (`views.py:311-379`).

**Fix:** center the hero (already), center the install search row, use a pill `FilledButton` for the primary action, and give the install card a centered header. Keep CollabShell's section-header style (uppercase primary) — do not copy DDGS's sentence-case headers.

### F9 · P2 · Header is missing the action cluster
CollabShell's bar has title · history · version chip · help · theme (`app_shell.py:523-545`). Ours has title · version chip · theme (`app_header.py:101-125`). DDGS adds settings and a credit pill (`app_header.py:208-234`). For this app, a help button (shortcuts/how-to) is the missing piece; history is meaningless.

### F10 · P2 · No SafeArea / nav bar styling
DDGS wraps the shell in `SafeArea` (`app_shell.py:185`) and styles the nav bar (`:67-74`). CollabShell wraps in `SafeArea` (`app_shell.py:569`). Ours returns a bare `Column` (`app_shell.py:57-74`), so the status-bar inset is whatever the platform gives, and the nav bar uses defaults.

**Fix:** wrap in `ft.SafeArea`, set `indicator_color=with_opacity(0.12, primary)`, `label_behavior=ALWAYS_SHOW`.

### F11 · P2 · Snackbars can be black-on-black
`app_controller.py:290-291` shows `ft.SnackBar(ft.Text(message))` with no `bgcolor`. The design-system audit already found the CollabShell warning (`CollabShell/src/core/notifications.py:33-36`): an unspecified SnackBar background falls back to the theme's `inverseSurface`, producing black-on-black in light mode / white-on-white in dark. DDGS pairs every snack with an explicit color (`onboarding_screen.py:144-149`).

**Fix:** central helper that always sets `bgcolor` + `behavior=FLOATING` (the app has a NavigationBar) and a dismissal backstop, as DDGS `core/snack.py:28-55`.

### F12 · P3 · No motion
DDGS animates chips (`home_screen.py:151`), the tools panel (`:732-735`), and onboarding dots (`onboarding_screen.py:114`). Ours animates nothing. This is low risk but is a large part of why DDGS feels modern.

### F13 · P3 · Onboarding is close, not equal
Ours: 96px plain icon, static dots, 52px button (`onboarding_view.py:76-125`). DDGS: 120px circular tinted container, 64px icon, 24pt title, 14pt body, animated width-changing dots (`onboarding_screen.py:70-117`). CollabShell's onboarding is chrome-free and centered, which ours matches structurally.

**Fix (optional):** adopt DDGS's circular icon backdrop and animated dots; keep our copy/tone.

---

## 4. Migration plan (ordered, minimal, state-driven)

1. **Shell first (F1/F2/F3/F10)** — `src/app_shell.py`
   - Wrap the outer `Column` in `ft.SafeArea(expand=True)`.
   - Put `AppHeader(title=<tab name>, ...)` as the first child, outside the scrolling body.
   - Keep `body` in `ft.Container(expand=True)`; the views stop rendering `AppHeader`.
   - Title map: `Distros`, `Terminal`, `Settings`; when `entry` is active, `Terminal` + back action.
2. **Remove per-view headers** — `src/screens/views.py:312` and `:431`; terminal view gets the shell header for free.
3. **Home composition (F1/F8)** — `src/screens/views.py:311-379`
   - Order: hero (centered) → hints → Install → Containers → banner.
   - Center the install search row; replace the two default `ft.Button`s with a pill `FilledButton` (height ≥ 44).
   - Keep section headers uppercase/primary (CollabShell), not DDGS sentence-case.
4. **Tokens (F4/F7)** — `src/core/tokens.py`
   - Raise the type floor and move to the 8-point spacing grid. Do this before touching individual screens so every screen moves at once.
5. **Theme + cards (F6)** — `src/core/theme.py`, `src/core/styles.py`
   - Separate `DARK_BG` from `DARK_SURFACE` visually and make `glass_*` a translucent overlay, not the surface color. Verify each card against its background in both modes.
6. **Font (F5)** — add `src/assets/fonts/Outfit-*.ttf`, then `font_family` on both themes. Do not set the family before the files exist.
7. **Snack helper (F11)** — one `show_snack` with explicit `bgcolor`, `behavior=FLOATING`, and a backstop; replace all 18 `show_snack` call sites.
8. **Nav bar + motion (F10/F12)** — indicator color, ALWAYS_SHOW, 150ms animations on chips/expandable panels.
9. **Onboarding polish (F13)** — optional, after the shell is correct.

**Do not copy from DDGS:** the logo-in-header (owner explicitly wants CollabShell's home hero), the sentence-case section headers (CollabShell's uppercase primary is the house rule), or the credit/premium surfaces (not this product).

**Do copy from DDGS:** the 11pt type floor, the 8-point spacing scale, Outfit at theme level, centered search-first composition, pill primary action, `SafeArea`, nav-bar indicator styling, explicit snack colors + backstop, and 150ms motion.

---

## 5. Verified-good (do not re-open)

- Hero is horizontally centered (`brand_hero.py:55-61`).
- Hero artwork inverts correctly with the theme (`brand_hero.py:42`).
- Uppercase primary section headers match CollabShell (`styles.py:25-56`).
- Version/update chip geometry matches both references (`app_header.py:35-86`).
- Theme mode resolution incl. SYSTEM and `theme_revision` subscription is correct (`theme.py:43-68`).
- Onboarding is structurally CollabShell-shaped: chrome-free, centered, skippable (`onboarding_view.py:62-141`).
- Radii scale (4/8/12/16/24/pill) is compatible with both references; no change needed.
