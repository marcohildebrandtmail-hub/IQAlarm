"""Person reports charge LVL 2; outdoor motion never charges its inner ring."""

from copy import deepcopy

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, Room, SensorConfig
from iqalarm_core.person_detection import PersonDetection


@pytest.fixture
def cameras():
    config = Configuration(
        rooms={key: Room(key, key) for key in ("front", "garden")},
        person_detection=PersonDetection(),
    )
    for room in config.rooms:
        for kind, role in (("person", "perimeter_camera"), ("motion", "perimeter_sensor")):
            key = f"binary_sensor.{room}_{kind}"
            config.sensors[key] = SensorConfig(key, role, room, name=key)
    for profile in config.profiles.values():
        profile.rule_ids = ["perimeter"]
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_away", 100)
    return engine


def report(engine, at, room="front", kind="person"):
    entity = f"binary_sensor.{room}_{kind}"
    engine.feed(entity, True, at)
    engine.feed(entity, False, at + 2)


def progress(engine):
    return next(
        (
            p
            for p in engine.snapshot(engine._last_time)["rule_progress"]
            if p["rule_id"] == "person:global"
        ),
        None,
    )


def test_motion_triggers_level_two_without_grade(cameras):
    report(cameras, 101, kind="motion")
    assert cameras.level == 2
    assert progress(cameras) is None


def test_outdoor_map_recognition_uses_the_actual_rule_deadline(cameras):
    report(cameras, 101, kind="motion")
    recognition = cameras.room_status("front", 103)["recognitions"]
    assert recognition[0]["expires_at"] == 163
    assert recognition[0]["sources"][0]["role"] == "perimeter_sensor"
    assert cameras.room_status("garden", 103)["recognitions"] == []
    cameras.tick(162.9)
    assert cameras.level == 2
    assert cameras.room_status("front", 162.9)["recognitions"][0]["expires_at"] == 163
    cameras.tick(163)
    assert cameras.level == 1
    assert cameras.room_status("front", 163)["recognitions"] == []


def test_active_motion_has_no_predicted_expiry_and_disarmed_has_no_level_context(cameras):
    entity = "binary_sensor.front_motion"
    cameras.feed(entity, True, 101)
    assert cameras.room_status("front", 101)["recognitions"][0]["expires_at"] is None
    cameras.set_profile(None, 110)
    assert cameras.room_status("front", 110)["recognitions"] == []


def test_defaults_apply_without_first_saving_new_settings(cameras):
    cameras.config.person_detection = None
    report(cameras, 101)
    assert progress(cameras)["current"] == 1
    assert progress(cameras)["next_decay"] == 163


def test_same_camera_reports_count_until_each_shared_timer_expires(cameras):
    for at, expected in ((101, 1), (110, 2), (120, 3)):
        report(cameras, at)
        assert cameras.level == 2
        assert progress(cameras)["current"] == expected
        assert progress(cameras)["next_decay"] == 163
        assert not cameras.confirmed
    for at, expected in ((162.9, 3), (163, 2), (172, 1), (182, 0)):
        cameras.tick(at)
        assert (progress(cameras) or {}).get("current", 0) == expected
    assert cameras.level == 1


def test_no_double_count_from_snapshots_ticks_or_held_active_state(cameras):
    entity = "binary_sensor.front_person"
    cameras.feed(entity, True, 101)
    cameras.feed(entity, True, 110)
    cameras.tick(161)
    assert progress(cameras)["current"] == 1
    assert progress(cameras)["next_decay"] is None
    cameras.feed(entity, False, 162)
    assert progress(cameras)["next_decay"] == 222
    cameras.tick(222)
    assert progress(cameras) is None


def test_outdoor_motion_does_not_charge_or_refresh_person_grade(cameras):
    report(cameras, 101)
    report(cameras, 120, kind="motion")
    assert progress(cameras)["current"] == 1
    assert progress(cameras)["next_decay"] == 163
    cameras.tick(163)
    assert progress(cameras) is None
    assert cameras.level == 2


def test_thresholds_and_quiet_time_are_configurable(cameras):
    cameras.config.person_detection = PersonDetection(thresholds=[2, 4, 6], quiet_seconds=90)
    for index in range(1, 7):
        report(cameras, 100 + index * 5)
        assert (progress(cameras) or {}).get("current", 0) == index // 2
    cameras.tick(197)
    assert progress(cameras)["current"] == 2
    cameras.tick(207)
    assert progress(cameras)["current"] == 1
    cameras.tick(222)
    assert progress(cameras) is None


def test_partial_threshold_expires_without_replaying_old_evidence(cameras):
    cameras.config.person_detection = PersonDetection(thresholds=[2, 3, 4])
    report(cameras, 101)
    cameras.tick(164)
    report(cameras, 170)
    assert progress(cameras) is None
    report(cameras, 180)
    assert progress(cameras)["current"] == 1


def test_camera_reports_pool_globally_and_have_equal_full_lifetimes(cameras):
    report(cameras, 101)
    report(cameras, 110, room="garden")
    assert progress(cameras)["current"] == 2
    front = cameras.room_status("front", 112)["recognitions"][0]
    garden = cameras.room_status("garden", 112)["recognitions"][0]
    assert front["expires_at"] == 163
    assert garden["expires_at"] == 172
    for item in [front, garden]:
        assert item["expires_at"] - item["sources"][0]["timestamp"] == 62
    # Different remaining times reflect different trigger times, never weights.
    cameras.tick(163)
    assert progress(cameras)["current"] == 1
    assert cameras.room_status("front", 163)["recognitions"] == []
    assert cameras.room_status("garden", 163)["recognitions"][0]["expires_at"] == 172
    cameras.tick(172)
    assert progress(cameras) is None and cameras.level == 1


def test_mode_change_clears_counter_and_does_not_seed_active_camera(cameras):
    report(cameras, 101)
    cameras.set_profile(None, 110)
    assert progress(cameras) is None
    cameras.seed("binary_sensor.front_person", True)
    cameras.set_profile("armed_away", 120)
    cameras.tick(121)
    assert progress(cameras) is None


def test_excluded_rule_and_disabled_camera_do_not_count(cameras):
    cameras.config.profiles["armed_away"].rule_ids = []
    report(cameras, 101)
    assert progress(cameras) is None
    cameras.config.profiles["armed_away"].rule_ids = ["perimeter"]
    cameras.sensors["binary_sensor.front_person"].enabled = False
    report(cameras, 110)
    assert progress(cameras) is None


def test_unavailable_camera_clears_grade(cameras):
    report(cameras, 101)
    cameras.feed("binary_sensor.front_person", None, 110)
    assert progress(cameras) is None


def test_one_unavailable_camera_does_not_reset_other_valid_reports(cameras):
    report(cameras, 101)
    report(cameras, 110, room="garden")
    cameras.feed("binary_sensor.front_person", None, 120)
    assert progress(cameras)["current"] == 1
    assert progress(cameras)["person_reports"][0]["entity_id"] == "binary_sensor.garden_person"


def test_shared_validity_overrides_legacy_rule_and_condition_windows(cameras):
    cameras.config.rules["perimeter"].window_seconds = 180
    cameras.config.rules["perimeter"].conditions[0].max_age_seconds = 10
    report(cameras, 101)
    cameras.tick(150)
    assert progress(cameras)["current"] == 1
    assert cameras.room_status("front", 150)["recognitions"][0]["expires_at"] == 163
    cameras.tick(163)
    assert cameras.level == 1 and progress(cameras) is None


def test_coupled_validity_rejects_a_delay_longer_than_report_lifetime(cameras):
    cameras.config.person_detection.quiet_seconds = 10
    cameras.config.rules["perimeter"].delay_seconds = 10
    with pytest.raises(ValueError, match="Meldegültigkeit"):
        cameras.config.validate()


def test_restore_preserves_counter_and_deadline_without_recounting(cameras):
    report(cameras, 101)
    report(cameras, 110)
    restored = CorrelationEngine(cameras.config)
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(deepcopy(cameras.persistent_state()), 120)
    assert progress(restored)["current"] == 2
    restored.tick(163)
    assert progress(restored)["current"] == 1
    restored.tick(172)
    assert progress(restored) is None


def test_config_roundtrip_and_legacy_config_without_new_settings(cameras):
    data = cameras.config.to_dict()
    assert Configuration.from_dict(data).person_detection == PersonDetection()
    data.pop("person_detection")
    assert Configuration.from_dict(data).person_detection is None


def test_camera_assigned_via_front_of_counts_for_its_room(cameras):
    camera = cameras.sensors["binary_sensor.front_person"]
    camera.room_id = None
    camera.front_of = ["front"]
    report(cameras, 101)
    assert progress(cameras)["current"] == 1


def test_camera_reports_never_provide_independent_full_alarm_sources(cameras):
    from iqalarm_core.level_rules import LevelRule, RuleCondition

    cameras.config.rules["two_cameras"] = LevelRule(
        "two_cameras",
        "Independent cameras",
        "5",
        [RuleCondition(roles=["perimeter_camera"], count=2)],
    )
    cameras.config.profiles["armed_away"].rule_ids.append("two_cameras")
    for at in (101, 110, 120, 130):
        report(cameras, at)
    assert progress(cameras)["current"] == 3
    assert cameras.level == 2
    assert not cameras.confirmed
    assert len(cameras.evidence) == 1


def test_changed_settings_do_not_recount_old_camera_reports(cameras):
    report(cameras, 101)
    cameras.config.person_detection.quiet_seconds = 90
    cameras.tick(110)
    assert progress(cameras) is None
    report(cameras, 120)
    assert progress(cameras)["current"] == 1


@pytest.mark.parametrize(
    "settings",
    [
        {"thresholds": [1, 1, 3]},
        {"thresholds": [0, 2, 3]},
        {"thresholds": [1, 2]},
        {"thresholds": [1, 2, 101]},
        {"quiet_seconds": 0},
        {"quiet_seconds": float("nan")},
    ],
)
def test_invalid_settings_rejected(settings):
    with pytest.raises(ValueError):
        PersonDetection(**settings)
