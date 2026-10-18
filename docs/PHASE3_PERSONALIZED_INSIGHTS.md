# Phase 3 · Personalized Health Insights (step 1)

The **Health → Overview → Personalized health insights** section presents
deterministic, source-attributed wellness observations. It runs locally in
the Streamlit process; it does not send private wellness information to AI
or create/store new insights in the database.

## Current calculations

- Evaluate the most recent **90 calendar days** ending today.
- Match each night of sleep to the manual daily energy/stress check-in on
  the **same waking date**. Sleep duration uses Compass's unified-night
  policy: Sleep Cycle takes precedence for a night, manual sleep fills gaps.
  Sleep quality requires a real Sleep Cycle quality score.
- Examine four exploratory pairs: sleep hours vs energy, sleep hours vs
  stress, quality % vs energy, and quality % vs stress.
- Require **at least 10 dates with both measurements** per pair. Check
  for actual variation in both metrics before computing Pearson's r.
  A magnitude less than 0.30 is described as *no clear linear pattern*.
  All results are explicitly exploratory, descriptive and non-causal.
- State the number of paired observations for every comparison. Missing
  dates never become zeros. No extra CPAP nightly readings are synthesized
  from overlapping 30-/90-/365-day reports.
- Check-in sparsity can legitimately yield *not enough paired observations*
  even after importing thousands of Sleep Cycle sessions.

## Safety and interpretability

With just ten matched dates, linear associations are highly unstable;
multiple exploratory comparisons can yield spurious results. Do not treat
any displayed association as a diagnosis, medical or treatment advice, or
proof of cause. In future versions consider stronger statistical thresholds,
confidence intervals, seasonality, and opted-in exploration controls before
making suggestions or surfacing unsolicited proactive claims.

## Local validation

```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

Check the new section after **Sleep Health**, plus the empty-data case
using a second test account. Existing imports should remain untouched.
No migrations or production changes are required for this step.
