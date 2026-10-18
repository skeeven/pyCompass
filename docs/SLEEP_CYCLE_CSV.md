# Sleep Cycle CSV import (local Compass development)

The actual Sleep Cycle database export is a **UTF-8, semicolon-delimited CSV**
with 28 headings. The example supplied for development had 3,555 lines of
sessions with 9 exact duplicate timestamp pairs (3,546 distinct sessions).
Never commit the user's CSV or its raw fields to Git.

## Import

1. Open Health → Sleep report imports.
2. Select Sleep Cycle → CSV database export (recommended).
3. Upload the original `.csv`; conversion to PDF is not necessary.
4. Review distinct sessions, duplicate counts, and the latest ten rows.
5. Explicitly confirm and click **Import new sessions**.

The new `sleep_cycle_sessions` table is installed by migration version 5.
It stores **only** session start/end (as exported in local clock time),
the date of waking, Sleep Quality percentage, Time asleep (hours), and
Time in bed (hours). City, notes, heart rate, body temperature, mood,
and other fields are ignored. Raw CSV bytes are not retained.

Identical session start/end timestamps are deduplicated within an uploaded
file and across prior imports for the same signed-in account. Reimporting
the same file does not overwrite prior values. CSV sessions are separate
from ResMed multi-day CPAP aggregates and manual Sleep Cycle chart
period reports.

## Review and removal

Open Health → Sleep Cycle history, then choose a 7-, 30-, 90-, or
365-day window. The chart and mean use **actual measured sessions**
only; unrecorded days are not zero-filled. The Remove section provides
a confirmation-gated operation to delete all this user's CSV sessions.
The normal account export includes the sessions; full account deletion
removes them.

## Boundaries

- Timestamps are recorded without a timezone in this export. The importer
  preserves their local wall-clock values and assigns each session to the
  date its sleep ended, rather than inferring a UTC offset.
- 0 seconds of recorded sleep are interpreted as unknown/missing instead of
  as zero hours to avoid spurious averages. No medical interpretation is made.
- A successful parse and unit tests do not replace a real local import test,
  especially when using a remote SQLiteCloud connection.
- Individual nightly values are not automatically copied into manually
  entered Health Daily check-ins or blended with report-period aggregates.

Test locally:

```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```
