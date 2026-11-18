# flet-xvnc — TigerVNC Xvnc payload

| | |
|---|---|
| Upstream | TigerVNC 1.16.2 (Termux `tigervnc` 1.16.2-1, x11 repo) |
| Builder | `scripts/build_flet_xvnc_wheel.py` |
| App pin | `flet-xvnc==1.16.2` |
| Ships | `libXvnc.so`, `libxkbcomp.so`, 33 ELF closure libs, `data/xkb/` (xkeyboard-config 2.49), `data/fonts/misc/` (Latin bitmap fonts + generated `fonts.dir`), `data/fonts/ttf/` (DejaVu TrueType) |

## Why Xvnc

One process is both the X server and the VNC server: guest apps draw on it over
loopback, the app proxies RFB to the noVNC viewer, and no guest X packages are
needed. The compiled-in Termux prefix is rewritten to the app's data dir at
build time.

## What the runtime does with it

- `libXvnc.so` is spawned with `-Geometry/-depth/-FrameRate/-SecurityTypes None`,
  optional `-localhost=1`, `-CompareFB`, `-dpi`, `-IdleTimeout`,
  `-MaxConnectionTime`, `-AcceptKeyEvents=0/-AcceptPointerEvents=0` (view-only),
  `-MaxCutText`, `-DisconnectClients`, `-fp`, `-xkbdir`.
- `libxkbcomp.so` is linked as `<app>/bin/xkbcomp`; Xvnc always execs
  `<prefix>/bin/xkbcomp`, and Android's W^X means the symlink into the
  native-library dir is what makes it runnable.
- `data/xkb` is staged into app storage and passed as `-xkbdir`.
- `data/fonts/misc` is staged and passed as the first `-fp` entry; guest font
  dirs that contain a `fonts.dir` follow.

## Fonts rule

Only the **core Latin** families ship (base sizes + ISO8859-1, clR/clB, fixed —
78 files). CJK, Syriac and the other charsets are excluded; they were 6.4 MB of
the APK. `fonts.dir` is generated from exactly the shipped files by
`_make_fonts_dir()` (each PCF's `FONT` property), so it can never list a font
that is not there. A desktop container still gets its own fonts through `-fp`.

## Update procedure

1. Bump `XVNC_VERSION` (`1.16.2`), `BUILD_TAG` and the `_PINNED_SOURCES` pins
   (each `.deb` + sha256) in the builder.
2. Update `pyproject.toml` (`flet-xvnc==<version>`).
3. Regenerate: `uv run python scripts/build_flet_xvnc_wheel.py --out wheels`.
4. Verify: the builder checks alignment, the closure (no unmet `DT_NEEDED`),
   and regenerates `fonts.dir`; `tests/test_xvnc_runtime.py` covers the argv and
   option threading.
5. Ship and device-check: display starts, xterm renders, no `[dix]` font lines,
   keyboard works.
