"""Recognize window contacts from the existing Home Assistant classification."""

from .const import Role


def is_window_contact(sensor, state=None, record=None):
    """Honor the user's HA override before the currently published device class."""
    if sensor.role != Role.ENTRY or sensor.information_only:
        return False
    attributes = state.attributes if state else {}
    device_class = (
        getattr(record, "device_class", None)
        or attributes.get("device_class")
        or getattr(record, "original_device_class", None)
    )
    return device_class == "window"
