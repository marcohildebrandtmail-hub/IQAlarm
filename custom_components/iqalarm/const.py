"""Shared identifiers and states; deliberately independent of Home Assistant."""

from enum import IntEnum, StrEnum

DOMAIN = "iqalarm"
NAME = "IQAlarm"
VERSION = "2.13.3"
STORAGE_VERSION = 1
EVENT_TYPE = "iqalarm_event"
SIGNAL_UPDATE = "iqalarm_update"
PLATFORMS = ("alarm_control_panel", "sensor", "binary_sensor", "switch")
MAX_EVENTS = 500
CHANGE_ACTIVITY_SECONDS = 15
RULE_NAMES = {
    "perimeter": "Vorfeld erkannt",
    "single": "Unbestätigtes Einzelereignis",
    "motion": "Unbestätigte Innenbewegung",
    "fault": "Sensor nicht verfügbar",
    "flapping": "Sensor-Prellen",
    "perimeter_contact": "Vorfeld + Öffnung",
    "contact_motion": "Öffnung + Bewegung",
    "multi_contact": "Zwei Öffnungssensoren",
    "multi_motion": "Zwei Innenraumsensoren",
    "immediate": "Freigegebene Einzelauslösung / Gefahr",
}
UNCONFIRMED_RULES = frozenset(("perimeter", "single", "motion", "fault", "flapping"))


class RunState(StrEnum):
    INACTIVE = "inactive"
    ACTIVE = "active"


class Mode(StrEnum):
    DISARMED = "disarmed"
    HOME = "armed_home"
    NIGHT = "armed_night"
    AWAY = "armed_away"
    VACATION = "armed_vacation"


class Role(StrEnum):
    PERIMETER_CAMERA = "perimeter_camera"
    PERIMETER_SENSOR = "perimeter_sensor"
    ENTRY = "entry_contact"
    LOCK = "lock_contact"
    GLASS = "vibration_glass"
    MOTION = "interior_motion"
    MMWAVE = "interior_mmwave"
    PANIC = "panic"
    SMOKE = "smoke"


class Level(IntEnum):
    SECURE = 0
    PERIMETER = 1
    SUSPICION = 2
    BREACH = 3


LEVEL_STATES = {
    0: "level_0_secure",
    1: "level_1_perimeter",
    2: "level_2_suspicion",
    3: "level_3_confirmed_breach",
}
CONTACT_ROLES = frozenset((Role.ENTRY, Role.LOCK, Role.GLASS))
INTERIOR_ROLES = frozenset((Role.MOTION, Role.MMWAVE))
PERIMETER_ROLES = frozenset((Role.PERIMETER_CAMERA, Role.PERIMETER_SENSOR))
ARMED_MODES = tuple(m for m in Mode if m != Mode.DISARMED)
MODE_NAMES = {
    Mode.HOME: "Zuhause",
    Mode.NIGHT: "Nacht",
    Mode.AWAY: "Abwesend",
    Mode.VACATION: "Urlaub",
}
ALLOWED_SENSOR_DOMAINS = frozenset(
    (
        "binary_sensor",
        "lock",
        "camera",
        "image_processing",
        "sensor",
        "input_boolean",
        "input_select",
        "select",
        "cover",
    )
)
