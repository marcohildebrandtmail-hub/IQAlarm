"""Remote watchdog durability, tenant isolation and idempotent messages."""

import importlib.util
import secrets
from pathlib import Path
from uuid import uuid4

import pytest
from iqalarm_core.models import Settings as ScenarioSettings

spec = importlib.util.spec_from_file_location(
    "iqalarm_watchdog", Path(__file__).parents[1] / "external_monitor/server.py"
)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


@pytest.fixture
def monitor(tmp_path):
    now = [1000.0]
    m = server.Monitor(tmp_path / "watchdog.db", lambda: now[0])
    key, secret = uuid4().hex, secrets.token_urlsafe(32)
    assert m.request("POST", "/v1/systems", {"id": key, "secret": secret})[0] == 201
    base = "/v1/systems/" + key
    assert m.request("PUT", base + "/enabled", {"enabled": True}, secret)[0] == 200
    return m, now, base, secret


def start(m, base, secret, alarm, remaining=300):
    return m.request(
        "POST",
        base + "/alarms/" + alarm,
        {"operation": "start", "remaining_seconds": remaining},
        secret,
    )


def test_registration_collision_and_retry(monitor):
    m, _, base, secret = monitor
    key = base.split("/")[-1]
    assert m.request("POST", "/v1/systems", {"id": key, "secret": secret})[0] == 200
    assert (
        m.request("POST", "/v1/systems", {"id": key, "secret": secrets.token_urlsafe(32)})[0] == 409
    )


def test_duplicate_start_never_extends_deadline(monitor):
    m, now, base, secret = monitor
    a = uuid4().hex
    assert start(m, base, secret, a)[1]["deadline"] == 1300
    now[0] = 1100
    assert start(m, base, secret, a)[1]["deadline"] == 1300
    now[0] = 1300
    m.expire()
    assert m.request("GET", base + "/alarms/" + a, {}, secret)[1]["state"] == "escalated"
    m.expire()
    with m.connect() as db:
        assert db.execute("SELECT count(*) FROM escalations").fetchone()[0] == 1


def test_cancel_before_deadline_and_reordered_start(monitor):
    m, now, base, secret = monitor
    a = uuid4().hex
    assert m.request("POST", base + "/alarms/" + a, {"operation": "cancel"}, secret)[0] == 200
    assert start(m, base, secret, a)[1]["state"] == "cancelled"
    now[0] = 1400
    m.expire()
    with m.connect() as db:
        assert db.execute("SELECT count(*) FROM escalations").fetchone()[0] == 0


def test_ha_disappearance_and_restart_do_not_clear_timer(monitor):
    m, now, base, secret = monitor
    a = uuid4().hex
    start(m, base, secret, a)
    now[0] = 1400
    restarted = server.Monitor(m.path, m.clock)
    restarted.expire()
    assert restarted.request("GET", base + "/alarms/" + a, {}, secret)[1]["state"] == "escalated"
    assert (
        restarted.request("POST", base + "/alarms/" + a, {"operation": "cancel"}, secret)[1][
            "state"
        ]
        == "cancelled_after_escalation"
    )


def test_other_tenant_cannot_read_or_cancel(monitor):
    m, _, base, secret = monitor
    a = uuid4().hex
    start(m, base, secret, a)
    for method, body in [("GET", {}), ("POST", {"operation": "cancel"})]:
        assert m.request(method, base + "/alarms/" + a, body, secrets.token_urlsafe(32))[0] == 401


def test_disabling_does_not_erase_started_alarm(monitor):
    m, now, base, secret = monitor
    a = uuid4().hex
    start(m, base, secret, a)
    m.request("PUT", base + "/enabled", {"enabled": False}, secret)
    assert start(m, base, secret, uuid4().hex)[0] == 409
    now[0] = 1400
    m.expire()
    assert m.request("GET", base + "/alarms/" + a, {}, secret)[1]["state"] == "escalated"


def test_nonfinite_or_negative_deadlines_are_rejected(monitor):
    m, _, base, secret = monitor
    for value in (-1, True, float("nan"), float("inf"), 100000):
        assert start(m, base, secret, uuid4().hex, value)[0] == 400


def test_monitoring_is_off_without_network_or_identity_leak():
    from types import SimpleNamespace as NS

    from iqalarm_core.external_monitor import ExternalMonitor

    runtime = NS(
        config=NS(external_monitoring={"enabled": False, "phone_numbers": ["+4915112345678"]}),
        engine=NS(alarm_state=None, reactions_enabled=False),
        stopped=False,
    )
    client = ExternalMonitor(runtime)
    client.reconcile()
    assert client.task is None and client.public()["status"] == "disabled"
    assert "secret" not in client.public()


def test_client_retries_collision_and_delivers_cancel_after_lost_ack():
    import asyncio
    from types import SimpleNamespace as NS

    from iqalarm_core.external_monitor import ExternalMonitor

    async def check():
        runtime = NS(
            config=NS(external_monitoring={"enabled": True}), stopped=False, publish=lambda: None
        )

        async def persist():
            pass

        runtime.persist = persist
        client = ExternalMonitor(runtime)
        old_id = client.state["id"]
        calls = []

        async def request(method, path, body):
            calls.append((method, path, body))
            if path == "/v1/systems":
                return None if len([x for x in calls if x[1] == path]) == 1 else {"id": body["id"]}
            if "/alarms/" in path:
                return {"id": path.split("/")[-1]}
            return {"enabled": True}

        client.request = request
        client.state["queue"] = [{"id": "a" * 32, "operation": "start", "deadline": 100}]
        await client.run()
        assert client.state["id"] != old_id and client.state["registered"]
        assert not client.state["queue"]
        assert any(x[2].get("remaining_seconds") == 0 for x in calls)
        client.state["queue"] = [{"id": "a" * 32, "operation": "cancel"}]
        await client.run()
        assert not client.state["queue"]

    asyncio.run(check())


def test_new_alarm_and_manual_cancel_bypass_periodic_refresh_delay():
    from types import SimpleNamespace as NS

    from iqalarm_core.external_monitor import ExternalMonitor

    runtime = NS(
        config=NS(external_monitoring={"enabled": True}),
        engine=NS(alarm_state=None, reactions_enabled=True),
        stopped=True,
    )
    client = ExternalMonitor(runtime)
    client.reconcile()
    client.next_attempt = 10**20
    runtime.engine.alarm_state = {"id": "b" * 32, "deadline": 1000}
    client.reconcile()
    assert client.next_attempt == 0 and client.state["queue"][0]["operation"] == "start"
    client.next_attempt = 10**20
    runtime.engine.alarm_state = None
    client.reconcile()
    assert client.next_attempt == 0 and client.state["queue"] == [
        {"operation": "cancel", "id": "b" * 32}
    ]


def test_user_label_is_authenticated_and_invalid_metadata_is_rejected(monitor):
    m, _, base, secret = monitor
    body = {"enabled": True, "user_label": "Familie Beispiel"}
    assert m.request("PUT", base + "/enabled", body, secrets.token_urlsafe(32))[0] == 401
    assert m.request("PUT", base + "/enabled", body, secret)[0] == 200
    assert m.request("PUT", base + "/enabled", {"enabled": True}, secret)[0] == 200
    with m.connect() as db:
        assert db.execute("SELECT user_label FROM systems").fetchone()[0] == "Familie Beispiel"
    for label in (None, "", "a" * 81, "Test\nAndere Nachricht"):
        assert m.request("PUT", base + "/enabled", {**body, "user_label": label}, secret)[0] == 400
    for duration in (True, float("nan"), 0, 100001, 1):
        assert (
            m.request(
                "POST",
                base + "/alarms/" + uuid4().hex,
                {"operation": "start", "remaining_seconds": 120, "duration_seconds": duration},
                secret,
            )[0]
            == 400
        )


def test_legacy_database_migration_keeps_identity_and_running_deadline(tmp_path):
    import hashlib
    import sqlite3

    path = tmp_path / "legacy.db"
    key, secret, alarm = uuid4().hex, secrets.token_urlsafe(32), uuid4().hex
    with sqlite3.connect(path) as db:
        db.executescript("""CREATE TABLE systems (
            id TEXT PRIMARY KEY,secret_hash TEXT NOT NULL,enabled INTEGER NOT NULL,created REAL NOT NULL);
            CREATE TABLE alarms(system_id TEXT NOT NULL,id TEXT NOT NULL,deadline REAL,state TEXT NOT NULL,
            created REAL NOT NULL,cancelled REAL,PRIMARY KEY(system_id,id));""")
        db.execute(
            "INSERT INTO systems VALUES(?,?,1,1000)",
            (key, hashlib.sha256(secret.encode()).hexdigest()),
        )
        db.execute("INSERT INTO alarms VALUES(?,?,1300,'pending',1000,NULL)", (key, alarm))
    migrated = server.Monitor(path, lambda: 1100)
    result = migrated.request("GET", f"/v1/systems/{key}/alarms/{alarm}", {}, secret)
    assert result[0] == 200 and result[1]["deadline"] == 1300
    assert result[1]["state"] == "pending" and result[1]["duration_seconds"] is None
    with migrated.connect() as db:
        assert db.execute("SELECT user_label FROM systems").fetchone()[0] == "deinem Freund"


def test_client_transmits_ui_label_and_original_duration_without_restarting_timer(monkeypatch):
    import asyncio
    from types import SimpleNamespace as NS

    from iqalarm_core.external_monitor import ExternalMonitor

    async def check():
        runtime = NS(
            config=NS(
                external_monitoring={
                    "enabled": True,
                    "user_label": "Familie Beispiel",
                    "phone_numbers": ["+4915112345678", "+4916112345678"],
                }
            ),
            engine=NS(
                reactions_enabled=True,
                alarm_state={
                    "id": "c" * 32,
                    "deadline": 400,
                    "duration": 300,
                },
            ),
            stopped=True,
            publish=lambda: None,
        )

        async def persist():
            pass

        runtime.persist = persist
        client = ExternalMonitor(runtime)
        client.reconcile()
        calls = []

        async def request(method, path, body):
            calls.append((method, path, body))
            return (
                {"id": body["id"]}
                if path == "/v1/systems"
                else ({"id": path.split("/")[-1]} if "/alarms/" in path else {"enabled": True})
            )

        client.request = request
        monkeypatch.setattr("iqalarm_core.external_monitor.time.time", lambda: 190)
        await client.run()
        assert any(
            body
            == {
                "enabled": True,
                "user_label": "Familie Beispiel",
                "phone_numbers": ["+4915112345678", "+4916112345678"],
            }
            for _, _, body in calls
        )
        assert any(
            body == {"operation": "start", "remaining_seconds": 210, "duration_seconds": 300}
            for _, _, body in calls
        )
        runtime.config.external_monitoring["user_label"] = "Anderer Name"
        client.next_attempt = 10**20
        client.reconcile()
        assert client.next_attempt == 0

    asyncio.run(check())


@pytest.mark.parametrize(
    "numbers,normalized",
    [
        ([], []),
        (
            ["+49 151 12345678", "0049-161-12345678", "+49 (171) 12345678"],
            ["+4915112345678", "+4916112345678", "+4917112345678"],
        ),
        (["+4915112345678", "0049 151 12345678", ""], ["+4915112345678"]),
    ],
)
def test_phone_numbers_normalize_consistently_in_ha_and_remote(monitor, numbers, normalized):
    import json

    from iqalarm_core.models import Configuration

    config = Configuration(
        settings=ScenarioSettings(startup_delay_seconds=0),
        external_monitoring={"enabled": False, "phone_numbers": numbers},
    )
    config.validate()
    assert config.external_monitoring["phone_numbers"] == normalized
    m, _, base, secret = monitor
    assert (
        m.request("PUT", base + "/enabled", {"enabled": True, "phone_numbers": numbers}, secret)[0]
        == 200
    )
    with m.connect() as db:
        assert (
            json.loads(db.execute("SELECT phone_numbers FROM systems").fetchone()[0]) == normalized
        )


@pytest.mark.parametrize(
    "numbers", [None, "12345", [123], ["015112345678"], ["+4915112345678"] * 4, ["+49broken"]]
)
def test_invalid_phone_numbers_are_rejected_without_changing_recipients(monitor, numbers):
    from iqalarm_core.models import Configuration

    with pytest.raises(ValueError):
        Configuration(
            settings=ScenarioSettings(startup_delay_seconds=0),
            external_monitoring={"phone_numbers": numbers},
        ).validate()
    m, _, base, secret = monitor
    assert (
        m.request("PUT", base + "/enabled", {"enabled": True, "phone_numbers": numbers}, secret)[0]
        == 400
    )
    with m.connect() as db:
        assert db.execute("SELECT phone_numbers FROM systems").fetchone()[0] is None


def test_other_tenant_cannot_replace_phone_numbers(monitor):
    m, _, base, _ = monitor
    assert (
        m.request(
            "PUT",
            base + "/enabled",
            {"enabled": True, "phone_numbers": ["+4915112345678"]},
            secrets.token_urlsafe(32),
        )[0]
        == 401
    )
    with m.connect() as db:
        assert db.execute("SELECT phone_numbers FROM systems").fetchone()[0] is None
