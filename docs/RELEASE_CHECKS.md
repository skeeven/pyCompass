# Personal-use release checks

Stage 8 prepares the current personal-use deployment. It does not certify a
public multi-user release or replace the hosted-hardening phase in BUILD_PLAN.

## Verified here

- Automated account isolation, consent gates, date windows, saved evidence,
  review decisions, session expiry, export and data lifecycle tests.
- Cloud adapter failures do not fall back to a local database. Successful
  transactions commit; write/commit failures roll back and close connections.
  These checks use a mocked cloud driver, not a live SQLiteCloud database.
- Weekly-reflection deletion now requires explicit confirmation, matching
  journal and observation deletion.
- Mobile CSS reduces outer padding and provides full-width action buttons
  with a minimum 44-pixel height at viewport widths of 640 pixels or less.
  Physical phone layout and touch behavior still require the checks below.
- No schema change or new dependency is introduced by Stage 8.

## User-confirmed deployed checks

- Accounts and existing records are accessible after the earlier cloud fix.
- Companion sends a message and returns a reply (Stage 4).
- Weekly reflection works satisfactorily (Stage 6).
- Personal observation generation and review look good (Stage 7).

## Remaining deployment and phone checks

Use your own account and harmless test text. Do not share credentials or
exports containing personal entries to report results.

| Check | Steps | Pass condition |
| --- | --- | --- |
| Phone layout | Open the deployed app on your phone; visit Today, Journal, Insights, Weekly reflection and Companion | Navigation, labels and buttons are usable; the main page does not scroll sideways. Tables and JSON previews may scroll within their panels. |
| Editing and drafts | Save a short check-in and journal entry; edit the journal; switch screens and return | Saved values remain correct; a journal draft survives screen changes during the same session. |
| Cloud persistence | Record harmless text, sign out, close the browser tab, reopen and sign in | Saved check-in, journal, chat and reflections remain. Session-only drafts are not expected to survive closing the session. |
| Deployment restart | Reboot the app through Streamlit's management controls, then sign in | Earlier saved records remain. A redeploy/reboot must not erase cloud data. |
| Review persistence | Approve an observation, sign out/in, then use Review again | Status remains saved and can return to Pending. |
| Export | Download Export my data (JSON) from Privacy & data | File contains only your account's wellness records. New observation content includes its saved context. |
| Deletion confirmation | Open a saved weekly reflection | Delete reflection stays disabled until its confirmation is checked. No deletion is needed to pass this check. |

## Operational checks still pending

- Confirm a SQLiteCloud backup exists and verify restoration into a separate
  test database before relying on it for recovery. JSON export is a personal
  copy; this app has no export-import restoration feature.
- Live provider timeout, refusal, unavailable-model and billing-failure
  behavior has not been comprehensively checked. Mocked tests do not prove
  those real service behaviors.
- Restrict registration if this is only for existing accounts, using
  `ALLOW_REGISTRATION = "false"` in Streamlit secrets. This is a user choice;
  no deployment configuration is changed by these code updates.
- Before inviting others, complete managed authentication/recovery, session
  revocation, rate limits, backup recovery, retention, privacy and access
  controls, accessibility and companion evaluation from the build plan.

Stage 8 stays in progress until the remaining deployment and phone checks
are reported. Any failures should become concrete fixes before it is closed.
