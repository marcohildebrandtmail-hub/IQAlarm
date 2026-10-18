"""Configuration security boundaries are validated in the backend."""

import math

import pytest
from iqalarm_core.models import (
    Action,
    Configuration,
    Profile,
    Room,
    SensorConfig,
    Settings,
    construct,
)


@pytest.mark.parametrize(
    "kind,target",
    [
        ("siren", "siren.house"),
        ("switch", "switch.siren"),
        ("script", "script.alarm"),
        ("tts", "tts.voice"),
    ],
)
@pytest.mark.parametrize("level", ["1", "2", "diagnostic"])
def test_loud_actions_cannot_bypass_silent_stages(kind, target, level):
    with pytest.raises(ValueError):
        config = Configuration(
            actions={
                "a": Action(
                    "a",
                    level,
                    kind,
                    target,
                    media_player="media_player.speaker" if kind == "tts" else None,
                )
            }
        )
        config.validate()


def test_critical_notification_cannot_bypass_silent_stage():
    with pytest.raises(ValueError):
        Configuration(
            actions={"a": Action("a", "2", "notify", "notify.phone", critical=True)}
        ).validate()


@pytest.mark.parametrize("value", [math.nan, math.inf, -1, 3601, True, "60"])
def test_timer_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        Profile(correlation_seconds=value)


def test_full_configuration_roundtrip(config):
    config.actions["push"] = Action("push", "2", "notify", "notify.phone")
    assert Configuration.from_dict(config.to_dict()).to_dict() == config.to_dict()


def test_unknown_fields_not_silently_ignored():
    with pytest.raises(ValueError):
        construct(Profile, {"correlation_second": 60})


def test_room_sensor_requires_known_room(config):
    data = config.to_dict()
    data["sensors"]["binary_sensor.window"]["room_id"] = "missing"
    with pytest.raises(ValueError):
        Configuration.from_dict(data)


def test_camera_requires_explicit_detection_attribute():
    with pytest.raises(ValueError, match="Erkennungsattribut"):
        SensorConfig("camera.front", "perimeter_camera")
    sensor = SensorConfig(
        "camera.front", "perimeter_camera", attribute="person_detected", active_states=["true"]
    )
    assert sensor.attribute == "person_detected"


@pytest.mark.parametrize("state", ["unknown", "unavailable"])
def test_unavailable_can_never_be_active(state):
    with pytest.raises(ValueError):
        SensorConfig("binary_sensor.front", "perimeter_sensor", active_states=[state])


def test_multistate_entities_allowed_and_validated():
    sensor = SensorConfig(
        "input_select.garagentor_zustand",
        "entry_contact",
        room_id="garage",
        active_states=["wird Geöffnet", "Geöffnet", "Lüften", "in Bewegung"],
    )
    assert sensor.entity_id == "input_select.garagentor_zustand"
    assert sensor.role == "entry_contact"
    assert "Geöffnet" in sensor.active_states

    cover_sensor = SensorConfig(
        "cover.garagentor",
        "entry_contact",
        room_id="garage",
        active_states=["open", "opening"],
    )
    assert cover_sensor.entity_id == "cover.garagentor"


def test_action_domain_not_arbitrary_service():
    with pytest.raises(ValueError):
        Action("a", "3", "script", "homeassistant.restart")


def test_room_cannot_reference_itself():
    with pytest.raises(ValueError):
        Room("a", "A", adjacent=["a"])


def test_settings_reject_invalid_simulation():
    with pytest.raises(ValueError):
        Settings(simulation_lights=["switch.siren"])


def test_numeric_sensor_settings_require_integer():
    with pytest.raises(ValueError):
        SensorConfig("binary_sensor.window", "entry_contact", "living", flap_threshold=3.5)


def test_settings_quiet_disarmed_defaults_and_validation():
    s = Settings()
    assert s.quiet_disarmed_floorplan is True
    assert s.quiet_disarmed_locks is True
    assert s.recent_seconds == 30
    assert s.floorplan_disarmed_motion is True
    assert s.floorplan_disarmed_contacts is True
    assert s.floorplan_disarmed_locks is False
    assert s.floorplan_disarmed_cameras is True
    assert s.floorplan_disarmed_animation is False
    assert s.floorplan_armed_animation is True
    with pytest.raises(ValueError):
        Settings(quiet_disarmed_floorplan="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(quiet_disarmed_locks="no")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(floorplan_disarmed_motion="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(floorplan_disarmed_locks="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(floorplan_armed_animation="invalid")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        Settings(recent_seconds=3)
    with pytest.raises(ValueError):
        Settings(recent_seconds=400)
    with pytest.raises(ValueError):
        Settings(recent_seconds=30.5)  # type: ignore[arg-type]


def test_settings_room_order_validation():
    s = Settings()
    assert s.room_order == []
    s2 = Settings(room_order=["living", "kitchen"])
    assert s2.room_order == ["living", "kitchen"]
    with pytest.raises(ValueError, match="Liste"):
        Settings(room_order="living")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Raum-IDs"):
        Settings(room_order=[123])  # type: ignore[list-item]
    with pytest.raises(ValueError, match="Maximal 250"):
        Settings(room_order=[f"room_{i}" for i in range(251)])


def test_configuration_validates_and_prunes_room_order(config):
    config.settings.room_order = ["bed", "missing_room", "living"]
    config.validate()
    assert config.settings.room_order == ["bed", "living"]


def test_sensor_order_roundtrip_deduplicates_and_prunes_removed_or_moved_sensors(config):
    config.settings.sensor_order = {
        "living": [
            "binary_sensor.motion",
            "binary_sensor.window",
            "binary_sensor.motion",
            "binary_sensor.removed",
        ],
        "bed": ["binary_sensor.bed_motion"],
        "removed_room": ["binary_sensor.window"],
    }
    saved = Configuration.from_dict(config.to_dict())
    assert saved.settings.sensor_order == {
        "living": ["binary_sensor.motion", "binary_sensor.window"],
        "bed": ["binary_sensor.bed_motion"],
    }
    saved.sensors["binary_sensor.motion"].room_id = "bed"
    saved.validate()
    assert saved.settings.sensor_order["living"] == ["binary_sensor.window"]
    assert saved.settings.sensor_order["bed"] == ["binary_sensor.bed_motion"]


@pytest.mark.parametrize(
    "order", [[], {"living": "binary_sensor.window"}, {"living": [1]}, {"living": ["../secret"]}]
)
def test_invalid_sensor_order_is_rejected(order):
    with pytest.raises(ValueError):
        Settings(sensor_order=order)
