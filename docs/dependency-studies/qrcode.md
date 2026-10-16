# qrcode 8.2 — Exhaustive API Reference

**Identity:** `qrcode` 8.2 · BSD (`License: BSD`, `Summary: QR Code image
generator` in `.venv/Lib/site-packages/qrcode-8.2.dist-info/METADATA:1-6`,
`Classifier: License :: OSI Approved :: BSD License`) · pure-Python QR
encoder + image factories + `qr` console script (`.venv/Scripts/qr.exe`).
Declared only transitively (`Requires-Dist: qrcode>=7.4.2` in
`.venv/Lib/site-packages/flet_cli-1.0.4.dist-info/METADATA:16`) for `flet run`
device-connect printing. Dev flows only — zero build relevance (roadmap §3
row D1).

**Verification method:** every claim traces to installed source (`file:line`)
or live introspection (`inspect.signature`, `dir()`); unverifiable items are
marked **unverified**.

---

## 1. `QRCode` — every ctor param + method

Package surface (`qrcode/__init__.py:1-9`): `from qrcode.main import QRCode,
make`; `from qrcode.constants import ERROR_CORRECT_L/M/Q/H`; `from qrcode
import image`; `run_example(data="http://www.lincolnloop.com", *args, **kwargs)`.

Class `QRCode(Generic[GenericImage])` (`qrcode/main.py:74`; attrs
`modules: ModulesType`, `_version: Optional[int] = None`).

Ctor (verified via `inspect.signature` + source `main.py:76-108`):

```python
(self, version=None, error_correction=0, box_size=10, border=4,
 image_factory: type[GenericImage] | None = None, mask_pattern=None)
```

Default `error_correction=0` ≡ `ERROR_CORRECT_M` (see §2 — M is 0, not a typo).
Body: `_check_box_size(box_size)`, `_check_border(border)`, int-coerces
`error_correction/box_size/border`, `mask_pattern` setter validates via
`_check_mask_pattern`, asserts `issubclass(image_factory, BaseImage)` when
given, then `self.clear()`. `version` property (`:91-105`): getter auto
`best_fit()` when `_version is None`; setter `util.check_version(value)`.

Methods (full `dir()` list verified live: `active_with_neighbors add_data
best_fit best_mask_pattern clear get_matrix is_constrained make makeImpl
make_image map_data mask_pattern print_ascii print_tty
setup_position_adjust_pattern setup_position_probe_pattern setup_timing_pattern
setup_type_info setup_type_number version`):

- `clear()` — `self.modules = [[]]; modules_count = 0; data_cache = None;
  data_list = []`.
- `add_data(data, optimize=20)` — appends `util.QRData(data)` directly, or
  `util.optimal_data_chunks(data, minimum=optimize)` when `optimize` truthy;
  passthrough if already `util.QRData`; resets `data_cache`.
- `make(fit=True)` — `best_fit(start=self.version)` when `fit` or version
  unset; then `makeImpl(False, best_mask_pattern())` or `self.mask_pattern`.
- `makeImpl(test, mask_pattern)` — `modules_count = version*4+17`; reuses
  `precomputed_qr_blanks[version]` or builds probe/adjust/timing patterns;
  `setup_type_info`, `setup_type_number` (v≥7), `data_cache =
  util.create_data(version, error_correction, data_list)`, `map_data(...)`.
- `best_fit(start=None)` (`:208`) — smallest version 1–40 fitting the data
  (**unverified** overflow exception type).
- `make_image(image_factory=None, **kwargs)` (`:330-339` overloads + impl
  `:339-384`): defaults — `self.image_factory`, else PIL `PilImage` if
  `Image` available else `PyPNGImage` (`:364-368`); embedded-image kwargs
  (`embedded_image[_path]` incl. legacy `embeded_*` typo) require
  `ERROR_CORRECT_H` else `ValueError`; drives `drawrect/drawrect_context` +
  `process()` via `needs_drawrect/needs_context/needs_processing` flags.
- `print_ascii(out=None, tty=False, invert=False)` (`:286`) — text QR to a
  stream (flet-cli uses `invert=True`); `print_tty(out=None)` (`:256`) —
  ANSI-color terminal variant (flet-cli leaves `qr.print_tty()` commented out).
- `get_matrix()` (`:515`) — 2-D module array WITH border (set `border = 0`
  first for borderless); auto-`make()` if needed.
- Layout internals: `setup_position_probe_pattern(row, col)`,
  `setup_position_adjust_pattern()`, `setup_timing_pattern()`,
  `setup_type_info(test, mask_pattern)`, `setup_type_number(test)`,
  `map_data(data_cache, mask_pattern)`, `mask_pattern` property,
  `best_mask_pattern()`, `is_constrained(row, col)`, `active_with_neighbors(...)`.
- Module shortcut: `make(data=None, **kwargs)` (`main.py:22-26`):
  `qr = QRCode(**kwargs); qr.add_data(data); return qr.make_image()`.

Guards: `_check_box_size`, `_check_border`, `_check_mask_pattern(:28-40)`,
`copy_2d_array(:51)`, `ActiveWithNeighbors(NamedTuple)(:55)`.

## 2. `constants` — error-correction levels etc.

`qrcode/constants.py` verbatim:

```python
ERROR_CORRECT_L = 1
ERROR_CORRECT_M = 0
ERROR_CORRECT_Q = 3
ERROR_CORRECT_H = 2
```

(Note the non-alphabetical values — L=1, M=0, Q=3, H=2.) `qr` CLI maps
`--error-correction L|M|Q|H` (default `M`) with help `L (7%), M (15%,
default), Q (25%), H (30%)` (`console_scripts.py`). `version` param range
1–40 per dist-info long description (`METADATA:98`).

## 3. `image` / `pil` factories + `util`

`qrcode/image/` (verified `ls`): `__init__.py base.py pil.py pure.py
styledpil.py svg.py styles/`. Base (`image/base.py:13,110`):
`BaseImage`, `BaseImageWithDrawer`. PIL (`image/pil.py:5`):
`PilImage(qrcode.image.base.BaseImage)` — default when importable
(`main.py:364-368`: `PilImage if Image else PyPNGImage`). `default_factories`
(`console_scripts.py`): `pil → qrcode.image.pil.PilImage`, `png →
qrcode.image.pure.PyPNGImage`, `svg → qrcode.image.svg.SvgImage`,
`svg-fragment → SvgFragmentImage`, `svg-path → SvgPathImage`, legacy
`pymaging → qrcode.image.pure.PymagingImage`; `--factory-drawer` + drawer
aliases via `drawer_aliases` (styledpil). Factory/plugin class bodies beyond
names are **unverified** here.

`util.py` top-level defs (grep-verified): `_data_count(:100)`,
`BCH_type_info(:114)`, `BCH_type_number(:122)`, `BCH_digit(:129)`,
`pattern_position(:137)`, `mask_func(:141)`, `mode_sizes_for_version(:164)`,
`length_in_bits(:173)`, `check_version(:182)`, `lost_point(:187)` +
`_lost_point_level1-4`, `optimal_data_chunks(data, minimum=4)(:354)`,
`_optimal_split`, `to_bytestring`, `optimal_mode`, classes `QRData(:415)`,
`BitBuffer(:470)`, `create_bytes(:498)`, `create_data(version,
error_correction, data_list)(:550)`. Reed-Solomon internals — call via
`QRCode`, not directly. `LUT.py`, `exceptions.py`, `compat/`, `release.py`
(zest.releaser `update_manpage`) present; `tests/` ships in the wheel.

`qr` console script (`console_scripts.py:main()`): reads stdin or `args[0]`
(bytes via `surrogateescape`); options `--factory`, `--factory-drawer`,
`--optimize INT`, `--error-correction {L,M,Q,H}`, `--ascii`, `--output FILE`;
TTY/stdout-pipe auto-select (`os.isatty` → `print_ascii`, else image bytes to
stdout buffer); Windows colorama init. Entry `.venv/Scripts/qr.exe` verified
present.

## 4. How flet-cli uses it — device-connect printing (quote sites)

`.venv/Lib/site-packages/flet_cli/commands/run.py`:

- Import (`:16`): `import qrcode`.
- `Handler.print_qr_code(orig_url, android)` (`:638-674`): parses the app URL,
  substitutes the LAN IP (`get_local_ip()`), prints `App is running on:
  <lan_url>`, builds `qr_url` — Android: `https://android.flet.dev/<quoted
  ip:port/path>`, otherwise `flet://flet-host/<quoted lan_url>` (`:652-668`).
- Renders (`:672-674`): `qr = qrcode.QRCode(); qr.add_data(qr_url);
  qr.print_ascii(invert=True)` (with `# qr.print_tty()` + `# print(qr_url)`
  left commented), then `Scan QR code above with Camera app.`

Purpose: phone joins the desktop dev server via the official Flet preview app
— `flet run --android/--web/--ios` flow (roadmap §1b). No build, packaging, or
runtime role.

## 5. Utilization ideas for OUR app/scripts (honest assessment)

Candidate: in-app container share links (invite codes, OCI refs, support
bundles) rendered as QR via this Python package. Honest verdict — dev flows
only, do NOT ship to Android:

1. No Flet QR widget exists in 1.0.4; we would have to rasterize
   (`make_image` → PNG bytes → `ft.Image(src_base64=…)`) or dump
   `print_ascii`/`get_matrix()` into a monospace `ft.Text` — both add a
   `qrcode[+pillow]` runtime dep to every APK for a niche screen.
2. The default factory prefers PIL (`PilImage if Image else PyPNGImage`) —
   Pillow is currently host-only (`flet-platform-assets` icon rendering);
   promoting it to a runtime dep enlarges the payload and the `[tool.flet.cleanup]`
   audit for zero core-loop gain (install/login/terminal never need QR).
3. Real uses are all host-side: CI artifact pages, device-harness URLs,
   `qr --output invite.png 'flet://…'` in release scripts, ASCII QR in dev
   terminals. Keep `qrcode` exactly where it is — transitive via flet-cli —
   and reach for the `qr` CLI or a 3-line `QRCode().add_data();
   .print_ascii()` snippet in `tools/` scripts when needed.

## 6. How qrcode makes our app significantly better than Termux's proot-distro

Narrowly, honestly: it smooths the dev-loop device join. Termux proot-distro
testing means reading an IP:port off a laptop screen and hand-typing it into a
phone browser/SSH client. `flet run` + qrcode prints a scannable LAN QR
(`android.flet.dev` launcher or `flet://flet-host` URL) so the preview app
joins in one camera scan. That is the entire win — developer onboarding and
daily UI iteration, not product capability. It adds nothing to the APK, the
container engine, or release quality, and must not be mistaken for an in-app
feature.

## 7. Fullest utilization — concrete for THIS project

qrcode: dev flows only. No `dependencies` entry, no in-app screen, no service.
Optional host-side conveniences: a `tools/print_qr.py` emitting ASCII + PNG for
harness URLs (M0/M5 device rituals), reusing flet-cli's exact 3-line pattern
(`QRCode()`, `add_data(url)`, `print_ascii(invert=True)`). Revisit only if a
future share/invite screen earns its dependency weight with a real user story.

## 8. Verification refs

- `qrcode/__init__.py:1-30`; `qrcode/constants.py` (4 lines, verbatim §2);
  `qrcode/main.py:22-26` (`make`), `:28-55` (guards), `:74-108` (ctor),
  `:208` (`best_fit`), `:256` (`print_tty`), `:286` (`print_ascii`),
  `:330-384` (`make_image` + PIL-default `:364-368`), `:515` (`get_matrix`);
  live `inspect.signature(QRCode.__init__)` + `dir(QRCode)` outputs (§1).
- `qrcode/image/` listing; `image/base.py:13,110`; `image/pil.py:5`;
  `qrcode/util.py` def/class inventory; `console_scripts.py` (full `main`,
  `default_factories`, `error_correction`); `.venv/Scripts/qr.exe` present.
- `qrcode-8.2.dist-info/METADATA:1-14,88,98` (version/summary/license/levels).
- `flet_cli/commands/run.py:16,630-680` (import, `print_qr_code`, `print_ascii
  (invert=True)`); `flet_cli-1.0.4.dist-info/METADATA:16`.
- `docs/roadmap.md` §1b + §3 D1; `docs/reference/dep-test-and-lint-stack.md`
  (§pluggy/colorama notes qrcode's dep context).
- **Unverified**: Reed-Solomon/overflow specifics, factory class bodies beyond
  names, `styledpil` drawers, `tests/`/`release.py` behavior.
