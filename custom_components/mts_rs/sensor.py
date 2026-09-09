"""Sensor platform for MTS RS."""

from __future__ import annotations

from datetime import date, datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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
from .device import get_msisdn_device_info

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
        key="credit_expires",
        translation_key="credit_expires",
        device_class=SensorDeviceClass.DATE,
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
    SensorEntityDescription(
        key="sim_expires",
        translation_key="sim_expires",
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="last_updated_at",
        translation_key="last_updated_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

DATE_SENSOR_FIELDS = {
    "credit_expires": "credit_expires",
    "package_end": "package_end",
    "internet_expires": "internet_expires",
    "sim_expires": "sim_expires",
}


def _parse_mts_date(value: str | None) -> date | None:
    """Convert MTS date formats to a date for HA date sensors."""
    if not value:
        return None
    cleaned = value.strip().rstrip(".")
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
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

    _attr_has_entity_name = True
    entity_description: SensorEntityDescription

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
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{entry.entry_id}_{msisdn}_{description.key}"

    @property
    def _report(self) -> dict:
        return self.coordinator.data.get(self._msisdn, {})

    @property
    def device_info(self) -> DeviceInfo:
        return get_msisdn_device_info(self._entry_id, self._msisdn, self._report)

    @property
    def native_value(self) -> str | float | date | datetime | None:
        key = self.entity_description.key
        if key == "last_updated_at":
            return self.coordinator.last_update_success_time
        if key in DATE_SENSOR_FIELDS:
            return _parse_mts_date(self._report.get(DATE_SENSOR_FIELDS[key]))
        return self._report.get(key)

    @property
    def extra_state_attributes(self) -> dict:
        if self.entity_description.key == "last_updated_at":
            return {}
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
