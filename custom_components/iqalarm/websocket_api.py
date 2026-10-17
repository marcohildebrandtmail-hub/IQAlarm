"""Admin-scoped, validated API with revision control and live subscriptions."""

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .compat import vol
from .const import ALLOWED_SENSOR_DOMAINS, DOMAIN, SIGNAL_UPDATE
from .floorplan_analysis import analyze_image
from .models import Action, FloorPlan, Profile, Room, SensorConfig, construct


def runtime(hass):
    instance = hass.data.get(DOMAIN, {}).get("runtime")
    if instance is None or instance.stopped:
        raise HomeAssistantError("IQAlarm ist nicht geladen")
    return instance


def register(hass) -> None:
    for handler in (
        ws_get,
        ws_subscribe,
        ws_config,
        ws_crud,
        ws_import_areas,
        ws_mode,
        ws_profile,
        ws_quarantine,
        ws_test,
        ws_catalog,
        ws_analyze_floorplan,
    ):
        websocket_api.async_register_command(hass, handler)


@websocket_api.websocket_command(
    {
        "type": "iqalarm/floorplan/analyze",
        vol.Required("plan_id"): str,
        vol.Optional("gap", default=28): vol.All(int, vol.Range(min=0, max=40)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_analyze_floorplan(hass, connection, msg) -> None:
    """Return local geometry proposals without persisting or changing assignments."""
    try:
        instance = runtime(hass)
        plan = instance.config.floorplans.get(msg["plan_id"])
        if plan is None or not plan.image:
            raise ValueError("Zuerst ein Grundrissbild hochladen")
        image = plan.image
        result = await hass.async_add_executor_job(
            analyze_image, Path(hass.config.path(".iqalarm_floorplans", image)), msg["gap"]
        )
        current = instance.config.floorplans.get(plan.id)
        if current is None or current.image != image:
            raise ValueError("Grundriss wurde inzwischen geändert; Analyse erneut starten")
        connection.send_result(
            msg["id"],
            {
                **result,
                "plan_id": plan.id,
                "image": image,
                "revision": instance.config.revision,
            },
        )
    except (ValueError, OSError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "floorplan_analysis_failed", str(err))


@websocket_api.websocket_command({"type": "iqalarm/get"})
@websocket_api.require_admin
@callback
def ws_get(hass, connection, msg) -> None:
    connection.send_result(msg["id"], runtime(hass).snapshot())


@websocket_api.websocket_command({"type": "iqalarm/subscribe"})
@websocket_api.require_admin
@callback
def ws_subscribe(hass, connection, msg) -> None:
    runtime(hass)

    @callback
    def updated() -> None:
        try:
            current = runtime(hass).snapshot()
        except HomeAssistantError:
            current = {"available": False}
        connection.send_event(msg["id"], current)

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATE, updated)
    connection.send_result(msg["id"])
    updated()


@websocket_api.websocket_command(
    {"type": "iqalarm/config/save", vol.Required("config"): dict, vol.Required("revision"): int}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_config(hass, connection, msg) -> None:
    try:
        instance = runtime(hass)
        await instance.update_config(msg["config"], msg["revision"])
        connection.send_result(msg["id"], instance.snapshot())
    except (ValueError, TypeError, AttributeError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "invalid_configuration", str(err))


@websocket_api.websocket_command(
    {
        "type": "iqalarm/crud",
        vol.Required("collection"): vol.In(
            ["rooms", "sensors", "actions", "profiles", "floorplans"]
        ),
        vol.Required("operation"): vol.In(["save", "delete"]),
        vol.Required("revision"): int,
        vol.Optional("item", default={}): dict,
        vol.Optional("key"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_crud(hass, connection, msg) -> None:
    try:
        instance = runtime(hass)
        data = deepcopy(instance.config.to_dict())
        collection = msg["collection"]
        if msg["operation"] == "delete":
            key = msg.get("key")
            if key not in data[collection]:
                raise ValueError("Eintrag nicht vorhanden")
            if collection == "profiles" and key == data["settings"]["observation_profile_id"]:
                raise ValueError("Zuerst ein anderes Hintergrund-Beobachtungsprofil auswählen")
            if collection == "rooms":
                if any(
                    s["room_id"] == key or key in s["front_of"] for s in data["sensors"].values()
                ):
                    raise ValueError(
                        "Zuerst Sensoren und Vorfeld-Zuordnungen dieses Raums entfernen"
                    )
                for room in data["rooms"].values():
                    room["adjacent"] = [r for r in room["adjacent"] if r != key]
                for plan in data["floorplans"].values():
                    plan["zones"].pop(key, None)
            reference = {"rooms": "room_ids", "sensors": "sensor_ids", "actions": "action_ids"}.get(
                collection
            )
            if reference:
                for profile in data["profiles"].values():
                    if profile.get(reference) is not None:
                        profile[reference] = [value for value in profile[reference] if value != key]
            del data[collection][key]
        else:
            item = dict(msg["item"])
            if collection in ("rooms", "actions", "profiles", "floorplans"):
                item.setdefault("id", uuid4().hex)
            key = item["entity_id" if collection == "sensors" else "id"]
            if collection == "profiles":
                item.pop("id")
                construct(Profile, item)
            else:
                cls = {
                    "rooms": Room,
                    "sensors": SensorConfig,
                    "actions": Action,
                    "floorplans": FloorPlan,
                }[collection]
                construct(cls, item)
            data[collection][key] = item
        await instance.update_config(data, msg["revision"])
        connection.send_result(msg["id"], instance.snapshot())
    except (ValueError, KeyError, TypeError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "invalid_configuration", str(err))


@websocket_api.websocket_command(
    {"type": "iqalarm/import_areas", vol.Required("revision"): int, vol.Optional("area_ids"): [str]}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import_areas(hass, connection, msg) -> None:
    try:
        instance = runtime(hass)
        data = instance.config.to_dict()
        imported = {r["area_id"] for r in data["rooms"].values()}
        for area in area_registry.async_get(hass).async_list_areas():
            if area.id not in imported and ("area_ids" not in msg or area.id in msg["area_ids"]):
                room = Room(uuid4().hex, area.name, area_id=area.id)
                data["rooms"][room.id] = {
                    "id": room.id,
                    "name": room.name,
                    "area_id": room.area_id,
                    "adjacent": [],
                    "home_enabled": False,
                }
        await instance.update_config(data, msg["revision"])
        connection.send_result(msg["id"], instance.snapshot())
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "import_failed", str(err))


@websocket_api.websocket_command(
    {
        "type": "iqalarm/set_mode",
        vol.Required("mode"): str,
        vol.Optional("code"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_mode(hass, connection, msg) -> None:
    try:
        instance = runtime(hass)
        if msg["mode"] == "active":
            await instance.activate()
        else:
            await instance.set_mode(msg["mode"], msg.get("code"))
        connection.send_result(msg["id"], instance.snapshot())
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "mode_failed", str(err))


@websocket_api.websocket_command({"type": "iqalarm/arm_profile", vol.Required("profile_id"): str})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile(hass, connection, msg) -> None:
    try:
        instance = runtime(hass)
        await instance.set_profile(msg["profile_id"])
        connection.send_result(msg["id"], instance.snapshot())
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "profile_failed", str(err))


@websocket_api.websocket_command(
    {"type": "iqalarm/clear_quarantine", vol.Optional("entity_id"): str}
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_quarantine(hass, connection, msg) -> None:
    instance = runtime(hass)
    instance.engine.clear_quarantine(msg.get("entity_id"), __import__("time").time())
    await instance.flush()
    connection.send_result(msg["id"], instance.snapshot())


@websocket_api.websocket_command(
    {
        "type": "iqalarm/test_level",
        vol.Required("level"): str,
        vol.Optional("dry_run", default=True): bool,
        vol.Optional("profile_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def ws_test(hass, connection, msg) -> None:
    try:
        instance = runtime(hass)
        result = await instance.test_level(msg["level"], msg["dry_run"], msg.get("profile_id"))
        connection.send_result(msg["id"], {"dry_run": msg["dry_run"], "actions": result})
    except (ValueError, HomeAssistantError) as err:
        connection.send_error(msg["id"], "test_failed", str(err))


@websocket_api.websocket_command({"type": "iqalarm/catalog"})
@websocket_api.require_admin
@callback
def ws_catalog(hass, connection, msg) -> None:
    domains = ALLOWED_SENSOR_DOMAINS | {
        "siren",
        "switch",
        "script",
        "light",
        "cover",
        "notify",
        "tts",
        "media_player",
    }
    entities = [
        {
            "entity_id": s.entity_id,
            "name": s.attributes.get("friendly_name", s.entity_id),
            "state": s.state,
            "attributes": {
                k: v
                for k, v in s.attributes.items()
                if isinstance(v, (str, int, float, bool))
                and k not in {"access_token", "entity_picture"}
            },
        }
        for s in hass.states.async_all()
        if s.domain in domains
        and not s.entity_id.startswith(("sensor.iqalarm", "binary_sensor.iqalarm"))
    ]
    notify = [
        f"notify.{service}"
        for service in hass.services.async_services().get("notify", {})
        if service not in ("notify", "send_message")
    ]
    areas = [{"id": a.id, "name": a.name} for a in area_registry.async_get(hass).async_list_areas()]
    connection.send_result(
        msg["id"], {"entities": entities, "notify_services": notify, "areas": areas}
    )
