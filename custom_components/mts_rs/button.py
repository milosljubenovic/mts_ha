"""Button platform for MTS RS."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MtsDataUpdateCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MtsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MtsRefreshButton(coordinator, entry)])


class MtsRefreshButton(CoordinatorEntity[MtsDataUpdateCoordinator], ButtonEntity):
    """Refresh MTS RS data on demand."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh"

    def __init__(
        self,
        coordinator: MtsDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="MTS RS",
        )

    async def async_press(self) -> None:
        """Fetch the latest data from Moj mts."""
        await self.coordinator.async_request_refresh()
