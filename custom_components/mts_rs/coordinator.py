"""DataUpdateCoordinator for MTS RS."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MtsApiClient, MtsApiError, MtsAuthError
from .const import (
    CONF_MSISDNS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class MtsDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetch MTS RS data for all configured phone numbers."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self._session = async_create_clientsession(hass)
        self._client = MtsApiClient(
            self._session,
            entry.data["username"],
            entry.data["password"],
        )
        self._store = Store[dict[str, Any]](
            hass,
            STORAGE_VERSION,
            f"{STORAGE_KEY}_{entry.entry_id}",
        )

    async def _async_setup(self) -> None:
        """Restore a saved session or log in once during setup."""
        stored = await self._store.async_load()
        if stored:
            self._client.load_session(stored)
        try:
            await self._client.ensure_logged_in()
        except MtsAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MtsApiError as err:
            raise UpdateFailed(str(err)) from err
        await self._persist_session()

    async def _persist_session(self) -> None:
        await self._store.async_save(self._client.dump_session())

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        msisdns = self.entry.data[CONF_MSISDNS]
        try:
            reports = await self._client.get_reports(msisdns)
            await self._persist_session()
            return reports
        except MtsAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MtsApiError as err:
            raise UpdateFailed(str(err)) from err

    def set_update_interval(self, seconds: int) -> None:
        """Apply a new polling interval from options."""
        self.update_interval = timedelta(seconds=seconds)
