"""Two independent, confirmed indoor areas establish one complete detection."""

import math
from dataclasses import asdict
from itertools import combinations

from .automatic_detection import AUTO_RULE
from .confirmations import memory_signature
from .models import Evidence

DISTRIBUTED_RULE = "distributed_level3"
DISTRIBUTED_DETECTED_RULE = "distributed_level4"


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _valid_chain(chain, sensors, raw, quarantine, now):
    return bool(chain) and all(
        item.entity_id in sensors
        and raw.get(item.entity_id) is not None
        and item.entity_id not in quarantine
        and item.role == sensors[item.entity_id].role
        and item.room_id == sensors[item.entity_id].room_id
        and item.source_id == (sensors[item.entity_id].source_id or item.entity_id)
        and _number(item.timestamp)
        and item.timestamp <= now
        for item in chain
    )


def _two_areas(states, settings, sensors, raw, quarantine, now):
    """Deduplicate room views of the same proof before looking for separate areas."""
    groups = {}
    for state in states.values():
        # A locally complete area already has its own normal 3/3 path.
        if state.get("grade") != 2:
            continue
        try:
            chain = [Evidence(**item) for item in state["chain"]]
            until = state["next_decay"]
            sources = frozenset(item.source_id for item in chain)
            rooms = frozenset(item.room_id for item in chain)
            if (
                not _number(until)
                or until <= now
                or len(sources) != len(chain)
                or len(sources) < settings.threshold + 1
                or not _valid_chain(chain, sensors, raw, quarantine, now)
            ):
                continue
            if sources not in groups or until > groups[sources][3]:
                groups[sources] = (sources, rooms, chain, until)
        except (KeyError, TypeError, ValueError):
            continue
    eligible = [
        (a, b)
        for a, b in combinations(groups.values(), 2)
        if a[0].isdisjoint(b[0]) and a[1].isdisjoint(b[1])
    ]
    if not eligible:
        return None
    a, b = max(
        eligible,
        key=lambda pair: (
            min(pair[0][3], pair[1][3]),
            tuple(sorted(pair[0][0] | pair[1][0])),
        ),
    )
    return (
        sorted(a[2] + b[2], key=lambda item: (item.timestamp, item.entity_id)),
        min(a[3], b[3]),
        [[item.entity_id for item in a[2]], [item.entity_id for item in b[2]]],
    )


def advance_distributed(config, context, states, sensors, raw, quarantine, fresh, now, previous):
    """Keep 3/3 only while both areas are confirmed; retain established LVL 4
    for the existing quiet interval, just like the other direct detection path.
    """
    settings = config.automatic_detection
    rule = settings.rules()[AUTO_RULE]
    previous = previous if isinstance(previous, dict) and previous.get("context") == context else {}
    last_full_at = previous.get("last_full_at", -1)
    if not _number(last_full_at) or last_full_at > now:
        last_full_at = -1
    full = previous.get("full")
    promoted = previous.get("promoted_at")
    try:
        chain = [Evidence(**item) for item in full["chain"]]
        since = full["since"]
        parts = full["areas"]
        if (
            not _valid_chain(chain, sensors, raw, quarantine, now)
            or not _number(since)
            or since != max(item.timestamp for item in chain)
            or len({item.source_id for item in chain}) != len(chain)
            or full["signature"] != memory_signature(rule, chain, sensors)
            or not isinstance(parts, list)
            or len(parts) != 2
            or any(
                not isinstance(part, list) or len(part) < settings.threshold + 1 for part in parts
            )
            or sorted(eid for part in parts for eid in part)
            != sorted(item.entity_id for item in chain)
        ):
            raise ValueError("Invalid distributed proof")
        by_id = {item.entity_id: item for item in chain}
        area_rooms = [{by_id[eid].room_id for eid in part} for part in parts]
        doors = {frozenset(pair) for pair in config.room_connections}
        if not area_rooms[0].isdisjoint(area_rooms[1]) or any(
            len(rooms) > 1
            and not any(
                all(other == center or frozenset((center, other)) in doors for other in rooms)
                for center in rooms
            )
            for rooms in area_rooms
        ):
            raise ValueError("Changed distributed areas")
        if promoted is not None and (not _number(promoted) or not since <= promoted <= now):
            raise ValueError("Invalid promotion time")
    except (KeyError, TypeError, ValueError):
        full, promoted, chain = None, None, []
    base = dict(
        context=context,
        last_full_at=last_full_at,
        grade=0,
        full=None,
        promoted_at=None,
        chain=[],
        next_decay=None,
        rooms=[],
    )
    if not settings.promotion_enabled:
        promoted = None
    if promoted is not None:
        until = promoted + settings.quiet_seconds
        if now < until:
            return {
                **base,
                "grade": 3,
                "full": full,
                "promoted_at": promoted,
                "chain": full["chain"],
                "next_decay": until,
                "rooms": sorted({item.room_id for item in chain}),
            }
        # The same old four sources cannot start a second detection cycle.
        full = None
    # An already complete distributed proof remains valid through its own
    # deadline, including when a new fifth source completes a local area.
    until = previous.get("next_decay")
    due = bool(
        full is not None
        and _number(until)
        and settings.promotion_enabled
        and until >= full["since"] + settings.promote_seconds
        and now >= full["since"] + settings.promote_seconds
    )
    if due:
        promoted = full["since"] + settings.promote_seconds
        until = promoted + settings.quiet_seconds
        if now < until:
            return {
                **base,
                "grade": 3,
                "full": full,
                "promoted_at": promoted,
                "chain": full["chain"],
                "next_decay": until,
                "rooms": sorted({item["room_id"] for item in full["chain"]}),
            }
        full = None
    if full is not None and (not _number(until) or now >= until):
        full = None
    if full is None:
        candidate = _two_areas(states, settings, sensors, raw, quarantine, now)
        if not candidate:
            return base
        current, until, area_sources = candidate
        at = max(item.timestamp for item in current)
        if at <= last_full_at:
            return base
        full = dict(
            since=at,
            chain=[asdict(item) for item in current],
            areas=area_sources,
            signature=memory_signature(rule, current, sensors),
        )
        last_full_at = at
    since = full["since"]
    sources = {item["source_id"] for item in full["chain"]}
    if settings.promotion_enabled:
        extra = next(
            (item for item in fresh if item.timestamp > since and item.source_id not in sources),
            None,
        )
        if extra is not None:
            promoted = now
        elif now >= since + settings.promote_seconds:
            promoted = since + settings.promote_seconds
        if promoted is not None:
            until = promoted + settings.quiet_seconds
            if now >= until:
                return {**base, "last_full_at": last_full_at}
    return dict(
        context=context,
        last_full_at=last_full_at,
        grade=3,
        full=full,
        promoted_at=promoted,
        chain=full["chain"],
        next_decay=until,
        rooms=sorted({item["room_id"] for item in full["chain"]}),
    )
