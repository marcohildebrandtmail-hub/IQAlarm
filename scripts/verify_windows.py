"""Exercise window calibration and generated entities against real Home Assistant."""

import asyncio
from copy import deepcopy

import aiohttp


async def verify_windows(hass, entry, admin_token, user_token, calls):
    runtime = entry.runtime_data
    original = runtime.config.to_dict()
    window = {
        "id": "verified_window",
        "name": "Prüffenster",
        "room_id": "living",
        "contact_entity_id": "binary_sensor.test_frame",
        "handle_entity_ids": ["binary_sensor.test_grip_a", "binary_sensor.test_grip_b"],
        "lock_entity_id": "lock.test_window_handle",
        "availability_entity_id": "lock.test_window_handle",
        "settle_seconds": 0.2,
        "mappings": [],
    }
    for source, value in (
        (window["contact_entity_id"], "off"),
        (window["handle_entity_ids"][0], "off"),
        (window["handle_entity_ids"][1], "off"),
        (window["lock_entity_id"], "locked"),
    ):
        hass.states.async_set(source, value)
    sequence = 0
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": admin_token})
            assert (await ws.receive_json())["type"] == "auth_ok"

            async def request(kind, **data):
                nonlocal sequence
                sequence += 1
                await ws.send_json({"id": sequence, "type": kind, **data})
                return await ws.receive_json()

            await asyncio.sleep(0.25)
            for state, frame, a, b in (
                ("closed", "off", "off", "off"),
                ("unlatched", "off", "on", "on"),
                ("open", "on", "on", "on"),
                ("tilt_ready", "off", "on", "off"),
                ("tilted", "on", "on", "off"),
            ):
                for source, value in zip(
                    [window["contact_entity_id"], *window["handle_entity_ids"]],
                    [frame, a, b],
                    strict=True,
                ):
                    hass.states.async_set(source, value)
                await asyncio.sleep(0.25)
                result = await request("iqalarm/window/capture", window=window, state=state)
                assert result["success"], result
                window["mappings"].append(result["result"]["mapping"])
            assert runtime.config.revision == original["revision"], (
                "Calibration wrote configuration"
            )
            hass.states.async_set(window["lock_entity_id"], "unavailable")
            result = await request("iqalarm/window/capture", window=window, state="tilted")
            assert not result["success"] and "Keine Verbindung" in result["error"]["message"]
            hass.states.async_set(window["lock_entity_id"], "unlocked")
            for source in [window["contact_entity_id"], *window["handle_entity_ids"]]:
                hass.states.async_set(source, "off")
            await asyncio.sleep(0.25)
            data = runtime.config.to_dict()
            data["windows"] = {window["id"]: window}
            data["profiles"]["armed_night"]["action_ids"] = None
            data["actions"]["window_push"] = {
                "id": "window_push",
                "level": "2",
                "kind": "notify",
                "target": "notify.test_phone",
                "message": "{{sensor}} · {{room}}",
            }
            for source in [window["contact_entity_id"], *window["handle_entity_ids"]]:
                data["sensors"][source] = {
                    "entity_id": source,
                    "role": "entry_contact",
                    "room_id": "living",
                }
            data["sensors"]["lock.fenstergriff_pruefung"] = {
                "entity_id": "lock.fenstergriff_pruefung",
                "name": "Fenstergriff Prüfung",
                "role": "lock_contact",
                "room_id": "living",
            }
            hass.states.async_set("lock.fenstergriff_pruefung", "unlocked")
            data["settings"]["block_unavailable_on_arm"] = False
            data["settings"]["block_open_on_arm"] = False
            saved = await request(
                "iqalarm/config/save", config=data, revision=runtime.config.revision
            )
            assert saved["success"], saved
            await hass.async_block_till_done()
            position = next(
                entity_id
                for entity_id in hass.states.async_entity_ids("sensor")
                if hass.states.get(entity_id).attributes.get("room_id") == "living"
                and "inputs" in hass.states.get(entity_id).attributes
            )
            assert hass.states.get(position).state == "closed"
            assert saved["result"]["information"] and runtime.engine.level == 0
            before_states = hass.states.async_entity_ids()
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            runtime = entry.runtime_data
            assert hass.states.get(position).state == "closed"
            assert set(hass.states.async_entity_ids()) == set(before_states)
            hass.states.async_set("binary_sensor.motion", "off")
            await hass.async_block_till_done()
            await runtime.set_mode("armed_night")
            for i in range(6):
                hass.states.async_set(
                    "lock.fenstergriff_pruefung", "locked" if i % 2 else "unlocked"
                )
                hass.states.async_set(window["handle_entity_ids"][0], "on" if i % 2 else "off")
                await asyncio.sleep(0.02)
            assert runtime.engine.level == 0 and not runtime.engine.quarantine
            hass.states.async_set(window["lock_entity_id"], "unavailable")
            await hass.async_block_till_done()
            assert hass.states.get(position).state == "unavailable"
            assert runtime.windows[window["id"]].reading["opening"] is False
            hass.states.async_set(window["contact_entity_id"], "on")
            await asyncio.sleep(0.4)
            assert runtime.engine.level == 2, runtime.snapshot()
            await asyncio.wait_for(runtime.queue.join(), 5)
            assert any(
                domain == "notify" and "Prüffenster" in str(data.get("message", ""))
                for domain, service, data in calls
            )
            hass.states.async_set("binary_sensor.motion", "on")
            await asyncio.sleep(0.2)
            assert runtime.engine.level == 3
            assert len(runtime.engine.breach_chain) == 2
            assert not set(window["handle_entity_ids"]).intersection(
                e.entity_id for e in runtime.engine.breach_chain
            )
            await runtime.set_mode("disarmed", "2468")
            stale = await request("iqalarm/config/save", config=data, revision=0)
            assert not stale["success"]
            restored = deepcopy(original)
            restored["revision"] = runtime.config.revision
            await runtime.update_config(restored, runtime.config.revision)
            await hass.async_block_till_done()
            assert hass.states.get(position) is None
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": user_token})
            await ws.receive_json()
            await ws.send_json({"id": 1, "type": "iqalarm/window/preview", "window": window})
            result = await ws.receive_json()
            assert not result["success"] and result["error"]["code"] == "unauthorized"
    for source in [
        window["contact_entity_id"],
        *window["handle_entity_ids"],
        window["lock_entity_id"],
        "lock.fenstergriff_pruefung",
    ]:
        hass.states.async_remove(source)
    print(
        "PASS window wizard capture, unavailable guards, generated entities/reload, neutral handles, one physical source and real contact fallback",
        flush=True,
    )
