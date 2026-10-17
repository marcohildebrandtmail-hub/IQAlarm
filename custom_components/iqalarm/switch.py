"""Presence simulation hook exposed as a native HA switch."""

from homeassistant.components.switch import SwitchEntity

from .entity import IQAlarmEntity
from .models import Configuration

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([IQAlarmSimulationSwitch(entry.runtime_data)])


class IQAlarmSimulationSwitch(IQAlarmEntity, SwitchEntity):
    _attr_translation_key = "simulation"
    _attr_icon = "mdi:home-clock-outline"

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "simulation")

    @property
    def is_on(self) -> bool:
        return self.runtime.config.settings.simulation_enabled

    async def _set(self, enabled: bool) -> None:
        async with self.runtime.lock:
            candidate = Configuration.from_dict(self.runtime.config.to_dict())
            candidate.settings.simulation_enabled = enabled
            candidate.revision += 1
            async with self.runtime.storage_lock:
                await self.runtime.store.async_save(config=candidate)
            self.runtime.engine.config = candidate
            self.runtime.publish()
        if not enabled:
            for target in self.runtime.dispatcher.simulation_outputs:
                if target in self.runtime.dispatcher.outputs:
                    self.runtime.dispatcher.outputs[target]["until"] = 0
            await self.runtime.dispatcher.cleanup()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
