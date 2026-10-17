"""Night motion gating must not admit historical occupant movement as evidence."""

import pytest
from iqalarm_core.const import Level


def test_night_real_breach_after_twelve_seconds(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.level == Level.SUSPICION
    engine.feed("binary_sensor.motion", True, 113)
    assert engine.level == Level.BREACH
    assert [e.timestamp for e in engine.breach_chain] == [101, 113]


def test_night_bathroom_trip_remains_secure(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.bed_motion", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 103)
    engine.tick(120)
    assert engine.level == Level.SECURE
    assert not engine.evidence
    assert not any(e.kind == "level_changed" for e in engine.events)


def test_occupant_motion_before_window_does_not_confirm(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.motion", True, 101)
    engine.feed("binary_sensor.window", True, 102)
    assert engine.level == Level.SUSPICION


def test_new_motion_edge_after_window_confirms(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.motion", True, 101)
    engine.feed("binary_sensor.window", True, 102)
    engine.feed("binary_sensor.motion", False, 103)
    engine.feed("binary_sensor.motion", True, 104)
    assert engine.level == Level.BREACH


def test_adjacent_hall_motion_confirms_window(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 113)
    assert engine.level == Level.BREACH


def test_non_adjacent_motion_does_not_confirm(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.bed_motion", True, 113)
    assert engine.level == Level.SUSPICION


def test_adjacency_switch_disables_cross_room_confirmation(engine):
    engine.config.profiles["armed_night"].adjacent_rooms = False
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 113)
    assert engine.level == Level.SUSPICION


def test_night_gate_expires_with_suspicion(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.tick(161)
    engine.feed("binary_sensor.motion", True, 162)
    assert engine.level == Level.SECURE


@pytest.mark.parametrize("mode", ["armed_away", "armed_vacation"])
def test_away_two_independent_motion_sensors(mode, engine):
    engine.set_mode(mode, 100)
    engine.feed("binary_sensor.bed_motion", True, 101)
    assert engine.level == Level.SUSPICION
    engine.feed("binary_sensor.hall_motion", True, 103)
    assert engine.level == Level.BREACH


def test_away_motion_before_window_is_valid(engine):
    engine.set_mode("armed_away", 100)
    engine.feed("binary_sensor.motion", True, 101)
    engine.feed("binary_sensor.window", True, 102)
    assert engine.level == Level.BREACH


def test_house_gate_still_respects_confirmation_topology(engine):
    engine.config.profiles["armed_night"].motion_scope = "house"
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.bed_motion", True, 103)
    assert any(e.entity_id == "binary_sensor.bed_motion" for e in engine.evidence)
    assert engine.level == Level.SUSPICION


def test_explicit_motion_override_is_not_suppressed_by_night_gate(engine):
    engine.config.sensors["binary_sensor.bed_motion"].immediate = True
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.bed_motion", True, 101)
    assert engine.level == Level.BREACH
