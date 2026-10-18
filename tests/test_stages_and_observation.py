"""Free profile semantics, dynamic stages and continuous silent observation."""

from copy import deepcopy

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Action, AlarmStage, Configuration, FloorPlan, Profile


def test_observer_correlates_and_expires_without_reaction_permission(engine):
    engine.feed("binary_sensor.window", True, 100)
    assert engine.level == 2
    engine.feed("binary_sensor.motion", True, 112)
    assert engine.confirmed and engine.level == 3
    assert not engine.reactions_enabled and not engine.latched
    assert not any(event.reactions_enabled for event in engine.drain())
    engine.tick(160)
    assert not engine.confirmed
    engine.tick(172)
    assert engine.level == 0


def test_motion_ignored_for_evaluation_is_still_visible_on_floorplan(engine):
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.motion", True, 101)
    assert engine.level == 0
    assert engine.room_status("living", 101)["motion"] == ["binary_sensor.motion"]
    assert not engine.evidence


def test_profile_name_and_id_never_select_motion_or_contact_policy(engine):
    engine.config.profiles["armed_night"].motion_mode = "always"
    engine.config.profiles["armed_night"].multi_motion = True
    engine.config.profiles["armed_night"].confirmation_paths = [["living", "hall"]]
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.motion", True, 101)
    assert engine.level == 2
    engine.feed("binary_sensor.hall_motion", True, 102)
    assert engine.confirmed


def test_contact_policy_can_be_disabled_independently(engine):
    engine.config.profiles["visitors"] = Profile(
        name="Besuch", contacts_enabled=False, motion_mode="ignore"
    )
    engine.config.validate()
    engine.set_profile("visitors", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.level == 0
    assert engine.room_status("living", 101)["open"] == ["binary_sensor.window"]


def six_stages(config):
    config.stages.extend(
        [
            AlarmStage("verified", "Einbruch bestätigt", "#ff6600", True, True, True),
            AlarmStage("emergency", "Gefahr", "#ff0000", True, True, True),
        ]
    )
    for profile in config.profiles.values():
        profile.stage_targets["contact_motion"] = "verified"
        profile.stage_targets["immediate"] = "emergency"
    config.actions["siren"] = Action("siren", "verified", "siren", "siren.test")
    config.validate()


def test_six_real_stages_bind_rules_and_actions_by_stable_id(engine):
    six_stages(engine.config)
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 113)
    assert engine.stage_id == "verified" and engine.level == 4
    assert engine.events[0].confirmed
    assert engine.events[0].stage_name == "Einbruch bestätigt"
    restored = CorrelationEngine(Configuration.from_dict(engine.config.to_dict()))
    restored.restore(engine.persistent_state(), 114)
    assert restored.level == 4 and restored.latched
    restored.config.stages[4].name = "Mein Alarm"
    assert restored.config.actions["siren"].level == restored.stage_id


def test_override_can_target_a_separate_fifth_stage(engine):
    six_stages(engine.config)
    engine.config.sensors["binary_sensor.window"].immediate = True
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.stage_id == "emergency" and engine.level == 5


@pytest.mark.parametrize("count", [1, 2, 3, 6, 12, 32])
def test_stage_count_is_not_fixed(config, count):
    config.stages = [AlarmStage(f"step{i}", f"Eigene Stufe {i}", "#123456") for i in range(count)]
    for profile in config.profiles.values():
        profile.stage_targets.clear()
    config.validate()
    assert len(Configuration.from_dict(config.to_dict()).stages) == count


@pytest.mark.parametrize("rule", ["perimeter", "single", "flapping"])
def test_unconfirmed_rules_cannot_target_loud_stages(config, rule):
    config.profiles["armed_night"].stage_targets[rule] = "3"
    with pytest.raises(ValueError, match="Unbestätigte"):
        config.validate()


def test_delete_stage_requires_remapping_rules_and_actions(config):
    config.stages.pop()
    with pytest.raises(ValueError, match="unbekannte Alarmstufe"):
        config.validate()


def test_existing_v11_profile_is_migrated_once(config):
    data = config.to_dict()
    data["profiles"]["guests"] = {
        "name": "Besuch",
        "base_mode": "armed_night",
        "night_motion_requires_contact": True,
        "night_motion_scope": "house",
        "correlation_seconds": 37,
    }
    data["settings"].pop("observation_profile_id")
    migrated = Configuration.from_dict(data)
    assert migrated.profiles["guests"].motion_mode == "after_contact"
    assert migrated.profiles["guests"].motion_scope == "house"
    assert migrated.profiles["guests"].correlation_seconds == 37
    migrated.profiles["guests"].motion_mode = "ignore"
    assert Configuration.from_dict(migrated.to_dict()).profiles["guests"].motion_mode == "ignore"
    assert "base_mode" not in migrated.to_dict()["profiles"]["guests"]


def test_observer_selection_cannot_enable_outputs(config):
    config.settings.observation_profile_id = "armed_night"
    with pytest.raises(ValueError, match="Beobachtungsprofil"):
        config.validate()


def test_no_background_profile_still_exposes_raw_states(engine):
    engine.config.settings.observation_profile_id = None
    engine.feed("binary_sensor.window", True, 100)
    engine.feed("binary_sensor.motion", True, 101)
    assert engine.level == 0 and not engine.reactions_enabled
    assert engine.room_status("living", 101)["open"]


def test_observe_profile_is_removed_and_live_status_is_not_a_profile(config):
    assert "observe" not in config.profiles
    data = config.to_dict()
    data["profiles"]["observe"] = {
        "name": "Live-Beobachtung",
        "reactions_enabled": False,
        "action_ids": [],
    }
    data["settings"]["observation_profile_id"] = "observe"
    migrated = Configuration.from_dict(data)
    assert "observe" not in migrated.profiles
    assert migrated.settings.observation_profile_id == "live"
    engine = CorrelationEngine(migrated)
    assert engine.snapshot(100)["profile_name"] is None
    assert engine.snapshot(100)["profile_id"] is None


def test_floorplan_roundtrip_and_normalized_coordinates(config):
    config.floorplans["eg"] = FloorPlan(
        "eg",
        "Erdgeschoss",
        zones={"living": [[0, 0], [1, 0], [1, 1], [0, 1]]},
        labels={"living": [0.35, 0.42]},
    )
    config.validate()
    clone = Configuration.from_dict(deepcopy(config.to_dict()))
    assert clone.floorplans["eg"].zones == config.floorplans["eg"].zones
    assert clone.floorplans["eg"].labels == config.floorplans["eg"].labels
    clone.floorplans["eg"].zones["living"][0][0] = 0.2
    assert config.floorplans["eg"].zones["living"][0][0] == 0


@pytest.mark.parametrize(
    "points",
    [
        [],
        [[0, 0], [1, 1]],
        [[0, 0], [0.5, 0.5], [1, 1]],
        [[0, 0], [2, 0], [0, 1]],
        [[0, 0], [1, 0], [0, float("nan")]],
    ],
)
def test_invalid_floorplan_geometry_rejected(points):
    with pytest.raises(ValueError):
        FloorPlan("eg", "EG", zones={"living": points})


@pytest.mark.parametrize("image", ["../secrets.yaml", "/config/secrets.yaml", "image.svg", "x.png"])
def test_floorplan_filename_cannot_escape_private_storage(image):
    with pytest.raises(ValueError):
        FloorPlan("eg", "EG", image=image, width=100, height=100)
