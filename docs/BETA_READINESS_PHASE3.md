# Compass Health — Phase 3 Step 5 Beta Readiness and Security

Review date: October 2026. Scope: **static source review and targeted
hardening on `feature/compass-health`**. This is not a penetration test,
security certification, HIPAA assessment, hosted deployment review, or
a promise that user data cannot be disclosed. Production `main`
and `mycompass.streamlit.app` are deliberately unchanged.

## Code changes in this phase

1. Password verification rejects malformed hashes, unbounded work factors,
   invalid salt/digest lengths and oversized passwords *before* PBKDF2.
   The current encoder issues 600,000-iteration hashes. If a legacy
   installation has a different valid factor, perform a controlled
   migration before shipping this validation.
2. The verified sleep-report saving boundary now rejects boolean,
   NaN, positive and negative infinity measurements. Only finite,
   numeric values within the existing constraints may be saved.
3. `compass.beta_preflight.inspect_beta_configuration(settings)`
   provides redacted, static risk flags for registration, database
   configuration, session timeout and recovery. An empty warning list
   does **not** attest to isolation, database encryption, TLS, privileges,
   service-side retention or actual email delivery.
4. Regression tests exercise these boundaries. They require local
   pytest verification before release.

## Verified by repository inspection (not hosted validation)

- Authenticated account IDs scope wellness data reads and writes.
- PBKDF2 with random salts, account-level failure throttling,
  versioned session revocation, single-use email reset links.
- User-controlled export and account deletion of active app records,
  including daily logs, weekly reviews and imported Sleep Cycle rows.
- Imported report verification, size checks, and minimization of
  raw CSV/PDF retention.
- Separate-source summaries avoid treating overlapping ResMed PDF
  reports as individual nights.
- Streamlit AI features request explicit consent for each invocation.
  Consent does not override external vendor retention.
- `.streamlit/secrets.toml` and `.env` are gitignored.
  This does not prove they were never committed in repository history.

## Blocking conditions before any outside testers

### High — hosting and sensitive-data protection (unverified)

- Create a **new, separate** Streamlit beta app and SQLiteCloud beta
  database with non-production OAuth/email/API credentials or tightly
  scoped credentials; do not point the beta at the existing live DB.
- Confirm SQLiteCloud TLS in transit, encryption at rest, least-privilege
  user access, data-region choices, encrypted backups, backup retention,
  restore testing and operational access logs with the provider.
- Confirm the service host's secret management and deployment access
  permissions. Rotate leaked credentials if any are found.
- Recognize health profiles, daily notes and reflections remain plaintext
  at the application/database field layer. Do not claim end-to-end or
  application-layer encryption.
- For **closed beta**, set `ALLOW_REGISTRATION=false` and establish a
  secure, identity-checked invite/account creation workflow. Simply
  disabling registration is not an invitation system.

### High — privacy, access and lifecycle (unverified)

- Publish a truthful beta privacy notice describing collected records,
  Streamlit and SQLiteCloud hosting, optional OpenAI flows, Zoho email,
  retention, export, account deletion, cloud backups, and contact path.
- Verify verified-email and password reset links end-to-end in the
  isolated beta environment, including session revocation across devices.
- Test two entirely separate beta accounts for denial of cross-account
  access to journaling, chat, health goals, CPAP reports, CSV sessions,
  exports and deletion.
- Confirm account deletion cannot be reversed via active application
  rows; clarify that infrastructure backups and vendor/provider logs may
  persist outside app-layer deletion.

### Medium — operational verification (unverified)

- Run `python -m pytest -q` on the branch and inspect failures/warnings.
- Run dependency vulnerability auditing on the actual resolved environment
  and establish pinned versions/lock-file policy. The requirements currently
  express compatible version ranges, not an immutable lockfile.
- Test upload rejection using empty/oversized/malformed CSV, PDF and
  chart images without enabling uncontrolled resource consumption.
- Check Streamlit error pages, provider logs, database service logs and
  repository history for accidental secrets, filenames and health data.
- Test disaster recovery on disposable data, abuse throttling and endpoint
  session timeout. Streamlit browser-session timeout is interaction-based,
  not instantaneous remote browser revocation.
- Verify accessibility, mobile usability, test-user support and feedback
  capture with fake/sample health records first.

## Recommended staged release decision

**NOT READY for outside beta users.** Static hardening is committed but
test results from the user's Mac, platform configurations, privacy notice,
isolated hosting and actual provider controls remain unverified.

When all high-severity gates have been independently verified, use a
small, explicit-consent test with disposable accounts and fake health data
before inviting any real users. Keep production untouched throughout.

## Local verification

```bash
cd ~/PycharmProjects/pyCompass
source .venv/bin/activate
git pull origin feature/compass-health
python -m pytest -q
python -m streamlit run app.py
```

Check password login/reset flows, Sleep report imports, CSV sessions,
one-week health review, export and deletion. Do not test deletion on
a production account containing irreplaceable records.
