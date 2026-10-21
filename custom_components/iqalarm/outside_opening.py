"""A fresh mapped opening after a live outdoor 3/3 establishes LVL 4."""

import math
from dataclasses import asdict

from .const import CONTACT_ROLES, Role
from .level_rules import LevelRule, RuleCondition
from .person_detection import motion_confirmation

OUTSIDE_OPENING_RULE = "outside_opening_level4"


def outside_opening_rule(settings):
    return LevelRule(
        OUTSIDE_OPENING_RULE,
        "Bestätigte Außenaktivität + Öffnung",
        settings.next_stage_id,
        [RuleCondition(roles=sorted(CONTACT_ROLES))],
        window_seconds=settings.quiet_seconds,
    )


def advance_outside_openings(
    config, context, outdoor, contacts, sensors, raw, quarantine, now, previous
):
    """Keep the existing LVL-4 quiet interval; never turn old openings into fresh ones.

    The outdoor grade must already have been full when a new contact arrives.
    Only reports contributing to that full grade can establish the mapped area.
    Once established, the original proof lives for the existing quiet interval,
    independently of the later decay of the outdoor display grade.
    """
    from .models import Evidence

    previous = previous or {}
    compatible = previous.get("context") == context
    seen = previous.get("seen", {}) if compatible else {}
    records = previous.get("openings", {}) if compatible else {}
    full_at = previous.get("full_at") if compatible else None
    if not isinstance(seen, dict) or not isinstance(records, dict):
        seen, records, full_at = {}, {}, None
    if full_at is not None and (
        type(full_at) not in (int, float) or not math.isfinite(full_at) or full_at > now
    ):
        full_at = None
    links = {tuple(pair) for pair in config.outside_inside_links}
    live = {}
    for room, record in records.items():
        try:
            at, until = record["at"], record["until"]
            chain = [Evidence(**item) for item in record["chain"]]
            opening = chain[-1]
            reports = [{**asdict(item), "expires_at": None} for item in chain[:-1]]
            camera_count = sum(item.role == Role.PERIMETER_CAMERA for item in chain[:-1])
            camera_grade = sum(
                camera_count >= threshold
                for threshold in config.person_detection_settings.thresholds
            )
            motion_grade = max(0, len(motion_confirmation(reports, config.room_connections)) - 1)
            if (
                any(
                    type(value) not in (int, float) or not math.isfinite(value)
                    for value in (at, until)
                )
                or not at <= now < until == at + config.automatic_detection.quiet_seconds
                or opening.role not in CONTACT_ROLES
                or camera_grade + motion_grade < 3
                or any(
                    item.role not in (Role.PERIMETER_CAMERA, Role.PERIMETER_SENSOR)
                    for item in chain[:-1]
                )
                or len({(item.entity_id, item.timestamp) for item in chain}) != len(chain)
                or opening.source_id in {item.source_id for item in chain[:-1]}
                or opening.entity_id not in contacts
                or opening.room_id != room
                or opening.timestamp != at
                or not any((item.room_id, room) in links for item in chain[:-1])
                or any(
                    item.entity_id not in sensors
                    or raw.get(item.entity_id) is None
                    or item.entity_id in quarantine
                    or item.role != sensors[item.entity_id].role
                    or item.room_id != sensors[item.entity_id].room_id
                    or item.source_id != (sensors[item.entity_id].source_id or item.entity_id)
                    or type(item.timestamp) not in (int, float)
                    or not math.isfinite(item.timestamp)
                    or item.timestamp > at
                    for item in chain
                )
            ):
                continue
            live[room] = record
        except (KeyError, TypeError, ValueError, IndexError, AttributeError):
            continue
    contributing = [r for r in outdoor.get("reports", []) if r["role"] == Role.PERIMETER_CAMERA]
    if outdoor.get("motion_grade", 0):
        contributing += outdoor.get("motion_sources", [])
    full = outdoor.get("grade") == 3
    source_ids = {r["source_id"] or r["entity_id"] for r in contributing}
    for item in sorted(contacts.values(), key=lambda item: item.timestamp):
        prior = seen.get(item.entity_id, -1)
        if type(prior) not in (int, float) or not math.isfinite(prior):
            prior = item.timestamp
        fresh = item.timestamp > prior
        seen[item.entity_id] = max(prior, item.timestamp)
        if (
            not fresh
            or full_at is None
            or not full
            or item.timestamp < full_at
            or now >= item.timestamp + config.automatic_detection.quiet_seconds
            or item.source_id in source_ids
            or not any((r["room_id"], item.room_id) in links for r in contributing)
        ):
            continue
        chain = [{k: v for k, v in r.items() if k != "expires_at"} for r in contributing]
        # No later outdoor event can be used as evidence for an earlier opening.
        if any(r["timestamp"] > item.timestamp for r in chain):
            continue
        live[item.room_id] = {
            "at": item.timestamp,
            "until": item.timestamp + config.automatic_detection.quiet_seconds,
            "chain": chain + [asdict(item)],
        }
    return {
        "context": context,
        "seen": {key: seen[key] for key in contacts if key in seen},
        "full_at": (full_at if full_at is not None else now) if full else None,
        "openings": live,
    }
