"""One sensor outage must not prevent protection by the remaining sensors."""

from copy import deepcopy

import pytest
from iqalarm_core.const import Level
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, Settings


@pytest.mark.parametrize("mode", ["armed_night", "armed_away", "armed_home", "armed_vacation"])
@pytest.mark.parametrize("missing", ["binary_sensor.window", "binary_sensor.motion"])
def test_sensor_outage_does_not_block_other_sensors(engine, mode, missing):
    engine.seed(missing, None)
    engine.set_mode(mode, 100)
    assert engine.reactions_enabled and engine.profile_id == mode
    assert missing not in engine.quarantine
    assert missing not in engine.ignored_windows
    engine.feed("binary_sensor.terrace", True, 101)
    assert engine.level == Level.PERIMETER


def test_recovered_sensor_automatically_resumes_monitoring(engine):
    source = "binary_sensor.window"
    engine.seed(source, None)
    engine.set_mode("armed_night", 100)
    engine.feed(source, False, 101)
    engine.feed(source, True, 102)
    assert engine.reactions_enabled
    assert engine.level == Level.SUSPICION
    assert any(event.entity_id == source for event in engine.evidence)


def test_sensor_outage_does_not_hide_an_open_door(engine):
    engine.seed("binary_sensor.terrace", None)
    engine.seed("binary_sensor.window", True)
    with pytest.raises(ValueError, match="offen"):
        engine.set_mode("armed_night", 100)
    assert not engine.reactions_enabled


@pytest.mark.parametrize("old_setting", [True, False, "missing"])
def test_upgrade_removes_old_outage_blocker_once_without_changing_other_settings(
    config, old_setting
):
    data = config.to_dict()
    data["settings"].pop("arming_policy_version")
    if old_setting == "missing":
        data["settings"].pop("block_unavailable_on_arm")
    else:
        data["settings"]["block_unavailable_on_arm"] = old_setting
    original = deepcopy(data)
    restored = Configuration.from_dict(data)
    expected = deepcopy(data)
    expected["settings"].update(block_unavailable_on_arm=False, arming_policy_version=1)
    assert restored.to_dict() == expected
    assert data == original
    assert Configuration.from_dict(restored.to_dict()).to_dict() == expected
    engine = CorrelationEngine(restored)
    for source in engine.sensors:
        engine.seed(source, None if source == "binary_sensor.window" else False)
    engine.set_mode("armed_night", 100)
    assert engine.reactions_enabled


def test_explicit_strict_policy_after_upgrade_survives_reload(config):
    config.settings.block_unavailable_on_arm = True
    restored = Configuration.from_dict(config.to_dict())
    assert restored.settings.block_unavailable_on_arm is True
    engine = CorrelationEngine(restored)
    for source in engine.sensors:
        engine.seed(source, None if source == "binary_sensor.window" else False)
    with pytest.raises(ValueError, match="nicht verfügbar"):
        engine.set_mode("armed_night", 100)


@pytest.mark.parametrize("version", [True, -1, 2, "1", None])
def test_invalid_arming_policy_is_rejected(config, version):
    data = config.to_dict()
    data["settings"]["arming_policy_version"] = version
    with pytest.raises(ValueError, match="Scharfschaltversion"):
        Configuration.from_dict(data)


def test_migration_does_not_hide_an_invalid_availability_setting(config):
    data = config.to_dict()
    data["settings"].pop("arming_policy_version")
    data["settings"]["block_unavailable_on_arm"] = "false"
    with pytest.raises(ValueError, match="boolesch"):
        Configuration.from_dict(data)


def test_new_installation_arms_with_an_unavailable_sensor():
    assert Settings().block_unavailable_on_arm is False
    assert Settings().arming_policy_version == 1
