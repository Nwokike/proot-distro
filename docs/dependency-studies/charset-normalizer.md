# charset-normalizer 3.5.2 — exhaustive API reference

Verified 2026-10-16 against the INSTALLED source in
`.venv/Lib/site-packages/charset_normalizer`
(`/home/maikel/.zcode/workspace/default/proot-distro-flet/.venv/Lib/site-packages/charset_normalizer`).
Project context read first: `docs/roadmap.md` + `docs/reference/dep-cookiecutter-stack.md`.
Flet app; flet stays 1.0.4 (D-010).
**Anti-hallucination rule (owner-mandated):** every API claim below cites installed
source (`charset_normalizer/<file>:<line>`) or installed dist metadata; anything not
verifiable in source is labeled **unverified**.

## 1. Identity

- Name/version: `charset-normalizer 3.5.2` (`charset_normalizer/version.py`:
  `__version__ = "3.5.2"`, `VERSION = __version__.split(".")`; dist metadata
  `charset_normalizer-3.5.2.dist-info/METADATA:2-3`).
- Tagline (METADATA:4): "The Real First Universal Charset Detector. Open, modern
  and actively maintained alternative to Chardet." License: **MIT** (METADATA:8).
- `Requires-Python: >=3.7` (verified from dist METADATA). Zero runtime deps
  (no `Requires-Dist` for installs — **unverified** exact wording, check METADATA
  if it matters; nothing is imported outside stdlib + the package itself).
- NOT pure-Python: ships compiled `cd.cp314-win_amd64.pyd` + `md.cp314-win_amd64.pyd`
  accelerators beside the `.py` fallbacks `cd.py`/`md.py` (both present — the `.py`
  files are the fallback when the extension is absent). Rest of the tree:
  `__init__.py`, `__main__.py`, `api.py`, `constant.py`, `legacy.py`, `models.py`,
  `utils.py`, `version.py`, `cli/`, `py.typed`.
- Package exports (`__init__.py:28-51`): `from_fp, from_path, from_bytes, is_binary,
  detect, CharsetMatch, CharsetMatches, __version__, VERSION, set_logging_handler`.
  Default logging: `NullHandler` on the `"charset_normalizer"` logger (:53-54).
- Role here: hard dep of requests (`requests-2.34.2.dist-info/METADATA:34`
  `charset_normalizer<4,>=2`; 3.5.2 inside the ceiling) — the `Response.text` /
  `apparent_encoding` detector of last resort. In OUR venv chardet 5.2.0 is ALSO
  present (via binaryornot→cookiecutter) and requests' `_resolve_char_detection`
  tries **chardet first** (`requests/compat.py`) — so charset-normalizer is the
  declared dep but currently the SECOND choice at runtime. Both satisfy
  `check_compatibility` (`charset_normalizer in [2.0.0, 4.0.0)`).

## 2. Entry points — `charset_normalizer/api.py` (every param)

`from_bytes(sequences, steps=5, chunk_size=512, threshold=0.2, cp_isolation=None,
cp_exclusion=None, preemptive_behaviour=True, explain=False, language_threshold=0.1,
enable_fallback=True) -> CharsetMatches` (:50): "Given a raw bytes sequence, return
the best possible charset[s]". Only `bytes | bytearray` accepted (else `TypeError`).
Empty input → single `CharsetMatch(b"", "utf_8", 0.0, ...)` ("assuming utf_8
intention"). Default strategy: 5 blocks × 512 bytes ("5 blocks of 512o"), give up a
code page after 20% measured mess. SIG/BOM stripped except on UTF-16/32. `explain=True`
attaches a stream handler + TRACE logging (removed on exit).

| Param | Meaning |
|---|---|
| `steps` | How many chunks sampled (default 5) |
| `chunk_size` | Bytes per sample block (default 512) |
| `threshold` | Mess ratio above which a code page is abandoned (default 0.2) |
| `cp_isolation` | Restrict to THESE encodings (debug focus; IANA-normalized) |
| `cp_exclusion` | Exclude THESE encodings |
| `preemptive_behaviour` | Prioritize (never assume) a preemptively-declared encoding (e.g. `<meta charset>`) |
| `explain` | Verbose TRACE logging for debugging a detection |
| `language_threshold` | Minimum language-coherence weight (default 0.1) |
| `enable_fallback` | Fallback guesses when nothing passes (default True) |

- `from_fp(fp, <same knobs>) -> CharsetMatches` (:810): reads (never closes) a binary
  file object, delegates to `from_bytes`.
- `from_path(path, <same knobs>) -> CharsetMatches` (:840): opens path `"rb"`,
  delegates; `IOError` propagates.
- `is_binary(fp_or_path_or_payload, steps=5, chunk_size=512, threshold=0.20,
  cp_isolation=None, cp_exclusion=None, preemptive_behaviour=True, explain=False,
  language_threshold=0.1, enable_fallback=False) -> bool` (:871): "not a string?"
  probe — SAME heuristic engine but fallback DISABLED (stricter on ASCII-compatible
  junk). Accepts path-like, file object, or bytes.
- Module logger: `logger = logging.getLogger("charset_normalizer")` (:32),
  `explain_handler` (:33-34), `TRACE` level constant (:19, custom level below DEBUG).
- Constants (`constant.py`): `ENCODING_MARKS` SIG/BOM table (:11),
  `TOO_SMALL_SEQUENCE = 32` / `TOO_BIG_SEQUENCE = 10_000_000` (:27-28),
  `UTF8_MAXIMAL_ALLOCATION` (:30), `UNICODE_RANGES_COMBINED` (ucd 17.0.0 ranges,
  :33+), `CHARDET_CORRESPONDENCE` legacy rename map (:919+), `RE_POSSIBLE_ENCODING_INDICATION`
  (preemptive-declaration regex — exact line **unverified**).

## 3. `CharsetMatch` — `charset_normalizer/models.py:11-260`

One guess. Constructor `(payload, guessed_encoding, mean_mess_ratio, has_sig_or_bom,
languages, decoded_payload=None, preemptive_declaration=None)` (:12-38).
`__eq__` vs str compares IANA-normalized names (:40-50); `__lt__` (:51-71) =
sort key — chaos first, coherence breaks <0.5% chaos ties, multi-byte usage last;
`__str__` lazy-decodes strict + strips UTF-7 BOM (:81-95); `__repr__`
`<CharsetMatch 'enc' fp(hash)>` (:97).

Properties/methods: `encoding` (:112), `encoding_aliases` (:116),
`bom`/`byte_order_mark` (:129/:133), `languages: list[str]` (:137),
`language: str` (:145: best language or `"Unknown"`; bare ASCII infers `"English"`),
`chaos: float` (:173, = mean mess ratio), `coherence: float` (:177, top language
score or 0.0), `percent_chaos/percent_coherence` (:183/:186),
`raw: bytes|bytearray` (:191, untouched input), `submatch/has_submatch` (:198/:202,
same-decoding alternates via `add_submatch` :100), `alphabets` (:206, detected
Unicode ranges), `could_be_from_charset: list[str]` (:216, self + leaves),
`multi_byte_usage` (:74), `output(encoding="utf_8") -> bytes` (:224: re-encode,
errors ignored→`replace`; patches a preemptive `<meta charset>` header in the
first 8192 chars), `fingerprint: int` (:254, `hash(str(self))`, dedup key).

## 4. `CharsetMatches`, `CliDetectionResult`, legacy `detect`

- `CharsetMatches` (`models.py:261`): sorted-best-first container. `__iter__`
  (sorted), `__getitem__(int|str)` (:280: by position OR by encoding alias via
  `could_be_from_charset`; `KeyError` on miss), `__len__/__bool__`, `append`
  (:301: same-fingerprint+chaos inserts become SUBMATCHES — dedup, skipped for
  >10 MB inputs), `best()` (:321, `None` when empty), `first()` (:330, BC alias).
- `CliDetectionResult` (`models.py:341`): plain record `(path, encoding,
  encoding_aliases, alternative_encodings, language, alphabets, has_sig_or_bom,
  chaos, coherence, unicode_path, is_preferred)` with `__dict__` + `to_json()`
  (:368-389) — the `__main__`/CLI output shape.
- Legacy shim `detect(byte_str, should_rename_legacy=False, **kwargs) -> ResultDict`
  (`legacy.py:18`): chardet-compatible `{"encoding", "language", "confidence"}`.
  `confidence = 1.0 - chaos`, −0.2 on small non-UTF8 samples without BOM;
  `utf_8`+BOM reported as `utf_8_sig`; names mapped through
  `CHARDET_CORRESPONDENCE` unless `should_rename_legacy`; unknown kwargs only
  WARN. "Deprecated… Not planned for removal." `ResultDict` TypedDict
  (`encoding: str|None, language: str, confidence: float|None`) is
  `TYPE_CHECKING`-only.
- Detection engine (`cd.py`, names verified, bodies not): `coherence_ratio` (:410),
  `encoding_languages/mb_encoding_languages/alphabet_languages` (:90/:114/:153),
  `characters_popularity_compare` (:193), `merge_coherence_ratios` (:355),
  `filter_alt_coherence_matches` (:383), `alpha_unicode_split` (:282).
- Char utilities (`utils.py`): `is_accentuated/remove_accent/unicode_range/is_latin/
  is_cjk/is_arabic/…` (:81-215), `identify_sig_or_bom/should_strip_sig_or_bom`
  (:278/:296), `iana_name` (:300), `cp_similarity/is_cp_similar` (:314/:334),
  `set_logging_handler(name, level, format_string)` (:345),
  `cut_sequence_chunks` (:358). CLI entry: `__main__.py` → `cli.cli_detect`
  (function name **unverified** beyond the import line).

## 5. Philosophy vs chardet — why requests switched

chardet = frequency-table statistical classifier (Mozilla heritage): per-encoding
probers vote; strong on long Western text, heavy tables, LGPL-2.1+ licensed
(5.2.0 in our tree — "do not vendor" per dep-cookiecutter-stack.md).
charset-normalizer = mess/coherence measurer: decode-candidate bytes under MANY
codecs, score each by "mess ratio" (control chars, mojibake patterns, unassigned
codepoints) + language coherence against `cd.py` frequency data, rank by chaos.

Why requests switched (2.x era, recorded in requests' compat + changelog —
historical claim, **unverified** from installed source but consistent with the
tree): (a) license — MIT vs LGPL, matters to every downstream packager;
(b) maintenance — chardet was near-dormant for years while charset-normalizer
 iterated; (c) `Response.text` quality — chaos-ranking degrades gracefully on
 short/mixed payloads where single-prober voting misfires; (d) API fit —
 `CharsetMatches.best()/output()` maps directly onto decode-then-serve.
requests keeps the `use-chardet-on-py3` extra + tries chardet FIRST in
`_resolve_char_detection`, so the switch is soft: chardet present → chardet wins;
absent → charset-normalizer. In OUR venv both are installed, so `apparent_encoding`
currently resolves via **chardet 5.2.0**, with 3.5.2 as the pinned fallback.

## 6. How it serves us — host/CI only, never in the APK

Path: `charset-normalizer ← requests (METADATA:34) ← cookiecutter (≥2.23.0) ←
flet-cli (dev group)`. It decodes nothing for us directly — it fires only when
SOME code reads `Response.text`/`apparent_encoding` on a non-UTF8 body without an
explicit `r.encoding`, i.e. inside cookiecutter's template-zip fetch IF a listing
page/registry body needed guessing (the actual zip path streams bytes via
`iter_content` — no decoding involved). Same guarantee chain as the companion files:
`uv.lock` subtree, `pyproject.toml` dev-group-only, on-device stdlib urllib in
`proot_distro/helpers/download.py:42-44`. Detection cost note: `from_bytes`
samples 5×512 B by default — trivial; full-file scans only if a caller raises
`steps/chunk_size` (nobody in our path does).

## 7. How this makes our app better than Termux's proot-distro (honest, concrete)

Termux shell has NO encoding story: `curl | grep`, manifest parsing, and checksum
comparisons assume bytes-are-UTF8 and corrupt or misparse localized registry text
(maintainer names, descriptions, non-ASCII tags). Our host stack gets, for free:

- **Correct text on first read.** Any CI/tooling response decoded via
  `Response.text` lands in the right script instead of mojibake — PyPI/GitHub JSON
  with non-ASCII fields, localized template READMEs, checksum manifests with
  comments in other languages.
- **No LGPL in the story.** chardet's LGPL ("do not vendor") vs charset-normalizer's
  MIT: our transitive detector is the permissive one, matching the project's
  GPL-hygiene posture (M6 tracks proot GPL obligations; we add no new copyleft
  surface via detection).
- **Deterministic fallback order.** chardet-first-then-normalizer is pinned in the
  lockfile; if chardet ever drops out of the tree, `check_compatibility` still
  passes (`[2.0.0, 4.0.0)`) and guesses continue with slightly different names —
  no crash, no behavior cliff. (Name differences ARE real: `detect()` maps them
  via `CHARDET_CORRESPONDENCE`; raw `from_bytes` does not — set `r.encoding`
  explicitly in tooling when the name feeds a codec lookup.)
- Non-goal (honest): zero on-device effect; guest distros, rootfs bytes, and OCI
  layers are byte-exact and never pass through a charset detector.

## 8. Fullest utilization for our tooling — guidance + consistency call

- **Don't add direct uses.** charset-normalizer is a transitive fallback; importing
  it in CI scripts for "detect this file's encoding" is legitimate but rare —
  prefer explicit UTF-8 (`path.read_text(encoding="utf-8")`) for OUR files, and
  `response.encoding = "utf-8"` (or the header charset) before `.text` for HTTP.
  Guessing is for OTHER people's bytes.
- When guessing IS right (unknown third-party text): `from_path(p,
  steps=5).best()` → check `.chaos` (reject > ~0.3?) → `str(match)`; keep
  `explain=True` output in the debug log for the one weird file. `is_binary()`
  gates "text or binary?" decisions (template-file filters, manifest sniffing).
- requests-vs-httpx consistency (companion files §12): httpx does NOT bundle a
  detector — `response.text` there uses `charset_normalizer` ONLY if installed
  (**unverified** for the installed httpx version — check before relying).
  Standardizing new tooling on httpx + explicit encodings keeps detection
  behavior identical on both stacks: guess nothing, declare everything.
- Pin hygiene: `charset-normalizer<4` ceiling (`requests METADATA:34`); bump with
  the `requests+urllib3+charset-normalizer` group. Major v4 (if it renames
  `CharsetMatch` APIs or drops `detect`) breaks requests 2.x resolution first —
  that's the canary, not our code.

## 9. Verification refs

- Installed: `.venv/Lib/site-packages/charset_normalizer` (`__init__.py:28-54`;
  `api.py:19/:32/:50/:810/:840/:871`; `models.py:11/:40/:51/:73/:81/:97/:100/
  :112/:116/:129/:133/:137/:144/:173/:177/:183/:186/:191/:198/:202/:206/:216/
  :224/:254/:261/:280/:301/:321/:330/:341/:368`; `legacy.py:18`;
  `constant.py:11/:27/:33/:919`; `utils.py:39/:81-215/:225/:254/:278/:296/
  :300/:314/:334/:345/:358`; `cd.py:24/:68/:90/:114/:135/:153/:193/:282/:355/
  :383/:410`; `version.py`; `__main__.py`; compiled `cd/md.cp314-win_amd64.pyd`
  + fallback `cd.py/md.py`).
- Dist: `charset_normalizer-3.5.2.dist-info/METADATA` (MIT, `Requires-Python >=3.7`).
- Wiring: `requests-2.34.2.dist-info/METADATA:34`; `requests/compat.py`
  (`_resolve_char_detection`, chardet-first); `requests/__init__.py:60-125`
  (`check_compatibility` range `[2.0.0, 4.0.0)`); `requests/models.py:895,1050`
  (`apparent_encoding`, `text`).
- Context: `docs/roadmap.md` (D3 row), `docs/reference/dep-cookiecutter-stack.md:16,19`
  (bump group, chardet LGPL note).
