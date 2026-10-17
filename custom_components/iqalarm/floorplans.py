"""Private floorplan images with bounded uploads and sanitized pixel storage."""

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import DOMAIN
from .floorplan_image import MAX_UPLOAD, prepare_image, write_image


class IQAlarmFloorPlanView(HomeAssistantView):
    url = "/api/iqalarm/floorplans/{plan_id}/image"
    name = "api:iqalarm:floorplan"
    requires_auth = True

    def instance(self, request, plan_id):
        if not request["hass_user"].is_admin:
            raise web.HTTPForbidden()
        instance = request.app["hass"].data.get(DOMAIN, {}).get("runtime")
        if instance is None or plan_id not in instance.config.floorplans:
            raise web.HTTPNotFound()
        return instance

    async def get(self, request, plan_id):
        instance = self.instance(request, plan_id)
        plan = instance.config.floorplans[plan_id]
        if not plan.image:
            raise web.HTTPNotFound()
        path = Path(instance.hass.config.path(".iqalarm_floorplans", plan.image))
        if not await instance.hass.async_add_executor_job(path.is_file):
            raise web.HTTPNotFound()
        return web.FileResponse(
            path,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    async def post(self, request, plan_id):
        instance = self.instance(request, plan_id)
        return await upload_image(self, request, instance, plan_id)


class IQAlarmFloorPlanUploadView(HomeAssistantView):
    """Create the named floor and its image in a single revision-checked commit."""

    url = "/api/iqalarm/floorplans/upload"
    name = "api:iqalarm:floorplan_upload"
    requires_auth = True

    async def post(self, request):
        if not request["hass_user"].is_admin:
            raise web.HTTPForbidden()
        instance = request.app["hass"].data.get(DOMAIN, {}).get("runtime")
        if instance is None:
            raise web.HTTPNotFound()
        return await upload_image(self, request, instance)


async def upload_image(view, request, instance, plan_id=None):
    """Validate and save a new or existing plan without leaving empty entries."""
    try:
        revision = int(request.headers.get("X-IQAlarm-Revision", "-1"))
        if instance.engine.reactions_enabled or revision != instance.config.revision:
            raise ValueError("Anlage aktiv oder Konfiguration geändert; bitte neu laden")
        name = request.query.get("name", "").strip()
        if plan_id is None and not 1 <= len(name) <= 100:
            raise ValueError("Bitte einen Etagennamen mit 1 bis 100 Zeichen angeben")
        payload = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            payload.extend(chunk)
            if len(payload) > MAX_UPLOAD:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD, actual_size=len(payload))
        pixels, width, height = await instance.hass.async_add_executor_job(
            prepare_image, bytes(payload)
        )
        async with instance.lock:
            if instance.engine.reactions_enabled or revision != instance.config.revision:
                raise ValueError("Anlage aktiv oder Konfiguration geändert; bitte neu laden")
            data = deepcopy(instance.config.to_dict())
            if plan_id is None:
                if len(data["floorplans"]) >= 20:
                    raise ValueError("Maximal 20 Grundrisse erlaubt")
                plan_id = uuid4().hex
                data["floorplans"][plan_id] = {"id": plan_id, "name": name, "zones": {}}
            if plan_id not in data["floorplans"]:
                raise ValueError("Grundriss wurde inzwischen entfernt")
            filename = uuid4().hex + ".png"
            directory = Path(instance.hass.config.path(".iqalarm_floorplans"))
            await instance.hass.async_add_executor_job(write_image, directory, filename, pixels)
            data["floorplans"][plan_id].update(image=filename, width=width, height=height)
            try:
                await instance.save_config_locked(data, revision)
            except Exception:
                await instance.hass.async_add_executor_job((directory / filename).unlink, True)
                raise
        return view.json({**instance.snapshot(), "uploaded_plan_id": plan_id})
    except (ValueError, OSError) as err:
        return view.json({"message": str(err)}, status_code=400)
