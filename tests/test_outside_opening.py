"""Only fresh, mapped contact evidence after outdoor 3/3 unlocks LVL 4."""

from copy import deepcopy

import pytest
from iqalarm_core.automatic_detection import AutomaticDetection
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.level_rules import LevelRule, RuleCondition
from iqalarm_core.models import Configuration, Room, SensorConfig
from iqalarm_core.models import Settings as ScenarioSettings
from iqalarm_core.outside_opening import OUTSIDE_OPENING_RULE
from iqalarm_core.person_detection import PersonDetection


@pytest.fixture
def outdoor():
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms={key: Room(key, key) for key in ("garden", "front", "living", "hall")},
        automatic_detection=AutomaticDetection(test_stage_id="4"),
        person_detection=PersonDetection(),
        outside_inside_links=[["garden", "living"], ["front", "hall"]],
    )
    for room in ("garden", "front"):
        for kind, role in (("person", "perimeter_camera"), ("motion", "perimeter_sensor")):
            key = f"binary_sensor.{room}_{kind}"
            config.sensors[key] = SensorConfig(key, role, room)
    for room in ("living", "hall"):
        for kind, role in (
            ("window", "entry_contact"),
            ("lock", "lock_contact"),
            ("motion", "interior_motion"),
        ):
            key = f"binary_sensor.{room}_{kind}"
            config.sensors[key] = SensorConfig(key, role, room)
    for profile in config.profiles.values():
        profile.rule_ids = ["perimeter", "single", "motion", "immediate"]
    config.validate()
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_away", 100)
    return engine


def pulse(engine, name, at):
    key = f"binary_sensor.{name}"
    engine.feed(key, True, at)
    engine.feed(key, False, at + 2)


def full(engine):
    for at in (101, 113, 125):
        pulse(engine, "garden_person", at)
    assert engine.level == 2
    assert engine.person_states["global"]["grade"] == 3


def test_mapped_new_opening_reaches_four_without_full_alarm_or_latch(outdoor):
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    assert outdoor.level == 4
    assert not outdoor.confirmed and not outdoor.latched
    assert outdoor.held_alarm is None
    match = next(m for m in outdoor.rule_matches if m.rule_id == OUTSIDE_OPENING_RULE)
    assert match.expires_at == 197
    assert [e.entity_id for e in match.chain][-1] == "binary_sensor.living_window"
    assert outdoor.room_status("living", 139)["level"] == 4
    recognition = next(
        r for r in outdoor.room_status("living", 139)["recognitions"] if r["level"] == 4
    )
    assert [source["entity_id"] for source in recognition["sources"]] == [
        "binary_sensor.living_window"
    ]
    assert recognition["expires_at"] == 197
    assert outdoor.room_status("hall", 139)["level"] == 1
    outdoor.snapshot(139)  # Every room must resolve the virtual rule safely.
    outdoor.tick(164)  # First outdoor report expired; original proof remains valid.
    assert outdoor.person_states["global"]["grade"] == 2
    assert outdoor.level == 4
    outdoor.tick(196.999)
    assert outdoor.level == 4
    outdoor.tick(197)
    assert outdoor.level < 4
    outdoor.tick(400)
    assert outdoor.level == 1
    assert all(event.level <= 4 for event in outdoor.drain())


@pytest.mark.parametrize("name", ["living_lock", "living_window"])
def test_lock_and_window_both_count_as_fresh_contacts(outdoor, name):
    full(outdoor)
    pulse(outdoor, name, 137)
    assert outdoor.level == 4


@pytest.mark.parametrize("name", ["hall_window", "living_motion"])
def test_unmapped_opening_or_motion_does_not_skip_to_four(outdoor, name):
    full(outdoor)
    pulse(outdoor, name, 137)
    assert outdoor.level == 3
    assert not outdoor.outside_opening_state["openings"]


def test_old_opening_cannot_be_promoted_by_later_outdoor_reports(outdoor):
    pulse(outdoor, "living_window", 101)
    for at in (113, 125, 137):
        pulse(outdoor, "garden_person", at)
    assert outdoor.person_states["global"]["grade"] == 3
    assert outdoor.level == 3
    outdoor.tick(140)
    assert outdoor.level == 3
    pulse(outdoor, "living_window", 149)
    assert outdoor.level == 4


def test_two_outdoor_points_are_insufficient(outdoor):
    for at in (101, 113):
        pulse(outdoor, "garden_person", at)
    pulse(outdoor, "living_window", 125)
    assert outdoor.level == 3


def test_expired_full_grade_cannot_promote_new_opening(outdoor):
    full(outdoor)
    outdoor.tick(164)
    pulse(outdoor, "living_window", 165)
    assert outdoor.level == 3


def test_mapping_must_belong_to_a_contributing_outdoor_area(outdoor):
    # Front has a mapping, but its single PIR contributed no grade.
    pulse(outdoor, "front_motion", 101)
    for at in (105, 117, 129):
        pulse(outdoor, "garden_person", at)
    pulse(outdoor, "hall_window", 141)
    assert outdoor.person_states["global"]["grade"] == 3
    assert outdoor.level == 3


def test_motion_contributing_to_full_grade_can_supply_the_mapping(outdoor):
    outdoor.config.room_connections = [["garden", "front"]]
    pulse(outdoor, "garden_motion", 101)
    pulse(outdoor, "front_motion", 113)
    pulse(outdoor, "garden_person", 125)
    pulse(outdoor, "garden_person", 137)
    assert outdoor.person_states["global"]["grade"] == 3
    pulse(outdoor, "hall_window", 149)
    assert outdoor.level == 4


@pytest.mark.parametrize("exclusion", ["ignored", "disabled", "information", "profile", "contacts"])
def test_excluded_contact_never_promotes(outdoor, exclusion):
    key = "binary_sensor.living_window"
    if exclusion == "ignored":
        outdoor.ignored_windows[key] = {}
    elif exclusion == "disabled":
        outdoor.sensors[key].enabled = False
    elif exclusion == "information":
        outdoor.sensors[key].sensor_kind = "window_handle"
    elif exclusion == "profile":
        outdoor.profile.sensor_ids = [k for k in outdoor.sensors if k != key]
    else:
        outdoor.profile.contacts_enabled = False
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    assert outdoor.level <= 3
    assert not outdoor.outside_opening_state.get("openings")


def test_same_physical_device_cannot_confirm_itself(outdoor):
    outdoor.sensors["binary_sensor.garden_person"].source_id = "shared"
    outdoor.sensors["binary_sensor.living_window"].source_id = "shared"
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    assert outdoor.level < 4


@pytest.mark.parametrize("change", ["unavailable", "disabled", "mapping", "profile", "revision"])
def test_invalidated_proof_is_removed(outdoor, change):
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    assert outdoor.level == 4
    if change == "unavailable":
        outdoor.feed("binary_sensor.garden_person", None, 140)
    elif change == "disabled":
        outdoor.sensors["binary_sensor.garden_person"].enabled = False
    elif change == "mapping":
        outdoor.config.outside_inside_links = []
    elif change == "profile":
        outdoor.set_profile(None, 140)
    else:
        outdoor.config.revision += 1
    outdoor.tick(141)
    assert outdoor.level < 4


def test_default_ceiling_remains_three(outdoor):
    outdoor.config.automatic_detection.test_stage_id = None
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    assert outdoor.level == 3
    assert not outdoor.outside_opening_state


def test_four_ceiling_still_blocks_five_after_indoor_promotion(outdoor):
    outdoor.config.rules["danger"] = LevelRule(
        "danger", "Danger", "5", [RuleCondition(roles=["entry_contact"], event="override")]
    )
    outdoor.profile.rule_ids.append("danger")
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    pulse(outdoor, "living_lock", 149)
    pulse(outdoor, "living_motion", 161)
    outdoor.tick(220)
    assert (
        outdoor.level == 4
    )  # Outdoor bonus completes the pair; third indoor source promotes at 161.
    assert not outdoor.stage_allowed("5") and outdoor.stage_allowed("4")
    assert all(event.level <= 4 for event in outdoor.drain())


def test_config_roundtrip_preserves_test_ceiling(outdoor):
    config = Configuration.from_dict(outdoor.config.to_dict())
    assert config.automatic_detection.test_stage_id == "4"
    with pytest.raises(ValueError):
        AutomaticDetection(test_stage_id="5")


def test_restart_preserves_proof_without_extending_deadline(outdoor):
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    saved = deepcopy(outdoor.persistent_state())
    restored = CorrelationEngine(deepcopy(outdoor.config))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(saved, 150)
    assert restored.level == 4
    restored.tick(197)
    assert restored.level < 4


@pytest.mark.parametrize(
    "bad", ["short_chain", "duplicate", "future", "nan", "missing", "role", "until"]
)
def test_invalid_restored_proof_cannot_raise_level_four(outdoor, bad):
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    saved = deepcopy(outdoor.persistent_state())
    record = saved["outside_opening_state"]["openings"]["living"]
    if bad == "short_chain":
        record["chain"] = record["chain"][-2:]
    elif bad == "duplicate":
        record["chain"][1] = record["chain"][0]
    elif bad == "future":
        record["chain"][0]["timestamp"] = 200
    elif bad == "nan":
        record["chain"][0]["timestamp"] = float("nan")
    elif bad == "missing":
        record["chain"] = None
    elif bad == "role":
        record["chain"][0]["role"] = "entry_contact"
    else:
        record["until"] += 60
    restored = CorrelationEngine(deepcopy(outdoor.config))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(saved, 150)
    assert restored.level < 4


def test_held_contact_does_not_refresh_level_four_timer(outdoor):
    full(outdoor)
    outdoor.feed("binary_sensor.living_window", True, 137)
    outdoor.feed("binary_sensor.living_window", True, 150)
    assert outdoor.level == 4
    assert outdoor.outside_opening_state["openings"]["living"]["until"] == 197
    outdoor.tick(197)
    assert outdoor.level < 4


def test_profile_change_does_not_replay_previous_full_grade_or_opening(outdoor):
    full(outdoor)
    pulse(outdoor, "living_window", 137)
    outdoor.set_profile(None, 140)
    outdoor.set_profile("armed_away", 142)
    outdoor.tick(143)
    assert outdoor.level == 1
    assert not outdoor.outside_opening_state.get("openings")


def bonus_full(engine):
    for at in (101, 105, 109):
        pulse(engine, "garden_person", at)


def indoor_grade(engine, room="hall"):
    return engine.room_status(room, engine._last_time)["detection"]


def test_outdoor_bonus_needs_an_indoor_source(outdoor):
    bonus_full(outdoor)
    assert outdoor.level == 2
    assert indoor_grade(outdoor) is None
    pulse(outdoor, "hall_motion", 111)
    assert outdoor.level == 3
    assert indoor_grade(outdoor)["current"] == 2
    assert not outdoor.outside_opening_state["openings"]


def test_outdoor_bonus_two_related_indoor_sources_then_thirty_seconds(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_window", 123)
    assert indoor_grade(outdoor)["current"] == 3
    assert indoor_grade(outdoor)["next_level_at"] == 153
    outdoor.tick(152.999)
    assert outdoor.level == 3
    outdoor.tick(153)
    assert outdoor.level == 4


def test_outdoor_bonus_next_independent_indoor_source_promotes(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_window", 123)
    pulse(outdoor, "hall_lock", 135)
    assert outdoor.level == 4


def test_outdoor_bonus_unrelated_indoor_sources_do_not_form_pair(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "living_motion", 123)
    assert outdoor.level == 3
    assert indoor_grade(outdoor)["current"] == 2
    assert indoor_grade(outdoor, "living")["current"] == 2
    outdoor.tick(154)
    assert outdoor.level == 3


def test_outdoor_bonus_expiry_cancels_incomplete_thirty_seconds(outdoor):
    full(outdoor)
    pulse(outdoor, "hall_motion", 137)
    pulse(outdoor, "hall_window", 149)
    assert indoor_grade(outdoor)["current"] == 3
    assert indoor_grade(outdoor)["next_level_at"] is None
    outdoor.tick(163)
    assert indoor_grade(outdoor)["current"] == 2
    outdoor.tick(179)
    assert outdoor.level == 3


def test_outdoor_bonus_can_start_later_without_backdating_timer(outdoor):
    pulse(outdoor, "hall_motion", 101)
    pulse(outdoor, "hall_window", 105)
    assert indoor_grade(outdoor)["current"] == 2
    for at in (109, 113, 117):
        pulse(outdoor, "garden_person", at)
    assert indoor_grade(outdoor)["current"] == 3
    assert indoor_grade(outdoor)["next_level_at"] == 147
    outdoor.tick(135)
    assert outdoor.level == 3
    outdoor.tick(147)
    assert outdoor.level == 4


def test_outdoor_bonus_two_points_do_not_count(outdoor):
    for at in (101, 105):
        pulse(outdoor, "garden_person", at)
    pulse(outdoor, "hall_motion", 111)
    assert indoor_grade(outdoor)["current"] == 1
    pulse(outdoor, "hall_window", 123)
    assert indoor_grade(outdoor)["current"] == 2


def test_outdoor_bonus_restart_keeps_original_deadline(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_window", 123)
    saved = deepcopy(outdoor.persistent_state())
    restored = CorrelationEngine(Configuration.from_dict(outdoor.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(saved, 130)
    assert indoor_grade(restored)["next_level_at"] == 153
    restored.tick(153)
    assert restored.level == 4


def test_outdoor_bonus_same_physical_source_cannot_count_twice(outdoor):
    outdoor.sensors["binary_sensor.garden_person"].source_id = "shared"
    outdoor.sensors["binary_sensor.hall_motion"].source_id = "shared"
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    assert indoor_grade(outdoor)["current"] == 1


@pytest.mark.parametrize("at", [163, 164])
def test_outdoor_bonus_thirty_seconds_wins_at_shared_expiry(outdoor, at):
    bonus_full(outdoor)  # First report expires at 163.
    pulse(outdoor, "hall_motion", 121)
    pulse(outdoor, "hall_window", 133)
    assert indoor_grade(outdoor)["next_level_at"] == 163
    outdoor.tick(at)
    assert outdoor.level == 4


def test_outdoor_bonus_third_sensor_can_be_distant(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_window", 123)
    pulse(outdoor, "living_motion", 135)
    assert outdoor.level == 4


def test_outdoor_bonus_repeated_indoor_source_never_completes_pair(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_motion", 123)
    assert indoor_grade(outdoor)["current"] == 2
    outdoor.tick(154)
    assert outdoor.level == 3


def test_outdoor_bonus_invalidated_camera_cancels_promotion(outdoor):
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_window", 123)
    outdoor.feed("binary_sensor.garden_person", None, 140)
    assert indoor_grade(outdoor)["current"] == 2
    outdoor.tick(153)
    assert outdoor.level == 3


def test_outdoor_bonus_respects_configured_indoor_sensitivity(outdoor):
    outdoor.config.automatic_detection.threshold = 2
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    assert indoor_grade(outdoor) is None
    pulse(outdoor, "hall_window", 123)
    assert indoor_grade(outdoor)["current"] == 2
    pulse(outdoor, "hall_lock", 135)
    assert indoor_grade(outdoor)["current"] == 3


def test_outdoor_bonus_respects_test_ceiling(outdoor):
    outdoor.config.automatic_detection.test_stage_id = "3"
    bonus_full(outdoor)
    pulse(outdoor, "hall_motion", 111)
    pulse(outdoor, "hall_window", 123)
    pulse(outdoor, "hall_lock", 135)
    outdoor.tick(154)
    assert outdoor.level == 3
