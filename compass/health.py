"""Private, user-scoped Compass Health onboarding profiles."""

import json
from datetime import datetime, timezone

ONBOARDING_STEPS = (
    "about_you", "goals", "sleep", "sleep_therapy",
    "health_context", "daily_life", "review",
)
ALLOWED_FIELDS = {
    "age", "height_cm", "starting_weight_lb", "activity_level",
    "priorities", "usual_bedtime", "usual_wake_time", "sleep_quality",
    "uses_cpap", "medications", "supplements", "health_notes",
    "barriers", "personal_time_minutes", "goals", "tracked_goals",
}


class HealthService:
    """Health profiles never cross authenticated user boundaries."""

    def __init__(self, db, user_id):
        self.db = db
        self.user_id = user_id
        with db.connect() as conn:
            if not conn.execute(
                "SELECT 1 FROM users WHERE id = ?", (user_id,)
            ).fetchone():
                raise ValueError("An authenticated account is required.")

    def load(self):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT profile_json, onboarding_step, completed_at "
                "FROM health_profiles WHERE user_id = ?",
                (self.user_id,),
            ).fetchone()
        if not row:
            return {"answers": {}, "step": 0, "completed_at": None}
        return {
            "answers": json.loads(row[0]),
            "step": row[1],
            "completed_at": row[2],
        }

    def save(self, answers, step, completed=False):
        if not isinstance(answers, dict) or set(answers) - ALLOWED_FIELDS:
            raise ValueError("Unknown health profile field.")
        if not isinstance(step, int) or not 0 <= step < len(ONBOARDING_STEPS):
            raise ValueError("Invalid onboarding step.")
        if "tracked_goals" in answers:
            from compass.health_goals import validate_goals
            validate_goals(answers["tracked_goals"])
        encoded = json.dumps(answers, ensure_ascii=False)
        if len(encoded) > 20000:
            raise ValueError("Health profile is too large.")
        timestamp = datetime.now(timezone.utc).isoformat() if completed else None
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO health_profiles
                (user_id, profile_json, onboarding_step, completed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  profile_json=excluded.profile_json,
                  onboarding_step=excluded.onboarding_step,
                  completed_at=COALESCE(
                    excluded.completed_at, health_profiles.completed_at
                  )""",
                (self.user_id, encoded, step, timestamp),
            )
