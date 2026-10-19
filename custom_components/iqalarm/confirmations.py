"""Bounded confirmation grades and spatially verified, expiring rule memories."""

import hashlib
import json
from dataclasses import asdict, replace

from .level_rules import RuleCondition, RuleMatch, match_rule, spaces


def grade_match(
    config,
    rule,
    sensors,
    raw,
    evidence,
    quarantine,
    now,
    debouncing=None,
    *,
    proof_only=False,
    maximum_sources=None,
    required_room_id=None,
):
    """Find the largest coherent proof up to the configured target, without side effects."""
    target = rule.confirmation_sources
    if target is None:
        return None
    if maximum_sources is not None:
        target = min(target, maximum_sources)
    candidates = (
        sensors
        if proof_only
        else {key: sensor for key, sensor in sensors.items() if raw.get(key) is not None}
    )
    base = [condition.count for condition in rule.conditions]
    budget = [5000]

    def allocations(index, remaining):
        if index == len(base) - 1:
            yield [base[index] + remaining]
        else:
            for extra in range(remaining + 1):
                for tail in allocations(index + 1, remaining - extra):
                    yield [base[index] + extra, *tail]

    for count in range(target, sum(base) - 1, -1):
        for counts in allocations(0, count - sum(base)):
            if budget[0] < 0:
                return None
            variant = replace(
                rule,
                confirmation_target=None,
                confirmation_thresholds=None,
                confirmation_decay_seconds=None,
                conditions=[
                    replace(c, count=n) for c, n in zip(rule.conditions, counts, strict=True)
                ],
            )
            found = match_rule(
                config,
                variant,
                candidates,
                raw,
                evidence,
                quarantine,
                now,
                proof_only=True,
                debouncing=debouncing,
                search_budget=budget,
                required_room_id=required_room_id,
            )
            if found:
                return found
    return None


def memory_signature(rule, chain, sensors):
    """Bind proof to its original rule, devices, roles and spatial assignments."""
    sources = []
    for item in chain:
        sensor = sensors[item.entity_id]
        sources.append(
            [
                sensor.entity_id,
                sensor.source_id or sensor.entity_id,
                sensor.role,
                sensor.room_id,
                sorted(sensor.front_of),
                sensor.enabled,
                sensor.sensor_kind,
            ]
        )
    value = [asdict(rule), sorted(sources, key=lambda item: item[0])]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def valid_memory(config, rule, record, sensors, quarantine, now):
    """Revalidate saved proof; never trust an expiry or source identity from storage."""
    from .models import Evidence

    if not record or rule.confirmation_target is None or not rule.enabled:
        return None
    try:
        chain = [Evidence(**item) for item in record["chain"]]
        at = max(e.timestamp for e in chain)
        until = at + rule.confirmation_memory_seconds
        if not at <= now < until or record["until"] != until or record["confirmed_at"] != at:
            return None
        if record["signature"] != memory_signature(rule, chain, sensors):
            return None
        found = grade_match(config, rule, sensors, {}, chain, quarantine, at, proof_only=True)
        if found and len(found.chain) >= rule.confirmation_sources:
            return found
    except (KeyError, TypeError, ValueError):
        return None
    return None


def match_with_memory(
    config,
    rule,
    sensors,
    raw,
    evidence,
    quarantine,
    now,
    memories,
    *,
    proof_only=False,
    debouncing=None,
    required_room_id=None,
    search_budget=None,
):
    """Require stored confirmation plus a new, independent, spatially related signal."""
    parent = config.rules.get(rule.prerequisite_rule_id) if rule.prerequisite_rule_id else None
    if rule.prerequisite_rule_id and parent is None:
        return None
    if not parent:
        direct = match_rule(
            config,
            rule,
            sensors,
            raw,
            evidence,
            quarantine,
            now,
            proof_only=proof_only,
            debouncing=debouncing,
            required_room_id=required_room_id,
            search_budget=search_budget,
        )
        memory = valid_memory(config, rule, memories.get(rule.id), sensors, quarantine, now)
        if (
            memory
            and (proof_only or all(raw.get(e.entity_id) is not None for e in memory.chain))
            and (
                required_room_id is None
                or any(required_room_id in spaces(sensors[e.entity_id]) for e in memory.chain)
            )
        ):
            return memory
        return direct
    record = memories.get(parent.id)
    proof = valid_memory(config, parent, record, sensors, quarantine, now)
    if not proof:
        return None
    if not proof_only and any(raw.get(e.entity_id) is None for e in proof.chain):
        return None
    at = record["confirmed_at"]
    # The original camera proof was verified in its own window. For the next
    # rule it becomes one stored prerequisite at completion time; retain the
    # original event times in the returned audit chain.
    stored = [replace(e, timestamp=at) for e in proof.chain]
    conditions = [
        RuleCondition(
            sensor_ids=[e.entity_id for e in proof.chain],
            count=len(proof.chain),
            max_age_seconds=parent.confirmation_memory_seconds,
        ),
        *[
            replace(
                c,
                max_age_seconds=min(c.max_age_seconds or rule.window_seconds, rule.window_seconds),
            )
            for c in rule.conditions
        ],
    ]
    composite = replace(
        rule,
        conditions=conditions,
        prerequisite_rule_id=None,
        window_seconds=max(rule.window_seconds, parent.confirmation_memory_seconds),
    )
    found = match_rule(
        config,
        composite,
        sensors,
        raw,
        [e for e in evidence if e.timestamp >= at] + stored,
        quarantine,
        now,
        proof_only=proof_only,
        debouncing=debouncing,
        required_room_id=required_room_id,
        search_budget=search_budget,
    )
    if not found:
        return None
    originals = {e.entity_id: e for e in proof.chain}
    return RuleMatch(
        rule.id,
        rule.stage_id,
        sorted([originals.get(e.entity_id, e) for e in found.chain], key=lambda e: e.timestamp),
        found.confirmed,
    )
