"""Design tokens — the house scale (spacing, radii, type, icons).

The 8-point spacing grid and the 11pt type legibility floor are the house
baseline (DDGS); the structure they size matches CollabShell.
"""

from __future__ import annotations

# Spacing — the 8-point grid
SPACE_MICRO = 2
SPACE_NANO = 2
SPACE_XXS = 2
SPACE_NONE = 0
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
OPACITY_WHISPER = 0.04
OPACITY_SUBTLE = 0.05
OPACITY_TEXT_HINT = 0.06
OPACITY_LIGHT = 0.08
OPACITY_TINT = 0.10
OPACITY_MEDIUM = 0.12
OPACITY_CONTAINER = 0.14
OPACITY_CHIP = 0.15
OPACITY_STRONG = 0.20
OPACITY_SELECTED = 0.24
OPACITY_BORDER = 0.30
OPACITY_DIM = 0.50

# Control heights — the touch-target scale
CONTROL_XS = 26  # numbered step badge
CONTROL_SM = 34  # compact buttons inside cards
CONTROL_MD = 36  # standard buttons / icon backdrops
CONTROL_LG = 38  # distro tile icon backdrop
CONTROL_XL = 42  # feature-card icon backdrop
CONTROL_INPUT = 44  # text fields and search bars

# Progress rings
PROGRESS_RING_XS = 14  # the header's connecting spinner
PROGRESS_RING_SM = 18
PROGRESS_RING_MD = 22
PROGRESS_RING_LG = 24
PROGRESS_RING_XL = 28
PROGRESS_RING_STROKE = 2
PROGRESS_RING_STROKE_THIN = 2.5

# Onboarding
ONBOARDING_ICON = 42
ONBOARDING_ICON_SM = 28
DOT_ACTIVE = 18  # the width-morphing page indicator
DOT_INACTIVE = 6
DOT_HEIGHT = 6
DOT_RADIUS = 3

# Ads — AdMob's banner is a fixed 320x50 box
BANNER_WIDTH = 320
BANNER_HEIGHT = 50

# Fixed-height surfaces
LOG_BOX_HEIGHT = 180  # the install log terminal
FILE_LIST_HEIGHT = 320
FILE_PREVIEW_HEIGHT = 340
FILE_MODAL_HEIGHT = 480

# Chrome
HEADER_DOT_SPACING = 6
HEADER_RADIUS = 10
LETTER_SPACING = 1  # uppercase section headers

# Typography — the monospace face used by logs and the terminal
MONO_FONT = "JetBrains Mono"
HAIRLINE = 1  # divider thickness
BORDER_WIDTH_EMPHASIS = 1.5
CONTROL_COMPACT = 32  # the search-result install button
HIDDEN = 0  # a zero-size container: the "render nothing" placeholder
