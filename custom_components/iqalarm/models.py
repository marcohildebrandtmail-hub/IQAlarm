"""Validated, serializable configuration and evidence records."""

import math
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any
from uuid import uuid4

from .const import ALLOWED_SENSOR_DOMAINS, ARMED_MODES, CONTACT_ROLES, PERIMETER_ROLES, Mode, Role

ENTITY_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z0-9_]+$")
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


def number(value: Any, minimum: float, maximum: float, name: str) -> float:
    """Reject non-finite, boolean, out-of-range and non-numeric input."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name}: Zahl erforderlich")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name}: Wert muss zwischen {minimum} und {maximum} liegen")
    return value


def text(value: Any, name: str, maximum: int = 200, empty: bool = False) -> str:
    """Validate user-visible text without silently coercing values."""
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError(f"{name}: ungültiger Text")
    return value


def entity(value: str, domains: set | frozenset | None = None) -> str:
    """Validate a concrete entity id; templates and service selectors are not entities."""
    if not isinstance(value, str) or not ENTITY_RE.fullmatch(value):
        raise ValueError("Ungültige Entitäts-ID")
    if domains and value.split(".", 1)[0] not in domains:
        raise ValueError(f"Entität {value} hat eine unzulässige Domain")
    return value


def construct[T](cls: type[T], data: dict) -> T:
    """Reject unknown fields so misspelled security settings cannot be ignored."""
    if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
        raise ValueError(f"Ungültige Felder für {cls.__name__}")
    try:
        return cls(**data)
    except TypeError as err:
        raise ValueError(f"Unvollständige Daten für {cls.__name__}") from err


@dataclass
class Room:
    id: str
    name: str
    area_id: str | None = None
    adjacent: list[str] = field(default_factory=list)
    home_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("Ungültige Raum-ID")
        text(self.name, "Raumname", 100)
        if self.area_id is not None:
            text(self.area_id, "Area-ID", 100)
        if not isinstance(self.adjacent, list) or any(
            not isinstance(x, str) for x in self.adjacent
        ):
            raise ValueError("Nachbarräume müssen eine Liste von IDs sein")
        if self.id in self.adjacent or len(set(self.adjacent)) != len(self.adjacent):
            raise ValueError("Raum darf nicht mit sich selbst oder doppelt verbunden sein")
        if type(self.home_enabled) is not bool:
            raise ValueError("home_enabled muss boolesch sein")


@dataclass
class SensorConfig:
    entity_id: str
    role: str
    room_id: str | None = None
    name: str = ""
    front_of: list[str] = field(default_factory=list)
    source_id: str = ""
    enabled: bool = True
    flap_enabled: bool = True
    flap_window: float = 15
    flap_threshold: int = 3
    debounce_ms: int = 0
    entry_delay: bool = False
    immediate: bool = False
    attribute: str | None = None
    active_states: list[str] = field(default_factory=lambda: ["on"])
    camera_entity_id: str | None = None

    def __post_init__(self) -> None:
        entity(self.entity_id, ALLOWED_SENSOR_DOMAINS)
        self.role = Role(self.role).value
        if (
            self.entity_id.startswith("lock.")
            and self.active_states == ["on"]
            and self.attribute is None
        ):
            self.active_states = ["unlocked", "open"]
        text(self.name, "Sensorname", empty=True)
        text(self.source_id, "Signalquelle", empty=True)
        if self.room_id is not None:
            text(self.room_id, "Raum-ID", 100)
        if not isinstance(self.front_of, list) or any(
            not isinstance(x, str) for x in self.front_of
        ):
            raise ValueError("Vorfeld-Räume müssen eine Liste sein")
        if self.front_of and self.role not in PERIMETER_ROLES:
            raise ValueError("Vorfeld-Räume sind nur für Vorfeld-Sensorrollen zulässig")
        if self.entry_delay and self.role not in CONTACT_ROLES:
            raise ValueError("Eingangsverzögerung ist nur für Öffnungssensoren zulässig")
        for key in ("enabled", "flap_enabled", "entry_delay", "immediate"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        number(self.flap_window, 1, 300, "Prellfenster")
        number(self.flap_threshold, 3, 100, "Prellschwelle")
        number(self.debounce_ms, 0, 60000, "Entprellzeit")
        if type(self.flap_threshold) is not int or type(self.debounce_ms) is not int:
            raise ValueError("Schwelle und Millisekunden müssen ganzzahlig sein")
        if (
            not isinstance(self.active_states, list)
            or not self.active_states
            or len(self.active_states) > 30
        ):
            raise ValueError("Mindestens ein aktiver Zustand erforderlich")
        for state in self.active_states:
            text(state, "Aktiver Zustand", 100)
            if state in ("unknown", "unavailable"):
                raise ValueError("unknown/unavailable sind niemals Alarmauslöser")
        if self.attribute is not None:
            text(self.attribute, "Attribut", 100)
        if self.entity_id.startswith(("camera.", "image_processing.")) and not self.attribute:
            raise ValueError("Kamera/Bildauswertung benötigt ein explizites Erkennungsattribut")
        if self.role in CONTACT_ROLES and self.room_id is None:
            raise ValueError("Öffnungssensor benötigt einen Raum")
        if self.role in (Role.MOTION, Role.MMWAVE) and self.room_id is None:
            raise ValueError("Innenraumsensor benötigt einen Raum")
        if self.camera_entity_id is not None:
            entity(self.camera_entity_id, {"camera"})


@dataclass
class Profile:
    perimeter_seconds: float = 180
    correlation_seconds: float = 60
    entry_seconds: float = 20
    exit_seconds: float = 0
    perimeter_contact: bool = True
    contact_motion: bool = True
    multi_contact: bool = True
    multi_motion: bool = True
    adjacent_rooms: bool = True
    night_motion_requires_contact: bool = True
    night_motion_scope: str = "room"

    def __post_init__(self) -> None:
        for key in ("perimeter_seconds", "correlation_seconds"):
            number(getattr(self, key), 1, 3600, key)
        for key in ("entry_seconds", "exit_seconds"):
            number(getattr(self, key), 0, 600, key)
        for key in (
            "perimeter_contact",
            "contact_motion",
            "multi_contact",
            "multi_motion",
            "adjacent_rooms",
            "night_motion_requires_contact",
        ):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        if self.night_motion_scope not in ("room", "house"):
            raise ValueError("Nacht-Scharfschaltung muss room oder house sein")


@dataclass
class Action:
    id: str
    level: str
    kind: str
    target: str = ""
    title: str = "IQAlarm · Stufe {{level}}"
    message: str = "{{room}}: {{sensor}} — {{reason}}"
    critical: bool = False
    camera_entity_id: str | None = None
    duration: int = 180
    brightness: int = 100
    color: list[int] | None = None
    media_player: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("Ungültige Aktions-ID")
        if self.level not in ("1", "2", "3", "diagnostic"):
            raise ValueError("Ungültige Aktionsstufe")
        allowed = {
            "notify",
            "siren",
            "switch",
            "script",
            "light",
            "cover",
            "snapshot",
            "record",
            "tts",
        }
        if self.kind not in allowed:
            raise ValueError("Unbekannte Aktionsart")
        if self.level != "3" and (
            self.kind in {"siren", "switch", "script", "tts"} or self.critical
        ):
            raise ValueError(
                "Akustische/freie Aktionen und kritische Pushs sind nur in Stufe 3 erlaubt"
            )
        if self.kind in {"siren", "switch", "script", "light", "cover", "tts"}:
            entity(self.target, {self.kind})
        if self.kind == "notify":
            entity(self.target, {"notify"})
        if self.kind in {"snapshot", "record"}:
            entity(self.target, {"camera"})
        if self.kind == "tts":
            entity(self.media_player, {"media_player"})
        if self.camera_entity_id:
            entity(self.camera_entity_id, {"camera"})
        for key in ("enabled", "critical"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        number(self.duration, 1, 3600, "Aktionsdauer")
        number(self.brightness, 1, 100, "Helligkeit")
        if type(self.duration) is not int or type(self.brightness) is not int:
            raise ValueError("Dauer und Helligkeit müssen ganzzahlig sein")
        if self.color is not None and (
            not isinstance(self.color, list)
            or len(self.color) != 3
            or any(type(n) is not int or not 0 <= n <= 255 for n in self.color)
        ):
            raise ValueError("Farbe muss aus drei RGB-Werten bestehen")
        text(self.title, "Titel", 200)
        text(self.message, "Nachricht", 3000)


@dataclass
class Settings:
    diagnose_disarmed: bool = True
    block_open_on_arm: bool = True
    block_unavailable_on_arm: bool = True
    auto_camera_snapshot: bool = True
    auto_camera_record: bool = False
    retention_days: int = 7
    simulation_enabled: bool = False
    simulation_lights: list[str] = field(default_factory=list)
    simulation_start: int = 18
    simulation_end: int = 23
    debounce_by_role: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key in (
            "diagnose_disarmed",
            "block_open_on_arm",
            "block_unavailable_on_arm",
            "auto_camera_snapshot",
            "auto_camera_record",
            "simulation_enabled",
        ):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        number(self.retention_days, 1, 90, "Aufbewahrung")
        number(self.simulation_start, 0, 23, "Simulationsbeginn")
        number(self.simulation_end, 1, 24, "Simulationsende")
        if any(
            type(getattr(self, key)) is not int
            for key in ("retention_days", "simulation_start", "simulation_end")
        ):
            raise ValueError("Stunden/Tage müssen ganzzahlig sein")
        if self.simulation_start >= self.simulation_end:
            raise ValueError("Simulationsende muss nach Beginn liegen")
        if not isinstance(self.simulation_lights, list) or len(self.simulation_lights) > 100:
            raise ValueError("Ungültige Simulationslichter")
        for light in self.simulation_lights:
            entity(light, {"light"})
        if not isinstance(self.debounce_by_role, dict):
            raise ValueError("Entprellzeiten müssen ein Objekt sein")
        for role, value in self.debounce_by_role.items():
            Role(role)
            number(value, 0, 60000, "Entprellzeit")
            if type(value) is not int:
                raise ValueError("Entprellzeit muss ganzzahlig sein")


def default_profiles() -> dict[str, Profile]:
    return {
        m.value: Profile(
            **({"correlation_seconds": 45, "entry_seconds": 5} if m == Mode.VACATION else {})
        )
        for m in ARMED_MODES
    }


@dataclass
class Configuration:
    rooms: dict[str, Room] = field(default_factory=dict)
    sensors: dict[str, SensorConfig] = field(default_factory=dict)
    profiles: dict[str, Profile] = field(default_factory=default_profiles)
    actions: dict[str, Action] = field(default_factory=dict)
    settings: Settings = field(default_factory=Settings)
    revision: int = 0

    def validate(self) -> None:
        if len(self.rooms) > 250 or len(self.sensors) > 1000 or len(self.actions) > 100:
            raise ValueError("Maximal 250 Räume, 1000 Sensoren und 100 Aktionen erlaubt")
        for key, room in self.rooms.items():
            if key != room.id or set(room.adjacent) - self.rooms.keys():
                raise ValueError("Raum-Verknüpfung verweist auf unbekannten Raum")
        for key, sensor in self.sensors.items():
            if key != sensor.entity_id:
                raise ValueError("Sensor-ID stimmt nicht überein")
            if sensor.room_id is not None and sensor.room_id not in self.rooms:
                raise ValueError("Sensor verweist auf unbekannten Raum")
            if set(sensor.front_of) - self.rooms.keys():
                raise ValueError("Vorfeld verweist auf unbekannten Raum")
        if set(self.profiles) != {m.value for m in ARMED_MODES}:
            raise ValueError("Alle vier scharfen Profile sind erforderlich")
        if any(key != action.id for key, action in self.actions.items()):
            raise ValueError("Aktions-ID stimmt nicht überein")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("Ungültige Konfigurationsrevision")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Configuration":
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError("Ungültige Konfiguration")
        for key in ("rooms", "sensors", "profiles", "actions", "settings"):
            if key in data and not isinstance(data[key], dict):
                raise ValueError(f"{key} muss ein Objekt sein")
        result = cls(
            rooms={k: construct(Room, v) for k, v in data.get("rooms", {}).items()},
            sensors={k: construct(SensorConfig, v) for k, v in data.get("sensors", {}).items()},
            profiles={
                k: construct(Profile, v)
                for k, v in data.get(
                    "profiles", {k: asdict(v) for k, v in default_profiles().items()}
                ).items()
            },
            actions={k: construct(Action, v) for k, v in data.get("actions", {}).items()},
            settings=construct(Settings, data.get("settings", {})),
            revision=data.get("revision", 0),
        )
        result.validate()
        return result


@dataclass(frozen=True)
class Evidence:
    entity_id: str
    source_id: str
    role: str
    room_id: str | None
    timestamp: float
    name: str


@dataclass
class EventLog:
    timestamp: float
    kind: str
    level: int
    mode: str
    reason: str
    room_id: str | None = None
    entity_id: str | None = None
    chain: list[dict] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)

    def to_dict(self) -> dict:
        return asdict(self)
