"""Device helpers for MTS RS."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def get_msisdn_device_info(
    entry_id: str, msisdn: str, report: dict[str, Any]
) -> DeviceInfo:
    """Return device info shared by entities for one phone number."""
    name = report.get("msisdn_formatted") or msisdn
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id, msisdn)},
        name=str(name),
        manufacturer="MTS RS",
        model="Mobile prepaid",
    )
