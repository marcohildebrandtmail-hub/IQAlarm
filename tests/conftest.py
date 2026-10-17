"""Load the independent engine without importing Home Assistant's integration entrypoint."""

import sys
import types
from pathlib import Path

import pytest

package = types.ModuleType("iqalarm_core")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components" / "iqalarm")]
sys.modules["iqalarm_core"] = package

from iqalarm_core.correlation_engine import CorrelationEngine  # noqa: E402
from iqalarm_core.models import Configuration, Room, SensorConfig  # noqa: E402


@pytest.fixture
def config():
    return Configuration(
        rooms={
            "living": Room("living", "Wohnzimmer", adjacent=["hall"]),
            "hall": Room("hall", "Flur"),
            "bed": Room("bed", "Schlafzimmer"),
        },
        sensors={
            "binary_sensor.window": SensorConfig(
                "binary_sensor.window", "entry_contact", "living", name="Fenster Wohnzimmer"
            ),
            "binary_sensor.lock": SensorConfig(
                "binary_sensor.lock", "lock_contact", "hall", name="MACO Haustür"
            ),
            "binary_sensor.motion": SensorConfig(
                "binary_sensor.motion", "interior_motion", "living", name="Bewegung Wohnzimmer"
            ),
            "binary_sensor.hall_motion": SensorConfig(
                "binary_sensor.hall_motion", "interior_motion", "hall"
            ),
            "binary_sensor.bed_motion": SensorConfig(
                "binary_sensor.bed_motion", "interior_motion", "bed"
            ),
            "binary_sensor.terrace": SensorConfig(
                "binary_sensor.terrace",
                "perimeter_camera",
                front_of=["living"],
                name="Kamera Terrasse",
            ),
        },
    )


@pytest.fixture
def engine(config):
    instance = CorrelationEngine(config)
    for entity_id in config.sensors:
        instance.seed(entity_id, False)
    return instance
