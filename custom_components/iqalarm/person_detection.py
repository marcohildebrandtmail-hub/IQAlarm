"""Room-local camera person reports, separate from independent alarm evidence."""

import math
from dataclasses import asdict, dataclass, field

from .const import Role


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


def advance_person_detection(settings, evidence, sensors, now, previous, context):
    """Count genuine activation edges, including repeat reports from one camera.

    This counter is display context only. It never creates independent sources,
    confirmation memories or full-alarm evidence.
    """
    from .models import Evidence

    previous = previous or {}
    incoming = {e.entity_id: e.timestamp for e in evidence}
    try:
        if previous.get("context") != context:
            raise ValueError("Changed camera scope")
        chain = [Evidence(**item) for item in previous["chain"]]
        seen = previous["seen"]
        deadline = previous["next_decay"]
        if (
            len(chain) > settings.thresholds[-1]
            or any(
                e.entity_id not in sensors
                or e.role != Role.PERIMETER_CAMERA
                or e.room_id != sensors[e.entity_id].room_id
                or not math.isfinite(e.timestamp)
                or e.timestamp > now
                for e in chain
            )
            or len({(e.entity_id, e.timestamp) for e in chain}) != len(chain)
            or not isinstance(seen, dict)
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v > now
                for v in seen.values()
            )
            or (chain and (type(deadline) not in (int, float) or not math.isfinite(deadline)))
        ):
            raise ValueError("Invalid person counter")
    except (KeyError, TypeError, ValueError):
        chain, deadline = [], None
        # A changed configuration must not reinterpret old events as new reports.
        seen = incoming if previous else {}

    thresholds = settings.thresholds
    while chain and deadline is not None and now >= deadline:
        grade = sum(len(chain) >= threshold for threshold in thresholds)
        keep = thresholds[grade - 1] - 1 if grade else 0
        chain = chain[-keep:] if keep else []
        deadline = deadline + settings.quiet_seconds if chain else None
    fresh = sorted(
        (e for e in evidence if e.timestamp > seen.get(e.entity_id, -1)),
        key=lambda e: (e.timestamp, e.entity_id),
    )
    for item in fresh:
        chain.append(item)
        chain = chain[-thresholds[-1] :]
        deadline = item.timestamp + settings.quiet_seconds
    seen = {key: max(incoming.get(key, -1), seen.get(key, -1)) for key in sensors}
    return {
        "context": context,
        "chain": [asdict(e) for e in chain],
        "seen": seen,
        "next_decay": deadline,
        "grade": sum(len(chain) >= threshold for threshold in thresholds),
    }
