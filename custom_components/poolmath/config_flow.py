"""Config flow for Pool Math integration."""

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_POOL_ID,
    CONF_SHARE_URL,
    CONF_TARGET,
    CONF_USER_ID,
    DEFAULT_NAME,
    DEFAULT_TARGET,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    INTEGRATION_NAME,
)
from .client import PoolMathClient

LOG = logging.getLogger(__name__)

# Define targets as a constant instead of a function for cleaner code
TARGET_OPTIONS = vol.All(
    vol.In(
        {
            'tfp': 'Trouble Free Pools',
            #'bioguard': 'Bio Guard',
            #'robert_lowry': 'Robert Lowry',
        }
    )
)


def _build_share_url_schema(share_url=None, name=None, target=None, scan_interval=None):
    """Build the data schema for share URL configuration."""
    return vol.Schema(
        {
            vol.Required(CONF_SHARE_URL, default=share_url): cv.string,
            vol.Optional(CONF_NAME, default=name or DEFAULT_NAME): cv.string,
            vol.Optional(CONF_TARGET, default=target or DEFAULT_TARGET): TARGET_OPTIONS,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=scan_interval or DEFAULT_UPDATE_INTERVAL
            ): cv.positive_int,
        }
    )


async def _process_share_url(
    flow, step_id: str, share_url: str, user_input: dict
) -> FlowResult:
    """Process a share URL and extract user_id and pool_id.

    Args:
        flow: The flow instance (ConfigFlow or OptionsFlow)
        step_id: The step ID for showing forms
        share_url: The Pool Math share URL
        user_input: The user input data containing form values

    Returns:
        A FlowResult with either an error form or the extracted IDs
    """

    try:
        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(share_url)

        if not user_id or not pool_id:
            return flow.async_show_form(
                step_id=step_id,
                data_schema=_build_share_url_schema(
                    share_url=share_url,
                    name=user_input.get(CONF_NAME, DEFAULT_NAME),
                    target=user_input.get(CONF_TARGET, DEFAULT_TARGET),
                    scan_interval=user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                ),
                errors={'base': 'invalid_share_url'},
            )

        # Return the extracted IDs along with other options
        return {
            CONF_USER_ID: user_id,
            CONF_POOL_ID: pool_id,
            CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
            CONF_TARGET: user_input.get(CONF_TARGET, DEFAULT_TARGET),
            CONF_SCAN_INTERVAL: user_input.get(
                CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
            ),
        }

    except Exception as exc:
        LOG.exception(f'Error processing Pool Math share URL: {exc}')
        return flow.async_show_form(
            step_id=step_id,
            data_schema=_build_share_url_schema(
                share_url=share_url,
                name=user_input.get(CONF_NAME, DEFAULT_NAME),
                target=user_input.get(CONF_TARGET, DEFAULT_TARGET),
                scan_interval=user_input.get(
                    CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                ),
            ),
            errors={'base': 'unknown_error'},
        )


def _initial_form(flow: ConfigFlow | OptionsFlow):
    """Return flow form for init/user step id."""
    # Determine the step ID based on flow type
    step_id = 'user' if isinstance(flow, ConfigFlow) else 'init'

    # Default values
    name = DEFAULT_NAME
    target = DEFAULT_TARGET
    scan_interval = DEFAULT_UPDATE_INTERVAL

    # Get current values from options if available
    if isinstance(flow, OptionsFlow) and hasattr(flow, 'config_entry'):
        options = flow.config_entry.options
        name = options.get(CONF_NAME, DEFAULT_NAME)
        target = options.get(CONF_TARGET, DEFAULT_TARGET)
        scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    # Return the form with the share URL schema
    return flow.async_show_form(
        step_id=step_id,
        data_schema=_build_share_url_schema(
            share_url=None, name=name, target=target, scan_interval=scan_interval
        ),
    )


class PoolMathOptionsFlow(OptionsFlow):
    """Handle Pool Math options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Pool Math options."""
        if user_input is not None:
            share_url = user_input.get(CONF_SHARE_URL)

            # If share URL is provided, extract user_id and pool_id
            if share_url:
                result = await _process_share_url(self, 'init', share_url, user_input)

                # If result is a dictionary (not a form), it contains the extracted data
                if isinstance(result, dict):
                    return self.async_create_entry(title=INTEGRATION_NAME, data=result)
                return result
            else:
                # No share URL provided, just update the other options
                options = {
                    CONF_USER_ID: self.config_entry.data.get(CONF_USER_ID),
                    CONF_POOL_ID: self.config_entry.data.get(CONF_POOL_ID),
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                    CONF_TARGET: user_input.get(CONF_TARGET, DEFAULT_TARGET),
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                }
                return self.async_create_entry(title=INTEGRATION_NAME, data=options)

        return _initial_form(self)


class PoolMathFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pool Math config flow."""

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""

        if user_input is not None:
            share_url = user_input.get(CONF_SHARE_URL)

            # Extract user_id and pool_id from the share URL
            try:
                result = await _process_share_url(self, 'user', share_url, user_input)

                # If result is a dictionary (not a form), it contains the extracted data
                if isinstance(result, dict):
                    user_id = result[CONF_USER_ID]
                    pool_id = result[CONF_POOL_ID]

                    await self.async_set_unique_id(f'{user_id}-{pool_id}')
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=INTEGRATION_NAME, data=result)

                return result

            except Exception as e:
                LOG.exception(f'Error processing Pool Math share URL: {result}', e)
                return self.async_show_form(
                    step_id='user',
                    data_schema=_build_share_url_schema(
                        share_url=share_url,
                        name=user_input.get(CONF_NAME, DEFAULT_NAME),
                        target=user_input.get(CONF_TARGET, DEFAULT_TARGET),
                        scan_interval=user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ),
                    errors={'base': 'unknown_error'},
                )

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
