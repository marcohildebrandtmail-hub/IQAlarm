"""Physical button inputs, separate from light and relay output states."""

import hashlib
import re
from datetime import datetime


def press_types(values):
    """Prefer the initial edge; release/repeat notifications are not new presses."""
    if not isinstance(values, (list, tuple)):
        return []
    values = [value for value in values if isinstance(value, str)]
    for initial in ("initial_press", "btn_down"):
        if initial in values:
            return [initial]
    return [
        value
        for value in values
        if re.search(r"press|push|click|single|double|triple", value, re.I)
        and not re.search(r"release|repeat|stop|held|hold", value, re.I)
        and not (value == "press_long" and "press_long_start" in values)
    ]


def event_time(state):
    if state is None or state.attributes.get("restored"):
        return None
    try:
        value = datetime.fromisoformat(state.state)
        return value.timestamp() if value.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def device_source_id(device_id, subtype):
    digest = hashlib.sha256(f"{device_id}:{subtype}".encode()).hexdigest()[:24]
    return f"event.iqalarm_button_{digest}"


async def mqtt_button_sources(hass):
    """List discovered MQTT device actions without creating HA entities."""
    if "mqtt" not in hass.data:
        return []
    from homeassistant.helpers import device_registry

    devices = [
        device
        for device in device_registry.async_get(hass).devices.values()
        if any(domain == "mqtt" for domain, _ in device.identifiers)
    ]
    if not devices:
        return []
    from homeassistant.components.mqtt.device_trigger import async_get_triggers

    sources = []
    for device in devices:
        for trigger in await async_get_triggers(hass, device.id):
            subtype = trigger.get("subtype")
            if trigger.get("type") != "action" or not press_types([subtype]):
                continue
            sources.append(
                {
                    "entity_id": device_source_id(device.id, subtype),
                    "name": f"{device.name_by_user or device.name or device.id} · {subtype}",
                    "state": "ready",
                    "platform": "mqtt",
                    "device_id": device.id,
                    "area_id": device.area_id,
                    "options": [subtype],
                    "attributes": {},
                    "role": "interior_motion",
                    "sensor_kind": "light_switch",
                    "activation_mode": "press",
                    "source_id": f"device:{device.id}",
                    "active_states": [subtype],
                    "attribute": None,
                    "active_above": None,
                    "device_trigger": {
                        "platform": "device",
                        "domain": "mqtt",
                        "device_id": device.id,
                        "type": "action",
                        "subtype": subtype,
                    },
                }
            )
    return sources
