"""Verify an existing installation upgrades and arms in disposable HA Core."""

from copy import deepcopy


async def verify_arming_availability(hass, entry):
    from custom_components.iqalarm.store import IQAlarmStore

    original = deepcopy(entry.runtime_data.config.to_dict())
    legacy = deepcopy(original)
    legacy["settings"].pop("arming_policy_version")
    legacy["settings"]["block_unavailable_on_arm"] = True
    assert await hass.config_entries.async_unload(entry.entry_id)
    store = IQAlarmStore(hass)
    await store._store.async_save({"config": legacy, "state": {}, "outputs": {}})
    hass.states.async_set("binary_sensor.window", "unavailable")
    try:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        runtime = entry.runtime_data
        assert runtime.config.settings.block_unavailable_on_arm is False
        saved = await runtime.store._store.async_load()
        expected = deepcopy(legacy)
        expected["settings"].update(block_unavailable_on_arm=False, arming_policy_version=1)
        assert saved["config"] == expected
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_night",
            {"entity_id": "alarm_control_panel.iqalarm"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert runtime.engine.reactions_enabled
        assert runtime.engine.raw["binary_sensor.window"] is None
        assert "binary_sensor.window" not in runtime.engine.ignored_windows
        hass.states.async_set("binary_sensor.person", "on")
        await hass.async_block_till_done()
        assert runtime.engine.level > 0
        hass.states.async_set("binary_sensor.window", "off")
        await hass.async_block_till_done()
        assert runtime.engine.raw["binary_sensor.window"] is False
        # An explicit choice after the upgrade is not migrated again on restart.
        await runtime.set_profile(None, "2468")
        strict = runtime.config.to_dict()
        strict["settings"]["block_unavailable_on_arm"] = True
        await runtime.update_config(strict, runtime.config.revision)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.config.settings.block_unavailable_on_arm is True
    finally:
        runtime = entry.runtime_data
        await runtime.set_profile(None, "2468")
        for source in ("binary_sensor.window", "binary_sensor.person"):
            hass.states.async_set(source, "off")
        await hass.async_block_till_done()
        await runtime.update_config(original, runtime.config.revision)
    print(
        "PASS persisted availability-policy upgrade, native arming with sensor outage, remaining protection and explicit opt-in after restart",
        flush=True,
    )
