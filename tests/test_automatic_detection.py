"""Automatic three-step detection and its bounded transition into the next level."""

from copy import deepcopy

import pytest
from iqalarm_core.automatic_detection import AutomaticDetection
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.level_rules import LevelRule, RuleCondition
from iqalarm_core.models import Configuration, Room, SensorConfig
from iqalarm_core.models import Settings as ScenarioSettings


@pytest.fixture
def automatic():
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms={key: Room(key, key) for key in ("kitchen", "living", "hall", "bed")},
        automatic_detection=AutomaticDetection(test_mode=False, promote_seconds=60),
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
    assert (grade(automatic) or {}).get("next_level_at") is None
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


@pytest.mark.parametrize("extra", [4])
def test_a_genuine_new_edge_after_three_of_three_reaches_level_four(automatic, extra):
    complete(automatic)
    fire(automatic, "kitchen", extra, 110)
    assert automatic.level == 4
    assert grade(automatic)["current"] == 3


def test_same_sensor_after_three_of_three_does_not_replace_a_further_independent_sensor(automatic):
    complete(automatic)
    fire(automatic, "kitchen", 1, 110)
    assert automatic.level == 3
    assert grade(automatic)["next_level_at"] == 163


@pytest.mark.parametrize("trigger", ["timer", "additional", "repeat", "remote", "same_device"])
def test_indoor_three_of_three_promotes_after_thirty_seconds_or_a_further_sensor(
    automatic, trigger
):
    settings = automatic.config.automatic_detection
    settings.test_mode = True
    settings.test_stage_id = settings.next_stage_id
    settings.promote_seconds = 30
    complete(automatic)
    assert automatic.level == 3
    assert grade(automatic)["next_level_at"] == 133
    if trigger in ("additional", "remote"):
        fire(automatic, "kitchen" if trigger == "additional" else "bed", 4, 110)
        assert automatic.level == 4
    else:
        if trigger == "repeat":
            fire(automatic, "kitchen", 1, 110)
        elif trigger == "same_device":
            automatic.sensors["binary_sensor.kitchen_4"].source_id = "binary_sensor.kitchen_1"
            fire(automatic, "kitchen", 4, 110)
        automatic.tick(132.999)
        assert automatic.level == 3
        assert grade(automatic)["next_level_at"] == 133
        automatic.tick(133)
        assert automatic.level == 4
    assert not automatic.confirmed and not automatic.latched
    assert not automatic.stage_allowed("5")


def test_old_remote_evidence_does_not_replay_as_the_fourth_sensor(automatic):
    settings = automatic.config.automatic_detection
    settings.test_stage_id = settings.next_stage_id
    settings.promote_seconds = 30
    fire(automatic, "bed", 1, 101)
    complete(automatic, start=110)
    automatic.tick(120)
    assert automatic.level == 3
    assert grade(automatic)["next_level_at"] == 142


def test_remote_entity_of_one_of_the_three_devices_is_not_a_fourth_source(automatic):
    settings = automatic.config.automatic_detection
    settings.test_stage_id = settings.next_stage_id
    settings.promote_seconds = 30
    automatic.sensors["binary_sensor.bed_1"].source_id = "binary_sensor.kitchen_1"
    complete(automatic)
    fire(automatic, "bed", 1, 110)
    assert automatic.level == 3


def test_lost_full_grade_cancels_the_pending_thirty_second_promotion(automatic):
    settings = automatic.config.automatic_detection
    settings.test_stage_id = settings.next_stage_id
    settings.promote_seconds = 30
    complete(automatic)
    automatic.feed("binary_sensor.kitchen_1", None, 120)
    assert (grade(automatic) or {}).get("next_level_at") is None
    automatic.tick(133)
    assert automatic.level < 4


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


def test_expired_neighbor_cannot_reappear_when_a_room_gets_its_first_trigger(automatic):
    automatic.config.room_connections = [["kitchen", "living"]]
    automatic.config.automatic_detection.promote_seconds = 30
    fire(automatic, "kitchen", 1, 101)
    automatic.tick(161)
    assert automatic.level == 1
    fire(automatic, "living", 1, 162)
    assert grade(automatic, "living")["current"] == 1
    fire(automatic, "living", 2, 174)
    assert grade(automatic, "living")["current"] == 2
    automatic.tick(204)
    assert automatic.level == 3


@pytest.mark.parametrize("decay_at,expected", [(150, 3), (163, 3), (223, 2), (283, 1)])
def test_first_neighbor_trigger_borrows_only_the_remaining_valid_grade(
    automatic, decay_at, expected
):
    automatic.config.room_connections = [["kitchen", "living"]]
    automatic.config.automatic_detection.promote_seconds = 300
    complete(automatic)
    automatic.tick(decay_at)
    fire(automatic, "living", 1, decay_at + 1)
    assert grade(automatic, "living")["current"] == expected


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
    assert automatic.room_status("kitchen", 115)["level"] == 4
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


def distributed_pairs(engine):
    engine.config.room_connections = [["kitchen", "living"], ["hall", "bed"]]
    engine.config.automatic_detection.promote_seconds = 30
    for room, at in zip(("kitchen", "living", "hall", "bed"), (101, 113, 125, 137), strict=True):
        fire(engine, room, 1, at)


def test_two_independent_confirmed_areas_reach_full_grade(automatic):
    automatic.config.room_connections = [["kitchen", "living"], ["hall", "bed"]]
    automatic.config.automatic_detection.promote_seconds = 30
    for room, at, expected in zip(
        ("kitchen", "living", "hall", "bed"), (101, 113, 125, 137), (1, 2, 2, 3), strict=True
    ):
        fire(automatic, room, 1, at)
        assert max(p["current"] for p in automatic.snapshot(at + 0.01)["rule_progress"]) == expected
        assert automatic.level == 3
    assert grade(automatic)["next_level_at"] == 167
    automatic.tick(166.99)
    assert automatic.level == 3
    automatic.tick(167)
    assert automatic.level == 4


def test_two_areas_extra_independent_sensor_promotes(automatic):
    distributed_pairs(automatic)
    fire(automatic, "living", 1, 140)  # Same physical source is no extra proof.
    assert automatic.level == 3
    assert grade(automatic)["next_level_at"] == 167
    fire(automatic, "kitchen", 2, 145)
    assert automatic.level == 4


def test_two_areas_expired_pair_does_not_combine(automatic):
    automatic.config.room_connections = [["kitchen", "living"], ["hall", "bed"]]
    fire(automatic, "kitchen", 1, 101)
    fire(automatic, "living", 1, 102)
    automatic.tick(163)
    fire(automatic, "hall", 1, 164)
    fire(automatic, "bed", 1, 165)
    assert max(p["current"] for p in automatic.snapshot(165.01)["rule_progress"]) == 2
    assert automatic.distributed_state["grade"] == 0


def test_two_areas_restart_keeps_original_deadline(automatic):
    distributed_pairs(automatic)
    restored = CorrelationEngine(automatic.config)
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(deepcopy(automatic.persistent_state()), 150)
    restored.tick(150)
    assert grade(restored)["next_level_at"] == 167
    restored.tick(167)
    assert restored.level == 4


def test_overlapping_area_views_cannot_count_twice(automatic):
    automatic.config.room_connections = [["kitchen", "living"], ["living", "hall"]]
    fire(automatic, "kitchen", 1, 101)
    fire(automatic, "living", 1, 102)
    assert automatic.distributed_state["grade"] == 0
    assert max(p["current"] for p in automatic.snapshot(102.01)["rule_progress"]) == 2


@pytest.mark.parametrize("invalidation", ["disabled", "unavailable", "connection", "profile"])
def test_two_areas_invalidated_proof_cannot_promote(automatic, invalidation):
    distributed_pairs(automatic)
    key = "binary_sensor.hall_1"
    if invalidation == "disabled":
        automatic.config.sensors[key].enabled = False
    elif invalidation == "unavailable":
        automatic.feed(key, None, 150)
    elif invalidation == "connection":
        automatic.config.room_connections = [["kitchen", "living"]]
    else:
        automatic.config.profiles["armed_away"].sensor_ids = [
            k for k in automatic.sensors if k != key
        ]
    automatic.tick(167)
    assert automatic.level <= 3
    assert automatic.distributed_state["grade"] == 0


def test_two_areas_late_tick_keeps_due_promotion_but_never_replays(automatic):
    distributed_pairs(automatic)
    automatic.tick(200)  # The deadline at 167 precedes the pair's decay at 173.
    assert automatic.level == 4
    assert grade(automatic)["detected_at"] == 167
    for at in (227, 300, 400):
        automatic.tick(at)
        assert automatic.level <= 3
        assert automatic.distributed_state["grade"] == 0
    assert automatic.level == 1


def test_two_areas_decay_before_thirty_seconds_cancels_promotion(automatic):
    automatic.config.room_connections = [["kitchen", "living"], ["hall", "bed"]]
    automatic.config.automatic_detection.promote_seconds = 30
    for room, at in zip(("kitchen", "living", "hall", "bed"), (101, 102, 155, 156), strict=True):
        fire(automatic, room, 1, at)
    assert grade(automatic)["current"] == 3
    automatic.tick(163)
    assert automatic.distributed_state["grade"] == 0
    automatic.tick(186)
    assert automatic.level == 3


def test_two_areas_higher_sensitivity_requires_two_complete_pairs(automatic):
    automatic.config.room_connections = [["kitchen", "living"], ["hall", "bed"]]
    automatic.config.automatic_detection.threshold = 2
    for room, index, at in [
        ("kitchen", 1, 101),
        ("living", 1, 102),
        ("hall", 1, 103),
        ("bed", 1, 104),
    ]:
        fire(automatic, room, index, at)
    assert automatic.distributed_state["grade"] == 0
    fire(automatic, "living", 2, 105)
    assert automatic.distributed_state["grade"] == 0
    fire(automatic, "bed", 2, 106)
    assert automatic.distributed_state["grade"] == 3


def test_two_areas_shared_physical_device_cannot_confirm_twice(automatic):
    automatic.config.sensors["binary_sensor.hall_1"].source_id = "shared"
    automatic.config.sensors["binary_sensor.kitchen_1"].source_id = "shared"
    distributed_pairs(automatic)
    assert automatic.distributed_state["grade"] == 0


def test_two_areas_disarming_clears_distributed_proof(automatic):
    distributed_pairs(automatic)
    automatic.set_profile(None, 150)
    assert automatic.distributed_state == {}
    automatic.set_profile("armed_away", 151)
    automatic.tick(167)
    assert automatic.level == 1


def test_two_areas_test_ceiling_blocks_level_four(automatic):
    automatic.config.automatic_detection.test_mode = True
    distributed_pairs(automatic)
    automatic.tick(167)
    assert automatic.level == 3
    assert grade(automatic)["next_level_at"] is None
