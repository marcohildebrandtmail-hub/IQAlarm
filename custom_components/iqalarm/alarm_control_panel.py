"""Native Home Assistant alarm entity; suspicion is not a triggered alarm."""

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)

from .entity import IQAlarmEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([IQAlarmPanel(entry.runtime_data)])


class IQAlarmPanel(IQAlarmEntity, AlarmControlPanelEntity):
    _attr_name = None
    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "alarm")
        self._attr_code_format = CodeFormat.NUMBER if runtime.entry.data.get("pin_hash") else None

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        engine = self.runtime.engine
        if not engine.reactions_enabled:
            return AlarmControlPanelState.DISARMED
        if engine.confirmed and engine.level > 0:
            return AlarmControlPanelState.TRIGGERED
        if engine.pending_until is not None:
            return AlarmControlPanelState.PENDING
        if engine.arming_until is not None:
            return AlarmControlPanelState.ARMING
        return AlarmControlPanelState.ARMED_AWAY

    @property
    def extra_state_attributes(self) -> dict:
        engine = self.runtime.engine
        return {
            "alarm_level": int(engine.level),
            "active": engine.reactions_enabled,
            "stage_id": engine.stage_id,
            "stage_name": self.runtime.config.stage(engine.stage_id).name,
            "profile_id": engine.evaluation_profile_id,
            "profile_name": (
                engine.config.profiles[engine.evaluation_profile_id].name
                if engine.evaluation_profile_id in engine.config.profiles
                else None
            ),
            "quarantined_flapping": list(engine.quarantine),
            "entry_deadline": engine.pending_until,
            "exit_deadline": engine.arming_until,
            "trigger_chain": [e.entity_id for e in engine.breach_chain],
        }

    async def async_alarm_disarm(self, code=None) -> None:
        await self.runtime.set_profile(None, code)

    async def async_alarm_arm_away(self, code=None) -> None:
        await self.runtime.activate()
