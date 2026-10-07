"""Keep observations paired with the exact context used to generate them."""

import json

PREFIX = "pyCompass observation v1\n"


def save_observation(text, context):
    """Serialize a reflection with its bounded evidence in one text field."""
    return PREFIX + json.dumps(
        {"text": text, "context": context}, ensure_ascii=False
    )


def read_observation(content):
    """Read new snapshots while retaining earlier plain-text observations."""
    if content.startswith(PREFIX):
        try:
            value = json.loads(content[len(PREFIX) :])
            if (
                isinstance(value, dict)
                and isinstance(value.get("text"), str)
                and isinstance(value.get("context"), dict)
                and isinstance(value["context"].get("start"), str)
                and isinstance(value["context"].get("end"), str)
                and isinstance(value["context"].get("checkins"), list)
                and isinstance(value["context"].get("journal"), list)
            ):
                return value["text"], value["context"]
        except (ValueError, TypeError):
            pass
    return content, None
