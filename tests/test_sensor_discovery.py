"""Unit tests for sensor discovery and proposal engine."""

from unittest.mock import MagicMock

from iqalarm_core.const import Role
from iqalarm_core.sensor_discovery import (
    build_room_matcher,
    classify_entity,
    discover_sensors,
    normalize_text,
)


def test_classify_entity_roles():
    # Doors and windows
    assert classify_entity("binary_sensor.fenster_wohnzimmer", "Fenster Wohnzimmer", "window") == Role.ENTRY.value
    assert classify_entity("binary_sensor.tur_haustur", "Haustür Kontakt", "door") == Role.ENTRY.value
    assert classify_entity("binary_sensor.garagentor", "Garagentor", "garage_door") == Role.ENTRY.value
    assert classify_entity("binary_sensor.balkon_kontakt", "Balkon Öffnung", None) == Role.ENTRY.value

    # Locks
    assert classify_entity("lock.haustur_schloss", "Haustürschloss", "lock") == Role.LOCK.value
    assert classify_entity("binary_sensor.riegel_kontakt", "Riegelkontakt", None) == Role.LOCK.value

    # Motion & Presence
    assert classify_entity("binary_sensor.motionsensor_wohnzimmer", "Bewegungsmelder", "motion") == Role.MOTION.value
    assert classify_entity("binary_sensor.radar_schlafzimmer", "Aqara FP2 Präsenz", "presence") == Role.MMWAVE.value
    assert classify_entity("binary_sensor.mmwave_flur", "LD2410 mmWave", None) == Role.MMWAVE.value

    # Outdoor / Perimeter
    assert classify_entity("camera.cctv_garagenhof", "CCTV Garagenhof", None) == Role.PERIMETER_CAMERA.value
    assert classify_entity("binary_sensor.cctv_person_vorne", "Personenerkennung Vorne", None) == Role.PERIMETER_CAMERA.value
    assert classify_entity("binary_sensor.motionsensor_garten", "Garten Bewegung", "motion") == Role.PERIMETER_SENSOR.value
    assert classify_entity("binary_sensor.terrasse_bwm", "Terrasse Bewegung", None) == Role.PERIMETER_SENSOR.value

    # Glass / Vibration
    assert classify_entity("binary_sensor.glasbruch_kuche", "Glasbruchsensor", "vibration") == Role.GLASS.value
    assert classify_entity("binary_sensor.vibration_schaufenster", "Erschütterung", None) == Role.GLASS.value

    # Smoke & Panic
    assert classify_entity("binary_sensor.rauchmelder_flur", "Rauchmelder Flur", "smoke") == Role.SMOKE.value
    assert classify_entity("binary_sensor.notruf_taster", "Panikschalter SOS", None) == Role.PANIC.value


def test_classify_entity_noise_exclusion():
    # Companion apps / phones
    assert classify_entity("binary_sensor.pixel_7_pro_is_charging", "Pixel 7 Pro Is Charging", "battery_charging") is None
    assert classify_entity("binary_sensor.galaxy_s22_app_active", "Galaxy S22 App", None) is None
    assert classify_entity("binary_sensor.iphone_14_geocoded", "iPhone Geocoded", None) is None

    # Battery & system diagnostics
    assert classify_entity("binary_sensor.fenster_battery", "Fenster Batterie", "battery") is None
    assert classify_entity("binary_sensor.bwm_update_available", "Update Available", "update") is None
    assert classify_entity("binary_sensor.zigbee_connectivity", "Network Connectivity", "connectivity") is None

    # Unrelated domains
    assert classify_entity("light.wohnzimmer_deckenleuchte", "Deckenleuchte", None) is None
    assert classify_entity("switch.steckdose_tv", "Steckdose", None) is None


def test_normalize_text():
    assert normalize_text("Fenster_Küche_Links") == "fenster kueche links"
    assert normalize_text("buero-tuer") == "buero tuer"
    assert normalize_text("Gäste_WC") == "gaeste wc"
    assert normalize_text("schlafzimmer_außen") == "schlafzimmer aussen"


def test_build_room_matcher_prioritization():
    rooms = {
        "r1": {"name": "Bad", "area_id": "bad"},
        "r2": {"name": "Elternbad", "area_id": "elternbad"},
        "r3": {"name": "Flur", "area_id": "flur"},
        "r4": {"name": "Flur OG", "area_id": "flur_og"},
    }
    matcher = build_room_matcher(rooms)
    # Longer keywords come first
    keywords = [k for k, _ in matcher]
    assert keywords.index("elternbad") < keywords.index("bad")
    assert keywords.index("flur og") < keywords.index("flur")


def test_discover_sensors_with_mock_hass():
    hass = MagicMock()

    # Areas
    area_wc = MagicMock(id="gaste_wc", name="Gäste WC")
    area_wz = MagicMock(id="wohnzimmer", name="Wohnzimmer")
    ar_mock = MagicMock()
    ar_mock.async_list_areas.return_value = [area_wc, area_wz]

    # Entity registry
    er_mock = MagicMock()
    ent_entry_1 = MagicMock(area_id="wohnzimmer", device_id=None, platform="mqtt")
    ent_entry_2 = MagicMock(area_id=None, device_id="dev_42", platform="hue")
    ent_entry_3 = MagicMock(area_id=None, device_id=None, platform="matter")
    er_mock.async_get.side_effect = lambda eid: {
        "binary_sensor.fenster_wz_1": ent_entry_1,
        "binary_sensor.motionsensor_dev": ent_entry_2,
        "binary_sensor.fenster_wc": ent_entry_3,
    }.get(eid)

    # Device registry
    dr_mock = MagicMock()
    dev_mock = MagicMock(id="dev_42", area_id="wohnzimmer", manufacturer="Signify Netherlands B.V.", model="SML002")
    dev_mock.name = "Hue BWM WZ"
    dr_mock.async_get.side_effect = lambda did: dev_mock if did == "dev_42" else None

    # Attach registries directly to mock hass
    hass.entity_registry = er_mock
    hass.device_registry = dr_mock
    hass.area_registry = ar_mock

    # States
    s1 = MagicMock(entity_id="binary_sensor.fenster_wz_1", attributes={"friendly_name": "Fenster WZ", "device_class": "window"}, state="off")
    s2 = MagicMock(entity_id="binary_sensor.motionsensor_dev", attributes={"friendly_name": "Bewegungsmelder", "device_class": "motion"}, state="off")
    s3 = MagicMock(entity_id="binary_sensor.fenster_wc", attributes={"friendly_name": "Fenster Gäste WC", "device_class": "window"}, state="off")
    s4 = MagicMock(entity_id="binary_sensor.already_done", attributes={"friendly_name": "Bereits da", "device_class": "window"}, state="off")
    s5 = MagicMock(entity_id="binary_sensor.tur_haustur", attributes={"friendly_name": "Eingangstür", "device_class": "door"}, state="off")
    hass.states.async_all.return_value = [s1, s2, s3, s4, s5]

    rooms = {
        "wz_id": {"name": "Wohnzimmer", "area_id": "wohnzimmer"},
        "wc_id": {"name": "WC", "area_id": "gaste_wc"},
        "flur_id": {"name": "Garderobe", "area_id": "flur_ug"},
    }
    current_sensors = {"binary_sensor.already_done": {}}

    candidates = discover_sensors(hass, current_sensors, rooms)

    # binary_sensor.already_done must be skipped
    assert not any(c["entity_id"] == "binary_sensor.already_done" for c in candidates)

    # s1 matched to Wohnzimmer via entity area
    c1 = next(c for c in candidates if c["entity_id"] == "binary_sensor.fenster_wz_1")
    assert c1["room_id"] == "wz_id"
    assert c1["role"] == Role.ENTRY.value
    assert c1["platform"] == "mqtt"
    assert c1["integration_name"] == "MQTT / Zigbee"

    # s2 matched to Wohnzimmer via device area, with Aliased Manufacturer Philips Hue
    c2 = next(c for c in candidates if c["entity_id"] == "binary_sensor.motionsensor_dev")
    assert c2["room_id"] == "wz_id"
    assert c2["role"] == Role.MOTION.value
    assert c2["device_name"] == "Hue BWM WZ"
    assert c2["manufacturer"] == "Philips Hue"
    assert c2["model"] == "SML002"
    assert c2["platform"] == "hue"

    # s3 matched to WC via name keyword "Gäste WC"
    c3 = next(c for c in candidates if c["entity_id"] == "binary_sensor.fenster_wc")
    assert c3["room_id"] == "wc_id"
    assert c3["role"] == Role.ENTRY.value
    assert c3["platform"] == "matter"

    # s5 is entrance door, should have entry_delay True
    c5 = next(c for c in candidates if c["entity_id"] == "binary_sensor.tur_haustur")
    assert c5["entry_delay"] is True

