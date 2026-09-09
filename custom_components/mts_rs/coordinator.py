"""DataUpdateCoordinator for MTS RS."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from aiohttp import CookieJar

from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .api import MtsApiClient, MtsApiError, MtsAuthError
from .const import CONF_MSISDNS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MtsDataUpdateCoordinator(
    TimestampDataUpdateCoordinator[dict[str, dict[str, Any]]]
):
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
        self._session = async_create_clientsession(
            hass,
            cookie_jar=CookieJar(unsafe=True),
        )
        self._client = MtsApiClient(
            self._session,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )

    def _sync_credentials(self) -> None:
        self._client.set_credentials(
            self.entry.data[CONF_USERNAME],
            self.entry.data[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        self._sync_credentials()
        msisdns = self.entry.data[CONF_MSISDNS]
        try:
            return await self._client.fetch_reports(msisdns)
        except MtsAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except MtsApiError as err:
            raise UpdateFailed(str(err), retry_after=err.retry_after) from err

    def set_update_interval(self, seconds: int) -> None:
        """Apply a new polling interval from options."""
        self.update_interval = timedelta(seconds=seconds)
