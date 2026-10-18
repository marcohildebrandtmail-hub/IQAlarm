"""Presentation overrides survive storage without changing security roles."""

import pytest
from iqalarm_core.models import Configuration, Room, SensorConfig, WindowConfig


def test_icons_roundtrip_and_composite_window_inherits_its_own_symbol(config):
    config.rooms["living"].icon = "mdi:sofa-outline"
    config.sensors["binary_sensor.window"].icon = "mdi:door-closed"
    config.windows["w"] = WindowConfig(
        "w",
        "Fenster",
        "living",
        contact_entity_id="binary_sensor.window",
        icon="mdi:window-open",
        mappings=[
            {"state": "closed", "values": {"binary_sensor.window": "off"}},
            {"state": "open", "values": {"binary_sensor.window": "on"}},
        ],
    )
    data = config.to_dict()
    restored = Configuration.from_dict(data)
    assert restored.to_dict() == data
    assert restored.rooms["living"].icon == "mdi:sofa-outline"
    assert restored.sensors["binary_sensor.window"].icon == "mdi:door-closed"
    assert restored.all_sensors()[restored.windows["w"].sensor_id].icon == "mdi:window-open"
    assert restored.all_sensors()[restored.windows["w"].sensor_id].role == "entry_contact"
    # Older archives have no override, so they keep their automatic symbols.
    del data["rooms"]["living"]["icon"]
    del data["sensors"]["binary_sensor.window"]["icon"]
    del data["windows"]["w"]["icon"]
    legacy = Configuration.from_dict(data)
    assert legacy.rooms["living"].icon is None
    assert legacy.sensors["binary_sensor.window"].icon is None
    assert legacy.windows["w"].icon is None


@pytest.mark.parametrize("value", ['mdi:fridge" onload="bad', "https://example.com/icon.svg", 7])
def test_non_mdi_icons_rejected_at_every_configuration_boundary(value):
    for factory in (
        lambda: Room("r", "Raum", icon=value),
        lambda: SensorConfig("binary_sensor.s", "interior_motion", "r", icon=value),
        lambda: WindowConfig("w", "Fenster", "r", contact_entity_id="binary_sensor.s", icon=value),
    ):
        with pytest.raises(ValueError, match="MDI"):
            factory()
