# tzdata 2026.5 — IANA time-zone database

Identity: tzdata 2026.5 (IANA release 2026e: `__init__.py` sets `__version__ = "2026.5"`,
`IANA_VERSION = "2026e"`), Apache-2.0 (`METADATA` License: Apache-2.0). Data-only:
`tzdata/zoneinfo/` tree (Africa, America, Asia, …) + `tzdata/zones` index; the
`tzdata/__init__.py` is ~8 lines. No code API beyond version constants — it exists so
`zoneinfo.ZoneInfo` finds data.

## Complete public API

- `tzdata.__version__` (`"2026.5"`), `tzdata.IANA_VERSION` (`"2026e"`).
- Data contract: `importlib.resources`-addressable `tzdata.zoneinfo/<Region>/<City>`
  files consumed by stdlib `zoneinfo` (and by dateutil/arrow through it).
- Usage pattern (stdlib, not tzdata code): `from zoneinfo import ZoneInfo;
  ZoneInfo("Africa/Lagos")` — works on hosts without a system tz database *because*
  this package is installed. That is the entire interface.

## Example

```python
from zoneinfo import ZoneInfo
from datetime import datetime
lagos = datetime.now(ZoneInfo("Africa/Lagos"))  # works with no OS tzdata present
print(lagos.strftime("%Y-%m-%d %H:%M %Z"))
```

## How cookiecutter/flet uses it

Transitively: arrow's `METADATA` requires `tzdata; python_version>='3.9'`, so any
`arrow.now("<named zone>")` inside a `{% now %}` tag resolves through this database on
hosts (Windows CI, minimal containers) that lack system zoneinfo. No direct import
anywhere in cookiecutter.

## Our-project utilization (M4/M5)

Android ships no usable IANA database to Python, and device OEM zones vary — bundling
tzdata (via the arrow chain) makes every `ZoneInfo`/arrow timestamp in install history,
session logs, and reports deterministic across devices. M5 ritual: bump tzdata with
arrow+dateutil as a group (IETF/DST rule changes ride IANA releases; 2026.5/2026e is
current as of this study).

## Better than Termux's proot-distro?

Reliability edge on odd devices: correct local-time display and DST handling without
depending on the OEM's system tz data. Invisible when right, confusing when wrong —
worth the free dependency.

## Verification refs

- `.../tzdata/__init__.py` (full file); `ls tzdata/zoneinfo` (Africa, America, …)
- `arrow-1.4.0.dist-info/METADATA` (`Requires-Dist: tzdata; python_version>='3.9'`)
- `tzdata-2026.5.dist-info/METADATA` (Apache-2.0)
