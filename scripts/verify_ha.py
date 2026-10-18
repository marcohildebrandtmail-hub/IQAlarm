"""Boot real HA Core and verify config flow, entities, services, storage and WS.

Run inside the official HA image with this repository mounted at /work:
docker run --rm --entrypoint python -v REPO:/work -w /work \
    ghcr.io/home-assistant/home-assistant:2026.10.2 scripts/verify_ha.py
"""

import argparse
import asyncio
import json
import logging
import shutil
import tempfile
import time
from pathlib import Path

import aiohttp
from aiohttp import web
from homeassistant import bootstrap, loader
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_USER
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry

logging.basicConfig(level=logging.WARNING)
ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Serve the local browser test harness after verification",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="iqalarm-ha-") as directory:
        target = Path(directory)
        shutil.copytree(
            ROOT / "custom_components",
            target / "custom_components",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        hass = HomeAssistant(str(target))
        loader.async_setup(hass)
        config = {
            "homeassistant": {
                "name": "IQAlarm verification",
                "latitude": 52.52,
                "longitude": 13.405,
                "elevation": 35,
                "unit_system": "metric",
                "time_zone": "Europe/Berlin",
                "country": "DE",
            },
            "http": {"server_host": "0.0.0.0" if args.serve else "127.0.0.1", "server_port": 18123},
            "frontend": {},
            "websocket_api": {},
        }
        result = await bootstrap.async_from_config_dict(config, hass)
        assert result is hass, "HA bootstrap failed"
        await hass.async_start()
        try:
            token = await verify(hass, target)
            if args.serve:

                class TestPanelView(HomeAssistantView):
                    url = "/iqalarm-test"
                    name = "iqalarm_test:panel"
                    requires_auth = False

                    async def get(self, request):
                        html = await hass.async_add_executor_job(
                            (ROOT / "tests" / "panel_harness.html").read_text
                        )
                        return web.Response(text=html, content_type="text/html")

                class TestSessionView(HomeAssistantView):
                    url = "/iqalarm-test/session"
                    name = "iqalarm_test:session"
                    requires_auth = False

                    async def get(self, request):
                        return web.json_response(
                            {"token": token}, headers={"Cache-Control": "no-store"}
                        )

                hass.http.register_view(TestPanelView())
                hass.http.register_view(TestSessionView())
                print("BROWSER HARNESS READY (bind Docker port to 127.0.0.1 only)", flush=True)
                await asyncio.Event().wait()
        finally:
            await hass.async_stop()


async def verify(hass, target) -> str:
    flow = await hass.config_entries.flow.async_init("iqalarm", context={"source": "user"})
    assert flow["type"] == "form", flow
    invalid = await hass.config_entries.flow.async_configure(flow["flow_id"], {"pin": "abc"})
    assert invalid["errors"]["pin"] == "invalid_pin"
    created = await hass.config_entries.flow.async_configure(flow["flow_id"], {"pin": "2468"})
    assert created["type"] == "create_entry", created
    entry = created["result"]
    await hass.async_block_till_done()
    assert entry.state.value == "loaded", (entry.state, entry.reason)
    runtime = entry.runtime_data
    assert hass.states.get("alarm_control_panel.iqalarm") is not None, list(
        hass.states.async_entity_ids()
    )
    assert "iqalarm" in hass.data["frontend_panels"]
    duplicate = await hass.config_entries.flow.async_init("iqalarm", context={"source": "user"})
    assert duplicate["type"] == "abort" and duplicate["reason"] == "already_configured"
    print("PASS config flow, PIN hash, single instance, sidebar and native entities", flush=True)

    calls = []

    async def capture(call):
        calls.append((call.domain, call.service, dict(call.data)))
        target_id = call.data.get("entity_id")
        if call.service in ("turn_on", "turn_off") and target_id:
            hass.states.async_set(target_id, "on" if call.service == "turn_on" else "off")

    for domain, service in (
        ("notify", "test_phone"),
        ("siren", "turn_on"),
        ("siren", "turn_off"),
        ("light", "turn_on"),
        ("light", "turn_off"),
    ):
        hass.services.async_register(domain, service, capture)
    for entity_id in (
        "binary_sensor.window",
        "binary_sensor.motion",
        "binary_sensor.person",
        "siren.test",
        "light.test",
    ):
        hass.states.async_set(entity_id, "off")

    data = runtime.config.to_dict()
    data["rooms"] = {
        "living": {"id": "living", "name": "Wohnzimmer", "adjacent": [], "home_enabled": False}
    }
    data["sensors"] = {
        "binary_sensor.window": {
            "entity_id": "binary_sensor.window",
            "role": "entry_contact",
            "room_id": "living",
        },
        "binary_sensor.motion": {
            "entity_id": "binary_sensor.motion",
            "role": "interior_motion",
            "room_id": "living",
        },
        "binary_sensor.person": {
            "entity_id": "binary_sensor.person",
            "role": "perimeter_camera",
            "front_of": ["living"],
        },
    }
    data["actions"] = {
        "push": {"id": "push", "level": "2", "kind": "notify", "target": "notify.test_phone"},
        "alarm": {
            "id": "alarm",
            "level": "3",
            "kind": "siren",
            "target": "siren.test",
            "duration": 2,
        },
        "critical": {
            "id": "critical",
            "level": "3",
            "kind": "notify",
            "target": "notify.test_phone",
            "critical": True,
        },
    }
    await runtime.update_config(data, 0)
    await hass.async_block_till_done()
    assert len([e for e in hass.states.async_entity_ids("binary_sensor") if "wohnzimmer" in e]) == 3
    try:
        await runtime.update_config(data, 0)
    except ValueError as err:
        assert "anderen Fenster" in str(err)
    else:
        raise AssertionError("Stale config revision accepted")
    print(
        "PASS room entity discovery, validated atomic config and stale revision protection",
        flush=True,
    )

    await hass.services.async_call(
        "iqalarm",
        "arm_profile",
        {"profile_id": "armed_night"},
        blocking=True,
    )
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    assert runtime.engine.level == 0 and not calls
    hass.states.async_set("binary_sensor.motion", "off")
    hass.states.async_set("binary_sensor.window", "on")
    await hass.async_block_till_done()
    await asyncio.wait_for(runtime.queue.join(), 10)
    assert runtime.engine.level == 2
    assert any(c[0] == "notify" for c in calls)
    assert not any(c[0] == "siren" for c in calls)
    hass.states.async_set("binary_sensor.motion", "on")
    await hass.async_block_till_done()
    await asyncio.wait_for(runtime.queue.join(), 10)
    assert runtime.engine.level == 3
    assert hass.states.get("alarm_control_panel.iqalarm").state == "triggered"
    assert any(c[:2] == ("siren", "turn_on") for c in calls)
    assert any(
        c[2].get("data", {}).get("push", {}).get("sound", {}).get("critical") == 1 for c in calls
    )
    before = len(calls)
    plan = await runtime.test_level("3")
    assert plan and len(calls) == before
    await hass.services.async_call(
        "iqalarm", "set_mode", {"mode": "disarmed", "code": "2468"}, blocking=True
    )
    assert runtime.engine.level == 0
    assert calls[-1][:2] == ("siren", "turn_off")
    print(
        "PASS native modes, night gating, silent suspicion, critical push, siren, dry run and disarm cleanup",
        flush=True,
    )
    await verify_actions(hass, runtime, calls, capture)

    admin = await hass.auth.async_create_user("IQAlarm admin", group_ids=[GROUP_ID_ADMIN])
    user = await hass.auth.async_create_user("IQAlarm user", group_ids=[GROUP_ID_USER])
    admin_refresh = await hass.auth.async_create_refresh_token(admin, client_id="http://localhost/")
    user_refresh = await hass.auth.async_create_refresh_token(user, client_id="http://localhost/")
    admin_token = hass.auth.async_create_access_token(admin_refresh)
    user_token = hass.auth.async_create_access_token(user_refresh)
    area_registry.async_get(hass).async_create("Flur")
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "http://127.0.0.1:18123/iqalarm_static/iqalarm-panel.js"
        ) as response:
            assert response.status == 200 and "customElements.define" in await response.text()
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": admin_token})
            assert (await ws.receive_json())["type"] == "auth_ok"
            await ws.send_json({"id": 1, "type": "iqalarm/get"})
            state = await ws.receive_json()
            assert state["success"] and state["result"]["pin_required"]
            assert "pin_hash" not in json.dumps(state)
            await ws.send_json({"id": 2, "type": "iqalarm/catalog"})
            catalog = await ws.receive_json()
            assert "notify.test_phone" in catalog["result"]["notify_services"]
            await ws.send_json(
                {"id": 3, "type": "iqalarm/import_areas", "revision": runtime.config.revision}
            )
            imported = await ws.receive_json()
            assert imported["success"], imported
            assert any(r.name == "Flur" for r in runtime.config.rooms.values())
            await ws.send_json({"id": 4, "type": "iqalarm/subscribe"})
            assert (await ws.receive_json())["success"]
            assert (await ws.receive_json())["type"] == "event"
            await ws.send_json({"id": 5, "type": "unsubscribe_events", "subscription": 4})
            assert (await ws.receive_json())["success"]
            await ws.send_json(
                {
                    "id": 6,
                    "type": "iqalarm/crud",
                    "collection": "rooms",
                    "operation": "save",
                    "revision": runtime.config.revision,
                    "item": {"name": "Keller"},
                }
            )
            assert (await ws.receive_json())["success"]
            await ws.send_json(
                {"id": 7, "type": "iqalarm/test_level", "level": "3", "dry_run": True}
            )
            assert (await ws.receive_json())["result"]["dry_run"]
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": user_token})
            await ws.receive_json()
            await ws.send_json({"id": 1, "type": "iqalarm/get"})
            denied = await ws.receive_json()
            assert denied["success"] is False and denied["error"]["code"] == "unauthorized", denied
        media_name = f"{int(time.time())}_0123456789abcdefabcd.jpg"
        (runtime.dispatcher.media_dir / media_name).write_bytes(b"IQAlarm private media test")
        media_url = "http://127.0.0.1:18123/api/iqalarm/media/" + media_name
        async with session.get(media_url) as response:
            assert response.status == 401
        async with session.get(
            media_url, headers={"Authorization": "Bearer " + user_token}
        ) as response:
            assert response.status == 403
        (runtime.dispatcher.media_dir / (media_name + ".json")).write_text(
            json.dumps({"camera_entity_id": "camera.test"})
        )
        async with session.get(
            media_url, headers={"Authorization": "Bearer " + user_token}
        ) as response:
            assert response.status == 200
        async with session.get(
            media_url, headers={"Authorization": "Bearer " + admin_token}
        ) as response:
            assert response.status == 200, await response.text()
    print(
        "PASS real authenticated HTTP/WS, CRUD, area import, subscriptions, admin boundaries and private snapshots",
        flush=True,
    )
    await verify_profiles(hass, entry, admin_token, user_token, calls)
    from verify_v2 import verify_v2

    await verify_v2(hass, entry, admin_token, user_token, calls)
    from verify_floorplan_assistant import verify_floorplan_assistant

    await verify_floorplan_assistant(hass, entry, admin_token, user_token)
    from verify_windows import verify_windows

    await verify_windows(hass, entry, admin_token, user_token)
    runtime = entry.runtime_data

    hass.states.async_set("binary_sensor.window", "off")
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await runtime.set_mode("armed_night")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": admin_token})
            await ws.receive_json()
            await ws.send_json({"id": 1, "type": "iqalarm/subscribe"})
            assert (await ws.receive_json())["success"]
            assert (await ws.receive_json())["type"] == "event"
            await hass.config_entries.async_reload(entry.entry_id)
            restored_subscription = False
            async with asyncio.timeout(5):
                while not restored_subscription:
                    message = await ws.receive_json()
                    restored_subscription = bool(message.get("event", {}).get("available"))
    await hass.async_block_till_done()
    assert entry.runtime_data.engine.profile_id == "armed_night"
    await entry.runtime_data.set_mode("disarmed", "2468")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert "iqalarm" not in hass.data["frontend_panels"]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    print(
        "PASS persistent arming, live subscriptions across reload, full unload/reload, panel re-registration and storage",
        flush=True,
    )
    print("HA INTEGRATION VERIFICATION PASSED", flush=True)
    return admin_token


async def verify_profiles(hass, entry, admin_token, user_token, calls) -> None:
    """Exercise profile identity, real actions, native compatibility and migration."""
    from copy import deepcopy

    saved = entry.runtime_data.config.to_dict()
    for entity_id in saved["sensors"]:
        hass.states.async_set(entity_id, "off")
    await hass.async_block_till_done()
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": admin_token})
            assert (await ws.receive_json())["type"] == "auth_ok"
            next_id = 0

            async def request(kind, **kwargs):
                nonlocal next_id
                next_id += 1
                await ws.send_json({"id": next_id, "type": f"iqalarm/{kind}", **kwargs})
                return await ws.receive_json()

            async def crud(collection, operation, **kwargs):
                return await request(
                    "crud",
                    collection=collection,
                    operation=operation,
                    revision=entry.runtime_data.config.revision,
                    **kwargs,
                )

            action = {
                "id": "profile_push",
                "level": "3",
                "kind": "notify",
                "target": "notify.test_phone",
                "message": "{{profile}} / {{mode}}",
            }
            assert (await crud("actions", "save", item=action))["success"]
            custom = deepcopy(saved["profiles"]["armed_night"])
            custom.update(
                id="guests",
                name="Nacht mit Gästen",
                motion_mode="after_contact",
                room_ids=["living"],
                sensor_ids=["binary_sensor.window", "binary_sensor.motion"],
                action_ids=["profile_push"],
            )
            created = await crud("profiles", "save", item=custom)
            assert created["success"], created
            assert created["result"]["config"]["profiles"]["guests"]["name"] == custom["name"]
            blocked = await crud("profiles", "delete", key="observe")
            assert not blocked["success"]
            before = len(calls)
            dry = await request("test_level", level="3", dry_run=True, profile_id="guests")
            assert dry["success"] and [p["id"] for p in dry["result"]["actions"]] == [
                "profile_push"
            ]
            assert len(calls) == before and entry.runtime_data.engine.mode.value == "inactive"
            assert (await request("arm_profile", profile_id="guests"))["success"]
            await hass.async_block_till_done()
            entity = hass.states.get("alarm_control_panel.iqalarm")
            assert entity.state == "armed_away" and entity.attributes["profile_id"] == "guests"
            assert entity.attributes["profile_name"] == "Nacht mit Gästen"
            switched = await request("set_mode", mode="armed_night")
            assert not switched["success"] and entry.runtime_data.engine.profile_id == "guests"
            changed = await crud("profiles", "save", item={**custom, "name": "Changed"})
            assert not changed["success"]
            hass.states.async_set("binary_sensor.window", "on")
            await hass.async_block_till_done()
            await asyncio.wait_for(entry.runtime_data.queue.join(), 5)
            assert entry.runtime_data.engine.level == 2
            assert len(calls) == before, "Excluded suspicion actions were executed"
            hass.states.async_set("binary_sensor.motion", "on")
            await hass.async_block_till_done()
            await asyncio.wait_for(entry.runtime_data.queue.join(), 5)
            assert hass.states.get("alarm_control_panel.iqalarm").state == "triggered"
            assert calls[before:] == [
                (
                    "notify",
                    "test_phone",
                    {
                        "title": "IQAlarm · Stufe 3",
                        "message": "Nacht mit Gästen / active",
                        "data": {},
                    },
                )
            ], calls[before:]
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            restored = entry.runtime_data
            assert restored.engine.profile_id == "guests" and restored.engine.level == 3
            assert restored.engine.events[0].profile_name == "Nacht mit Gästen"
            assert len(calls) == before + 1, "Restart replayed profile actions"
            refused = await request("set_mode", mode="disarmed", code="0000")
            assert not refused["success"] and restored.engine.profile_id == "guests"
            assert (await request("set_mode", mode="disarmed", code="2468"))["success"]
            for entity_id in saved["sensors"]:
                hass.states.async_set(entity_id, "off")
            await hass.async_block_till_done()
            await hass.services.async_call(
                "iqalarm", "arm_profile", {"profile_id": "guests"}, blocking=True
            )
            assert entry.runtime_data.engine.profile_id == "guests"
            await entry.runtime_data.set_mode("disarmed", "2468")
            await entry.runtime_data.set_mode("armed_night")
            assert entry.runtime_data.engine.profile_id == "armed_night"
            await entry.runtime_data.set_mode("disarmed", "2468")
            assert (await crud("actions", "delete", key="profile_push"))["success"]
            assert entry.runtime_data.config.profiles["guests"].action_ids == []
            empty = await request("test_level", level="3", profile_id="guests")
            assert empty["success"] and empty["result"]["actions"] == []
            assert (await crud("profiles", "delete", key="guests"))["success"]
        async with session.ws_connect("http://127.0.0.1:18123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": user_token})
            await ws.receive_json()
            await ws.send_json(
                {"id": 1, "type": "iqalarm/arm_profile", "profile_id": "armed_night"}
            )
            denied = await ws.receive_json()
            assert not denied["success"] and denied["error"]["code"] == "unauthorized"
    await entry.runtime_data.update_config(saved, entry.runtime_data.config.revision)
    print(
        "PASS custom profile CRUD, scoped real actions, native HA state, PIN, permissions, deletion and restart identity",
        flush=True,
    )


async def verify_actions(hass, runtime, calls, capture) -> None:
    from custom_components.iqalarm.models import Action, EventLog

    async def camera_capture(call):
        assert hass.config.is_allowed_path(call.data["filename"])
        await hass.async_add_executor_job(
            Path(call.data["filename"]).write_bytes, b"IQAlarm camera service contract test"
        )
        calls.append((call.domain, call.service, dict(call.data)))

    for domain, service in (
        ("switch", "turn_on"),
        ("switch", "turn_off"),
        ("script", "turn_on"),
        ("script", "turn_off"),
        ("cover", "open_cover"),
        ("tts", "speak"),
        ("notify", "send_message"),
    ):
        hass.services.async_register(domain, service, capture)
    for service in ("snapshot", "record"):
        hass.services.async_register("camera", service, camera_capture)
    for entity_id in ("switch.test", "script.test", "light.test"):
        hass.states.async_set(entity_id, "off")
    event = EventLog(time.time(), "test", 3, "armed_away", "Verifikation")
    variables = runtime.dispatcher.variables(event)
    configurations = [
        Action("switch", "3", "switch", "switch.test", duration=2),
        Action("script", "3", "script", "script.test", duration=2),
        Action("light", "3", "light", "light.test", brightness=100, color=[255, 0, 0], duration=2),
        Action("cover", "3", "cover", "cover.test"),
        Action("snap", "1", "snapshot", "camera.test"),
        Action("record", "1", "record", "camera.test", duration=20),
        Action("tts", "3", "tts", "tts.test", media_player="media_player.test"),
        Action(
            "image",
            "3",
            "notify",
            "notify.test_phone",
            camera_entity_id="camera.test",
            critical=True,
        ),
        Action("entity_push", "2", "notify", "notify.test_entity"),
    ]
    for action in configurations:
        await runtime.dispatcher.execute(action, variables, runtime.generation)
    assert any(c[:2] == ("cover", "open_cover") for c in calls)
    assert any(
        c[:2] == ("tts", "speak") and c[2]["media_player_entity_id"] == "media_player.test"
        for c in calls
    )
    assert any(c[:2] == ("light", "turn_on") and c[2]["rgb_color"] == [255, 0, 0] for c in calls)
    assert any(c[:2] == ("notify", "send_message") for c in calls)
    assert any(
        c[2].get("data", {}).get("image", "").startswith("/api/iqalarm/media/") for c in calls
    )
    for owned in runtime.dispatcher.outputs.values():
        owned["until"] = 0
    await runtime.dispatcher.cleanup()
    assert not runtime.dispatcher.outputs
    hass.states.async_set("light.test", "on")
    await runtime.dispatcher.execute(configurations[2], variables, runtime.generation)
    assert "light.test" not in runtime.dispatcher.outputs
    hass.states.async_set("light.test", "off")

    async def broken_camera(call):
        raise HomeAssistantError("Deliberately unavailable test camera")

    hass.services.async_register("camera", "snapshot", broken_camera)
    prior = sum(c[:2] == ("notify", "test_phone") for c in calls)
    await runtime.dispatcher.execute(configurations[7], variables, runtime.generation)
    assert sum(c[:2] == ("notify", "test_phone") for c in calls) == prior + 1
    hass.services.async_register("camera", "snapshot", camera_capture)

    delayed_started, delayed_release = asyncio.Event(), asyncio.Event()

    async def delayed_notify(call):
        delayed_started.set()
        await delayed_release.wait()

    hass.services.async_register("notify", "delayed", delayed_notify)
    data = runtime.config.to_dict()
    data["actions"]["delayed"] = {
        "id": "delayed",
        "level": "2",
        "kind": "notify",
        "target": "notify.delayed",
    }
    await runtime.update_config(data, runtime.config.revision)
    hass.states.async_set("binary_sensor.window", "off")
    hass.states.async_set("binary_sensor.motion", "off")
    await hass.async_block_till_done()
    await runtime.set_mode("armed_night")
    hass.states.async_set("binary_sensor.window", "on")
    await asyncio.wait_for(delayed_started.wait(), 5)
    hass.states.async_set("binary_sensor.motion", "on")
    for _ in range(50):
        if hass.states.get("siren.test").state == "on":
            break
        await asyncio.sleep(0.02)
    assert hass.states.get("siren.test").state == "on", (
        "Slow suspicion notification blocked full alarm"
    )
    delayed_release.set()
    await asyncio.wait_for(runtime.queue.join(), 5)
    await runtime.set_mode("disarmed", "2468")
    assert hass.states.get("siren.test").state == "off"
    data = runtime.config.to_dict()
    del data["actions"]["delayed"]
    await runtime.update_config(data, runtime.config.revision)

    for _ in range(5):
        try:
            await runtime.validate_code("wrong")
        except HomeAssistantError:
            continue
        raise AssertionError("Invalid PIN accepted")
    try:
        await runtime.validate_code("2468")
    except HomeAssistantError as err:
        assert "Minute" in str(err)
    else:
        raise AssertionError("PIN rate limit not enforced")
    runtime._failed_pins = [t - 61 for t in runtime._failed_pins]
    await runtime.validate_code("2468")
    print(
        "PASS all action kinds, private camera files, ownership/timers, camera failure fallback, nonblocking escalation and PIN throttling",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
