"""Explicit level conditions and bounded, independent spatial proof matching."""

import json
import re
from dataclasses import asdict, dataclass, field, replace
from typing import TYPE_CHECKING

from .const import CONTACT_ROLES, INTERIOR_ROLES, PERIMETER_ROLES, Role

if TYPE_CHECKING:
    from .models import Configuration, Evidence, SensorConfig

_ID = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
_ENTITY = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z0-9_]+$")
ALL_ROLES = [role.value for role in Role]


@dataclass
class RuleCondition:
    sensor_ids: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    event: str = "active"
    count: int = 1
    max_age_seconds: float | None = None

    def __post_init__(self):
        from .models import number

        if not isinstance(self.sensor_ids, list) or len(self.sensor_ids) > 1250:
            raise ValueError("Bedingung: maximal 1250 Sensoren erlaubt")
        if any(not isinstance(s, str) or not _ENTITY.fullmatch(s) for s in self.sensor_ids):
            raise ValueError("Bedingung enthält ungültige Sensor-IDs")
        if not isinstance(self.roles, list) or any(r not in ALL_ROLES for r in self.roles):
            raise ValueError("Bedingung enthält unbekannte Sensorrollen")
        self.roles = list(self.roles)
        self.sensor_ids = list(self.sensor_ids)
        if self.event not in ("active", "unavailable", "flapping", "override"):
            raise ValueError("Unbekannte Meldungsart")
        if type(self.count) is not int or not 1 <= self.count <= 8:
            raise ValueError("1 bis 8 unabhängige Quellen pro Bedingung erforderlich")
        if self.max_age_seconds is not None:
            number(self.max_age_seconds, 1, 3600, "Meldungsgültigkeit")

    def accepts(self, sensor: "SensorConfig") -> bool:
        return sensor.entity_id in self.sensor_ids or sensor.role in self.roles


@dataclass
class LevelRule:
    id: str
    name: str
    stage_id: str
    conditions: list[RuleCondition] = field(default_factory=list)
    window_seconds: float = 60
    delay_seconds: float = 0
    entry_only: bool = False
    ordered: bool = False
    room_ids: list[str] | None = None
    paths: list[list[str]] = field(default_factory=list)
    enabled: bool = True
    confirmation_target: int | None = None
    confirmation_memory_seconds: float = 180
    prerequisite_rule_id: str | None = None
    confirmation_thresholds: list[int] | None = None
    confirmation_decay_seconds: list[float] | None = None

    @property
    def grade_thresholds(self) -> list[int]:
        return self.confirmation_thresholds or list(range(1, (self.confirmation_target or 0) + 1))

    @property
    def confirmation_sources(self) -> int | None:
        return self.grade_thresholds[-1] if self.confirmation_target is not None else None

    def __post_init__(self):
        from .models import construct, number, text

        if not isinstance(self.id, str) or not _ID.fullmatch(self.id):
            raise ValueError("Ungültige Regel-ID")
        text(self.name, "Regelname", 100)
        if not isinstance(self.stage_id, str) or not _ID.fullmatch(self.stage_id):
            raise ValueError("Ungültige Zielstufe")
        if not isinstance(self.conditions, list) or not 1 <= len(self.conditions) <= 4:
            raise ValueError("Eine Regel benötigt 1 bis 4 Bedingungen")
        self.conditions = [
            construct(RuleCondition, c) if isinstance(c, dict) else c for c in self.conditions
        ]
        if any(not isinstance(c, RuleCondition) for c in self.conditions):
            raise ValueError("Ungültige Regelbedingung")
        if sum(c.count for c in self.conditions) > 8:
            raise ValueError("Maximal 8 unabhängige Quellen pro Regel")
        number(self.window_seconds, 1, 3600, "Bestätigungsfenster")
        number(self.delay_seconds, 0, 600, "Regelverzögerung")
        number(self.confirmation_memory_seconds, 1, 3600, "Bestätigungsspeicher")
        if self.confirmation_target is not None and (
            type(self.confirmation_target) is not int or not 1 <= self.confirmation_target <= 8
        ):
            raise ValueError("Bestätigungsziel muss zwischen Auslöseschwelle und 8 liegen")
        if self.confirmation_thresholds is not None:
            values = self.confirmation_thresholds
            if (
                self.confirmation_target is None
                or not isinstance(values, list)
                or len(values) != self.confirmation_target
                or any(type(v) is not int or not 1 <= v <= 8 for v in values)
                or any(a >= b for a, b in zip(values, values[1:], strict=False))
            ):
                raise ValueError(
                    "Meldeschwellen müssen pro Bestätigungsgrad streng aufsteigend zwischen 1 und 8 liegen"
                )
        if self.confirmation_sources is not None and self.confirmation_sources < sum(
            c.count for c in self.conditions
        ):
            raise ValueError("Bestätigungsziel benötigt mindestens die Quellen der Auslöseschwelle")
        if self.confirmation_decay_seconds is not None:
            values = self.confirmation_decay_seconds
            if (
                self.confirmation_target is None
                or not isinstance(values, list)
                or len(values) != self.confirmation_target
            ):
                raise ValueError("Jeder Bestätigungsgrad benötigt seine Rückstufungszeit")
            for value in values:
                number(value, 1, 3600, "Rückstufungszeit")
        if self.prerequisite_rule_id is not None:
            if not isinstance(self.prerequisite_rule_id, str) or not _ID.fullmatch(
                self.prerequisite_rule_id
            ):
                raise ValueError("Ungültige Bestätigungsvoraussetzung")
            if self.confirmation_target is not None:
                raise ValueError(
                    "Eine Regel nutzt ein eigenes Bestätigungsziel oder eine Voraussetzung"
                )
        for name in ("entry_only", "ordered", "enabled"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} muss boolesch sein")
        if self.room_ids is not None and (
            not isinstance(self.room_ids, list)
            or len(self.room_ids) > 250
            or any(not isinstance(r, str) or not _ID.fullmatch(r) for r in self.room_ids)
        ):
            raise ValueError("Ungültige Raumauswahl")
        if not isinstance(self.paths, list) or len(self.paths) > 500:
            raise ValueError("Maximal 500 Bestätigungswege erlaubt")
        for path in self.paths:
            if (
                not isinstance(path, list)
                or len(path) != 2
                or path[0] == path[1]
                or any(not isinstance(r, str) or not _ID.fullmatch(r) for r in path)
            ):
                raise ValueError("Bestätigungsweg benötigt zwei verschiedene Räume")


def spaces(sensor: "SensorConfig") -> set[str]:
    return set(sensor.front_of or ([sensor.room_id] if sensor.room_id else []))


def accepts(rule: LevelRule, condition: RuleCondition, sensor: "SensorConfig") -> bool:
    return condition.accepts(sensor) and (
        rule.room_ids is None or bool(spaces(sensor).intersection(rule.room_ids))
    )


@dataclass
class RuleMatch:
    rule_id: str
    stage_id: str
    chain: list["Evidence"]
    confirmed: bool
    room_id: str | None = None


def match_rule(
    config: "Configuration",
    rule: LevelRule,
    sensors: dict,
    raw: dict,
    evidence: list,
    quarantine: dict,
    now: float,
    *,
    proof_only: bool = False,
    debouncing: dict | None = None,
    search_budget: list[int] | None = None,
    required_room_id: str | None = None,
) -> RuleMatch | None:
    """Match each slot to a distinct physical source with one coherent spatial chain.

    Eight slots and a finite search budget bound adversarial/large configurations.
    Exhaustion fails closed rather than guessing that a correlation exists.
    """
    from .models import Evidence

    if not rule.enabled:
        return None
    confirmed = config.stage(rule.stage_id).requires_confirmation
    latest = {e.entity_id: e for e in evidence}
    grouped = config.window_members()
    groups = []
    for condition in rule.conditions:
        candidates = []
        for key, sensor in sensors.items():
            if not sensor.enabled or sensor.information_only or key in grouped:
                continue
            if not accepts(rule, condition, sensor):
                continue
            item = latest.get(key)
            if item is not None:
                if item.role != sensor.role or item.room_id != sensor.room_id:
                    continue
                item = replace(item, source_id=sensor.source_id or key)
            age = min(rule.window_seconds, condition.max_age_seconds or rule.window_seconds)
            if condition.event in ("active", "override"):
                if key in quarantine:
                    continue
                if not proof_only and raw.get(key) is None:
                    continue
                if condition.event == "override" and not (
                    sensor.immediate or sensor.role in (Role.PANIC, Role.SMOKE)
                ):
                    continue
                if item is None or not 0 <= now - item.timestamp < age:
                    # A seeded/still-active value is display information, never a
                    # newly independent confirmation and never a danger override.
                    if (
                        confirmed
                        or sum(c.count for c in rule.conditions) > 1
                        or (debouncing is not None and key in debouncing)
                        or proof_only
                        or condition.event == "override"
                        or raw.get(key) is not True
                    ):
                        continue
                    item = Evidence(
                        key,
                        sensor.source_id or key,
                        sensor.role,
                        sensor.room_id,
                        now,
                        sensor.name or key,
                    )
            elif condition.event == "unavailable":
                if proof_only or raw.get(key) is not None:
                    continue
                item = Evidence(
                    key,
                    sensor.source_id or key,
                    sensor.role,
                    sensor.room_id,
                    now,
                    sensor.name or key,
                )
            else:
                q = quarantine.get(key)
                if proof_only or not q or not 0 <= now - q["since"] < age:
                    continue
                item = Evidence(
                    key,
                    sensor.source_id or key,
                    sensor.role,
                    sensor.room_id,
                    q["since"],
                    sensor.name or key,
                )
            candidates.append(item)
        candidates.sort(
            key=lambda e: (
                required_room_id in spaces(sensors[e.entity_id]),
                e.timestamp,
                e.entity_id,
            ),
            reverse=True,
        )
        if len({e.source_id for e in candidates}) < condition.count:
            return None
        groups.append(candidates)

    if required_room_id is not None and not any(
        required_room_id in spaces(sensors[e.entity_id]) for group in groups for e in group
    ):
        return None

    # Slot order follows the condition order; repetitions within a condition are unordered.
    slots = [
        (index, candidates)
        for index, (condition, candidates) in enumerate(zip(rule.conditions, groups, strict=True))
        for _ in range(condition.count)
    ]
    budget = search_budget if search_budget is not None else [50000]
    doors = {frozenset(pair) for pair in config.room_connections}

    def search(index, chain, used, anchors, previous_time):
        if index == len(slots):
            if required_room_id is not None and not any(
                required_room_id in spaces(sensors[e.entity_id]) for e in chain
            ):
                return None
            if confirmed:
                roles = {e.role for e in chain}
                if any(c.event in ("unavailable", "flapping") for c in rule.conditions):
                    return None
                if Role.LOCK in roles and roles <= {Role.LOCK, Role.MOTION, Role.MMWAVE}:
                    return None
            return chain
        group_index, candidates = slots[index]
        prior_group = slots[index - 1][0] if index else -1
        boundary = previous_time if group_index != prior_group else None
        for candidate in candidates:
            budget[0] -= 1
            if budget[0] < 0:
                return None
            if candidate.source_id in used:
                continue
            if rule.ordered and boundary is not None and candidate.timestamp < boundary:
                continue
            candidate_spaces = spaces(sensors[candidate.entity_id])
            next_anchors = (
                candidate_spaces
                if index == 0
                else {
                    a
                    for a in anchors
                    if a in candidate_spaces
                    or any(
                        [a, b] in rule.paths or frozenset((a, b)) in doors for b in candidate_spaces
                    )
                }
            )
            if index and not next_anchors:
                continue
            # Distinct events must fall inside the same window, including restored proof.
            if (
                chain
                and max(e.timestamp for e in chain + [candidate])
                - min(e.timestamp for e in chain + [candidate])
                >= rule.window_seconds
            ):
                continue
            result = search(
                index + 1,
                chain + [candidate],
                used | {candidate.source_id},
                next_anchors,
                max(previous_time or candidate.timestamp, candidate.timestamp),
            )
            if result:
                return result
        return None

    chain = search(0, [], set(), set(), None)
    if chain is None:
        return None
    return RuleMatch(rule.id, rule.stage_id, sorted(chain, key=lambda e: e.timestamp), confirmed)


def default_rules() -> dict[str, LevelRule]:
    specs = {
        "perimeter": (
            "Person / Bewegung außen",
            "2",
            [RuleCondition(roles=list(PERIMETER_ROLES))],
            180,
            False,
        ),
        "single": (
            "Einzelner Öffnungs- oder Schlosssensor",
            "3",
            [RuleCondition(roles=list(CONTACT_ROLES))],
            60,
            False,
        ),
        "motion": ("Bewegung innen", "4", [RuleCondition(roles=list(INTERIOR_ROLES))], 60, False),
        "fault": (
            "Sensor ohne Verbindung",
            "3",
            [RuleCondition(roles=ALL_ROLES, event="unavailable")],
            60,
            False,
        ),
        "flapping": (
            "Sensor-Prellen",
            "3",
            [RuleCondition(roles=list(CONTACT_ROLES), event="flapping")],
            60,
            False,
        ),
        "perimeter_contact": (
            "Person vor dem passenden Eingang und Öffnung",
            "5",
            [
                RuleCondition(roles=[Role.PERIMETER_CAMERA]),
                RuleCondition(roles=list(CONTACT_ROLES), max_age_seconds=60),
            ],
            180,
            True,
        ),
        "contact_motion": (
            "Öffnung und neue Innenbewegung",
            "5",
            [
                RuleCondition(roles=[Role.ENTRY, Role.GLASS]),
                RuleCondition(roles=list(INTERIOR_ROLES)),
            ],
            60,
            True,
        ),
        "multi_contact": (
            "Zwei unabhängige Öffnungssensoren",
            "5",
            [RuleCondition(roles=[Role.ENTRY, Role.GLASS], count=2)],
            60,
            False,
        ),
        "multi_motion": (
            "Zwei unabhängige Innenraumsensoren",
            "5",
            [RuleCondition(roles=list(INTERIOR_ROLES), count=2)],
            60,
            False,
        ),
        "immediate": (
            "Freigegebener Gefahrensensor",
            "5",
            [RuleCondition(roles=ALL_ROLES, event="override")],
            60,
            False,
        ),
    }
    result = {
        key: LevelRule(key, name, stage, conditions, seconds, ordered=ordered)
        for key, (name, stage, conditions, seconds, ordered) in specs.items()
    }
    unordered = asdict(result["contact_motion"])
    unordered.update(
        id="contact_motion_any_order",
        name="Öffnung und Innenbewegung (beliebige Reihenfolge)",
        ordered=False,
    )
    result["contact_motion_any_order"] = LevelRule(**unordered)
    for rule in result.values():
        if rule.stage_id == "5":
            rule.delay_seconds, rule.entry_only = 20, True
    return result


def upgrade_level_rules(data: dict, stage_defaults: list[dict]) -> None:
    """Convert old scopes/timers/targets once, deduplicating equivalent profile rules."""
    stages = data.get("stages", stage_defaults)
    secure = data.get("secure_stage_id", stages[1 if len(stages) > 1 else 0]["id"])
    secure_rank = next(i for i, stage in enumerate(stages) if stage["id"] == secure)
    quiet = [s["id"] for s in stages[secure_rank + 1 :] if not s.get("requires_confirmation")] or [
        secure
    ]
    targets = {
        key: quiet[min(0 if key == "perimeter" else 2 if key == "motion" else 1, len(quiet) - 1)]
        if key in ("perimeter", "single", "motion", "fault", "flapping")
        else stages[-1]["id"]
        for key in default_rules()
    }
    rules, signatures = {}, {}
    virtual = {
        f"binary_sensor.iqalarm_window_{key}": {
            "role": Role.ENTRY,
            "room_id": w["room_id"],
            "front_of": [],
            "members": [w.get("contact_entity_id"), *w.get("handle_entity_ids", [])],
        }
        for key, w in data.get("windows", {}).items()
    }
    sensors = data.get("sensors", {}) | virtual
    templates = default_rules()
    templates.pop("contact_motion_any_order")
    for profile in data["profiles"].values():
        selected = []
        scope = profile.get("sensor_ids")
        for key, template in templates.items():
            target = profile.get("stage_targets", {}).get(key, targets[key])
            if target in (stages[0]["id"], secure):
                continue
            motion_mode = profile.get("motion_mode", "always")
            if key == "motion" and motion_mode != "always":
                continue
            if key == "perimeter" and not profile.get("perimeter_enabled", True):
                continue
            if key in ("single", "flapping") and not profile.get("contacts_enabled", True):
                continue
            if key in ("perimeter_contact", "contact_motion", "multi_contact", "multi_motion"):
                if not profile.get(key, key in ("perimeter_contact", "contact_motion")):
                    continue
                if key != "multi_motion" and not profile.get("contacts_enabled", True):
                    continue
                if key in ("contact_motion", "multi_motion") and motion_mode == "ignore":
                    continue
                if key == "perimeter_contact" and not profile.get("perimeter_enabled", True):
                    continue
            item = asdict(template)
            item["stage_id"] = target
            item["window_seconds"] = (
                profile.get("perimeter_seconds", 180)
                if key in ("perimeter", "perimeter_contact")
                else profile.get("correlation_seconds", 60)
            )
            item["room_ids"] = profile.get("room_ids")
            item["paths"] = (
                profile.get("confirmation_paths", []) if key != "perimeter_contact" else []
            )
            item["ordered"] = key == "perimeter_contact" or (
                key == "contact_motion" and motion_mode == "after_contact"
            )
            if key not in ("perimeter", "single", "motion", "fault", "flapping"):
                item["delay_seconds"] = profile.get("entry_seconds", 20)
                item["entry_only"] = True
            if key == "perimeter_contact":
                item["conditions"][1]["max_age_seconds"] = profile.get("correlation_seconds", 60)
            if key == "multi_motion" and motion_mode == "after_contact":
                if not profile.get("contacts_enabled", True):
                    continue
                item["conditions"].insert(0, asdict(RuleCondition(roles=[Role.ENTRY, Role.GLASS])))
                item["ordered"] = True
            for condition in item["conditions"]:
                condition["roles"] = [
                    role
                    for role in condition["roles"]
                    if (role not in PERIMETER_ROLES or profile.get("perimeter_enabled", True))
                    and (role not in CONTACT_ROLES or profile.get("contacts_enabled", True))
                    and (role not in INTERIOR_ROLES or motion_mode != "ignore")
                ]
            if any(not c["roles"] for c in item["conditions"]):
                continue
            if scope is not None:
                for condition in item["conditions"]:
                    condition["sensor_ids"] = [
                        eid
                        for eid, sensor in sensors.items()
                        if sensor.get("role") in condition["roles"]
                        and (eid in scope or set(sensor.get("members", [])).intersection(scope))
                    ]
                    condition["roles"] = []
                if any(not c["sensor_ids"] for c in item["conditions"]):
                    continue
            signature = json.dumps(
                {k: v for k, v in item.items() if k not in ("id", "name")}, sort_keys=True
            )
            if signature not in signatures:
                rule_id = key if key not in rules else f"{key}_{len(rules)}"
                item["id"] = rule_id
                rules[rule_id] = item
                signatures[signature] = rule_id
            selected.append(signatures[signature])
        profile["rule_ids"] = selected
        profile["simulation_enabled"] = bool(
            profile.get("simulation_enabled") and data.get("settings", {}).get("simulation_enabled")
        )
    data["rules"] = rules
    for action in data.get("actions", {}).values():
        action["profile_ids"] = [
            key
            for key, profile in data["profiles"].items()
            if profile.get("action_ids") is None or action["id"] in profile["action_ids"]
        ]
    # Replace automatic camera effects with visible, profile-scoped actions.
    for kind, setting in (("snapshot", "auto_camera_snapshot"), ("record", "auto_camera_record")):
        if not data.get("settings", {}).get(setting, kind == "snapshot"):
            continue
        for stage in stages:
            owners = [
                key
                for key, profile in data["profiles"].items()
                if any(
                    rules[r]["stage_id"] == stage["id"]
                    and all(
                        c["event"] == "active" and set(c["roles"]) <= set(PERIMETER_ROLES)
                        for c in rules[r]["conditions"]
                    )
                    and r.startswith("perimeter")
                    and len(rules[r]["conditions"]) == 1
                    for r in profile["rule_ids"]
                )
            ]
            if owners:
                actions = data.setdefault("actions", {})
                key = f"migrated_camera_{kind}_{len(actions)}"
                while key in actions:
                    key += "x"
                actions[key] = {
                    "id": key,
                    "level": stage["id"],
                    "kind": kind,
                    "target": "trigger_camera",
                    "profile_ids": owners,
                }
