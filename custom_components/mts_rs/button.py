"""Button platform for MTS RS."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import DOMAIN
from .coordinator import MtsDataUpdateCoordinator
from .device import get_msisdn_device_info

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MtsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MtsRefreshButton(coordinator, entry, msisdn)
        for msisdn in entry.data["msisdns"]
    )


class MtsRefreshButton(CoordinatorEntity[MtsDataUpdateCoordinator], ButtonEntity):
    """Refresh MTS RS data on demand."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(
        self,
        coordinator: MtsDataUpdateCoordinator,
        entry: ConfigEntry,
        msisdn: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._msisdn = msisdn
        self._attr_unique_id = f"{entry.entry_id}_{msisdn}_refresh"

    @property
    def device_info(self) -> DeviceInfo:
        data = self.coordinator.data or {}
        return get_msisdn_device_info(self._entry_id, self._msisdn, data.get(self._msisdn, {}))

    async def async_press(self) -> None:
        """Fetch the latest data from Moj mts."""
        await self.coordinator.async_refresh()
        if self.coordinator.last_update_success:
            return

        exc = self.coordinator.last_exception
        if isinstance(exc, ConfigEntryAuthFailed):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed_auth",
            ) from exc
        if isinstance(exc, UpdateFailed):
            raise HomeAssistantError(str(exc)) from exc
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="refresh_failed",
        )
