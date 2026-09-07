"""Config flow for MTS RS."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import MtsApiClient, MtsApiError, MtsAuthError
from .const import CONF_MSISDNS, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
    }
)


class MtsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MTS RS."""

    VERSION = 1

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._discovered_msisdns: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(self._username)
            self._abort_if_unique_id_configured()

            session = async_create_clientsession(self.hass)
            client = MtsApiClient(session, self._username, self._password)
            try:
                await client.login()
                services = await client.get_mobile_services()
            except MtsAuthError:
                errors["base"] = "invalid_auth"
            except MtsApiError as err:
                _LOGGER.error("MTS RS setup failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                if not services:
                    errors["base"] = "no_services"
                else:
                    self._discovered_msisdns = [
                        {
                            "value": str(service["id"]),
                            "label": f"{service.get('title', service['id'])} ({service['id']})",
                        }
                        for service in services
                    ]
                    return await self.async_step_msisdn()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_msisdn(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            msisdns = user_input[CONF_MSISDNS]
            if not msisdns:
                errors["base"] = "no_msisdns"
            else:
                return self.async_create_entry(
                    title="MTS RS",
                    data={
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_MSISDNS: msisdns,
                    },
                    options={
                        CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MSISDNS): selector(
                    {
                        "select": {
                            "options": self._discovered_msisdns,
                            "multiple": True,
                            "mode": "list",
                        }
                    }
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL,
                ): selector(
                    {
                        "number": {
                            "min": 60,
                            "max": 86400,
                            "step": 60,
                            "mode": "box",
                            "unit_of_measurement": "s",
                        }
                    }
                ),
            }
        )
        return self.async_show_form(
            step_id="msisdn",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="unknown_entry")

        if user_input is not None:
            session = async_create_clientsession(self.hass)
            client = MtsApiClient(
                session,
                entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                await client.login()
            except MtsAuthError:
                errors["base"] = "invalid_auth"
            except MtsApiError as err:
                _LOGGER.error("MTS RS reauth failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> MtsOptionsFlowHandler:
        return MtsOptionsFlowHandler(config_entry)


class MtsOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for MTS RS."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        return self.async_show_form(
            step_id="init",
            data_schema=OPTIONS_SCHEMA,
            data={CONF_SCAN_INTERVAL: current},
        )
