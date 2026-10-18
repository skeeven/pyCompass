# Compass Phase 2: Security and Privacy Review

Scope: static code review of branch `feature/compass-health` (October 2026).
This is **not** a penetration test, legal compliance assessment, or validation
of the hosted Streamlit / SQLiteCloud environment.

## Verified in code (positive controls)

- PBKDF2-HMAC-SHA256 password hashing uses random salts and 600,000 iterations.
- Account sign-in has persisted rate limiting (five failures / five minutes).
- Streamlit login sessions expire after inactivity; password changes and
  recovery increment the account's session version.
- Database reads, writes, health reports, and exports scope requests to a user ID.
- Recovery links are hashed at rest, short-lived, purpose-bound, single-use.
- Companion uses explicit consent and only bounded chat history; Insight and
  weekly AI generation require their own consent and show payload previews.
  Requests use `store=False`, which does not eliminate provider retention.
- PDF reports are verified before values are saved; raw PDF files and OCR
  output are not persisted by the app.
- `.gitignore` excludes local database files, data folder, and
  `.streamlit/secrets.toml`.

## Changes made during this review

1. Uploaded PDF filename is replaced by a generic source label before
   storage. This avoids retaining filenames that may contain sensitive
   names, dates, or directory paths. Existing imported filenames remain
   in the database unless separately changed.
2. ResMed OCR rejects empty PDFs and pages whose rendered size would
   exceed a fixed resource ceiling.
3. `Settings.__repr__` no longer includes the SQLiteCloud URL or OpenAI
   key, alongside the previously excluded Zoho client secret and token.
4. Added regression tests for these boundaries.

## Release blockers / work not yet verified

**High: sensitive records at rest.** Wellness text and health profiles are
stored in application-level plaintext JSON/TEXT fields, not encrypted at the
application layer. Confirm SQLiteCloud encryption-at-rest, encryption in
transit, least-privilege access, backup protection and deletion policies
before inviting outside testers. Do not claim HIPAA compliance.

**High: deployment isolation and registration controls.** The source default
allows self-service registration. For a closed beta, deploy to a dedicated
Streamlit app and separate database/API credentials, and keep registration
disabled until a safe invitation/onboarding process is available. Never
point the beta at the production database. Protect all Streamlit app secrets.

**Medium: data lifecycle.** Account deletion removes active rows, not cloud
backups, third-party logs, or data retained by an AI provider. Publish an
accurate privacy notice and retention/deletion expectations before beta.

**Medium: third-party data flows.** Test and document exactly what is sent to
OpenAI and Zoho, and check API-provider settings, privacy disclosures,
regional data handling and access controls. The in-app checkbox is not a
substitute for a full privacy notice.

**Medium: runtime and deployment testing.** This review did not perform a
network vulnerability assessment, test the deployed hostname, inspect
SQLiteCloud grants, validate TLS, verify email delivery end-to-end, or
test the OCR parser on adversarial PDF corpora. Maintain locked compatible
dependencies, inspect vulnerability advisories, and verify cloud backups.

**Medium: session and abuse protections.** Streamlit's in-memory session
state expires on interaction rather than independently revoking browser
connections. Evaluate stronger authenticated routing, public rate limits
and anti-automation controls before any large public release.

## Recommended verification before beta

1. Pull the development branch and run `python -m pytest -q`.
2. Test two independent accounts: check-ins, journals, AI chats, health
   profiles, reports, exports, review history and account deletion.
3. Verify password reset and session revocation in separate browser sessions.
4. Test uploads of valid ResMed reports and malformed/oversized documents.
5. Confirm no private data, PDF filenames or secrets in logs, exported
   screenshots, error pages, repository history, and service dashboards.
6. Set up isolated beta app, credentials, database, backups, and privacy
   policy; conduct a staged test with disposable accounts before inviting
   any real users.

Do not merge or deploy to production until high-priority blockers are resolved.
