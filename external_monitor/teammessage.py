"""TeamMessage HTTPS adapter; never log credentials, recipients or response bodies."""

import json
import math
import re
import ssl
import urllib.error
import urllib.request

ENDPOINT = "https://www.teammessage.de/api/v1/sms/send/"
PHONE = re.compile(r"^\+[1-9][0-9]{6,14}$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None  # A redirect must never forward the Bearer credential.


class Outcome:
    def __init__(self, state, http_status=None, provider_code=None, retry_after=0):
        self.state = state
        self.http_status = http_status
        self.provider_code = provider_code
        self.retry_after = retry_after


def alarm_message(user_label, duration_seconds):
    if (
        not isinstance(user_label, str)
        or not user_label.strip()
        or len(user_label) > 80
        or not user_label.isprintable()
    ):
        raise ValueError("invalid_user_label")
    if (
        type(duration_seconds) not in (int, float)
        or not math.isfinite(duration_seconds)
        or not 0 <= duration_seconds <= 86400
    ):
        raise ValueError("invalid_duration")
    minutes, seconds = divmod(round(duration_seconds), 60)
    elapsed = []
    if minutes:
        elapsed.append(f"{minutes} {'Minute' if minutes == 1 else 'Minuten'}")
    if seconds or not minutes:
        elapsed.append(f"{seconds} {'Sekunde' if seconds == 1 else 'Sekunden'}")
    return (
        f"IQAlarm - ALARM LVL05! Die Alarmanlage von {user_label.strip()} "
        f"hat einen Einbruchsalarm gemeldet. Seit {' '.join(elapsed)} keine Entwarnung. "
        "Bitte sofort Anrufen und prüfen!"
    )


def payload_for(config, system_id, alarm_id, user_label="deinem Freund", duration_seconds=300):
    """Require an explicit per-installation recipient mapping, including in test mode."""
    if type(config.get("test_mode")) is not bool:
        raise ValueError("test_mode_required")
    token = config.get("token")
    if (
        not isinstance(token, str)
        or not token
        or not token.isascii()
        or any(c.isspace() for c in token)
    ):
        raise ValueError("invalid_token")
    settings = config.get("systems", {}).get(system_id)
    if not isinstance(settings, dict):
        raise ValueError("system_not_configured")
    team = settings.get("team_id")
    if type(team) is not int or team <= 0:
        raise ValueError("invalid_team")
    recipients = settings.get("recipients")
    if (
        not isinstance(recipients, list)
        or not recipients
        or len(recipients) > 3
        or any(not isinstance(p, str) or not PHONE.fullmatch(p) for p in recipients)
    ):
        raise ValueError("invalid_recipients")
    payload = {
        "team_id": team,
        "to_mobile": ",".join(dict.fromkeys(recipients)),
        "message": alarm_message(user_label, duration_seconds),
        # The provider's explicit UCS2 mode produced garbled text on the handset.
        # Use the normal SMS alphabet; the template's dash is GSM-7 compatible.
        "ucs2": 0,
        "test": int(config["test_mode"]),
    }
    if type(settings.get("tl")) is int and settings["tl"] > 0:
        payload["tl"] = settings["tl"]
    elif isinstance(settings.get("teamlist_email"), str) and "@" in settings["teamlist_email"]:
        payload["teamlist_email"] = settings["teamlist_email"]
    else:
        raise ValueError("invalid_teamlist")
    for name, limit in (("sender_email", 128), ("keyword", 32), ("from_mobile", 16)):
        value = settings.get(name, "")
        if not isinstance(value, str) or len(value) > limit or "\n" in value or "\r" in value:
            raise ValueError("invalid_sender_setting")
        if value:
            payload[name] = value
    return token, payload


class TeamMessage:
    def __init__(self, opener=None):
        self.opener = opener or urllib.request.build_opener(
            NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
        )

    def send(self, token, payload):
        request = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            try:
                response = self.opener.open(request, timeout=15)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                raw = response.read(65537)
            if len(raw) > 65536:
                return Outcome("uncertain", status)
            result = json.loads(raw)
            if not isinstance(result, dict):
                return Outcome("uncertain", status)
            code = result.get("code")
            if type(code) is not int:
                return Outcome("uncertain", status)
            if status == 429 and code == -13:
                delay = result.get("retry_after", 60)
                if type(delay) not in (int, float) or not math.isfinite(delay):
                    delay = 60
                return Outcome("retry", status, code, min(3600, max(1, delay)))
            if status == 200:
                if payload["test"] == 1 and code == 0 and result.get("message") == "TEST MODE":
                    return Outcome("validated", status, code)
                if payload["test"] == 0 and code == 1:
                    return Outcome("accepted", status, code)
            if status in (200, 400, 403) and code < 0:
                return Outcome("rejected", status, code)
            return Outcome("uncertain", status, code)
        except (OSError, ValueError, urllib.error.URLError):
            # No provider idempotency key: a lost response could follow an accepted SMS.
            return Outcome("uncertain")
