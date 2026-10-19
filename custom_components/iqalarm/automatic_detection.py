"""Automatic room-local detection grades, independent from full-alarm confirmation."""

import math
from dataclasses import asdict, dataclass

from .confirmations import memory_signature
from .const import CONTACT_ROLES, INTERIOR_ROLES
from .grade_decay import advance_grade
from .level_rules import LevelRule, RuleCondition, RuleMatch

AUTO_RULE = "automatic_level3"
DETECTED_RULE = "automatic_level4"
DETECTION_ROLES = CONTACT_ROLES | INTERIOR_ROLES


@dataclass
class AutomaticDetection:
    stage_id: str = "3"
    next_stage_id: str = "4"
    threshold: int = 1
    quiet_seconds: float = 60
    promote_seconds: float = 60
    test_mode: bool = True

    def __post_init__(self):
        from .models import ID_RE, number

        if any(
            not isinstance(key, str) or not ID_RE.fullmatch(key)
            for key in (self.stage_id, self.next_stage_id)
        ):
            raise ValueError("Automatische Erkennung benötigt gültige Stufen")
        if type(self.threshold) is not int or not 1 <= self.threshold <= 6:
            raise ValueError("Bestätigungsschwelle muss zwischen 1 und 6 liegen")
        number(self.quiet_seconds, 1, 600, "Ruhezeit")
        number(self.promote_seconds, 1, 600, "Verweildauer bei 3/3")
        if type(self.test_mode) is not bool:
            raise ValueError("Testbetrieb muss ein Wahrheitswert sein")

    def rules(self):
        return {
            AUTO_RULE: LevelRule(
                AUTO_RULE,
                "Automatische Sensorerkennung",
                self.stage_id,
                [RuleCondition(roles=sorted(DETECTION_ROLES))],
                window_seconds=min(3600, self.quiet_seconds * 3 + self.promote_seconds + 60),
                confirmation_target=3,
                confirmation_thresholds=list(range(self.threshold, self.threshold + 3)),
                confirmation_decay_seconds=[self.quiet_seconds] * 3,
            ),
            DETECTED_RULE: LevelRule(
                DETECTED_RULE,
                "Echte Erkennung",
                self.next_stage_id,
                [RuleCondition(roles=sorted(DETECTION_ROLES))],
            ),
        }


def advance_detection(
    config,
    settings,
    room_id,
    sensors,
    raw,
    evidence,
    quarantine,
    now,
    previous,
    debouncing,
    *,
    rule=None,
):
    """Advance one room and its direct connections without pooling unrelated rooms."""
    from .models import Evidence

    rule = rule or settings.rules()[AUTO_RULE]
    previous = previous or {}
    state, proof, _ = advance_grade(
        config,
        rule,
        sensors,
        raw,
        evidence,
        quarantine,
        now,
        previous or None,
        debouncing,
        required_room_id=room_id,
    )
    full = previous.get("full")
    promoted = previous.get("promoted_at")
    try:
        chain = [Evidence(**item) for item in full["chain"]]
        since = full["since"]
        if (
            not isinstance(since, (int, float))
            or not math.isfinite(since)
            or since != max(item.timestamp for item in chain)
            or since > now
            or full["signature"] != memory_signature(rule, chain, sensors)
            or any(
                raw.get(item.entity_id) is None or item.entity_id in quarantine for item in chain
            )
        ):
            raise ValueError("Invalid full grade")
        if promoted is not None and (
            not isinstance(promoted, (int, float))
            or not math.isfinite(promoted)
            or not since <= promoted <= now
        ):
            raise ValueError("Invalid detection time")
    except (KeyError, TypeError, ValueError):
        full, promoted = None, None
    if settings.test_mode:
        promoted = None
    fresh = {
        (item.entity_id, item.timestamp)
        for item in evidence
        if item.timestamp > previous.get("seen", {}).get(item.entity_id, -1)
    }
    was_full = previous.get("grade") == 3 and full is not None
    deadline = previous.get("next_decay")
    due = bool(
        not settings.test_mode
        and was_full
        and deadline is not None
        and deadline >= full["since"] + settings.promote_seconds
        and now >= full["since"] + settings.promote_seconds
    )
    # At the shared deadline the explicitly requested promotion takes precedence
    # over inactivity decay. Revalidate the old proof at that deadline first.
    if due and promoted is None:
        at = full["since"] + settings.promote_seconds
        checked, checked_proof, _ = advance_grade(
            config,
            rule,
            sensors,
            raw,
            [item for item in evidence if item.timestamp < at],
            quarantine,
            max(full["since"], at - 0.000001),
            previous,
            debouncing,
            required_room_id=room_id,
        )
        if checked["grade"] == 3 and checked_proof and now - at < settings.quiet_seconds:
            state, proof, promoted = checked, checked_proof, at
            state["next_decay"] = at + settings.quiet_seconds
    if state["grade"] == 3:
        if full is None or not was_full:
            at = max(item.timestamp for item in proof.chain)
            full = {
                "since": at,
                "chain": [asdict(item) for item in proof.chain],
                "signature": memory_signature(rule, proof.chain, sensors),
            }
        elif (
            not settings.test_mode
            and promoted is None
            and deadline is not None
            and now < deadline
            and any((item.entity_id, item.timestamp) in fresh for item in proof.chain)
        ):
            promoted = now
    elif not state["grade"]:
        full, promoted = None, None
    else:
        full, promoted = None, None
    state.update(full=full, promoted_at=promoted)
    if not proof or not state["grade"]:
        return state, None
    match = RuleMatch(
        DETECTED_RULE if promoted is not None else AUTO_RULE,
        settings.next_stage_id if promoted is not None else settings.stage_id,
        proof.chain,
        False,
        room_id,
    )
    return state, match
