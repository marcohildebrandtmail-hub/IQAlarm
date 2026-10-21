"""Durable, authenticated remote monitoring with no networking while disabled."""

import asyncio
import secrets
import time
from uuid import uuid4


class ExternalMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self.state = {
            "id": uuid4().hex,
            "secret": secrets.token_urlsafe(32),
            "registered": False,
            "enabled": False,
            "queue": [],
            "observed": None,
            "status": "disabled",
        }
        self.task = None
        self.next_attempt = 0
        self.desired_enabled = None
        self.desired_label = None
        self.desired_phones = None

    def restore(self, state):
        if isinstance(state, dict) and len(state.get("id", "")) == 32 and state.get("secret"):
            self.state = {**self.state, **state}

    def public(self):
        return {
            "id": self.state["id"],
            "enabled": self.runtime.config.external_monitoring.get("enabled", False),
            "status": self.state["status"],
            "pending": len(self.state["queue"]),
        }

    def reconcile(self):
        enabled = self.runtime.config.external_monitoring.get("enabled", False)
        user_label = self.runtime.config.external_monitoring.get("user_label", "deinem Freund")
        phones = self.runtime.config.external_monitoring.get("phone_numbers")
        alarm = self.runtime.engine.alarm_state if self.runtime.engine.reactions_enabled else None
        old = self.state.get("observed")
        changed = (
            enabled != self.desired_enabled
            or user_label != self.desired_label
            or phones != self.desired_phones
        )
        self.desired_enabled = enabled
        self.desired_label = user_label
        self.desired_phones = list(phones) if phones is not None else None
        # An alarm already registered externally must be cancelled explicitly;
        # disconnection, disabled monitoring or an HA shutdown never cancels it.
        if old and (alarm is None or old != alarm["id"]):
            self.state["queue"] = [
                item
                for item in self.state["queue"]
                if not (item["id"] == old and item["operation"] == "start")
            ]
            self.state["queue"].append({"operation": "cancel", "id": old})
            self.state["observed"] = None
            changed = True
        if enabled and alarm and self.state["observed"] is None:
            item = {"operation": "start", "id": alarm["id"], "deadline": alarm["deadline"]}
            if alarm.get("duration") is not None:
                item["duration_seconds"] = alarm["duration"]
            self.state["queue"].append(item)
            self.state["observed"] = alarm["id"]
            changed = True
        if changed:
            self.next_attempt = 0
        wanted = enabled or bool(self.state["queue"]) or self.state["enabled"]
        if not wanted:
            self.state["status"] = "disabled"
            return
        if (
            not self.runtime.stopped
            and time.time() >= self.next_attempt
            and (self.task is None or self.task.done())
        ):
            self.task = self.runtime.hass.async_create_background_task(
                self.run(), "IQAlarm external monitoring"
            )

    async def request(self, method, path, body):
        import aiohttp
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        config = self.runtime.config.external_monitoring
        if not config.get("url"):
            raise ValueError("Dienstadresse fehlt")
        ssl = (
            aiohttp.Fingerprint(bytes.fromhex(config["certificate_sha256"]))
            if config.get("certificate_sha256")
            else True
        )
        session = async_get_clientsession(self.runtime.hass)
        async with session.request(
            method,
            config["url"].rstrip("/") + path,
            json=body,
            headers={"Authorization": "Bearer " + self.state["secret"]},
            ssl=ssl,
            timeout=aiohttp.ClientTimeout(total=5),
            allow_redirects=False,
        ) as response:
            result = await response.json()
            if response.status == 409 and path == "/v1/systems":
                return None
            if response.status not in (200, 201):
                raise OSError("Überwachungsdienst hat die Meldung nicht bestätigt")
            return result

    async def run(self):
        try:
            # Commit identity and outbox before transmitting anything.
            await self.runtime.persist()
            if not self.state["registered"]:
                for _ in range(8):
                    result = await self.request(
                        "POST",
                        "/v1/systems",
                        {"id": self.state["id"], "secret": self.state["secret"]},
                    )
                    if result is not None:
                        self.state["registered"] = True
                        break
                    self.state["id"] = uuid4().hex
                    self.state["secret"] = secrets.token_urlsafe(32)
                    await self.runtime.persist()
                else:
                    raise OSError("Keine freie System-ID erhalten")
            base = "/v1/systems/" + self.state["id"]
            enabled = self.runtime.config.external_monitoring.get("enabled", False)
            user_label = self.runtime.config.external_monitoring.get("user_label", "deinem Freund")
            metadata = {"user_label": user_label}
            if "phone_numbers" in self.runtime.config.external_monitoring:
                metadata["phone_numbers"] = self.runtime.config.external_monitoring["phone_numbers"]
            # Start messages must be delivered before a later disabling update.
            if enabled or any(item["operation"] == "start" for item in self.state["queue"]):
                await self.request("PUT", base + "/enabled", {"enabled": True, **metadata})
                self.state["enabled"] = True
            while self.state["queue"]:
                item = self.state["queue"][0]
                body = {"operation": item["operation"]}
                if item["operation"] == "start":
                    body["remaining_seconds"] = max(0, item["deadline"] - time.time())
                    if "duration_seconds" in item:
                        body["duration_seconds"] = item["duration_seconds"]
                result = await self.request("POST", base + "/alarms/" + item["id"], body)
                if result.get("id") != item["id"]:
                    raise OSError("Alarm-ID wurde nicht bestätigt")
                if item in self.state["queue"]:
                    self.state["queue"].remove(item)
                await self.runtime.persist()
            if not enabled and self.state["enabled"]:
                await self.request("PUT", base + "/enabled", {"enabled": False, **metadata})
                self.state["enabled"] = False
            self.state["status"] = "active" if enabled else "disabled"
            self.next_attempt = (
                time.time() + 30
                if (
                    enabled == self.runtime.config.external_monitoring.get("enabled", False)
                    and user_label
                    == self.runtime.config.external_monitoring.get("user_label", "deinem Freund")
                    and metadata.get("phone_numbers")
                    == self.runtime.config.external_monitoring.get("phone_numbers")
                )
                else 0
            )
            await self.runtime.persist()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Keep credentials and unacknowledged events private and durable.
            self.state["status"] = "pending"
            self.next_attempt = time.time() + 5
        finally:
            if (
                self.runtime.config.external_monitoring.get("enabled", False)
                != self.desired_enabled
                or self.state["queue"]
            ):
                self.next_attempt = min(self.next_attempt, time.time() + 5)
            self.runtime.publish()
