# Stage 1: project foundation

The foundation is implemented. It runs locally with no service credentials,
and can select SQLiteCloud through configuration. The UI, account services and
data access are separate so later features do not need to rewrite login logic.

## Project structure

| Path | Role |
| --- | --- |
| `app.py` | Streamlit screens, configuration errors and access checks |
| `compass/config.py` | Secrets/environment settings and validation |
| `compass/db.py` | Connections, transactions and schema version baseline |
| `compass/auth.py` | Registration, password hashing and login throttling |
| `compass/session.py` | Login state and inactivity expiry |
| `compass/repository.py` | Account-scoped records, export and deletion |
| `compass/reflection.py` | Prompt content and optional AI calls |
| `.streamlit/secrets.toml.example` | Credential-free configuration example |
| `tests/` | Service and Streamlit workflow checks |

## Database design

| Table | Stored information | Ownership / key |
| --- | --- | --- |
| `users` | Username, salted password hash, lockout and creation time | Account UUID; unique normalized username |
| `checkins` | Local date, mood, energy, stress, sleep and note | Account UUID; unique account/date |
| `journal` | UTC creation time, title, body and tags | Account UUID and entry UUID |
| `messages` | UTC creation time, role and chat text | Account UUID and message UUID |
| `insights` | UTC creation time, suggestion/reflection and review status | Account UUID and insight UUID |
| `schema_migrations` | Applied schema version and timestamp | Internal metadata; excluded from user export |

All wellness reads and mutations include the current account id. A record UUID
alone cannot grant access to another account's entry. Table names are fixed;
record values are parameterized. Password hashes never appear in wellness exports.

Schema version 1 records the original layout. Existing unversioned Compass
databases are adopted without replacing records. Initialization is repeatable.
An older app refuses a database marked with a newer schema version. No data
transformation is needed for this baseline; future schema changes require new,
ordered migration steps and a tested backup/restore procedure.

## Account and session behavior

Usernames use 3–32 lowercase letters, numbers or underscores. Passwords use
12–256 characters and are hashed with salted PBKDF2-HMAC-SHA256. Five failed
attempts lock that account for five minutes. This account lockout is not a
replacement for distributed rate limiting in a public deployment.

Signing in clears prior session data. Signing out or expiring a session clears
the whole Streamlit session, including drafts and consent flags. The default
inactivity limit is 30 minutes. Set `SESSION_TIMEOUT_MINUTES` to a whole number
from 1 to 1440. Expiration is enforced on the next interaction; the app does not
blank an unattended screen automatically or remove already downloaded exports.

After creating intended accounts, set `ALLOW_REGISTRATION = "false"` to hide
registration and reject registration through the service as well. Password
recovery, remembered logins and managed identity are not part of this stage.

## Configuration failures

The app validates timezone, registration flag, session timeout, the cloud URL
scheme, model name and local database path before proceeding. Invalid settings
produce a concise error without echoing credential values. A configured cloud
connection cannot silently fall back to the local database.

## Next stage

Refine Today: choose check-in labels, optional emotion/context tags and the daily
activity experience. Keep the default check-in short enough to use every day.
Cloud initialization, live AI and phone/browser testing remain separate gates.
