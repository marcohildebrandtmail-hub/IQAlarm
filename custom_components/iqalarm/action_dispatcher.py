"""Bounded, cancellable stage actions with guarded outputs and private media."""

import asyncio
import json
import logging
import re
import secrets
import time
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
        self.lock = asyncio.Lock()
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
        self.simulation_outputs = {
            target for target, owned in self.outputs.items() if owned.get("simulation")
        }
        await self.cleanup(force=not self.runtime.engine.reactions_enabled)
        await self.prune_media()

    def release_media_path(self) -> None:
        if self._added_media_path:
            self.hass.config.allowlist_external_dirs.discard(str(self.media_dir))
            self._added_media_path = False

    def variables(self, event: EventLog) -> dict[str, str]:
        sensor = self.runtime.config.sensors.get(event.entity_id)
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
        self, domain: str, service: str, data: dict, generation: int | None = None
    ) -> None:
        if generation is not None and generation != self.runtime.generation:
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
            sensor = self.runtime.config.sensors.get(evidence["entity_id"])
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
                        async with self.lock:
                            if generation == self.runtime.generation:
                                await self.execute(action, variables, generation)
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
            await self.runtime.persist()
        except (HomeAssistantError, OSError) as err:
            self.runtime.report("runtime_error", f"Aktionszustand nicht gespeichert: {err}")

    async def execute(self, action: Action, variables: dict[str, str], generation: int) -> None:
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
                self.outputs[action.target] = {
                    "until": time.time() + action.duration,
                    "kind": domain,
                }
                await self._persist_outputs()
            elif action.target in self.outputs:
                self.outputs[action.target]["until"] = time.time() + action.duration
            await self._call(domain, "turn_on", data, generation)
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

    async def cleanup(self, force: bool = False) -> None:
        """Stop only outputs IQAlarm switched on, retrying failures on the next tick."""
        async with self.lock:
            now = time.time()
            for target, owned in list(self.outputs.items()):
                if not force and now < max(owned["until"], owned.get("retry_at", 0)):
                    continue
                try:
                    await self._call(owned["kind"], "turn_off", {"entity_id": target})
                except (HomeAssistantError, TimeoutError) as err:
                    owned["retry_at"] = time.time() + 30
                    self.runtime.report("action_failed", f"Abschaltung {target}: {err}")
                else:
                    self.outputs.pop(target, None)
                    self.simulation_outputs.discard(target)

    async def simulate(self, local_hour: int) -> None:
        config = self.runtime.config.settings
        enabled = (
            self.runtime.engine.profile is not None
            and self.runtime.engine.profile.simulation_enabled
            and self.runtime.engine.reactions_enabled
            and config.simulation_enabled
            and config.simulation_start <= local_hour < config.simulation_end
        )
        if not enabled:
            for target in self.simulation_outputs:
                if target in self.outputs:
                    self.outputs[target]["until"] = 0
            return
        available = [
            s
            for e in config.simulation_lights
            if (s := self.hass.states.get(e)) and s.state == "off"
        ]
        if available:
            state = secrets.choice(available)
            generation = self.runtime.generation
            async with self.lock:
                if generation != self.runtime.generation or not (
                    self.runtime.engine.profile
                    and self.runtime.engine.profile.simulation_enabled
                    and self.runtime.engine.reactions_enabled
                ):
                    return
                self.outputs[state.entity_id] = {
                    "kind": "light",
                    "until": time.time() + 180 + secrets.randbelow(1200),
                    "simulation": True,
                }
                self.simulation_outputs.add(state.entity_id)
                await self._persist_outputs()
                try:
                    await self._call(
                        "light",
                        "turn_on",
                        {
                            "entity_id": state.entity_id,
                            "brightness_pct": 30 + secrets.randbelow(50),
                        },
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
