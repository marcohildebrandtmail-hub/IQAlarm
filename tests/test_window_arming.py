"""Known-open windows are ignored for exactly one complete arming session."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace as NS

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, Room, SensorConfig, WindowConfig
from iqalarm_core.models import Settings as ScenarioSettings

WINDOW = "binary_sensor.iqalarm_window_w"


def window_config(key, source):
    return WindowConfig(
        key,
        "Fenster",
        "living",
        contact_entity_id=source,
        mappings=[
            {"state": "closed", "values": {source: "off"}},
            {"state": "open", "values": {source: "on"}},
        ],
    )


def make_engine(opened=True, exit_seconds=0):
    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        rooms={"living": Room("living", "Wohnzimmer")},
        windows={"w": window_config("w", "binary_sensor.raw")},
        sensors={
            "binary_sensor.door": SensorConfig("binary_sensor.door", "entry_contact", "living"),
            "binary_sensor.motion": SensorConfig(
                "binary_sensor.motion", "interior_motion", "living"
            ),
            "binary_sensor.person": SensorConfig(
                "binary_sensor.person", "perimeter_camera", front_of=["living"]
            ),
        },
    )
    for profile in config.profiles.values():
        profile.entry_seconds = 0
        profile.exit_seconds = exit_seconds
    config.settings.startup_delay_seconds = exit_seconds
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, opened if key == WINDOW else False)
    return engine


def arm(engine, now=100):
    engine.set_profile("armed_away", now)
    engine.tick(now)


def test_open_window_arms_at_baseline_without_an_additional_setting():
    engine = make_engine()
    assert engine.config.settings.block_open_on_arm
    arm(engine)
    status = engine.snapshot(100)
    assert status["level"] == 1 and not status["confirmed"]
    assert status["ignored_windows"] == [WINDOW]
    assert WINDOW not in status["monitored_sensors"]
    assert WINDOW not in status["rooms"]["living"]["open"]
    assert status["coverage"]["current"] == 1
    assert status["raw"][WINDOW] is True


def test_closing_reopening_and_flapping_never_end_the_session_exception():
    engine = make_engine()
    arm(engine)
    for index, value in enumerate([False, True, False, True, False, True]):
        engine.feed(WINDOW, value, 101 + index)
        assert WINDOW in engine.ignored_windows
        assert not engine.confirmed and engine.level == 1
    assert WINDOW not in engine.quarantine
    assert not engine.evidence and not engine.debouncing
    engine.tick(2000)
    assert WINDOW in engine.ignored_windows


def test_ignored_window_never_confirms_camera_or_motion():
    engine = make_engine()
    arm(engine)
    engine.feed("binary_sensor.person", True, 101)
    engine.feed(WINDOW, False, 102)
    engine.feed(WINDOW, True, 103)
    engine.feed("binary_sensor.motion", True, 104)
    assert not engine.confirmed
    assert all(item.entity_id != WINDOW for item in engine.evidence)


def test_ignored_window_never_increases_a_confirmation_grade():
    from iqalarm_core.level_rules import LevelRule, RuleCondition

    engine = make_engine()
    engine.config.rules = {
        "grade": LevelRule(
            "grade", "Fenstergrad", "2", [RuleCondition(sensor_ids=[WINDOW])], confirmation_target=3
        )
    }
    for profile in engine.config.profiles.values():
        profile.rule_ids = ["grade"]
    arm(engine)
    for index, value in enumerate([False, True, False, True]):
        engine.feed(WINDOW, value, 101 + index)
    assert engine.level == 1 and not engine.rule_confirmations
    assert all(progress["current"] == 0 for progress in engine.snapshot(105)["rule_progress"])


def test_previous_window_quarantine_does_not_leave_a_room_warning_when_ignored():
    engine = make_engine()
    engine.quarantine[WINDOW] = {"reason": "quarantined_flapping", "since": 99}
    arm(engine)
    assert not engine.snapshot(100)["rooms"]["living"]["quarantined"]
    assert engine.level == 1


def test_other_doors_and_camera_confirmation_still_work():
    engine = make_engine()
    arm(engine)
    engine.feed("binary_sensor.person", True, 101)
    engine.feed("binary_sensor.door", True, 102)
    assert engine.confirmed and engine.level == 5


def test_closed_window_is_monitored_normally_and_not_ignored_later():
    engine = make_engine(False)
    arm(engine)
    assert not engine.ignored_windows
    engine.feed(WINDOW, True, 101)
    assert engine.level == 3
    assert WINDOW not in engine.ignored_windows


def test_disarming_is_the_only_automatic_release_then_next_arm_uses_current_position():
    engine = make_engine()
    arm(engine)
    engine.feed(WINDOW, False, 101)
    engine.set_profile(None, 102)
    assert not engine.ignored_windows and not engine.snapshot(102)["coverage"]["ignored_windows"]
    arm(engine, 103)
    assert not engine.ignored_windows
    engine.feed(WINDOW, True, 104)
    assert engine.level == 3


def test_opening_during_exit_delay_is_not_reclassified_as_preexisting_ventilation():
    engine = make_engine(False, exit_seconds=10)
    arm(engine)
    engine.feed(WINDOW, True, 105)
    engine.tick(110)
    assert not engine.ignored_windows and engine.level == 3


def test_open_before_exit_delay_remains_ignored_even_if_it_closes_during_the_delay():
    engine = make_engine(True, exit_seconds=10)
    arm(engine)
    engine.feed(WINDOW, False, 105)
    engine.tick(110)
    assert WINDOW in engine.ignored_windows and engine.level == 1


def test_open_doors_still_block_and_failed_activation_leaves_no_window_exception():
    engine = make_engine()
    engine.seed("binary_sensor.door", True)
    with pytest.raises(ValueError, match="Scharfschalten verhindert"):
        arm(engine)
    assert engine.profile_id is None and not engine.ignored_windows


def test_missing_window_connection_is_not_assumed_to_be_ventilation():
    engine = make_engine(None)
    with pytest.raises(ValueError, match="nicht verfügbar"):
        arm(engine)
    assert not engine.ignored_windows


@pytest.mark.parametrize("current", [False, True, None])
def test_ignored_session_survives_restart_regardless_of_current_window_position(current):
    engine = make_engine()
    arm(engine)
    saved = deepcopy(engine.persistent_state())
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, current if key == WINDOW else False)
    restored.restore(saved, 110)
    assert WINDOW in restored.ignored_windows
    assert not restored.confirmed and restored.level == 1
    restored.feed(WINDOW, True, 111)
    assert not restored.confirmed and restored.level == 1


def test_restart_does_not_ignore_windows_that_opened_after_arming():
    engine = make_engine(False)
    arm(engine)
    restored = CorrelationEngine(engine.config)
    for key in restored.sensors:
        restored.seed(key, key == WINDOW)
    restored.restore(deepcopy(engine.persistent_state()), 110)
    assert not restored.ignored_windows and restored.level == 3


def test_disarmed_saved_exception_is_not_restored():
    engine = make_engine()
    arm(engine)
    saved = deepcopy(engine.persistent_state())
    saved["profile_id"] = None
    restored = CorrelationEngine(engine.config)
    restored.restore(saved, 110)
    assert not restored.ignored_windows


def test_exception_is_not_rebound_to_another_device_or_room():
    engine = make_engine()
    arm(engine)
    saved = deepcopy(engine.persistent_state())
    restored = CorrelationEngine(engine.config)
    restored.sensors[WINDOW].source_id = "device:replacement"
    restored.seed(WINDOW, True)
    restored.restore(saved, 110)
    assert not restored.ignored_windows


def test_only_current_profiles_monitored_windows_are_marked():
    engine = make_engine()
    for rule in engine.config.rules.values():
        rule.room_ids = ["unselected"]
    engine.config.rooms["unselected"] = Room("unselected", "Anderer Raum")
    # Keep an eligible source so the profile itself remains usable.
    engine.config.sensors["binary_sensor.motion"].room_id = "unselected"
    arm(engine)
    assert not engine.ignored_windows


def test_risk_is_bounded_and_never_an_intrusion_confirmation():
    engine = make_engine()
    for index in range(4):
        window = window_config(f"extra{index}", f"binary_sensor.extra{index}")
        engine.config.windows[window.id] = window
    engine = CorrelationEngine(engine.config)
    for key in engine.sensors:
        engine.seed(key, key in engine.window_contacts)
    arm(engine)
    assert len(engine.ignored_windows) == 5
    assert engine.snapshot(100)["coverage"]["current"] == 3
    assert not engine.rule_confirmations and not engine.confirmed and engine.level == 1


def test_real_runtime_recognizes_ha_window_class_without_ignoring_a_door(tmp_path):
    from safety_support import local_runtime

    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.hass.states.set("binary_sensor.contact", "on", {"device_class": "window"})
        runtime.hass.states.set("binary_sensor.contact2", "off", {"device_class": "door"})
        await runtime.update_config(runtime.config.to_dict(), runtime.config.revision)
        assert runtime.engine.window_contacts == {"binary_sensor.contact"}
        await runtime.set_profile("armed_away")
        await runtime.hass.drain()
        assert set(runtime.engine.ignored_windows) == {"binary_sensor.contact"}
        for value in ["off", "on"]:
            runtime.hass.states.set("binary_sensor.contact", value, {"device_class": "window"})
            runtime._state_changed(
                NS(
                    data={
                        "entity_id": "binary_sensor.contact",
                        "new_state": runtime.hass.states.get("binary_sensor.contact"),
                    }
                )
            )
            await runtime.hass.drain()
            assert "binary_sensor.contact" in runtime.engine.ignored_windows
        assert runtime.store.state["ignored_windows"]
        assert not runtime.hass.services.calls

    asyncio.run(scenario())


def test_obsolete_contact_quarantine_is_cleared_when_converted_to_motion(tmp_path):
    from safety_support import local_runtime

    async def scenario():
        runtime = local_runtime(tmp_path)
        key = "binary_sensor.contact"
        runtime.engine.quarantine[key] = {"reason": "quarantined_flapping", "since": 99}
        data = runtime.config.to_dict()
        data["sensors"][key].update(role="interior_motion", activation_mode="change")
        await runtime.update_config(data, runtime.config.revision)
        assert key not in runtime.engine.quarantine
        saved = deepcopy(runtime.engine.persistent_state())
        saved["quarantine"][key] = {"reason": "quarantined_flapping", "since": 99}
        runtime.engine.restore(saved, 100)
        assert key not in runtime.engine.quarantine

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "name,device_class,expected",
    [
        ("FensterSens Test", "door", False),
        ("FensterSens Test Tür", "door", False),
        ("Fenstergriff Büro Links Tür", "door", False),
        ("Window contact", "door", False),
        ("Kontakt", "window", True),
        ("Kontakt", "door", False),
        ("Terrassentür Fensterkontakt", "window", True),
        ("Terrassentür", "window", True),
        ("Garagentor", "window", True),
        ("Tür Eingang", "door", False),
    ],
)
def test_ha_window_classification_is_independent_of_the_name(name, device_class, expected):
    from iqalarm_core.opening_types import is_window_contact

    sensor = SensorConfig("binary_sensor.contact", "entry_contact", "room", name=name)
    state = NS(attributes={"device_class": device_class})
    assert is_window_contact(sensor, state) is expected


@pytest.mark.parametrize(
    "attributes,override,original,expected",
    [
        ({"device_class": "door"}, "window", "door", True),
        ({"device_class": "window"}, "door", "window", False),
        ({"device_class": "window"}, None, "door", True),
        ({}, None, "window", True),
        ({}, None, None, False),
    ],
)
def test_ha_user_classification_takes_priority(attributes, override, original, expected):
    from iqalarm_core.opening_types import is_window_contact

    sensor = SensorConfig("binary_sensor.contact", "entry_contact", "room")
    record = NS(device_class=override, original_device_class=original)
    assert is_window_contact(sensor, NS(attributes=attributes), record) is expected


def test_lock_information_and_motion_do_not_become_windows_from_ha_metadata():
    from iqalarm_core.opening_types import is_window_contact

    for role, kind in [("interior_motion", "generic"), ("entry_contact", "window_handle")]:
        sensor = SensorConfig("binary_sensor.contact", role, "room", sensor_kind=kind)
        assert not is_window_contact(sensor, NS(attributes={"device_class": "window"}))


def test_chosen_ha_classification_is_refreshed_at_arming(tmp_path, monkeypatch):
    from safety_support import local_runtime, runtime_module

    async def scenario():
        runtime = local_runtime(tmp_path)
        key = "binary_sensor.contact"
        runtime.hass.states.set(key, "on", {"device_class": "door"})
        runtime.engine.seed(key, True)
        assert key not in runtime.engine.window_contacts
        record = NS(device_class="window", original_device_class="door")
        monkeypatch.setattr(
            runtime_module.er,
            "async_get",
            lambda hass: NS(async_get=lambda entity_id: record if entity_id == key else None),
        )
        await runtime.set_profile("armed_away")
        await runtime.hass.drain()
        assert key in runtime.engine.ignored_windows
        await runtime.set_profile(None)
        record.device_class = "door"
        with pytest.raises(ValueError, match="Scharfschalten verhindert"):
            await runtime.set_profile("armed_away")
        assert key not in runtime.engine.window_contacts
        assert not runtime.engine.ignored_windows
        assert not runtime.hass.services.calls

    asyncio.run(scenario())
