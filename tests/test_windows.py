"""Window calibration, missing links and a single independent alarm source."""

from copy import deepcopy

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, Room, SensorConfig, WindowConfig
from iqalarm_core.windows import (
    WindowTracker,
    capture_position,
    inspect_window,
    related_window_information,
)


@pytest.mark.parametrize(
    "case", ["same", "other_room", "unrelated", "missing", "ambiguous", "not_information"]
)
def test_related_actor_requires_unique_physical_window_owner(case):
    window = WindowConfig(
        "w",
        "Fenster",
        "living",
        lock_entity_id="lock.grip",
        handle_entity_ids=["binary_sensor.grip"],
    )
    actor = SensorConfig(
        "binary_sensor.actor", "lock_contact", "living", sensor_kind="window_handle"
    )
    config = Configuration(windows={"w": window}, sensors={actor.entity_id: actor})
    devices = {
        "lock.grip": "hardware",
        "binary_sensor.grip": "hardware",
        actor.entity_id: "hardware",
    }
    if case == "other_room":
        actor.room_id = "hall"
    if case == "unrelated":
        devices[actor.entity_id] = "other"
    if case == "missing":
        devices.pop(actor.entity_id)
    if case == "ambiguous":
        config.windows["other"] = WindowConfig(
            "other", "Anderes Fenster", "living", contact_entity_id="binary_sensor.other"
        )
        devices["binary_sensor.other"] = "hardware"
    if case == "not_information":
        actor.sensor_kind = "door_lock"
    assert related_window_information(config, devices)["w"] == (
        [actor.entity_id] if case == "same" else []
    )


@pytest.fixture
def window():
    return WindowConfig(
        "living",
        "Wohnzimmer rechts",
        "living",
        contact_entity_id="binary_sensor.contact",
        handle_entity_ids=["binary_sensor.grip_a", "binary_sensor.grip_b"],
        lock_entity_id="lock.handle",
        availability_entity_id="lock.handle",
        mappings=[
            {
                "state": "closed",
                "values": {
                    "binary_sensor.contact": "off",
                    "binary_sensor.grip_a": "off",
                    "binary_sensor.grip_b": "off",
                },
            },
            {
                "state": "unlatched",
                "values": {
                    "binary_sensor.contact": "off",
                    "binary_sensor.grip_a": "on",
                    "binary_sensor.grip_b": "on",
                },
            },
            {
                "state": "open",
                "values": {
                    "binary_sensor.contact": "on",
                    "binary_sensor.grip_a": "on",
                    "binary_sensor.grip_b": "on",
                },
            },
            {
                "state": "tilt_ready",
                "values": {
                    "binary_sensor.contact": "off",
                    "binary_sensor.grip_a": "on",
                    "binary_sensor.grip_b": "off",
                },
            },
            {
                "state": "tilted",
                "values": {
                    "binary_sensor.contact": "on",
                    "binary_sensor.grip_a": "on",
                    "binary_sensor.grip_b": "off",
                },
            },
        ],
    )


def states_for(window, state):
    return next(deepcopy(rule["values"]) for rule in window.mappings if rule["state"] == state) | {
        "lock.handle": "unlocked"
    }


@pytest.mark.parametrize(
    "state,position,opening",
    [
        ("closed", "closed", False),
        ("unlatched", "closed", False),
        ("open", "open", True),
        ("tilt_ready", "closed", False),
        ("tilted", "tilted", True),
    ],
)
def test_calibrated_positions_are_independent_of_lock(window, state, position, opening):
    reading = inspect_window(window, states_for(window, state))
    assert reading["state"] == state and reading["available"]
    assert reading["position"] == position and reading["opening"] is opening
    assert reading["locked"] is False


@pytest.mark.parametrize("missing", ["unknown", "unavailable", None])
def test_lost_lock_never_becomes_an_open_window(window, missing):
    values = states_for(window, "closed") | {"lock.handle": missing}
    reading = inspect_window(window, values)
    assert reading["state"] == "no_connection" and not reading["available"]
    assert reading["opening"] is False
    assert "lock.handle" in reading["faults"]


def test_live_contact_survives_handle_failure(window):
    values = states_for(window, "open") | {"lock.handle": "unavailable"}
    reading = inspect_window(window, values)
    assert reading["state"] == "no_connection"
    assert reading["opening"] is True


def test_missing_contact_is_never_assumed_closed(window):
    values = states_for(window, "closed") | {"binary_sensor.contact": "unavailable"}
    reading = inspect_window(window, values)
    assert reading["state"] == "no_connection" and reading["opening"] is None


def test_unlearned_combination_has_explicit_status(window):
    values = states_for(window, "closed") | {
        "binary_sensor.grip_a": "off",
        "binary_sensor.grip_b": "on",
    }
    reading = inspect_window(window, values)
    assert reading["available"] and reading["state"] == "unknown_position"


def test_unknown_grip_code_allowed_for_handles_and_guarded(window):
    values = states_for(window, "tilted") | {"binary_sensor.grip_b": "unknown"}
    # Handle inputs accept unknown as a valid signal code without failing connection
    assert inspect_window(window, values)["available"] is True
    rule = capture_position(window, values, "tilted")
    window.mappings = [rule]
    assert inspect_window(window, values)["state"] == "tilted"
    assert (
        inspect_window(window, values | {"lock.handle": "unavailable"})["state"] == "no_connection"
    )
    assert (
        inspect_window(window, values | {"binary_sensor.grip_b": "unavailable"})["state"]
        == "no_connection"
    )


def test_capture_rejects_indistinguishable_and_unreachable_states(window):
    with pytest.raises(ValueError, match="nicht unterschieden"):
        capture_position(window, states_for(window, "closed"), "unlatched")
    with pytest.raises(ValueError, match="Keine Verbindung"):
        capture_position(
            window, states_for(window, "closed") | {"lock.handle": "unknown"}, "closed"
        )
    with pytest.raises(ValueError, match="Fensterkontakt"):
        capture_position(window, states_for(window, "closed"), "open")


def test_simple_contact_requires_no_handle(window):
    simple = WindowConfig(
        "simple",
        "Einfaches Fenster",
        "living",
        contact_entity_id="binary_sensor.contact",
        mappings=[],
    )
    simple.mappings = [
        capture_position(simple, {"binary_sensor.contact": "off"}, "closed"),
        capture_position(simple, {"binary_sensor.contact": "on"}, "open"),
    ]
    assert inspect_window(simple, {"binary_sensor.contact": "on"})["state"] == "open"


def test_tracker_stabilizes_without_publishing_every_tick(window):
    tracker = WindowTracker(window)
    tracker.update(states_for(window, "closed"), 100, seed=True)
    assert not tracker.update(states_for(window, "closed"), 101)
    tracker.update(states_for(window, "open"), 102)
    assert tracker.reading["state"] == "settling" and not tracker.reading["opening_stable"]
    tracker.update(states_for(window, "open"), 103.1)
    assert tracker.reading["state"] == "open" and tracker.reading["opening_stable"]
    assert not tracker.update(states_for(window, "open"), 104)
    tracker.update(states_for(window, "open") | {"lock.handle": "unavailable"}, 104.1)
    assert tracker.reading["state"] == "no_connection"
    assert tracker.reading["last_known"]["state"] == "open"


def test_handle_flapping_cannot_starve_a_working_open_contact(window):
    tracker = WindowTracker(window)
    tracker.update(states_for(window, "closed"), 100, seed=True)
    tracker.update(states_for(window, "open"), 101)
    tracker.update(states_for(window, "tilted"), 101.4)
    tracker.update(states_for(window, "open"), 102.1)
    assert tracker.reading["opening_stable"] and tracker.reading["opening"] is True


def test_legacy_window_handles_become_information_only(config):
    for entity_id in ("lock.fenstergriff_links", "binary_sensor.fenstergriff_links_tur"):
        config.sensors[entity_id] = SensorConfig(entity_id, "lock_contact", "living")
    engine = CorrelationEngine(Configuration.from_dict(config.to_dict()))
    for entity_id in engine.sensors:
        engine.seed(entity_id, False)
    engine.set_profile("armed_night", 100)
    for index in range(8):
        for entity_id in ("lock.fenstergriff_links", "binary_sensor.fenstergriff_links_tur"):
            engine.feed(entity_id, index % 2 == 0, 101 + index)
    assert not engine.quarantine and engine.level == 0
    assert not engine.evidence


def test_explicit_door_lock_retains_security_rules(config):
    sensor = SensorConfig("lock.front_door", "lock_contact", "hall", sensor_kind="door_lock")
    config.sensors[sensor.entity_id] = sensor
    engine = CorrelationEngine(config)
    for source in engine.sensors:
        engine.seed(source, False)
    engine.set_profile("armed_night", 100)
    engine.feed(sensor.entity_id, True, 101)
    assert engine.level == 2


def test_window_counts_once_and_groups_do_not_confirm_themselves(config, window):
    config.windows[window.id] = window
    for source in window.position_inputs:
        config.sensors[source] = SensorConfig(source, "entry_contact", "living")
    engine = CorrelationEngine(config)
    for source in engine.sensors:
        engine.seed(source, False)
    engine.set_profile("armed_night", 100)
    for index, source in enumerate(window.position_inputs):
        engine.feed(source, True, 101 + index)
    assert engine.level == 0
    engine.feed(window.sensor_id, True, 105)
    assert engine.level == 2 and len(engine.evidence) == 1
    engine.feed("binary_sensor.motion", True, 117)
    assert engine.level == 3


def test_old_false_handle_alarm_and_quarantine_do_not_survive_classification(config):
    entity_id = "lock.fenstergriff_living"
    config.sensors[entity_id] = SensorConfig(
        entity_id, "lock_contact", "living", sensor_kind="door_lock", immediate=True
    )
    original = CorrelationEngine(config)
    for source in original.sensors:
        original.seed(source, False)
    original.set_profile("armed_away", 100)
    original.feed(entity_id, True, 101)
    saved = original.persistent_state()
    saved["quarantine"] = {entity_id: {"reason": "quarantined_flapping"}}
    migrated = Configuration.from_dict(config.to_dict())
    migrated.sensors[entity_id].sensor_kind = "window_handle"
    restored = CorrelationEngine(migrated)
    restored.seed(entity_id, True)
    restored.restore(saved, 102)
    assert restored.level == 0 and not restored.confirmed and not restored.quarantine


def test_window_roundtrip_and_validation(config, window):
    config.windows[window.id] = window
    assert Configuration.from_dict(config.to_dict()).to_dict() == config.to_dict()
    duplicate = deepcopy(window)
    duplicate.id = "duplicate"
    config.windows[duplicate.id] = duplicate
    with pytest.raises(ValueError, match="nur zu einem"):
        config.validate()


@pytest.mark.parametrize("bad", ["unknown", "unavailable"])
def test_faults_cannot_be_calibrated_as_normal_positions(window, bad):
    data = Configuration(
        rooms={"living": Room("living", "Wohnzimmer")}, windows={"living": window}
    ).to_dict()
    data["windows"]["living"]["mappings"][0]["values"]["binary_sensor.contact"] = bad
    with pytest.raises(ValueError, match="Keine Verbindung"):
        Configuration.from_dict(data)


def test_smart_handle_with_unknown_tilt_code_and_independent_lock():
    """Verify smart handle where tilt reports unknown on tur_kipp, without requiring separate guard or lock."""
    window = WindowConfig(
        id="buro_links",
        name="Fenster Büro Links",
        room_id="living",
        contact_entity_id="binary_sensor.fensterkontakt_arbeitszimmer_tur",
        handle_entity_ids=[
            "binary_sensor.fenstergriff_buro_links_tur_kipp",
            "binary_sensor.fenstergriff_buro_links_tur_offen",
        ],
        lock_entity_id="lock.fenstergriff_buro_links",
    )
    # 1. Closed
    closed_states = {
        "binary_sensor.fensterkontakt_arbeitszimmer_tur": "off",
        "binary_sensor.fenstergriff_buro_links_tur_kipp": "off",
        "binary_sensor.fenstergriff_buro_links_tur_offen": "off",
        "lock.fenstergriff_buro_links": "locked",
    }
    closed_rule = capture_position(window, closed_states, "closed")

    # 2. Open
    open_states = {
        "binary_sensor.fensterkontakt_arbeitszimmer_tur": "on",
        "binary_sensor.fenstergriff_buro_links_tur_kipp": "off",
        "binary_sensor.fenstergriff_buro_links_tur_offen": "on",
        "lock.fenstergriff_buro_links": "unlocked",
    }
    open_rule = capture_position(window, open_states, "open")

    # 3. Tilted (tur_kipp is physically unknown)
    tilted_states = {
        "binary_sensor.fensterkontakt_arbeitszimmer_tur": "on",
        "binary_sensor.fenstergriff_buro_links_tur_kipp": "unknown",
        "binary_sensor.fenstergriff_buro_links_tur_offen": "off",
        "lock.fenstergriff_buro_links": "unlocked",
    }
    tilted_rule = capture_position(window, tilted_states, "tilted")

    window.mappings = [closed_rule, open_rule, tilted_rule]

    # Inspection in tilted state with lock engaged ("Lüften ohne Gefahr")
    reading_tilt_locked = inspect_window(
        window, tilted_states | {"lock.fenstergriff_buro_links": "locked"}
    )
    assert reading_tilt_locked["available"] is True
    assert reading_tilt_locked["state"] == "tilted"
    assert reading_tilt_locked["position"] == "tilted"
    assert reading_tilt_locked["locked"] is True
    assert reading_tilt_locked["opening"] is True

    # If handle disconnects (unavailable), it is flagged as no_connection
    offline_reading = inspect_window(
        window,
        tilted_states | {"binary_sensor.fenstergriff_buro_links_tur_kipp": "unavailable"},
    )
    assert offline_reading["available"] is False
    assert offline_reading["state"] == "no_connection"
    assert "binary_sensor.fenstergriff_buro_links_tur_kipp" in offline_reading["faults"]
