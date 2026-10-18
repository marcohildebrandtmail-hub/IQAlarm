"""Exercise the six-stage defaults and output permissions in a disposable HA Core."""

import asyncio
from copy import deepcopy
from dataclasses import asdict


async def verify_six_stages(hass, entry, calls):
    from custom_components.iqalarm.models import default_stages

    runtime = entry.runtime_data
    await runtime.set_profile(None, "2468")
    original = deepcopy(runtime.config.to_dict())
    frame, motion, person = (
        "binary_sensor.qa_stage_frame",
        "binary_sensor.qa_stage_motion",
        "binary_sensor.qa_stage_person",
    )
    for key in (frame, motion, person):
        hass.states.async_set(key, "off")
    data = deepcopy(original)
    data["stages"] = [asdict(stage) for stage in default_stages()]
    data["secure_stage_id"] = "1"
    data["actions"] = {
        "stage_push": {
            "id": "stage_push",
            "level": "3",
            "kind": "notify",
            "target": "notify.test_phone",
        },
        "stage_siren": {
            "id": "stage_siren",
            "level": "5",
            "kind": "siren",
            "target": "siren.test",
            "duration": 2,
        },
    }
    for profile in data["profiles"].values():
        profile["stage_targets"] = {}
        profile["action_ids"] = []
    data["sensors"].update(
        {
            frame: {"entity_id": frame, "role": "entry_contact", "room_id": "living"},
            motion: {"entity_id": motion, "role": "interior_motion", "room_id": "living"},
            person: {"entity_id": person, "role": "perimeter_camera", "front_of": ["living"]},
        }
    )
    data["profiles"]["six_stage_qa"] = {
        "name": "Sechs Stufen QA",
        "motion_mode": "after_contact",
        "sensor_ids": [frame, motion, person],
        "action_ids": ["stage_push", "stage_siren"],
        "entry_seconds": 0,
    }
    try:
        await runtime.update_config(data, runtime.config.revision)
        await runtime.set_profile("six_stage_qa")
        assert runtime.engine.level == 1 and runtime.engine.secure
        hass.states.async_set(motion, "on")
        await hass.async_block_till_done()
        assert runtime.engine.level == 1
        hass.states.async_set(motion, "off")
        calls.clear()
        hass.states.async_set(frame, "on")
        await hass.async_block_till_done()
        await asyncio.wait_for(
            asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 10
        )
        assert runtime.engine.level == 3 and not runtime.engine.confirmed
        assert any(c[0] == "notify" for c in calls) and not any(c[0] == "siren" for c in calls)
        hass.states.async_set(motion, "on")
        await hass.async_block_till_done()
        await asyncio.wait_for(
            asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 10
        )
        assert runtime.engine.level == 5 and runtime.engine.confirmed
        assert any(c[:2] == ("siren", "turn_on") for c in calls)
        await runtime.set_profile(None, "2468")
        assert runtime.engine.level == 0 and hass.states.get("siren.test").state == "off"
    finally:
        await runtime.set_profile(None, "2468")
        for key in (frame, motion, person):
            hass.states.async_set(key, "off")
        await hass.async_block_till_done()
        await runtime.update_config(original, runtime.config.revision)
    print(
        "PASS six-stage defaults: active 1, silent single 3, confirmed siren 5, inactive 0",
        flush=True,
    )
