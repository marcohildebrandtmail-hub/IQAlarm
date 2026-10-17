"""Private floorplan images with bounded uploads and sanitized pixel storage."""

import warnings
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from PIL import Image, UnidentifiedImageError

from .const import DOMAIN

MAX_UPLOAD = 10 * 1024 * 1024


def prepare_image(payload: bytes) -> tuple[bytes, int, int]:
    """Keep only bounded PNG/JPEG pixels, discarding metadata and extra frames."""
    if not payload or len(payload) > MAX_UPLOAD:
        raise ValueError("Grundriss muss zwischen 1 Byte und 10 MB groß sein")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as image:
                if image.format not in {"PNG", "JPEG"}:
                    raise ValueError("Nur PNG oder JPEG sind erlaubt")
                width, height = image.size
                if not 1 <= width <= 8192 or not 1 <= height <= 8192 or width * height > 32_000_000:
                    raise ValueError("Bild maximal 8192 Pixel pro Seite und 32 Megapixel")
                image.load()
                output = BytesIO()
                image.convert("RGB").save(output, format="PNG")
                return output.getvalue(), width, height
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as err:
        raise ValueError("Ungültiges oder zu großes Bild") from err


def write_image(directory: Path, filename: str, payload: bytes) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / (filename + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(directory / filename)
    finally:
        temporary.unlink(missing_ok=True)


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
        payload = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            payload.extend(chunk)
            if len(payload) > MAX_UPLOAD:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_UPLOAD, actual_size=len(payload))
        try:
            revision = int(request.headers.get("X-IQAlarm-Revision", "-1"))
            pixels, width, height = await instance.hass.async_add_executor_job(
                prepare_image, bytes(payload)
            )
            async with instance.lock:
                if instance.engine.reactions_enabled or revision != instance.config.revision:
                    raise ValueError("Anlage aktiv oder Konfiguration geändert; bitte neu laden")
                filename = uuid4().hex + ".png"
                directory = Path(instance.hass.config.path(".iqalarm_floorplans"))
                await instance.hass.async_add_executor_job(write_image, directory, filename, pixels)
                data = deepcopy(instance.config.to_dict())
                data["floorplans"][plan_id].update(image=filename, width=width, height=height)
                try:
                    await instance.save_config_locked(data, revision)
                except Exception:
                    await instance.hass.async_add_executor_job((directory / filename).unlink, True)
                    raise
            return self.json(instance.snapshot())
        except (ValueError, OSError) as err:
            return self.json({"message": str(err)}, status_code=400)
