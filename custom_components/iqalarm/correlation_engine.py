"""Deterministic spatial/temporal state machine with raw-edge flap detection.

All timestamps are epoch seconds supplied by the caller. No timer, I/O or HA
dependency lives here. Only distinct, non-quarantined signal sources can confirm
one another. Full alarm is latched until disarming.
"""

from collections import defaultdict, deque
from dataclasses import asdict
from typing import Any

from .const import (
    CONTACT_ROLES,
    INTERIOR_ROLES,
    LEVEL_STATES,
    MAX_EVENTS,
    PERIMETER_ROLES,
    Level,
    Mode,
    Role,
)
from .models import Configuration, EventLog, Evidence


class CorrelationEngine:
    """Process edges, delayed activations and timer expiry in one serial context."""

    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.mode = Mode.DISARMED
        self.level = Level.SECURE
        self.raw: dict[str, bool | None] = {}
        self.edges: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=101))
        self.debouncing: dict[str, float] = {}
        self.quarantine: dict[str, dict] = {}
        self.evidence: deque[Evidence] = deque(maxlen=2000)
        self.events: deque[EventLog] = deque(maxlen=MAX_EVENTS)
        self._outbox: list[EventLog] = []
        self.arming_until: float | None = None
        self.pending_until: float | None = None
        self.pending_chain: list[Evidence] = []
        self.breach_chain: list[Evidence] = []
        self._last_time = 0.0

    @property
    def profile(self):
        return self.config.profiles.get(self.mode.value)

    def _time(self, now: float) -> float:
        # A wall-clock correction must never resurrect already expired evidence.
        self._last_time = max(self._last_time, now)
        return self._last_time

    def drain(self) -> list[EventLog]:
        result, self._outbox = self._outbox, []
        return result

    def _log(
        self,
        now: float,
        kind: str,
        reason: str,
        chain: list[Evidence] | None = None,
        entity_id: str | None = None,
    ) -> None:
        chain = sorted(chain or [], key=lambda e: e.timestamp)
        event = EventLog(
            now,
            kind,
            int(self.level),
            self.mode.value,
            reason,
            chain[-1].room_id if chain else None,
            entity_id or (chain[-1].entity_id if chain else None),
            [asdict(e) for e in chain],
        )
        self.events.appendleft(event)
        self._outbox.append(event)

    def seed(self, entity_id: str, active: bool | None) -> None:
        """Record current availability without creating synthetic intrusion evidence."""
        self.raw[entity_id] = active

    def arm_blockers(self) -> list[str]:
        """List contact openings and unavailable inputs under the selected policy."""
        result = []
        for sensor in self.config.sensors.values():
            if not sensor.enabled or sensor.entity_id in self.quarantine:
                continue
            if self.mode == Mode.HOME and sensor.role not in PERIMETER_ROLES:
                room = self.config.rooms.get(sensor.room_id)
                if room is None or not room.home_enabled:
                    continue
            state = self.raw.get(sensor.entity_id)
            if state is None and self.config.settings.block_unavailable_on_arm:
                result.append(f"{sensor.name or sensor.entity_id}: nicht verfügbar")
            elif (
                state is True
                and sensor.role in CONTACT_ROLES
                and self.config.settings.block_open_on_arm
            ):
                result.append(f"{sensor.name or sensor.entity_id}: offen")
        return result

    def set_mode(self, mode: str, now: float, *, restore: bool = False) -> None:
        now = self._time(now)
        target = Mode(mode)
        if target == self.mode:
            return
        if self.mode != Mode.DISARMED and target != Mode.DISARMED:
            raise ValueError("Vor einem Profilwechsel zuerst entschärfen")
        previous = self.mode
        self.mode = target
        if target != Mode.DISARMED and not restore:
            blockers = self.arm_blockers()
            if blockers:
                self.mode = previous
                raise ValueError("Scharfschalten verhindert: " + "; ".join(blockers))
        self.level = Level.SECURE
        self.evidence.clear()
        self.debouncing.clear()
        self.edges.clear()
        self.pending_until = None
        self.pending_chain = []
        self.breach_chain = []
        self.arming_until = None
        if target == Mode.DISARMED:
            self.quarantine.clear()
        elif not restore and self.profile.exit_seconds:
            self.arming_until = now + self.profile.exit_seconds
        self._log(now, "mode_changed", f"Modus: {target.value}")

    def clear_quarantine(self, entity_id: str | None, now: float) -> None:
        now = self._time(now)
        targets = list(self.quarantine) if entity_id is None else [entity_id]
        for target in targets:
            if target in self.quarantine:
                del self.quarantine[target]
                self.edges.pop(target, None)
                self.evidence = deque(
                    (e for e in self.evidence if e.entity_id != target), maxlen=2000
                )
                self._log(
                    now,
                    "quarantine_cleared",
                    "Quarantäne aufgehoben; neue Signalflanke erforderlich",
                    entity_id=target,
                )
        self._recompute(now)

    def _same_space(self, first: str | None, second: str | None) -> bool:
        if first is None or second is None:
            return False
        if first == second:
            return True
        if not self.profile.adjacent_rooms:
            return False
        a, b = self.config.rooms.get(first), self.config.rooms.get(second)
        return bool(a and b and (second in a.adjacent or first in b.adjacent))

    def _perimeter_matches(self, perimeter: Evidence, contact: Evidence) -> bool:
        sensor = self.config.sensors[perimeter.entity_id]
        spaces = sensor.front_of or ([sensor.room_id] if sensor.room_id else [])
        return not spaces or contact.room_id in spaces

    def _fresh(self, evidence: Evidence, now: float) -> bool:
        if self.profile is None or evidence.entity_id in self.quarantine:
            return False
        duration = (
            self.profile.perimeter_seconds
            if evidence.role in PERIMETER_ROLES
            else self.profile.correlation_seconds
        )
        return 0 <= now - evidence.timestamp < duration

    def _enabled(self, sensor) -> bool:
        if not sensor.enabled or self.mode == Mode.DISARMED or self.arming_until is not None:
            return False
        if self.mode == Mode.HOME and sensor.role not in PERIMETER_ROLES:
            room = self.config.rooms.get(sensor.room_id)
            return bool(room and room.home_enabled)
        return True

    def _has_flap_confirmation(self, entity_id: str, now: float) -> bool:
        sensor = self.config.sensors[entity_id]
        source = sensor.source_id or entity_id
        for other in self.evidence:
            if other.source_id == source or not self._fresh(other, now):
                continue
            if other.role in PERIMETER_ROLES:
                candidate = Evidence(
                    entity_id, source, sensor.role, sensor.room_id, now, sensor.name
                )
                if self._perimeter_matches(other, candidate):
                    return True
            elif other.room_id == sensor.room_id:
                return True
        return False

    def feed(self, entity_id: str, active: bool | None, now: float) -> None:
        """Handle only meaningful raw transitions; unavailable never counts as an edge."""
        now = self._time(now)
        sensor = self.config.sensors.get(entity_id)
        if sensor is None or not sensor.enabled:
            return
        old = self.raw.get(entity_id)
        self.raw[entity_id] = active
        if active is None:
            self.debouncing.pop(entity_id, None)
            if old is not None:
                self._log(
                    now,
                    "sensor_unavailable",
                    f"{sensor.name or entity_id}: nicht verfügbar",
                    entity_id=entity_id,
                )
            return
        if old is None:
            # Restored/rediscovered states are a baseline, not independent evidence.
            self._log(
                now,
                "sensor_available",
                f"{sensor.name or entity_id}: wieder verfügbar",
                entity_id=entity_id,
            )
            return
        if old == active:
            return
        diagnose = self.mode != Mode.DISARMED or self.config.settings.diagnose_disarmed
        if diagnose and sensor.role in CONTACT_ROLES and sensor.flap_enabled:
            changes = self.edges[entity_id]
            changes.append(now)
            while changes and now - changes[0] > sensor.flap_window:
                changes.popleft()
            if (
                len(changes) >= sensor.flap_threshold
                and entity_id not in self.quarantine
                and not self._has_flap_confirmation(entity_id, now)
            ):
                self.quarantine[entity_id] = {
                    "reason": "quarantined_flapping",
                    "since": now,
                    "transitions": len(changes),
                }
                self.debouncing.pop(entity_id, None)
                self.evidence = deque(
                    (e for e in self.evidence if e.entity_id != entity_id), maxlen=2000
                )
                if any(e.entity_id == entity_id for e in self.pending_chain):
                    self.pending_until = None
                    self.pending_chain = []
                self._log(
                    now,
                    "quarantined_flapping",
                    f"Warnung: {sensor.name or entity_id} prellt und wurde für diese Scharfschalt-Periode isoliert",
                    entity_id=entity_id,
                )
                if self._enabled(sensor) and self.level < Level.SUSPICION:
                    self.level = Level.SUSPICION
                return
        if not active:
            self.debouncing.pop(entity_id, None)
            return
        if entity_id in self.quarantine or not self._enabled(sensor):
            return
        delay_ms = sensor.debounce_ms or self.config.settings.debounce_by_role.get(sensor.role, 0)
        if delay_ms:
            self.debouncing[entity_id] = now + delay_ms / 1000
        else:
            self._activate(entity_id, now)

    def _activate(self, entity_id: str, now: float) -> None:
        sensor = self.config.sensors[entity_id]
        if not self._enabled(sensor) or entity_id in self.quarantine:
            return
        current = Evidence(
            entity_id,
            sensor.source_id or entity_id,
            sensor.role,
            sensor.room_id,
            now,
            sensor.name or entity_id,
        )
        valid = [e for e in self.evidence if self._fresh(e, now)]
        if (
            sensor.role in INTERIOR_ROLES
            and self.mode == Mode.NIGHT
            and self.profile.night_motion_requires_contact
            and not sensor.immediate
        ):
            contacts = [e for e in valid if e.role in CONTACT_ROLES]
            if not any(
                self.profile.night_motion_scope == "house"
                or self._same_space(e.room_id, current.room_id)
                for e in contacts
            ):
                return
        # Keep one latest activation per entity: on/off/on from one contact can
        # never provide its own second factor, even with flap protection disabled.
        self.evidence = deque((e for e in valid if e.entity_id != entity_id), maxlen=2000)
        self.evidence.append(current)
        self._log(now, "signal", f"Signal: {current.name}", [current])
        if self.level == Level.BREACH:
            return
        if sensor.immediate or sensor.role in (Role.PANIC, Role.SMOKE):
            self._confirm(
                [current],
                now,
                "Einzelauslösung ausdrücklich freigegeben" if sensor.immediate else "Gefahr/Panik",
            )
            return
        for other in reversed(self.evidence):
            if other.source_id == current.source_id or other.entity_id == current.entity_id:
                continue
            a, b = other.role, current.role
            contact_pair = a in CONTACT_ROLES and b in CONTACT_ROLES
            motion_pair = a in INTERIOR_ROLES and b in INTERIOR_ROLES
            mixed = (a in CONTACT_ROLES and b in INTERIOR_ROLES) or (
                b in CONTACT_ROLES and a in INTERIOR_ROLES
            )
            perimeter_pair = (a in PERIMETER_ROLES and b in CONTACT_ROLES) or (
                b in PERIMETER_ROLES and a in CONTACT_ROLES
            )
            reason = None
            if perimeter_pair and self.profile.perimeter_contact:
                perimeter, contact = (other, current) if a in PERIMETER_ROLES else (current, other)
                if self._perimeter_matches(perimeter, contact):
                    reason = "Vorfeld + Außenhaut"
            elif (
                mixed
                and self.profile.contact_motion
                and self._same_space(other.room_id, current.room_id)
            ):
                reason = "Außenhaut + Innenraum"
            elif contact_pair and self.profile.multi_contact:
                reason = "Zwei unabhängige Öffnungssensoren"
            elif (
                motion_pair
                and self.profile.multi_motion
                and self.mode in (Mode.AWAY, Mode.VACATION)
            ):
                reason = "Zwei unabhängige Innenraumsensoren"
            if reason:
                self._confirm([other, current], now, reason)
                return
        self._recompute(now, current)

    def _confirm(self, chain: list[Evidence], now: float, reason: str) -> None:
        if any(e.entity_id in self.quarantine for e in chain):
            return
        # Only a chain involving a configured entry contact gets an entry delay.
        entry = any(
            self.config.sensors[e.entity_id].entry_delay and e.role in CONTACT_ROLES for e in chain
        )
        duration = self.profile.entry_seconds if entry else 0
        if duration:
            deadline = now + duration
            if self.pending_until is None:
                self.pending_until = deadline
                self.pending_chain = chain
                self._set_level(Level.SUSPICION, now, "Bestätigt; Eingangsverzögerung läuft", chain)
                self._log(now, "entry_delay", reason, chain)
            elif deadline < self.pending_until:
                self.pending_until = deadline
                self.pending_chain = chain
            return
        self.pending_until = None
        self.pending_chain = []
        self.breach_chain = chain
        self._set_level(Level.BREACH, now, reason, chain)

    def _set_level(
        self, level: Level, now: float, reason: str, chain: list[Evidence] | None = None
    ) -> None:
        if self.level == level or self.level == Level.BREACH:
            return
        kind = "level_expired" if level < self.level else "level_changed"
        self.level = level
        self._log(now, kind, reason, chain)

    def _recompute(self, now: float, current: Evidence | None = None) -> None:
        if (
            self.mode == Mode.DISARMED
            or self.level == Level.BREACH
            or self.pending_until is not None
        ):
            return
        valid = [e for e in self.evidence if self._fresh(e, now)]
        suspects = [e for e in valid if e.role not in PERIMETER_ROLES]
        perimeter = [e for e in valid if e.role in PERIMETER_ROLES]
        # A quarantine is a persistent fault, but suspicion itself times out.
        fault_active = any(
            0 <= now - q["since"] < self.profile.correlation_seconds
            for q in self.quarantine.values()
        )
        level = (
            Level.SUSPICION
            if suspects or fault_active
            else Level.PERIMETER
            if perimeter
            else Level.SECURE
        )
        reason = {
            0: "Korrelationsfenster abgelaufen; keine Bestätigung",
            1: "Vorfeld-Erkennung",
            2: "Unbestätigtes Einzelereignis",
        }[int(level)]
        self._set_level(level, now, reason, [current] if current else (suspects or perimeter)[-1:])

    def tick(self, now: float) -> None:
        """Advance timers even when no sensor changes state."""
        now = self._time(now)
        if self.arming_until is not None and now >= self.arming_until:
            self.arming_until = None
            self._log(now, "armed", "Ausgangsverzögerung abgelaufen")
            for sensor in self.config.sensors.values():
                if sensor.role in CONTACT_ROLES and self.raw.get(sensor.entity_id) is True:
                    self._activate(sensor.entity_id, now)
        for entity_id, deadline in list(self.debouncing.items()):
            if now >= deadline:
                del self.debouncing[entity_id]
                if self.raw.get(entity_id) is True:
                    self._activate(entity_id, now)
        if self.pending_until is not None and now >= self.pending_until:
            chain, self.pending_chain = self.pending_chain, []
            self.pending_until = None
            if chain and all(e.entity_id not in self.quarantine for e in chain):
                self.breach_chain = chain
                self._set_level(Level.BREACH, now, "Eingangsverzögerung abgelaufen", chain)
        self.evidence = deque((e for e in self.evidence if self._fresh(e, now)), maxlen=2000)
        self._recompute(now)

    def room_status(self, room_id: str, now: float) -> dict[str, Any]:
        valid = [e for e in self.evidence if self._fresh(e, now)]
        suspicious = any(e.room_id == room_id and e.role not in PERIMETER_ROLES for e in valid)
        perimeter = any(
            e.role in PERIMETER_ROLES
            and self._perimeter_matches(e, Evidence("", "", "", room_id, now, ""))
            for e in valid
        )
        breach = self.level == Level.BREACH and any(
            e.room_id == room_id
            or (
                e.role in PERIMETER_ROLES
                and self._perimeter_matches(e, Evidence("", "", "", room_id, now, ""))
            )
            for e in self.breach_chain
        )
        return {
            "level": 3 if breach else 2 if suspicious else 1 if perimeter else 0,
            "suspicion": suspicious,
            "perimeter": perimeter,
            "open": [
                s.entity_id
                for s in self.config.sensors.values()
                if s.room_id == room_id
                and s.role in CONTACT_ROLES
                and self.raw.get(s.entity_id) is True
            ],
            "quarantined": [
                s.entity_id
                for s in self.config.sensors.values()
                if s.room_id == room_id and s.entity_id in self.quarantine
            ],
        }

    def snapshot(self, now: float) -> dict:
        return {
            "mode": self.mode.value,
            "level": int(self.level),
            "level_state": LEVEL_STATES[int(self.level)],
            "arming_until": self.arming_until,
            "pending_until": self.pending_until,
            "quarantine": self.quarantine,
            "raw": self.raw.copy(),
            "rooms": {r: self.room_status(r, now) for r in self.config.rooms},
            "events": [e.to_dict() for e in list(self.events)[:50]],
            "breach_chain": [asdict(e) for e in self.breach_chain],
        }

    def persistent_state(self) -> dict:
        """Preserve arming, quarantine, confirmed alarm and log across HA restarts."""
        return {
            "mode": self.mode.value,
            "level": int(self.level),
            "quarantine": self.quarantine,
            "pending_until": self.pending_until,
            "arming_until": self.arming_until,
            "pending_chain": [asdict(e) for e in self.pending_chain],
            "breach_chain": [asdict(e) for e in self.breach_chain],
            "evidence": [asdict(e) for e in self.evidence],
            "events": [e.to_dict() for e in self.events],
        }

    def restore(self, data: dict, now: float) -> None:
        """Restore evidence only within its original window; never replay actions."""
        self.mode = Mode(data.get("mode", Mode.DISARMED))
        self.level = Level(data.get("level", 0))
        self.quarantine = {
            k: v for k, v in data.get("quarantine", {}).items() if k in self.config.sensors
        }
        self.arming_until = data.get("arming_until")
        self.pending_until = data.get("pending_until")
        self.pending_chain = [
            Evidence(**e)
            for e in data.get("pending_chain", [])
            if e["entity_id"] in self.config.sensors
        ]
        self.breach_chain = [
            Evidence(**e)
            for e in data.get("breach_chain", [])
            if e["entity_id"] in self.config.sensors
        ]
        self.evidence = deque(
            (
                Evidence(**e)
                for e in data.get("evidence", [])
                if e["entity_id"] in self.config.sensors
            ),
            maxlen=2000,
        )
        self.events = deque(
            (EventLog(**e) for e in data.get("events", [])[:MAX_EVENTS]), maxlen=MAX_EVENTS
        )
        self.tick(now)
