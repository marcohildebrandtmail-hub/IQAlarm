"""Dynamically maintained room status entities."""

import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import SIGNAL_UPDATE
from .entity import IQAlarmEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    known: dict[str, list] = {}
    runtime = entry.runtime_data
    async_add_entities([IQAlarmActiveSensor(runtime)])

    @callback
    def add_rooms() -> None:
        registry = er.async_get(hass)
        for removed in set(known) - runtime.config.rooms.keys():
            for entity in known.pop(removed):
                if entity.entity_id and registry.async_get(entity.entity_id):
                    registry.async_remove(entity.entity_id)
        additions = []
        for room in runtime.config.rooms.values():
            if room.id not in known:
                known[room.id] = list(
                    IQAlarmRoomSensor(runtime, room.id, room.name, kind)
                    for kind in ("room", "perimeter", "suspicion")
                )
                additions.extend(known[room.id])
        if additions:
            async_add_entities(additions)

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, add_rooms))
    add_rooms()

    windows = {}

    @callback
    def add_windows():
        registry = er.async_get(hass)
        for removed in set(windows) - runtime.config.windows.keys():
            entity = windows.pop(removed)
            if entity.entity_id and registry.async_get(entity.entity_id):
                registry.async_remove(entity.entity_id)
        additions = []
        for window in runtime.config.windows.values():
            if window.id not in windows:
                windows[window.id] = IQAlarmWindowOpening(runtime, window.id)
                additions.append(windows[window.id])
        if additions:
            async_add_entities(additions)

    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_UPDATE, add_windows))
    add_windows()


class IQAlarmWindowOpening(IQAlarmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, runtime, window_id):
        super().__init__(runtime, f"window_{window_id}_opening")
        self.window_id = window_id

    @property
    def name(self):
        window = self.runtime.config.windows.get(self.window_id)
        return f"{window.name if window else self.window_id} Fenster geöffnet"

    @property
    def available(self):
        window = self.runtime.config.windows.get(self.window_id)
        return bool(
            window
            and window.enabled
            and self.runtime.windows[self.window_id].reading.get("opening") is not None
        )

    @property
    def is_on(self):
        return self.runtime.windows[self.window_id].reading["opening"] if self.available else None


class IQAlarmRoomSensor(IQAlarmEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, runtime, room_id: str, room_name: str, kind: str) -> None:
        super().__init__(runtime, f"room_{room_id}_{kind}")
        self.room_id = room_id
        self.kind = kind
        self._set_name(room_name)

    def _set_name(self, name: str) -> None:
        suffix = {"room": "Raumstatus", "perimeter": "Vorfeld", "suspicion": "Verdacht"}[self.kind]
        self._attr_name = f"{name} {suffix}"

    @property
    def available(self) -> bool:
        return self.room_id in self.runtime.config.rooms

    @property
    def name(self) -> str:
        room = self.runtime.config.rooms.get(self.room_id)
        if room:
            self._set_name(room.name)
        return self._attr_name

    @property
    def is_on(self) -> bool:
        status = self.runtime.engine.room_status(self.room_id, time.time())
        if self.kind == "room":
            return status["suspicion"] or status["confirmed"] or bool(status["quarantined"])
        return status[self.kind]

    @property
    def extra_state_attributes(self) -> dict:
        return self.runtime.engine.room_status(self.room_id, time.time())


class IQAlarmActiveSensor(IQAlarmEntity, BinarySensorEntity):
    _attr_name = "Aktiv"
    _attr_icon = "mdi:shield-check"

    def __init__(self, runtime):
        super().__init__(runtime, "active")

    @property
    def is_on(self):
        return self.runtime.engine.reactions_enabled
