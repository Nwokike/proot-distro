# chardet 5.2.0 — universal encoding detector

Identity: chardet 5.2.0, LGPL license (`METADATA` License: LGPL; `License-File: LICENSE`),
pure Python (probers + `universaldetector.py`; no compiled files). **Do not vendor**
(dep-cookiecutter-stack.md) — LGPL copyleft applies to vendored copies.

## Complete public API

Top-level (`chardet/__init__.py`, verified by introspection):
- `detect(byte_str: bytes | bytearray, should_rename_legacy: bool = False) -> dict` —
  returns `{"encoding": str|None, "confidence": float, "language": str|None}`.
- `detect_all(byte_str: bytes | bytearray, ignore_threshold: bool = False, should_rename_legacy: bool = False) -> List[dict]` —
  every probed candidate, not just the winner.
- `UniversalDetector` — incremental API: `__init__()`, `feed(data: bytes)`, `close()`,
  `reset()`, result in `.result` dict. For streaming/chunked input.
- `ResultDict` — typed-dict shape of results; `VERSION` / `__version__` = 5.2.0.
- Submodules (probers, `enums.InputState`, `codingstatemachine`, frequency tables) are
  internal machinery — use `detect`/`detect_all`/`UniversalDetector` only.

## Example

```python
import chardet
raw = open("guest-file.conf", "rb").read()
print(chardet.detect(raw))  # {'encoding': 'utf-8', 'confidence': 0.99, 'language': ''}
text = raw.decode(chardet.detect(raw)["encoding"] or "utf-8", errors="replace")
```

## How cookiecutter/flet uses it

Indirectly: `binaryornot/helpers.py:11` does `import chardet`, and `helpers.py:93-94`
calls `chardet.detect(bytes_to_check)` as the second stage of the binary probe. So
chardet is what keeps a UTF-16/Shift-JIS/Latin-1 template file classified as *text*.
flet-cli inherits this only through the template render path.

## Our-project utilization (M3 import/export)

Same file-type pipeline as binaryornot: once `is_binary()` says "text", `chardet.detect`
(or `detect_all` when confidence is low) picks the decode codec for guest files with
unknown locale encodings (e.g. configs created inside Debian vs Alpine images with
different default locales). Rule: trust confidence > 0.8, else fall back to UTF-8 with
`errors="replace"` and say so in the UI. Never vendor — depend on the package.

## Better than Termux's proot-distro?

User-visible only in the import/export viewer: files in legacy encodings render correctly
instead of mojibake. Small, honest tooling-side win.

## Verification refs

- Introspected live: `chardet.__version__` 5.2.0; `inspect.signature(chardet.detect/detect_all)`
- `.../binaryornot/helpers.py:11,93-94`
- `METADATA` of `chardet-5.2.0.dist-info` (License: LGPL); `docs/reference/dep-cookiecutter-stack.md` (LGPL — don't vendor)
