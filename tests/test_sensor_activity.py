"""A binary inner-door contact can provide bounded motion on either real edge."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, SensorConfig
from iqalarm_core.models import Settings as ScenarioSettings
from iqalarm_core.robots import RobotConfig

DOOR = "binary_sensor.inner_door"


def activity_engine(config, initial=False):
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms=deepcopy(config.rooms),
        sensors=deepcopy(config.sensors),
    )
    config.sensors[DOOR] = SensorConfig(
        DOOR, "interior_motion", "living", name="Innentür", activation_mode="change"
    )
    for profile in config.profiles.values():
        profile.entry_seconds = 0
        profile.exit_seconds = 0
    config.settings.block_unavailable_on_arm = False
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, initial if key == DOOR else False)
    engine.set_profile("armed_away", 100)
    engine.drain()
    return engine


@pytest.mark.parametrize("initial", [False, True, None])
def test_current_door_position_is_only_a_baseline(config, initial):
    engine = activity_engine(config, initial)
    assert engine.raw[DOOR] is (None if initial is None else False)
    assert not engine.evidence and not engine.activity_until
    assert not engine.snapshot(100)["rooms"]["living"]["open"]


@pytest.mark.parametrize("initial", [False, True])
def test_either_edge_reports_motion_for_exactly_fifteen_seconds(config, initial):
    engine = activity_engine(config, initial)
    engine.feed(DOOR, not initial, 101)
    assert engine.raw[DOOR] is True
    assert engine.level == 4 and not engine.confirmed
    assert engine.evidence[-1].role == "interior_motion"
    assert DOOR in engine.snapshot(101)["rooms"]["living"]["motion"]
    assert not engine.snapshot(101)["rooms"]["living"]["open"]
    engine.tick(115.999)
    assert engine.raw[DOOR] is True
    assert engine.tick(116) is True
    assert engine.raw[DOOR] is False and DOOR not in engine.last_active
    assert DOOR not in engine.snapshot(116)["rooms"]["living"]["motion"]
    assert engine.tick(117) is False


def test_new_edges_restart_timer_but_identical_notifications_do_not(config):
    engine = activity_engine(config)
    engine.feed(DOOR, True, 101)
    engine.feed(DOOR, True, 110)
    assert engine.activity_until[DOOR] == 116
    engine.feed(DOOR, False, 112)
    assert engine.raw[DOOR] is True and engine.activity_until[DOOR] == 127
    engine.tick(126.999)
    assert engine.raw[DOOR] is True
    engine.tick(127)
    assert engine.raw[DOOR] is False


def test_connection_failure_cancels_activity_and_reconnect_is_not_motion(config):
    engine = activity_engine(config)
    engine.feed(DOOR, True, 101)
    engine.feed(DOOR, None, 102)
    assert engine.raw[DOOR] is None and DOOR not in engine.activity_until
    assert DOOR not in engine.last_active
    signals = len([event for event in engine.events if event.kind == "signal"])
    engine.feed(DOOR, False, 103)
    assert engine.raw[DOOR] is False
    assert signals == len([event for event in engine.events if event.kind == "signal"])
    engine.feed(DOOR, True, 104)
    assert engine.raw[DOOR] is True and engine.activity_until[DOOR] == 119


def test_door_repetition_never_becomes_independent_confirmation(config):
    engine = activity_engine(config)
    for index, value in enumerate([True, False, True, False, True]):
        engine.feed(DOOR, value, 101 + index)
    assert engine.level == 4 and not engine.confirmed
    assert DOOR not in engine.quarantine


def test_real_opening_can_still_correlate_with_the_inner_door_as_motion(config):
    engine = activity_engine(config)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed(DOOR, True, 102)
    assert engine.confirmed and engine.level == 5


def test_robot_exception_also_ignores_contact_based_motion(config):
    engine = activity_engine(config)
    engine.config.robots["bot"] = RobotConfig(
        "bot", "Roboter", [{"entity_id": "vacuum.robot"}], ["living"]
    )
    engine.update_robots({"vacuum.robot": {"state": "cleaning"}}, 101)
    engine.feed(DOOR, True, 102)
    engine.feed("binary_sensor.window", True, 103)
    assert not engine.confirmed
    engine.update_robots({"vacuum.robot": {"state": "docked"}}, 104)
    assert DOOR in engine.robot_waiting
    engine.tick(117)
    assert DOOR not in engine.robot_mask and engine.raw[DOOR] is False


@pytest.mark.parametrize(
    "now,current,active",
    [(110, True, True), (116, True, False), (110, False, False), (110, None, None)],
)
def test_restart_preserves_only_remaining_activity_with_unchanged_available_source(
    config, now, current, active
):
    engine = activity_engine(config)
    engine.feed(DOOR, True, 101)
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, current if key == DOOR else engine.raw[key])
    restored.restore(deepcopy(engine.persistent_state()), now)
    assert restored.raw[DOOR] is active
    if active:
        assert restored.activity_until[DOOR] == 116
        restored.tick(116)
        assert restored.raw[DOOR] is False
    else:
        assert DOOR not in restored.last_active


def test_roundtrip_and_invalid_activation_modes(config):
    engine = activity_engine(config)
    assert (
        Configuration.from_dict(engine.config.to_dict()).sensors[DOOR].activation_mode == "change"
    )
    with pytest.raises(ValueError, match="Zustandswechsel"):
        SensorConfig(DOOR, "entry_contact", "living", activation_mode="change")
    with pytest.raises(ValueError, match="Sensorauswertung"):
        SensorConfig(DOOR, "interior_motion", "living", activation_mode="anything")


@pytest.mark.parametrize("busy_tick", [False, True])
def test_runtime_publishes_pulse_expiry_even_when_level_does_not_change(
    tmp_path, monkeypatch, busy_tick
):
    from safety_support import local_runtime, runtime_module

    clock = [1000.0]
    monkeypatch.setattr(runtime_module, "time", NS(time=lambda: clock[0]))

    async def scenario():
        runtime = local_runtime(tmp_path)
        data = runtime.config.to_dict()
        runtime.hass.states.set(DOOR, "off")
        data["sensors"][DOOR] = {
            "entity_id": DOOR,
            "name": "Innentür",
            "role": "interior_motion",
            "room_id": "r",
            "activation_mode": "change",
        }
        await runtime.update_config(data, runtime.config.revision)
        clock[0] = 1001
        runtime.hass.states.set(DOOR, "on")
        runtime._state_changed(
            NS(data={"entity_id": DOOR, "new_state": runtime.hass.states.get(DOOR)})
        )
        await runtime.hass.drain()
        assert runtime.engine.raw[DOOR] is True
        before = len(runtime.hass.published)
        gate = asyncio.Event()
        if busy_tick:
            runtime.flush_task = asyncio.create_task(gate.wait())
        clock[0] = 1016
        await runtime._tick(None)
        await runtime.hass.drain()
        if busy_tick:
            assert len(runtime.hass.published) == before
            # A pending writer may save the expiry before its UI update was sent.
            await runtime.persist()
            gate.set()
            await runtime.flush_task
            clock[0] += 0.1
            await runtime._tick(None)
            await runtime.hass.drain()
        assert runtime.engine.raw[DOOR] is False
        assert len(runtime.hass.published) > before
        assert DOOR not in runtime.store.state["activity_until"]

    asyncio.run(scenario())
