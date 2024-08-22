"""Config flow for Pool Math integration."""

import logging
from typing import Any, Union

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_TARGET,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_TARGET,
    DEFAULT_TIMEOUT,
    DOMAIN,
    INTEGRATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


def _initial_form(flow: Union[ConfigFlow, OptionsFlow]):
    """Return flow form for init/user step id."""
    if isinstance(flow, ConfigFlow):
        step_id = "user"
        url = "https://api.poolmathapp.com/share/<UNIQUE_ID>.json"
        name = DEFAULT_NAME
        timeout = DEFAULT_TIMEOUT
        target = DEFAULT_TARGET
    elif isinstance(flow, OptionsFlow):
        step_id = "init"
        url = flow.config_entry.options.get(CONF_URL)
        name = flow.config_entry.options.get(CONF_NAME, DEFAULT_NAME)
        timeout = flow.config_entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        target = flow.config_entry.options.get(CONF_NAME, DEFAULT_TARGET)
    else:
        raise TypeError("Invalid flow type")

    return flow.async_show_form(
        step_id=step_id,  # parameterized to follow guidance on using "user"
        data_schema=vol.Schema(
            {
                vol.Required(CONF_URL, default=url): cv.string,
                vol.Optional(CONF_NAME, default=name): cv.string,
                vol.Optional(CONF_TIMEOUT, default=timeout): cv.positive_int,
                # NOTE: targets are not really implemented, other than tfp
                vol.Optional(
                    CONF_TARGET, default=target
                ): cv.string,  # targets/*.yaml file with min/max targets
                # FIXME: allow specifying EXACTLY which log types to monitor, always create the sensors
                # vol.Optional(CONF_LOG_TYPES, default=None):
            }
        ),
        last_step=True,
    )


class PoolMathOptionsFlowHandler(OptionsFlow):
    """Handle Pool Math options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize Pool Math options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Pool Math options."""
        if user_input is not None:
            # TODO: santize inputs
            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        return _initial_form(self)


class PoolMathFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pool Math config flow."""

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PoolMathOptionsFlowHandler:
        """Get the options flow for this handler."""
        return PoolMathOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        # integration already configured?
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            # TODO: santize inputs
            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        return _initial_form(self)
