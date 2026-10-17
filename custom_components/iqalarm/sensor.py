"""Alarm level, quarantined inputs and last significant event."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .entity import IQAlarmEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities(
        [IQAlarmSensor(entry.runtime_data, key) for key in ("level", "flapping", "last_event")]
    )


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
        }[key]

    @property
    def native_value(self):
        engine = self.runtime.engine
        if self.key == "level":
            return int(engine.level)
        if self.key == "flapping":
            return len(engine.quarantine)
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
        return {"mode": engine.mode.value}
