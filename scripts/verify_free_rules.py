"""Exercise free level conditions and profile-isolated actions in real HA Core."""

import asyncio
from copy import deepcopy
from dataclasses import asdict

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect


async def verify_free_rules(hass, entry, calls):
    from custom_components.iqalarm.level_rules import LevelRule, RuleCondition
    from custom_components.iqalarm.models import default_stages

    runtime = entry.runtime_data
    await runtime.set_profile(None, "2468")
    original = deepcopy(runtime.config.to_dict())
    person, other, frame, motion = [
        f"binary_sensor.qa_free_{name}" for name in ("person", "other", "frame", "motion")
    ]
    for key in (person, other, frame, motion):
        hass.states.async_set(key, "off")
    data = deepcopy(original)
    data["stages"] = [asdict(s) for s in default_stages()]
    data["secure_stage_id"] = "1"
    data["rules"] = {
        r.id: asdict(r)
        for r in [
            LevelRule(
                "outside", "Person außen", "2", [RuleCondition(sensor_ids=[person, other])], 30
            ),
            LevelRule(
                "two",
                "Zwei Außenquellen",
                "3",
                [RuleCondition(sensor_ids=[person, other], count=2)],
                30,
            ),
            LevelRule("single", "Öffnung einzeln", "3", [RuleCondition(sensor_ids=[frame])], 30),
            LevelRule(
                "flap", "Prellen", "3", [RuleCondition(sensor_ids=[frame], event="flapping")], 30
            ),
            LevelRule(
                "breach",
                "Öffnung und neue Bewegung",
                "5",
                [RuleCondition(sensor_ids=[frame]), RuleCondition(sensor_ids=[motion])],
                30,
                delay_seconds=0.3,
                ordered=True,
            ),
        ]
    }
    for profile in data["profiles"].values():
        profile["rule_ids"] = []
        profile["action_ids"] = None
    data["profiles"]["qa_free_night"] = {
        "name": "Freie Regeln Nacht",
        "rule_ids": list(data["rules"]),
    }
    data["profiles"]["qa_free_away"] = {
        "name": "Freie Regeln Abwesend",
        "rule_ids": list(data["rules"]),
    }
    data["actions"] = {
        "night": {
            "id": "night",
            "level": "3",
            "kind": "notify",
            "target": "notify.test_phone",
            "message": "Nur freie Nacht",
            "profile_ids": ["qa_free_night"],
        },
        "away": {
            "id": "away",
            "level": "3",
            "kind": "notify",
            "target": "notify.test_phone",
            "message": "Nur frei abwesend",
            "profile_ids": ["qa_free_away"],
        },
        "alarm": {
            "id": "alarm",
            "level": "5",
            "kind": "siren",
            "target": "siren.test",
            "duration": 2,
            "profile_ids": ["qa_free_night"],
        },
        "secure": {
            "id": "secure",
            "level": "1",
            "kind": "notify",
            "target": "notify.test_phone",
            "message": "Nacht sicher",
            "profile_ids": ["qa_free_night"],
        },
    }
    for key, role in (
        (person, "perimeter_camera"),
        (other, "perimeter_camera"),
        (frame, "entry_contact"),
        (motion, "interior_motion"),
    ):
        data["sensors"][key] = {
            "entity_id": key,
            "role": role,
            "room_id": "living",
            "front_of": ["living"] if role.startswith("perimeter") else [],
        }

    async def settle():
        await hass.async_block_till_done()
        await asyncio.wait_for(asyncio.gather(runtime.queue.join(), runtime.urgent_queue.join()), 5)
        if runtime.cleanup_tasks:
            await asyncio.wait_for(asyncio.gather(*list(runtime.cleanup_tasks)), 5)

    try:
        await runtime.update_config(data, runtime.config.revision)
        calls.clear()
        await runtime.set_profile("qa_free_night")
        await settle()
        assert runtime.engine.level == 1
        assert any(c[2].get("message") == "Nacht sicher" for c in calls)
        calls.clear()
        hass.states.async_set(person, "on")
        await settle()
        assert runtime.engine.level == 2
        hass.states.async_set(other, "on")
        await settle()
        assert runtime.engine.level == 3 and not runtime.engine.confirmed
        assert any(c[2].get("message") == "Nur freie Nacht" for c in calls)
        assert not any(c[2].get("message") == "Nur frei abwesend" for c in calls)
        plan = await runtime.test_level("3", profile_id="qa_free_away")
        assert {a["id"] for a in plan} == {"away"}
        await runtime.set_profile(None, "2468")
        for key in (person, other):
            hass.states.async_set(key, "off")
        await settle()
        await runtime.set_profile("qa_free_night")
        calls.clear()
        hass.states.async_set(frame, "on")
        await settle()
        hass.states.async_set(motion, "on")
        await settle()
        assert runtime.engine.pending_until is not None and not runtime.engine.confirmed
        assert not any(c[:2] == ("siren", "turn_on") for c in calls)
        confirmed = asyncio.Event()

        @callback
        def observe_confirmation():
            if runtime.engine.confirmed:
                confirmed.set()

        cancel = async_dispatcher_connect(hass, "iqalarm_update", observe_confirmation)
        try:
            observe_confirmation()
            await asyncio.wait_for(confirmed.wait(), 3)
        finally:
            cancel()
        await settle()
        assert runtime.engine.level == 5 and any(c[:2] == ("siren", "turn_on") for c in calls)
        await runtime.set_profile(None, "2468")
        hass.states.async_set(frame, "off")
        hass.states.async_set(motion, "off")
        await settle()
        await runtime.set_profile("qa_free_night")
        calls.clear()
        for value in ("on", "off", "on", "off", "on"):
            hass.states.async_set(frame, value)
            await settle()
        assert frame in runtime.engine.quarantine and not runtime.engine.confirmed
        assert not any(c[:2] == ("siren", "turn_on") for c in calls)
    finally:
        await runtime.set_profile(None, "2468")
        for key in (person, other, frame, motion):
            hass.states.async_set(key, "off")
        await settle()
        await runtime.update_config(original, runtime.config.revision)
    print(
        "PASS free level rules, independent outdoor sources, profile-isolated real/dry actions, secure actions, delay and flap safety",
        flush=True,
    )


async def verify_rule_storage_migration(hass, entry):
    """Load a real pre-rules storage document, verify its backup, then restore the fixture."""
    from custom_components.iqalarm.store import IQAlarmStore

    original = deepcopy(entry.runtime_data.config.to_dict())
    assert await hass.config_entries.async_unload(entry.entry_id)
    legacy = deepcopy(original)
    legacy.pop("rules", None)
    store = IQAlarmStore(hass)
    await store._store.async_save({"config": legacy, "state": {}, "outputs": {}})
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    migrated = entry.runtime_data
    assert migrated.config.rules is not None
    backup = await migrated.store._migration_backup.async_load()
    assert backup["config"] == legacy
    saved = await migrated.store._store.async_load()
    assert saved["config"]["rules"] == migrated.config.to_dict()["rules"]
    for name in ("rooms", "sensors", "windows", "floorplans", "stages"):
        assert migrated.config.to_dict()[name] == original[name]
    await migrated.update_config(original, migrated.config.revision)
    print(
        "PASS real storage migration, private pre-rules backup and persisted level conditions",
        flush=True,
    )
