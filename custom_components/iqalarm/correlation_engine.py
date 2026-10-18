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
    MAX_EVENTS,
    PERIMETER_ROLES,
    RULE_NAMES,
    Level,
    Role,
    RunState,
)
from .models import Configuration, EventLog, Evidence, Profile


class CorrelationEngine:
    """Process edges, delayed activations and timer expiry in one serial context."""

    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.sensors = config.all_sensors()
        self.grouped_inputs = config.window_members()
        self.config.validate()
        self.stage_id = config.stages[0].id
        self.profile_id: str | None = None
        self.severity = Level.SECURE
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
        self.confirmation_rule: str | None = None
        self.pending_rule: str | None = None
        self.latched = False
        self.last_profile_id: str | None = None
        self._last_time = 0.0

    @property
    def profile(self):
        if self.evaluation_profile_id:
            return self.config.profiles.get(self.evaluation_profile_id)
        if self.config.settings.observation_profile_id == "live":
            return Profile(
                name="Aus",
                reactions_enabled=False,
                action_ids=[],
                stage_targets=self.config.default_stage_targets(),
            )
        return None

    @property
    def evaluation_profile_id(self):
        if self.profile_id:
            return self.profile_id
        obs = self.config.settings.observation_profile_id
        return None if obs in (None, "live") else obs

    @property
    def mode(self):
        return RunState.ACTIVE if self.reactions_enabled else RunState.INACTIVE

    @property
    def reactions_enabled(self) -> bool:
        return bool(self.profile_id and self.profile and self.profile.reactions_enabled)

    @property
    def confirmed(self) -> bool:
        return self.severity == Level.BREACH and self.pending_until is None

    @property
    def level(self) -> int:
        return self.config.stage_rank(self.stage_id)

    def target(self, rule: str) -> str:
        return self.profile.stage_targets[rule] if self.profile else self.config.stages[0].id

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
            self.level,
            self.mode.value,
            reason,
            chain[-1].room_id if chain else None,
            entity_id or (chain[-1].entity_id if chain else None),
            [asdict(e) for e in chain],
            profile_id=self.evaluation_profile_id,
            profile_name=self.profile.name if self.profile else "",
            stage_id=self.stage_id,
            stage_name=self.config.stage(self.stage_id).name,
            confirmed=self.confirmed,
            reactions_enabled=self.reactions_enabled,
        )
        self.events.appendleft(event)
        self._outbox.append(event)

    def seed(self, entity_id: str, active: bool | None) -> None:
        """Record current availability without creating synthetic intrusion evidence."""
        if entity_id in self.config.sensors:
            self.sensors[entity_id] = self.config.sensors[entity_id]
        self.raw[entity_id] = active

    def arm_blockers(self) -> list[str]:
        """List contact openings and unavailable inputs under the selected policy."""
        result = []
        included = [sensor for sensor in self.sensors.values() if self._included(sensor)]
        if (
            self.profile
            and (self.profile.room_ids is not None or self.profile.sensor_ids is not None)
            and not included
            and not any(
                sensor.enabled
                and sensor.information_only
                and (self.profile.room_ids is None or sensor.room_id in self.profile.room_ids)
                and (self.profile.sensor_ids is None or sensor.entity_id in self.profile.sensor_ids)
                for sensor in self.sensors.values()
            )
        ):
            result.append("Profil enthält keine aktivierten Sensoren in seiner Auswahl")
        for sensor in included:
            if sensor.entity_id in self.quarantine:
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
        """Legacy service adapter; IDs select profiles and never define behavior."""
        self.set_profile(None if mode in ("disarmed", "inactive") else mode, now, restore=restore)

    def set_profile(self, profile_id: str | None, now: float, *, restore: bool = False) -> None:
        """Select an independent profile, separating analysis from output permission."""
        now = self._time(now)
        if profile_id is not None and profile_id not in self.config.profiles:
            raise ValueError("Unbekanntes Alarmprofil")
        profile = self.config.profiles.get(profile_id)
        if profile_id == self.profile_id:
            return
        if self.reactions_enabled and profile_id is not None:
            raise ValueError("Vor einem Profilwechsel zuerst entschärfen")
        previous_profile = self.profile_id
        self.profile_id = profile_id
        if self.reactions_enabled and not restore:
            blockers = self.arm_blockers()
            if blockers:
                self.profile_id = previous_profile
                raise ValueError("Scharfschalten verhindert: " + "; ".join(blockers))
        self.severity = Level.SECURE
        self.stage_id = self.config.stages[0].id
        self.latched = False
        self.confirmation_rule = None
        self.pending_rule = None
        self.evidence.clear()
        self.debouncing.clear()
        self.edges.clear()
        self.pending_until = None
        self.pending_chain = []
        self.breach_chain = []
        self.arming_until = None
        if profile_id is None:
            self.quarantine.clear()
        elif self.reactions_enabled:
            self.last_profile_id = profile_id
        if self.reactions_enabled and not restore and self.profile.exit_seconds:
            self.arming_until = now + self.profile.exit_seconds
        self._log(
            now,
            "mode_changed",
            f"Profil: {profile.name or profile_id}" if profile else "Alarm aus; Live-Beobachtung",
        )

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
        sensor = self.sensors[perimeter.entity_id]
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

    def _included(self, sensor) -> bool:
        """Intersect profile scopes before blockers, evidence and correlation."""
        profile = self.profile
        if sensor.information_only or sensor.entity_id in self.grouped_inputs:
            return False
        if not sensor.enabled or profile is None:
            return False
        if sensor.role in PERIMETER_ROLES and not profile.perimeter_enabled:
            return False
        if sensor.role in CONTACT_ROLES and not profile.contacts_enabled:
            return False
        if sensor.role in INTERIOR_ROLES and profile.motion_mode == "ignore":
            return False
        if profile.sensor_ids is not None and sensor.entity_id not in profile.sensor_ids:
            window = next(
                (w for w in self.config.windows.values() if w.sensor_id == sensor.entity_id), None
            )
            if window is None or not set(window.position_inputs).intersection(profile.sensor_ids):
                return False
        if profile.room_ids is not None:
            rooms = set(profile.room_ids)
            if sensor.role in PERIMETER_ROLES:
                spaces = set(sensor.front_of or ([sensor.room_id] if sensor.room_id else []))
                # A global perimeter belongs to every non-empty room selection.
                if not rooms or (spaces and not rooms.intersection(spaces)):
                    return False
            elif sensor.room_id not in rooms:
                return False
        return True

    def _enabled(self, sensor) -> bool:
        return self.arming_until is None and self._included(sensor)

    def _has_flap_confirmation(self, entity_id: str, now: float) -> bool:
        sensor = self.sensors[entity_id]
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
        sensor = self.sensors.get(entity_id)
        if sensor is None:
            return
        old = self.raw.get(entity_id)
        self.raw[entity_id] = active
        if not sensor.enabled:
            return
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
        if sensor.information_only or entity_id in self.grouped_inputs:
            return
        diagnose = self.reactions_enabled or self.config.settings.diagnose_disarmed
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
                if self._enabled(sensor):
                    self._recompute(now)
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
        sensor = self.sensors[entity_id]
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
            and self.profile.motion_mode == "after_contact"
            and not sensor.immediate
        ):
            contacts = [e for e in valid if e.role in CONTACT_ROLES]
            if not any(
                self.profile.motion_scope == "house" or self._same_space(e.room_id, current.room_id)
                for e in contacts
            ):
                return
        # Keep one latest activation per entity: on/off/on from one contact can
        # never provide its own second factor, even with flap protection disabled.
        self.evidence = deque((e for e in valid if e.entity_id != entity_id), maxlen=2000)
        self.evidence.append(current)
        self._log(now, "signal", f"Signal: {current.name}", [current])
        if self.latched:
            return
        if sensor.immediate or sensor.role in (Role.PANIC, Role.SMOKE):
            self._confirm(
                [current],
                now,
                "Einzelauslösung ausdrücklich freigegeben" if sensor.immediate else "Gefahr/Panik",
                "immediate",
            )
            return
        matches = []
        for other in reversed(self.evidence):
            rule = self._pair_rule(other, current)
            if rule:
                matches.append((self.config.stage_rank(self.target(rule)), rule, other))
        if matches:
            _, rule, other = max(matches, key=lambda match: match[0])
            self._confirm([other, current], now, RULE_NAMES[rule], rule)
            return
        self._recompute(now, current)

    def _pair_rule(self, first: Evidence, second: Evidence) -> str | None:
        if first.entity_id == second.entity_id or first.source_id == second.source_id:
            return None
        a, b = first.role, second.role
        if self.profile.perimeter_contact and (
            (a in PERIMETER_ROLES and b in CONTACT_ROLES)
            or (b in PERIMETER_ROLES and a in CONTACT_ROLES)
        ):
            perimeter, contact = (first, second) if a in PERIMETER_ROLES else (second, first)
            if self._perimeter_matches(perimeter, contact):
                return "perimeter_contact"
        if (
            self.profile.contact_motion
            and (
                (a in CONTACT_ROLES and b in INTERIOR_ROLES)
                or (b in CONTACT_ROLES and a in INTERIOR_ROLES)
            )
            and self._same_space(first.room_id, second.room_id)
        ):
            return "contact_motion"
        if self.profile.multi_contact and a in CONTACT_ROLES and b in CONTACT_ROLES:
            return "multi_contact"
        if self.profile.multi_motion and a in INTERIOR_ROLES and b in INTERIOR_ROLES:
            return "multi_motion"
        return None

    def _confirm(self, chain: list[Evidence], now: float, reason: str, rule: str) -> None:
        if any(e.entity_id in self.quarantine for e in chain):
            return
        # Only a chain involving a configured entry contact gets an entry delay.
        entry = any(
            self.sensors[e.entity_id].entry_delay and e.role in CONTACT_ROLES for e in chain
        )
        duration = self.profile.entry_seconds if entry and self.reactions_enabled else 0
        if duration:
            deadline = now + duration
            if self.pending_until is None:
                self.pending_until = deadline
                self.pending_chain = chain
                self.pending_rule = rule
                self._set_level(
                    Level.SUSPICION, now, "Bestätigt; Eingangsverzögerung läuft", chain, "single"
                )
                self._log(now, "entry_delay", reason, chain)
            elif deadline < self.pending_until:
                self.pending_until = deadline
                self.pending_chain = chain
                self.pending_rule = rule
            return
        self.pending_until = None
        self.pending_chain = []
        self.breach_chain = chain
        self._set_level(Level.BREACH, now, reason, chain, rule)

    def _set_level(
        self,
        level: Level,
        now: float,
        reason: str,
        chain: list[Evidence] | None = None,
        rule: str | None = None,
    ) -> None:
        rule = rule or {
            Level.PERIMETER: "perimeter",
            Level.SUSPICION: "single",
            Level.BREACH: "contact_motion",
        }.get(level)
        stage_id = self.target(rule) if rule else self.config.stages[0].id
        if self.latched or (self.severity == level and self.stage_id == stage_id):
            return
        previous_rank = self.level
        previous_confirmed = self.confirmed
        self.severity, self.stage_id = level, stage_id
        if level == Level.BREACH:
            self.confirmation_rule = rule
            self.latched = self.reactions_enabled and self.config.stage(stage_id).latch
        kind = "level_expired" if self.level < previous_rank else "level_changed"
        if previous_confirmed != self.confirmed:
            kind = "confirmation_changed"
        self._log(now, kind, reason, chain)

    def _recompute(self, now: float, current: Evidence | None = None) -> None:
        if self.latched or self.pending_until is not None:
            return
        if self.severity == Level.BREACH:
            if self.breach_chain and all(self._fresh(e, now) for e in self.breach_chain):
                return
            self.breach_chain = []
            self.confirmation_rule = None
        valid = [e for e in self.evidence if self._fresh(e, now)]
        suspects = [e for e in valid if e.role not in PERIMETER_ROLES]
        perimeter = [e for e in valid if e.role in PERIMETER_ROLES]
        choices = [(0, Level.SECURE, None, "Korrelationsfenster abgelaufen; keine Bestätigung", [])]
        for signals, severity, rule in (
            (suspects, Level.SUSPICION, "single"),
            (perimeter, Level.PERIMETER, "perimeter"),
        ):
            if signals:
                choices.append(
                    (
                        self.config.stage_rank(self.target(rule)),
                        severity,
                        rule,
                        RULE_NAMES[rule],
                        [current] if current else signals[-1:],
                    )
                )
        if self.profile and any(
            0 <= now - q["since"] < self.profile.correlation_seconds
            and self._included(self.sensors[key])
            for key, q in self.quarantine.items()
            if key in self.sensors
        ):
            choices.append(
                (
                    self.config.stage_rank(self.target("flapping")),
                    Level.SUSPICION,
                    "flapping",
                    "Sensor-Prellen; keine unabhängige Bestätigung",
                    [],
                )
            )
        _, severity, rule, reason, chain = max(choices, key=lambda value: value[0])
        self._set_level(severity, now, reason, chain, rule)

    def tick(self, now: float) -> None:
        """Advance timers even when no sensor changes state."""
        now = self._time(now)
        if self.arming_until is not None and now >= self.arming_until:
            self.arming_until = None
            self._log(now, "armed", "Ausgangsverzögerung abgelaufen")
            for sensor in self.sensors.values():
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
                self._set_level(
                    Level.BREACH, now, "Eingangsverzögerung abgelaufen", chain, self.pending_rule
                )
            self.pending_rule = None
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
        breach = self.confirmed and any(
            e.room_id == room_id
            or (
                e.role in PERIMETER_ROLES
                and self._perimeter_matches(e, Evidence("", "", "", room_id, now, ""))
            )
            for e in self.breach_chain
        )
        return {
            "level": self.level
            if breach
            else self.config.stage_rank(self.target("single"))
            if suspicious
            else self.config.stage_rank(self.target("perimeter"))
            if perimeter
            else 0,
            "confirmed": breach,
            "suspicion": suspicious,
            "perimeter": perimeter,
            "open": [
                s.entity_id
                for s in self.sensors.values()
                if s.room_id == room_id
                and s.role in CONTACT_ROLES
                and not s.information_only
                and s.entity_id not in self.grouped_inputs
                and self.raw.get(s.entity_id) is True
            ],
            "motion": [
                s.entity_id
                for s in self.sensors.values()
                if s.room_id == room_id
                and s.role in INTERIOR_ROLES
                and self.raw.get(s.entity_id) is True
            ],
            "persons": [
                s.entity_id
                for s in self.sensors.values()
                if s.role in PERIMETER_ROLES
                and self.raw.get(s.entity_id) is True
                and self._perimeter_matches(
                    Evidence(s.entity_id, "", s.role, s.room_id, now, ""),
                    Evidence("", "", "", room_id, now, ""),
                )
            ],
            "quarantined": [
                s.entity_id
                for s in self.sensors.values()
                if s.room_id == room_id and s.entity_id in self.quarantine
            ],
        }

    def snapshot(self, now: float) -> dict:
        return {
            "mode": self.mode.value,
            "active": self.reactions_enabled,
            "observing": not self.reactions_enabled,
            "confirmed": self.confirmed,
            "evaluation_profile_id": self.evaluation_profile_id,
            "profile_id": self.profile_id,
            "profile_name": (
                self.config.profiles[self.evaluation_profile_id].name
                if self.evaluation_profile_id in self.config.profiles
                else None
            ),
            "monitored_sensors": [
                sensor.entity_id for sensor in self.sensors.values() if self._included(sensor)
            ],
            "level": self.level,
            "stage_id": self.stage_id,
            "stage_name": self.config.stage(self.stage_id).name,
            "stage_color": self.config.stage(self.stage_id).color,
            "reactions_enabled": self.reactions_enabled,
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
            "profile_id": self.profile_id,
            "level": self.level,
            "severity": int(self.severity),
            "stage_id": self.stage_id,
            "latched": self.latched,
            "confirmation_rule": self.confirmation_rule,
            "pending_rule": self.pending_rule,
            "last_profile_id": self.last_profile_id,
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
        self.profile_id = data.get("profile_id")
        if "profile_id" not in data and data.get("mode", "disarmed").startswith("armed_"):
            self.profile_id = data["mode"]
        if self.profile_id is not None and self.profile_id not in self.config.profiles:
            raise ValueError("Gespeichertes Alarmprofil fehlt; Konfiguration prüfen")
        self.severity = Level(data.get("severity", min(data.get("level", 0), 3)))
        self.stage_id = data.get("stage_id", str(data.get("level", 0)))
        self.config.stage(self.stage_id)
        self.latched = (
            bool(data.get("latched", self.severity == Level.BREACH)) and self.reactions_enabled
        )
        self.confirmation_rule = data.get("confirmation_rule")
        self.pending_rule = data.get("pending_rule", "contact_motion")
        self.last_profile_id = data.get("last_profile_id", self.profile_id)
        self.quarantine = {
            k: v
            for k, v in data.get("quarantine", {}).items()
            if k in self.sensors
            and not self.sensors[k].information_only
            and k not in self.grouped_inputs
        }
        self.arming_until = data.get("arming_until")
        self.pending_until = data.get("pending_until")
        self.pending_chain = [
            Evidence(**e)
            for e in data.get("pending_chain", [])
            if e["entity_id"] in self.sensors
            and not self.sensors[e["entity_id"]].information_only
            and e["entity_id"] not in self.grouped_inputs
        ]
        self.breach_chain = [
            Evidence(**e)
            for e in data.get("breach_chain", [])
            if e["entity_id"] in self.sensors
            and not self.sensors[e["entity_id"]].information_only
            and e["entity_id"] not in self.grouped_inputs
        ]
        self.evidence = deque(
            (
                Evidence(**e)
                for e in data.get("evidence", [])
                if e["entity_id"] in self.sensors
                and not self.sensors[e["entity_id"]].information_only
                and e["entity_id"] not in self.grouped_inputs
            ),
            maxlen=2000,
        )
        self.events = deque(
            (EventLog(**e) for e in data.get("events", [])[:MAX_EVENTS]), maxlen=MAX_EVENTS
        )
        previous_chain = data.get("breach_chain", []) + data.get("pending_chain", [])
        if any(
            e["entity_id"] not in self.sensors
            or self.sensors[e["entity_id"]].information_only
            or e["entity_id"] in self.grouped_inputs
            for e in previous_chain
        ):
            self.latched = False
            self.severity = Level.SECURE
            self.stage_id = self.config.stages[0].id
            self.confirmation_rule = None
            self.pending_until = None
            self.pending_rule = None
            self.pending_chain = []
            self.breach_chain = []
        self.tick(now)
