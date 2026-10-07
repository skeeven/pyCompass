"""Journal formatting and local calendar filtering."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def normalize_tags(text):
    """Trim comma-separated tags and remove case-insensitive duplicates."""
    tags = {}
    for tag in text.split(","):
        tag = tag.strip()
        if tag:
            tags.setdefault(tag.casefold(), tag)
    return ", ".join(tags.values())[:300]


def filter_entries(entries, query, tags, days, today, timezone):
    """Return newest entries matching text, all tags and local dates."""
    query = query.strip().casefold()
    selected = {tag.casefold() for tag in tags}
    cutoff = today - timedelta(days=days - 1) if days else None
    results = []
    for row in reversed(entries):
        entry_tags = {tag.strip().casefold() for tag in row["tags"].split(",")}
        text = " ".join(row[key] for key in ("title", "body", "tags"))
        day = (
            datetime.fromisoformat(row["created_at"])
            .astimezone(ZoneInfo(timezone))
            .date()
        )
        if query not in text.casefold() or not selected <= entry_tags:
            continue
        if cutoff and not cutoff <= day <= today:
            continue
        results.append(row)
    return results
