"""Single-instance, UI-only setup with optional hashed disarm PIN."""

import hashlib
import secrets

from homeassistant import config_entries
from homeassistant.helpers import selector

from .compat import vol
from .const import DOMAIN, NAME


class IQAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            pin = user_input.get("pin", "")
            if pin and (not pin.isdigit() or not 4 <= len(pin) <= 12):
                errors["pin"] = "invalid_pin"
            else:
                data = {}
                if pin:
                    salt = secrets.token_bytes(16)
                    digest = await self.hass.async_add_executor_job(
                        hashlib.pbkdf2_hmac, "sha256", pin.encode(), salt, 260000
                    )
                    data = {"pin_salt": salt.hex(), "pin_hash": digest.hex()}
                return self.async_create_entry(title=NAME, data=data)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("pin", default=""): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    )
                }
            ),
            errors=errors,
        )
