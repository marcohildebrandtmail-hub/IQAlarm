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
