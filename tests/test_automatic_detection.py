"""Automatic three-step detection and its bounded transition into the next level."""

from copy import deepcopy

import pytest
from iqalarm_core.automatic_detection import AutomaticDetection
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.level_rules import LevelRule, RuleCondition
from iqalarm_core.models import Configuration, Room, SensorConfig


@pytest.fixture
def automatic():
    config = Configuration(
        rooms={key: Room(key, key) for key in ("kitchen", "living", "hall", "bed")},
        automatic_detection=AutomaticDetection(test_mode=False),
    )
    # Keep this suite about LVL 3; no separately configured full-alarm rule.
    for profile in config.profiles.values():
        profile.rule_ids = ["single", "motion", "fault", "flapping"]
    for room in config.rooms:
        for index in range(1, 7):
            key = f"binary_sensor.{room}_{index}"
            config.sensors[key] = SensorConfig(key, "interior_motion", room, name=key)
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_away", 100)
    return engine


def fire(engine, room, number, at):
    key = f"binary_sensor.{room}_{number}"
    engine.feed(key, True, at)
    engine.feed(key, False, at + 0.01)


def grade(engine, room="kitchen"):
    return engine.room_status(room, engine._last_time)["detection"]


def complete(engine, room="kitchen", start=101):
    for index in range(1, 4):
        fire(engine, room, index, start + index - 1)


def test_test_mode_stays_at_level_three_on_extra_triggers_and_timer(automatic):
    automatic.config.automatic_detection.test_mode = True
    complete(automatic)
    assert grade(automatic)["current"] == 3
    assert grade(automatic)["next_level_at"] is None
    fire(automatic, "kitchen", 4, 110)
    automatic.tick(163)  # The former LVL-4 deadline must not promote.
    assert automatic.level == 3 and not automatic.confirmed
    assert grade(automatic)["current"] == 3
    assert grade(automatic)["detected_at"] is None
    for at, expected in ((170, 2), (230, 1), (290, 0)):
        automatic.tick(at)
        progress = grade(automatic)
        assert (progress["current"] if progress else 0) == expected
        assert automatic.level == (3 if expected else 1)
    assert all(event.level <= 3 for event in automatic.drain())


@pytest.mark.parametrize("automatic_enabled", [False, True])
def test_test_ceiling_also_blocks_manual_full_alarm_and_danger_overrides(
    automatic, automatic_enabled
):
    automatic.config.automatic_detection.test_mode = True
    profile = automatic.config.profiles["armed_away"]
    profile.automatic_detection = automatic_enabled
    profile.rule_ids.extend(["later", "immediate"])
    automatic.config.rules["later"] = LevelRule(
        "later", "Vollalarm", "5", [RuleCondition(roles=["interior_motion"], count=2)]
    )
    key = "binary_sensor.fire"
    automatic.config.sensors[key] = SensorConfig(key, "smoke", "bed", immediate=True)
    automatic.seed(key, False)
    complete(automatic)
    automatic.feed(key, True, 110)
    automatic.tick(164)
    assert automatic.level <= 3
    assert not automatic.confirmed and not automatic.latched
    assert all(automatic.config.stage_rank(rule.stage_id) <= 3 for rule in automatic.active_rules())
    assert all(event.level <= 3 for event in automatic.drain())


def test_restart_cannot_restore_a_held_or_pending_high_stage_in_test_mode(automatic):
    automatic.config.rules["later"] = LevelRule(
        "later", "Vollalarm", "5", [RuleCondition(roles=["interior_motion"], count=2)]
    )
    automatic.config.profiles["armed_away"].rule_ids.append("later")
    complete(automatic)
    fire(automatic, "kitchen", 4, 110)
    fire(automatic, "kitchen", 5, 111)
    assert automatic.level == 5 and automatic.latched
    saved = deepcopy(automatic.persistent_state())
    saved["rule_pending"] = {"later": {"until": 130, "chain": saved["breach_chain"]}}
    config = automatic.config.to_dict()
    config["automatic_detection"].pop("test_mode")  # New test operation is the default.
    restored = CorrelationEngine(Configuration.from_dict(config))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(saved, 120)
    restored.tick(180)
    assert restored.level <= 3
    assert not restored.confirmed and not restored.latched and restored.held_alarm is None
    assert "later" not in restored.rule_pending
    assert all(event.level <= 3 for event in restored.drain())
    assert restored.config.to_dict()["automatic_detection"]["test_mode"] is True


def test_independent_sources_reach_three_steps_without_skipping_to_level_four(automatic):
    for index in range(1, 4):
        fire(automatic, "kitchen", index, 100 + index)
        assert automatic.level == 3
        assert grade(automatic)["current"] == index
        assert not automatic.confirmed and not automatic.latched
    assert grade(automatic)["next_level_at"] == 163
    automatic.tick(162.999)
    assert automatic.level == 3
    automatic.tick(163)
    assert automatic.level == 4
    assert not automatic.confirmed and not automatic.latched
    assert grade(automatic)["stage_id"] == "3"  # No invented LVL-4 confirmation grade.


@pytest.mark.parametrize("extra", [1, 4])
def test_a_genuine_new_edge_after_three_of_three_reaches_level_four(automatic, extra):
    complete(automatic)
    fire(automatic, "kitchen", extra, 110)
    assert automatic.level == 4
    assert grade(automatic)["current"] == 3


def test_held_active_values_and_ticks_do_not_count_as_additional_triggers(automatic):
    for index in range(1, 4):
        automatic.feed(f"binary_sensor.kitchen_{index}", True, 100 + index)
    for moment in (104, 110, 120):
        automatic.feed("binary_sensor.kitchen_1", True, moment)
        automatic.tick(moment)
        assert automatic.level == 3
    assert grade(automatic)["next_level_at"] == 163


def test_old_events_cannot_replay_after_stepwise_inactivity_decay(automatic):
    automatic.config.automatic_detection.promote_seconds = 300
    complete(automatic)
    for at, expected in ((163, 2), (223, 1), (283, 0), (284, 0), (300, 0)):
        automatic.tick(at)
        current = grade(automatic)
        assert (current["current"] if current else 0) == expected
        assert automatic.level == (3 if expected else 1)


def test_sensitivity_requires_the_displayed_number_of_independent_devices(automatic):
    automatic.config.automatic_detection.threshold = 2
    fire(automatic, "kitchen", 1, 101)
    assert grade(automatic) is None and automatic.level == 1
    for index in range(2, 5):
        fire(automatic, "kitchen", index, 100 + index)
        assert grade(automatic)["current"] == index - 1
        assert automatic.level == 3


def test_multiple_entities_of_one_device_cannot_raise_the_grade(automatic):
    for index in (1, 2, 3):
        automatic.sensors[f"binary_sensor.kitchen_{index}"].source_id = "device:one"
        fire(automatic, "kitchen", index, 100 + index)
    assert grade(automatic)["current"] == 1
    assert automatic.level == 3


def test_unrelated_rooms_have_independent_simultaneous_grades(automatic):
    fire(automatic, "kitchen", 1, 101)
    fire(automatic, "living", 1, 102)
    fire(automatic, "living", 2, 103)
    assert grade(automatic, "kitchen")["current"] == 1
    assert grade(automatic, "living")["current"] == 2
    assert grade(automatic, "bed") is None
    complete(automatic, "kitchen", 110)
    fire(automatic, "bed", 1, 115)
    assert automatic.room_status("kitchen", 115)["level"] == 3
    assert grade(automatic, "bed")["current"] == 1


def test_only_direct_connections_can_combine_sources(automatic):
    automatic.config.room_connections = [["kitchen", "living"], ["living", "hall"]]
    fire(automatic, "kitchen", 1, 101)
    fire(automatic, "living", 1, 102)
    fire(automatic, "hall", 1, 103)
    assert grade(automatic, "kitchen")["current"] == 2
    assert grade(automatic, "living")["current"] == 3
    assert grade(automatic, "hall")["current"] == 2
    assert automatic.room_status("kitchen", 103)["level"] == 3


@pytest.mark.parametrize("failure", ["offline", "quarantine", "robot", "ignored", "disabled"])
def test_excluded_or_failed_sources_do_not_supply_confirmation(automatic, failure):
    complete(automatic)
    key = "binary_sensor.kitchen_1"
    if failure == "offline":
        automatic.feed(key, None, 110)
    elif failure == "quarantine":
        automatic.quarantine[key] = {"since": 110, "reason": "test"}
    elif failure == "robot":
        automatic.robot_paused.add(key)
    elif failure == "ignored":
        automatic.ignored_windows[key] = {}
    else:
        automatic.sensors[key].enabled = False
    automatic.tick(163)
    assert automatic.level < 4
    assert not automatic.confirmed


def test_profile_freedom_and_night_opening_gate_are_preserved(automatic):
    automatic.set_profile(None, 109)
    automatic.set_profile("armed_night", 110)
    fire(automatic, "kitchen", 1, 111)
    assert automatic.level == 1
    contact = automatic.sensors["binary_sensor.kitchen_2"]
    contact.role = "entry_contact"
    fire(automatic, "kitchen", 2, 112)
    assert grade(automatic)["current"] == 1
    fire(automatic, "kitchen", 3, 113)
    assert grade(automatic)["current"] == 2
    automatic.set_profile(None, 120)
    assert not automatic.automatic_states
    automatic.config.profiles["armed_away"].sensor_ids = ["binary_sensor.kitchen_1"]
    automatic.set_profile("armed_away", 121)
    fire(automatic, "kitchen", 2, 122)
    assert automatic.level == 1


def test_restart_keeps_the_original_three_of_three_deadline(automatic):
    complete(automatic)
    saved = deepcopy(automatic.persistent_state())
    restored = CorrelationEngine(Configuration.from_dict(automatic.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(saved, 150)
    assert grade(restored)["current"] == 3
    assert grade(restored)["next_level_at"] == 163
    restored.tick(163)
    assert restored.level == 4 and not restored.confirmed


def test_restart_does_not_repeat_an_already_reached_level_four_event(automatic):
    complete(automatic)
    fire(automatic, "kitchen", 4, 110)
    restored = CorrelationEngine(Configuration.from_dict(automatic.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(deepcopy(automatic.persistent_state()), 120)
    assert restored.level == 4
    assert restored.drain() == []


def test_connected_rooms_share_one_confirmation_event_for_the_same_proof(automatic):
    automatic.config.room_connections = [["kitchen", "living"]]
    fire(automatic, "kitchen", 1, 101)
    fire(automatic, "kitchen", 2, 102)
    automatic.drain()
    fire(automatic, "living", 1, 103)
    assert grade(automatic, "kitchen")["current"] == 3
    assert grade(automatic, "living")["current"] == 3
    assert len([event for event in automatic.drain() if event.kind == "rule_confirmation"]) == 1


def test_profile_can_disable_automatic_levels_without_reenabling_legacy_rules(automatic):
    automatic.config.profiles["armed_away"].automatic_detection = False
    complete(automatic)
    assert automatic.level == 1
    assert not automatic.automatic_states


def test_unlocking_alone_does_not_open_the_night_motion_gate(automatic):
    automatic.set_profile(None, 109)
    automatic.set_profile("armed_night", 110)
    automatic.sensors["binary_sensor.kitchen_1"].role = "lock_contact"
    fire(automatic, "kitchen", 1, 111)
    fire(automatic, "kitchen", 2, 112)
    assert grade(automatic)["current"] == 1


def test_existing_full_alarm_rules_cannot_skip_the_new_detection_progression(automatic):
    automatic.config.rules["later"] = LevelRule(
        "later", "Bestehender Vollalarm", "5", [RuleCondition(roles=["interior_motion"], count=2)]
    )
    automatic.config.profiles["armed_away"].rule_ids.append("later")
    complete(automatic)
    assert automatic.level == 3 and not automatic.confirmed
    fire(automatic, "kitchen", 4, 110)
    assert automatic.level == 4 and not automatic.confirmed
    # Newer matches in an unrelated room cannot hide a valid admitted context.
    fire(automatic, "bed", 1, 111)
    fire(automatic, "bed", 2, 112)
    assert automatic.level == 5 and automatic.confirmed
    assert automatic.room_status("kitchen", 112)["confirmed"]
    assert not automatic.room_status("bed", 112)["confirmed"]


def test_explicit_danger_override_keeps_its_immediate_path(automatic):
    automatic.config.profiles["armed_away"].rule_ids.append("immediate")
    key = "binary_sensor.fire"
    automatic.config.sensors[key] = SensorConfig(key, "smoke", "bed", immediate=True)
    automatic.seed(key, False)
    automatic.feed(key, True, 101)
    assert automatic.level == 5 and automatic.confirmed


def test_settings_roundtrip_preserves_custom_stage_ids_and_old_configs(automatic):
    data = automatic.config.to_dict()
    for stage in data["stages"]:
        if stage["id"] == "4":
            stage["id"] = "custom_detection"
    for rule in data["rules"].values():
        if rule["stage_id"] == "4":
            rule["stage_id"] = "custom_detection"
    data["automatic_detection"]["next_stage_id"] = "custom_detection"
    for profile in data["profiles"].values():
        for key in profile["stage_targets"]:
            if profile["stage_targets"][key] == "4":
                profile["stage_targets"][key] = "custom_detection"
    assert Configuration.from_dict(data).automatic_detection.next_stage_id == "custom_detection"
    del data["automatic_detection"]
    assert Configuration.from_dict(data).automatic_detection is None


@pytest.mark.parametrize(
    "changes",
    [
        {"threshold": 0},
        {"threshold": 7},
        {"quiet_seconds": 0},
        {"promote_seconds": 601},
        {"next_stage_id": "5"},
        {"test_mode": "true"},
    ],
)
def test_invalid_automatic_settings_are_rejected(automatic, changes):
    data = automatic.config.to_dict()
    data["automatic_detection"].update(changes)
    with pytest.raises((ValueError, StopIteration)):
        Configuration.from_dict(data)


def test_disarmed_inactive_does_not_count_or_elevate_automatic_detection(automatic):
    automatic.set_profile(None, 200)
    assert not automatic.reactions_enabled
    # Trigger sensors while disarmed
    for index in range(1, 4):
        fire(automatic, "kitchen", index, 201 + index)
    snap = automatic.snapshot(210)
    assert snap["level"] == 0
    assert snap["stage_id"] == automatic.config.stages[0].id
    assert snap["stage_name"] == automatic.config.stages[0].name
    assert snap["rule_progress"] == []
    assert snap["matched_rules"] == []
    assert snap["breach_chain"] == []
    assert grade(automatic, "kitchen") is None
