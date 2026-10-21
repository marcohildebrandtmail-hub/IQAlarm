"""Robot activity reduces motion coverage, never manufactures intrusion confidence."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.level_rules import LevelRule, RuleCondition
from iqalarm_core.models import Configuration, FloorPlan, SensorConfig
from iqalarm_core.models import Settings as ScenarioSettings
from iqalarm_core.robots import RobotConfig


def robot_config(config, **changes):
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms=deepcopy(config.rooms),
        sensors=deepcopy(config.sensors),
    )
    config.robots["vacuum"] = RobotConfig(
        **(
            {
                "id": "vacuum",
                "name": "Saugroboter",
                "activities": [{"entity_id": "vacuum.robot"}],
                "room_ids": ["living"],
            }
            | changes
        )
    )
    config.validate()
    return config


def frame(value="docked", **extra):
    return {"vacuum.robot": {"state": value, "attributes": {}}} | extra


def robot_engine(config, **changes):
    engine = CorrelationEngine(robot_config(config, **changes))
    for key in engine.sensors:
        engine.seed(key, False)
    engine.update_robots(frame(), 99, seed=True)
    engine.set_profile("armed_night", 100)
    engine.drain()
    return engine


def test_working_robot_stays_at_secure_level_with_risk_but_without_signal(config):
    engine = robot_engine(config)
    engine.update_robots(frame("cleaning"), 101)
    engine.feed("binary_sensor.motion", True, 102)
    status = engine.snapshot(102)
    assert status["level"] == 1 and not status["confirmed"]
    assert status["coverage"]["current"] == 1
    assert status["robot_paused_sensors"] == ["binary_sensor.motion"]
    assert status["raw"]["binary_sensor.motion"] is True
    assert "binary_sensor.motion" not in status["last_active"]
    assert not status["rooms"]["living"]["motion"]
    assert not engine.evidence and not engine.rule_confirmations
    assert all(event.kind != "signal" for event in engine.drain())


def test_three_activity_inputs_use_or_and_count_one_robot_once(config):
    activities = [
        {"entity_id": key, "active_states": ["on"]}
        for key in ("sensor.one", "binary_sensor.two", "switch.three")
    ]
    engine = robot_engine(config, activities=activities, risk_points=2)
    readings = {source["entity_id"]: {"state": "on", "attributes": {}} for source in activities}
    engine.update_robots(readings, 101)
    status = engine.snapshot(101)["coverage"]
    assert status["current"] == 2 and len(status["robots"]) == 1
    readings["sensor.one"]["state"] = "off"
    readings["binary_sensor.two"]["state"] = "off"
    engine.update_robots(readings, 102)
    assert engine.robot_paused == {"binary_sensor.motion"}


def test_robot_risk_caps_at_three_and_excluded_rooms_do_not_increase_it(config):
    engine = robot_engine(config, risk_points=2)
    engine.config.robots["second"] = RobotConfig(
        "second", "Zweiter Roboter", [{"entity_id": "vacuum.second"}], ["living"], risk_points=2
    )
    engine.config.robots["bedroom"] = RobotConfig(
        "bedroom", "Schlafzimmer", [{"entity_id": "vacuum.bedroom"}], ["bed"], risk_points=3
    )
    engine.config.profiles["armed_night"].sensor_ids = ["binary_sensor.motion"]
    engine.config.rules = None
    readings = frame("cleaning", **{"vacuum.second": {"state": "cleaning"}})
    engine.update_robots(readings, 101)
    assert engine.snapshot(101)["coverage"]["current"] == 3
    engine.update_robots(frame("docked", **{"vacuum.bedroom": {"state": "cleaning"}}), 102)
    assert engine.snapshot(102)["coverage"]["current"] == 0
    engine.feed("binary_sensor.bed_motion", True, 103)
    assert not engine.confirmed


def test_disabled_exception_never_masks_a_sensor(config):
    engine = robot_engine(config, enabled=False)
    engine.update_robots(frame("cleaning"), 101)
    assert not engine.robot_mask
    engine.feed("binary_sensor.window", True, 102)
    engine.feed("binary_sensor.motion", True, 103)
    assert engine.confirmed


def test_overlapping_idle_robot_adds_no_risk_during_another_robots_recovery(config):
    engine = robot_engine(config)
    engine.config.robots["second"] = RobotConfig(
        "second", "Zweiter Roboter", [{"entity_id": "vacuum.second"}], ["living"], risk_points=3
    )
    readings = frame("cleaning", **{"vacuum.second": {"state": "docked"}})
    engine.update_robots(readings, 101)
    engine.feed("binary_sensor.motion", True, 102)
    readings["vacuum.robot"]["state"] = "docked"
    engine.update_robots(readings, 103)
    coverage = engine.snapshot(103)["coverage"]
    assert coverage["current"] == 1
    assert coverage["robots"][0]["waiting"]
    assert not coverage["robots"][1]["paused_sensors"]


def test_floor_scope_only_masks_motion_and_keeps_contacts_and_cameras(config):
    config = robot_config(config)
    config.floorplans["eg"] = FloorPlan(
        "eg", "EG", zones={"living": [[0, 0], [1, 0], [1, 1]], "hall": [[0, 0], [0, 1], [1, 1]]}
    )
    config.robots["vacuum"].room_ids = []
    config.robots["vacuum"].floorplan_id = "eg"
    config.validate()
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_night", 100)
    engine.update_robots(frame("cleaning"), 101)
    assert engine.robot_paused == {"binary_sensor.motion", "binary_sensor.hall_motion"}
    engine.feed("binary_sensor.terrace", True, 102)
    engine.feed("binary_sensor.window", True, 103)
    assert engine.confirmed and engine.level == 5


def test_mmwave_is_paused_but_unrelated_rooms_keep_their_motion(config):
    engine = robot_engine(config)
    sensor = SensorConfig("binary_sensor.mmwave", "interior_mmwave", "living")
    engine.config.sensors[sensor.entity_id] = sensor
    engine.sensors[sensor.entity_id] = sensor
    engine.seed(sensor.entity_id, False)
    engine.update_robots(frame("cleaning"), 101)
    assert sensor.entity_id in engine.robot_paused
    assert "binary_sensor.bed_motion" not in engine.robot_paused


def test_robot_end_waits_for_quiet_and_never_replays_previous_motion(config):
    engine = robot_engine(config)
    engine.update_robots(frame("cleaning"), 101)
    engine.feed("binary_sensor.motion", True, 102)
    engine.update_robots(frame("docked"), 103)
    assert engine.robot_waiting == {"binary_sensor.motion"}
    engine.feed("binary_sensor.window", True, 104)
    assert not engine.confirmed
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, engine.raw.get(key))
    restored.update_robots(frame("cleaning"), 109, seed=True)
    restored.restore(deepcopy(engine.persistent_state()), 110)
    assert not restored.rule_confirmations and not restored.confirmed
    engine.feed("binary_sensor.motion", True, 105)
    assert not engine.confirmed
    engine.feed("binary_sensor.motion", False, 106)
    assert not engine.robot_mask and engine.snapshot(106)["coverage"]["current"] == 0
    assert "binary_sensor.motion" not in engine.last_active
    engine.feed("binary_sensor.motion", True, 107)
    assert engine.confirmed


def test_unknown_activity_never_opens_a_new_exception(config):
    engine = robot_engine(config)
    engine.update_robots(frame("unavailable"), 101)
    assert not engine.robot_mask
    assert engine.snapshot(101)["coverage"]["robots"][0]["fault"]
    assert engine.snapshot(101)["coverage"]["current"] == 0
    engine.feed("binary_sensor.window", True, 102)
    engine.feed("binary_sensor.motion", True, 103)
    assert engine.confirmed


def test_lost_robot_connection_waits_for_quiet_instead_of_replaying_motion(config):
    engine = robot_engine(config)
    engine.update_robots(frame("cleaning"), 101)
    engine.feed("binary_sensor.motion", True, 102)
    engine.update_robots({}, 103)
    assert engine.robot_waiting == {"binary_sensor.motion"}
    assert engine.snapshot(103)["coverage"]["robots"][0]["fault"]
    assert not engine.confirmed


def test_robot_cannot_provide_flap_corroboration(config):
    engine = robot_engine(config, room_ids=["hall"])
    engine.update_robots(frame("cleaning"), 101)
    engine.feed("binary_sensor.hall_motion", True, 102)
    for index, value in enumerate((True, False, True, False, True)):
        engine.feed("binary_sensor.lock", value, 103 + index)
    assert "binary_sensor.lock" in engine.quarantine
    assert not engine.confirmed


def test_held_real_alarm_survives_robot_activity_and_restart(config):
    engine = robot_engine(config)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.confirmed and engine.latched
    engine.update_robots(frame("cleaning"), 103)
    assert engine.confirmed and engine.latched
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, engine.raw.get(key))
    restored.update_robots(frame("cleaning"), 109, seed=True)
    restored.restore(deepcopy(engine.persistent_state()), 110)
    assert restored.confirmed and restored.latched


def test_waiting_state_survives_restart_with_current_robot_inactive(config):
    engine = robot_engine(config)
    engine.update_robots(frame("cleaning"), 101)
    engine.feed("binary_sensor.motion", True, 102)
    engine.update_robots(frame(), 103)
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, engine.raw.get(key))
    restored.update_robots(frame(), 109, seed=True)
    restored.restore(deepcopy(engine.persistent_state()), 110)
    assert restored.robot_waiting == {"binary_sensor.motion"}
    restored.feed("binary_sensor.window", True, 111)
    assert not restored.confirmed


def test_pausing_invalidates_prior_motion_confirmation_memory(config):
    engine = robot_engine(config)
    engine.config.rules = {
        "proof": LevelRule(
            "proof",
            "Vorfeld und Bewegung",
            "2",
            [
                RuleCondition(sensor_ids=["binary_sensor.terrace"]),
                RuleCondition(sensor_ids=["binary_sensor.motion"]),
            ],
            confirmation_target=2,
        ),
        "breach": LevelRule(
            "breach",
            "Vorfeld plus neue Öffnung",
            "5",
            [RuleCondition(sensor_ids=["binary_sensor.window"])],
            prerequisite_rule_id="proof",
        ),
    }
    for profile in engine.config.profiles.values():
        profile.rule_ids = ["proof", "breach"]
    engine.config.validate()
    engine.feed("binary_sensor.terrace", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.rule_confirmations
    engine.update_robots(frame("cleaning"), 103)
    assert not engine.rule_confirmations
    engine.feed("binary_sensor.window", True, 104)
    assert not engine.confirmed
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, engine.raw.get(key))
    restored.update_robots(frame("cleaning"), 109, seed=True)
    restored.restore(deepcopy(engine.persistent_state()), 110)
    assert not restored.rule_confirmations and not restored.confirmed


def test_activity_attribute_and_configuration_roundtrip(config):
    config = robot_config(
        config,
        activities=[
            {"entity_id": "vacuum.robot", "attribute": "working", "active_states": ["true"]}
        ],
    )
    restored = Configuration.from_dict(config.to_dict())
    assert restored.to_dict() == config.to_dict()
    engine = CorrelationEngine(restored)
    engine.update_robots({"vacuum.robot": {"state": "idle", "attributes": {"working": True}}}, 100)
    assert engine.robot_paused == {"binary_sensor.motion"}


@pytest.mark.parametrize(
    "changes",
    [
        {"activities": []},
        {"activities": [{"entity_id": f"sensor.{i}"} for i in range(4)]},
        {"activities": [{"entity_id": "vacuum.robot"}, {"entity_id": "vacuum.robot"}]},
        {"activities": [{"entity_id": "vacuum.robot", "active_states": ["unavailable"]}]},
        {"risk_points": 4},
        {"risk_points": True},
        {"room_ids": []},
        {"floorplan_id": "eg"},
        {"room_ids": ["missing"]},
        {"activities": [{"entity_id": "binary_sensor.motion"}]},
    ],
)
def test_invalid_robot_configuration_is_rejected(config, changes):
    with pytest.raises(ValueError):
        robot_config(config, **changes)


def test_real_runtime_updates_robot_sources_and_persists_suppression_on_save(tmp_path):
    from safety_support import local_runtime

    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.hass.states.set("vacuum.robot", "cleaning")
        data = runtime.config.to_dict()
        data["robots"] = {
            "bot": {
                "id": "bot",
                "name": "Testrobot",
                "activities": [{"entity_id": "vacuum.robot"}],
                "room_ids": ["r"],
            }
        }
        await runtime.update_config(data, runtime.config.revision)
        assert runtime.engine.robot_paused == {"binary_sensor.motion", "binary_sensor.motion2"}
        assert runtime.store.state["robot_suppressed"]
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.drain()
        runtime.hass.states.set("binary_sensor.motion", "on")
        runtime._state_changed(
            NS(
                data={
                    "entity_id": "binary_sensor.motion",
                    "new_state": runtime.hass.states.get("binary_sensor.motion"),
                }
            )
        )
        await runtime.hass.drain()
        assert not runtime.queue.qsize() and not runtime.hass.services.calls
        runtime.hass.states.set("vacuum.robot", "docked")
        runtime._state_changed(
            NS(
                data={
                    "entity_id": "vacuum.robot",
                    "new_state": runtime.hass.states.get("vacuum.robot"),
                }
            )
        )
        await runtime.hass.drain()
        assert runtime.engine.robot_waiting == {"binary_sensor.motion"}
        assert runtime.store.state["robot_suppressed"] == ["binary_sensor.motion"]

    asyncio.run(scenario())
