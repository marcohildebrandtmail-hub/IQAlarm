"""Audit regressions execute real business bodies with isolated HA infrastructure."""

import asyncio
import time
from types import SimpleNamespace as NS

import pytest
from safety_support import core, local_runtime, models, runtime_module, windows_module


def test_automatic_grade_decay_is_published_and_saved_without_a_level_change(tmp_path, monkeypatch):
    async def scenario():
        config = models.Configuration(
            rooms={"r": models.Room("r", "Raum")},
            sensors={
                f"binary_sensor.motion_{n}": models.SensorConfig(
                    f"binary_sensor.motion_{n}", "interior_motion", "r"
                )
                for n in (1, 2)
            },
            automatic_detection=models.AutomaticDetection(promote_seconds=300),
        )
        config.profiles["armed_away"].rule_ids = ["single", "motion"]
        runtime = local_runtime(tmp_path, config)
        runtime.engine.set_profile("armed_away", 100)
        runtime.engine.feed("binary_sensor.motion_1", True, 101)
        runtime.engine.feed("binary_sensor.motion_2", True, 102)
        runtime.engine.drain()
        await runtime.persist()
        published = []
        monkeypatch.setattr(
            runtime_module,
            "async_dispatcher_send",
            lambda *_: published.append(runtime.engine.snapshot(162)),
        )
        monkeypatch.setattr(runtime_module, "time", NS(time=lambda: 162))
        await runtime._tick(None)
        await runtime.hass.drain()
        assert runtime.engine.level == 3
        assert published[-1]["rooms"]["r"]["detection"]["current"] == 1
        assert runtime.store.state["automatic_states"]["r"]["grade"] == 1

    asyncio.run(scenario())


def composite(**kwargs):
    return models.WindowConfig(
        "w",
        "Fenster",
        "r",
        handle_entity_ids=["binary_sensor.a", "binary_sensor.b"],
        mappings=[
            {"state": "closed", "values": {"binary_sensor.a": "off", "binary_sensor.b": "off"}},
            {"state": "open", "values": {"binary_sensor.a": "on", "binary_sensor.b": "on"}},
        ],
        **kwargs,
    )


def test_ambiguous_grip_intermediate_keeps_real_opening_edge(tmp_path):
    runtime = local_runtime(tmp_path)
    window = composite()
    runtime.config.windows[window.id] = window
    runtime.engine = core(runtime.config)
    for source in window.members:
        runtime.hass.states.set(source, "off")
    runtime.seed()
    runtime.engine.set_profile("armed_night", 100)
    runtime.hass.states.set("binary_sensor.a", "on")
    runtime._update_windows(101)
    runtime._update_windows(102.1)
    assert runtime.engine.raw[window.sensor_id] is None
    runtime.hass.states.set("binary_sensor.b", "on")
    runtime._update_windows(103)
    runtime._update_windows(104.1)
    runtime.engine.feed("binary_sensor.motion", True, 105)
    assert runtime.engine.confirmed


def test_window_save_invariants_and_enum_contact():
    with pytest.raises(ValueError, match="widerspricht"):
        models.WindowConfig(
            "w",
            "Fenster",
            "r",
            contact_entity_id="binary_sensor.frame",
            mappings=[{"state": "closed", "values": {"binary_sensor.frame": "on"}}],
        )
    window = models.WindowConfig(
        "w",
        "Fenster",
        "r",
        contact_entity_id="sensor.frame",
        contact_open_states=["open", "tilted"],
        contact_closed_states=["closed"],
        mappings=[
            {"state": "closed", "values": {"sensor.frame": "closed"}},
            {"state": "open", "values": {"sensor.frame": "open"}},
        ],
    )
    assert windows_module.inspect_window(window, {"sensor.frame": "open"})["opening"] is True
    assert windows_module.inspect_window(window, {"sensor.frame": "unexpected"})["opening"] is None
    assert (
        windows_module.capture_position(window, {"sensor.frame": "open"}, "open")["state"] == "open"
    )
    window.mappings.pop()
    config = models.Configuration(rooms={"r": models.Room("r", "Raum")}, windows={"w": window})
    with pytest.raises(ValueError, match="Geschlossen und Offen"):
        config.validate()


def test_window_protection_controls_reach_alarm_source():
    window = composite(
        immediate=True, debounce_ms=250, flap_threshold=20, flap_window=30, entry_delay=True
    )
    config = models.Configuration(rooms={"r": models.Room("r", "Raum")}, windows={"w": window})
    sensor = config.all_sensors()[window.sensor_id]
    assert (
        sensor.immediate,
        sensor.debounce_ms,
        sensor.flap_threshold,
        sensor.flap_window,
        sensor.entry_delay,
    ) == (True, 250, 20, 30, True)


def test_real_setup_formats_and_physical_source_identity(tmp_path):
    from iqalarm_core.sensor_discovery import sensor_setup

    runtime = local_runtime(tmp_path)
    for key, value in [("binary_sensor.deadbolt", "on"), ("binary_sensor.deadbolt2", "off")]:
        state = NS(entity_id=key, state=value, attributes={})
        proposed = sensor_setup(state, "physical-lock")
        sensor = models.SensorConfig(
            key, "lock_contact", "r", active_states=proposed["active_states"]
        )
        assert runtime.active_state(sensor, state) is (value == "on")
    for value in (True, 3):
        state = NS(entity_id="camera.outside", state="idle", attributes={"person_detected": value})
        proposed = sensor_setup(state, "camera")
        sensor = models.SensorConfig(
            state.entity_id,
            "perimeter_camera",
            attribute=proposed["attribute"],
            active_states=proposed["active_states"],
            active_above=proposed["active_above"],
        )
        assert runtime.active_state(sensor, state) is True
    assert sensor_setup(NS(entity_id="camera.no_detection", attributes={}))["setup_required"]
    a = sensor_setup(NS(entity_id="binary_sensor.a", attributes={}), "same-pir")
    b = sensor_setup(NS(entity_id="binary_sensor.b", attributes={}), "same-pir")
    assert a["source_id"] == b["source_id"]


def test_multistate_input_select_active_evaluation(tmp_path):
    from iqalarm_core.sensor_discovery import sensor_setup

    runtime = local_runtime(tmp_path)
    state = NS(
        entity_id="input_select.garagentor_zustand",
        state="Geschlossen",
        attributes={
            "options": [
                "wird Geöffnet",
                "wird Geschlossen",
                "Geschlossen",
                "Geöffnet",
                "Lüften",
                "in Bewegung",
            ]
        },
    )
    proposed = sensor_setup(state, "garage-door")
    assert "Geöffnet" in proposed["active_states"]
    assert "Geschlossen" not in proposed["active_states"]

    sensor = models.SensorConfig(
        state.entity_id,
        "entry_contact",
        "garage",
        active_states=["wird Geöffnet", "Geöffnet", "Lüften", "in Bewegung"],
    )

    # 1. Closed -> Inactive (False)
    state.state = "Geschlossen"
    assert runtime.active_state(sensor, state) is False

    # 2. Open -> Active (True)
    state.state = "Geöffnet"
    assert runtime.active_state(sensor, state) is True

    # 3. Ventilating -> Active (True)
    state.state = "Lüften"
    assert runtime.active_state(sensor, state) is True

    # 4. Moving -> Active (True)
    state.state = "in Bewegung"
    assert runtime.active_state(sensor, state) is True

    # 5. Case-insensitive tolerance -> True
    state.state = "geöffnet"
    assert runtime.active_state(sensor, state) is True


def test_alarm_timer_advances_while_maintenance_device_hangs(tmp_path, monkeypatch):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.sensors["binary_sensor.contact"].entry_delay = True
        runtime.config.profiles["armed_night"].entry_seconds = 2
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.feed("binary_sensor.contact", True, 101)
        runtime.engine.feed("binary_sensor.motion", True, 102)
        runtime.engine.drain()
        clock = [103.0]
        monkeypatch.setattr(runtime_module, "time", NS(time=lambda: clock[0]))
        started, release = asyncio.Event(), asyncio.Event()

        async def slow(data):
            started.set()
            await release.wait()

        runtime.hass.services.hooks[("light", "turn_off")] = slow
        runtime.dispatcher.outputs["light.slow"] = {"kind": "light", "until": 0}
        await runtime._tick(None)
        await started.wait()
        clock[0] = 110
        await runtime._tick(None)
        assert runtime.engine.confirmed
        release.set()
        await runtime.hass.drain()

    asyncio.run(scenario())


def test_slow_suspicion_light_does_not_block_siren(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.actions = {
            "quiet": models.Action("quiet", "2", "light", "light.slow"),
            "alarm": models.Action("alarm", "3", "siren", "siren.test"),
        }
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.feed("binary_sensor.contact", True, 101)
        event = next(e for e in runtime.engine.drain() if e.kind == "level_changed")
        started, release, siren = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def slow(data):
            started.set()
            await release.wait()

        async def alarm(data):
            siren.set()

        runtime.hass.services.hooks[("light", "turn_on")] = slow
        runtime.hass.services.hooks[("siren", "turn_on")] = alarm
        lower = asyncio.create_task(runtime.dispatcher.dispatch(event, 0))
        await started.wait()
        runtime.engine.feed("binary_sensor.motion", True, 102)
        event = next(e for e in runtime.engine.drain() if e.kind == "confirmation_changed")
        higher = asyncio.create_task(runtime.dispatcher.dispatch(event, 0))
        await asyncio.wait_for(siren.wait(), 1)
        assert not lower.done()
        release.set()
        await asyncio.gather(lower, higher)

    asyncio.run(scenario())


def test_simulation_cannot_switch_on_after_disarm(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.settings.simulation_enabled = True
        runtime.config.settings.simulation_lights = ["light.test"]
        runtime.engine.set_profile("armed_vacation", 100)
        runtime.hass.states.set("light.test", "off")
        reached, release = asyncio.Event(), asyncio.Event()

        async def persist():
            reached.set()
            await release.wait()

        runtime.persist = persist
        task = asyncio.create_task(runtime.dispatcher.simulate(20))
        await reached.wait()
        runtime.engine.set_profile(None, 101)
        runtime.generation += 1
        release.set()
        await task
        assert not runtime.hass.services.calls

    asyncio.run(scenario())


def test_alarm_owns_simulation_light_until_its_own_deadline(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.hass.states.set("light.test", "on")
        runtime.dispatcher.outputs["light.test"] = {
            "kind": "light",
            "until": time.time() + 10,
            "simulation": True,
        }
        runtime.dispatcher.simulation_outputs.add("light.test")
        await runtime.dispatcher.execute(
            models.Action("alarm", "3", "light", "light.test", duration=300), {}, 0
        )
        runtime.dispatcher.release_simulation()
        await runtime.dispatcher.cleanup()
        assert runtime.hass.states.get("light.test").state == "on"
        assert runtime.dispatcher.outputs["light.test"]["alarm_until"] > time.time()

    asyncio.run(scenario())


def test_secure_transition_stops_alarm_outputs(tmp_path, monkeypatch):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.stages[3].latch = False
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.feed("binary_sensor.contact", True, 101)
        runtime.engine.feed("binary_sensor.motion", True, 102)
        runtime.engine.drain()
        runtime.hass.states.set("siren.test", "on")
        runtime.dispatcher.outputs["siren.test"] = {"kind": "siren", "until": time.time() + 1000}
        monkeypatch.setattr(runtime_module, "time", NS(time=lambda: 163))
        await runtime._tick(None)
        await runtime.hass.drain()
        assert runtime.engine.level == 0
        assert runtime.hass.states.get("siren.test").state == "off"

    asyncio.run(scenario())


def test_restart_resumes_only_live_owned_alarm_outputs(tmp_path):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.feed("binary_sensor.contact", True, 101)
        runtime.engine.feed("binary_sensor.motion", True, 102)
        runtime.engine.drain()
        runtime.dispatcher.outputs["siren.test"] = {
            "kind": "siren",
            "until": time.time() + 1000,
            "alarm_until": time.time() + 1000,
            "data": {"entity_id": "siren.test"},
        }
        runtime.hass.states.set("siren.test", "on")
        await runtime.stop()
        assert runtime.hass.states.get("siren.test").state == "off"
        restored = local_runtime(tmp_path)
        restored.engine.restore(runtime.store.state, 103)
        restored.store.outputs = runtime.store.outputs
        await restored.dispatcher.initialize()
        assert restored.hass.states.get("siren.test").state == "on"
        assert not restored.engine.drain()

    asyncio.run(scenario())
