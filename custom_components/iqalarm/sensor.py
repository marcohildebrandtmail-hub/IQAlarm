"""Alarm level, quarantined inputs and last significant event."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_UPDATE
from .entity import IQAlarmEntity
from .models import WINDOW_STATES

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        [
            IQAlarmSensor(entry.runtime_data, key)
            for key in ("level", "flapping", "last_event", "profile")
        ]
    )
    known = {}
    runtime = entry.runtime_data

    @callback
    def add_windows():
        registry = er.async_get(hass)
        for removed in set(known) - runtime.config.windows.keys():
            entity = known.pop(removed)
            if entity.entity_id and registry.async_get(entity.entity_id):
                registry.async_remove(entity.entity_id)
        additions = []
        for window in runtime.config.windows.values():
            if window.id not in known:
                known[window.id] = IQAlarmWindowSensor(runtime, window.id)
                additions.append(known[window.id])
        if additions:
            async_add_entities(additions)

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, add_windows))
    add_windows()


class IQAlarmWindowSensor(IQAlarmEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "window_position"
    _attr_options = list(WINDOW_STATES) + ["unknown_position", "settling"]
    _attr_icon = "mdi:window-closed-variant"

    def __init__(self, runtime, window_id):
        super().__init__(runtime, f"window_{window_id}_position")
        self.window_id = window_id

    @property
    def name(self):
        window = self.runtime.config.windows.get(self.window_id)
        return f"{window.name if window else self.window_id} Fensterstellung"

    @property
    def available(self):
        return bool(
            self.window_id in self.runtime.config.windows
            and self.runtime.config.windows[self.window_id].enabled
            and self.runtime.windows[self.window_id].reading.get("available")
        )

    @property
    def native_value(self):
        return self.runtime.windows[self.window_id].reading["state"] if self.available else None

    @property
    def extra_state_attributes(self):
        tracker = self.runtime.windows.get(self.window_id)
        return {**tracker.reading, "room_id": tracker.window.room_id} if tracker else {}


class IQAlarmSensor(IQAlarmEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime, key: str) -> None:
        super().__init__(runtime, key)
        self.key = key
        self._attr_translation_key = key
        self._attr_icon = {
            "level": "mdi:shield-half-full",
            "flapping": "mdi:connection",
            "last_event": "mdi:timeline-clock-outline",
            "profile": "mdi:account-shield-outline",
        }[key]

    @property
    def native_value(self):
        engine = self.runtime.engine
        is_active = bool(engine.reactions_enabled and engine.profile_id)
        if self.key == "level":
            return int(engine.level) if is_active else 0
        if self.key == "flapping":
            return len(engine.quarantine)
        if self.key == "profile":
            return (
                engine.config.profiles[engine.evaluation_profile_id].name
                if engine.evaluation_profile_id in engine.config.profiles
                else "Aus"
            )
        return engine.events[0].kind if engine.events else "none"

    @property
    def extra_state_attributes(self):
        engine = self.runtime.engine
        if self.key == "flapping":
            return {"entities": list(engine.quarantine)}
        if self.key == "last_event":
            return {
                "reason": engine.events[0].reason if engine.events else "",
                "timestamp": engine.events[0].timestamp if engine.events else None,
            }
        is_active = bool(engine.reactions_enabled and engine.profile_id)
        stage_id = engine.stage_id if is_active else self.runtime.config.stages[0].id
        return {
            "mode": engine.mode.value,
            "stage_id": stage_id,
            "stage_name": self.runtime.config.stage(stage_id).name,
            "active": engine.reactions_enabled,
            "profile_id": engine.profile_id,
            "profile_name": (
                engine.config.profiles[engine.evaluation_profile_id].name
                if engine.evaluation_profile_id in engine.config.profiles
                else None
            ),
        }
