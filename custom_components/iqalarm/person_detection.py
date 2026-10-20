"""Shared outdoor report lifetimes, separate from independent alarm evidence."""

import math
from dataclasses import asdict, dataclass, field

from .const import PERIMETER_ROLES, Role


@dataclass
class PersonDetection:
    stage_id: str = "2"
    thresholds: list[int] = field(default_factory=lambda: [1, 2, 3])
    quiet_seconds: float = 60

    def __post_init__(self):
        from .models import ID_RE, number

        if not isinstance(self.stage_id, str) or not ID_RE.fullmatch(self.stage_id):
            raise ValueError("Personenerkennung benötigt eine gültige Stufe")
        if (
            not isinstance(self.thresholds, list)
            or len(self.thresholds) != 3
            or any(type(n) is not int or not 1 <= n <= 100 for n in self.thresholds)
            or any(a >= b for a, b in zip(self.thresholds, self.thresholds[1:], strict=False))
        ):
            raise ValueError("Drei aufsteigende Meldeschwellen zwischen 1 und 100 erforderlich")
        number(self.quiet_seconds, 1, 3600, "Rückzählzeit der Personenerkennung")


def managed_person_rule(rule, settings, configured):
    """Only simple outdoor trigger rules use the shared lifetime policy."""
    return bool(
        settings
        and rule.stage_id == settings.stage_id
        and rule.confirmation_target is None
        and rule.prerequisite_rule_id is None
        and len(rule.conditions) == 1
        and rule.conditions[0].event == "active"
        and rule.conditions[0].count == 1
        and (configured or rule.id == "perimeter")
    )


def advance_person_detection(settings, evidence, sensors, raw, last_active, now, previous, context):
    """Each report has one lifetime, used by level, grade, map and countdown.

    Separate reports from one camera can add to the display grade. They never
    become independent physical sources or a full-alarm confirmation memory.
    """
    from .models import Evidence

    previous = previous or {}
    incoming = {e.entity_id: e.timestamp for e in evidence}
    try:
        if previous.get("schema") != 2 or previous.get("context") != context:
            raise ValueError("Changed report scope")
        reports = previous["reports"]
        seen = previous["seen"]
        if not isinstance(reports, list) or len(reports) > 2000 or not isinstance(seen, dict):
            raise ValueError("Invalid report state")
        if any(
            type(at) not in (int, float) or not math.isfinite(at) or at > now
            for at in seen.values()
        ):
            raise ValueError("Invalid report timestamp")
        identities = set()
        for report in reports:
            if not isinstance(report, dict):
                raise ValueError("Invalid report")
            item = Evidence(**{k: v for k, v in report.items() if k != "expires_at"})
            expiry = report["expires_at"]
            identity = (item.entity_id, item.timestamp)
            if (
                item.role not in PERIMETER_ROLES
                or type(item.timestamp) not in (int, float)
                or not math.isfinite(item.timestamp)
                or item.timestamp > now
                or identity in identities
                or (
                    expiry is not None
                    and (
                        type(expiry) not in (int, float)
                        or not math.isfinite(expiry)
                        or not item.timestamp <= expiry <= now + settings.quiet_seconds
                    )
                )
            ):
                raise ValueError("Invalid report lifetime")
            identities.add(identity)
    except (KeyError, TypeError, ValueError):
        reports = []
        seen = incoming if previous else {}

    live = []
    for report in reports:
        key = report["entity_id"]
        sensor = sensors.get(key)
        if (
            not sensor
            or raw.get(key) is None
            or report["room_id"] != sensor.room_id
            or report["role"] != sensor.role
            or report["source_id"] != (sensor.source_id or key)
        ):
            continue
        report = dict(report)
        if report["expires_at"] is None and raw.get(key) is not True:
            ended = max(report["timestamp"], last_active.get(key, report["timestamp"]))
            report["expires_at"] = ended + settings.quiet_seconds
        if report["expires_at"] is None or now < report["expires_at"]:
            live.append(report)
    fresh = sorted(
        (e for e in evidence if e.timestamp > seen.get(e.entity_id, -1)),
        key=lambda e: (e.timestamp, e.entity_id),
    )
    for item in fresh:
        if item.entity_id not in sensors or raw.get(item.entity_id) is None:
            continue
        ended = max(item.timestamp, last_active.get(item.entity_id, item.timestamp))
        expiry = None if raw.get(item.entity_id) is True else ended + settings.quiet_seconds
        if expiry is None or expiry > now:
            live.append({**asdict(item), "expires_at": expiry})
    # Keep active and latest-expiring reports if the bounded history is full.
    live = sorted(
        live,
        key=lambda r: (r["expires_at"] is None, r["expires_at"] or 0, r["timestamp"]),
        reverse=True,
    )[:2000]
    seen = {key: max(incoming.get(key, -1), seen.get(key, -1)) for key in sensors}
    persons = [r for r in live if r["role"] == Role.PERIMETER_CAMERA]
    deadlines = [r["expires_at"] for r in persons if r["expires_at"] is not None]
    return {
        "schema": 2,
        "context": context,
        "reports": live,
        "seen": seen,
        "chain": [{k: v for k, v in r.items() if k != "expires_at"} for r in live],
        "grade": sum(len(persons) >= threshold for threshold in settings.thresholds),
        "next_decay": min(deadlines, default=None),
    }
