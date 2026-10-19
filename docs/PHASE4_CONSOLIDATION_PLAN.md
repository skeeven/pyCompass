# Phase 4 — Consolidation and Experience

## Status: Stage 1 committed for local verification

This release **begins** Phase 4; it does NOT finish the five priorities.
All changes are limited to `feature/compass-health`. Production is untouched.

### 1. Unified daily check-ins — first compatibility pass

- `compass.unified_daily.UnifiedDailyService` exposes a **single, owner-scoped
  daily read model** composed of the existing `checkins` (Today) and
  `health_daily_logs` (Health) stores.
- Source attribution is retained for every field. Older conflicting
  values are reported as conflicts; the Health value wins for overlapping
  energy/stress/manual sleep on the **read model only**. No historical
  row is removed or silently replaced.
- Saving **Today** now atomically saves the original emotional check-in
  and shared Health energy/stress/manual sleep in one transaction.
  Additional Health fields already saved for that day remain unchanged.
- Saving an **additional Health measurement** uses a transactional merge,
  and updates energy/stress/manual sleep in an *existing* Today check-in.
  It never fabricates an emotional check-in for a date where one did
  not exist.
- Health dashboard, patterns, weekly health review, goal progress, Health
  trends and detailed Health edit form now consume reconciled data.
- The competing quick-entry form inside Health was removed; **Today** is
  the main everyday check-in. Detailed historic and additional Health
  measurements remain available from Health.
- No schema change or destructive backfill is made in this stage. This is
  an **in-place virtual migration with preserved provenance**. A physical
  consolidation of the stored rows is deferred until behavior and
  conflict rules have been tested on real user data, using backup,
  dry-run counts and reversible migration steps.

### 2. Today as home — initial view

- Today shows latest recorded sleep (with source and wake date),
  energy and stress, one configured goal and the next step saved from
  the current weekly health reflection, before the single daily form.
- A future UX pass will improve detail links, optional fields and
  prioritization of cards; this first implementation is intentionally
  small.

### 3. One weekly review — pending

After daily unification is verified, bring mental wellness's optional
AI weekly reflection and Health's metrics/goal reflection onto **one**
screen, protecting all previously saved free-text reflections and
requiring explicit AI consent.

### 4. One Insights destination — pending

Bring mood charts, health patterns, sleep and goal trends under one
insights page with distinct tabs; maintain transparent descriptive
analysis separate from AI observations.

### 5. Settings and Data Management — pending

Move imports, report history, export/deletion and account security into
an organized Settings area. Keep privacy controls prominent and visible.

## Compatibility risks to verify

- Earlier Today-only and Health-only entries may contain different
  measurements for the same calendar date. Review reported conflicts
  before considering physical consolidation.
- A Health-only entry lacks mood data; it must not silently produce a
  fabricated emotional check-in. Original Today form currently requires
  mood and has a default rating. A later UI step should allow a
  truly optional mood without creating artificial observations.
- The original Today table requires a numeric sleep field. Until a safe
  schema migration, the main form still asks for manual sleep; when
  present, imported Sleep Cycle duration takes precedence in reporting.
- Editing additional Health measurements currently **merges** entered
  fields; to clear a specific older value, more explicit clearing
  controls are needed. Do not interpret a blank as zero.
- Original psychological check-ins and private Health logs are still
  distinct database tables despite their unified view and write
  synchronization. Do not describe this stage as a finished physical
  data migration.
- Current week's next step uses the existing Health reflection. Older
  emotional weekly reflections are not lost; merging is pending.

## Local smoke checks

```bash
cd ~/PycharmProjects/pyCompass
source .venv/bin/activate
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

1. On Today, save a mood, energy, stress and sleep check-in.
   Confirm Health Overview and Health → Daily check-in show the same
   energy and stress values without re-entering them.
2. In Health → Daily check-in, add movement and weight for the day.
   Confirm the original mood and journal notes remain unchanged.
3. Edit energy for a day with an existing Today check-in under Health.
   Confirm Today and Health display the new rating.
4. Select a date with imported Sleep Cycle data; confirm the imported
   recording remains read-only and source-attributed.
5. Check Health trends, goal progress, weekly health review and
   personalized insights for data from older Today-only days.
6. If conflicting historical data exists, confirm the Today warning
   and that both underlying source records are preserved.
7. Test two separate accounts and ensure no measurements are shared.
8. Avoid experimenting with deletion or migrations on irreplaceable
   real data; use a backup or disposable test accounts.

**Test status:** Code committed; full local pytest and browser interaction
have not yet been verified. No production deployment or merge is authorized.
