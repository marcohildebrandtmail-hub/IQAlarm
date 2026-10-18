"""Bounded, cancellable stage actions with guarded outputs and private media."""

import asyncio
import json
import logging
import re
import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .models import Action, EventLog

_LOGGER = logging.getLogger(__name__)
VARIABLE = re.compile(r"{{\s*(room|sensor|level|reason|chain|mode|profile)\s*}}")


class ActionDispatcher:
    """Never execute a stale alarm action after disarming; never run loud level 2."""

    def __init__(self, hass: HomeAssistant, runtime) -> None:
        self.hass = hass
        self.runtime = runtime
        self.locks = defaultdict(asyncio.Lock)
        self.outputs: dict[str, dict] = {}
        self.media_dir = Path(hass.config.path(".iqalarm_media"))
        self.simulation_outputs: set[str] = set()
        self._added_media_path = False

    async def initialize(self) -> None:
        await self.hass.async_add_executor_job(self.media_dir.mkdir, 0o700, True, True)
        if str(self.media_dir) not in self.hass.config.allowlist_external_dirs:
            self.hass.config.allowlist_external_dirs.add(str(self.media_dir))
            self._added_media_path = True
        self.outputs = dict(self.runtime.store.outputs)
        for owned in self.outputs.values():
            self._normalize_ownership(owned)
        self.simulation_outputs = {
            target for target, owned in self.outputs.items() if owned.get("simulation_until", 0)
        }
        await self.cleanup(force=not self.runtime.engine.reactions_enabled)
        if self.runtime.engine.confirmed and self.runtime.engine.reactions_enabled:
            for owned in self.outputs.values():
                if owned.get("alarm_until", 0) > time.time() and owned["kind"] in {
                    "siren",
                    "light",
                    "switch",
                }:
                    owned["resume_at"] = 0
            await self.resume_outputs()
        await self.prune_media()

    async def resume_outputs(self) -> None:
        if not self.runtime.engine.confirmed or not self.runtime.engine.reactions_enabled:
            return
        generation = self.runtime.generation

        async def resume(target):
            async with self.locks[target]:
                owned = self.outputs.get(target)
                if (
                    not owned
                    or "resume_at" not in owned
                    or owned["resume_at"] > time.time()
                    or owned.get("alarm_until", 0) <= time.time()
                ):
                    return
                try:
                    await self._call(
                        owned["kind"],
                        "turn_on",
                        owned.get("data", {"entity_id": target}),
                        generation,
                    )
                except (HomeAssistantError, TimeoutError) as err:
                    owned["resume_at"] = time.time() + 30
                    self.runtime.report(
                        "action_failed", f"Alarm-Ausgang nach Neustart: {target}: {err}"
                    )
                else:
                    owned.pop("resume_at", None)

        await asyncio.gather(*(resume(target) for target in list(self.outputs)))

    def release_media_path(self) -> None:
        if self._added_media_path:
            self.hass.config.allowlist_external_dirs.discard(str(self.media_dir))
            self._added_media_path = False

    def variables(self, event: EventLog) -> dict[str, str]:
        sensor = self.runtime.engine.sensors.get(event.entity_id)
        room = self.runtime.config.rooms.get(event.room_id or (sensor.room_id if sensor else None))
        chain = " → ".join(
            f"{e['name']} [{dt_util.as_local(datetime.fromtimestamp(e['timestamp'], UTC)).strftime('%H:%M:%S')}]"
            for e in event.chain
        )
        return {
            "room": room.name if room else "Haus",
            "sensor": (sensor.name or sensor.entity_id) if sensor else "IQAlarm",
            "level": str(event.level),
            "reason": event.reason,
            "chain": chain,
            "mode": event.mode,
            "profile": event.profile_name,
        }

    def render(self, template: str, variables: dict[str, str]) -> str:
        return VARIABLE.sub(lambda m: variables[m[1]], template)

    async def _call(
        self,
        domain: str,
        service: str,
        data: dict,
        generation: int | None = None,
        expected_stage: str | None = None,
    ) -> None:
        if generation is not None and generation != self.runtime.generation:
            return
        if expected_stage is not None and expected_stage != self.runtime.engine.stage_id:
            return
        if not self.hass.services.has_service(domain, service):
            raise HomeAssistantError(f"Dienst {domain}.{service} ist nicht verfügbar")
        async with asyncio.timeout(30):
            await self.hass.services.async_call(domain, service, data, blocking=True)

    async def snapshot(self, camera: str) -> str:
        """Save outside /local and expose only through the authenticated media view."""
        name = f"{int(time.time())}_{secrets.token_hex(10)}.jpg"
        await self._call(
            "camera", "snapshot", {"entity_id": camera, "filename": str(self.media_dir / name)}
        )
        await self.hass.async_add_executor_job(
            (self.media_dir / (name + ".json")).write_text, json.dumps({"camera_entity_id": camera})
        )
        return f"/api/iqalarm/media/{name}"

    async def _record(self, camera: str, duration: int) -> None:
        name = f"{int(time.time())}_{secrets.token_hex(10)}.mp4"
        await self._call(
            "camera",
            "record",
            {
                "entity_id": camera,
                "filename": str(self.media_dir / name),
                "duration": min(duration, 120),
                "lookback": 5,
            },
        )

    async def dispatch(
        self, event: EventLog, generation: int, dry_run: bool = False, stage: str | None = None
    ) -> list[dict]:
        stage = stage or ("diagnostic" if event.kind == "quarantined_flapping" else event.stage_id)
        profile = self.runtime.config.profiles.get(event.profile_id)
        actions = [
            a
            for a in self.runtime.config.actions.values()
            if a.enabled
            and a.level == stage
            and (profile is None or profile.action_ids is None or a.id in profile.action_ids)
        ]
        if stage != "diagnostic":
            configured_stage = self.runtime.config.stage(stage)
            actions = [
                action
                for action in actions
                if not (action.kind in {"siren", "switch", "script", "tts"} or action.critical)
                or (event.confirmed and configured_stage.allow_loud)
            ]
        plan = [{"id": a.id, "kind": a.kind, "target": a.target, "level": a.level} for a in actions]
        cameras = set()
        for evidence in event.chain:
            sensor = self.runtime.engine.sensors.get(evidence["entity_id"])
            if sensor and sensor.camera_entity_id:
                cameras.add(sensor.camera_entity_id)
            elif sensor and sensor.entity_id.startswith("camera."):
                cameras.add(sensor.entity_id)
        if (
            event.kind != "test"
            and event.chain
            and all(e["role"].startswith("perimeter") for e in event.chain)
        ):
            for camera in sorted(cameras):
                if self.runtime.config.settings.auto_camera_snapshot:
                    plan.append({"kind": "snapshot", "target": camera, "automatic": True})
                if self.runtime.config.settings.auto_camera_record:
                    plan.append({"kind": "record", "target": camera, "automatic": True})
        if dry_run:
            return plan
        allowed = (
            bool(profile and profile.reactions_enabled)
            if event.kind == "test"
            else event.reactions_enabled and self.runtime.engine.reactions_enabled
        )
        if not allowed:
            if event.kind == "test":
                raise ValueError("Dieses Profil erlaubt nur Beobachtung; kein realer Aktionstest")
            return []
        variables = self.variables(event)
        throttle = asyncio.Semaphore(8)

        async def automatic_action(automatic: dict) -> None:
            async with throttle:
                if generation != self.runtime.generation:
                    return
                try:
                    if automatic["kind"] == "snapshot":
                        await self.snapshot(automatic["target"])
                    else:
                        await self._record(automatic["target"], 30)
                except (HomeAssistantError, TimeoutError, OSError) as err:
                    self.runtime.report("action_failed", f"Kamera: {err}")

        async def configured_action(action: Action) -> None:
            async with throttle:
                if generation != self.runtime.generation:
                    return
                try:
                    if action.kind in {"siren", "switch", "light", "script"}:
                        async with self.locks[action.target]:
                            if generation == self.runtime.generation and (
                                event.kind == "test"
                                or stage == "diagnostic"
                                or self.runtime.engine.stage_id == event.stage_id
                            ):
                                await self.execute(
                                    action,
                                    variables,
                                    generation,
                                    expected_stage=None
                                    if event.kind == "test" or stage == "diagnostic"
                                    else event.stage_id,
                                )
                    else:
                        await self.execute(action, variables, generation)
                except (HomeAssistantError, TimeoutError, OSError, ValueError) as err:
                    _LOGGER.warning("IQAlarm action %s failed: %s", action.id, err)
                    self.runtime.report(
                        "action_failed", f"Aktion {action.kind}/{action.target}: {err}"
                    )

        priorities = {"siren": 0, "switch": 1, "light": 2, "cover": 3, "notify": 4}
        actions.sort(key=lambda a: priorities.get(a.kind, 5))
        await asyncio.gather(
            *(configured_action(a) for a in actions),
            *(automatic_action(p) for p in plan if p.get("automatic")),
        )
        await self._persist_outputs()
        return plan

    async def _persist_outputs(self) -> None:
        try:
            async with asyncio.timeout(2):
                await self.runtime.persist()
        except (HomeAssistantError, OSError, TimeoutError) as err:
            self.runtime.report("runtime_error", f"Aktionszustand nicht gespeichert: {err}")

    async def execute(
        self,
        action: Action,
        variables: dict[str, str],
        generation: int,
        expected_stage: str | None = None,
    ) -> None:
        if action.kind == "notify":
            title = self.render(action.title, variables)
            message = self.render(action.message, variables)
            data: dict = {}
            if action.camera_entity_id:
                try:
                    data["image"] = await self.snapshot(action.camera_entity_id)
                    data["entity_id"] = action.camera_entity_id
                except (HomeAssistantError, TimeoutError, OSError) as err:
                    # A broken camera must not suppress the intrusion notification.
                    self.runtime.report("action_failed", f"Push-Bild fehlgeschlagen: {err}")
            if action.critical:
                data.update(
                    {
                        "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
                        "ttl": 0,
                        "priority": "high",
                        "channel": "alarm_stream",
                    }
                )
            if self.hass.services.has_service("notify", action.target.split(".", 1)[1]):
                await self._call(
                    "notify",
                    action.target.split(".", 1)[1],
                    {"title": title, "message": message, "data": data},
                    generation,
                )
            else:
                if action.camera_entity_id or action.critical:
                    raise ValueError(
                        "Kritische Pushs und Bilder benötigen einen Mobile-App-notify-Dienst"
                    )
                await self._call(
                    "notify",
                    "send_message",
                    {"entity_id": action.target, "title": title, "message": message},
                    generation,
                )
        elif action.kind in {"siren", "switch", "light", "script"}:
            domain = action.kind
            state = self.hass.states.get(action.target)
            was_on = state is not None and state.state == "on"
            data = {"entity_id": action.target}
            if domain == "light":
                data["brightness_pct"] = action.brightness
                if action.color:
                    data["rgb_color"] = action.color
            if not was_on or domain == "script":
                # Record ownership before calling, covering services that turn on
                # an output but return a timeout or lose their acknowledgement.
                self._claim(action.target, domain, time.time() + action.duration, "alarm", data)
                await self._persist_outputs()
            elif action.target in self.outputs:
                self._claim(action.target, domain, time.time() + action.duration, "alarm", data)
            await self._call(domain, "turn_on", data, generation, expected_stage)
        elif action.kind == "cover":
            await self._call("cover", "open_cover", {"entity_id": action.target}, generation)
        elif action.kind == "snapshot":
            await self.snapshot(action.target)
        elif action.kind == "record":
            await self._record(action.target, action.duration)
        elif action.kind == "tts":
            await self._call(
                "tts",
                "speak",
                {
                    "entity_id": action.target,
                    "media_player_entity_id": action.media_player,
                    "message": self.render(action.message, variables),
                    "cache": False,
                },
                generation,
            )

    @staticmethod
    def _normalize_ownership(owned: dict) -> None:
        if "alarm_until" not in owned and "simulation_until" not in owned:
            owned["simulation_until" if owned.get("simulation") else "alarm_until"] = owned["until"]
        owned["until"] = max(owned.get("alarm_until", 0), owned.get("simulation_until", 0))

    def _claim(self, target: str, kind: str, deadline: float, reason: str, data: dict) -> None:
        owned = self.outputs.setdefault(target, {"kind": kind, "until": 0})
        self._normalize_ownership(owned)
        owned[reason + "_until"] = max(owned.get(reason + "_until", 0), deadline)
        owned["data"] = data
        owned.pop("retry_at", None)
        self._normalize_ownership(owned)

    def release_simulation(self) -> None:
        for target in list(self.simulation_outputs):
            if target in self.outputs:
                owned = self.outputs[target]
                self._normalize_ownership(owned)
                owned["simulation_until"] = 0
                self._normalize_ownership(owned)
            self.simulation_outputs.discard(target)

    async def cleanup(
        self,
        force: bool = False,
        *,
        alarm_only: bool = False,
        secure_only: bool = False,
        generation: int | None = None,
    ) -> None:
        """Serialize per device; alarm and simulation keep independent deadlines."""

        async def stop_output(target):
            async with self.locks[target]:
                if generation is not None and generation != self.runtime.generation:
                    return
                if secure_only and not self.runtime.engine.secure:
                    return
                owned = self.outputs.get(target)
                if owned is None:
                    return
                if owned["until"] == 0:
                    owned["alarm_until"] = owned["simulation_until"] = 0
                self._normalize_ownership(owned)
                if alarm_only:
                    owned["alarm_until"] = 0
                    self._normalize_ownership(owned)
                    if owned["until"] > time.time():
                        return
                now = time.time()
                if not force and now < max(owned["until"], owned.get("retry_at", 0)):
                    return
                try:
                    await self._call(owned["kind"], "turn_off", {"entity_id": target})
                except (HomeAssistantError, TimeoutError) as err:
                    owned["retry_at"] = time.time() + 30
                    self.runtime.report("action_failed", f"Abschaltung {target}: {err}")
                else:
                    self.outputs.pop(target, None)
                    self.simulation_outputs.discard(target)

        await asyncio.gather(*(stop_output(target) for target in list(self.outputs)))

    async def simulate(self, local_hour: int) -> None:
        config = self.runtime.config.settings
        enabled = (
            self.runtime.engine.profile is not None
            and self.runtime.engine.profile.simulation_enabled
            and self.runtime.engine.reactions_enabled
            and not self.runtime.engine.confirmed
            and config.simulation_enabled
            and config.simulation_start <= local_hour < config.simulation_end
        )
        if not enabled:
            self.release_simulation()
            return
        available = [
            s
            for e in config.simulation_lights
            if (s := self.hass.states.get(e)) and s.state == "off"
        ]
        if available:
            state = secrets.choice(available)
            generation = self.runtime.generation
            async with self.locks[state.entity_id]:
                if generation != self.runtime.generation or not (
                    self.runtime.engine.profile
                    and self.runtime.engine.profile.simulation_enabled
                    and self.runtime.engine.reactions_enabled
                ):
                    return
                current = self.hass.states.get(state.entity_id)
                if current is None or current.state != "off" or self.runtime.engine.confirmed:
                    return
                data = {"entity_id": state.entity_id, "brightness_pct": 30 + secrets.randbelow(50)}
                self._claim(
                    state.entity_id,
                    "light",
                    time.time() + 180 + secrets.randbelow(1200),
                    "simulation",
                    data,
                )
                self.simulation_outputs.add(state.entity_id)
                await self._persist_outputs()
                try:
                    await self._call(
                        "light",
                        "turn_on",
                        data,
                        generation,
                    )
                except (HomeAssistantError, TimeoutError) as err:
                    self.runtime.report("action_failed", f"Anwesenheitssimulation: {err}")

    async def prune_media(self) -> None:
        cutoff = time.time() - self.runtime.config.settings.retention_days * 86400

        def prune() -> None:
            for path in self.media_dir.iterdir():
                if (
                    re.fullmatch(r"\d+_[a-f0-9]{20}\.(jpg|mp4)(\.json)?", path.name)
                    and path.is_file()
                    and path.stat().st_mtime < cutoff
                ):
                    path.unlink(missing_ok=True)

        await self.hass.async_add_executor_job(prune)
