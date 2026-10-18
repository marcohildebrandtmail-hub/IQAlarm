"""Six display stages remain independent of confirmation and reaction permission."""

import asyncio
import time

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, default_stages
from safety_support import local_runtime, models, runtime_module


@pytest.fixture
def six(config):
    config.stages = default_stages()
    config.secure_stage_id = "1"
    for profile in config.profiles.values():
        profile.stage_targets.clear()
    engine = CorrelationEngine(config)
    for sensor_id in engine.sensors:
        engine.seed(sensor_id, False)
    return engine


def test_new_install_has_requested_names_colors_and_targets():
    config = Configuration()
    config.validate()
    assert [s.name for s in config.stages] == [
        "Deaktiviert",
        "Sicher",
        "Bewegung Außen",
        "Erste Sensorauslösung / Fehlerfall",
        "Bewegung Innen",
        "ALARM!!!",
    ]
    assert [s.color for s in config.stages] == [
        "#ffffff",
        "#64bc29",
        "#08ba1d",
        "#cad345",
        "#bc2929",
        "#8000ff",
    ]
    assert config.profiles["armed_night"].stage_targets == {
        "perimeter": "2",
        "single": "3",
        "motion": "4",
        "fault": "3",
        "flapping": "3",
        "perimeter_contact": "5",
        "contact_motion": "5",
        "multi_contact": "5",
        "multi_motion": "5",
        "immediate": "5",
    }
    assert config.stage("5").requires_confirmation


def test_inactive_zero_active_secure_one_and_return(six):
    assert six.level == 0
    six.set_profile("armed_night", 100)
    assert six.level == 1 and six.secure
    six.feed("binary_sensor.window", True, 101)
    assert six.level == 3 and not six.confirmed
    six.tick(162)
    assert six.level == 1 and six.secure
    six.set_profile(None, 163)
    assert six.level == 0


def test_perimeter_two_then_related_window_confirms_five(six):
    six.set_profile("armed_night", 100)
    six.feed("binary_sensor.terrace", True, 101)
    assert six.level == 2 and not six.confirmed
    six.feed("binary_sensor.window", True, 141)
    assert six.level == 5 and six.confirmed and six.latched


def test_night_motion_stays_secure_until_related_opening(six):
    six.set_profile("armed_night", 100)
    six.feed("binary_sensor.bed_motion", True, 101)
    six.feed("binary_sensor.hall_motion", True, 102)
    assert six.level == 1 and not six.evidence
    six.feed("binary_sensor.window", True, 103)
    assert six.level == 3
    six.feed("binary_sensor.motion", True, 115)
    assert six.level == 5 and six.confirmed


def test_away_interior_four_does_not_confirm_unrelated_window(six):
    six.set_profile("armed_away", 100)
    six.feed("binary_sensor.window", True, 101)
    six.feed("binary_sensor.bed_motion", True, 103)
    assert six.level == 4 and not six.confirmed and not six.latched
    assert six.room_status("living", 103)["level"] == 3
    assert six.room_status("bed", 103)["level"] == 4
    six.tick(165)
    assert six.level == 1


def test_flapping_and_connection_fault_are_three_without_confirmation(six):
    six.set_profile("armed_night", 100)
    for index in range(5):
        six.feed("binary_sensor.lock", index % 2 == 0, 101 + index * 2)
    assert "binary_sensor.lock" in six.quarantine
    assert six.level == 3 and not six.confirmed
    assert any(event.kind == "quarantined_flapping" for event in six.events)
    six.clear_quarantine(None, 111)
    six.tick(180)
    six.feed("binary_sensor.motion", None, 181)
    assert six.level == 3 and six.room_status("living", 181)["level"] == 3
    six.feed("binary_sensor.motion", False, 182)
    assert six.level == 1 and not six.evidence


def test_live_observation_uses_levels_without_reactions_or_latch(six):
    six.feed("binary_sensor.terrace", True, 100)
    assert six.level == 2 and not six.reactions_enabled
    six.feed("binary_sensor.window", True, 101)
    assert six.level == 5 and six.confirmed and not six.latched
    assert not any(event.reactions_enabled for event in six.events)
    six.tick(300)
    assert six.level == 0


def test_disabled_rule_does_not_mark_breach(six):
    six.config.profiles["armed_night"].stage_targets["contact_motion"] = "0"
    six.set_profile("armed_night", 100)
    six.feed("binary_sensor.window", True, 101)
    six.feed("binary_sensor.motion", True, 113)
    assert not six.confirmed and six.level == 4


def test_legacy_stage_ids_actions_and_baseline_survive(config):
    data = config.to_dict()
    data.pop("secure_stage_id")
    for profile in data["profiles"].values():
        profile["stage_targets"].pop("motion")
        profile["stage_targets"].pop("fault")
    data["actions"]["alarm"] = {
        "id": "alarm",
        "level": "3",
        "kind": "siren",
        "target": "siren.test",
    }
    restored = Configuration.from_dict(data)
    assert restored.secure_stage_id == "0" and len(restored.stages) == 4
    assert restored.actions["alarm"].level == "3"
    assert restored.profiles["armed_away"].stage_targets["motion"] == "2"
    assert restored.profiles["armed_away"].stage_targets["fault"] == "0"


def test_output_cleanup_returns_to_secure_one(tmp_path, monkeypatch):
    async def scenario():
        runtime = local_runtime(tmp_path)
        runtime.config.stages = models.default_stages()
        runtime.config.secure_stage_id = "1"
        runtime.config.stages[5].latch = False
        for profile in runtime.config.profiles.values():
            profile.stage_targets.clear()
        runtime.config.validate()
        runtime.engine.set_profile("armed_night", 100)
        runtime.engine.feed("binary_sensor.contact", True, 101)
        runtime.engine.feed("binary_sensor.motion", True, 102)
        assert runtime.engine.level == 5
        runtime.engine.drain()
        runtime.hass.states.set("siren.test", "on")
        runtime.dispatcher.outputs["siren.test"] = {"kind": "siren", "until": time.time() + 1000}
        monkeypatch.setattr(
            runtime_module, "time", type("Clock", (), {"time": staticmethod(lambda: 163)})
        )
        await runtime._tick(None)
        await runtime.hass.drain()
        assert runtime.engine.level == 1 and runtime.engine.secure
        assert runtime.hass.states.get("siren.test").state == "off"

    asyncio.run(scenario())
