"""Versioned atomic HA storage; configuration changes are committed before use."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION
from .models import Configuration


class IQAlarmStore:
    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.configuration", private=True)
        self._migration_backup = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.configuration.before_level_rules", private=True
        )
        self.config = Configuration()
        self.state: dict = {}
        self.outputs: dict = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if data is not None:
            self.config = Configuration.from_dict(data["config"])
            self.state = data.get("state", {})
            self.outputs = data.get("outputs", {})
            if self.config.to_dict() != data["config"]:
                if "rules" not in data["config"]:
                    await self._migration_backup.async_save(data)
                await self._store.async_save({**data, "config": self.config.to_dict()})

    async def async_save(
        self,
        config: Configuration | None = None,
        state: dict | None = None,
        outputs: dict | None = None,
    ) -> None:
        candidate = {
            "config": (config or self.config).to_dict(),
            "state": self.state if state is None else state,
            "outputs": self.outputs if outputs is None else outputs,
        }
        await self._store.async_save(candidate)
        self.config = config or self.config
        self.state = candidate["state"]
        self.outputs = candidate["outputs"]
