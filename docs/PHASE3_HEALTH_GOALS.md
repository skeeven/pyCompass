# Phase 3, Step 3 — Health Goals and Progress

Existing owner-scoped `tracked_goals` remain in `health_profiles`.
No migration, reimport, or production deployment is required.

## Expanded goals

On Health → My goals, users can set personal targets for:
- Sleep duration and CPAP use (hours)
- Movement and personal downtime (minutes)
- Energy at least a chosen 1–10 rating
- Stress at most a chosen 1–10 rating
- Weight target in pounds (progress toward a lower target)
- Nutrition plan followed: a yes/no daily adherence goal, never a
  calorie calculation or inference from journal text

On Health → Daily check-in → Full health check-in, an optional
**Did you follow your own nutrition plan today?** selector has
**Not recorded / Yes / No** choices. Yes is stored as 1, No as 0;
Not recorded is omitted, so missing data never masquerades as failure.
The user's actual plan and targets are their own choice.

## Progress

Health → My goals supports 7- and 30-day windows. All counts are
among measured days only. The Sleep Cycle nightly duration is used
in preference to a manual sleep log on the same date, and manual
sleep fills gaps. CPAP report-period averages are *never* expanded
into nightly CPAP observations. A manually entered nightly CPAP
value remains a separate measurement.

Energy/sleep/movement/downtime goals use >= target. Stress uses
<= target. Nutrition counts explicit Yes entries as met and explicit
No entries as unmet. Weight displays the earliest and latest
recorded weights for the selected period, the observed change when
two or more measurements exist, and remaining pounds above a chosen
lower weight target. It is not presented as a streak or a guarantee
of achieving weight loss.

Health → Overview also displays source-aware goal progress rather
than sleep counts derived only from manual check-ins.

## Verification

```bash
cd ~/PycharmProjects/pyCompass
source .venv/bin/activate
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

Set an energy target, a movement target, and optionally a personal
weight or nutrition goal. Record a daily Yes/No nutrition answer
and verify missing days remain uncounted. Toggle 7-/30-day windows.
Confirm that Sleep Cycle entries count for sleep goals while ResMed
period averages do not count as daily CPAP goal completion.
Check that private accounts cannot read each other's goals or logs.
