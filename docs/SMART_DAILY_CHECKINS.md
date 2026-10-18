# Phase 3 · Step 2: smarter daily check-ins

In **Health → Daily check-in**, choose a date. Compass retrieves only the
signed-in user's Sleep Cycle sessions whose **wake date** equals that date.

- Imported sleep time and sleep quality are displayed as *read-only* context.
- The quick form asks for **Energy, Stress, and Movement**, instead of
  asking the user to type imported sleep again.
- The expanded full editor retains an **optional manual sleep** field for
  overrides and gaps. It never changes imported recordings.
- A quick save merges its newly entered values with the saved manual log,
  preserving other existing manual fields. Imported sleep values are not
  copied into the manual log.
- Missing or unavailable recordings show a neutral explanation, not a zero.
- If multiple sessions ended on one day, display total time asleep and an
  hours-weighted sleep-quality percent only if every session has valid
  quality and duration. Otherwise the quality value is hidden.
- The unified Sleep Health overview still applies its separately tested
  preference for Sleep Cycle sleep duration over manual sleep on the same
  wake date. ResMed PDF period summaries remain separate.

No schema changes, reimport, data migration, or production deployment.

Local check:
```bash
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```
Navigate to Health → Daily check-in; choose a date with a previously imported
Sleep Cycle session, save only Energy and Stress, then verify the original
Sleep Cycle session remains unchanged and the manual log has no imported
sleep field.
