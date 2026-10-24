"""Design tokens — the house scale (spacing, radii, type, icons).

The 8-point spacing grid and the 11pt type legibility floor are the house
baseline (DDGS); the structure they size matches CollabShell.
"""

from __future__ import annotations

# Spacing — the 8-point grid
SPACE_MICRO = 2
SPACE_NANO = 2
SPACE_XXS = 2
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_XXL = 32
SPACE_XXXL = 40

# Radii
RADIUS_XS = 4
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_XL = 24
RADIUS_PILL = 999

# Typography — no user-facing text below 11pt (the legibility floor)
FONT_XXS = 11
FONT_XS = 11
FONT_SM = 12
FONT_MD = 14
FONT_LG = 16
FONT_XL = 20
FONT_XXL = 24
FONT_HERO = 32

# Icons
ICON_MICRO = 12
ICON_XS = 14
ICON_SM = 16
ICON_MD = 20
ICON_LG = 24
ICON_XL = 32
ICON_XXL = 48
ICON_HERO = 64
ICON_XXXL = 80
ICON_EMPTY = 48

# Components
ICON_BACKDROP = 44
ICON_CONTAINER = 56
HERO_ICON_SIZE = 80  # CollabShell's ICON_XXXL — the brand hero renders at this
EMPTY_ICON_SIZE = 96
STATUS_DOT = 12
CHIP_PADDING_H = 10
CHIP_PADDING_V = 4
NAV_BAR_CLEARANCE = 88
MESSAGE_MAX_WIDTH = 320
DIALOG_WIDTH = 380
DIALOG_MIN_WIDTH = 300

# Opacity
OPACITY_SUBTLE = 0.05
OPACITY_LIGHT = 0.08
OPACITY_MEDIUM = 0.12
OPACITY_STRONG = 0.20
OPACITY_DIM = 0.50
