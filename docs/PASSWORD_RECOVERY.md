# Password recovery and account security

Compass now supports a verified recovery email, Forgot password on the sign-in
screen, and Change password under Account security. Zoho delivers these messages
over HTTPS with OAuth. Real email delivery and the live SQLiteCloud migration
still need verification after deployment; automated tests use a fake mailbox.

## Streamlit secrets

Use top-level entries in Streamlit's Secrets settings (or the local
`.streamlit/secrets.toml`). Keep credentials out of GitHub:

```toml
ZOHO_CLIENT_ID = "your-client-id"
ZOHO_CLIENT_SECRET = "your-client-secret"
ZOHO_REFRESH_TOKEN = "your-refresh-token"
ZOHO_ACCOUNT_ID = "your-numeric-account-id"
MAIL_FROM = "compass@mightymiraclemax.com"
APP_BASE_URL = "https://mycompass.streamlit.app/"
ZOHO_DOMAIN = "com"
```

`ZOHO_ACCOUNT_ID` is the numeric `accountId` returned by Zoho's Get All User
Accounts API, not the mailbox name. The refresh token needs the
`ZohoMail.messages.CREATE` scope. `MAIL_FROM` must belong to the authenticated
Zoho account. `ZOHO_DOMAIN` defaults to `com`; use the region where the OAuth
client and mailbox were created (`eu`, `in`, `com.au`, `jp`, `ca`, `com.cn`, or
`sa` as appropriate). A token from a different region will not work.

If any required delivery entry is empty, email recovery is disabled. Existing
users can still sign in and change their password. The optional email features
do not require a new Python dependency.

## Existing and new accounts

Existing users keep their usernames, password hashes, and wellness records.
They can sign in, open **Account security**, enter a recovery email and their
current password, then select **Send verification link**. The address becomes
usable for recovery only after they open the email and select **Verify my email**.

When email delivery is configured, new accounts must verify an email before
accessing wellness screens. If delivery fails, their account still exists: they
can sign in to Account security and request another verification link. An
unverified user cannot access the other screens. A replacement address becomes
active only after verification, and one verified address belongs to one account.

A user who forgot their password before enrolling a verified email needs
identity-verified assistance from the app owner. There is no blank-password
bypass or self-service claim of an existing account by an unverified email.

## Link and session behavior

- Tokens contain 32 random bytes, are stored only as SHA-256 fingerprints, expire
  after 30 minutes, and work once. Opening the URL alone does not redeem it.
- The app clears the token from query parameters and requires a confirmation.
  Email providers and browser history may still retain the original link.
- A new link replaces earlier links for that account and purpose. Successful
  verification, reset, or password change invalidates outstanding account links.
- Reset requests return the same message for known, unknown, and unverified
  addresses. Delivery runs in a background thread to avoid provider latency
  revealing whether an account exists; this is not a claim of identical timing.
- Reset requests are limited to five per email per hour, at least 60 seconds
  apart, and 100 globally per hour. Verification uses the same limits per user
  and globally. Counters persist in the database across app sessions.
- Passwords require 12–256 characters. A reset clears the login lockout.
  Password changes require the current password and sign the user out.
- Verification and password changes increment a database session version.
  Earlier signed-in sessions are rejected on their next interaction. Already
  rendered pages are not remotely erased.
- Password-change notices contain no password or reset credential. Notice
  delivery failures do not undo a completed change. Failed link delivery
  invalidates that token and logs a generic message without mailbox or API data.
- The background queue is in memory. Restarting Streamlit can interrupt a queued
  email; request a fresh link after the cooldown if it does not arrive.

Email addresses and tokens are excluded from wellness exports and AI prompts.
Deleting an account also removes its security and token records; backup and
provider retention remain governed by those services.

## Database upgrade

Schema version 3 creates `account_security`, `account_tokens`, and
`account_limits`, plus a token-owner index. It seeds security rows for existing
users with email verification optional. It does not alter wellness tables.
Initialization runs this migration once and records version 3. The cloud
credential must permit table and index creation and ordinary reads/writes.

The SQLiteCloud Python driver's default is autocommit, so the app now explicitly
starts each database unit with `BEGIN` and completes it with `COMMIT` or
`ROLLBACK`. This makes token redemption and password/session changes one unit.
Tests emulate the driver's autocommit behavior; live cloud transaction support
and privileges remain part of the deployment check.

If initialization reports Cannot open the database, check cloud permissions
and the selected `myCompass` database first. Do not drop tables or clear password
hashes. Obtain the failure context from the hosting logs without sharing secrets.

## Deployment check

1. Wait for Streamlit to update from GitHub, or reboot the app if necessary.
2. Sign in with an existing account and confirm its records remain visible.
3. Add and verify your recovery email under Account security.
4. Sign out, open Forgot password, and request a reset with that verified email.
5. Open the message, set a new password, and confirm it signs in with the same
   records. Confirm the old password fails and the used link is rejected.
6. In a second signed-in browser session, confirm its next interaction returns
   to sign-in after a reset or password change.
7. With a disposable new account, confirm verification gates the wellness
   screens. Check inbox and spam delivery on a phone as well.

If messages fail, check the Zoho region, numeric account ID, sender ownership,
and refresh-token scope. The app deliberately does not display raw provider
responses or credentials. Live acceptance is pending until these checks pass.

## References

- [Zoho Send Email API](https://www.zoho.com/mail/help/api/post-send-an-email.html)
- [Zoho Get All User Accounts](https://www.zoho.com/mail/help/api/get-all-users-accounts.html)
- [SQLiteCloud transaction documentation](https://docs.sqlitecloud.io/docs/sqlite/lang_transaction)
- [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)
