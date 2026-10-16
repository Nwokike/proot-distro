# arrow 1.4.0 — better dates and times

Identity: arrow 1.4.0, Apache-2.0 (`METADATA` classifier `License :: OSI Approved ::
Apache Software License`), pure Python. Requires `python-dateutil>=2.7.0` and
`tzdata` on py3.9+ (its own `METADATA Requires-Dist`) — the arrow+dateutil+tzdata bump
group (dep-cookiecutter-stack.md).

## Complete public API

Module factories (`arrow/__init__.py`, signatures introspected):
- `arrow.get(*args, **kwargs) -> Arrow` — parse almost anything: datetime, timestamp,
  ISO/foreign string (+ format args), struct_time.
- `arrow.now(tz=None) -> Arrow`, `arrow.utcnow() -> Arrow` — current time, optional tz.

`Arrow` instance methods (full member list introspected; key signatures verified):
- `shift(self, check_imaginary=True, **kwargs) -> Arrow` — relative move
  (`days=`, `hours=`, `weeks=`, `months=`, …); powers cookiecutter's `{% now %}` offsets.
- `format(self, fmt="YYYY-MM-DD HH:mm:ssZZ", locale="en-us") -> str` — token formatting.
- `humanize(other=None, locale="en-us", only_distance=False, granularity="auto") -> str` —
  `"3 hours ago"`.
- `to(self, tz) -> Arrow` — convert zone (tz name or tzinfo); `astimezone`, `replace`,
  `floor`/`ceil`/`span`/`span_range`/`range`/`interval` for rounding and iteration.
- stdlib bridges: `datetime()`, `naive`, `date()`, `time()`, `timetuple()`, `utcoffset()`,
  `isoformat()`, `strftime()`, `strptime()`, `for_json()`, `timestamp()`,
  `int_timestamp`/`float_timestamp`, `fromdatetime/fromdate/fromtimestamp/utcfromtimestamp/fromordinal`,
  `is_between/min/max`, `dehumanize`, `isocalendar/isoweekday/weekday`.
- `ArrowFactory` (`arrow/factory.py`): `get`, `now`, `utcnow` — same factories as methods.

## Example

```python
import arrow
stamp = arrow.now("Africa/Lagos").format("YYYY-MM-DD HH:mm:ssZZ")
print(arrow.get("2026-10-16T10:00:00+01:00").shift(hours=+2).humanize())  # "in 2 hours"
```

## How cookiecutter/flet uses it

`cookiecutter/extensions.py:12` (`import arrow`); `TimeExtension._now` calls
`arrow.now(timezone).strftime(...)` (`extensions.py:141-144`) and `_datetime` parses
`{% now 'tz' + 'days=1,hours=2' %}` offsets through `d.shift(**shift_params)`
(`extensions.py:128-137`). This is the `{% now %}` tag. M5 note: unpinned
`arrow.now(timezone)` reads the host clock/IANA db at build time — fine for stamps.

## Our-project utilization (M4/M5 reports and logs)

Every timestamp the app shows: install-history entries, session logs, report headers —
`arrow.now(<device tz>).format(...)` for display plus `.humanize()` for friendly relative
times ("installed 3 days ago"). `shift()` computes retention windows (prune logs older
than N days). Keep arrow+dateutil+tzdata bumped as a group; on Android the tz database
comes from this chain, not the OS.

## Better than Termux's proot-distro?

Marginal user win: consistent, locale-correct timestamps in install history and logs
instead of raw epoch/ISO strings. Tooling-side consistency win.

## Verification refs

- Live introspection: `arrow.__version__` 1.4.0; `inspect.signature(arrow.get/now/utcnow,
  Arrow.shift/format/humanize/to)`; `ArrowFactory` members; `METADATA Requires-Dist`
- `.../cookiecutter/extensions.py:12,113-144`
- `docs/reference/dep-cookiecutter-stack.md` (arrow+dateutil+tzdata bump group)
