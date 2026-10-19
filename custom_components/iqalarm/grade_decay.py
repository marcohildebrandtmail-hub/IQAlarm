"""Evidence-backed grade accumulation with per-step inactivity decay."""

from dataclasses import asdict

from .confirmations import grade_match, memory_signature


def advance_grade(
    config,
    rule,
    sensors,
    raw,
    evidence,
    quarantine,
    now,
    previous,
    debouncing,
    *,
    required_room_id=None,
):
    """Count independent sources once; expired steps require a genuine new edge to rise."""
    from .models import Evidence

    thresholds = rule.grade_thresholds
    state = previous or {"chain": [], "seen": {}, "grade": 0, "next_decay": None}
    try:
        chain = [Evidence(**item) for item in state["chain"]]
        if previous and state.get("signature") != memory_signature(rule, chain, sensors):
            raise ValueError("Changed grade proof")
        seen = {key: float(value) for key, value in state["seen"].items() if key in sensors}
        deadline = state["next_decay"]
        if deadline is not None and not isinstance(deadline, (float, int)):
            raise ValueError("Invalid grade deadline")
    except (KeyError, TypeError, ValueError):
        chain, deadline = [], None
        seen = {item.entity_id: item.timestamp for item in evidence}

    def best(items, cap=None):
        return grade_match(
            config,
            rule,
            sensors,
            raw,
            items,
            quarantine,
            now,
            debouncing,
            maximum_sources=cap,
            required_room_id=required_room_id,
        )

    proof = best(chain)
    chain = proof.chain if proof else []
    grade = sum(len(chain) >= threshold for threshold in thresholds)
    if not grade:
        deadline = None
    while grade and deadline is not None and now >= deadline:
        proof = best(chain, thresholds[grade - 1] - 1)
        chain = proof.chain if proof else []
        grade = sum(len(chain) >= threshold for threshold in thresholds)
        deadline = deadline + rule.confirmation_decay_seconds[grade - 1] if grade else None
    incoming = [item for item in evidence if item.timestamp > seen.get(item.entity_id, -1)]
    previous_grade = grade
    for item in evidence:
        seen[item.entity_id] = max(item.timestamp, seen.get(item.entity_id, -1))
    if incoming:
        candidate = best(chain + incoming)
        fresh = {(item.entity_id, item.timestamp) for item in incoming}
        if candidate and any((item.entity_id, item.timestamp) in fresh for item in candidate.chain):
            proof, chain = candidate, candidate.chain
            grade = sum(len(chain) >= threshold for threshold in thresholds)
            if grade:
                at = max(
                    item.timestamp for item in chain if (item.entity_id, item.timestamp) in fresh
                )
                deadline = at + rule.confirmation_decay_seconds[grade - 1]
    state = {
        "chain": [asdict(item) for item in chain],
        "seen": seen,
        "grade": grade,
        "next_decay": deadline,
        "signature": memory_signature(rule, chain, sensors),
    }
    full = bool(grade == rule.confirmation_target and grade)
    return state, proof if chain else None, full and previous_grade < rule.confirmation_target
