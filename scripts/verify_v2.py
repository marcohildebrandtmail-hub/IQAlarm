"""Real-Core checks for observation permissions, stages and private floorplans."""

import asyncio
from copy import deepcopy
from io import BytesIO

import aiohttp
from PIL import Image


async def verify_v2(hass, entry, admin_token, user_token, calls):
    runtime = entry.runtime_data
    saved = deepcopy(runtime.config.to_dict())
    data = deepcopy(saved)
    data["settings"]["startup_delay_seconds"] = 0
    data["stages"].append(
        {
            "id": "verified",
            "name": "Mein bestätigter Alarm",
            "color": "#cc0011",
            "requires_confirmation": True,
            "allow_loud": True,
            "latch": True,
        }
    )
    for profile in data["profiles"].values():
        profile["stage_targets"]["contact_motion"] = "verified"
    silent = deepcopy(data["profiles"]["armed_away"])
    silent.update(
        name="Nur sehen",
        reactions_enabled=False,
        simulation_enabled=True,
        action_ids=None,
        correlation_seconds=1,
    )
    data["profiles"]["silent"] = silent
    data["settings"]["observation_profile_id"] = "silent"
    data["settings"]["simulation_enabled"] = True
    data["settings"]["simulation_lights"] = ["light.test"]
    data["sensors"]["binary_sensor.person"]["camera_entity_id"] = "camera.test"
    data["actions"]["v2_push"] = {
        "id": "v2_push",
        "level": "verified",
        "kind": "notify",
        "target": "notify.test_phone",
    }
    data["floorplans"]["eg"] = {
        "id": "eg",
        "name": "Erdgeschoss",
        "zones": {"living": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]},
    }
    for entity_id in data["sensors"]:
        hass.states.async_set(entity_id, "off")
    await hass.async_block_till_done()
    await runtime.update_config(data, runtime.config.revision)
    before = len(calls)
    hass.states.async_set("binary_sensor.person", "on")
    hass.states.async_set("binary_sensor.window", "on")
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await asyncio.wait_for(asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 5)
    await runtime.dispatcher.simulate(19)
    assert runtime.engine.confirmed and not runtime.engine.reactions_enabled
    assert len(calls) == before, "Observer executed an action, camera or simulation"
    assert hass.states.get("alarm_control_panel.iqalarm").state == "disarmed"
    assert hass.states.get("binary_sensor.iqalarm_aktiv").state == "off"
    try:
        await runtime.test_level("verified", False, "silent")
    except ValueError:
        assert len(calls) == before
    else:
        raise AssertionError("Observer allowed real action test")
    await asyncio.sleep(1.25)
    assert not runtime.engine.confirmed, "Silent confirmation remained latched"

    # All image routes require an administrator. They never become public assets.
    origin = "http://127.0.0.1:18123"
    url = origin + "/api/iqalarm/floorplans/eg/image"
    admin = {"Authorization": "Bearer " + admin_token}
    user = {"Authorization": "Bearer " + user_token}
    image = BytesIO()
    Image.new("RGB", (320, 200), "white").save(image, "PNG")
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 401
        for method in ("get", "post"):
            async with getattr(session, method)(url, headers=user) as response:
                assert response.status == 403
        revision = runtime.config.revision
        async with session.post(
            url, headers={**admin, "X-IQAlarm-Revision": str(revision)}, data=b"<svg/>"
        ) as response:
            assert response.status == 400
        assert runtime.config.revision == revision
        async with session.post(
            url, headers={**admin, "X-IQAlarm-Revision": str(revision)}, data=image.getvalue()
        ) as response:
            assert response.status == 200, await response.text()
        async with session.get(url, headers=admin) as response:
            assert response.status == 200
            assert response.headers["Cache-Control"] == "private, no-store"
            assert (await response.read()).startswith(b"\x89PNG")
        async with session.post(
            url, headers={**admin, "X-IQAlarm-Revision": str(revision)}, data=image.getvalue()
        ) as response:
            assert response.status == 400, "Stale upload revision accepted"
        jpeg = BytesIO()
        Image.new("RGB", (200, 100), "gray").save(jpeg, "JPEG")
        async with session.post(
            url,
            headers={**admin, "X-IQAlarm-Revision": str(runtime.config.revision)},
            data=jpeg.getvalue(),
        ) as response:
            assert response.status == 200
        assert runtime.config.floorplans["eg"].width == 200
        assert runtime.config.floorplans["eg"].zones["living"][0] == [0.1, 0.1]

    for entity_id in data["sensors"]:
        hass.states.async_set(entity_id, "off")
    await hass.async_block_till_done()
    data = runtime.config.to_dict()
    data["profiles"]["party"] = {
        **data["profiles"]["armed_night"],
        "name": "Mein Schutz",
        "motion_mode": "always",
        "action_ids": ["v2_push"],
    }
    await runtime.update_config(data, runtime.config.revision)
    await runtime.set_profile("party")
    hass.states.async_set("binary_sensor.window", "on")
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await asyncio.wait_for(asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 5)
    assert runtime.engine.level == 4 and runtime.engine.stage_id == "verified"
    assert any(call[:2] == ("notify", "test_phone") for call in calls[before:])
    assert hass.states.get("alarm_control_panel.iqalarm").state == "triggered"
    assert hass.states.get("binary_sensor.iqalarm_aktiv").state == "on"
    await runtime.set_profile(None, "2468")
    for entity_id in data["sensors"]:
        hass.states.async_set(entity_id, "off")
    await hass.async_block_till_done()
    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_arm_away",
        {"entity_id": "alarm_control_panel.iqalarm"},
        blocking=True,
    )
    assert runtime.engine.profile_id == "party", "HA adapter selected another IQAlarm profile"
    await runtime.set_profile(None, "2468")
    assert await hass.config_entries.async_reload(entry.entry_id)
    runtime = entry.runtime_data
    assert runtime.config.floorplans["eg"].width == 200
    await runtime.update_config(saved, runtime.config.revision)
    print(
        "PASS observation without devices/cameras/simulation, dynamic stage actions, generic HA on/off, private PNG/JPEG upload, geometry, revisions and restart",
        flush=True,
    )
