"""Custom profiles must preserve native HA semantics and isolate their inputs."""

from copy import deepcopy

import pytest
from iqalarm_core.const import Level, Mode
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, Profile, SensorConfig


def add_profile(config, **changes):
    values = {"name": "Nacht mit Gästen", "base_mode": "armed_night", **changes}
    config.profiles["guests"] = Profile(**values)
    config.validate()
    return config.profiles["guests"]


def test_custom_profile_keeps_its_identity_with_native_night_state(engine):
    add_profile(engine.config)
    engine.set_profile("guests", 100)
    snapshot = engine.snapshot(100)
    assert snapshot["mode"] == "armed_night"
    assert snapshot["profile_id"] == "guests"
    assert snapshot["profile_name"] == "Nacht mit Gästen"
    assert engine.events[0].profile_name == "Nacht mit Gästen"
    engine.feed("binary_sensor.motion", True, 101)
    assert engine.level == Level.SECURE
    engine.feed("binary_sensor.window", True, 102)
    engine.feed("binary_sensor.motion", False, 110)
    engine.feed("binary_sensor.motion", True, 114)
    assert engine.level == Level.BREACH
    assert all(event.profile_id == "guests" for event in engine.events)


def test_same_ha_mode_does_not_allow_profile_switch_while_armed(engine):
    add_profile(engine.config)
    engine.set_profile("guests", 100)
    engine.set_profile("guests", 101)
    with pytest.raises(ValueError, match="entschärfen"):
        engine.set_mode("armed_night", 102)
    assert engine.profile_id == "guests"
    engine.set_mode("disarmed", 103)
    engine.set_mode("armed_night", 104)
    assert engine.profile_id == "armed_night"


def test_excluded_room_cannot_block_or_confirm_alarm(engine):
    add_profile(engine.config, room_ids=["living"])
    engine.seed("binary_sensor.lock", True)
    engine.seed("binary_sensor.bed_motion", None)
    engine.set_profile("guests", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 102)
    assert engine.level == Level.SUSPICION
    assert "binary_sensor.hall_motion" not in engine.snapshot(102)["monitored_sensors"]
    engine.feed("binary_sensor.motion", True, 103)
    assert engine.level == Level.BREACH


def test_contact_in_selected_room_still_blocks_arming(engine):
    add_profile(engine.config, room_ids=["living"])
    engine.seed("binary_sensor.window", True)
    with pytest.raises(ValueError, match="offen"):
        engine.set_profile("guests", 100)
    assert engine.mode == Mode.DISARMED and engine.profile_id is None


def test_scoped_home_profile_monitors_explicit_selection(engine):
    add_profile(engine.config, base_mode="armed_home", room_ids=["living"])
    assert not engine.config.rooms["living"].home_enabled
    engine.set_profile("guests", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.level == Level.BREACH


def test_sensor_and_room_selection_intersect(engine):
    add_profile(engine.config, room_ids=["living"], sensor_ids=["binary_sensor.window"])
    engine.set_profile("guests", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    engine.feed("binary_sensor.window", True, 102)
    engine.feed("binary_sensor.motion", True, 103)
    assert engine.level == Level.SUSPICION
    assert engine.snapshot(103)["monitored_sensors"] == ["binary_sensor.window"]


@pytest.mark.parametrize("selection", [{"room_ids": []}, {"sensor_ids": []}])
def test_empty_explicit_scope_never_expands_to_all_sensors(engine, selection):
    add_profile(engine.config, **selection)
    with pytest.raises(ValueError, match="keine aktivierten Sensoren"):
        engine.set_profile("guests", 100)
    assert engine.mode == Mode.DISARMED


def test_scoped_global_perimeter_and_spatial_perimeter(engine):
    config = engine.config
    config.sensors["binary_sensor.global_person"] = SensorConfig(
        "binary_sensor.global_person", "perimeter_sensor"
    )
    engine.seed("binary_sensor.global_person", False)
    add_profile(config, room_ids=["hall"])
    engine.set_profile("guests", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    assert engine.level == Level.SECURE
    engine.feed("binary_sensor.global_person", True, 102)
    assert engine.level == Level.PERIMETER
    engine.feed("binary_sensor.lock", True, 103)
    assert engine.level == Level.BREACH


def test_custom_timers_are_used_without_changing_standard_profile(engine):
    add_profile(engine.config, correlation_seconds=5, exit_seconds=3)
    engine.set_profile("guests", 100)
    assert engine.arming_until == 103
    engine.tick(103)
    engine.feed("binary_sensor.window", True, 104)
    assert engine.level == Level.SUSPICION
    engine.tick(109)
    assert engine.level == Level.SECURE
    assert engine.config.profiles["armed_night"].correlation_seconds == 60


def test_custom_profile_survives_restart_with_confirmation_chain(engine):
    add_profile(engine.config)
    engine.set_profile("guests", 100)
    engine.feed("binary_sensor.window", True, 101)
    restored = CorrelationEngine(engine.config)
    restored.seed("binary_sensor.motion", False)
    restored.restore(engine.persistent_state(), 105)
    assert restored.profile_id == "guests" and restored.mode == Mode.NIGHT
    restored.feed("binary_sensor.motion", True, 113)
    assert restored.level == Level.BREACH
    assert restored.events[0].profile_name == "Nacht mit Gästen"


def test_version_one_configuration_and_armed_state_migrate_without_losing_rules(engine):
    old = engine.config.to_dict()
    for profile in old["profiles"].values():
        for key in ("name", "base_mode", "room_ids", "sensor_ids", "action_ids"):
            del profile[key]
    old["profiles"]["armed_night"]["correlation_seconds"] = 47
    migrated = Configuration.from_dict(old)
    assert migrated.profiles["armed_night"].name == "Nacht"
    assert migrated.profiles["armed_night"].correlation_seconds == 47
    restored = CorrelationEngine(migrated)
    restored.restore({"mode": "armed_night"}, 100)
    assert restored.profile_id == "armed_night"


def test_missing_or_mismatched_profile_does_not_silently_restore_default(engine):
    with pytest.raises(ValueError, match="fehlt"):
        engine.restore({"mode": "armed_night", "profile_id": "deleted"}, 100)
    add_profile(engine.config, base_mode="armed_away")
    with pytest.raises(ValueError, match="passt nicht"):
        engine.restore({"mode": "armed_night", "profile_id": "guests"}, 101)


@pytest.mark.parametrize(
    "values",
    [
        {"name": ""},
        {"name": " nacht "},
        {"base_mode": "disarmed"},
        {"room_ids": ["unknown"]},
        {"room_ids": ["living", "living"]},
        {"sensor_ids": "binary_sensor.window"},
        {"sensor_ids": ["binary_sensor.unknown"]},
        {"action_ids": ["unknown"]},
    ],
)
def test_invalid_custom_profile_is_rejected(config, values):
    with pytest.raises(ValueError):
        add_profile(config, **values)


def test_standard_profile_mapping_cannot_be_reassigned(config):
    config.profiles["armed_night"].base_mode = "armed_away"
    with pytest.raises(ValueError, match="Basismodus behalten"):
        config.validate()


def test_profile_limit_is_enforced(config):
    for i in range(47):
        config.profiles[f"profile_{i}"] = Profile(name=f"Profil {i}", base_mode="armed_night")
    with pytest.raises(ValueError, match="50 Profile"):
        config.validate()


def test_saved_profile_selections_are_independent_copies(config):
    add_profile(config, room_ids=["living"], sensor_ids=["binary_sensor.window"])
    clone = Configuration.from_dict(deepcopy(config.to_dict()))
    clone.profiles["guests"].room_ids.append("hall")
    assert config.profiles["guests"].room_ids == ["living"]


def test_unknown_profile_does_not_change_armed_state(engine):
    engine.set_mode("armed_night", 100)
    with pytest.raises(ValueError, match="Unbekanntes"):
        engine.set_profile("unknown", 101)
    assert engine.profile_id == "armed_night" and engine.mode == Mode.NIGHT
