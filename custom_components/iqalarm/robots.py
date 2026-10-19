"""Explicit robot activity and bounded coverage reduction, separate from intrusion proof."""

from dataclasses import dataclass, field

from .const import INTERIOR_ROLES


@dataclass
class RobotActivity:
    entity_id: str
    active_states: list[str] = field(
        default_factory=lambda: ["on", "cleaning", "returning", "mowing", "working"]
    )
    attribute: str | None = None

    def __post_init__(self):
        from .models import entity, text

        entity(self.entity_id)
        if not isinstance(self.active_states, list) or not 1 <= len(self.active_states) <= 20:
            raise ValueError("Roboter-Aktivität benötigt 1 bis 20 aktive Zustände")
        for value in self.active_states:
            text(value, "Aktiver Roboterzustand", 100)
            if value.strip().casefold() in {"unknown", "unavailable"}:
                raise ValueError("Unbekannt / nicht verfügbar ist kein aktiver Roboterzustand")
        if self.attribute is not None:
            text(self.attribute, "Aktivitätsattribut", 100)


@dataclass
class RobotConfig:
    id: str
    name: str
    activities: list[RobotActivity]
    room_ids: list[str] = field(default_factory=list)
    floorplan_id: str | None = None
    risk_points: int = 1
    enabled: bool = True

    def __post_init__(self):
        from .models import ID_RE, construct, text

        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("Ungültige Roboter-ID")
        text(self.name, "Robotername", 100)
        if not isinstance(self.activities, list) or not 1 <= len(self.activities) <= 3:
            raise ValueError("Pro Roboter sind 1 bis 3 Aktivitätsentitäten erlaubt")
        self.activities = [
            construct(RobotActivity, item) if isinstance(item, dict) else item
            for item in self.activities
        ]
        if any(not isinstance(item, RobotActivity) for item in self.activities):
            raise ValueError("Ungültige Roboter-Aktivitätsentität")
        keys = [(item.entity_id, item.attribute) for item in self.activities]
        if len(set(keys)) != len(keys):
            raise ValueError("Aktivitätsentität doppelt eingetragen")
        if not isinstance(self.room_ids, list) or any(
            not isinstance(room, str) or not ID_RE.fullmatch(room) for room in self.room_ids
        ):
            raise ValueError("Ungültige Roboterräume")
        if len(self.room_ids) > 250 or len(set(self.room_ids)) != len(self.room_ids):
            raise ValueError("Roboterräume müssen eindeutig sein")
        if self.floorplan_id is not None and (
            not isinstance(self.floorplan_id, str) or not ID_RE.fullmatch(self.floorplan_id)
        ):
            raise ValueError("Ungültige Roboter-Etage")
        if bool(self.room_ids) == bool(self.floorplan_id):
            raise ValueError("Für einen Roboter Räume oder eine Etage auswählen")
        if type(self.risk_points) is not int or not 1 <= self.risk_points <= 3:
            raise ValueError("Überwachungsrisiko benötigt 1 bis 3 Punkte")
        if type(self.enabled) is not bool:
            raise ValueError("Roboter-Ausnahme muss aktiviert oder deaktiviert sein")

    def rooms(self, config):
        return (
            set(config.floorplans[self.floorplan_id].zones)
            if self.floorplan_id
            else set(self.room_ids)
        )


def evaluate_robots(config, readings):
    """Any explicitly active input activates one robot; unknown never means working."""
    devices = []
    grouped = config.window_members()
    for robot in config.robots.values():
        if not robot.enabled:
            continue
        sources = []
        for source in robot.activities:
            reading = readings.get(source.entity_id)
            value = None
            if reading and reading.get("state") not in (None, "unknown", "unavailable"):
                value = (
                    reading.get("attributes", {}).get(source.attribute)
                    if source.attribute
                    else reading["state"]
                )
            state = str(value).strip().casefold() if value is not None else None
            active = state is not None and state in {
                s.strip().casefold() for s in source.active_states
            }
            sources.append(
                {
                    "entity_id": source.entity_id,
                    "attribute": source.attribute,
                    "value": value,
                    "active": active,
                    "available": state not in (None, "unknown", "unavailable"),
                }
            )
        rooms = robot.rooms(config)
        sensors = [
            key
            for key, sensor in config.all_sensors().items()
            if sensor.enabled
            and sensor.role in INTERIOR_ROLES
            and sensor.room_id in rooms
            and key not in grouped
        ]
        devices.append(
            {
                "id": robot.id,
                "name": robot.name,
                "active": any(source["active"] for source in sources),
                "fault": any(not source["available"] for source in sources),
                "sources": sources,
                "room_ids": sorted(rooms),
                "sensors": sensors,
                "risk_points": robot.risk_points,
            }
        )
    return devices
