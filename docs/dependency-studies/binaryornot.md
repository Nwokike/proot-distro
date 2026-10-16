# binaryornot 0.4.4 — binary-vs-text probe

Identity: binaryornot 0.4.4, BSD license (`METADATA`: Name/Version/License fields), pure Python
(`binaryornot/check.py`, `binaryornot/helpers.py`; no compiled files in the installed package).
Upstream dependency: chardet (imported at `helpers.py:11`).

## Complete public API

`binaryornot.check`:
- `is_binary(filename) -> bool` — True for `.pyc` by extension, else delegates to the
  starting-chunk probe (`check.py:22-40`).

`binaryornot.helpers`:
- `get_starting_chunk(filename, length=1024) -> bytes` — opens the file in `rb` mode,
  reads the first `length` bytes (`helpers.py:26-38`).
- `is_binary_string(bytes_to_check) -> bool` — Perl-inspired heuristic: low non-text-byte
  ratio counts as text, then falls back to `chardet.detect` (`helpers.py:93-94`); biased
  toward calling files text.
- `print_as_hex(s)` — debug helper printing a string as hex bytes (`helpers.py:17-21`).

That's the whole surface: two modules, four functions.

## Example

```python
from binaryornot.check import is_binary
from binaryornot.helpers import get_starting_chunk, is_binary_string

print(is_binary("downloaded-rootfs.tar.gz"))  # True -> copy, don't decode
print(is_binary_string(get_starting_chunk("manifest.json", 512)))  # False -> safe to read as text
```

## How cookiecutter/flet uses it

`cookiecutter/generate.py:15`: `from binaryornot.check import is_binary`, applied at
`generate.py:221` (`if is_binary(infile):`): binary template files are copied with
`shutil.copyfile`/`copymode` and never passed through Jinja2. This is what lets a
cookiecutter template carry images, archives, or `.so` blobs. flet-cli inherits this
mechanically: `overwrite_if_exists=True` re-renders the Flutter template and binary
assets (icons/splash) survive via the copy path (dep-cookiecutter-stack.md).

## Our-project utilization (M3/M5)

Import/export feature (M3+ planning): guest files pulled out of a container (logs,
configs, user downloads) need a binary-vs-text decision before display — decode-and-show
vs offer-a-save/share path. `is_binary(path)` is exactly that gate, no new dependency
(it rides with cookiecutter on the build host; for on-device use it is a ~10-line
vendored heuristic — but chardet is LGPL, so do NOT vendor; reimplement the ratio check
or depend on binaryornot itself). Build side (M5): any CI script that stamps or patches
generated files should copy the same guard so a binary asset is never rendered as a
template.

## Better than Termux's proot-distro?

Honestly: no user-visible edge — Termux ships binary files fine too. The win is
developer-side: our import/export UI will not crash or mojibake on binary files because
the text/binary gate is a deliberate, tested decision rather than a try/except around a
decode.

## Verification refs

- `.../.venv/Lib/site-packages/binaryornot/check.py` (full file, 40 lines), `helpers.py:11,26-38,93-94`
- `.../cookiecutter/generate.py:15,221`
- `METADATA` of `binaryornot-0.4.4.dist-info` (Name/Version/License: BSD)
- `docs/reference/dep-cookiecutter-stack.md` (per-package notes)
