# Personalized weekly health review

The Weekly review screen summarizes observed sleep and daily check-ins for
the selected Monday–Sunday week, ending no later than today.

Sleep Cycle takes precedence over manual sleep for the same waking date.
ResMed reporting-period aggregates are shown only as context; they are not
treated as nightly measurements. Changes from the preceding week require
two observations per period. Goal progress counts only recorded days in
the selected week. Existing wins, challenges and next-step reflections
remain editable and private.

Test locally:
```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

Review a previous week and the current partial week. Check the separate
sleep-report context, measurement counts, goal totals, and saved reflection.
No production deployment or database migration is included.
