"""Provider results and durable SMS dispatch without contacting a real recipient."""

import io
import json
import secrets
import urllib.error
from uuid import uuid4

import pytest

from external_monitor.server import Monitor
from external_monitor.sms_worker import SMSWorker
from external_monitor.teammessage import ENDPOINT, Outcome, TeamMessage, payload_for


class Response(io.BytesIO):
    def __init__(self, status, result):
        super().__init__(json.dumps(result).encode())
        self.code = status


class Opener:
    def __init__(self, status, result):
        self.status, self.result, self.requests = status, result, []

    def open(self, request, timeout):
        self.requests.append(request)
        assert timeout == 15
        if self.status >= 400:
            raise urllib.error.HTTPError(
                ENDPOINT, self.status, "provider error", {}, Response(self.status, self.result)
            )
        return Response(self.status, self.result)


@pytest.mark.parametrize(
    "status,result,test_mode,state",
    [
        (200, {"code": 1}, False, "accepted"),
        (200, {"code": 0, "message": "TEST MODE"}, True, "validated"),
        (200, {"code": 0, "message": "TEST MODE"}, False, "uncertain"),
        (200, {"code": 1}, True, "uncertain"),
        (200, {"code": -10}, False, "rejected"),
        (400, {"code": -6}, False, "rejected"),
        (403, {"code": -14}, False, "rejected"),
        (429, {"code": -13, "retry_after": 12}, False, "retry"),
        (500, {"code": 1}, False, "uncertain"),
        (302, {"code": 1}, False, "uncertain"),
        (200, {"code": True}, False, "uncertain"),
        (200, [1], False, "uncertain"),
    ],
)
def test_provider_response_is_not_confused_with_delivery(status, result, test_mode, state):
    opener = Opener(status, result)
    outcome = TeamMessage(opener).send("unit-test-token", {"test": int(test_mode)})
    assert outcome.state == state
    request = opener.requests[0]
    assert request.full_url == ENDPOINT and request.method == "POST"
    assert request.get_header("Authorization") == "Bearer unit-test-token"
    assert "unit-test-token" not in request.full_url
    if state == "retry":
        assert outcome.retry_after == 12


@pytest.fixture
def setup(tmp_path):
    now = [1000.0]
    monitor = Monitor(tmp_path / "monitor.db", lambda: now[0])
    key, secret = uuid4().hex, secrets.token_urlsafe(32)
    monitor.request("POST", "/v1/systems", {"id": key, "secret": secret})
    base = "/v1/systems/" + key
    monitor.request("PUT", base + "/enabled", {"enabled": True}, secret)
    config = {
        "enabled": True,
        "test_mode": True,
        "active_from": 999,
        "token": "unit-test-token",
        "systems": {
            key: {
                "team_id": 123,
                "tl": 456,
                "sender_email": "unit@example.invalid",
                "from_mobile": "IQAlarm",
                "recipients": ["+4915112345678"],
            }
        },
    }
    alarm = uuid4().hex
    monitor.request(
        "POST", base + "/alarms/" + alarm, {"operation": "start", "remaining_seconds": 10}, secret
    )

    class Client:
        def __init__(self):
            self.calls = []
            self.outcome = Outcome("validated", 200, 0)

        def send(self, token, payload):
            self.calls.append(payload)
            return self.outcome

    client = Client()
    worker = SMSWorker(monitor.path, client, lambda: now[0])
    return monitor, worker, now, config, key, base, secret, alarm, client


def expire(setup):
    m, _, now, *_ = setup
    now[0] = 1010
    m.expire()


def test_timeout_dispatches_once_after_durable_claim(setup):
    m, worker, _, config, key, _, _, alarm, client = setup
    worker.tick(config)
    assert not client.calls
    expire(setup)
    original = client.send

    def check_claim(token, payload):
        with m.connect() as db:
            assert db.execute("SELECT state FROM sms_jobs").fetchone()[0] == "sending"
        return original(token, payload)

    client.send = check_claim
    worker.tick(config)
    worker.tick(config)
    SMSWorker(m.path, client, m.clock).tick(config)
    assert len(client.calls) == 1
    with m.connect() as db:
        assert (
            db.execute("SELECT action_state FROM escalations").fetchone()[0]
            == "teammessage_validated"
        )
    token, payload = payload_for(config, key, alarm)
    assert payload["from_mobile"] == "IQAlarm" and payload["test"] == 1
    assert len(payload["message"]) <= 160


@pytest.mark.parametrize("after_expiry", [False, True])
def test_cancellation_before_dispatch_prevents_sms(setup, after_expiry):
    m, worker, _, config, _, base, secret, alarm, client = setup
    if after_expiry:
        expire(setup)
    m.request("POST", base + "/alarms/" + alarm, {"operation": "cancel"}, secret)
    expire(setup)
    worker.tick(config)
    assert not client.calls


def test_disabled_and_historical_alarms_cannot_send(setup):
    _, worker, _, config, _, _, _, _, client = setup
    expire(setup)
    config["enabled"] = False
    worker.tick(config)
    config["enabled"] = True
    config["active_from"] = 1001
    worker.tick(config)
    assert not client.calls


def test_other_installation_cannot_use_recipients(setup):
    _, worker, _, config, key, _, _, _, client = setup
    expire(setup)
    config["systems"][uuid4().hex] = config["systems"].pop(key)
    worker.tick(config)
    assert not client.calls


def test_lost_response_and_process_crash_are_not_resent(setup):
    m, worker, _, config, _, _, _, _, client = setup
    expire(setup)

    def lost_response(*_):
        client.calls.append("sent-but-response-lost")
        raise TimeoutError

    client.send = lost_response
    worker.tick(config)
    worker.tick(config)
    with m.connect() as db:
        assert db.execute("SELECT state FROM sms_jobs").fetchone()[0] == "uncertain"
        db.execute("UPDATE sms_jobs SET state='sending'")
    SMSWorker(m.path, client, m.clock).tick(config)
    assert len(client.calls) == 1
    with m.connect() as db:
        assert db.execute("SELECT state FROM sms_jobs").fetchone()[0] == "uncertain"


def test_rate_limit_waits_and_cancellation_stops_retry(setup):
    m, worker, now, config, _, base, secret, alarm, client = setup
    expire(setup)
    client.outcome = Outcome("retry", 429, -13, 12)
    worker.tick(config)
    now[0] = 1021
    worker.tick(config)
    assert len(client.calls) == 1
    m.request("POST", base + "/alarms/" + alarm, {"operation": "cancel"}, secret)
    now[0] = 1022
    worker.tick(config)
    assert len(client.calls) == 1


def test_rate_limit_retries_at_most_three_times(setup):
    _, worker, now, config, _, _, _, _, client = setup
    expire(setup)
    for moment in (1010, 1022, 1034, 1046):
        client.outcome = Outcome("retry", 429, -13, 12)
        now[0] = moment
        worker.tick(config)
    assert len(client.calls) == 3


def test_missing_recipients_never_calls_provider(setup):
    _, worker, _, config, key, _, _, _, client = setup
    expire(setup)
    config["systems"][key]["recipients"] = []
    worker.tick(config)
    assert not client.calls


def test_invalid_other_tenant_does_not_block_a_valid_tenant(setup):
    _, worker, _, config, _, _, _, _, client = setup
    expire(setup)
    config["systems"][uuid4().hex] = {"recipients": []}
    worker.tick(config)
    assert len(client.calls) == 1


def test_empty_mapping_never_uses_a_global_recipient(setup):
    _, worker, _, config, _, _, _, _, client = setup
    expire(setup)
    config["systems"] = {}
    worker.tick(config)
    assert not client.calls


def test_health_reports_separate_worker_without_tenant_details(tmp_path):
    monitor = Monitor(tmp_path / "health.db")
    assert monitor.request("GET", "/health", {})[1]["actions"] == "unconfigured"
    SMSWorker(monitor.path)
    assert monitor.request("GET", "/health", {}) == (
        200,
        {"service": "iqalarm-monitor", "ok": True, "actions": "separate_worker"},
    )


def test_sms_keeps_original_alarm_duration_after_delayed_delivery(setup):
    m, worker, now, config, _, base, secret, alarm, client = setup
    m.request("POST", base + "/alarms/" + alarm, {"operation": "cancel"}, secret)
    assert (
        m.request(
            "PUT", base + "/enabled", {"enabled": True, "user_label": "Familie Beispiel"}, secret
        )[0]
        == 200
    )
    second = uuid4().hex
    assert (
        m.request(
            "POST",
            base + "/alarms/" + second,
            {"operation": "start", "remaining_seconds": 120, "duration_seconds": 300},
            secret,
        )[0]
        == 201
    )
    now[0] = 1120
    Monitor(m.path, m.clock).expire()
    worker.tick(config)
    assert len(client.calls) == 1
    assert client.calls[0]["message"] == (
        "IQAlarm - ALARM LVL05! Die Alarmanlage von Familie Beispiel hat einen Einbruchsalarm "
        "gemeldet. Seit 5 Minuten keine Entwarnung. Bitte sofort Anrufen und prüfen!"
    )
    assert client.calls[0]["ucs2"] == 0


def test_default_label_and_changed_time_follow_the_external_alarm(setup):
    _, worker, _, config, _, _, _, _, client = setup
    expire(setup)
    worker.tick(config)
    assert "von deinem Freund hat" in client.calls[0]["message"]
    assert "Seit 10 Sekunden keine Entwarnung" in client.calls[0]["message"]


def test_german_sms_uses_utf8_json_without_forcing_ucs2(setup):
    _, _, _, config, key, _, _, alarm, _ = setup
    token, payload = payload_for(config, key, alarm, "Müller & Söhne", 300)
    opener = Opener(200, {"code": 1})
    payload["test"] = 0
    assert TeamMessage(opener).send(token, payload).state == "accepted"
    request = opener.requests[0]
    submitted = json.loads(request.data.decode("utf-8"))
    assert submitted["ucs2"] == 0 and "–" not in submitted["message"]
    assert "von Müller & Söhne hat" in submitted["message"]
    assert submitted["message"].endswith("Bitte sofort Anrufen und prüfen!")
    assert "prüfen".encode() in request.data


def test_three_ui_numbers_replace_operator_recipients_in_one_request(setup):
    m, worker, _, config, key, base, secret, _, client = setup
    numbers = ["+4915111111111", "+4916111111111", "+4917111111111"]
    assert (
        m.request("PUT", base + "/enabled", {"enabled": True, "phone_numbers": numbers}, secret)[0]
        == 200
    )
    config["systems"][key]["recipients"] = []
    expire(setup)
    worker.tick(config)
    assert len(client.calls) == 1
    assert client.calls[0]["to_mobile"] == ",".join(numbers)


def test_removing_all_ui_numbers_does_not_fall_back_to_operator_phone(setup):
    m, worker, _, config, _, base, secret, _, client = setup
    assert (
        m.request("PUT", base + "/enabled", {"enabled": True, "phone_numbers": []}, secret)[0]
        == 200
    )
    expire(setup)
    worker.tick(config)
    assert not client.calls
