"""User-selected level conditions are the single authority for profile evaluation."""

from copy import deepcopy

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.level_rules import LevelRule, RuleCondition
from iqalarm_core.models import Action, AlarmStage, Configuration, SensorConfig
from iqalarm_core.models import Settings as ScenarioSettings


@pytest.fixture
def free(config):
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms=deepcopy(config.rooms),
        sensors=deepcopy(config.sensors),
    )
    config.sensors["binary_sensor.person2"] = SensorConfig(
        "binary_sensor.person2", "perimeter_camera", front_of=["living"]
    )
    config.sensors["binary_sensor.outside_motion"] = SensorConfig(
        "binary_sensor.outside_motion", "perimeter_sensor", front_of=["living"]
    )
    result = CorrelationEngine(config)
    for key in result.sensors:
        result.seed(key, False)
    return result


def custom(engine, **changes):
    values = dict(
        id="custom",
        name="Außen bestätigt",
        stage_id="3",
        conditions=[
            RuleCondition(
                sensor_ids=[
                    "binary_sensor.terrace",
                    "binary_sensor.person2",
                    "binary_sensor.outside_motion",
                ],
                count=2,
            )
        ],
        window_seconds=30,
    )
    values.update(changes)
    rule = LevelRule(**values)
    engine.config.rules[rule.id] = rule
    for profile in engine.config.profiles.values():
        profile.rule_ids = [rule.id]
    engine.config.validate()
    return rule


def test_night_defaults_allow_bathroom_then_confirm_matching_opening(free):
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.motion", True, 101)
    assert free.level == 1
    free.feed("binary_sensor.window", True, 102)
    assert free.level == 3 and not free.confirmed
    free.feed("binary_sensor.motion", False, 103)
    free.feed("binary_sensor.motion", True, 114)
    assert free.level == 5 and free.confirmed


def test_single_source_rule_respects_configured_debounce(free):
    free.config.sensors["binary_sensor.window"].debounce_ms = 1000
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", True, 101)
    free.tick(101.5)
    assert free.level == 1
    free.feed("binary_sensor.window", False, 101.6)
    free.tick(102.1)
    assert free.level == 1
    free.feed("binary_sensor.window", True, 103)
    free.tick(104.1)
    assert free.level == 3


@pytest.mark.parametrize("second", ["binary_sensor.person2", "binary_sensor.outside_motion"])
def test_two_selected_outdoor_sources_within_thirty_seconds(free, second):
    custom(free)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    assert free.level == 1
    free.feed(second, True, 125)
    assert free.level == 3 and not free.confirmed


def test_repeated_same_camera_never_counts_twice(free):
    custom(free)
    free.set_profile("armed_away", 100)
    for index in range(8):
        free.feed("binary_sensor.terrace", index % 2 == 0, 101 + index)
    assert free.level == 1


def test_same_physical_device_never_counts_twice(free):
    custom(free)
    free.sensors["binary_sensor.terrace"].source_id = "device:one"
    free.sensors["binary_sensor.person2"].source_id = "device:one"
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.person2", True, 102)
    assert free.level == 1


def parallel_room_rule(engine, *, count=1, stage_id="2", delay_seconds=0):
    engine.sensors["binary_sensor.outside_motion"].front_of = ["hall"]
    key = "binary_sensor.hall_person"
    engine.config.sensors[key] = SensorConfig(key, "perimeter_camera", front_of=["hall"])
    engine.seed(key, False)
    return custom(
        engine,
        stage_id=stage_id,
        conditions=[
            RuleCondition(
                sensor_ids=[
                    "binary_sensor.terrace",
                    "binary_sensor.person2",
                    "binary_sensor.outside_motion",
                    key,
                ],
                count=count,
            )
        ],
        window_seconds=30,
        delay_seconds=delay_seconds,
    )


def test_one_rule_reports_simultaneous_outdoor_activity_in_both_rooms(free):
    parallel_room_rule(free)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.terrace", False, 102)
    free.feed("binary_sensor.outside_motion", True, 105)
    free.feed("binary_sensor.outside_motion", False, 106)
    before = deepcopy(free.persistent_state())
    snapshot = free.snapshot(110)
    for room in ("living", "hall"):
        assert snapshot["rooms"][room]["level"] == 2
        assert snapshot["rooms"][room]["perimeter"]
    assert snapshot["rooms"]["bed"]["level"] == 1
    assert snapshot["matched_rules"] == ["custom"]
    assert len(free.rule_matches[0].chain) == 1
    assert free.persistent_state() == before
    # Each room expires on its own evidence; the older room cannot borrow the newer event.
    free.tick(131)
    assert free.room_status("living", 131)["level"] == 1
    assert free.room_status("hall", 131)["level"] == 2
    free.tick(135)
    assert free.room_status("hall", 135)["level"] == 1


@pytest.mark.parametrize("stage_id", ["2", "5"])
def test_parallel_room_proofs_still_require_each_rooms_independent_sources(free, stage_id):
    parallel_room_rule(free, count=2, stage_id=stage_id)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.outside_motion", True, 102)
    assert free.level == 1  # Two unrelated rooms do not confirm each other.
    free.feed("binary_sensor.person2", True, 103)
    assert free.room_status("living", 103)["level"] == int(stage_id)
    assert free.room_status("hall", 103)["level"] == 1
    free.feed("binary_sensor.hall_person", True, 104)
    before = deepcopy(free.persistent_state())
    for room in ("living", "hall"):
        status = free.room_status(room, 104)
        assert status["level"] == int(stage_id)
        assert status["confirmed"] == (stage_id == "5")
    assert free.room_status("bed", 104)["level"] == 1
    assert len(free.rule_matches[0].chain) == 2
    assert free.persistent_state() == before


def test_parallel_room_display_does_not_bypass_a_pending_rule_delay(free):
    parallel_room_rule(free, delay_seconds=10)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.outside_motion", True, 105)
    before = deepcopy(free.persistent_state())
    for room in ("living", "hall"):
        assert free.room_status(room, 105)["level"] == 1
    assert free.persistent_state() == before
    free.tick(111)
    for room in ("living", "hall"):
        assert free.room_status(room, 111)["level"] == 2


def test_parallel_room_display_respects_rule_and_sensor_exclusions(free):
    rule = parallel_room_rule(free)
    rule.conditions[0].sensor_ids.remove("binary_sensor.outside_motion")
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.outside_motion", True, 102)
    assert free.room_status("living", 102)["level"] == 2
    assert free.room_status("hall", 102)["level"] == 1
    free.sensors["binary_sensor.person2"].enabled = False
    free.feed("binary_sensor.person2", True, 103)
    assert free.room_status("hall", 103)["level"] == 1


def test_window_and_unrelated_motion_never_confirm(free):
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", True, 101)
    free.feed("binary_sensor.bed_motion", True, 112)
    assert free.level == 3 and not free.confirmed


def test_cross_room_rule_requires_an_explicit_directed_path(free):
    rule = custom(
        free,
        stage_id="5",
        ordered=True,
        conditions=[
            RuleCondition(sensor_ids=["binary_sensor.window"]),
            RuleCondition(sensor_ids=["binary_sensor.hall_motion"]),
        ],
    )
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", True, 101)
    free.feed("binary_sensor.hall_motion", True, 102)
    assert not free.confirmed
    rule.paths = [["living", "hall"]]
    free.tick(103)
    assert free.level == 5 and free.confirmed


def test_expired_camera_event_cannot_confirm_another_sensor(free):
    custom(free)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.terrace", False, 102)
    free.feed("binary_sensor.person2", True, 132)
    assert free.level == 1


def test_still_active_camera_is_not_a_new_confirmation_after_window(free):
    custom(free)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.person2", True, 132)
    assert free.level == 1


def test_migration_preserves_night_contact_gate_even_for_two_motion_rule(config):
    data = config.to_dict()
    del data["rules"]
    data["profiles"]["armed_night"]["multi_motion"] = True
    migrated = Configuration.from_dict(data)
    engine = CorrelationEngine(migrated)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.motion", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 102)
    assert not engine.confirmed and engine.secure
    rules = [migrated.rules[key] for key in migrated.profiles["armed_night"].rule_ids]
    double_motion = next(r for r in rules if r.id.startswith("multi_motion"))
    assert double_motion.ordered and len(double_motion.conditions) == 2
    assert double_motion.conditions[0].roles == ["entry_contact", "vibration_glass"]


def test_unavailable_source_cannot_confirm_and_does_not_become_open(free):
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", True, 101)
    free.feed("binary_sensor.window", None, 102)
    free.feed("binary_sensor.motion", True, 103)
    assert free.level == 3 and not free.confirmed
    assert free.room_status("living", 103)["open"] == []


def test_flapping_never_fulfils_full_alarm_conditions(free):
    free.set_profile("armed_night", 100)
    for index in range(5):
        free.feed("binary_sensor.lock", index % 2 == 0, 101 + index)
    assert "binary_sensor.lock" in free.quarantine
    assert free.level == 3 and not free.confirmed


def test_interior_motion_level_can_be_enabled_without_changing_global_sensor_policy(free):
    free.config.profiles["armed_night"].rule_ids.append("motion")
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.motion", True, 101)
    assert free.level == 4 and not free.confirmed


def test_confirmed_rule_delay_and_restored_alarm(free):
    custom(free, stage_id="5", delay_seconds=10)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.person2", True, 105)
    assert free.level == 1 and free.pending_until == 115
    free.tick(114)
    assert not free.confirmed
    free.tick(115)
    assert free.level == 5 and free.confirmed
    restored = CorrelationEngine(Configuration.from_dict(free.config.to_dict()))
    restored.restore(free.persistent_state(), 500)
    assert restored.level == 5 and restored.confirmed and restored.latched


def test_pending_restore_rechecks_current_physical_device_identity(free):
    custom(free, stage_id="5", delay_seconds=10)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.person2", True, 102)
    data = free.persistent_state()
    config = Configuration.from_dict(free.config.to_dict())
    for key in ("binary_sensor.terrace", "binary_sensor.person2"):
        config.sensors[key].source_id = "device:merged"
    restored = CorrelationEngine(config)
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(data, 103)
    restored.tick(113)
    assert not restored.confirmed


def test_diagnostic_delay_keeps_its_deadline_across_restart(free):
    custom(
        free,
        delay_seconds=10,
        conditions=[RuleCondition(sensor_ids=["binary_sensor.window"], event="unavailable")],
    )
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", None, 101)
    restored = CorrelationEngine(Configuration.from_dict(free.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.seed("binary_sensor.window", None)
    restored.restore(free.persistent_state(), 105)
    assert restored.pending_until == 111
    restored.tick(111)
    assert restored.level == 3 and not restored.confirmed


def test_single_source_cannot_target_confirmed_alarm(free):
    with pytest.raises(ValueError, match="unabhängige"):
        custom(free, stage_id="5", conditions=[RuleCondition(sensor_ids=["binary_sensor.terrace"])])


def test_live_evaluation_has_no_output_permission(free):
    free.feed("binary_sensor.terrace", True, 100)
    free.feed("binary_sensor.window", True, 110)
    assert free.level == 5 and free.confirmed and not free.reactions_enabled and not free.latched


def test_disabled_profile_rule_cannot_leak_from_another_profile(free):
    free.config.profiles["armed_night"].rule_ids = ["perimeter"]
    free.config.profiles["armed_away"].rule_ids = ["motion"]
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.motion", True, 101)
    assert free.level == 1


def test_away_default_accepts_reverse_contact_motion_order(free):
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.motion", True, 101)
    free.feed("binary_sensor.window", True, 102)
    assert free.level == 5 and free.confirmed


def test_three_sources_need_one_common_space_not_a_chain_of_camera_overlaps(free):
    custom(
        free,
        conditions=[
            RuleCondition(
                sensor_ids=[
                    "binary_sensor.terrace",
                    "binary_sensor.person2",
                    "binary_sensor.outside_motion",
                ],
                count=3,
            )
        ],
    )
    free.sensors["binary_sensor.terrace"].front_of = ["living", "hall"]
    free.sensors["binary_sensor.person2"].front_of = ["living"]
    free.sensors["binary_sensor.outside_motion"].front_of = ["hall"]
    free.set_profile("armed_away", 100)
    for index, key in enumerate(
        ("binary_sensor.terrace", "binary_sensor.person2", "binary_sensor.outside_motion")
    ):
        free.feed(key, True, 101 + index)
    assert free.level == 1


def test_paths_are_direct_and_never_transitive(free):
    rule = custom(
        free,
        conditions=[
            RuleCondition(sensor_ids=["binary_sensor.window"]),
            RuleCondition(sensor_ids=["binary_sensor.hall_motion"]),
            RuleCondition(sensor_ids=["binary_sensor.bed_motion"]),
        ],
    )
    rule.paths = [["living", "hall"], ["hall", "bed"]]
    free.set_profile("armed_away", 100)
    for index, key in enumerate(
        ("binary_sensor.window", "binary_sensor.hall_motion", "binary_sensor.bed_motion")
    ):
        free.feed(key, True, 101 + index)
    assert free.level == 1


def test_pending_match_is_cancelled_when_a_source_loses_connection(free):
    custom(free, stage_id="5", delay_seconds=10)
    free.set_profile("armed_away", 100)
    free.feed("binary_sensor.terrace", True, 101)
    free.feed("binary_sensor.person2", True, 102)
    assert free.pending_until == 112
    free.feed("binary_sensor.person2", None, 104)
    free.tick(113)
    assert not free.confirmed and free.pending_until is None


@pytest.mark.parametrize("event", ["unavailable", "flapping"])
def test_diagnostic_conditions_can_use_a_delay_and_clear_on_recovery(free, event):
    custom(
        free,
        delay_seconds=5,
        conditions=[RuleCondition(sensor_ids=["binary_sensor.window"], event=event)],
    )
    free.set_profile("armed_night", 100)
    if event == "unavailable":
        free.feed("binary_sensor.window", None, 101)
    else:
        for index, value in enumerate((True, False, True)):
            free.feed("binary_sensor.window", value, 101 + index)
    deadline = free.pending_until
    assert deadline is not None and free.level == 1
    free.tick(deadline)
    assert free.level == 3 and not free.confirmed
    if event == "unavailable":
        free.feed("binary_sensor.window", False, deadline + 1)
    else:
        free.clear_quarantine(None, deadline + 1)
    assert free.level == 1


def test_new_rules_cannot_use_faults_as_alarm_confirmation(free):
    with pytest.raises(ValueError, match="Störungen"):
        custom(
            free,
            stage_id="5",
            conditions=[
                RuleCondition(sensor_ids=["binary_sensor.window"], event="unavailable"),
                RuleCondition(sensor_ids=["binary_sensor.motion"]),
            ],
        )


def test_override_requires_an_explicitly_approved_sensor(free):
    custom(
        free,
        stage_id="5",
        conditions=[RuleCondition(sensor_ids=["binary_sensor.window"], event="override")],
    )
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", True, 101)
    assert not free.confirmed
    free.sensors["binary_sensor.window"].immediate = True
    free.feed("binary_sensor.window", False, 102)
    free.feed("binary_sensor.window", True, 103)
    # The third edge quarantines a lone ordinary contact before override admission.
    assert not free.confirmed
    free.clear_quarantine(None, 104)
    free.config.sensors["binary_sensor.window"].flap_enabled = False
    free.feed("binary_sensor.window", False, 105)
    free.feed("binary_sensor.window", True, 106)
    assert free.confirmed


def test_higher_unlatched_alarm_restores_the_held_floor_after_reload(free):
    free.config.stages.append(AlarmStage("higher", "Gefahr", "#ff0000", True, False, False))
    free.config.rules["higher"] = LevelRule(
        "higher",
        "Zwei Kameras",
        "higher",
        [RuleCondition(sensor_ids=["binary_sensor.terrace", "binary_sensor.person2"], count=2)],
        10,
    )
    free.config.profiles["armed_night"].rule_ids.append("higher")
    free.set_profile("armed_night", 100)
    free.feed("binary_sensor.window", True, 101)
    free.feed("binary_sensor.motion", True, 102)
    assert free.level == 5 and free.latched
    free.feed("binary_sensor.terrace", True, 103)
    free.feed("binary_sensor.person2", True, 104)
    assert free.stage_id == "higher" and not free.latched
    restored = CorrelationEngine(Configuration.from_dict(free.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(free.persistent_state(), 105)
    restored.tick(200)
    assert restored.level == 5 and restored.latched


def test_old_profile_scopes_and_action_owners_are_migrated_once(config):
    data = config.to_dict()
    del data["rules"]
    data["actions"] = {
        "push": {"id": "push", "level": "2", "kind": "notify", "target": "notify.phone"}
    }
    data["profiles"]["armed_night"]["action_ids"] = []
    data["profiles"]["armed_away"]["perimeter_seconds"] = 27
    migrated = Configuration.from_dict(data)
    assert "armed_night" not in migrated.actions["push"].profile_ids
    assert "armed_away" in migrated.actions["push"].profile_ids
    assert any(
        migrated.rules[r].window_seconds == 27 for r in migrated.profiles["armed_away"].rule_ids
    )
    assert Configuration.from_dict(migrated.to_dict()).to_dict() == migrated.to_dict()


def test_empty_selected_rule_set_does_not_enable_all_other_profiles_rules(free):
    free.config.profiles["armed_night"].rule_ids = []
    with pytest.raises(ValueError, match="keine verwendbaren Sensoren"):
        free.set_profile("armed_night", 100)


def test_new_action_requires_an_explicit_profile_owner(free):
    free.config.actions["a"] = Action("a", "3", "notify", "notify.phone")
    with pytest.raises(ValueError, match="Alarmmodus-Zuordnung"):
        free.config.validate()


@pytest.mark.parametrize(
    "changes",
    [
        {"conditions": []},
        {"window_seconds": 0},
        {"delay_seconds": 601},
        {"ordered": "yes"},
        {"paths": [["a", "a"]]},
    ],
)
def test_invalid_rule_input_is_rejected(changes):
    with pytest.raises(ValueError):
        LevelRule(
            **(
                {
                    "id": "r",
                    "name": "R",
                    "stage_id": "2",
                    "conditions": [RuleCondition(roles=["perimeter_camera"])],
                }
                | changes
            )
        )
