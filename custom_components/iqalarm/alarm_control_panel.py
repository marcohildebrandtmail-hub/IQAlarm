"""Native Home Assistant alarm entity; suspicion is not a triggered alarm."""

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)

from .entity import IQAlarmEntity
from .ha_profiles import HA_CUSTOM_MODE

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([IQAlarmPanel(entry.runtime_data)])


class IQAlarmPanel(IQAlarmEntity, AlarmControlPanelEntity):
    _attr_name = None
    _attr_code_arm_required = False

    def __init__(self, runtime) -> None:
        super().__init__(runtime, "alarm")
        self._attr_code_format = CodeFormat.NUMBER if runtime.entry.data.get("pin_hash") else None

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        features = AlarmControlPanelEntityFeature(0)
        for mode, key in (self.runtime.config.ha_profile_ids or {}).items():
            profile = self.runtime.config.profiles.get(key)
            if profile and profile.reactions_enabled:
                features |= getattr(
                    AlarmControlPanelEntityFeature, mode.upper().replace("ARMED_", "ARM_")
                )
        # A custom profile activated inside IQAlarm must still display as custom.
        engine = self.runtime.engine
        if engine.reactions_enabled and engine.profile_id not in {
            key
            for mode, key in (self.runtime.config.ha_profile_ids or {}).items()
            if mode != HA_CUSTOM_MODE
        }:
            features |= AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        return features

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
        mode = next(
            (
                mode
                for mode, key in (self.runtime.config.ha_profile_ids or {}).items()
                if key == engine.profile_id
            ),
            HA_CUSTOM_MODE,
        )
        return AlarmControlPanelState(mode)

    @property
    def extra_state_attributes(self) -> dict:
        engine = self.runtime.engine
        is_active = bool(engine.reactions_enabled and engine.profile_id)
        stage_id = engine.stage_id if is_active else self.runtime.config.stages[0].id
        return {
            "alarm_level": int(engine.level) if is_active else 0,
            "active": engine.reactions_enabled,
            "stage_id": stage_id,
            "stage_name": self.runtime.config.stage(stage_id).name,
            "profile_id": engine.evaluation_profile_id,
            "profile_name": (
                engine.config.profiles[engine.evaluation_profile_id].name
                if engine.evaluation_profile_id in engine.config.profiles
                else None
            ),
            "quarantined_flapping": list(engine.quarantine),
            "entry_deadline": engine.pending_until,
            "exit_deadline": engine.arming_until,
            "trigger_chain": [e.entity_id for e in engine.breach_chain] if is_active else [],
        }

    async def async_alarm_disarm(self, code=None) -> None:
        await self.runtime.set_profile(None, code)

    async def async_alarm_arm_away(self, code=None) -> None:
        await self.runtime.arm_ha_mode("armed_away", code)

    async def async_alarm_arm_home(self, code=None) -> None:
        await self.runtime.arm_ha_mode("armed_home", code)

    async def async_alarm_arm_night(self, code=None) -> None:
        await self.runtime.arm_ha_mode("armed_night", code)

    async def async_alarm_arm_vacation(self, code=None) -> None:
        await self.runtime.arm_ha_mode("armed_vacation", code)

    async def async_alarm_arm_custom_bypass(self, code=None) -> None:
        await self.runtime.arm_ha_mode(HA_CUSTOM_MODE, code)
