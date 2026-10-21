"""Startup grace, switch edges and explicitly configured grade actions."""

import asyncio
from copy import deepcopy

import pytest
from iqalarm_core.automatic_detection import AutomaticDetection
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Action, Configuration, Room, SensorConfig, Settings
from safety_support import local_runtime, models


def prepared(delay=60, actions=False):
    config = Configuration(
        settings=Settings(startup_delay_seconds=delay),
        rooms={"r": Room("r", "Flur")},
        automatic_detection=AutomaticDetection(test_mode=False),
        sensors={
            **{
                f"binary_sensor.m{i}": SensorConfig(f"binary_sensor.m{i}", "interior_motion", "r")
                for i in range(3)
            },
            "binary_sensor.door": SensorConfig("binary_sensor.door", "entry_contact", "r"),
            "binary_sensor.flur_input": SensorConfig(
                "binary_sensor.flur_input",
                "interior_motion",
                "r",
                activation_mode="change",
                sensor_kind="light_switch",
            ),
        },
    )
    for profile in config.profiles.values():
        profile.rule_ids = ["single", "motion"]
    if actions:
        config.actions = {
            str(i): Action(
                str(i),
                "3",
                "notify",
                "notify.phone",
                trigger=f"grade_{i}",
                profile_ids=["armed_away"],
            )
            for i in (1, 2, 3)
        }
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_away", 100)
    engine.drain()
    return engine


def pulse(engine, entity, at):
    engine.feed(entity, True, at)
    engine.feed(entity, False, at + 0.1)


def test_new_and_existing_configurations_default_to_sixty_seconds():
    assert Settings().startup_delay_seconds == 60
    config = Configuration().to_dict()
    config["settings"].pop("startup_delay_seconds")
    assert Configuration.from_dict(config).settings.startup_delay_seconds == 60


@pytest.mark.parametrize("value", [-1, 601, True, 1.5])
def test_startup_delay_validation(value):
    with pytest.raises(ValueError):
        Settings(startup_delay_seconds=value)


def test_startup_events_are_not_replayed_or_quarantined():
    engine = prepared()
    assert engine.arming_until == 160
    for at in (101, 104, 107, 110):
        pulse(engine, "binary_sensor.door", at)
        pulse(engine, "binary_sensor.m0", at + 1)
    engine.feed("binary_sensor.flur_input", True, 158)
    engine.tick(159.999)
    assert engine.level == 1 and not engine.evidence and not engine.quarantine
    engine.tick(160)
    assert engine.level == 1 and not engine.evidence
    assert not engine.activity_until and engine.raw["binary_sensor.flur_input"] is False
    pulse(engine, "binary_sensor.m0", 161)
    assert engine.level == 3


def test_current_active_source_is_evaluated_only_after_startup():
    engine = prepared()
    engine.feed("binary_sensor.m0", True, 155)
    assert engine.level == 1
    engine.tick(160)
    assert engine.level == 3
    assert engine.automatic_states["r"]["grade"] == 1


def test_startup_deadline_survives_restart_and_disarming_cancels_it():
    engine = prepared()
    saved = deepcopy(engine.persistent_state())
    restored = CorrelationEngine(Configuration.from_dict(engine.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(saved, 130)
    assert restored.arming_started_at == 100 and restored.arming_until == 160
    restored.set_profile(None, 140)
    restored.tick(170)
    assert restored.arming_until is None and not restored.reactions_enabled


def test_grade_actions_fire_on_rising_crossings_once_and_not_after_restart():
    engine = prepared(0, actions=True)
    for i in range(3):
        pulse(engine, f"binary_sensor.m{i}", 101 + i)
    events = [event for event in engine.drain() if event.kind == "grade_reached"]
    assert [event.confirmation_grade for event in events] == [1, 2, 3]
    pulse(engine, "binary_sensor.m2", 105)
    engine.tick(106)
    assert not [event for event in engine.drain() if event.kind == "grade_reached"]
    restored = CorrelationEngine(Configuration.from_dict(engine.config.to_dict()))
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(deepcopy(engine.persistent_state()), 110)
    assert not [event for event in restored.drain() if event.kind == "grade_reached"]


@pytest.mark.parametrize("state", [True, False])
def test_light_switch_either_edge_counts_as_one_independent_interior_source(state):
    engine = prepared(0)
    engine.seed("binary_sensor.flur_input", not state)
    engine.feed("binary_sensor.flur_input", state, 101)
    assert engine.raw["binary_sensor.flur_input"] is True
    assert engine.automatic_states["r"]["grade"] == 1
    engine.feed("binary_sensor.flur_input", not state, 102)
    assert engine.automatic_states["r"]["grade"] == 1
    engine.tick(117)
    assert engine.raw["binary_sensor.flur_input"] is False


def test_grade_dispatch_is_threshold_and_profile_scoped(tmp_path):
    async def scenario():
        config = models.Configuration(settings=models.Settings(startup_delay_seconds=0))
        config.rooms = {"r": models.Room("r", "Flur")}
        config.sensors = {
            "binary_sensor.motion": models.SensorConfig(
                "binary_sensor.motion", "interior_motion", "r"
            )
        }
        config.actions = {
            "one": models.Action(
                "one", "3", "notify", "notify.phone", trigger="grade_1", profile_ids=["armed_away"]
            ),
            "two": models.Action(
                "two", "3", "notify", "notify.phone", trigger="grade_2", profile_ids=["armed_away"]
            ),
            "night": models.Action(
                "night",
                "3",
                "notify",
                "notify.phone",
                trigger="grade_2",
                profile_ids=["armed_night"],
            ),
            "entry": models.Action(
                "entry", "3", "notify", "notify.phone", profile_ids=["armed_away"]
            ),
        }
        runtime = local_runtime(tmp_path, config)
        runtime.engine.seed("binary_sensor.motion", False)
        runtime.engine.set_profile("armed_away", 100)
        event = models.EventLog(
            101,
            "grade_reached",
            3,
            "active",
            "2/3",
            profile_id="armed_away",
            stage_id="3",
            reactions_enabled=True,
            confirmation_grade=2,
        )
        plan = await runtime.dispatcher.dispatch(event, 0, dry_run=True)
        assert [item["id"] for item in plan] == ["two"]
        runtime.engine.arming_until = 160
        assert await runtime.dispatcher.dispatch(event, 0) == []
        assert not runtime.hass.services.calls

    asyncio.run(scenario())


def test_outdoor_grade_actions_follow_new_person_reports_once():
    engine = prepared(0)
    entity = "binary_sensor.person"
    engine.config.sensors[entity] = SensorConfig(entity, "perimeter_camera", "r")
    engine.sensors[entity] = engine.config.sensors[entity]
    engine.seed(entity, False)
    engine.profile.rule_ids.append("perimeter")
    engine.config.actions = {
        str(i): Action(
            str(i), "2", "notify", "notify.phone", trigger=f"grade_{i}", profile_ids=["armed_away"]
        )
        for i in (1, 2, 3)
    }
    for at in (101, 105, 109):
        pulse(engine, entity, at)
    assert [
        event.confirmation_grade for event in engine.drain() if event.kind == "grade_reached"
    ] == [1, 2, 3]
    engine.tick(110)
    assert not [event for event in engine.drain() if event.kind == "grade_reached"]


def test_baseline_action_can_prepare_the_house_at_start_and_is_not_repeated(tmp_path):
    async def scenario():
        config = models.Configuration(
            settings=models.Settings(startup_delay_seconds=60),
            rooms={"r": models.Room("r", "Flur")},
            sensors={
                "binary_sensor.motion": models.SensorConfig(
                    "binary_sensor.motion", "interior_motion", "r"
                )
            },
        )
        config.actions = {
            "ready": models.Action(
                "ready", "1", "notify", "notify.phone", profile_ids=["armed_away"]
            )
        }
        runtime = local_runtime(tmp_path, config)
        runtime.engine.seed("binary_sensor.motion", False)
        runtime.engine.set_profile("armed_away", 100)
        await runtime.flush()
        await runtime.hass.drain()
        assert [(call[0], call[1]) for call in runtime.hass.services.calls] == [("notify", "phone")]
        runtime.engine.tick(160)
        await runtime.flush()
        await runtime.hass.drain()
        assert [(call[0], call[1]) for call in runtime.hass.services.calls] == [("notify", "phone")]

    asyncio.run(scenario())
