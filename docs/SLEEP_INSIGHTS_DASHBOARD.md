# Sleep insights dashboard

Compass Health → Overview displays a Sleep Cycle section sourced only from
imported nightly CSV sessions, followed by a separately labeled ResMed CPAP
report-period summary.

## Sleep Cycle nightly records

- Latest recorded quality and time asleep (not necessarily yesterday).
- Averages over the previous 7, 30, and 90 calendar days, anchored to
  today's date, with session and measurement counts. Missing sessions and
  missing values are excluded, never interpreted as zero.
- Two *disjoint* seven-day windows for descriptive changes in sleep quality
  (percentage points) and time asleep (minutes).
- Nightly quality or duration chart over 7, 30, or 90 days, plotting only
  recorded sessions. Multiple sessions on one date remain separate readings.
- Typical bedtime and wake time during the past 30 days, plus mean absolute
  difference from each typical clock time. Bedtimes straddling midnight
  use circular unwrapping rather than a mathematically misleading noon
  average. Times remain the local clock times from Sleep Cycle's CSV;
  no original timezone offset is reconstructed.

## ResMed CPAP

The latest verified ResMed CPAP reporting period is presented separately
from Sleep Cycle nightly sessions. AHI and CPAP usage are *period aggregates*.
They are never combined with Sleep Cycle values or manual daily logs.

## Limitations

These are descriptive, self-tracked trends, not diagnoses, sleep studies
or evidence of a causal relationship between CPAP usage and sleep quality.
The dashboard doesn't claim a medically meaningful change based on
different reporting periods or uneven recording frequency. Clock consistency
summarizes recorded sessions only.

## Local test

```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

Open Health → Overview after importing a Sleep Cycle CSV. Confirm the latest
session, the recorded-session counts, chart windows, and your ResMed report.
Test with an account with no Sleep Cycle entries to confirm private empty
states. No production deployment is involved.
