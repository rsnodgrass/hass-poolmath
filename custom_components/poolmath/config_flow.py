"""Config flow for Pool Math integration."""

import logging
from typing import Any, Union

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_USER_ID,
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_TARGET,
    DEFAULT_TIMEOUT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    INTEGRATION_NAME,
)

LOG = logging.getLogger(__name__)


def _initial_form(flow: Union[ConfigFlow, OptionsFlow]):
    """Return flow form for init/user step id."""

    if isinstance(flow, ConfigFlow):
        step_id = "user"
    else:
        step_id = "init"

    options = {} # empty in case of isinstance ConfigFlow
    if isinstance(flow, OptionsFlow):
        options = flow.config_entry.options

    user_id = options.get(CONF_USER_ID)
    pool_id = options.get(CONF_POOL_ID)
    name = options.get(CONF_NAME, DEFAULT_NAME)
    timeout = options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    target = options.get(CONF_TARGET, DEFAULT_TARGET)
    scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    return flow.async_show_form(
        step_id=step_id,  # parameterized to follow guidance on using "user"
        data_schema=vol.Schema({
            vol.Required(CONF_USER_ID, default=user_id): cv.string,
            vol.Required(CONF_POOL_ID, default=pool_id): cv.string,
            vol.Optional(CONF_NAME, default=name): cv.string,
            vol.Optional(CONF_TIMEOUT, default=timeout): cv.positive_int,
            # NOTE: targets are not really implemented, other than tfp
            vol.Optional(CONF_TARGET, default=target): cv.string,  # targets/*.yaml file with min/max targets
            # FIXME: allow specifying EXACTLY which log types to monitor, always create the sensors
            # vol.Optional(CONF_LOG_TYPES, default=None):
            vol.Optional(CONF_SCAN_INTERVAL, default=scan_interval): cv.positive_int,
        })
    )


class PoolMathOptionsFlow(OptionsFlow):
    """Handle Pool Math options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Pool Math options."""
        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        return _initial_form(self)


class PoolMathFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pool Math config flow."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # already configured user_id and pool_id?
            user_id = user_input.get(CONF_USER_ID)
            pool_id = user_input.get(CONF_POOL_ID)
            
            await self.async_set_unique_id(f"{user_id}-{pool_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        return _initial_form(self)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PoolMathOptionsFlow:
        """Get the options flow for this handler."""
        return PoolMathOptionsFlow(config_entry)
