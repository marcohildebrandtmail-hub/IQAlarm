"""Explicit LVL-0 actions run once after alarm-output cleanup, never from observation."""

import asyncio

import pytest
from safety_support import local_runtime, models, runtime_module


def configuration(delay=0):
    return models.Configuration(
        settings=models.Settings(startup_delay_seconds=delay),
        rooms={"r": models.Room("r", "Flur")},
        sensors={
            "binary_sensor.motion": models.SensorConfig(
                "binary_sensor.motion", "interior_motion", "r"
            )
        },
        actions={
            "green": models.Action(
                "green",
                "0",
                "light",
                "light.indicator",
                color=[0, 255, 0],
                duration=10,
                profile_ids=["armed_away"],
            ),
            "off_notice": models.Action(
                "off_notice",
                "0",
                "notify",
                "notify.phone",
                message="Aus {{profile}}",
                profile_ids=["armed_away"],
            ),
            "other_profile": models.Action(
                "other_profile",
                "0",
                "notify",
                "notify.phone",
                message="Falsches Profil",
                profile_ids=["armed_night"],
            ),
            "disabled": models.Action(
                "disabled", "0", "notify", "notify.phone", enabled=False, profile_ids=["armed_away"]
            ),
            "alarm": models.Action(
                "alarm", "3", "notify", "notify.phone", message="Alarm", profile_ids=["armed_away"]
            ),
        },
    )


@pytest.mark.parametrize("delay", [0, 60])
def test_green_light_runs_once_on_deactivation_with_profile_scope_and_duration(
    tmp_path, monkeypatch, delay
):
    async def run():
        clock = [100.0]
        monkeypatch.setattr(runtime_module.time, "time", lambda: clock[0])
        runtime = local_runtime(tmp_path, configuration(delay))
        runtime.hass.states.set("light.indicator", "off")
        await runtime.set_profile(None)
        assert not runtime.hass.services.calls
        await runtime.set_profile("armed_away")
        await runtime.hass.drain()
        assert not runtime.hass.services.calls
        await runtime.set_profile(None)
        assert runtime.engine.reactions_enabled is False
        assert runtime.hass.states.get("light.indicator").state == "on"
        on = [c for c in runtime.hass.services.calls if c[:2] == ("light", "turn_on")]
        assert len(on) == 1 and on[0][2]["rgb_color"] == [0, 255, 0]
        assert [c[2]["message"] for c in runtime.hass.services.calls if c[0] == "notify"] == [
            "Aus Abwesend"
        ]
        await runtime.set_profile(None)
        runtime.engine.feed("binary_sensor.motion", True, 101)
        await runtime.flush()
        await runtime.hass.drain()
        assert len(runtime.hass.services.calls) == 2
        clock[0] = 105
        await runtime._maintenance()
        assert runtime.hass.states.get("light.indicator").state == "on"
        clock[0] = 110
        await runtime._maintenance()
        assert runtime.hass.states.get("light.indicator").state == "off"
        assert len(runtime.hass.services.calls) == 3

    asyncio.run(run())


def test_alarm_cleanup_precedes_the_green_action_on_the_same_output(tmp_path, monkeypatch):
    async def run():
        monkeypatch.setattr(runtime_module.time, "time", lambda: 100)
        runtime = local_runtime(tmp_path, configuration())
        await runtime.set_profile("armed_away")
        await runtime.hass.drain()
        runtime.hass.states.set("light.indicator", "off")
        await runtime.dispatcher.execute(
            models.Action("red", "4", "light", "light.indicator", color=[255, 0, 0]),
            {},
            runtime.generation,
        )
        await runtime.set_profile(None)
        light_calls = [c for c in runtime.hass.services.calls if c[0] == "light"]
        assert [c[1] for c in light_calls] == ["turn_on", "turn_off", "turn_on"]
        assert light_calls[-1][2]["rgb_color"] == [0, 255, 0]
        assert runtime.dispatcher.outputs["light.indicator"]["until"] == 110

    asyncio.run(run())


def test_an_old_disarm_action_cannot_run_after_rearming(tmp_path):
    async def run():
        runtime = local_runtime(tmp_path, configuration())
        await runtime.set_profile("armed_away")
        await runtime.hass.drain()
        runtime.hass.states.set("light.indicator", "off")
        runtime.dispatcher._claim(
            "light.old_alarm", "light", 9999999999, "alarm", {"entity_id": "light.old_alarm"}
        )
        runtime.hass.states.set("light.old_alarm", "on")
        started, release = asyncio.Event(), asyncio.Event()

        async def turning_off(data):
            if data["entity_id"] == "light.old_alarm":
                started.set()
                await release.wait()

        runtime.hass.services.hooks[("light", "turn_off")] = turning_off
        task = asyncio.create_task(runtime.set_profile(None))
        await asyncio.wait_for(started.wait(), 1)
        await runtime.set_profile("armed_night")
        release.set()
        await asyncio.wait_for(task, 1)
        await runtime.hass.drain()
        assert not [c for c in runtime.hass.services.calls if c[:2] == ("light", "turn_on")]
        assert not [c for c in runtime.hass.services.calls if c[0] == "notify"]

    asyncio.run(run())


def test_ordinary_offline_events_still_cannot_execute_actions(tmp_path):
    async def run():
        runtime = local_runtime(tmp_path, configuration())
        for kind, stage in [
            ("level_changed", "0"),
            ("level_changed", "3"),
            ("grade_reached", "3"),
            ("disarmed", "3"),
        ]:
            event = models.EventLog(
                100,
                kind,
                int(stage),
                "inactive",
                "Beobachtung",
                profile_id="armed_away",
                stage_id=stage,
                reactions_enabled=False,
                confirmation_grade=1,
            )
            assert await runtime.dispatcher.dispatch(event, runtime.generation) == []
        assert not runtime.hass.services.calls

    asyncio.run(run())


def test_observation_expiry_cannot_shorten_the_deactivation_light(tmp_path, monkeypatch):
    async def run():
        clock = [100.0]
        monkeypatch.setattr(runtime_module.time, "time", lambda: clock[0])
        config = configuration()
        config.actions["green"].duration = 600
        config.profiles["observer"] = models.Profile(
            name="Beobachtung", reactions_enabled=False, rule_ids=["perimeter"]
        )
        config.settings.observation_profile_id = "observer"
        config.sensors["binary_sensor.outside"] = models.SensorConfig(
            "binary_sensor.outside", "perimeter_sensor", "r"
        )
        runtime = local_runtime(tmp_path, config)
        runtime.hass.states.set("light.indicator", "off")
        await runtime.set_profile("armed_away")
        await runtime.hass.drain()
        await runtime.set_profile(None)
        runtime.engine.feed("binary_sensor.outside", True, 101)
        runtime.engine.feed("binary_sensor.outside", False, 102)
        assert runtime.engine.stage_id == "2"
        await runtime.flush()
        clock[0] = 400
        runtime.engine.tick(400)
        assert runtime.engine.stage_id == "0"
        await runtime.flush()
        await runtime.hass.drain()
        await runtime._maintenance()
        assert runtime.hass.states.get("light.indicator").state == "on"
        assert runtime.dispatcher.outputs["light.indicator"]["until"] == 700

    asyncio.run(run())


def test_deactivation_action_test_requires_off_state_and_uses_the_selected_profile(tmp_path):
    async def run():
        runtime = local_runtime(tmp_path, configuration())
        runtime.hass.states.set("light.indicator", "off")
        plan = await runtime.test_level("0", profile_id="armed_away")
        assert {p["id"] for p in plan} == {"green", "off_notice"}
        assert not runtime.hass.services.calls
        await runtime.set_profile("armed_away")
        with pytest.raises(ValueError, match="ausgeschalteter Anlage"):
            await runtime.test_level("0", dry_run=False, profile_id="armed_away")
        assert not runtime.hass.services.calls
        await runtime.set_profile(None)
        runtime.hass.services.calls.clear()
        await runtime.test_level("0", dry_run=False)
        assert {c[0] for c in runtime.hass.services.calls} == {"light", "notify"}

    asyncio.run(run())
