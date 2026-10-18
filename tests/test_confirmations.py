"""A remembered 3/3 perimeter proof never replaces a new, related opening."""

from copy import deepcopy

import pytest
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.level_rules import LevelRule, RuleCondition
from iqalarm_core.models import Configuration, SensorConfig


@pytest.fixture
def graded(config):
    config = Configuration(rooms=deepcopy(config.rooms), sensors=deepcopy(config.sensors))
    for name in ("two", "three"):
        sensor = SensorConfig(f"binary_sensor.{name}", "perimeter_camera", front_of=["living"])
        config.sensors[sensor.entity_id] = sensor
    config.rules = {
        "outside": LevelRule(
            "outside",
            "Vorfeld",
            "2",
            [
                RuleCondition(
                    sensor_ids=[
                        "binary_sensor.terrace",
                        "binary_sensor.two",
                        "binary_sensor.three",
                    ],
                    count=1,
                )
            ],
            window_seconds=30,
            confirmation_target=3,
            confirmation_memory_seconds=180,
        ),
        "entry": LevelRule(
            "entry",
            "Bestätigtes Vorfeld plus Öffnung",
            "5",
            [RuleCondition(roles=["entry_contact"])],
            window_seconds=60,
            prerequisite_rule_id="outside",
        ),
    }
    for profile in config.profiles.values():
        profile.rule_ids = ["outside", "entry"]
    engine = CorrelationEngine(config)
    for key in engine.sensors:
        engine.seed(key, False)
    engine.set_profile("armed_night", 100)
    return engine


def complete(engine):
    for index, name in enumerate(("terrace", "two", "three")):
        engine.feed(f"binary_sensor.{name}", True, 101 + index)


def test_grade_grows_without_full_alarm_and_memory_does_not_extend_on_ticks(graded):
    for index, name in enumerate(("terrace", "two", "three")):
        graded.feed(f"binary_sensor.{name}", True, 101 + index)
        progress = graded.snapshot(101 + index)["rule_progress"][0]
        assert progress["current"] == index + 1
        assert progress["complete"] == (index == 2)
        assert graded.level == 2 and not graded.confirmed
    until = graded.rule_confirmations["outside"]["until"]
    for moment in (110, 132, 160, 282):
        graded.tick(moment)
        assert graded.level == 2
        assert graded.rule_confirmations["outside"]["until"] == until == 283
    for key in ("binary_sensor.terrace", "binary_sensor.two", "binary_sensor.three"):
        graded.raw[key] = False
    graded.tick(283)
    assert graded.level == 1


def test_only_a_new_related_opening_inside_memory_reaches_full_alarm(graded):
    complete(graded)
    graded.tick(200)
    graded.feed("binary_sensor.window", True, 201)
    assert graded.level == 5 and graded.confirmed
    assert len(graded.breach_chain) == 4
    assert [e.timestamp for e in graded.breach_chain] == [101, 102, 103, 201]


@pytest.mark.parametrize(
    "scenario",
    [
        "only_two",
        "same_device",
        "expired",
        "unrelated",
        "opening_before",
        "unavailable",
        "quarantine",
        "unrelated_camera",
    ],
)
def test_incomplete_unrelated_or_invalid_confirmation_cannot_alarm(graded, scenario):
    if scenario == "same_device":
        graded.sensors["binary_sensor.two"].source_id = "same"
        graded.sensors["binary_sensor.three"].source_id = "same"
    if scenario == "opening_before":
        graded.feed("binary_sensor.window", True, 100.5)
    if scenario == "unrelated_camera":
        graded.sensors["binary_sensor.three"].front_of = ["bed"]
    if scenario == "only_two":
        graded.feed("binary_sensor.terrace", True, 101)
        graded.feed("binary_sensor.two", True, 102)
    else:
        complete(graded)
    now = 284 if scenario == "expired" else 115
    if scenario == "unavailable":
        graded.feed("binary_sensor.two", None, 110)
    if scenario == "quarantine":
        graded.quarantine["binary_sensor.two"] = {"since": 110, "reason": "test"}
    if scenario == "opening_before":
        graded.tick(now)
    elif scenario == "unrelated":
        graded.config.sensors["binary_sensor.other"] = SensorConfig(
            "binary_sensor.other", "entry_contact", "bed"
        )
        graded.sensors["binary_sensor.other"] = graded.config.sensors["binary_sensor.other"]
        graded.feed("binary_sensor.other", True, now)
    else:
        graded.feed("binary_sensor.window", True, now)
    assert not graded.confirmed and graded.level < 5


def test_memory_restores_with_original_expiry_and_rejects_spatial_changes(graded):
    complete(graded)
    state = deepcopy(graded.persistent_state())
    restored = CorrelationEngine(graded.config)
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(state, 200)
    assert restored.level == 2
    assert restored.rule_confirmations["outside"]["until"] == 283
    restored.feed("binary_sensor.window", True, 201)
    assert restored.confirmed
    # A latched breach survives restart after the prerequisite memory expired.
    latched = CorrelationEngine(graded.config)
    for key in latched.sensors:
        latched.seed(key, False)
    latched.restore(deepcopy(restored.persistent_state()), 400)
    assert latched.level == 5 and latched.confirmed
    changed = deepcopy(graded.config)
    changed.sensors["binary_sensor.three"].front_of = ["hall"]
    rejected = CorrelationEngine(changed)
    for key in rejected.sensors:
        rejected.seed(key, False)
    rejected.restore(state, 200)
    rejected.feed("binary_sensor.window", True, 201)
    assert not rejected.confirmed


def test_profile_switch_and_unarm_clear_confirmation_memory(graded):
    complete(graded)
    graded.set_profile(None, 110)
    assert not graded.rule_confirmations
    graded.set_profile("armed_night", 111)
    graded.feed("binary_sensor.window", True, 112)
    assert not graded.confirmed


def test_configuration_rejects_missing_self_or_higher_dependencies(graded):
    for parent in ("missing", "entry"):
        data = graded.config.to_dict()
        data["rules"]["entry"]["prerequisite_rule_id"] = parent
        with pytest.raises(ValueError, match="Voraussetzung"):
            Configuration.from_dict(data)
    data = graded.config.to_dict()
    data["rules"]["outside"]["confirmation_target"] = 0
    with pytest.raises(ValueError, match="Bestätigungsziel"):
        Configuration.from_dict(data)
