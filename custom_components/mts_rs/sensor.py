"""Sensor platform for MTS RS."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BALANCE,
    ATTR_CREDIT_EXPIRES,
    ATTR_MSISDN,
    ATTR_MSISDN_FORMATTED,
    ATTR_PACKAGE_AUTO_RENEW,
    ATTR_PACKAGE_END,
    ATTR_PACKAGE_NAME,
    ATTR_PACKAGE_START,
    ATTR_QUOTA_EXPIRES,
    ATTR_QUOTA_UNIT,
    ATTR_SIM_EXPIRES,
    DOMAIN,
)
from .coordinator import MtsDataUpdateCoordinator

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="internet_remaining",
        translation_key="internet_remaining",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
    ),
    SensorEntityDescription(
        key="balance",
        translation_key="balance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="RSD",
    ),
    SensorEntityDescription(
        key="package_name",
        translation_key="package_name",
    ),
    SensorEntityDescription(
        key="package_end",
        translation_key="package_end",
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="internet_expires",
        translation_key="internet_expires",
        device_class=SensorDeviceClass.DATE,
    ),
)


def _parse_mts_date(value: str | None) -> str | None:
    """Convert MTS date formats to YYYY-MM-DD for HA date entities."""
    if not value:
        return None
    cleaned = value.strip().rstrip(".")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MtsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[MtsSensor] = []
    for msisdn in entry.data["msisdns"]:
        for description in SENSORS:
            entities.append(MtsSensor(coordinator, entry, msisdn, description))
    async_add_entities(entities)


class MtsSensor(CoordinatorEntity[MtsDataUpdateCoordinator], SensorEntity):
    """Representation of an MTS RS sensor."""

    entity_description: SensorEntityDescription
    _msisdn: str

    def __init__(
        self,
        coordinator: MtsDataUpdateCoordinator,
        entry: ConfigEntry,
        msisdn: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._msisdn = msisdn
        self._attr_unique_id = f"{entry.entry_id}_{msisdn}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id, msisdn)},
            "name": f"MTS {msisdn}",
            "manufacturer": "MTS RS",
            "model": "Mobile prepaid",
        }
        self._attr_translation_key = description.translation_key

    @property
    def _report(self) -> dict:
        return self.coordinator.data.get(self._msisdn, {})

    @property
    def native_value(self) -> str | float | None:
        key = self.entity_description.key
        if key == "internet_remaining":
            return self._report.get("internet_remaining")
        if key == "balance":
            return self._report.get("balance")
        if key == "package_name":
            return self._report.get("package_name")
        if key == "package_end":
            return _parse_mts_date(self._report.get("package_end"))
        if key == "internet_expires":
            return _parse_mts_date(self._report.get("internet_expires"))
        return None

    @property
    def extra_state_attributes(self) -> dict:
        report = self._report
        return {
            ATTR_MSISDN: report.get("msisdn"),
            ATTR_MSISDN_FORMATTED: report.get("msisdn_formatted"),
            ATTR_BALANCE: report.get("balance_formatted") or report.get("balance"),
            ATTR_CREDIT_EXPIRES: report.get("credit_expires"),
            ATTR_SIM_EXPIRES: report.get("sim_expires"),
            ATTR_PACKAGE_NAME: report.get("package_name"),
            ATTR_PACKAGE_START: report.get("package_start"),
            ATTR_PACKAGE_END: report.get("package_end"),
            ATTR_PACKAGE_AUTO_RENEW: report.get("package_auto_renew"),
            ATTR_QUOTA_EXPIRES: report.get("internet_expires"),
            ATTR_QUOTA_UNIT: report.get("internet_unit"),
            "internet_remaining_formatted": report.get("internet_remaining_formatted"),
            "internet_bonuses": report.get("internet_bonuses"),
            "internet_packages": report.get("internet_packages"),
        }
