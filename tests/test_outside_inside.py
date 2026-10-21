"""Outdoor-to-indoor context is explicit and separate from physical doors."""

import pytest
from iqalarm_core.models import Configuration, Room


def test_area_links_roundtrip_without_changing_sensor_or_door_assignments(config):
    before = config.to_dict()
    config.rooms["garden"] = Room("garden", "Garten")
    config.outside_inside_links = [["garden", "living"], ["garden", "hall"]]
    data = config.to_dict()
    restored = Configuration.from_dict(data)
    assert restored.outside_inside_links == [["garden", "living"], ["garden", "hall"]]
    assert restored.to_dict() == data
    assert restored.to_dict()["sensors"] == before["sensors"]
    assert restored.to_dict()["profiles"] == before["profiles"]
    assert restored.room_connections == before["room_connections"]


def test_old_configuration_does_not_invent_area_links(config):
    data = config.to_dict()
    data.pop("outside_inside_links")
    assert Configuration.from_dict(data).outside_inside_links == []


@pytest.mark.parametrize(
    "links",
    [
        None,
        {},
        "living",
        [["living"]],
        [["living", "missing"]],
        [["living", "living"]],
        [["living", "hall"], ["living", "hall"]],
        [["living", 3]],
        [["living", "hall", "bed"]],
    ],
)
def test_invalid_area_links_are_rejected(config, links):
    data = config.to_dict()
    data["outside_inside_links"] = links
    with pytest.raises(ValueError):
        Configuration.from_dict(data)


def test_area_links_are_directional(config):
    config.outside_inside_links = [["living", "hall"]]
    config.validate()
    assert ["hall", "living"] not in config.outside_inside_links
