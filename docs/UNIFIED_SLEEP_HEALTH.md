# Unified Sleep Health (Health → Overview)

A single Sleep Health section replaces the old, separate Sleep Cycle and ResMed
display panels. No historical records are changed, and the production branch
is untouched.

## Reconciliation rules

- **Nightly time asleep**: Sleep Cycle's recorded `sleep_hours` takes priority
  over a manually entered `sleep_hours` on the *same wake-date*. Where Sleep
  Cycle has no measured sleep duration, the manual value is the fallback.
- **Sleep quality**: only a recorded Sleep Cycle nightly percentage is used.
  A manual estimate, ResMed AHI, or sleep-hours entry is never converted into
  a quality percentage.
- **ResMed CPAP**: the latest end date is selected and all available distinct
  reporting windows ending on that date are shown, shortest first. The
  shortest is highlighted in the top summary cards. These are overlapping
  period-wide aggregates, not nightly readings. They never contribute to
  nightly duration averages or chart points.
- **Windows**: 7-, 30-, 90-day sleep summaries include only recorded nights,
  with measurement counts and the number of nights coming from each source.
  Missing nights are not treated as zero.
- **Other wellness checks**: energy, stress, activity, weight, and personal
  goals remain in their own wellness sections. The manual sleep card and
  manual sleep-only chart were removed to avoid duplicate sleep headlines.
- **Privacy**: lookups remain account-scoped. No new persistence is added.
  CSV and ResMed data already imported are reused.

## Verify locally

```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

On Health → Overview, confirm the Sleep Health cards show current sleep
values and source/date captions, each look-back window counts distinct
nights only, the trend offers duration and quality, and the ResMed table
shows 30-/90-/365-day periods where present. Confirm another account sees
none of this user's measurements. This is not a treatment recommendation.
