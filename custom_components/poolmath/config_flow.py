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

    # from https://api.poolmathapp.com/share/?userId=[USER_ID]&poolId=[POOL_ID]
    user_id = options.get(CONF_USER_ID)
    pool_id = options.get(CONF_POOL_ID)
    name = options.get(CONF_NAME, DEFAULT_NAME)
    timeout = options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    target = options.get(CONF_TARGET, DEFAULT_TARGET)
    scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    # FIXME:
    # What is the best customer experience here? Is it actually taking user_id and pool_id
    # since that seems hard to find in Pool Math app and online web portal when using the
    # share URL. Or is it better to just take share URL and then extract these user/pool ids
    # from the data returned?  Let's make this EASY on users with minimal technical understanding.

    return flow.async_show_form(
        step_id=step_id,  # parameterized to follow guidance on using "user"
        data_schema=vol.Schema({
            vol.Required(CONF_USER_ID, default=user_id): cv.string,
            vol.Required(CONF_POOL_ID, default=pool_id): cv.string,
            vol.Optional(CONF_NAME, default=name): cv.string,
            # NOTE: targets are not really implemented, other than tfp
            vol.Optional(CONF_TARGET, default="tfp"): vol.All(
                vol.In({
                    "tfp": "Trouble Free Pools",
                    "hayward_aquarite": "Hayward AquaRite SWG",
                    "bioguard": "Bio Guard",
                    "robert_lowry": "Robert Lowry"
                })
            ),
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
        
        # Maintain compatibility with Home Assistant's options flow 
        # system while adapting to the new pattern where the constructor 
        # doesn't take config_entry. The config_entry is still available 
        # to the options flow through self.config_entry, but we're now 
        # setting it as an attribute rather than passing it through the constructor.
        flow = PoolMathOptionsFlow()
        flow.config_entry = config_entry
        return flow
