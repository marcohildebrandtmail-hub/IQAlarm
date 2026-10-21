"""End-to-end engine semantics for confirmed alarm persistence and escalation."""

from copy import deepcopy

from iqalarm_core.alarm_escalation import AlarmEscalation
from iqalarm_core.automatic_detection import AutomaticDetection
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, Room, SensorConfig
from iqalarm_core.models import Settings as ScenarioSettings


def setup():
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms={"a": Room("a", "A"), "b": Room("b", "B")},
        automatic_detection=AutomaticDetection(test_mode=False),
        alarm_escalation=AlarmEscalation(),
    )
    for i in range(5):
        key = f"binary_sensor.m{i}"
        config.sensors[key] = SensorConfig(key, "interior_motion", "a" if i < 4 else "b")
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_away", 100)
    return engine


def fire(e, i, at):
    e.feed(f"binary_sensor.m{i}", True, at)
    e.feed(f"binary_sensor.m{i}", False, at + 0.01)


def alarm():
    e = setup()
    for i in range(3):
        fire(e, i, 101 + i)
    e.tick(133)
    assert e.level == 4 and e.confirmed
    return e


def test_alarm_survives_quiet_inputs_and_escalates_once():
    e = alarm()
    identity = e.alarm_state["id"]
    e.tick(300)
    assert e.level == 4
    fire(e, 4, 320)
    assert e.alarm_state["deadline"] == 433
    e.tick(432.99)
    assert e.level == 4
    e.tick(433)
    assert e.level == 5 and e.confirmed
    e.tick(900)
    assert e.level == 5 and e.alarm_state["id"] == identity
    assert len([x for x in e.drain() if x.level == 5]) == 1


def test_manual_off_cancels_alarm_and_next_alarm_has_new_id():
    e = alarm()
    identity = e.alarm_state["id"]
    e.set_profile(None, 200)
    e.tick(900)
    assert e.level == 0 and e.alarm_state is None
    e.set_profile("armed_away", 901)
    for i in range(3):
        fire(e, i, 902 + i)
    e.tick(934)
    assert e.level == 4 and e.alarm_state["id"] != identity


def test_restart_keeps_original_deadline_and_catches_up():
    e = alarm()
    saved = deepcopy(e.persistent_state())
    restored = CorrelationEngine(e.config)
    for key in e.sensors:
        restored.seed(key, None)
    restored.restore(saved, 500)
    restored.tick(500)
    assert restored.level == 5 and restored.alarm_state["deadline"] == 433


def test_sensor_rules_cannot_reach_followup_alarm_directly():
    e = setup()
    for i in range(5):
        fire(e, i, 101 + i)
    assert e.level <= 4
    assert e.config.alarm_escalation.delay_seconds == 300
