# House UI design language (verified 2026-10-19 across ffmpeg / Sherlock / ktv-player / CollabShell)

Condensed from a four-app source study; every item cites the file it came from.
This is the reference M4's header/menu and home polish build from.

## 1. The header / menu (what CollabShell actually does)

`CollabShell/src/app_shell.py:518-546` — a slim header-bar `Container`
(SURFACE background, small padding) holding a `Row`:

- **left:** the CURRENT TAB'S NAME as a bold text (`_TAB_NAMES[state.current_tab]`, `FONT_LG`, BOLD)
- **right action cluster:** a spacer, then IconButtons/chips — history (home tab only), a version chip that flips to an Update pill when a newer build exists, the help button, and the theme IconButton (`BRIGHTNESS_AUTO_ROUNDED` / `LIGHT_MODE_ROUNDED` / `DARK_MODE_ROUNDED`).

No `ft.AppBar` anywhere; no brand mark in the bar (the brand hero lives in the
home body). Screens are full-bleed columns; the bottom `NavigationBar` carries
the tabs. KTV's `Header` (ktv-player `src/components/header.py:75-91`) is the
older generation of the same idea (brand left + ink action containers right);
Sherlock's `AppHeader` (src/components/app_header.py:98-107) is the fully
parameterized one. ffmpeg keeps the header only on the dashboard.

## 2. The home screen

- **CollabShell home** (`src/screens/home/__init__.py:321-406`): brand hero →
  offline banner → status chips → quick-actions glass card (`SPACE_AROUND`) →
  sessions header (title + refresh IconButton, `SPACE_BETWEEN`) → list →
  features → how-it-works → bottom spacer (`ICON_XXXL`). Outer Column has
  `spacing=0`, full-width sections.
- **ffmpeg home** (`src/screens/home_screen.py:189-213`): section header →
  ResponsiveRow tool grid (`col={"xs":12,"sm":6,"md":4,"lg":3,"xl":2}`) →
  recent jobs → `ft.Container(height=88)` nav-bar clearance INSIDE the scroll.
- **ktv home**: `ft.Stack` (scrollable column + a mini FAB overlay);
  LoadingState (shimmer) → EmptyState → grid.
- **Sherlock home**: search-first column; note the chip row comment —
  "START, not CENTER: a centered scrollable row clips the leading chips".

## 3. Icons

- In screens: `ft.Icon` with rounded Material names, sized from tokens
  (16/20/24/32; CollabShell adds 12/14/48/80 + `HERO_ICON_SIZE=72`).
- Brand SVGs live in `src/assets/`; loaded either as bytes
  (`ffmpeg/src/core/assets.py:10-26`, tinted `color` + `BlendMode.SRC_IN`) or
  by URL (`src="/icon.svg"` via `assets_dir`).
- **One self-adapting SVG everywhere (owner ruling 2026-10-19):** each app's
  `icon.svg` now carries an internal `<style>` with a
  `prefers-color-scheme` block, so READMEs swap on GitHub dark with no second
  file; the apps keep tinting the same file at render time (their renderers
  ignore SVG CSS and use the presentation attributes).

## 4. Cards / sections / chips

- Card: `Container` with bgcolor per theme, `border_radius` 12–16,
  padding 12–16, 1px border; glass variants read `adaptive_glass_bg()` /
  `adaptive_glass_border()` (Sherlock `core/theme.py:144-155`).
- Section header: title BOLD (Sherlock/CollabShell: uppercase, PRIMARY color,
  `letter_spacing=1`; ffmpeg: `FONT_XL=20` + muted subtitle), optional
  right-side action.
- Chips: Material `ft.Chip` with `selected_color`/`bgcolor` tinted
  `with_opacity(0.08–0.14, color)` (Sherlock), or pill Containers with
  `RADIUS_XS=4` + `FONT_XXS=8` W_700 white (CollabShell badges).
- Status dot: 10–14px pill (`RADIUS_PILL`).

## 5. Empty / loading states

- Empty: centered icon (48–64) + title (16–20, W_600) + message (12–14,
  muted, max width ~300–320); Sherlock wraps the icon in a 96×96 circular
  tinted backdrop.
- Loading: CollabShell uses `ProgressRing` (28); ktv uses a `Shimmer` skeleton
  (3 cards 360×96, radius 16, period 1400ms).

## 6. Theme application at component level

- `is_dark_mode(page)` / `is_light_theme(page)` resolvers; components read them
  at build time and pick colors inline, or pass `is_dark` as a prop (ffmpeg).
- ktv's lesson: the theme IconButton needs a LOCAL `use_state` mirror so the
  icon flips in the same frame as the theme (a 2.3.0 regression fix).
- A full light/dark `ft.Theme` pair (`AppTheme.get_light_theme()` /
  `get_dark_theme()`) is applied at page level, but component surfaces use
  explicit per-theme picks rather than the Material scheme alone.
