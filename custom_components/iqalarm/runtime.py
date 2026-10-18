"""Home Assistant event bridge, persistence, action queue and live subscriptions."""

import asyncio
import hashlib
import hmac
import logging
import time
from collections.abc import Callable
from copy import deepcopy
from datetime import timedelta
from pathlib import Path

from homeassistant.const import EVENT_HOMEASSISTANT_STOP, EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .action_dispatcher import ActionDispatcher
from .const import EVENT_TYPE, SIGNAL_UPDATE
from .correlation_engine import CorrelationEngine
from .models import Configuration, EventLog
from .store import IQAlarmStore
from .windows import WindowTracker

_LOGGER = logging.getLogger(__name__)


class IQAlarmRuntime:
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.store = IQAlarmStore(hass)
        self.engine = CorrelationEngine(Configuration())
        self.dispatcher = ActionDispatcher(hass, self)
        self.generation = 0
        self.queue: asyncio.Queue[tuple[EventLog, int]] = asyncio.Queue(maxsize=200)
        self.worker: asyncio.Task | None = None
        self.action_tasks: set[asyncio.Task] = set()
        self.lock = asyncio.Lock()
        self.storage_lock = asyncio.Lock()
        self.pin_lock = asyncio.Lock()
        self.cancels: list[Callable] = []
        self.stopped = False
        self._timer_running = False
        self._next_simulation = 0.0
        self._next_prune = 0.0
        self._failed_pins: list[float] = []
        self.windows: dict[str, WindowTracker] = {}

    @property
    def config(self) -> Configuration:
        return self.engine.config

    def active_state(self, sensor, state) -> bool | None:
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        if sensor.entity_id.startswith("lock.") and state.state in ("locking", "unlocking"):
            return self.engine.raw.get(sensor.entity_id)
        if sensor.entity_id.startswith("lock.") and state.state == "jammed":
            return None
        value = state.attributes.get(sensor.attribute) if sensor.attribute else state.state
        if value is None:
            return None
        normalized = str(value).lower() if isinstance(value, bool) else str(value)
        return normalized in sensor.active_states

    def seed(self) -> None:
        for sensor in self.config.sensors.values():
            self.engine.seed(
                sensor.entity_id, self.active_state(sensor, self.hass.states.get(sensor.entity_id))
            )
        self.windows = {key: WindowTracker(window) for key, window in self.config.windows.items()}
        self._update_windows(time.time(), seed=True)

    def _window_states(self, window) -> dict[str, str]:
        return {
            source: (state.state if (state := self.hass.states.get(source)) else "unavailable")
            for source in window.members
        }

    def _update_windows(self, now: float, *, seed: bool = False) -> bool:
        changed = False
        for tracker in self.windows.values():
            changed = tracker.update(self._window_states(tracker.window), now, seed=seed) or changed
            if seed:
                self.engine.seed(tracker.window.sensor_id, tracker.reading["opening"])
            elif tracker.reading["opening_stable"]:
                self.engine.feed(tracker.window.sensor_id, tracker.reading["opening"], now)
        return changed

    async def start(self) -> None:
        await self.store.async_load()
        self.engine = CorrelationEngine(self.store.config)
        self.seed()
        if self.store.state:
            self.engine.restore(self.store.state, time.time())
        await self.dispatcher.initialize()
        self.cancels.append(self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed))
        self.cancels.append(
            async_track_time_interval(self.hass, self._tick, timedelta(milliseconds=100))
        )
        self.cancels.append(self.hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self._ha_stop))
        self.worker = self.hass.async_create_background_task(
            self._action_worker(), "IQAlarm actions"
        )
        await self.flush()

    @callback
    def _state_changed(self, event) -> None:
        entity_id = event.data["entity_id"]
        sensor = self.config.sensors.get(entity_id)
        if self.stopped:
            return
        grouped = entity_id in self.config.window_members()
        if sensor is None and not grouped:
            return
        if sensor:
            self.engine.feed(
                entity_id, self.active_state(sensor, event.data.get("new_state")), time.time()
            )
        if grouped:
            self._update_windows(time.time())
        self.hass.async_create_task(self.flush(), "IQAlarm sensor update")

    async def _tick(self, now) -> None:
        if self.stopped or self._timer_running:
            return
        self._timer_running = True
        try:
            windows_changed = self._update_windows(time.time())
            self.engine.tick(time.time())
            if self.engine._outbox or windows_changed:
                await self.flush()
            if time.time() >= self._next_simulation:
                self._next_simulation = time.time() + 180
                await self.dispatcher.simulate(dt_util.now().hour)
            if any(
                max(v["until"], v.get("retry_at", 0)) <= time.time()
                for v in self.dispatcher.outputs.values()
            ):
                await self.dispatcher.cleanup()
                await self.persist()
            if time.time() >= self._next_prune:
                self._next_prune = time.time() + 3600
                await self.dispatcher.prune_media()
        except (HomeAssistantError, OSError) as err:
            _LOGGER.error("IQAlarm timer failed: %s", err)
            self.report("runtime_error", f"Timer/Speicherung: {err}")
        finally:
            self._timer_running = False

    async def _ha_stop(self, event) -> None:
        await self.stop()

    async def stop(self, save: bool = True) -> None:
        if self.stopped:
            return
        self.stopped = True
        self.generation += 1
        for cancel in self.cancels:
            cancel()
        self.cancels.clear()
        if self.worker:
            self.worker.cancel()
            await asyncio.gather(self.worker, return_exceptions=True)
        for task in self.action_tasks:
            task.cancel()
        await asyncio.gather(*self.action_tasks, return_exceptions=True)
        # Turn off owned outputs at shutdown; arming/full-alarm state is retained.
        await self.dispatcher.cleanup(force=True)
        self.dispatcher.release_media_path()
        if save:
            await self.persist()

    async def persist(self) -> None:
        async with self.storage_lock:
            await self.store.async_save(
                config=self.config,
                state=deepcopy(self.engine.persistent_state()),
                outputs=deepcopy(self.dispatcher.outputs),
            )

    async def flush(self) -> None:
        events = self.engine.drain()
        generation = self.generation
        if not events:
            self.publish()
            return
        try:
            await self.persist()
        except (HomeAssistantError, OSError) as err:
            self.report("runtime_error", f"Zustand nicht gespeichert: {err}")
        for event in events:
            self.hass.bus.async_fire(EVENT_TYPE, event.to_dict())
            if (
                event.kind in ("level_changed", "confirmation_changed") and event.level > 0
            ) or event.kind == "quarantined_flapping":
                if not event.reactions_enabled:
                    continue
                if self.queue.full():
                    self.report(
                        "action_failed",
                        "Aktionswarteschlange voll; Ereignis im Logbuch gespeichert",
                    )
                else:
                    self.queue.put_nowait((event, generation))
        self.publish()

    @callback
    def publish(self) -> None:
        async_dispatcher_send(self.hass, SIGNAL_UPDATE)

    def report(self, kind: str, reason: str) -> None:
        event = EventLog(
            time.time(),
            kind,
            self.engine.level,
            self.engine.mode.value,
            reason,
            profile_id=self.engine.evaluation_profile_id,
            profile_name=self.engine.profile.name if self.engine.profile else "",
            stage_id=self.engine.stage_id,
            stage_name=self.config.stage(self.engine.stage_id).name,
            confirmed=self.engine.confirmed,
            reactions_enabled=self.engine.reactions_enabled,
        )
        self.engine.events.appendleft(event)
        self.hass.bus.async_fire(EVENT_TYPE, event.to_dict())
        self.publish()

    async def _action_worker(self) -> None:
        while True:
            event, generation = await self.queue.get()
            if len(self.action_tasks) >= 32 and not event.confirmed:
                await asyncio.wait(self.action_tasks, return_when=asyncio.FIRST_COMPLETED)
            task = self.hass.async_create_background_task(
                self._dispatch_event(event, generation), "IQAlarm stage actions"
            )
            self.action_tasks.add(task)
            task.add_done_callback(self.action_tasks.discard)

    async def _dispatch_event(self, event: EventLog, generation: int) -> None:
        try:
            if generation == self.generation:
                await self.dispatcher.dispatch(event, generation)
        except (HomeAssistantError, OSError) as err:
            self.report("action_failed", f"Aktionsausführung: {err}")
        finally:
            self.queue.task_done()

    async def validate_code(self, code: str | None) -> None:
        async with self.pin_lock:
            await self._validate_code(code)

    async def _validate_code(self, code: str | None) -> None:
        saved = self.entry.data.get("pin_hash")
        if not saved:
            return
        now = time.time()
        self._failed_pins = [t for t in self._failed_pins if now - t < 60]
        if len(self._failed_pins) >= 5:
            raise HomeAssistantError("Zu viele falsche PINs; eine Minute warten")
        if code is None or len(code) > 100:
            self._failed_pins.append(now)
            raise HomeAssistantError("Gültige PIN erforderlich")
        salt = self.entry.data["pin_salt"]
        digest = await self.hass.async_add_executor_job(
            hashlib.pbkdf2_hmac, "sha256", code.encode(), bytes.fromhex(salt), 260000
        )
        if not hmac.compare_digest(digest.hex(), saved):
            self._failed_pins.append(now)
            raise HomeAssistantError("Ungültige PIN")
        self._failed_pins.clear()

    async def set_mode(self, mode: str, code: str | None = None) -> None:
        await self.set_profile(None if mode in ("disarmed", "inactive") else mode, code)

    async def activate(self) -> None:
        """HA's generic on command selects the last usable IQAlarm profile."""
        key = self.engine.last_profile_id
        if key not in self.config.profiles or not self.config.profiles[key].reactions_enabled:
            key = next(
                (key for key, profile in self.config.profiles.items() if profile.reactions_enabled),
                None,
            )
        if key is None:
            raise ValueError("Kein Profil mit freigegebenen Aktionen vorhanden")
        await self.set_profile(key)

    async def set_profile(self, profile_id: str | None, code: str | None = None) -> None:
        if profile_id is None:
            await self.validate_code(code)
        async with self.lock:
            previous = (self.engine.mode, self.engine.profile_id)
            self.engine.set_profile(profile_id, time.time())
            if previous != (self.engine.mode, self.engine.profile_id):
                self.generation += 1
            await self.flush()
        if not self.engine.reactions_enabled:
            await self.dispatcher.cleanup(force=True)
            await self.persist()

    async def update_config(self, data: dict, revision: int) -> None:
        async with self.lock:
            await self.save_config_locked(data, revision)

    async def save_config_locked(self, data: dict, revision: int) -> None:
        if self.engine.reactions_enabled:
            raise ValueError("Konfiguration nur im unscharfen Zustand änderbar")
        if revision != self.config.revision:
            raise ValueError(
                "Konfiguration wurde in einem anderen Fenster geändert. Bitte neu laden."
            )
        candidate = Configuration.from_dict(data)
        registry = er.async_get(self.hass)
        for window in candidate.windows.values():
            if any(
                (entry := registry.async_get(source)) and entry.platform == "iqalarm"
                for source in window.members
            ):
                raise ValueError(
                    "IQAlarm-Fenster benötigen unabhängige Eingangssensoren; keine eigenen Ausgabesensoren"
                )
        candidate.revision = self.config.revision + 1
        obsolete_images = {p.image for p in self.config.floorplans.values() if p.image} - {
            p.image for p in candidate.floorplans.values() if p.image
        }
        replacement = CorrelationEngine(candidate)
        replacement.events = self.engine.events.copy()
        replacement.last_profile_id = self.engine.last_profile_id
        replacement.quarantine = {
            key: value
            for key, value in self.engine.quarantine.items()
            if key in replacement.sensors
            and not replacement.sensors[key].information_only
            and key not in replacement.grouped_inputs
        }
        for sensor in candidate.sensors.values():
            replacement.seed(
                sensor.entity_id, self.active_state(sensor, self.hass.states.get(sensor.entity_id))
            )
        replacement._log(time.time(), "configuration_changed", "Konfiguration gespeichert")
        async with self.storage_lock:
            await self.store.async_save(
                config=candidate,
                state=deepcopy(replacement.persistent_state()),
                outputs=deepcopy(self.dispatcher.outputs),
            )
        self.engine = replacement
        self.seed()
        self.generation += 1
        for event in replacement.drain():
            self.hass.bus.async_fire(EVENT_TYPE, event.to_dict())
        self.publish()
        for filename in obsolete_images:
            try:
                await self.hass.async_add_executor_job(
                    Path(self.hass.config.path(".iqalarm_floorplans", filename)).unlink, True
                )
            except OSError as err:
                self.report(
                    "runtime_error", f"Altes Grundrissbild konnte nicht entfernt werden: {err}"
                )

    async def test_level(
        self, stage: str, dry_run: bool = True, profile_id: str | None = None
    ) -> list[dict]:
        if stage != "diagnostic" and stage not in {value.id for value in self.config.stages}:
            raise ValueError("Ungültige Teststufe")
        if profile_id is not None and profile_id not in self.config.profiles:
            raise ValueError("Unbekanntes Alarmprofil")
        profile_id = profile_id or self.engine.evaluation_profile_id
        profile = self.config.profiles.get(profile_id)
        event = EventLog(
            time.time(),
            "test",
            0 if stage == "diagnostic" else self.config.stage_rank(stage),
            self.engine.mode.value,
            "Manueller Aktionstest",
            profile_id=profile_id,
            profile_name=profile.name if profile else "",
            stage_id=stage,
            stage_name="Diagnose" if stage == "diagnostic" else self.config.stage(stage).name,
            confirmed=stage != "diagnostic" and self.config.stage(stage).requires_confirmation,
            reactions_enabled=bool(profile and profile.reactions_enabled),
        )
        result = await self.dispatcher.dispatch(
            event, self.generation, dry_run=dry_run, stage=stage
        )
        self.report(
            "test",
            f"{'Trockenlauf' if dry_run else 'Realer Aktionstest'} Stufe {stage}: {len(result)} Aktionen",
        )
        await self.persist()
        return result

    def snapshot(self) -> dict:
        return {
            "available": True,
            "status": self.engine.snapshot(time.time()),
            "config": self.config.to_dict(),
            "pin_required": bool(self.entry.data.get("pin_hash")),
            "windows": {key: tracker.reading for key, tracker in self.windows.items()},
            "information": self._lock_information(),
        }

    def _lock_information(self):
        result = []
        for key, tracker in self.windows.items():
            if tracker.window.enabled and (
                tracker.reading.get("locked") is False
                or tracker.reading.get("state") in ("unlatched", "tilt_ready")
            ):
                result.append(
                    {
                        "entity_id": tracker.window.sensor_id,
                        "name": tracker.window.name,
                        "room_id": tracker.window.room_id,
                        "window_id": key,
                        "category": "information",
                        "label": "Potenziell unsicher",
                    }
                )
        registry = er.async_get(self.hass)
        seen = set()
        claimed = self.config.window_members()
        candidates = sorted(
            self.config.sensors.values(),
            key=lambda sensor: not sensor.entity_id.startswith("lock."),
        )
        for sensor in candidates:
            if (
                not sensor.enabled
                or not sensor.information_only
                or sensor.entity_id in claimed
                or self.engine.raw.get(sensor.entity_id) is not True
            ):
                continue
            record = registry.async_get(sensor.entity_id)
            source = (
                record.device_id
                if record and record.device_id
                else sensor.source_id or sensor.entity_id
            )
            if source in seen:
                continue
            seen.add(source)
            result.append(
                {
                    "entity_id": sensor.entity_id,
                    "name": sensor.name or sensor.entity_id,
                    "room_id": sensor.room_id,
                    "category": "information",
                    "label": "Potenziell unsicher",
                }
            )
        return result
