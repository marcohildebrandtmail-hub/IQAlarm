"""Read-only data shared with authenticated Home Assistant dashboard viewers."""


def _pick(data, fields):
    return {key: data[key] for key in fields.split() if key in data}


def dashboard_snapshot(instance):
    snapshot = instance.snapshot()
    config = snapshot["config"]
    status = snapshot["status"]
    display = _pick(
        status,
        "server_time active mode confirmed profile_id profile_name level stage_id stage_name "
        "arming_until arming_started_at pending_until raw last_active robot_paused_sensors "
        "ignored_windows",
    )
    display["coverage"] = _pick(status["coverage"], "current target")
    display["alarm"] = (
        _pick(status["alarm"], "stage_id escalated started_at deadline duration")
        if status["alarm"]
        else None
    )
    display["rooms"] = {}
    for room_id, room in status["rooms"].items():
        entry = _pick(room, "level confirmed open motion persons quarantined")
        if "recognitions" in room:
            entry["recognitions"] = [
                _pick(recognition, "stage_id level confirmed event expires_at")
                | {
                    "sources": [
                        _pick(source, "entity_id role") for source in recognition["sources"]
                    ]
                }
                for recognition in room["recognitions"]
            ]
        display["rooms"][room_id] = entry
    display["rule_progress"] = []
    for progress in status["rule_progress"]:
        entry = _pick(progress, "stage_id current target next_level_at detected_at thresholds")
        for key in ("person_reports", "motion_reports"):
            if key in progress:
                entry[key] = [
                    _pick(report, "entity_id room_id role source_id timestamp expires_at")
                    for report in progress[key]
                ]
        display["rule_progress"].append(entry)

    return {
        "available": True,
        "status": display,
        "config": {
            **_pick(config, "secure_stage_id room_connections floorplans"),
            "automatic_detection": _pick(
                config.get("automatic_detection") or {}, "stage_id promote_seconds"
            ),
            "stages": [_pick(stage, "id name color") for stage in config["stages"]],
            "settings": _pick(
                config["settings"],
                "startup_delay_seconds floorplan_armed_animation floorplan_disarmed_animation "
                "floorplan_disarmed_motion floorplan_disarmed_contacts floorplan_disarmed_locks "
                "floorplan_disarmed_cameras",
            ),
            "rooms": {key: _pick(room, "id name") for key, room in config["rooms"].items()},
            "sensors": {
                key: _pick(
                    sensor,
                    "entity_id name room_id front_of role enabled sensor_kind activation_mode",
                )
                for key, sensor in config["sensors"].items()
            },
            "windows": {
                key: _pick(
                    window,
                    "id name room_id enabled contact_entity_id handle_entity_ids lock_entity_id availability_entity_id",
                )
                for key, window in config["windows"].items()
            },
            "robots": {key: _pick(robot, "enabled") for key, robot in config["robots"].items()},
        },
        "window_details": {
            key: [_pick(source, "entity_id") for source in sources]
            for key, sources in snapshot["window_details"].items()
        },
        "information": [_pick(item, "room_id") for item in snapshot["information"]],
    }
