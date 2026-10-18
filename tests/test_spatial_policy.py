"""Acceptance scenarios KOR-01..14: meaning, space, time and physical independence."""

import pytest
from iqalarm_core.models import AlarmStage, SensorConfig


@pytest.mark.parametrize(
    "scenario",
    [
        "KOR-01",
        "KOR-02",
        "KOR-03",
        "KOR-04",
        "KOR-05",
        "KOR-06",
        "KOR-07-allowed",
        "KOR-07-denied",
        "KOR-08-contacts",
        "KOR-08-motion",
        "KOR-09",
        "KOR-10",
        "KOR-11",
        "KOR-12",
        "KOR-13",
        "KOR-14",
    ],
)
def test_acceptance_spatial_chain(engine, scenario):
    profile = engine.config.profiles["armed_night"]
    profile.multi_contact = profile.multi_motion = True
    if scenario == "KOR-07-allowed":
        profile.confirmation_paths = [["living", "hall"]]
    if scenario == "KOR-03":
        engine.config.sensors["binary_sensor.terrace"].front_of = ["hall"]
    if scenario == "KOR-08-contacts":
        engine.config.sensors["binary_sensor.lock"].role = "entry_contact"
    if scenario == "KOR-11":
        sensor = SensorConfig(
            "lock.fenstergriff", "lock_contact", "living", sensor_kind="window_handle"
        )
        engine.config.sensors[sensor.entity_id] = sensor
        engine.seed(sensor.entity_id, False)
    if scenario == "KOR-13":
        for key in ("binary_sensor.window", "binary_sensor.motion"):
            engine.config.sensors[key].source_id = "same-physical-window"
    engine.set_profile("armed_night", 100)
    if scenario in {"KOR-01", "KOR-02", "KOR-14"}:
        for index in range(5):
            engine.feed("binary_sensor.lock", index % 2 == 0, 101 + index * 2)
            if scenario == "KOR-02":
                engine.feed("binary_sensor.bed_motion", True, 101 + index * 2)
        assert "binary_sensor.lock" in engine.quarantine
        if scenario == "KOR-14":
            engine.feed("binary_sensor.terrace", True, 111)
            engine.feed("binary_sensor.window", True, 112)
    elif scenario in {"KOR-03", "KOR-04"}:
        engine.feed("binary_sensor.terrace", True, 101)
        engine.feed("binary_sensor.lock", True, 113)
    elif scenario == "KOR-10":
        engine.feed("binary_sensor.terrace", True, 101)
        engine.feed("binary_sensor.window", True, 281)
    elif scenario == "KOR-11":
        engine.feed("lock.fenstergriff", True, 101)
        assert engine.level == 0 and not engine.quarantine
    elif scenario == "KOR-08-contacts":
        engine.feed("binary_sensor.window", True, 101)
        engine.feed("binary_sensor.lock", True, 102)
    elif scenario == "KOR-08-motion":
        engine.feed("binary_sensor.bed_motion", True, 101)
        engine.feed("binary_sensor.hall_motion", True, 102)
    elif scenario == "KOR-09":
        engine.feed("binary_sensor.motion", True, 101)
        engine.feed("binary_sensor.window", True, 102)
    else:
        if scenario == "KOR-12":
            engine.feed("binary_sensor.terrace", None, 101)
        engine.feed("binary_sensor.window", True, 102)
        motion = (
            "binary_sensor.bed_motion"
            if scenario == "KOR-06"
            else "binary_sensor.hall_motion"
            if scenario.startswith("KOR-07")
            else "binary_sensor.motion"
        )
        engine.feed(motion, True, 114)
    assert engine.confirmed is (
        scenario in {"KOR-03", "KOR-05", "KOR-07-allowed", "KOR-12", "KOR-14"}
    )


def test_unlock_and_resident_motion_never_substitute_physical_entry(engine):
    engine.set_profile("armed_away", 100)
    engine.feed("binary_sensor.lock", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 102)
    assert not engine.confirmed


def test_outdoor_motion_without_person_does_not_confirm(engine):
    engine.config.sensors["binary_sensor.terrace"].role = "perimeter_sensor"
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    engine.feed("binary_sensor.window", True, 102)
    assert not engine.confirmed


def test_higher_danger_can_escalate_held_alarm_and_restore_floor(engine):
    config = engine.config
    config.stages.append(AlarmStage("danger", "Gefahr", "#ff0000", True, True, False))
    config.profiles["armed_night"].stage_targets["immediate"] = "danger"
    config.sensors["binary_sensor.hall_motion"].immediate = True
    config.validate()
    engine.set_profile("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.latched and engine.stage_id == "3"
    engine.feed("binary_sensor.hall_motion", True, 103)
    assert engine.confirmed and engine.stage_id == "danger"
    engine.tick(200)
    assert engine.stage_id == "3" and engine.latched


def test_confirmation_paths_are_directional_and_not_transitive(engine):
    engine.config.profiles["armed_night"].confirmation_paths = [["living", "hall"], ["hall", "bed"]]
    engine.set_profile("armed_night", 100)
    assert engine._same_space("living", "hall")
    assert not engine._same_space("hall", "living")
    assert not engine._same_space("living", "bed")


def test_explicit_same_room_multi_motion_is_available_for_away(engine):
    engine.config.profiles["armed_away"].multi_motion = True
    engine.config.sensors["binary_sensor.hall_motion"].room_id = "living"
    engine.set_profile("armed_away", 100)
    engine.feed("binary_sensor.motion", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 102)
    assert engine.confirmed
