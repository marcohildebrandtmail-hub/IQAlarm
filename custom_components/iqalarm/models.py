"""Validated, serializable configuration and evidence records."""

import math
import re
from copy import deepcopy
from dataclasses import asdict, dataclass, field, fields
from typing import Any
from uuid import uuid4

from .automatic_detection import AUTO_RULE, DETECTED_RULE, AutomaticDetection
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
from .level_rules import LevelRule, default_rules, upgrade_level_rules
from .robots import RobotConfig

ENTITY_RE = re.compile(r"^[a-z_][a-z0-9_]*\.[a-z0-9_]+$")
ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


def display_icon(value: str | None) -> None:
    """Validate an optional presentation override, independently of alarm roles."""
    if value is not None and (
        not isinstance(value, str) or not re.fullmatch(r"mdi:[a-z0-9][a-z0-9-]{0,79}", value)
    ):
        raise ValueError("Symbol muss eine gültige MDI-Kennung sein, z. B. mdi:fridge-outline")


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
    icon: str | None = None

    def __post_init__(self) -> None:
        display_icon(self.icon)
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
    sensor_kind: str | None = None
    active_above: float | None = None
    icon: str | None = None
    activation_mode: str = "state"

    def __post_init__(self) -> None:
        display_icon(self.icon)
        entity(self.entity_id, ALLOWED_SENSOR_DOMAINS)
        self.role = Role(self.role).value
        if self.activation_mode not in ("state", "change"):
            raise ValueError("Unbekannte Sensorauswertung")
        if self.activation_mode == "change" and self.role != Role.MOTION:
            raise ValueError("Zustandswechsel-Auswertung benötigt die Rolle Bewegung innen")
        if self.sensor_kind is None:
            self.sensor_kind = (
                "window_handle"
                if re.search(r"fenstergriff|window.?handle", f"{self.entity_id} {self.name}", re.I)
                else "door_lock"
                if self.role == Role.LOCK
                else "generic"
            )
        if self.sensor_kind not in ("generic", "window_handle", "door_lock"):
            raise ValueError("Unbekannte Sensorart")
        if self.sensor_kind != "generic" and self.role not in CONTACT_ROLES:
            raise ValueError("Fenstergriff/Türschloss benötigt eine Außenhaut-Rolle")
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
        if self.active_above is not None:
            number(self.active_above, -1_000_000, 1_000_000, "Erkennungsschwelle")
            if not self.attribute:
                raise ValueError("Numerische Erkennungsschwelle benötigt ein Attribut")
        if self.entity_id.startswith(("camera.", "image_processing.")) and not self.attribute:
            raise ValueError("Kamera/Bildauswertung benötigt ein explizites Erkennungsattribut")
        if self.role in CONTACT_ROLES and self.room_id is None:
            raise ValueError("Öffnungssensor benötigt einen Raum")
        if self.role in (Role.MOTION, Role.MMWAVE) and self.room_id is None:
            raise ValueError("Innenraumsensor benötigt einen Raum")
        if self.camera_entity_id is not None:
            entity(self.camera_entity_id, {"camera"})

    @property
    def information_only(self) -> bool:
        return self.sensor_kind == "window_handle"


WINDOW_STATES = {
    "closed": ("Geschlossen", "closed", "closed"),
    "unlatched": ("Geschlossen · entriegelt", "closed", "turn"),
    "open": ("Offen", "open", "turn"),
    "tilt_ready": ("Geschlossen · Griff in Kippstellung", "closed", "tilt"),
    "tilted": ("Gekippt geöffnet", "tilted", "tilt"),
}


@dataclass
class WindowConfig:
    """One physical window; raw inputs never confirm one another."""

    id: str
    name: str
    room_id: str
    contact_entity_id: str | None = None
    handle_entity_ids: list[str] = field(default_factory=list)
    lock_entity_id: str | None = None
    availability_entity_id: str | None = None
    availability_states: list[str] = field(default_factory=list)
    allow_unknown_inputs: list[str] = field(default_factory=list)
    mappings: list[dict] = field(default_factory=list)
    settle_seconds: float = 1
    enabled: bool = True
    entry_delay: bool = False
    contact_open_states: list[str] = field(default_factory=lambda: ["on"])
    contact_closed_states: list[str] = field(default_factory=lambda: ["off"])
    immediate: bool = False
    debounce_ms: int = 0
    flap_enabled: bool = True
    flap_window: float = 15
    flap_threshold: int = 3
    icon: str | None = None

    @property
    def sensor_id(self) -> str:
        return f"binary_sensor.iqalarm_window_{self.id}"

    @property
    def position_inputs(self) -> list[str]:
        return ([self.contact_entity_id] if self.contact_entity_id else []) + self.handle_entity_ids

    @property
    def members(self) -> list[str]:
        return list(
            dict.fromkeys(
                self.position_inputs
                + [e for e in (self.lock_entity_id, self.availability_entity_id) if e]
            )
        )

    def __post_init__(self) -> None:
        display_icon(self.icon)
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("Ungültige Fenster-ID")
        text(self.name, "Fenstername", 100)
        text(self.room_id, "Raum-ID", 100)
        if not isinstance(self.handle_entity_ids, list) or len(self.handle_entity_ids) > 2:
            raise ValueError("Maximal zwei Griffsignale erlaubt")
        for value in self.members:
            entity(value, {"binary_sensor", "sensor", "lock"})
        for value in self.position_inputs:
            entity(value, {"binary_sensor", "sensor"})
        if self.lock_entity_id:
            entity(self.lock_entity_id, {"lock"})
        if not self.position_inputs or len(set(self.position_inputs)) != len(self.position_inputs):
            raise ValueError("Mindestens ein eindeutiger Stellungssensor erforderlich")
        for key in ("enabled", "entry_delay", "immediate", "flap_enabled"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        number(self.settle_seconds, 0.2, 10, "Stabilisierungszeit")
        number(self.debounce_ms, 0, 60000, "Entprellzeit")
        number(self.flap_window, 1, 300, "Prellfenster")
        number(self.flap_threshold, 3, 100, "Prellschwelle")
        if type(self.debounce_ms) is not int or type(self.flap_threshold) is not int:
            raise ValueError("Entprellzeit und Prellschwelle müssen ganzzahlig sein")
        for key in (
            "availability_states",
            "allow_unknown_inputs",
            "contact_open_states",
            "contact_closed_states",
        ):
            values = getattr(self, key)
            if not isinstance(values, list) or len(values) > 20 or len(set(values)) != len(values):
                raise ValueError(f"Ungültige Liste: {key}")
            for value in values:
                text(value, key, 100)
        if not self.contact_open_states or set(self.contact_open_states) & {
            "unknown",
            "unavailable",
        }:
            raise ValueError("Ungültige Kontakt-Offenwerte")
        if not self.contact_closed_states or set(self.contact_closed_states) & {
            "unknown",
            "unavailable",
        }:
            raise ValueError("Ungültige Kontakt-Geschlossenwerte")
        if set(self.contact_open_states) & set(self.contact_closed_states):
            raise ValueError("Offen- und Geschlossenwerte müssen verschieden sein")
        if self.allow_unknown_inputs and (
            set(self.allow_unknown_inputs) - set(self.handle_entity_ids)
            or (self.availability_entity_id and self.availability_entity_id in self.position_inputs)
        ):
            raise ValueError("unknown als Griffcode ist nur für Griffsensoren zulässig")
        if set(self.availability_states) & {"unknown", "unavailable"}:
            raise ValueError("Fehlzustände dürfen keine Verbindung bestätigen")
        if not isinstance(self.mappings, list) or len(self.mappings) > len(WINDOW_STATES):
            raise ValueError("Ungültige Fensterstellungen")
        seen_states, signatures = set(), {}
        for mapping in self.mappings:
            if not isinstance(mapping, dict) or set(mapping) != {"state", "values"}:
                raise ValueError("Ungültige Stellungszuordnung")
            state, values = mapping["state"], mapping["values"]
            if state not in WINDOW_STATES or state in seen_states:
                raise ValueError("Fensterstellungen müssen eindeutig sein")
            seen_states.add(state)
            if not isinstance(values, dict) or set(values) != set(self.position_inputs):
                raise ValueError("Stellungszuordnung muss alle Eingangssignale enthalten")
            for source, value in values.items():
                text(value, "Signalzustand", 100)
                if value == "unavailable" or (
                    value == "unknown"
                    and source not in self.handle_entity_ids
                    and source not in self.allow_unknown_inputs
                ):
                    raise ValueError(
                        "Keine Verbindung darf nicht als Fensterstellung eingelernt werden"
                    )
            if self.contact_entity_id:
                contact = values[self.contact_entity_id]
                allowed = (
                    self.contact_open_states
                    if WINDOW_STATES[state][1] in ("open", "tilted")
                    else self.contact_closed_states
                )
                if contact not in allowed:
                    raise ValueError(
                        "Fensterstellung widerspricht den Kontakt-Offen-/Geschlossenwerten"
                    )
            signature = tuple(sorted(values.items()))
            if signature in signatures:
                raise ValueError(
                    "Diese Stellungen sind mit den ausgewählten Sensoren nicht unterscheidbar"
                )
            signatures[signature] = state


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
    multi_contact: bool = False
    multi_motion: bool = False
    adjacent_rooms: bool = False
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
    confirmation_paths: list[list[str]] = field(default_factory=list)
    rule_ids: list[str] | None = None
    automatic_detection: bool = True

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
            "automatic_detection",
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
        if not isinstance(self.confirmation_paths, list) or len(self.confirmation_paths) > 500:
            raise ValueError("Maximal 500 ausdrückliche Bestätigungswege erlaubt")
        seen_paths = set()
        for path in self.confirmation_paths:
            if (
                not isinstance(path, list)
                or len(path) != 2
                or any(not isinstance(room, str) for room in path)
                or path[0] == path[1]
            ):
                raise ValueError(
                    "Bestätigungsweg benötigt zwei verschiedene Räume in Ereignisreihenfolge"
                )
            if tuple(path) in seen_paths:
                raise ValueError("Bestätigungsweg darf nicht doppelt vorhanden sein")
            seen_paths.add(tuple(path))
        for key in ("room_ids", "sensor_ids", "action_ids", "rule_ids"):
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
    profile_ids: list[str] | None = None
    trigger: str = "level_entered"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not ID_RE.fullmatch(self.id):
            raise ValueError("Ungültige Aktions-ID")
        if self.trigger not in ("level_entered", "rule_confirmed"):
            raise ValueError("Ungültiger Aktionszeitpunkt")
        if self.level == "diagnostic" and self.trigger == "rule_confirmed":
            raise ValueError("Diagnose verwendet keinen Bestätigungsgrad")
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
        if self.kind in {"snapshot", "record"} and self.target != "trigger_camera":
            entity(self.target, {"camera"})
        if self.profile_ids is not None and (
            not isinstance(self.profile_ids, list)
            or len(self.profile_ids) > 50
            or any(not isinstance(p, str) or not ID_RE.fullmatch(p) for p in self.profile_ids)
        ):
            raise ValueError("Ungültige Alarmmodus-Zuordnung der Aktion")
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
    quiet_disarmed_floorplan: bool = True
    quiet_disarmed_locks: bool = True
    recent_seconds: int = 30
    floorplan_disarmed_motion: bool = True
    floorplan_disarmed_contacts: bool = True
    floorplan_disarmed_locks: bool = False
    floorplan_disarmed_cameras: bool = True
    floorplan_disarmed_animation: bool = False
    floorplan_armed_animation: bool = True
    room_order: list[str] = field(default_factory=list)
    sensor_order: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key in (
            "diagnose_disarmed",
            "block_open_on_arm",
            "block_unavailable_on_arm",
            "auto_camera_snapshot",
            "auto_camera_record",
            "simulation_enabled",
            "quiet_disarmed_floorplan",
            "quiet_disarmed_locks",
            "floorplan_disarmed_motion",
            "floorplan_disarmed_contacts",
            "floorplan_disarmed_locks",
            "floorplan_disarmed_cameras",
            "floorplan_disarmed_animation",
            "floorplan_armed_animation",
        ):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} muss boolesch sein")
        number(self.retention_days, 1, 90, "Aufbewahrung")
        number(self.simulation_start, 0, 23, "Simulationsbeginn")
        number(self.simulation_end, 1, 24, "Simulationsende")
        number(self.recent_seconds, 5, 300, "Kürzlich-Dauer")
        if any(
            type(getattr(self, key)) is not int
            for key in ("retention_days", "simulation_start", "simulation_end", "recent_seconds")
        ):
            raise ValueError("Stunden/Tage/Sekunden müssen ganzzahlig sein")
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
        if not isinstance(self.room_order, list):
            raise ValueError("Raum-Reihenfolge muss eine Liste sein")
        if not all(isinstance(x, str) for x in self.room_order):
            raise ValueError("Raum-Reihenfolge darf nur Raum-IDs enthalten")
        if len(self.room_order) > 250:
            raise ValueError("Maximal 250 Räume in der Reihenfolge erlaubt")
        if not isinstance(self.sensor_order, dict) or len(self.sensor_order) > 251:
            raise ValueError("Sensor-Reihenfolge muss ein Objekt mit maximal 251 Gruppen sein")
        for room_id, order in self.sensor_order.items():
            if not isinstance(room_id, str) or (room_id and not ID_RE.fullmatch(room_id)):
                raise ValueError("Ungültiger Raum in der Sensor-Reihenfolge")
            if not isinstance(order, list) or len(order) > 1250:
                raise ValueError(
                    "Sensor-Reihenfolge benötigt eine Liste mit maximal 1250 Einträgen"
                )
            for sensor_id in order:
                entity(sensor_id, ALLOWED_SENSOR_DOMAINS)


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
        AlarmStage("0", "Deaktiviert", "#ffffff"),
        AlarmStage("1", "Sicher", "#64bc29"),
        AlarmStage("2", "Bewegung Außen", "#08ba1d"),
        AlarmStage("3", "Erste Sensorauslösung / Fehlerfall", "#cad345"),
        AlarmStage("4", "Bewegung Innen", "#bc2929"),
        AlarmStage("5", "ALARM!!!", "#8000ff", True, True, True),
    ]


@dataclass
class FloorPlan:
    id: str
    name: str
    image: str | None = None
    width: int = 0
    height: int = 0
    zones: dict[str, list[list[float]]] = field(default_factory=dict)
    labels: dict[str, list[float]] = field(default_factory=dict)
    image_opacity: float = 0

    def __post_init__(self) -> None:
        number(self.image_opacity, 0, 1, "Originalbild-Deckkraft")
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
        if not isinstance(self.labels, dict) or len(self.labels) > 250:
            raise ValueError("Ungültige Beschriftungspositionen")
        for room_id, point in self.labels.items():
            text(room_id, "Raum-ID", 100)
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Ungültige Beschriftungskoordinate")
            for coordinate in point:
                number(coordinate, 0, 1, "Beschriftungskoordinate")


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
            rule_ids=["perimeter", "fault", "immediate"]
            + (
                [
                    "single",
                    "flapping",
                    "perimeter_contact",
                    "contact_motion" if m == Mode.NIGHT else "contact_motion_any_order",
                ]
                if m != Mode.HOME
                else []
            )
            + (["motion"] if m in (Mode.AWAY, Mode.VACATION) else []),
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
    windows: dict[str, WindowConfig] = field(default_factory=dict)
    policy_version: int = 2
    secure_stage_id: str = "1"
    rules: dict[str, LevelRule] | None = field(default_factory=default_rules)
    room_connections: list[list[str]] = field(default_factory=list)
    robots: dict[str, RobotConfig] = field(default_factory=dict)
    automatic_detection: AutomaticDetection | None = None

    def all_sensors(self) -> dict[str, SensorConfig]:
        return self.sensors | {
            window.sensor_id: SensorConfig(
                window.sensor_id,
                Role.ENTRY,
                window.room_id,
                name=window.name,
                icon=window.icon,
                source_id=self.sensors[window.contact_entity_id].source_id or f"window:{window.id}"
                if window.contact_entity_id in self.sensors
                else f"window:{window.id}",
                enabled=window.enabled,
                entry_delay=window.entry_delay,
                immediate=window.immediate,
                debounce_ms=window.debounce_ms,
                flap_enabled=window.flap_enabled,
                flap_window=window.flap_window,
                flap_threshold=window.flap_threshold,
                sensor_kind="generic",
            )
            for window in self.windows.values()
        }

    def window_members(self) -> set[str]:
        return {source for window in self.windows.values() for source in window.members}

    def stage(self, stage_id: str) -> AlarmStage:
        result = next((stage for stage in self.stages if stage.id == stage_id), None)
        if result is None:
            raise ValueError("Unbekannte Alarmstufe")
        return result

    def stage_rank(self, stage_id: str) -> int:
        return next(index for index, stage in enumerate(self.stages) if stage.id == stage_id)

    def default_stage_targets(self) -> dict[str, str]:
        secure_rank = self.stage_rank(self.secure_stage_id)
        quiet = [
            stage.id for stage in self.stages[secure_rank + 1 :] if not stage.requires_confirmation
        ] or [self.secure_stage_id]
        return {
            rule: (
                quiet[
                    min(0 if rule == "perimeter" else 2 if rule == "motion" else 1, len(quiet) - 1)
                ]
                if rule in UNCONFIRMED_RULES
                else self.stages[-1].id
            )
            for rule in RULE_NAMES
        }

    def validate(self) -> None:
        if self.automatic_detection is not None:
            detection = self.automatic_detection
            if not isinstance(detection, AutomaticDetection) or self.rules is None:
                raise ValueError("Ungültige automatische Erkennung")
            self.stage(detection.stage_id)
            self.stage(detection.next_stage_id)
            start, target = (
                self.stage_rank(detection.stage_id),
                self.stage_rank(detection.next_stage_id),
            )
            if start <= self.stage_rank(self.secure_stage_id) or target != start + 1:
                raise ValueError(
                    "Automatische Erkennung benötigt zwei aufeinanderfolgende Stufen oberhalb Sicher"
                )
            if (
                self.stage(detection.stage_id).requires_confirmation
                or self.stage(detection.next_stage_id).requires_confirmation
            ):
                raise ValueError("Automatische Erkennung darf keine Vollalarmstufe verwenden")
            if {AUTO_RULE, DETECTED_RULE}.intersection(self.rules):
                raise ValueError("Regel-ID ist für automatische Erkennung reserviert")
        if not isinstance(self.robots, dict) or len(self.robots) > 100:
            raise ValueError("Maximal 100 Roboter-Ausnahmen erlaubt")
        for key, robot in self.robots.items():
            if not isinstance(robot, RobotConfig) or key != robot.id:
                raise ValueError("Ungültige Roboter-Zuordnung")
            if set(robot.room_ids) - self.rooms.keys():
                raise ValueError("Roboter verweist auf unbekannte Räume")
            if robot.floorplan_id is not None and robot.floorplan_id not in self.floorplans:
                raise ValueError("Roboter verweist auf unbekannte Etage")
            if any(
                source.entity_id in self.all_sensors() or source.entity_id in self.window_members()
                for source in robot.activities
            ):
                raise ValueError(
                    "Roboter-Aktivität benötigt eigene Statusentitäten außerhalb der Alarmeingänge"
                )
        if not isinstance(self.room_connections, list) or len(self.room_connections) > 500:
            raise ValueError("Maximal 500 direkte Raumverbindungen erlaubt")
        seen_connections = set()
        for pair in self.room_connections:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or any(not isinstance(room, str) or room not in self.rooms for room in pair)
                or pair[0] == pair[1]
            ):
                raise ValueError("Eine Tür verbindet zwei verschiedene vorhandene Räume")
            key = tuple(sorted(pair))
            if key in seen_connections:
                raise ValueError("Raumverbindung doppelt eingetragen")
            seen_connections.add(key)
        if self.rules is not None and (not isinstance(self.rules, dict) or len(self.rules) > 500):
            raise ValueError("Maximal 500 Levelregeln als Objekt erlaubt")
        if len(self.rooms) > 250 or len(self.sensors) > 1000 or len(self.actions) > 500:
            raise ValueError("Maximal 250 Räume, 1000 Sensoren und 500 Aktionen erlaubt")
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
        if len(self.windows) > 250:
            raise ValueError("Maximal 250 Fenster erlaubt")
        used = set()
        for key, window in self.windows.items():
            if key != window.id or window.room_id not in self.rooms:
                raise ValueError("Fenster verweist auf einen unbekannten Raum")
            if not {"closed", "open"} <= {mapping["state"] for mapping in window.mappings}:
                raise ValueError(
                    "Fenster benötigt mindestens die eingelernten Stellungen Geschlossen und Offen"
                )
            if used.intersection(window.position_inputs):
                raise ValueError("Ein Stellungssensor darf nur zu einem Fenster gehören")
            used.update(window.position_inputs)
            if window.sensor_id in self.sensors or set(window.members).intersection(
                w.sensor_id for w in self.windows.values()
            ):
                raise ValueError("Zusammengeführte Fenster dürfen keine Schleifen bilden")
        if not 1 <= len(self.profiles) <= 50:
            raise ValueError("1 bis 50 Profile erforderlich")
        if not 1 <= len(self.stages) <= 32 or len({stage.id for stage in self.stages}) != len(
            self.stages
        ):
            raise ValueError("1 bis 32 eindeutige Alarmstufen erforderlich")
        baseline = self.stages[0]
        if baseline.requires_confirmation or baseline.allow_loud or baseline.latch:
            raise ValueError("Stufe 0 ist der lautlose Normalzustand")
        secure = self.stage(self.secure_stage_id)
        if secure.requires_confirmation or secure.allow_loud or secure.latch:
            raise ValueError(
                "Der aktive Normalzustand muss lautlos, ohne Bestätigung und Halten sein"
            )
        stage_ids = {stage.id for stage in self.stages}
        defaults = self.default_stage_targets()
        for key, profile in self.profiles.items():
            if not isinstance(key, str) or not ID_RE.fullmatch(key) or key == Mode.DISARMED:
                raise ValueError("Ungültige Profil-ID")
            profile.name = profile.name.strip() or MODE_NAMES.get(key, "")
            text(profile.name, "Profilname", 100)
            if profile.icon is None:
                profile.icon = profile_icon(profile.name, key, profile.reactions_enabled)
            if self.rules is None:
                for rule, target in defaults.items():
                    profile.stage_targets.setdefault(rule, target)
            if any(room not in self.rooms for path in profile.confirmation_paths for room in path):
                raise ValueError("Bestätigungsweg verweist auf unbekannten Raum")
            if self.rules is None and set(profile.stage_targets.values()) - stage_ids:
                raise ValueError("Profil verweist auf eine unbekannte Alarmstufe")
            for rule in UNCONFIRMED_RULES if self.rules is None else ():
                if self.stage(profile.stage_targets[rule]).requires_confirmation:
                    raise ValueError(
                        "Unbestätigte Signale benötigen eine lautlose Stufe ohne Bestätigungspflicht"
                    )
            for field_name, known in (
                ("room_ids", self.rooms),
                ("sensor_ids", self.all_sensors()),
                ("action_ids", self.actions),
            ):
                values = getattr(profile, field_name)
                if self.rules is None and values is not None and set(values) - known.keys():
                    raise ValueError(f"Profil {profile.name}: unbekannte Zuordnung in {field_name}")
            if (
                self.rules is not None
                and profile.rule_ids is not None
                and set(profile.rule_ids) - self.rules.keys()
            ):
                raise ValueError(f"Profil {profile.name}: unbekannte Levelregel")
        if self.rules is not None:
            if not isinstance(self.rules, dict) or len(self.rules) > 500:
                raise ValueError("Maximal 500 Levelregeln erlaubt")
            sensors = self.all_sensors()
            for key, rule in self.rules.items():
                if not isinstance(rule, LevelRule):
                    raise ValueError("Ungültige Levelregel")
                if key != rule.id or rule.stage_id not in stage_ids:
                    raise ValueError("Regel verweist auf eine unbekannte Alarmstufe")
                if rule.stage_id in (baseline.id, secure.id):
                    raise ValueError(
                        "Deaktiviert und Sicher ergeben sich automatisch ohne Sensorregel"
                    )
                if rule.room_ids is not None and set(rule.room_ids) - self.rooms.keys():
                    raise ValueError("Regel verweist auf einen unbekannten Raum")
                if any(room not in self.rooms for path in rule.paths for room in path):
                    raise ValueError("Regel verweist auf einen unbekannten Bestätigungsweg")
                if rule.confirmation_target is not None and any(
                    c.event not in ("active", "override") for c in rule.conditions
                ):
                    raise ValueError(
                        "Störungen und Prellen dürfen keinen Bestätigungsspeicher füllen"
                    )
                if rule.prerequisite_rule_id:
                    if len(rule.conditions) > 3:
                        raise ValueError(
                            "Mit gespeicherter Bestätigung sind höchstens 3 neue Bedingungen erlaubt"
                        )
                    parent = self.rules.get(rule.prerequisite_rule_id)
                    if (
                        parent is None
                        or parent.confirmation_target is None
                        or parent.prerequisite_rule_id is not None
                        or self.stage_rank(parent.stage_id) >= self.stage_rank(rule.stage_id)
                    ):
                        raise ValueError(
                            "Voraussetzung benötigt eine niedrigere Regel mit Bestätigungsziel"
                        )
                    if parent.confirmation_sources + sum(c.count for c in rule.conditions) > 8:
                        raise ValueError(
                            "Bestätigung und neue Meldungen dürfen zusammen höchstens 8 Quellen benötigen"
                        )
                    for profile in self.profiles.values():
                        if (
                            rule.enabled
                            and profile.rule_ids is not None
                            and rule.id in profile.rule_ids
                            and parent.id not in profile.rule_ids
                        ):
                            raise ValueError(
                                f"Profil {profile.name}: auch die Bestätigungsregel {parent.name} auswählen"
                            )
                for condition in rule.conditions:
                    if set(condition.sensor_ids) - sensors.keys():
                        raise ValueError("Regel verweist auf einen unbekannten Sensor")
                    if rule.enabled and not (condition.sensor_ids or condition.roles):
                        raise ValueError("Aktive Regel benötigt Sensoren oder Sensorgruppen")
                    if (
                        rule.enabled
                        and not condition.roles
                        and len({sensors[s].source_id or s for s in condition.sensor_ids})
                        < condition.count
                    ):
                        raise ValueError("Bedingung enthält zu wenige unabhängige Sensoren")
                if self.stage(rule.stage_id).requires_confirmation:
                    if any(c.event in ("unavailable", "flapping") for c in rule.conditions):
                        raise ValueError(
                            "Störungen und Prellen dürfen keinen bestätigten Alarm erzeugen"
                        )
                    if (
                        not rule.prerequisite_rule_id
                        and sum(c.count for c in rule.conditions) < 2
                        and not (
                            len(rule.conditions) == 1 and rule.conditions[0].event == "override"
                        )
                    ):
                        raise ValueError(
                            "Bestätigte Alarmstufe benötigt unabhängige Quellen oder einen freigegebenen Gefahrensensor"
                        )
            self.settings.simulation_enabled = any(
                p.simulation_enabled for p in self.profiles.values()
            )
        names = [profile.name.strip().casefold() for profile in self.profiles.values()]
        if len(set(names)) != len(names):
            raise ValueError("Profilnamen müssen eindeutig sein")
        if any(key != action.id for key, action in self.actions.items()):
            raise ValueError("Aktions-ID stimmt nicht überein")
        for action in self.actions.values():
            if self.rules is not None and action.profile_ids is None:
                raise ValueError("Aktion benötigt eine ausdrückliche Alarmmodus-Zuordnung")
            if action.profile_ids is not None and set(action.profile_ids) - self.profiles.keys():
                raise ValueError("Aktion verweist auf einen unbekannten Alarmmodus")
            if action.level != "diagnostic" and action.level not in stage_ids:
                raise ValueError("Aktion verweist auf eine unbekannte Alarmstufe")
            loud = action.kind in {"siren", "switch", "script", "tts"} or action.critical
            if loud and (action.level == "diagnostic" or not self.stage(action.level).allow_loud):
                raise ValueError(
                    "Akustische/freie Aktionen und kritische Pushs benötigen eine freigegebene bestätigte Alarmstufe"
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
        if self.policy_version != 2:
            raise ValueError("Nicht unterstützte Korrelationsversion")
        if self.settings.room_order:
            self.settings.room_order = [r for r in self.settings.room_order if r in self.rooms]
        sensors = self.all_sensors()
        self.settings.sensor_order = {
            room_id: list(
                dict.fromkeys(
                    sensor_id
                    for sensor_id in order
                    if sensor_id in sensors
                    and (
                        sensors[sensor_id].room_id == room_id
                        or room_id in sensors[sensor_id].front_of
                        if room_id
                        else not sensors[sensor_id].room_id and not sensors[sensor_id].front_of
                    )
                )
            )
            for room_id, order in self.settings.sensor_order.items()
            if not room_id or room_id in self.rooms
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Configuration":
        data = migrate_configuration(data)
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError("Ungültige Konfiguration")
        if data.get("rules") is not None and not isinstance(data["rules"], dict):
            raise ValueError("Levelregeln müssen ein Objekt sein")
        for key in (
            "rooms",
            "sensors",
            "profiles",
            "actions",
            "settings",
            "floorplans",
            "windows",
            "robots",
        ):
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
            windows={
                key: construct(WindowConfig, value)
                for key, value in data.get("windows", {}).items()
            },
            policy_version=data.get("policy_version", 2),
            secure_stage_id=data.get("secure_stage_id", "1"),
            room_connections=data.get("room_connections", []),
            robots={
                key: construct(RobotConfig, value) for key, value in data.get("robots", {}).items()
            },
            automatic_detection=construct(AutomaticDetection, data["automatic_detection"])
            if data.get("automatic_detection") is not None
            else None,
            rules={key: construct(LevelRule, value) for key, value in data["rules"].items()}
            if data.get("rules") is not None
            else None,
        )
        result.validate()
        return result


def migrate_configuration(data: dict) -> dict:
    """Translate legacy HA-derived behavior once, keeping user rules and IDs."""
    if not isinstance(data, dict):
        raise ValueError("Ungültige Konfiguration")
    result = deepcopy(data)
    # Existing installations keep their stage identities, actions and baseline.
    # Six-stage defaults apply to new configurations; the active baseline is explicit.
    if "secure_stage_id" not in result and result.get("stages"):
        result["secure_stage_id"] = result["stages"][0]["id"]
        for profile in result.get("profiles", {}).values():
            targets = profile.get("stage_targets", {})
            if "single" in targets:
                targets.setdefault("motion", targets["single"])
            targets.setdefault("fault", result["stages"][0]["id"])
    if type(result.get("policy_version", 1)) is not int or result.get("policy_version", 1) not in (
        1,
        2,
    ):
        raise ValueError("Nicht unterstützte Korrelationsversion")
    legacy_policy = result.get("policy_version", 1) < 2
    if legacy_policy:
        for sensor in result.get("sensors", {}).values():
            if (
                sensor.get("entity_id", "").startswith("binary_sensor.")
                and sensor.get("role") == "lock_contact"
                and not sensor.get("attribute")
                and sensor.get("active_states") == ["unlocked", "open"]
            ):
                sensor["active_states"] = ["on"]
            if (
                sensor.get("entity_id", "").startswith(("camera.", "image_processing."))
                and sensor.get("attribute") == "person_detected"
                and sensor.get("active_states") == ["on"]
            ):
                sensor["active_states"] = ["true", "on", "1"]
    for window in result.get("windows", {}).values():
        contact = result.get("sensors", {}).get(window.get("contact_entity_id"), {})
        for name in (
            "entry_delay",
            "immediate",
            "debounce_ms",
            "flap_enabled",
            "flap_window",
            "flap_threshold",
        ):
            if name in contact and name not in window:
                window[name] = contact[name]
        window.setdefault(
            "contact_closed_states",
            ["on"] if window.get("contact_open_states") == ["off"] else ["off"],
        )
    result["policy_version"] = 2
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
    settings.setdefault("quiet_disarmed_floorplan", True)
    settings.setdefault("quiet_disarmed_locks", True)
    settings.setdefault("recent_seconds", 30)
    settings.setdefault("floorplan_disarmed_motion", True)
    settings.setdefault("floorplan_disarmed_contacts", True)
    settings.setdefault("floorplan_disarmed_locks", False)
    settings.setdefault("floorplan_disarmed_cameras", True)
    settings.setdefault("floorplan_disarmed_animation", False)
    settings.setdefault("floorplan_armed_animation", True)
    if "rules" not in result:
        upgrade_level_rules(result, [asdict(stage) for stage in default_stages()])
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
    category: str | None = None

    def __post_init__(self):
        if self.category is None:
            self.category = (
                "fault"
                if self.kind
                in {
                    "quarantined_flapping",
                    "sensor_unavailable",
                    "runtime_error",
                    "action_failed",
                    "window_position_ambiguous",
                }
                else "alarm"
                if self.confirmed and self.reactions_enabled and self.level > 0
                else "warning"
                if self.level > 0
                and self.kind in {"level_changed", "confirmation_changed", "signal"}
                else "information"
            )

    def to_dict(self) -> dict:
        return asdict(self)
