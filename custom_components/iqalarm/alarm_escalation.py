"""Confirmed alarm lifetime and independent five-minute escalation."""

import math
from dataclasses import dataclass
from uuid import uuid4

ALARM_RULE = "alarm_lifetime"


@dataclass
class AlarmEscalation:
    stage_id: str = "4"
    next_stage_id: str = "5"
    delay_seconds: int = 300

    def __post_init__(self):
        if type(self.delay_seconds) is not int or not 1 <= self.delay_seconds <= 86400:
            raise ValueError("Eskalationszeit muss zwischen 1 und 86400 Sekunden liegen")
        if (
            not isinstance(self.stage_id, str)
            or not isinstance(self.next_stage_id, str)
            or self.stage_id == self.next_stage_id
        ):
            raise ValueError("Alarm und Folgealarm benötigen verschiedene Stufen")


def new_alarm(settings, now, chain):
    from dataclasses import asdict

    return dict(
        id=uuid4().hex,
        started_at=now,
        deadline=now + settings.delay_seconds,
        duration=settings.delay_seconds,
        stage_id=settings.stage_id,
        next_stage_id=settings.next_stage_id,
        escalated=False,
        chain=[asdict(item) for item in chain or []],
    )


def restore_alarm(value, settings, now):
    if not settings or not isinstance(value, dict):
        return None
    try:
        valid = (
            isinstance(value["id"], str)
            and len(value["id"]) == 32
            and all(c in "0123456789abcdef" for c in value["id"])
            and value["stage_id"] == settings.stage_id
            and value["next_stage_id"] == settings.next_stage_id
            and all(
                type(value[k]) in (int, float) and math.isfinite(value[k])
                for k in ("started_at", "deadline", "duration")
            )
            and value["duration"] > 0
            and value["deadline"] == value["started_at"] + value["duration"]
            and value["started_at"] <= now
            and isinstance(value["chain"], list)
            and type(value["escalated"]) is bool
        )
        return value if valid else None
    except (KeyError, TypeError):
        return None
