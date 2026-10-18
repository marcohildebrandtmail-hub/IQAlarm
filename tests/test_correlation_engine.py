"""Required intrusion scenarios plus timer, source-independence and restart boundaries."""

import pytest
from iqalarm_core.const import Level
from iqalarm_core.correlation_engine import CorrelationEngine
from iqalarm_core.models import SensorConfig


def test_maco_flap_five_edges_eight_seconds(engine):
    engine.set_mode("armed_night", 100)
    for i in range(5):
        engine.feed("binary_sensor.lock", i % 2 == 0, 101 + i * 2)
    assert engine.quarantine["binary_sensor.lock"]["reason"] == "quarantined_flapping"
    assert engine.level == Level.SUSPICION
    assert any(e.kind == "quarantined_flapping" for e in engine.events)
    assert not any(e.level == Level.BREACH for e in engine.events)
    assert engine.raw["binary_sensor.hall_motion"] is False


def test_single_window_suspicion_and_timeout(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.level == Level.SUSPICION
    assert [e.level for e in engine.drain() if e.kind == "level_changed"] == [2]
    engine.tick(160.99)
    assert engine.level == Level.SUSPICION
    engine.tick(161)
    assert engine.level == Level.SECURE
    assert any("keine Bestätigung" in e.reason for e in engine.events)


def test_perimeter_then_window_after_forty_seconds(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    assert engine.level == Level.PERIMETER
    engine.feed("binary_sensor.window", True, 141)
    assert engine.level == Level.BREACH
    assert [e.entity_id for e in engine.breach_chain] == [
        "binary_sensor.terrace",
        "binary_sensor.window",
    ]


def test_perimeter_expiry_not_a_confirmation(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    engine.feed("binary_sensor.window", True, 281)
    assert engine.level == Level.SUSPICION


def test_unrelated_camera_does_not_confirm_contact(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    engine.feed("binary_sensor.lock", True, 105)
    assert engine.level == Level.SUSPICION


def test_unassigned_camera_does_not_confirm_any_contact(engine):
    engine.config.sensors["binary_sensor.terrace"].front_of = []
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.terrace", True, 101)
    engine.feed("binary_sensor.lock", True, 105)
    assert engine.level == Level.SUSPICION


def test_independent_contacts_do_not_confirm_across_house(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.lock", True, 110)
    assert engine.level == Level.SUSPICION


def test_one_sensor_cannot_confirm_itself_even_without_flap(engine):
    engine.config.sensors["binary_sensor.window"].flap_enabled = False
    engine.set_mode("armed_away", 100)
    for i in range(20):
        engine.feed("binary_sensor.window", i % 2 == 0, 101 + i)
    assert engine.level == Level.SUSPICION


def test_same_physical_source_cannot_cross_confirm(engine):
    for entity_id in ("binary_sensor.window", "binary_sensor.lock"):
        engine.config.sensors[entity_id].source_id = "same-device"
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.lock", True, 102)
    assert engine.level == Level.SUSPICION


def test_quarantined_sensor_cannot_confirm_motion_or_camera(engine):
    engine.set_mode("armed_night", 100)
    for i, state in enumerate((True, False, True)):
        engine.feed("binary_sensor.window", state, 101 + i)
    engine.feed("binary_sensor.terrace", True, 105)
    engine.feed("binary_sensor.motion", True, 106)
    assert engine.level < Level.BREACH


def test_verified_breach_is_not_erased_by_subsequent_flapping(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    for i in range(8):
        engine.feed("binary_sensor.window", i % 2 == 1, 103 + i)
    engine.tick(1000)
    assert engine.level == Level.BREACH


def test_debounce_rejects_microbreak_and_fires_after_minimum(engine):
    engine.config.sensors["binary_sensor.window"].debounce_ms = 500
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.tick(101.2)
    assert engine.level == Level.SECURE
    engine.feed("binary_sensor.window", False, 101.3)
    engine.tick(102)
    assert engine.level == Level.SECURE
    engine.feed("binary_sensor.window", True, 120)
    engine.tick(120.5)
    assert engine.level == Level.SUSPICION


def test_raw_flap_detection_survives_debounce(engine):
    engine.config.sensors["binary_sensor.window"].debounce_ms = 5000
    engine.set_mode("armed_night", 100)
    for i, state in enumerate((True, False, True)):
        engine.feed("binary_sensor.window", state, 101 + i)
    assert "binary_sensor.window" in engine.quarantine
    assert not engine.debouncing
    engine.tick(110)
    assert engine.level < Level.BREACH


def test_role_debounce_default(engine):
    engine.config.settings.debounce_by_role = {"entry_contact": 1000}
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.tick(101.9)
    assert engine.level == Level.SECURE
    engine.tick(102)
    assert engine.level == Level.SUSPICION


def test_unavailable_recovery_does_not_count_as_edges(engine):
    engine.set_mode("armed_night", 100)
    for i in range(5):
        engine.feed("binary_sensor.window", None, 101 + i * 2)
        engine.feed("binary_sensor.window", True, 102 + i * 2)
    assert not engine.quarantine
    assert engine.level == Level.SECURE


def test_entry_delay_expires_without_sensor_updates(engine):
    engine.config.sensors["binary_sensor.window"].entry_delay = True
    engine.set_mode("armed_away", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.pending_until == 122
    assert engine.level == Level.SUSPICION
    engine.tick(122)
    assert engine.level == Level.BREACH


def test_disarm_cancels_entry_delay_and_quarantine(engine):
    engine.config.sensors["binary_sensor.window"].entry_delay = True
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    engine.set_mode("disarmed", 110)
    engine.tick(150)
    assert engine.level == Level.SECURE
    assert engine.pending_until is None
    assert not engine.evidence
    assert not engine.quarantine


def test_exit_delay_ignores_movement_then_checks_open_door(engine):
    engine.config.profiles["armed_away"].exit_seconds = 30
    engine.set_mode("armed_away", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.level == Level.SECURE
    engine.tick(130)
    assert engine.arming_until is None
    assert engine.level == Level.SUSPICION


def test_arming_blockers_and_failed_mode_is_rolled_back(engine):
    engine.seed("binary_sensor.window", True)
    with pytest.raises(ValueError, match="offen"):
        engine.set_mode("armed_night", 100)
    assert not engine.reactions_enabled


def test_unavailable_arm_blocker(engine):
    engine.seed("binary_sensor.window", None)
    with pytest.raises(ValueError, match="nicht verfügbar"):
        engine.set_mode("armed_away", 100)


def test_home_only_enabled_rooms_and_perimeter(engine):
    engine.set_mode("armed_home", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.level == Level.SECURE
    engine.feed("binary_sensor.terrace", True, 103)
    assert engine.level == Level.PERIMETER


def test_home_selected_basement(engine):
    engine.config.profiles["armed_home"].contacts_enabled = True
    engine.config.profiles["armed_home"].motion_mode = "always"
    engine.config.profiles["armed_home"].room_ids = ["living"]
    engine.set_mode("armed_home", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.level == Level.BREACH


def test_explicit_override(engine):
    engine.config.sensors["binary_sensor.window"].immediate = True
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.level == Level.BREACH


def test_vacation_defaults_shorter_delay(engine):
    engine.config.sensors["binary_sensor.window"].entry_delay = True
    engine.set_mode("armed_vacation", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.pending_until == 107
    assert engine.profile.correlation_seconds == 45


def test_restore_full_alarm_and_log(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 113)
    restored = CorrelationEngine(engine.config)
    restored.restore(engine.persistent_state(), 200)
    assert restored.level == Level.BREACH
    assert restored.reactions_enabled and restored.profile_id == "armed_night"
    assert len(restored.breach_chain) == 2
    assert restored.events[0].reason == engine.events[0].reason
    assert not restored.drain()  # No duplicate actions from a stored full alarm.


def test_restore_pending_delay_is_completed(engine):
    engine.config.sensors["binary_sensor.window"].entry_delay = True
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 113)
    restored = CorrelationEngine(engine.config)
    restored.restore(engine.persistent_state(), 200)
    assert restored.level == Level.BREACH
    assert any(e.kind == "confirmation_changed" and e.confirmed for e in restored.drain())


def test_restore_old_suspicion_expires(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    restored = CorrelationEngine(engine.config)
    restored.restore(engine.persistent_state(), 200)
    assert restored.level == Level.SECURE


def test_quarantine_persists_until_disarm_or_manual_release(engine):
    engine.set_mode("armed_night", 100)
    for i, state in enumerate((True, False, True)):
        engine.feed("binary_sensor.window", state, 101 + i)
    engine.tick(200)
    assert engine.level == Level.SECURE
    assert "binary_sensor.window" in engine.quarantine
    restored = CorrelationEngine(engine.config)
    restored.restore(engine.persistent_state(), 210)
    assert "binary_sensor.window" in restored.quarantine
    restored.clear_quarantine("binary_sensor.window", 211)
    assert not restored.quarantine
    assert not restored.evidence


def test_room_status_and_fault(engine):
    engine.set_mode("armed_night", 100)
    engine.feed("binary_sensor.window", True, 101)
    assert engine.room_status("living", 101)["open"] == ["binary_sensor.window"]
    assert engine.room_status("living", 101)["level"] == 2
    assert engine.snapshot(101)["stage_id"] == "2"


def test_direct_profile_switch_rejected(engine):
    engine.set_mode("armed_night", 100)
    with pytest.raises(ValueError, match="entschärfen"):
        engine.set_mode("armed_away", 101)


def test_disarmed_diagnosis_optional(engine):
    engine.config.settings.diagnose_disarmed = False
    engine.config.settings.observation_profile_id = None
    for i, state in enumerate((True, False, True, False, True)):
        engine.feed("binary_sensor.window", state, 101 + i)
    assert not engine.quarantine
    assert engine.level == Level.SECURE


def test_quarantine_invalidates_pending_chain_even_after_manual_release(engine):
    engine.config.sensors["binary_sensor.window"].entry_delay = True
    engine.config.profiles["armed_away"].entry_seconds = 120
    engine.set_mode("armed_away", 100)
    engine.feed("binary_sensor.window", True, 101)
    engine.feed("binary_sensor.motion", True, 102)
    assert engine.pending_until == 222
    for i, active in enumerate((False, True, False)):
        engine.feed("binary_sensor.window", active, 170 + i)
    assert "binary_sensor.window" in engine.quarantine
    assert engine.pending_until is None
    engine.clear_quarantine("binary_sensor.window", 180)
    engine.tick(223)
    assert engine.level == Level.SECURE


def test_new_source_signal_and_duplicated_states(engine):
    engine.set_mode("armed_night", 100)
    for i in range(10):
        engine.feed("binary_sensor.window", True, 101 + i)
    assert len(engine.edges["binary_sensor.window"]) == 1
    assert engine.level == Level.SUSPICION


def test_smoke_is_explicit_emergency_role(engine):
    engine.config.sensors["binary_sensor.smoke"] = SensorConfig(
        "binary_sensor.smoke", "smoke", "living"
    )
    engine.seed("binary_sensor.smoke", False)
    engine.set_mode("armed_away", 100)
    engine.feed("binary_sensor.smoke", True, 101)
    assert engine.level == Level.BREACH
