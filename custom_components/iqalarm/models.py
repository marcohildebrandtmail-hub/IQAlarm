"""Validated, serializable configuration and evidence records."""

import math
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from typing import Any
from uuid import uuid4

from .const import (
    ALLOWED_SENSOR_DOMAINS,
    ARMED_MODES,
    CONTACT_ROLES,
    MODE_NAMES,
    PERIMETER_ROLES,
    RULE_NAMES,
    UNCONFIRMED_RULES,
    Mode,
    Role,
)

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


def profile_icon(name: str, key: str = "", reactions_enabled: bool = True) -> str:
    """Choose presentation defaults once; icon/name never determine security rules."""
    words = name.casefold()
    for terms, symbol in (
        (("nacht", "night"), "weather-night"),
        (("urlaub", "vacation", "reise"), "palm-tree"),
        (("besuch", "gast", "gäste", "gaeste", "guest"), "account-group-outline"),
        (("abwesend", "away"), "home-export-outline"),
        (("zuhause", "home", "anwesend"), "home-outline"),
        (("garage",), "garage-variant"),
    ):
        if any(term in words for term in terms):
            return "mdi:" + symbol
    return {
        "armed_home": "mdi:home-outline",
        "armed_night": "mdi:weather-night",
        "armed_away": "mdi:home-export-outline",
        "armed_vacation": "mdi:palm-tree",
    }.get(key, "mdi:shield-check-outline" if reactions_enabled else "mdi:eye-outline")


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
    name: str = ""
    icon: str | None = None
    motion_mode: str = "always"
    motion_scope: str = "room"
    perimeter_enabled: bool = True
    contacts_enabled: bool = True
    reactions_enabled: bool = True
    simulation_enabled: bool = False
    stage_targets: dict[str, str] = field(default_factory=dict)
    room_ids: list[str] | None = None
    sensor_ids: list[str] | None = None
    action_ids: list[str] | None = None

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
            "perimeter_enabled",
            "contacts_enabled",
            "reactions_enabled",
            "simulation_enabled",
        ):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        if self.motion_scope not in ("room", "house"):
            raise ValueError("Bewegungsfreigabe muss room oder house sein")
        if self.motion_mode not in ("always", "after_contact", "ignore"):
            raise ValueError("Ungültige Bewegungsauswertung")
        text(self.name, "Profilname", 100, empty=True)
        if self.icon is not None and (
            not isinstance(self.icon, str)
            or not re.fullmatch(r"mdi:[a-z0-9][a-z0-9-]{0,79}", self.icon)
        ):
            raise ValueError("Profilsymbol muss eine MDI-Kennung wie mdi:home-outline sein")
        if not isinstance(self.stage_targets, dict) or set(self.stage_targets) - RULE_NAMES.keys():
            raise ValueError("Ungültige Stufenzuordnungen")
        if any(not isinstance(value, str) for value in self.stage_targets.values()):
            raise ValueError("Stufenziele müssen IDs sein")
        for key in ("room_ids", "sensor_ids", "action_ids"):
            values = getattr(self, key)
            if values is not None and (
                not isinstance(values, list)
                or any(not isinstance(value, str) for value in values)
                or len(set(values)) != len(values)
            ):
                raise ValueError(f"{key}: eindeutige Liste erforderlich; null bedeutet alle")


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
        if not isinstance(self.level, str) or not ID_RE.fullmatch(self.level):
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
        if self.level == "diagnostic" and (
            self.kind in {"siren", "switch", "script", "tts"} or self.critical
        ):
            raise ValueError(
                "Akustische/freie Aktionen und kritische Pushs sind nicht für Diagnose erlaubt"
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
    observation_profile_id: str | None = "live"

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
        if self.observation_profile_id is not None:
            text(self.observation_profile_id, "Beobachtungsprofil", 100)


@dataclass
class AlarmStage:
    id: str
    name: str
    color: str = "#2986bb"
    requires_confirmation: bool = False
    allow_loud: bool = False
    latch: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id) or self.id == "diagnostic":
            raise ValueError("Ungültige Stufen-ID")
        text(self.name, "Stufenname", 100)
        if not isinstance(self.color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", self.color):
            raise ValueError("Stufenfarbe muss eine RGB-Hexfarbe sein")
        for key in ("requires_confirmation", "allow_loud", "latch"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        if (self.allow_loud or self.latch) and not self.requires_confirmation:
            raise ValueError("Akustische oder gehaltene Stufen benötigen eine Bestätigung")


def default_stages() -> list[AlarmStage]:
    return [
        AlarmStage("0", "Sicher", "#16816a"),
        AlarmStage("1", "Vorfeld-Erkennung", "#2986bb"),
        AlarmStage("2", "Verdacht / Einzelsensor", "#b87808"),
        AlarmStage("3", "Bestätigter Alarm", "#d34454", True, True, True),
    ]


@dataclass
class FloorPlan:
    id: str
    name: str
    image: str | None = None
    width: int = 0
    height: int = 0
    zones: dict[str, list[list[float]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("Ungültige Grundriss-ID")
        text(self.name, "Grundrissname", 100)
        if self.image is not None and not re.fullmatch(r"[a-f0-9]{32}\.png", self.image):
            raise ValueError("Ungültige Grundrissdatei")
        for value in (self.width, self.height):
            if type(value) is not int or not 0 <= value <= 8192:
                raise ValueError("Ungültige Bildgröße")
        if self.image and not (self.width and self.height):
            raise ValueError("Grundriss benötigt eine Bildgröße")
        if not isinstance(self.zones, dict) or len(self.zones) > 250:
            raise ValueError("Ungültige Grundrissbereiche")
        for room_id, points in self.zones.items():
            text(room_id, "Raum-ID", 100)
            if not isinstance(points, list) or not 3 <= len(points) <= 64:
                raise ValueError("Ein Bereich benötigt 3 bis 64 Eckpunkte")
            for point in points:
                if not isinstance(point, list) or len(point) != 2:
                    raise ValueError("Ungültiger Eckpunkt")
                for coordinate in point:
                    number(coordinate, 0, 1, "Eckpunkt")
            area = sum(
                a[0] * b[1] - b[0] * a[1]
                for a, b in zip(points, points[1:] + points[:1], strict=True)
            )
            if abs(area) < 0.00001:
                raise ValueError("Bereich muss eine Fläche einschließen")


def default_profiles() -> dict[str, Profile]:
    return {
        m.value: Profile(
            name=MODE_NAMES[m],
            motion_mode="after_contact"
            if m == Mode.NIGHT
            else "ignore"
            if m == Mode.HOME
            else "always",
            contacts_enabled=m != Mode.HOME,
            simulation_enabled=m == Mode.VACATION,
            **({"correlation_seconds": 45, "entry_seconds": 5} if m == Mode.VACATION else {}),
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
    stages: list[AlarmStage] = field(default_factory=default_stages)
    floorplans: dict[str, FloorPlan] = field(default_factory=dict)

    def stage(self, stage_id: str) -> AlarmStage:
        result = next((stage for stage in self.stages if stage.id == stage_id), None)
        if result is None:
            raise ValueError("Unbekannte Alarmstufe")
        return result

    def stage_rank(self, stage_id: str) -> int:
        return next(index for index, stage in enumerate(self.stages) if stage.id == stage_id)

    def default_stage_targets(self) -> dict[str, str]:
        quiet = [stage.id for stage in self.stages if not stage.requires_confirmation]
        return {
            rule: (
                quiet[min(1 if rule == "perimeter" else 2, len(quiet) - 1)]
                if rule in UNCONFIRMED_RULES
                else self.stages[-1].id
            )
            for rule in RULE_NAMES
        }

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
        if not 1 <= len(self.profiles) <= 50:
            raise ValueError("1 bis 50 Profile erforderlich")
        if not 1 <= len(self.stages) <= 32 or len({stage.id for stage in self.stages}) != len(
            self.stages
        ):
            raise ValueError("1 bis 32 eindeutige Alarmstufen erforderlich")
        baseline = self.stages[0]
        if baseline.requires_confirmation or baseline.allow_loud or baseline.latch:
            raise ValueError("Stufe 0 ist der lautlose Normalzustand")
        stage_ids = {stage.id for stage in self.stages}
        defaults = self.default_stage_targets()
        for key, profile in self.profiles.items():
            if not isinstance(key, str) or not ID_RE.fullmatch(key) or key == Mode.DISARMED:
                raise ValueError("Ungültige Profil-ID")
            profile.name = profile.name.strip() or MODE_NAMES.get(key, "")
            text(profile.name, "Profilname", 100)
            if profile.icon is None:
                profile.icon = profile_icon(profile.name, key, profile.reactions_enabled)
            for rule, target in defaults.items():
                profile.stage_targets.setdefault(rule, target)
            if set(profile.stage_targets.values()) - stage_ids:
                raise ValueError("Profil verweist auf eine unbekannte Alarmstufe")
            for rule in UNCONFIRMED_RULES:
                if self.stage(profile.stage_targets[rule]).requires_confirmation:
                    raise ValueError(
                        "Unbestätigte Signale benötigen eine lautlose Stufe ohne Bestätigungspflicht"
                    )
            for field_name, known in (
                ("room_ids", self.rooms),
                ("sensor_ids", self.sensors),
                ("action_ids", self.actions),
            ):
                values = getattr(profile, field_name)
                if values is not None and set(values) - known.keys():
                    raise ValueError(f"Profil {profile.name}: unbekannte Zuordnung in {field_name}")
        names = [profile.name.strip().casefold() for profile in self.profiles.values()]
        if len(set(names)) != len(names):
            raise ValueError("Profilnamen müssen eindeutig sein")
        if any(key != action.id for key, action in self.actions.items()):
            raise ValueError("Aktions-ID stimmt nicht überein")
        for action in self.actions.values():
            if action.level != "diagnostic" and action.level not in stage_ids:
                raise ValueError("Aktion verweist auf eine unbekannte Alarmstufe")
            loud = action.kind in {"siren", "switch", "script", "tts"} or action.critical
            if loud and (action.level == "diagnostic" or not self.stage(action.level).allow_loud):
                raise ValueError(
                    "Akustische/freie Aktionen und kritische Pushs benötigen eine freigegebene bestätigte Stufe (standardmäßig nur in Stufe 3)"
                )
        observer = self.settings.observation_profile_id
        if observer not in (None, "live") and (
            observer not in self.profiles or self.profiles[observer].reactions_enabled
        ):
            raise ValueError(
                "Beobachtungsprofil muss vorhanden sein und Geräteaktionen ausschalten"
            )
        if len(self.floorplans) > 20:
            raise ValueError("Maximal 20 Grundrisse erlaubt")
        for key, plan in self.floorplans.items():
            if key != plan.id or set(plan.zones) - self.rooms.keys():
                raise ValueError("Grundriss verweist auf einen unbekannten Raum")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("Ungültige Konfigurationsrevision")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Configuration":
        data = migrate_configuration(data)
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError("Ungültige Konfiguration")
        for key in ("rooms", "sensors", "profiles", "actions", "settings", "floorplans"):
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
            stages=[
                construct(AlarmStage, value)
                for value in data.get("stages", [asdict(s) for s in default_stages()])
            ],
            floorplans={
                key: construct(FloorPlan, value)
                for key, value in data.get("floorplans", {}).items()
            },
        )
        result.validate()
        return result


def migrate_configuration(data: dict) -> dict:
    """Translate legacy HA-derived behavior once, keeping user rules and IDs."""
    if not isinstance(data, dict):
        raise ValueError("Ungültige Konfiguration")
    result = deepcopy(data)
    profiles = result.setdefault(
        "profiles", {key: asdict(value) for key, value in default_profiles().items()}
    )
    if not isinstance(profiles, dict):
        raise ValueError("Profile müssen ein Objekt sein")
    if (
        "observe" in profiles
        and isinstance(profiles["observe"], dict)
        and profiles["observe"].get("name") in ("Live-Beobachtung", "Beobachtung")
        and len(profiles) > 1
    ):
        profiles.pop("observe", None)
    for key, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError("Ungültiges Profil")
        base = profile.pop(
            "base_mode", key if key in ARMED_MODES and "motion_mode" not in profile else None
        )
        gated = profile.pop("night_motion_requires_contact", True)
        scope = profile.pop("night_motion_scope", "room")
        profile.setdefault("name", MODE_NAMES.get(key, key))
        profile.setdefault(
            "motion_mode", "after_contact" if base == Mode.NIGHT and gated else "always"
        )
        profile.setdefault("motion_scope", scope)
        profile.setdefault("simulation_enabled", base == Mode.VACATION)
        if (
            base == Mode.HOME
            and profile.get("room_ids") is None
            and profile.get("sensor_ids") is None
        ):
            profile["sensor_ids"] = [
                entity_id
                for entity_id, sensor in result.get("sensors", {}).items()
                if sensor["role"] in PERIMETER_ROLES
                or result.get("rooms", {}).get(sensor.get("room_id"), {}).get("home_enabled", False)
            ]
    settings = result.setdefault("settings", {})
    if not isinstance(settings, dict):
        raise ValueError("Einstellungen müssen ein Objekt sein")
    if settings.get("observation_profile_id") == "observe":
        settings["observation_profile_id"] = "live"
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
    profile_id: str | None = None
    profile_name: str = ""
    stage_id: str = "0"
    stage_name: str = ""
    confirmed: bool = False
    reactions_enabled: bool = False

    def to_dict(self) -> dict:
        return asdict(self)
