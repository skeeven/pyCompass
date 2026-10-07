# 🧭 pyCompass

A personal wellness dashboard, guided journal and optional reflective AI
companion built with Python and Streamlit. Start with local SQLite. Connect
SQLiteCloud and OpenAI when you are ready.

The project includes a working first version and a staged implementation plan
in [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md). Stage 1 architecture and
database details are in [docs/FOUNDATION.md](docs/FOUNDATION.md).

## Quick start on your Mac

Unzip the project and open the **pyCompass** folder in PyCharm. In its terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Python 3.11+ is supported by the source; this delivery was tested on Python
3.12.14. If dependencies cause trouble on your Python 3.14 environment, use a
Python 3.12 or 3.13 interpreter for this project. In PyCharm, select the
`.venv/bin/python` interpreter under the project's interpreter settings.

Open the local URL shown in the terminal. Create an account with a username
and a password of at least 12 characters, then sign in. No email address or
API key is needed for check-ins, journaling, charts or the local weekly summary.
The first run creates `data/compass.db` automatically.

## What's included

- Daily mood, energy, stress and sleep check-ins, with optional emotions,
  context tags, needs and daily activity completion.
- Free writing and three guided journal formats.
- Searchable journal history with date/tag filters, editing and confirmed
  deletion.
- Optional AI companion and saved conversations.
- Mood, energy and stress trends over 7, 30 or 90 days.
- On-demand weekly reflection, with a local summary when AI is off.
- Suggested observations you can approve or dismiss.
- JSON export, conversation clearing and account deletion.
- A small daily activity prompt.

Habits, programs, scheduled reminders and months-long pattern detection are
future phases in the plan. This is a local-first foundation, not a hardened
public mental-health service.

## Configure secrets.toml

From the project root:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit that file in PyCharm:

```toml
SQLITECLOUD_URL = ""
OPENAI_API_KEY = ""
OPENAI_MODEL = "gpt-4.1-mini"
DATABASE_PATH = "data/compass.db"
APP_TIMEZONE = "America/Denver"
ALLOW_REGISTRATION = "true"
SESSION_TIMEOUT_MINUTES = "30"
```

The empty values are intentional. Add real credentials only to your local
`secrets.toml`. It is excluded from git. Environment variables with these
names override the file, including empty values.

### SQLiteCloud

1. Create a dedicated empty database, for example `pyCompass`, in your account.
2. Copy its Python-compatible connection string from the connection panel.
3. Put the complete string in `SQLITECLOUD_URL` as a quoted TOML value.
4. Restart Streamlit. The configured account must be allowed to create tables,
   indexes and read/write records in that database.
5. Use disposable accounts to verify both account isolation and deletion.

A connection string has this general shape; use your dashboard's exact value:

```toml
SQLITECLOUD_URL = "sqlitecloud://HOST:8860/pyCompass?apikey=YOUR_API_KEY"
```

A configured cloud connection never silently falls back to local storage.
Adding a cloud URL starts using that database; it does **not** copy existing
local data. Live cloud connectivity was not tested in this delivery.

### OpenAI

1. Create an API key in your OpenAI API account and configure API billing.
2. Set `OPENAI_API_KEY` in `secrets.toml`.
3. Set `OPENAI_MODEL` to an accessible model supporting the Responses API.
   `gpt-4.1-mini` is the default, and can be replaced without changing code.
4. Restart Streamlit. Open Companion, Insights or Weekly reflection.
5. Read the context disclosure and opt in before generating a response.

Chat sends the new message and up to 12 previous messages, not journal entries.
Weekly reflection and observations send seven days of check-ins/notes and up
to 20 journal entries, limited to 2,000 characters each. Check-in context includes emotion/context tags, needs and activity completion.
Those screens show an exact context preview. Requests limit output to 800 tokens.

ChatGPT membership does not pay for this project's API use. Provider calls
were mocked in tests; real model access, billing and response behavior remain
to be verified with your account. No background AI job runs automatically.

## Verify the project

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

`requirements-tested.txt` records the direct dependency versions used in this
validation run. The standard requirements allow compatible updates rather
than locking all transitive dependencies.

## Data and security boundaries

- Passwords use random salts and PBKDF2-HMAC-SHA256 (600,000 iterations).
- Five failed attempts lock an account for five minutes.
- Every wellness operation is scoped to the authenticated user.
- Signing out clears session state; restarting the browser session requires
  signing in again. Idle sessions expire on the next interaction after
  30 minutes by default. There is no password recovery or persistent login.
- Export contains wellness records, not password hashes or API credentials.
- Journal text is not encrypted by this app. Secure your device and backups.
- API requests use `store=False`. That does not guarantee zero provider
  retention. See [OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data).
- Account deletion removes active database records, not backups/provider logs.
- Registration can be disabled after creating your accounts by setting
  `ALLOW_REGISTRATION = "false"` and restarting the app.

Use the initial app locally for personal testing. Before inviting other people
or hosting it publicly, complete the release-hardening phase in the build plan.
Use persistent database storage for a hosted app; ephemeral disks can lose the
local SQLite file. The database tracks schema version 2 and preserves existing records.
Future changes need explicit migrations. No automatic backup is included.

Compass is a reflection tool, not therapy or diagnosis. No person monitors
entries. The UI includes a support notice for immediate danger and U.S. 988
crisis support. AI safety instructions are a guardrail, not a guarantee of
correct crisis handling.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Cannot open database | Local folder permissions, or the exact cloud connection string and privileges |
| AI buttons disabled | An API key is configured and that screen's consent checkbox is selected |
| AI request fails | API billing, model access, network and retry later; entries remain saved |
| Login fails repeatedly | Check username/password and wait five minutes for lockout to expire |
| Entries disappeared after enabling cloud | The app switched databases; local records remain in `data/compass.db` |
| Import error | Activate this project's venv and reinstall the requirements |

## Official references

- [Streamlit secrets](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [Streamlit AppTest](https://docs.streamlit.io/develop/concepts/app-testing/get-started)
- [SQLiteCloud Python driver](https://github.com/sqlitecloud/sqlitecloud-py)
- [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)

These informed the configuration, driver interface and API adapter. They do
not establish that this particular app has clinically validated outcomes.
