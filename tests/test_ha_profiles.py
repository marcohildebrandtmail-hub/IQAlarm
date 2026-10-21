"""Native HA buttons retain profile identity and all arming/disarming guards."""

import ast
import asyncio
from copy import deepcopy
from enum import IntFlag, StrEnum
from pathlib import Path

import pytest
from iqalarm_core.models import Configuration, Profile
from safety_support import HAError, local_runtime, models


def test_new_default_profiles_match_requested_order_names_and_symbols():
    config = Configuration()
    config.validate()
    assert [p.name for p in config.profiles.values()] == ["Nacht", "Abwesend", "Urlaub", "Besuch"]
    assert [p.icon for p in config.profiles.values()] == [
        "mdi:weather-night",
        "mdi:home-export-outline",
        "mdi:palm-tree",
        "mdi:account-group-outline",
    ]
    assert config.ha_profile_ids == {
        "armed_home": "armed_home",
        "armed_night": "armed_night",
        "armed_away": "armed_away",
        "armed_vacation": "armed_vacation",
    }
    assert "armed_custom_bypass" not in config.ha_profile_ids


def test_existing_besuch_is_associated_without_deleting_old_home_or_changing_policy():
    config = Configuration()
    config.profiles["armed_home"].name = "Zuhause"
    config.profiles["user_guests"] = Profile(name="Besuch", room_ids=[], sensor_ids=[])
    before = {key: deepcopy(p) for key, p in config.profiles.items()}
    data = config.to_dict()
    data.pop("ha_profile_ids")
    migrated = Configuration.from_dict(data)
    assert migrated.ha_profile_ids["armed_home"] == "user_guests"
    assert set(migrated.profiles) == set(before)
    for key, profile in before.items():
        assert migrated.profiles[key].motion_mode == profile.motion_mode
        assert migrated.profiles[key].room_ids == profile.room_ids
        assert migrated.profiles[key].sensor_ids == profile.sensor_ids
        assert migrated.profiles[key].name == profile.name


def test_native_identity_survives_renaming_sorting_and_a_new_profile_using_old_name():
    config = Configuration()
    config.validate()
    mapping = deepcopy(config.ha_profile_ids)
    config.profiles["armed_home"].name = "Gästeabend"
    config.profiles["extra"] = Profile(name="Besuch")
    config.profiles = dict(reversed(list(config.profiles.items())))
    restored = Configuration.from_dict(config.to_dict())
    assert restored.ha_profile_ids == mapping
    assert restored.ha_profile_ids["armed_home"] != "extra"


@pytest.mark.parametrize(
    "mapping",
    [
        [],
        {"wrong": "armed_night"},
        {"armed_home": 42},
        {"armed_home": "armed_home", "armed_custom_bypass": "armed_home"},
    ],
)
def test_invalid_native_assignments_are_rejected(mapping):
    with pytest.raises(ValueError, match="Profilzuordnung"):
        Configuration(ha_profile_ids=mapping).validate()


def test_custom_choice_roundtrips_and_deleted_profile_removes_shortcut_without_fallback():
    config = Configuration()
    config.validate()
    config.profiles["custom"] = Profile(name="Werkstatt")
    config.ha_profile_ids["armed_custom_bypass"] = "custom"
    restored = Configuration.from_dict(config.to_dict())
    assert restored.ha_profile_ids["armed_custom_bypass"] == "custom"
    del restored.profiles["custom"]
    restored.validate()
    assert "armed_custom_bypass" not in restored.ha_profile_ids
    assert "armed_home" in restored.ha_profile_ids


class Features(IntFlag):
    ARM_HOME = 1
    ARM_AWAY = 2
    ARM_NIGHT = 4
    ARM_CUSTOM_BYPASS = 16
    ARM_VACATION = 32


class States(StrEnum):
    DISARMED = "disarmed"
    ARMED_HOME = "armed_home"
    ARMED_NIGHT = "armed_night"
    ARMED_AWAY = "armed_away"
    ARMED_VACATION = "armed_vacation"
    ARMED_CUSTOM_BYPASS = "armed_custom_bypass"
    TRIGGERED = "triggered"
    ARMING = "arming"
    PENDING = "pending"


def panel_type():
    """Load unchanged entity methods with HA infrastructure bases substituted."""
    path = Path(__file__).resolve().parents[1] / "custom_components/iqalarm/alarm_control_panel.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [
        node
        for node in tree.body
        if not (
            isinstance(node, ast.ImportFrom)
            and ((node.module or "").startswith("homeassistant") or node.module == "entity")
        )
    ]

    class Entity:
        def __init__(self, runtime, key):
            self.runtime = runtime

    namespace = {
        "__package__": "iqalarm_core",
        "IQAlarmEntity": Entity,
        "AlarmControlPanelEntity": object,
        "AlarmControlPanelEntityFeature": Features,
        "AlarmControlPanelState": States,
        "CodeFormat": type("CodeFormat", (), {"NUMBER": "number"}),
    }
    exec(compile(tree, str(path), "exec"), namespace)
    return namespace["IQAlarmPanel"]


def setup_native(tmp_path):
    runtime = local_runtime(tmp_path)
    for profile in runtime.config.profiles.values():
        profile.motion_mode = "always"
        profile.contacts_enabled = True
    runtime.config.profiles["workshop"] = models.Profile(name="Werkstatt")
    runtime.config.ha_profile_ids["armed_custom_bypass"] = "workshop"
    return runtime, panel_type()(runtime)


@pytest.mark.parametrize("mode", list(States)[:6][1:])
def test_native_buttons_activate_exact_assigned_profile_and_report_matching_state(tmp_path, mode):
    async def scenario():
        runtime, panel = setup_native(tmp_path)
        runtime.engine.last_profile_id = "armed_vacation"  # away must ignore generic last-profile
        method = getattr(panel, "async_alarm_" + mode.replace("armed_", "arm_"))
        await method()
        assert runtime.engine.profile_id == runtime.config.ha_profile_ids[mode]
        assert panel.alarm_state == mode
        assert panel.supported_features == sum(Features)
        runtime.engine.arming_until = 9999999999
        assert panel.alarm_state == "arming"
        runtime.engine.arming_until = None
        runtime.engine.pending_until = 9999999999
        assert panel.alarm_state == "pending"
        runtime.engine.pending_until = None
        runtime.engine.severity = 3
        runtime.engine.stage_id = "3"
        assert panel.alarm_state == "triggered"
        await panel.async_alarm_disarm()
        assert panel.alarm_state == "disarmed"
        await runtime.hass.drain()

    asyncio.run(scenario())


def test_missing_disabled_and_deleted_custom_targets_never_activate_another_profile(tmp_path):
    async def scenario():
        runtime, panel = setup_native(tmp_path)
        del runtime.config.ha_profile_ids["armed_custom_bypass"]
        with pytest.raises(ValueError, match="festlegen"):
            await panel.async_alarm_arm_custom_bypass()
        runtime.config.ha_profile_ids["armed_custom_bypass"] = "workshop"
        runtime.config.profiles["workshop"].reactions_enabled = False
        assert not panel.supported_features & Features.ARM_CUSTOM_BYPASS
        with pytest.raises(ValueError, match="festlegen"):
            await panel.async_alarm_arm_custom_bypass()
        del runtime.config.profiles["workshop"]
        runtime.config.validate()
        with pytest.raises(ValueError, match="festlegen"):
            await panel.async_alarm_arm_custom_bypass()
        assert runtime.engine.profile_id is None

    asyncio.run(scenario())


def test_native_controls_keep_profile_change_open_door_and_disarm_guards(tmp_path):
    async def scenario():
        runtime, panel = setup_native(tmp_path)
        runtime.engine.seed("binary_sensor.contact", True)
        with pytest.raises(ValueError, match="offen"):
            await panel.async_alarm_arm_away()
        runtime.engine.seed("binary_sensor.contact", False)
        await panel.async_alarm_arm_home()
        with pytest.raises(ValueError, match="entschärfen"):
            await panel.async_alarm_arm_night()
        assert runtime.engine.profile_id == runtime.config.ha_profile_ids["armed_home"]

        async def denied(code):
            raise HAError("Ungültige PIN")

        runtime.validate_code = denied
        with pytest.raises(HAError, match="PIN"):
            await panel.async_alarm_disarm("wrong")
        assert panel.alarm_state == "armed_home"
        await runtime.hass.drain()

    asyncio.run(scenario())


def test_custom_profile_activated_inside_iqalarm_keeps_custom_native_state(tmp_path):
    async def scenario():
        runtime, panel = setup_native(tmp_path)
        del runtime.config.ha_profile_ids["armed_custom_bypass"]
        await runtime.set_profile("workshop")
        assert panel.alarm_state == "armed_custom_bypass"
        assert panel.supported_features & Features.ARM_CUSTOM_BYPASS
        await runtime.hass.drain()

    asyncio.run(scenario())
