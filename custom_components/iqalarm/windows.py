"""Pure window recognition, availability guards and stable multi-input sampling."""

from dataclasses import dataclass, field

from .models import WINDOW_STATES, WindowConfig


def normalize(value) -> str:
    return "unavailable" if value is None else str(value)


def inspect_window(window: WindowConfig, states: dict[str, str]) -> dict:
    """Retain a working contact even if the handle/connection is unavailable."""
    values = {source: normalize(states.get(source)) for source in window.members}
    faults = []
    for source, value in values.items():
        if value == "unavailable" or (
            value == "unknown" and source not in window.allow_unknown_inputs
        ):
            faults.append(source)
    guard = window.availability_entity_id
    if guard and window.availability_states and values[guard] not in window.availability_states:
        faults.append(guard)
    faults = list(dict.fromkeys(faults))
    lock = values.get(window.lock_entity_id, "unknown")
    if window.lock_entity_id and lock == "jammed":
        faults = list(dict.fromkeys([*faults, window.lock_entity_id]))
    locked = True if lock == "locked" else False if lock in ("unlocked", "open") else None
    contact = values.get(window.contact_entity_id, "unavailable")
    opening = (
        None if contact in ("unknown", "unavailable") else contact in window.contact_open_states
    )
    mapping = next(
        (
            rule
            for rule in window.mappings
            if all(values[source] == value for source, value in rule["values"].items())
        ),
        None,
    )
    state = "no_connection" if faults else mapping["state"] if mapping else "unknown_position"
    position, handle = (
        WINDOW_STATES[state][1:] if state in WINDOW_STATES else ("unknown", "unknown")
    )
    if opening is None and not faults and mapping:
        opening = position in ("open", "tilted")
    return {
        "state": state,
        "label": "Keine Verbindung"
        if faults
        else WINDOW_STATES[state][0]
        if mapping
        else "Stellung nicht eindeutig",
        "available": not faults,
        "position": position,
        "handle": handle,
        "locked": locked,
        "lock_state": lock,
        "lock_label": {
            "locked": "verriegelt",
            "unlocked": "entriegelt",
            "open": "entriegelt",
            "locking": "wird verriegelt",
            "unlocking": "wird entriegelt",
            "jammed": "Störung: blockiert",
        }.get(lock, "Keine Verbindung"),
        "opening": opening,
        "faults": faults,
        "inputs": values,
        "settling": False,
    }


def capture_position(window: WindowConfig, states: dict[str, str], state: str) -> dict:
    """Capture only explicitly supported, reachable and distinguishable inputs."""
    if state not in WINDOW_STATES:
        raise ValueError("Unbekannte Fensterstellung")
    preview = inspect_window(window, states)
    if not preview["available"]:
        raise ValueError("Keine Verbindung: Zuerst alle benötigten Signale prüfen")
    values = {source: normalize(states.get(source)) for source in window.position_inputs}
    if window.contact_entity_id:
        opened = values[window.contact_entity_id] in window.contact_open_states
        if opened != (WINDOW_STATES[state][1] in ("open", "tilted")):
            raise ValueError(
                "Fensterkontakt passt nicht zur gewählten Stellung. Kontakt oder Invertierung prüfen."
            )
    for mapping in window.mappings:
        if mapping["state"] != state and mapping["values"] == values:
            raise ValueError(
                "Diese Stellungen können mit den ausgewählten Sensoren nicht unterschieden werden. Schritt überspringen oder Signale prüfen."
            )
    return {"state": state, "values": values}


@dataclass
class WindowTracker:
    """Coalesce changes without turning missing inputs into a known position."""

    window: WindowConfig
    reading: dict = field(default_factory=dict)
    last_signature: tuple | None = None
    changed_at: float = 0
    last_known: dict | None = None
    contact_state: str | None = None
    contact_changed_at: float = 0

    def update(self, states: dict[str, str], now: float, *, seed: bool = False) -> bool:
        signature = tuple((source, states.get(source)) for source in self.window.position_inputs)
        changed = signature != self.last_signature
        if changed:
            self.last_signature, self.changed_at = signature, now
        incoming = inspect_window(self.window, states)
        stable = seed or now - self.changed_at >= self.window.settle_seconds
        if not stable and incoming["available"]:
            # Retain a stable last position only as a labelled transition; a working
            # contact still reaches the alarm engine after its own stabilization.
            incoming.update(
                state="settling",
                label="Stellung wird ermittelt",
                position="unknown",
                handle="unknown",
                settling=True,
            )
        if (
            stable
            and incoming["available"]
            and incoming["state"] in WINDOW_STATES
            and (
                self.last_known is None or self.reading.get("state") != incoming["state"] or changed
            )
        ):
            self.last_known = {"state": incoming["state"], "timestamp": now}
        contact = states.get(self.window.contact_entity_id)
        if contact != self.contact_state:
            self.contact_state, self.contact_changed_at = contact, now
        incoming["opening_stable"] = seed or (
            now - self.contact_changed_at >= self.window.settle_seconds
            if self.window.contact_entity_id and incoming["opening"] is not None
            else stable
        )
        incoming["last_known"] = self.last_known
        previous = self.reading
        if previous == incoming:
            return False
        self.reading = incoming
        return True
