"""Only explicitly marked direct doors add spatial corroboration, never transitive paths."""

from copy import deepcopy

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import Configuration, FloorPlan


def connected_engine(config, pairs):
    configuration = Configuration(rooms=deepcopy(config.rooms), sensors=deepcopy(config.sensors))
    configuration.room_connections = pairs
    engine = CorrelationEngine(configuration)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_night", 100)
    return engine


@pytest.mark.parametrize(
    "pairs,expected", [([], False), ([["living", "hall"]], True), ([["hall", "living"]], True)]
)
def test_physical_door_allows_related_opening_and_motion(config, pairs, expected):
    engine = connected_engine(config, pairs)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 112)
    assert engine.confirmed == expected


def test_two_doors_do_not_confirm_motion_two_rooms_away(config):
    engine = connected_engine(config, [["living", "hall"], ["hall", "bed"]])
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.bed_motion", True, 112)
    assert not engine.confirmed


def test_plain_old_adjacency_does_not_create_a_door(config):
    assert "hall" in config.rooms["living"].adjacent
    engine = connected_engine(config, [])
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.hall_motion", True, 112)
    assert not engine.confirmed


@pytest.mark.parametrize(
    "scenario", ["same_device", "offline", "quarantine", "expired", "no_opening"]
)
def test_a_door_does_not_bypass_other_alarm_requirements(config, scenario):
    engine = connected_engine(config, [["living", "hall"]])
    if scenario == "same_device":
        engine.sensors["binary_sensor.window"].source_id = "shared"
        engine.sensors["binary_sensor.hall_motion"].source_id = "shared"
    if scenario != "no_opening":
        engine.feed("binary_sensor.window", True, 101)
    if scenario == "quarantine":
        engine.quarantine["binary_sensor.window"] = {"since": 102, "reason": "flapping"}
    elif scenario == "offline":
        engine.feed("binary_sensor.window", None, 102)
    engine.feed("binary_sensor.hall_motion", True, 170 if scenario == "expired" else 112)
    assert not engine.confirmed


def test_doors_and_opacity_roundtrip_without_modifying_source_geometry(config):
    engine = connected_engine(config, [["living", "hall"]])
    engine.config.floorplans["eg"] = FloorPlan(
        "eg",
        "Erdgeschoss",
        zones={"living": [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8]]},
        image_opacity=0.2,
    )
    data = engine.config.to_dict()
    restored = Configuration.from_dict(data)
    assert restored.room_connections == [["living", "hall"]]
    assert restored.floorplans["eg"].image_opacity == 0.2
    assert restored.to_dict() == data


@pytest.mark.parametrize(
    "pairs",
    [
        [["living", "missing"]],
        [["living", "living"]],
        [["living"]],
        [["living", "hall"], ["hall", "living"]],
        "invalid",
    ],
)
def test_invalid_room_connections_are_rejected(config, pairs):
    data = config.to_dict()
    data["room_connections"] = pairs
    with pytest.raises(ValueError):
        Configuration.from_dict(data)


@pytest.mark.parametrize("opacity", [-0.01, 1.01, True, float("inf"), "0.2"])
def test_opacity_requires_a_finite_fraction(opacity):
    with pytest.raises(ValueError):
        FloorPlan("eg", "Erdgeschoss", image_opacity=opacity)
