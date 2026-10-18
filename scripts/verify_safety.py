"""Real-Core regression checks for spatial policy, independent devices and timers."""

import asyncio
from copy import deepcopy

from homeassistant.helpers.dispatcher import async_dispatcher_connect


async def verify_safety(hass, entry, calls, capture):
    runtime = entry.runtime_data
    original = deepcopy(runtime.config.to_dict())
    await runtime.set_profile(None, "2468")
    source, motion = "binary_sensor.qa_safety_frame", "binary_sensor.qa_safety_motion"
    for key in (source, motion, "light.qa_safety", "light.qa_blocked", "siren.qa_safety"):
        hass.states.async_set(key, "off")
    data = deepcopy(original)
    data["sensors"][source] = {"entity_id": source, "role": "entry_contact", "room_id": "living"}
    data["sensors"][motion] = {"entity_id": motion, "role": "interior_motion", "room_id": "living"}
    data["profiles"]["qa_safety"] = {
        "name": "QA Safety",
        "motion_mode": "after_contact",
        "sensor_ids": [source, motion],
        "action_ids": ["qa_safety_light", "qa_safety_siren"],
        "entry_seconds": 0,
    }
    data["actions"]["qa_safety_light"] = {
        "id": "qa_safety_light",
        "level": "2",
        "kind": "light",
        "target": "light.qa_safety",
        "duration": 60,
    }
    data["actions"]["qa_safety_siren"] = {
        "id": "qa_safety_siren",
        "level": data["stages"][-1]["id"],
        "kind": "siren",
        "target": "siren.qa_safety",
        "duration": 60,
    }
    light_started, light_release = asyncio.Event(), asyncio.Event()
    stop_started, stop_release = asyncio.Event(), asyncio.Event()

    async def slow_light(call):
        if call.data.get("entity_id") == "light.qa_safety":
            light_started.set()
            await light_release.wait()
        await capture(call)

    async def slow_stop(call):
        if call.data.get("entity_id") == "light.qa_blocked":
            stop_started.set()
            await stop_release.wait()
        await capture(call)

    async def wait_for(predicate, seconds=5):
        changed = asyncio.Event()
        cancel = hass.bus.async_listen("state_changed", lambda event: changed.set())
        cancel_update = async_dispatcher_connect(hass, "iqalarm_update", changed.set)
        try:
            async with asyncio.timeout(seconds):
                while not predicate():
                    await changed.wait()
                    changed.clear()
        finally:
            cancel()
            cancel_update()

    try:
        await runtime.update_config(data, runtime.config.revision)
        hass.services.async_register("light", "turn_on", slow_light)
        await runtime.set_profile("qa_safety")
        hass.states.async_set(source, "on")
        await asyncio.wait_for(light_started.wait(), 5)
        hass.states.async_set(motion, "on")
        await wait_for(lambda: hass.states.get("siren.qa_safety").state == "on", 2)
        assert not light_release.is_set(), "Siren waited for unrelated suspicion light"
        light_release.set()
        await asyncio.wait_for(asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 5)
        await hass.config_entries.async_reload(entry.entry_id)
        runtime = entry.runtime_data
        assert runtime.engine.confirmed and hass.states.get("siren.qa_safety").state == "on"
        await runtime.set_profile(None, "2468")
        for key in (source, motion):
            hass.states.async_set(key, "off")
        await hass.async_block_till_done()
        data = runtime.config.to_dict()
        data["sensors"][source]["entry_delay"] = True
        data["profiles"]["qa_safety"]["entry_seconds"] = 0.35
        await runtime.update_config(data, runtime.config.revision)
        await runtime.set_profile("qa_safety")
        hass.services.async_register("light", "turn_off", slow_stop)
        runtime.dispatcher.outputs["light.qa_blocked"] = {"kind": "light", "until": 0}
        await asyncio.wait_for(stop_started.wait(), 5)
        hass.states.async_set(source, "on")
        await wait_for(lambda: runtime.engine.level == 2)
        hass.states.async_set(motion, "on")
        await wait_for(lambda: runtime.engine.pending_until is not None)
        await wait_for(lambda: runtime.engine.confirmed, 2)
        assert not stop_release.is_set(), "Entry timer waited for device shutdown"
        stop_release.set()
        await asyncio.wait_for(asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 5)
    finally:
        light_release.set()
        stop_release.set()
        hass.services.async_register("light", "turn_on", capture)
        hass.services.async_register("light", "turn_off", capture)
        runtime = entry.runtime_data
        await runtime.set_profile(None, "2468")
        await runtime.update_config(original, runtime.config.revision)
    print(
        "PASS real-Core slow-light isolation, urgent siren, bounded alarm-output resumption and independent entry timers",
        flush=True,
    )
