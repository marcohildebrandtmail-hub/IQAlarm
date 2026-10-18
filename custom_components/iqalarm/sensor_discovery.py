"""Automated sensor discovery and proposal engine for Home Assistant."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

try:
    from homeassistant.helpers import area_registry, device_registry, entity_registry
except ImportError:
    area_registry = None  # type: ignore[assignment]
    device_registry = None  # type: ignore[assignment]
    entity_registry = None  # type: ignore[assignment]

from .const import ALLOWED_SENSOR_DOMAINS, Role

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

OUTDOOR_KEYWORDS = (
    "garten",
    "hof",
    "garagenhof",
    "cctv",
    "vorfeld",
    "carport",
    "aussen",
    "draussen",
    "einfahrt",
    "vorgarten",
    "terrasse",
    "terras",
    "balkon",
    "fassade",
    "gehweg",
    "gartenweg",
    "zufahrt",
    "outdoor",
)

DOOR_WINDOW_KEYWORDS = (
    "fenster",
    "tuer",
    "kontakt",
    "garagentor",
    "hoftor",
    "gartentor",
    "schiebetor",
    "eingangstor",
    "sektionaltor",
    "rolltor",
    "terrassentuer",
    "balkontuer",
    "schiebetuer",
    "haustuer",
    "nebentuer",
    "kellerfenster",
    "dachfenster",
    "window",
    "door",
    "opening",
)

LOCK_KEYWORDS = (
    "schloss",
    "riegel",
    "tuerschloss",
    "haustuerschloss",
    "bolzen",
    "sperre",
    "motorschloss",
    "lock",
    "deadbolt",
)

MOTION_KEYWORDS = (
    "motion",
    "bewegung",
    "bwm",
    "pir",
    "occupancy",
)

MMWAVE_KEYWORDS = (
    "mmwave",
    "praesenz",
    "presence",
    "radar",
    "fp2",
    "fp1",
    "ld2410",
    "ld2450",
    "human_presence",
    "anwesenheit",
)

GLASS_KEYWORDS = (
    "glas",
    "vibration",
    "erschuetterung",
    "glasbruch",
)

SMOKE_KEYWORDS = (
    "rauch",
    "smoke",
    "feuermelder",
    "brandmelder",
    "rauchmelder",
    "co_melder",
    "gasmelder",
)

PANIC_KEYWORDS = (
    "panik",
    "sos",
    "notruf",
    "ueberfall",
    "panic",
)

ENTRY_DELAY_KEYWORDS = (
    "haustuer",
    "eingang",
    "nebentuer",
    "garagentor",
    "tor",
)

EXCLUDED_DC = frozenset(
    (
        "battery",
        "battery_charging",
        "connectivity",
        "plug",
        "power",
        "energy",
        "running",
        "update",
        "moisture",
        "heat",
        "cold",
        "light",
        "problem",
        "sound",
    )
)

EXCLUDED_ID_PATTERNS = re.compile(
    r"(pixel_|galaxy_|iphone_|ipad_|sm_|app_|geocoded_|high_accuracy_|"
    r"backofen|geschirrspuel|geschirrspul|kuehlschrank|kuehl_|gefrier|waschmaschin|trockner|"
    r"deck_lid|sunroof|windows_closed|"
    r"_battery|_akku|_charging|_update|_signal_strength|_linkquality|"
    r"_voltage|_current|_power|_energy|_temperature|_humidity|_illuminance|_lux|_identify|_restart)",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Normalize umlauts and common character transcriptions for fuzzy matching."""
    s = text.lower().replace("_", " ").replace("-", " ")
    s = s.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return s


PLATFORM_LABELS: dict[str, str] = {
    "mqtt": "MQTT / Zigbee",
    "matter": "Matter",
    "hue": "Philips Hue",
    "zha": "Zigbee (ZHA)",
    "shelly": "Shelly",
    "esphome": "ESPHome",
    "homematicip_cloud": "Homematic IP",
    "homematicip_local": "Homematic IP (CCU)",
    "deconz": "deCONZ",
    "tapo": "TP-Link Tapo",
    "tuya": "Tuya",
    "reolink": "Reolink",
    "frigate": "Frigate",
    "unifiprotect": "UniFi Protect",
    "group": "Helfer-Gruppe",
    "template": "Template",
    "bthome": "BTHome (Bluetooth)",
    "smartthings": "SmartThings",
    "fritzbox": "FRITZ!Box",
    "xiaomi_miio": "Xiaomi",
    "xiaomi_ble": "Xiaomi BLE",
}

MANUFACTURER_ALIASES: dict[str, str] = {
    "signify netherlands b.v.": "Philips Hue",
    "lumi": "Aqara",
    "mayer & co beschlaege gmbh": "MACO",
}


def friendly_platform_label(platform: str | None) -> str:
    if not platform:
        return "Direkt"
    return PLATFORM_LABELS.get(platform, platform.replace("_", " ").title())


def friendly_manufacturer(manufacturer: str | None) -> str | None:
    if not manufacturer:
        return None
    cleaned = str(manufacturer).strip()
    return MANUFACTURER_ALIASES.get(cleaned.lower(), cleaned)


def build_room_matcher(
    rooms: dict[str, Any], areas: dict[str, str] | None = None
) -> list[tuple[str, str]]:
    """Build a priority list of (search_keyword, room_id) tuples sorted by keyword length descending."""
    aliases_map: dict[str, list[str]] = {
        "wc": ["gaste_wc", "gäste wc", "gästewc", "toilette", "klo", "gaste wc", "guest wc"],
        "hwr": ["hwr", "hauswirtschaftsraum", "hauswirtschaft", "utility room"],
        "garderobe": [
            "garderobe",
            "gardrobe",
            "diele",
            "eingang",
            "haustür",
            "haustuer",
            "eingangsbereich",
            "flur ug",
        ],
        "sophies bad": ["sophies bad", "sophies_bad", "kinderbad", "sbad"],
        "sophie": ["sophie", "kinderzimmer"],
        "garage": ["garage", "garagentor"],
        "garagenhof": ["garagenhof", "einfahrt", "hof", "garagenzufahrt", "driveway"],
        "terrasse": ["terrasse", "terras", "freisitz", "patio"],
        "dachboden": ["dachboden", "speicher", "bühne", "attic"],
        "fitnessraum": ["fitnessraum", "fitness", "sport", "gym"],
        "schlafzimmer": ["schlafzimmer", "elternschlafzimmer", "master bedroom", "bedroom"],
        "elternbad": ["elternbad", "hauptbad", "master bathroom"],
        "dusche": ["dusche", "duschbad"],
        "flur og": ["flur og", "flurog", "og flur", "obergeschoss flur"],
        "flur ug": ["flur ug", "flurug", "ug flur", "erdgeschoss flur", "eg flur"],
        "küche": ["küche", "kuche", "kitchen"],
        "büro": ["büro", "buero", "buro", "office", "arbeitszimmer"],
        "wohnzimmer": ["wohnzimmer", "living room"],
        "vorgarten": ["vorgarten", "front yard"],
        "garten": ["garten", "garden", "backyard"],
    }

    matcher_entries: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for rid, r in rooms.items():
        raw_name = (
            getattr(r, "name", None) or (r.get("name", "") if isinstance(r, dict) else "") or ""
        ).strip()
        raw_area = (
            getattr(r, "area_id", None)
            or (r.get("area_id", "") if isinstance(r, dict) else "")
            or ""
        ).strip()
        norm_name = normalize_text(raw_name)
        norm_area = normalize_text(raw_area)

        cands: set[str] = set()
        if raw_name:
            cands.add(raw_name.lower())
            cands.add(norm_name)
        if raw_area:
            cands.add(raw_area.lower())
            cands.add(norm_area)
            if areas and raw_area in areas:
                cands.add(areas[raw_area].lower())
                cands.add(normalize_text(areas[raw_area]))

        for key, aliases in aliases_map.items():
            if (
                key == norm_name
                or key == norm_area
                or key == raw_name.lower()
                or key == raw_area.lower()
            ):
                for alias in aliases:
                    cands.add(alias.lower())
                    cands.add(normalize_text(alias))

        for cand in cands:
            cleaned = cand.strip()
            if len(cleaned) >= 2 and (cleaned, rid) not in seen:
                seen.add((cleaned, rid))
                matcher_entries.append((cleaned, rid))

    # Match longer keywords first so "elternbad" matches before "bad"
    matcher_entries.sort(key=lambda x: len(x[0]), reverse=True)
    return matcher_entries


def classify_entity(entity_id: str, name: str, device_class: str | None) -> str | None:
    """Classify a Home Assistant entity into an IQAlarm role or return None if unrelated."""
    domain = entity_id.split(".")[0]
    if domain not in ALLOWED_SENSOR_DOMAINS:
        return None

    if EXCLUDED_ID_PATTERNS.search(entity_id):
        return None

    norm = normalize_text(f"{name} {entity_id}")

    # Check for excluded device classes unless explicit security keywords are present
    if device_class in EXCLUDED_DC and not any(
        k in norm for k in DOOR_WINDOW_KEYWORDS + MOTION_KEYWORDS + LOCK_KEYWORDS
    ):
        return None

    # 1. Panic
    if any(k in norm for k in PANIC_KEYWORDS):
        return Role.PANIC.value

    # 2. Smoke / Fire
    if device_class in ("smoke", "gas", "carbon_monoxide") or any(
        k in norm for k in SMOKE_KEYWORDS
    ):
        return Role.SMOKE.value

    # 3. Perimeter Camera / Person Detection
    if domain in ("camera", "image_processing"):
        return Role.PERIMETER_CAMERA.value
    if "person" in norm and domain == "binary_sensor":
        return Role.PERIMETER_CAMERA.value
    if "cctv" in norm and domain == "binary_sensor":
        if "bewegung" in norm and "person" not in norm:
            return Role.PERIMETER_SENSOR.value
        return Role.PERIMETER_CAMERA.value

    # 4. Glass / Vibration
    if device_class == "vibration" or any(k in norm for k in GLASS_KEYWORDS):
        return Role.GLASS.value

    # 5. Lock / Deadbolt
    if domain == "lock" or device_class == "lock" or any(k in norm for k in LOCK_KEYWORDS):
        return Role.LOCK.value

    # 6. Doors & Windows
    if device_class in ("door", "window", "opening", "garage_door") or any(
        k in norm for k in DOOR_WINDOW_KEYWORDS
    ):
        return Role.ENTRY.value

    # 7. Motion & Presence
    if device_class in ("motion", "occupancy", "presence") or any(
        k in norm for k in MOTION_KEYWORDS + MMWAVE_KEYWORDS
    ):
        if any(k in norm for k in OUTDOOR_KEYWORDS):
            return Role.PERIMETER_SENSOR.value
        if device_class == "presence" or any(k in norm for k in MMWAVE_KEYWORDS):
            return Role.MMWAVE.value
        return Role.MOTION.value

    return None


def sensor_setup(state, device_id: str | None = None) -> dict:
    """Propose real raw formats; a camera requires a verified detection attribute."""
    domain = state.entity_id.split(".", 1)[0]
    result = {
        "source_id": f"device:{device_id}" if device_id else state.entity_id,
        "attribute": None,
        "active_states": ["unlocked", "open"] if domain == "lock" else ["on"],
        "active_above": None,
        "setup_required": False,
        "setup_reason": "",
    }
    if domain in {"camera", "image_processing"}:
        for attribute in ("person_detected", "person", "persons", "person_count", "count_person"):
            value = state.attributes.get(attribute)
            if isinstance(value, bool):
                result.update(attribute=attribute, active_states=["true"])
                break
            if isinstance(value, (int, float)):
                result.update(attribute=attribute, active_above=0)
                break
        else:
            result.update(
                setup_required=True,
                setup_reason="Kein geprüftes Personenattribut: Personen-Binary-Sensor wählen oder Kamera manuell einrichten",
            )
    return result


def discover_sensors(
    hass: HomeAssistant,
    current_sensors: dict[str, Any],
    rooms: dict[str, Any],
) -> list[dict[str, Any]]:
    """Scan Home Assistant entities and propose security sensors with role and room assignments."""
    ent_reg = (
        entity_registry.async_get(hass)
        if entity_registry
        else getattr(hass, "entity_registry", None)
    )
    dev_reg = (
        device_registry.async_get(hass)
        if device_registry
        else getattr(hass, "device_registry", None)
    )
    ar_reg = (
        area_registry.async_get(hass) if area_registry else getattr(hass, "area_registry", None)
    )

    areas_map = {a.id: a.name for a in ar_reg.async_list_areas()} if ar_reg else {}
    matcher = build_room_matcher(rooms, areas_map)

    # Build direct area_id -> room_id lookup
    area_to_room: dict[str, str] = {}
    for rid, r in rooms.items():
        r_area = getattr(r, "area_id", None) or (r.get("area_id") if isinstance(r, dict) else None)
        r_name = getattr(r, "name", None) or (r.get("name") if isinstance(r, dict) else None)
        if r_area:
            area_to_room[r_area.lower()] = rid
            area_to_room[normalize_text(r_area)] = rid
        if r_name:
            area_to_room[r_name.lower()] = rid
            area_to_room[normalize_text(r_name)] = rid

    candidates: list[dict[str, Any]] = []

    for state in hass.states.async_all():
        entity_id = state.entity_id
        if entity_id in current_sensors:
            continue
        if entity_id.startswith(("sensor.iqalarm", "binary_sensor.iqalarm")):
            continue

        name = state.attributes.get("friendly_name") or entity_id
        dc = state.attributes.get("device_class")

        role = classify_entity(entity_id, name, dc)
        if not role:
            continue

        # Determine registry and device info
        entry = ent_reg.async_get(entity_id) if ent_reg else None
        platform = getattr(entry, "platform", None) if entry else None
        device_id = getattr(entry, "device_id", None) if entry else None
        dev = dev_reg.async_get(device_id) if (device_id and dev_reg) else None

        device_name = getattr(dev, "name", None) if dev else None
        raw_mfr = getattr(dev, "manufacturer", None) if dev else None
        manufacturer = friendly_manufacturer(raw_mfr)
        model = getattr(dev, "model", None) if dev else None

        effective_area_id = None
        if entry:
            effective_area_id = getattr(entry, "area_id", None)
            if not effective_area_id and dev:
                effective_area_id = getattr(dev, "area_id", None)

        # Room matching
        matched_room_id = None
        if effective_area_id:
            norm_area = normalize_text(effective_area_id)
            matched_room_id = area_to_room.get(effective_area_id.lower()) or area_to_room.get(
                norm_area
            )

        if not matched_room_id:
            norm_text = normalize_text(f"{name} {entity_id} {device_name or ''}")
            for keyword, rid in matcher:
                if keyword in norm_text:
                    matched_room_id = rid
                    break

        # Entry delay recommendation
        entry_delay = False
        if role == Role.ENTRY.value:
            norm_name = normalize_text(f"{name} {entity_id} {device_name or ''}")
            if any(k in norm_name for k in ENTRY_DELAY_KEYWORDS):
                entry_delay = True

        r_obj = rooms.get(matched_room_id) if matched_room_id else None
        r_name = (
            (
                getattr(r_obj, "name", None)
                or (r_obj.get("name") if isinstance(r_obj, dict) else None)
            )
            if r_obj
            else None
        )

        candidates.append(
            {
                "entity_id": entity_id,
                "name": name,
                "role": role,
                "room_id": matched_room_id,
                "room_name": r_name,
                "area_id": effective_area_id,
                "area_name": areas_map.get(effective_area_id) if effective_area_id else None,
                "device_class": dc,
                "state": state.state,
                "entry_delay": entry_delay,
                "platform": platform or "other",
                "integration_name": friendly_platform_label(platform),
                "device_id": device_id,
                "device_name": device_name,
                "manufacturer": manufacturer,
                "model": model,
                **sensor_setup(state, device_id),
            }
        )

    # Sort candidates by role and name for easy navigation
    role_order = {
        Role.ENTRY.value: 1,
        Role.LOCK.value: 2,
        Role.MOTION.value: 3,
        Role.MMWAVE.value: 4,
        Role.PERIMETER_CAMERA.value: 5,
        Role.PERIMETER_SENSOR.value: 6,
        Role.GLASS.value: 7,
        Role.SMOKE.value: 8,
        Role.PANIC.value: 9,
    }
    candidates.sort(key=lambda c: (role_order.get(c["role"], 99), c["name"].lower()))
    return candidates
