"""Exercise new-plan uploads, proposals, icon persistence and admin boundaries."""

import asyncio
from copy import deepcopy
from io import BytesIO
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw


async def verify_floorplan_assistant(hass, entry, admin_token, user_token):
    runtime = entry.runtime_data
    saved = deepcopy(runtime.config.to_dict())
    origin = "http://127.0.0.1:18123"
    admin = {"Authorization": "Bearer " + admin_token}
    user = {"Authorization": "Bearer " + user_token}
    url = origin + "/api/iqalarm/floorplans/upload?name=Test-Etage"
    image = Image.new("RGB", (500, 300), "white")
    drawing = ImageDraw.Draw(image)
    drawing.rectangle((30, 30, 470, 270), outline="black", width=6)
    drawing.line((250, 30, 250, 270), fill="black", width=6)
    payload = BytesIO()
    image.save(payload, "PNG")
    before = len(runtime.config.floorplans)
    revision = runtime.config.revision
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload.getvalue()) as response:
            assert response.status == 401
        async with session.post(url, headers=user, data=payload.getvalue()) as response:
            assert response.status == 403
        headers = {**admin, "X-IQAlarm-Revision": str(revision)}
        async with session.post(url, headers=headers, data=b"broken image") as response:
            assert response.status == 400
        assert len(runtime.config.floorplans) == before
        assert runtime.config.revision == revision
        async with session.post(
            origin + "/api/iqalarm/floorplans/upload", headers=headers, data=payload.getvalue()
        ) as response:
            assert response.status == 400
        async with session.post(url, headers=headers, data=payload.getvalue()) as response:
            assert response.status == 200, await response.text()
            created = await response.json()
        plan_id = created["uploaded_plan_id"]
        assert len(runtime.config.floorplans) == before + 1
        assert runtime.config.floorplans[plan_id].name == "Test-Etage"
        assert runtime.config.floorplans[plan_id].width == 500
        async with session.post(url, headers=headers, data=payload.getvalue()) as response:
            assert response.status == 400
        assert len(runtime.config.floorplans) == before + 1

        async def request(ws, seq, **data):
            await ws.send_json({"id": seq, **data})
            async with asyncio.timeout(10):
                while True:
                    result = await ws.receive_json()
                    if result.get("type") == "result" and result.get("id") == seq:
                        return result

        async with session.ws_connect(origin + "/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": admin_token})
            await ws.receive_json()
            current_revision = runtime.config.revision
            result = await request(ws, 1, type="iqalarm/floorplan/analyze", plan_id=plan_id, gap=0)
            assert result["success"], result
            proposals = result["result"]["candidates"]
            assert len(proposals) == 2
            assert runtime.config.revision == current_revision
            assert not runtime.config.floorplans[plan_id].zones, (
                "Analysis saved unreviewed proposals"
            )
            data = runtime.config.to_dict()
            data["floorplans"][plan_id]["zones"]["living"] = proposals[0]["points"]
            data["profiles"]["armed_night"]["icon"] = "mdi:cat"
            saved_result = await request(
                ws, 2, type="iqalarm/config/save", config=data, revision=current_revision
            )
            assert saved_result["success"], saved_result
            assert runtime.config.profiles["armed_night"].icon == "mdi:cat"

        async with session.ws_connect(origin + "/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": user_token})
            await ws.receive_json()
            denied = await request(ws, 1, type="iqalarm/floorplan/analyze", plan_id=plan_id)
            assert not denied["success"] and denied["error"]["code"] == "unauthorized"

        assert await hass.config_entries.async_reload(entry.entry_id)
        runtime = entry.runtime_data
        assert runtime.config.floorplans[plan_id].zones["living"] == proposals[0]["points"]
        assert runtime.config.profiles["armed_night"].icon == "mdi:cat"
        filename = runtime.config.floorplans[plan_id].image
        await runtime.update_config(saved, runtime.config.revision)
        assert not await hass.async_add_executor_job(
            Path(hass.config.path(".iqalarm_floorplans", filename)).exists
        )
        async with session.get(
            origin + f"/api/iqalarm/floorplans/{plan_id}/image", headers=admin
        ) as response:
            assert response.status == 404
    print(
        "PASS atomic new-floor upload, failed/stale upload rollback, private image access, read-only proposals, reviewed geometry, custom icons, deletion and restart",
        flush=True,
    )
