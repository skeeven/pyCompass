# pyCompass build plan

## Purpose

Create a personal wellness app that helps adults notice feelings, reflect on
experiences, and choose manageable actions. Compass is an original product,
not a reproduction of Liven's content or interface. It is a self-reflection
tool, not a diagnostic service or a substitute for therapy.

## Decisions for the first version

- Working project name: `pyCompass`. Rename before public release if desired;
  availability of the name has not been checked.
- Stack: Python 3.11+, Streamlit, SQLite or SQLiteCloud, optional OpenAI API.
- Local SQLite is the default so setup does not depend on external accounts.
- Credentials come from `.streamlit/secrets.toml` or environment variables.
- Timezone defaults to America/Denver for calendar days.
- Individual accounts; no access to someone else's wellness records in the UI.
- AI runs only on a user request with consent on that feature's screen.
- Keep the layout narrow and forms simple for phone use. Actual iPhone browser
  testing remains a release check.

## First-version scope and acceptance criteria

| Feature | Acceptance criterion | Status |
| --- | --- | --- |
| Accounts | Create account, sign in, sign out; salted password hashes and login throttling | Implemented |
| Daily check-in | Mood, energy, stress, sleep and note; one editable record per local day | Implemented |
| Guided journal | Free writing plus three prompt sets; save title, body and tags | Implemented |
| Journal history | Search, view and delete owned entries | Implemented |
| AI companion | Reflective chat; bounded recent conversation context; no journals silently attached | Implemented; provider call mocked in tests |
| Trend dashboard | 7-, 30-, 90-day mood/energy/stress chart; no invented missing days | Implemented |
| Weekly reflection | Local numeric summary; optional AI reflection of a selected seven-day period | Implemented; provider call mocked in tests |
| Personal insights | Dated AI suggestions with approve/dismiss controls | Implemented; provider call mocked in tests |
| Privacy controls | Export wellness records, clear chat, delete account | Implemented |

The daily activity is a small deterministic prompt, not AI personalization.
Weekly reflections are generated on demand, not on a schedule.
Insights currently use a seven-day window; months-long pattern detection is
planned. Approving a suggestion saves its status, but does not automatically
make it part of future AI prompts.

## Architecture

`app.py` renders the screens and gates access to AI. It loads configuration,
checks the signed-in session and delegates to services.

| Module | Responsibility |
| --- | --- |
| `compass/config.py` | Environment and Streamlit secret configuration |
| `compass/db.py` | Short-lived connections, transactions, initial schema |
| `compass/auth.py` | Registration, PBKDF2 hashes, account login lockout |
| `compass/repository.py` | Owned record reads, writes, export and deletion |
| `compass/reflection.py` | Prompt sets, bounded context, API adapter |
| `tests/` | Account isolation, data lifecycle, AI contract and UI workflows |

Data tables are `users`, `checkins`, `journal`, `messages`, and `insights`.
Identifiers are UUIDs. Timestamps are stored in UTC; weekly journal filtering
converts them into the configured local timezone. Check-ins use local dates.
All wellness queries include the authenticated account id. SQL values use
parameters; dynamic table names come only from a fixed allowlist.

## Roadmap and gates

### Phase 1 — Run and personalize this foundation

Deliverables: this project, setup guide, tests, and the first eight features.
Run locally, create a test account, record check-ins and entries, and verify
export and deletion using disposable data. Then try it on a phone and revise
forms based on actual use.

Exit gate: a complete check-in/journal/review cycle is useful and comfortable,
and records survive restarts.

### Phase 2 — Connect the services

Create an empty SQLiteCloud database and use a dedicated credential scoped to
that database. Test initialization, parameterized queries, upserts, transactions,
and account isolation against the real service. No automatic local fallback is
allowed when the configured cloud connection fails.

Configure an OpenAI key, confirm model access and billing, preview context,
and make a short test conversation and reflection using nonsensitive entries.
Check timeouts, unavailable models, provider refusal and billing failures.

Exit gate: service tests pass and the user understands exactly what is stored
and sent. Local and cloud databases are separate; adding a URL does not migrate
existing local records. A deliberate migration utility is future work.

### Phase 3 — Daily usefulness

Add habits, small goals, completion logs, a 7-day introductory program and
optional reminders. Define the user's preferred reminder channel before
implementing delivery. Extend the schema version baseline with explicit migration steps before
changing the schema.

Exit gate: a week of use requires little effort, and reminders are optional.

### Phase 4 — Longitudinal understanding

Add monthly summaries and evidence-linked observations across multiple weeks.
Require sufficient data, show source dates, distinguish co-occurrence from
causation, and retain user approval/dismissal. Allow corrections to an observation.
Use approved observations as AI context only with an explicit choice. Avoid
interpreting a missing check-in as a bad day.

Exit gate: every suggested pattern is traceable to actual records, and the user
can reject or correct it.

### Phase 5 — Hosted release hardening

Before public multi-user deployment: replace or strengthen authentication with
managed identity, password recovery, server-enforced session revocation and distributed rate limits;
restrict account creation; implement deployment monitoring without journal text;
test backup restoration; implement retention and encryption controls; define a
privacy policy and hosting access controls. Add accessibility and real mobile
browser checks. Evaluate the companion's crisis behavior and misleading advice
with a dedicated adversarial test set and human review.

Exit gate: a security/privacy review and a verified hosted configuration.
No deployment is included in this project delivery.

## Verification

Tests cover salted hashes, login lockout, registration validation, check-in
upserts, cross-account reads/mutations, account deletion, export, weekly timezone
boundaries, bounded AI requests, SQL allowlisting, and Streamlit screens/forms.
Live provider, live SQLiteCloud, production security and physical phone testing
are separate gates rather than claims made by the local tests.

## Cost and privacy choices

Local journaling does not require an AI subscription or paid API. OpenAI API
billing is separate from ChatGPT subscriptions; charges depend on the configured
model and usage. The UI bounds each request's context and output, but does not
enforce a monthly spending cap. Set budget alerts in the provider account.

Passwords are hashed; journal text is stored as readable database content.
Protect the database file, machine, cloud credentials and backups. `store=False`
disables stored API responses but does not guarantee zero provider retention.
Deletion removes active app records; backup and provider-log retention follow
their own policies. No advertising or third-party analytics SDK is included.

## Stage 1 update

Configuration validation, idle session expiry and schema version tracking are
implemented. See [FOUNDATION.md](FOUNDATION.md) for the database design and
current authentication boundaries. Registration and login are also tested
through the actual Streamlit forms.

## Stage 2 update

Today now includes optional emotion/context tags, a needs prompt, rating anchors
and an activity completion checkbox. One save records the whole check-in.
Schema version 2 adds these fields with empty defaults and preserves all earlier
records. Weekly AI context includes these fields after the existing consent step.

## Stage 3 update

Journal drafts now clear only after a successful save. Guided prompts can be
skipped, and saved tags are trimmed and deduplicated. History includes text
search, local date windows, tag filters and a matching entry count. Users can
edit their own entries while preserving original timestamps. Deletion requires
a confirmation checkbox. These changes use the existing schema version 2.
Drafts remain session-only and are cleared on sign-out or session expiry.
