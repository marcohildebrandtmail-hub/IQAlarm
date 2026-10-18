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


def test_entry_delay_can_finish_after_memory_expiry_and_restore(graded):
    graded.config.rules["entry"].delay_seconds = 30
    complete(graded)
    graded.feed("binary_sensor.window", True, 280)
    assert graded.pending_until == 310 and not graded.confirmed
    state = deepcopy(graded.persistent_state())
    restored = CorrelationEngine(graded.config)
    for key in restored.sensors:
        restored.seed(key, graded.raw.get(key))
    restored.restore(state, 290)
    assert restored.pending_until == 310
    restored.tick(310)
    assert restored.level == 5 and restored.confirmed


def test_offline_source_is_not_shown_as_a_completed_grade(graded):
    complete(graded)
    graded.feed("binary_sensor.two", None, 110)
    progress = graded.snapshot(110)["rule_progress"][0]
    assert progress["current"] == 2 and not progress["complete"]


def test_memory_rejects_tampered_expiry_and_source_identity(graded):
    complete(graded)
    state = deepcopy(graded.persistent_state())
    for mutation in ("expiry", "source"):
        config = deepcopy(graded.config)
        saved = deepcopy(state)
        if mutation == "expiry":
            saved["rule_confirmations"]["outside"]["until"] += 1000
        else:
            config.sensors["binary_sensor.three"].source_id = "other-device"
        engine = CorrelationEngine(config)
        for key in engine.sensors:
            engine.seed(key, False)
        engine.restore(saved, 200)
        engine.feed("binary_sensor.window", True, 201)
        assert not engine.confirmed


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


def with_decay(engine, thresholds=None, times=None):
    rule = engine.config.rules["outside"]
    rule.window_seconds = 600
    rule.confirmation_thresholds = thresholds or [1, 2, 3]
    rule.confirmation_decay_seconds = times or [60, 60, 60]
    rule.__post_init__()
    return engine


def progress(engine, at):
    engine.tick(at)
    return engine.snapshot(at)["rule_progress"][0]


def test_inactivity_counts_down_without_replaying_old_evidence(graded):
    with_decay(graded)
    graded.feed("binary_sensor.terrace", True, 101)
    graded.feed("binary_sensor.two", True, 120)
    assert progress(graded, 179)["current"] == 2
    assert progress(graded, 180)["current"] == 1
    assert progress(graded, 200)["current"] == 1
    assert progress(graded, 240)["current"] == 0
    assert progress(graded, 245)["current"] == 0
    graded.feed("binary_sensor.three", True, 246)
    assert progress(graded, 246)["current"] == 1
    assert not graded.rule_confirmations


def test_each_grade_has_its_own_inactivity_deadline(graded):
    with_decay(graded, times=[60, 30, 10])
    complete(graded)
    assert progress(graded, 112)["current"] == 3
    assert progress(graded, 113)["current"] == 2
    assert progress(graded, 142)["current"] == 2
    assert progress(graded, 143)["current"] == 1
    assert progress(graded, 203)["current"] == 0
    assert progress(graded, 210)["remembered"]
    assert graded.rule_confirmations["outside"]["until"] == 283
    graded.feed("binary_sensor.window", True, 211)
    assert graded.level == 5 and graded.confirmed


def test_repeated_device_refreshes_time_but_never_counts_as_two_sources(graded):
    with_decay(graded)
    graded.feed("binary_sensor.terrace", True, 101)
    graded.feed("binary_sensor.terrace", False, 110)
    graded.feed("binary_sensor.terrace", True, 120)
    assert progress(graded, 161)["current"] == 1
    assert progress(graded, 180)["current"] == 0
    graded.feed("binary_sensor.two", True, 181)
    assert progress(graded, 181)["current"] == 1
    assert not graded.rule_confirmations


def test_nonuniform_source_thresholds_and_restored_deadlines(graded):
    rule = graded.config.rules["outside"]
    for name in ("four", "five"):
        sensor = SensorConfig(f"binary_sensor.{name}", "perimeter_camera", front_of=["living"])
        graded.config.sensors[sensor.entity_id] = sensor
        graded.sensors[sensor.entity_id] = sensor
        graded.seed(sensor.entity_id, False)
        rule.conditions[0].sensor_ids.append(sensor.entity_id)
    with_decay(graded, [1, 3, 5])
    for index, name in enumerate(("terrace", "two", "three", "four", "five")):
        graded.feed(f"binary_sensor.{name}", True, 101 + index)
        assert progress(graded, 101 + index)["current"] == [1, 1, 2, 2, 3][index]
    state = deepcopy(graded.persistent_state())
    restored = CorrelationEngine(graded.config)
    for key in restored.sensors:
        restored.seed(key, False)
    restored.restore(state, 130)
    assert progress(restored, 164)["current"] == 3
    assert progress(restored, 165)["current"] == 2
    assert progress(restored, 225)["current"] == 1
    assert restored.rule_confirmations["outside"]["until"] == 285
    assert len([e for e in restored.events if e.kind == "rule_confirmation"]) == 1


@pytest.mark.parametrize("invalid", ["quarantine", "offline", "room"])
def test_grade_rejects_invalid_sources(graded, invalid):
    with_decay(graded)
    complete(graded)
    if invalid == "quarantine":
        graded.quarantine["binary_sensor.two"] = {"since": 110, "reason": "test"}
    elif invalid == "offline":
        graded.feed("binary_sensor.two", None, 110)
    else:
        graded.sensors["binary_sensor.two"].front_of = ["bed"]
    data = progress(graded, 111)
    assert data["current"] < 3 and not data["remembered"]
    graded.feed("binary_sensor.window", True, 112)
    assert not graded.confirmed


def test_completion_event_happens_once_per_rising_full_grade(graded):
    with_decay(graded, times=[60, 60, 10])
    complete(graded)
    graded.tick(110)
    assert len([e for e in graded.events if e.kind == "rule_confirmation"]) == 1
    assert progress(graded, 113)["current"] == 2
    graded.feed("binary_sensor.terrace", False, 114)
    graded.feed("binary_sensor.terrace", True, 115)
    assert progress(graded, 115)["current"] == 3
    events = [e for e in graded.events if e.kind == "rule_confirmation"]
    assert len(events) == 2
    assert all(e.stage_id == "2" and not e.confirmed for e in events)


@pytest.mark.parametrize(
    "field,value",
    [
        ("confirmation_thresholds", [1, 1, 3]),
        ("confirmation_thresholds", [1, 3]),
        ("confirmation_thresholds", [1, 2, 9]),
        ("confirmation_decay_seconds", [60, 60]),
        ("confirmation_decay_seconds", [60, 0, 60]),
    ],
)
def test_grade_configuration_rejects_invalid_steps(graded, field, value):
    data = graded.config.to_dict()
    data["rules"]["outside"][field] = value
    with pytest.raises(ValueError):
        Configuration.from_dict(data)


def test_runtime_publishes_and_persists_decay_without_another_sensor_event(
    graded, tmp_path, monkeypatch
):
    import asyncio

    from safety_support import local_runtime, runtime_module

    async def scenario():
        with_decay(graded)
        complete(graded)
        runtime = local_runtime(tmp_path)
        runtime.engine = graded
        runtime._next_simulation = runtime._next_prune = 1000
        await runtime.flush()
        queued = runtime.queue.qsize()
        writes = len(runtime.store.writes)
        published = len(runtime.hass.published)
        monkeypatch.setattr(runtime_module.time, "time", lambda: 163)
        await runtime._tick(None)
        await runtime.hass.drain()
        assert graded.rule_grades["outside"]["grade"] == 2
        assert len(runtime.hass.published) > published
        assert len(runtime.store.writes) == writes + 1
        assert runtime.store.state["rule_grades"]["outside"]["grade"] == 2
        assert runtime.queue.qsize() == queued
        await runtime._tick(None)
        await runtime.hass.drain()
        assert len(runtime.store.writes) == writes + 1

    asyncio.run(scenario())
