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

# Radii
RADIUS_XS = 4
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
RADIUS_PILL = 999

# Typography — no user-facing text below 11pt (the legibility floor)
FONT_XXS = 11
FONT_XS = 11
FONT_SM = 12
FONT_MD = 14
FONT_LG = 16
FONT_XL = 20

# Icons
ICON_MICRO = 12
ICON_XS = 14
ICON_SM = 16
ICON_MD = 20
ICON_LG = 24
ICON_XXL = 48
ICON_HERO = 64
ICON_XXXL = 80
ICON_EMPTY = 48

# Components
HERO_ICON_SIZE = 80  # CollabShell's ICON_XXXL — the brand hero renders at this
EMPTY_ICON_SIZE = 96
STATUS_DOT = 12
STATUS_DOT_SM = 10
CHIP_PADDING_H = 10
CHIP_PADDING_V = 4
# Material's Switch is ~60x40 dp — at this scale it reads as a normal toggle
# next to a pill instead of dominating the row (owner ruling 2026-11-15).
SWITCH_SCALE = 0.6
# A compact inline field aligned with a pill's box (pills are ~30 high).
CONTROL_CHIP = 32
FIELD_COMPACT_WIDTH = 80
# Filled house input: no outline box, one tinted rounded surface.
FIELD_FILL_OPACITY = 0.06
NAV_BAR_CLEARANCE = 88
MESSAGE_MAX_WIDTH = 320
DIALOG_WIDTH = 380
DIALOG_MIN_WIDTH = 300
DIALOG_WIDTH_LG = 520

# Opacity
OPACITY_WHISPER = 0.04
OPACITY_SUBTLE = 0.05
OPACITY_TEXT_HINT = 0.06
OPACITY_LIGHT = 0.08
OPACITY_TINT = 0.10
OPACITY_MEDIUM = 0.12
OPACITY_CONTAINER = 0.14
OPACITY_CHIP = 0.15
OPACITY_SELECTED = 0.24
OPACITY_BORDER = 0.30
OPACITY_DIM = 0.50

# SnackBar visible time (ms) — the app-wide default.
SNACK_DURATION_MS = 3000

# Control heights — the touch-target scale
# Buttons inside cards and rows: compact, but still a 36dp tap target. The
# Material default (44dp + 24dp side padding) is what made every button read
# as a big blue box; one style helper now owns the density.
CONTROL_SM = 36
CONTROL_MD = 40  # primary actions / icon backdrops
CONTROL_LG = 44  # distro tile icon backdrop
CONTROL_INPUT = 44  # text fields and search bars
# Button density: horizontal padding + icon size. Tune THESE two numbers to
# resize every pill button in the app. Material's visual_density lives in
# styles.pill_button_style (it is an enum, not a number).
BUTTON_PADDING_H = 12
BUTTON_ICON_SIZE = 18

# Fixed field widths (rows never overflow; narrow screens wrap under)
FIELD_NAME_WIDTH = 190
FIELD_TARGET_WIDTH = 170
FIELD_INSTALL_AS_WIDTH = 190
FIELD_EMULATOR_WIDTH = 210
DIALOG_SIGNAL_WIDTH = 110
DIALOG_COPY_WIDTH = 240

# Animation durations
ANIM_FAST_MS = 150
ANIM_MD_MS = 200

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
FILE_MODAL_HEIGHT = 480

# Chrome
HEADER_DOT_SPACING = 6
HEADER_RADIUS = 10
LETTER_SPACING = 1  # uppercase section headers

# Typography — the monospace face used by logs and the terminal
MONO_FONT = "JetBrains Mono"
HAIRLINE = 1  # divider thickness
BORDER_WIDTH_EMPHASIS = 1.5
CONTROL_COMPACT = 44  # the search-result install button (>=44dp)
HIDDEN = 0  # a zero-size container: the "render nothing" placeholder

# ── Repeated UI values (were inline literals across screens) ───────────────
MAX_LINES_ONE = 1
MAX_LINES_TWO = 2
OUTPUT_LINE_HEIGHT = 18
OUTPUT_VERTICAL_PAD = 8
OUTPUT_MIN_HEIGHT = 36
OUTPUT_MAX_HEIGHT = 220
COMMAND_CELL_MAX_LINES = 400
COMMAND_CELL_RENDER_LINES = 200
ERROR_LINE_MAX_CHARS = 200
SNACK_DETAIL_MAX_CHARS = 120
INSTALL_LOG_MAX_LINES = 500
INSTALL_LOG_TAIL_LINES = 60
RUN_OUTPUT_TAIL_CHARS = 4000
BUILD_LOG_MAX_LINES = 500
BUILD_OUTPUT_TAIL_CHARS = 2000
DISPLAY_LOG_TAIL_LINES = 200
DISPLAY_LOG_TAIL_BYTES = 65536
DIAGNOSTIC_LOG_TAIL = 50
TERMINAL_SCROLLBACK_LINES = 10000
TERM_COLS_DEFAULT = 80
TERM_ROWS_DEFAULT = 24
LOG_RING_MAX_LINES = 5000
SCROLLBACK_BYTES = 2 * 1024 * 1024
PTY_READ_CHUNK_BYTES = 65536
PTY_FLUSH_INTERVAL_SEC = 0.016
PTY_FLUSH_BYTES = 64 * 1024
SCROLLBACK_REPLAY_FRAME_BYTES = 256 * 1024
WS_MAX_MSG_BYTES = 64 * 1024
WS_HEARTBEAT_SEC = 25.0
WS_WRITE_HIGH_WATER_BYTES = 512 * 1024
NOVNC_LEVEL_MAX = 9
FILE_PREVIEW_MAX_BYTES = 100 * 1024  # 100 KB — large files hang the TextField
HTTP_TIMEOUT_SEC = 15.0
HTTP_CONNECT_TIMEOUT_SEC = 10.0
HTTP_MAX_ATTEMPTS = 2
FIELD_PATH_WIDTH = 220
FIELD_BUILD_ARGS_WIDTH = 260
DIALOG_LOG_HEIGHT = 260
AUTO_GEOMETRY_LONG_SIDE = 1280
PROGRESS_RING_STROKE_THICK = 3
