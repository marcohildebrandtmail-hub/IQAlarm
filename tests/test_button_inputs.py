"""Physical switch inputs; actuator output states must never confirm intrusion."""

import asyncio
import sys
from copy import deepcopy
from datetime import UTC, datetime
from types import ModuleType
from types import SimpleNamespace as NS

import pytest
from iqalarm_core.button_inputs import device_source_id, mqtt_button_sources, press_types
from iqalarm_core.sensor_discovery import classify_entity, sensor_setup
from safety_support import local_runtime, models, runtime_module

HUE = "event.hue_wall_switch_module_14_button_1"
INPUT = "binary_sensor.licht_flur_og_input_0_input"
DEVICE = "bd3c8cf65bec9038a01fe8a92b811feb"
MQTT = device_source_id(DEVICE, "single_left")
TRIGGER = {
    "platform": "device",
    "domain": "mqtt",
    "device_id": DEVICE,
    "type": "action",
    "subtype": "single_left",
}
HUE_TYPES = ["initial_press", "repeat", "short_release", "long_press", "long_release"]


def configuration(delay=0):
    config = models.Configuration(
        settings=models.Settings(startup_delay_seconds=delay),
        automatic_detection=models.AutomaticDetection(test_mode=False),
        rooms={"r": models.Room("r", "Flur")},
        sensors={
            HUE: models.SensorConfig(
                HUE,
                "interior_motion",
                "r",
                sensor_kind="light_switch",
                activation_mode="press",
                active_states=["initial_press"],
            ),
            INPUT: models.SensorConfig(
                INPUT, "interior_motion", "r", sensor_kind="light_switch", activation_mode="change"
            ),
            MQTT: models.SensorConfig(
                MQTT,
                "interior_motion",
                "r",
                sensor_kind="light_switch",
                activation_mode="press",
                active_states=["single_left"],
                device_trigger=deepcopy(TRIGGER),
            ),
        },
    )
    for profile in config.profiles.values():
        profile.rule_ids = ["single", "motion"]
    return config


def event_state(at, kind="initial_press", **extra):
    return NS(
        entity_id=HUE,
        state=datetime.fromtimestamp(at, UTC).isoformat(),
        attributes={"event_type": kind, "event_types": HUE_TYPES, **extra},
    )


@pytest.mark.parametrize(
    ("available", "expected"),
    [
        (HUE_TYPES, ["initial_press"]),
        (["btn_down", "btn_up", "single_push", "double_push", "long_push"], ["btn_down"]),
        (
            ["press_short", "press_long_start", "press_long", "press_long_stop"],
            ["press_short", "press_long_start"],
        ),
        (["single_left", "release_left_down", "hold_left_down"], ["single_left"]),
        (["KeyPressed", "KeyReleased", "KeyHeldDown"], ["KeyPressed"]),
        (["clock_wise", "counter_clock_wise"], []),
    ],
)
def test_only_press_notifications_are_proposed(available, expected):
    assert press_types(available) == expected


def test_discovery_recognizes_examples_and_excludes_actuator_states():
    assert classify_entity(INPUT, "Licht Flur OG Input 0 input", "power") == "interior_motion"
    assert sensor_setup(NS(entity_id=INPUT, attributes={})) == {
        "source_id": INPUT,
        "attribute": None,
        "active_states": ["on"],
        "active_above": None,
        "setup_required": False,
        "setup_reason": "",
        "sensor_kind": "light_switch",
        "activation_mode": "change",
    }
    setup = sensor_setup(event_state(90), "physical-hue")
    assert setup["sensor_kind"] == "light_switch" and setup["activation_mode"] == "press"
    assert (
        setup["active_states"] == ["initial_press"] and setup["source_id"] == "device:physical-hue"
    )
    for domain in ("light", "switch"):
        assert classify_entity(f"{domain}.bewegung_flur", "Lichtschalter Tür", None) is None
        with pytest.raises(ValueError, match="Lichtzustände"):
            models.SensorConfig(
                f"{domain}.flur",
                "interior_motion",
                "r",
                sensor_kind="light_switch",
                activation_mode="change",
            )


def test_legacy_output_assignments_are_disabled_but_output_actions_are_preserved():
    data = configuration().to_dict()
    data["sensors"]["light.flur"] = {
        "entity_id": "light.flur",
        "role": "interior_motion",
        "room_id": "r",
        "sensor_kind": "light_switch",
        "activation_mode": "change",
    }
    data["actions"]["light"] = {
        "id": "light",
        "level": "3",
        "kind": "light",
        "target": "light.flur",
        "profile_ids": ["armed_away"],
    }
    loaded = models.Configuration.from_dict(data)
    assert loaded.sensors["light.flur"].enabled is False
    assert loaded.actions["light"].enabled and loaded.actions["light"].target == "light.flur"


def test_hue_initial_press_counts_once_release_repeat_and_stale_states_do_not(
    tmp_path, monkeypatch
):
    async def run():
        clock = [100.0]
        monkeypatch.setattr(runtime_module.time, "time", lambda: clock[0])
        instance = local_runtime(tmp_path, configuration())
        instance.hass.states.values[HUE] = event_state(90)
        instance.seed()
        instance.engine.set_profile("armed_away", 100)
        assert instance.engine.level == 1

        async def emit(state, at):
            clock[0] = at
            instance.hass.states.values[HUE] = state
            instance._state_changed(NS(data={"entity_id": HUE, "new_state": state}))
            await instance.hass.drain()

        await emit(event_state(101), 101)
        assert instance.engine.automatic_states["r"]["grade"] == 1
        assert instance.engine.activity_until[HUE] == 116
        for state, at in [
            (event_state(101, friendly_name="renamed"), 102),
            (event_state(102, "repeat"), 103),
            (event_state(103, "short_release"), 104),
            (event_state(104, "long_press"), 105),
            (event_state(105, "long_release"), 106),
            (event_state(99), 107),
        ]:
            await emit(state, at)
            assert instance.engine.activity_until[HUE] == 116
        await emit(event_state(108), 108)
        assert instance.engine.activity_until[HUE] == 123
        assert instance.engine.automatic_states["r"]["grade"] == 1
        instance.engine.tick(123)
        assert instance.engine.raw[HUE] is False
        # Reinitialization never turns the event's last timestamp into a new press.
        clock[0] = 130
        instance.seed()
        await emit(event_state(108), 131)
        assert instance.engine.raw[HUE] is False

    asyncio.run(run())


def test_initial_binary_input_and_unknown_event_are_quiet_but_real_edge_counts(tmp_path):
    instance = local_runtime(tmp_path, configuration())
    instance.hass.states.set(HUE, "unknown", {"event_types": HUE_TYPES})
    instance.hass.states.set(INPUT, "on")
    instance.seed()
    assert instance.engine.raw[HUE] is False and instance.engine.raw[INPUT] is False
    assert instance.active_state(instance.config.sensors[HUE], NS(state="unavailable")) is None
    instance.engine.set_profile("armed_away", 100)
    instance.engine.feed(INPUT, False, 101)
    assert instance.engine.automatic_states["r"]["grade"] == 1
    instance.engine.feed(INPUT, True, 102)
    assert instance.engine.automatic_states["r"]["grade"] == 1
    assert instance.engine.activity_until[INPUT] == 117


def test_presses_during_startup_are_discarded(tmp_path):
    instance = local_runtime(tmp_path, configuration(60))
    instance.engine.set_profile("armed_away", 100)
    instance.engine.feed_press(HUE, 159)
    instance.engine.tick(160)
    assert instance.engine.level == 1 and not instance.engine.evidence
    assert instance.engine.raw[HUE] is False
    instance.engine.feed_press(HUE, 161)
    assert instance.engine.automatic_states["r"]["grade"] == 1


def test_two_buttons_on_one_device_remain_one_independent_source(tmp_path):
    config = configuration()
    second = device_source_id(DEVICE, "single_right")
    config.sensors[second] = models.SensorConfig(
        second,
        "interior_motion",
        "r",
        sensor_kind="light_switch",
        activation_mode="press",
        device_trigger={**TRIGGER, "subtype": "single_right"},
        active_states=["single_right"],
    )
    instance = local_runtime(tmp_path, config)
    instance.engine.set_profile("armed_away", 100)
    instance.engine.feed_press(MQTT, 101)
    instance.engine.feed_press(second, 102)
    assert instance.engine.automatic_states["r"]["grade"] == 1
    instance.engine.feed_press(HUE, 103)
    assert instance.engine.automatic_states["r"]["grade"] == 2


def test_robot_exception_does_not_hide_physical_switches(tmp_path):
    config = configuration()
    config.robots["vacuum"] = models.RobotConfig(
        "vacuum",
        "Roboter",
        [{"entity_id": "vacuum.robot"}],
        room_ids=["r"],
    )
    instance = local_runtime(tmp_path, config)
    instance.engine.update_robots({"vacuum.robot": {"state": "cleaning", "attributes": {}}}, 99)
    assert not instance.engine.robot_mask
    instance.engine.set_profile("armed_away", 100)
    instance.engine.feed_press(HUE, 101)
    assert instance.engine.automatic_states["r"]["grade"] == 1


def test_lamp_and_relay_state_events_cannot_add_confirmation(tmp_path, monkeypatch):
    async def run():
        monkeypatch.setattr(runtime_module.time, "time", lambda: 101)
        instance = local_runtime(tmp_path, configuration())
        instance.engine.set_profile("armed_away", 100)
        instance.engine.feed_press(HUE, 101)
        for entity in ("light.flur", "switch.flur"):
            for value in ("on", "off"):
                instance._state_changed(
                    NS(data={"entity_id": entity, "new_state": NS(state=value, attributes={})})
                )
        await instance.hass.drain()
        instance.engine.tick(132)
        assert instance.engine.level == 3
        assert instance.engine.automatic_states["r"]["grade"] == 1
        assert {e.entity_id for e in instance.engine.evidence} == {HUE}

    asyncio.run(run())


def fake_module(monkeypatch, name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def test_mqtt_device_trigger_uses_action_callback_and_unsubscribes(tmp_path, monkeypatch):
    async def run():
        attached, canceled = [], []

        async def validate(hass, config):
            assert config == TRIGGER
            return config

        async def attach(hass, config, action, info):
            assert config == TRIGGER and info["trigger_data"]["id"] == MQTT
            attached.append(action)
            return lambda: canceled.append(True)

        platform = fake_module(
            monkeypatch,
            "homeassistant.components.device_automation.trigger",
            async_validate_trigger_config=validate,
            async_attach_trigger=attach,
        )
        fake_module(monkeypatch, "homeassistant.components.device_automation", trigger=platform)
        monkeypatch.setattr(runtime_module.time, "time", lambda: 101)
        instance = local_runtime(tmp_path, configuration())
        instance.engine.set_profile("armed_away", 100)
        await instance._attach_button_triggers()
        # No HA state entity exists for this device automation.
        assert instance.active_state(instance.config.sensors[MQTT], None) is False
        instance._state_changed(NS(data={"entity_id": MQTT, "new_state": event_state(101)}))
        assert instance.engine.level == 1
        await attached[0]({"trigger": {"id": MQTT}})
        assert instance.engine.automatic_states["r"]["grade"] == 1
        assert instance.config.sensors[MQTT].source_id == f"device:{DEVICE}"
        instance.config.sensors[MQTT].enabled = False
        await instance._attach_button_triggers()
        assert canceled == [True] and len(attached) == 1
        instance.engine.tick(116)
        await attached[0]({})
        assert instance.engine.raw[MQTT] is False

    asyncio.run(run())


def test_mqtt_catalog_lists_press_actions_only_and_keeps_stable_identity(monkeypatch):
    async def run():
        device = NS(
            id=DEVICE,
            name_by_user="Flur Taster",
            name="Switch",
            area_id="flur",
            identifiers={("mqtt", "test")},
        )
        registry = NS(async_get=lambda hass: NS(devices={DEVICE: device}))
        fake_module(monkeypatch, "homeassistant.helpers", device_registry=registry)

        async def get_triggers(hass, device_id):
            assert device_id == DEVICE
            return [
                {**TRIGGER, "subtype": subtype}
                for subtype in ("single_left", "hold_left_down", "release_left_down")
            ] + [{"type": "turned_on"}]

        fake_module(
            monkeypatch,
            "homeassistant.components.mqtt.device_trigger",
            async_get_triggers=get_triggers,
        )
        assert await mqtt_button_sources(NS(data={})) == []
        sources = await mqtt_button_sources(NS(data={"mqtt": object()}))
        assert len(sources) == 1
        assert sources[0]["entity_id"] == MQTT and sources[0]["device_trigger"] == TRIGGER
        assert sources[0]["source_id"] == f"device:{DEVICE}"
        loaded = models.Configuration.from_dict(configuration().to_dict())
        assert loaded.sensors[MQTT].device_trigger == TRIGGER
        with pytest.raises(ValueError, match="MQTT"):
            models.SensorConfig(
                MQTT,
                "interior_motion",
                "r",
                sensor_kind="light_switch",
                activation_mode="press",
                device_trigger={**TRIGGER, "subtype": "release_left_down"},
            )

    asyncio.run(run())
