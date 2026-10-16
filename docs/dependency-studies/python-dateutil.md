# python-dateutil 2.9.0.post0 — datetime extensions

Identity: python-dateutil 2.9.0.post0, dual-licensed (`METADATA` License: Dual License;
BSD-3 + Apache-2.0, `License-File: LICENSE`), pure Python. Modules in
`dateutil/`: `parser`, `rrule`, `relativedelta`, `tz`, `easter`, `utils`, `tzwin`,
`zoneinfo` (ships `dateutil-zoneinfo.tar.gz` + `rebuild.py`). Arrow's parser/tz engine.

## Complete public API (by module, signatures introspected)

- `dateutil.parser.parse(timestr, parserinfo=None, **kwargs) -> datetime` — fuzzy,
  free-form parsing (`"Oct 16 2026 10am"`, RFC strings); `parser.isoparse(dt_str)` —
  strict ISO-8601; `parser.parserinfo` for locale customization.
- `dateutil.relativedelta.relativedelta(dt1=None, dt2=None, years=0, months=0, days=0,
  leapdays=0, weeks=0, hours=0, minutes=0, seconds=0, microseconds=0, year=None, ...,
  weekday=None, ...)` — calendar-aware deltas (months/years, nth-weekday); add to a
  datetime or diff two datetimes.
- `dateutil.rrule.rrule(freq, dtstart=None, interval=1, wkst=None, count=None, until=None,
  bysetpos=, bymonth=, bymonthday=, byyearday=, byeaster=, byweekno=, byweekday=, byhour=,
  byminute=, bysecond=, cache=False)` — RFC-2445 recurrences; `YEARLY/MONTHLY/WEEKLY/
  DAILY/HOURLY/MINUTELY/SECONDLY` + `MO/TU/WE/TH/FR/SA/SU` constants; `rruleset`/`exrule`
  for inclusion/exclusion sets.
- `dateutil.tz`: `tzutc()`, `tzlocal()`, `gettz(name)`, `tzfile`, `tzical` (parse .ics
  VTIMEZONE), `tzrange/tzstr`, `tzwin/tzwinlocal` (Windows), `datetime_ambiguous`,
  `datetime_exists`, `resolve_imaginary`, `enfold`.
- `dateutil.easter.easter(year, method=3)` — Western/Orthodox/Julian Easter; `dateutil.utils`
  (`today`, `default_tzinfo`).

## Example

```python
from dateutil import parser, relativedelta, rrule
print(parser.parse("Oct 16 2026 10am"))  # free-form guest-log timestamps
from datetime import datetime
print(datetime(2026, 1, 31) + relativedelta.relativedelta(months=+1))  # 2026-02-28, calendar-aware
print(list(rrule.rrule(rrule.WEEKLY, dtstart=datetime(2026, 10, 16), count=3)))  # backup schedule
```

## How cookiecutter/flet uses it

Transitively: arrow requires `python-dateutil>=2.7.0`, so every `{% now %}` render and
every `Arrow.shift/to` call runs on dateutil's parser and tz machinery. No direct
cookiecutter import (verified: no `dateutil` import in `cookiecutter/*.py`).

## Our-project utilization (M4/M5)

Parsing side to arrow's formatting side: guest/system timestamps in odd formats
(`apt` history, backup manifests) go through `parser.parse`/`isoparse`; expiry and
retention math uses `relativedelta` (months-aware, unlike `timedelta`); any scheduled
job (log rotation, backup reminders in M5+) uses `rrule`. Prefer `isoparse` for
machine-generated stamps (strict, fast) and `parse` only for human/guest text.

## Better than Termux's proot-distro?

No direct user edge; robustness edge: log/report timestamps parse instead of crash on
unexpected formats, and month-aware retention math is correct where naive day-counts
drift.

## Verification refs

- Live introspection: `parser.parse/isoparse`, `relativedelta.__init__`,
  `rrule.__init__`, `easter.easter` signatures; module listing of `dateutil/`
- `arrow-1.4.0.dist-info/METADATA` (`Requires-Dist: python-dateutil>=2.7.0`)
- `python_dateutil-2.9.0.post0.dist-info/METADATA` (Dual License)
