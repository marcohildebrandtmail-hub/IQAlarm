"""IQAlarm: locally evaluated, spatially correlated multi-stage security."""

import json
import logging
import re
import time
from functools import partial
from pathlib import Path

from aiohttp import web
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service

from .compat import vol
from .const import DOMAIN, PLATFORMS, VERSION, Mode
from .runtime import IQAlarmRuntime
from .websocket_api import register, runtime

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class IQAlarmMediaView(HomeAssistantView):
    """Authenticated camera attachments, never publicly exposed under /local."""

    url = "/api/iqalarm/media/{filename}"
    name = "api:iqalarm:media"
    requires_auth = True

    async def get(self, request: web.Request, filename: str) -> web.StreamResponse:
        if not re.fullmatch(r"\d+_[a-f0-9]{20}\.(jpg|mp4)", filename):
            raise web.HTTPNotFound()
        hass = request.app["hass"]
        instance = hass.data.get(DOMAIN, {}).get("runtime")
        if instance is None:
            raise web.HTTPNotFound()
        path = instance.dispatcher.media_dir / filename
        if not await hass.async_add_executor_job(path.is_file):
            raise web.HTTPNotFound()
        user = request["hass_user"]
        if not user.is_admin:
            try:
                metadata = json.loads(
                    await hass.async_add_executor_job(path.with_name(filename + ".json").read_text)
                )
            except (OSError, ValueError):
                raise web.HTTPForbidden() from None
            camera = metadata.get("camera_entity_id")
            if (
                not isinstance(camera, str)
                or not camera.startswith("camera.")
                or not user.permissions.check_entity(camera, POLICY_READ)
            ):
                raise web.HTTPForbidden()
        return web.FileResponse(
            path,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data.setdefault(DOMAIN, {})
    instance = IQAlarmRuntime(hass, entry)
    entry.runtime_data = instance
    try:
        await instance.start()
    except (OSError, ValueError, KeyError, HomeAssistantError) as err:
        await instance.stop(save=False)
        raise ConfigEntryNotReady(f"IQAlarm-Speicher konnte nicht geladen werden: {err}") from err
    data["runtime"] = instance
    panel_registered = False
    try:
        if not data.get("api_registered"):
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        "/iqalarm_static", str(Path(__file__).parent / "frontend"), False
                    )
                ]
            )
            hass.http.register_view(IQAlarmMediaView())
            register(hass)
            data["api_registered"] = True
        if not data.get("services_registered"):
            async_register_admin_service(
                hass,
                DOMAIN,
                "set_mode",
                partial(_set_mode, hass),
                schema=vol.Schema(
                    {
                        vol.Required("mode"): vol.In([m.value for m in Mode]),
                        vol.Optional("code"): str,
                    }
                ),
            )
            async_register_admin_service(
                hass,
                DOMAIN,
                "clear_quarantine",
                partial(_clear_quarantine, hass),
                schema=vol.Schema({vol.Optional("entity_id"): cv.entity_id}),
            )
            async_register_admin_service(
                hass,
                DOMAIN,
                "trigger_test_level",
                partial(_test_level, hass),
                schema=vol.Schema(
                    {
                        vol.Required("level"): vol.In(["1", "2", "3", "diagnostic"]),
                        vol.Optional("dry_run", default=True): bool,
                    }
                ),
            )
            data["services_registered"] = True
        if DOMAIN in hass.data.get(frontend.DATA_PANELS, {}):
            raise HomeAssistantError("Der Seitenpanel-Pfad /iqalarm ist bereits belegt")
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="iqalarm-panel",
            sidebar_title="IQAlarm",
            sidebar_icon="mdi:shield-check",
            module_url=f"/iqalarm_static/iqalarm-panel.js?v={VERSION}",
            require_admin=True,
            config_panel_domain=DOMAIN,
        )
        panel_registered = True
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        if panel_registered:
            frontend.async_remove_panel(hass, DOMAIN)
        await instance.stop()
        data.pop("runtime", None)
        raise
    instance.publish()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.stop()
    frontend.async_remove_panel(hass, DOMAIN)
    hass.data[DOMAIN].pop("runtime", None)
    entry.runtime_data.publish()
    return True


async def _set_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    try:
        await runtime(hass).set_mode(call.data["mode"], call.data.get("code"))
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err


async def _clear_quarantine(hass: HomeAssistant, call: ServiceCall) -> None:
    instance = runtime(hass)
    instance.engine.clear_quarantine(call.data.get("entity_id"), time.time())
    await instance.flush()


async def _test_level(hass: HomeAssistant, call: ServiceCall) -> None:
    await runtime(hass).test_level(call.data["level"], call.data["dry_run"])
