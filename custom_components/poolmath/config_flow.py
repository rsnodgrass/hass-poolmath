"""Config flow for Pool Math integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import PoolMathClient
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

LOG = logging.getLogger(__name__)

TARGET_OPTIONS = [
    {'value': 'tfp', 'label': 'Trouble Free Pools'},
]


def _build_share_url_schema() -> vol.Schema:
    """Build the data schema for share URL configuration using Selectors."""
    return vol.Schema(
        {
            vol.Required(CONF_SHARE_URL): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.URL,
                )
            ),
            vol.Optional(CONF_NAME): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.TEXT,
                )
            ),
            vol.Optional(CONF_TARGET): SelectSelector(
                SelectSelectorConfig(
                    options=TARGET_OPTIONS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key='target',
                )
            ),
            vol.Optional(CONF_SCAN_INTERVAL): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=60,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement='minutes',
                )
            ),
        }
    )


def _build_suggested_values(
    share_url: str | None = None,
    name: str | None = None,
    target: str | None = None,
    scan_interval: int | None = None,
) -> dict[str, Any]:
    """Build suggested values for the form."""
    return {
        CONF_SHARE_URL: share_url or '',
        CONF_NAME: name or DEFAULT_NAME,
        CONF_TARGET: target or DEFAULT_TARGET,
        CONF_SCAN_INTERVAL: scan_interval or DEFAULT_UPDATE_INTERVAL,
    }


async def _process_share_url(
    flow: ConfigFlow | OptionsFlow,
    step_id: str,
    share_url: str,
    user_input: dict[str, Any],
) -> ConfigFlowResult | dict[str, Any]:
    """Process a share URL and extract user_id and pool_id.

    Args:
        flow: The flow instance (ConfigFlow or OptionsFlow)
        step_id: The step ID for showing forms
        share_url: The Pool Math share URL
        user_input: The user input data containing form values

    Returns:
        A ConfigFlowResult with either an error form or the extracted IDs
    """
    default_name = DEFAULT_NAME

    try:
        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(share_url)

        if not user_id or not pool_id:
            return flow.async_show_form(
                step_id=step_id,
                data_schema=_build_share_url_schema(),
                data_description={
                    'suggested_values': _build_suggested_values(
                        share_url=share_url,
                        name=user_input.get(CONF_NAME, default_name),
                        target=user_input.get(CONF_TARGET, DEFAULT_TARGET),
                        scan_interval=user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    )
                },
                errors={'base': 'invalid_share_url'},
            )

        return {
            CONF_USER_ID: user_id,
            CONF_POOL_ID: pool_id,
            CONF_NAME: user_input.get(CONF_NAME, default_name),
            CONF_TARGET: user_input.get(CONF_TARGET, DEFAULT_TARGET),
            CONF_SCAN_INTERVAL: int(
                user_input.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
        }

    except Exception:
        LOG.exception('Error processing Pool Math share URL')
        return flow.async_show_form(
            step_id=step_id,
            data_schema=_build_share_url_schema(),
            data_description={
                'suggested_values': _build_suggested_values(
                    share_url=share_url,
                    name=user_input.get(CONF_NAME, default_name),
                    target=user_input.get(CONF_TARGET, DEFAULT_TARGET),
                    scan_interval=user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                    ),
                )
            },
            errors={'base': 'unknown_error'},
        )


def _initial_form(
    flow: ConfigFlow | OptionsFlow,
) -> ConfigFlowResult:
    """Return flow form for init/user step id."""
    step_id = 'user' if isinstance(flow, ConfigFlow) else 'init'

    name = DEFAULT_NAME
    target = DEFAULT_TARGET
    scan_interval = DEFAULT_UPDATE_INTERVAL

    if isinstance(flow, OptionsFlow) and hasattr(flow, 'config_entry'):
        options = flow.config_entry.options
        name = options.get(CONF_NAME, DEFAULT_NAME)
        target = options.get(CONF_TARGET, DEFAULT_TARGET)
        scan_interval = options.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)

    return flow.async_show_form(
        step_id=step_id,
        data_schema=_build_share_url_schema(),
        data_description={
            'suggested_values': _build_suggested_values(
                name=name,
                target=target,
                scan_interval=scan_interval,
            )
        },
    )


class PoolMathOptionsFlow(OptionsFlow):
    """Handle Pool Math options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Pool Math options."""
        if user_input is not None:
            share_url = user_input.get(CONF_SHARE_URL)

            if share_url:
                result = await _process_share_url(self, 'init', share_url, user_input)

                if isinstance(result, dict):
                    return self.async_create_entry(title=INTEGRATION_NAME, data=result)
                return result

            # no share URL provided, just update the other options
            options = {
                CONF_USER_ID: self.config_entry.data.get(CONF_USER_ID),
                CONF_POOL_ID: self.config_entry.data.get(CONF_POOL_ID),
                CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                CONF_TARGET: user_input.get(CONF_TARGET, DEFAULT_TARGET),
                CONF_SCAN_INTERVAL: int(
                    user_input.get(CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                ),
            }
            return self.async_create_entry(title=INTEGRATION_NAME, data=options)

        return _initial_form(self)


class PoolMathFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Pool Math config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            share_url = user_input.get(CONF_SHARE_URL)

            try:
                result = await _process_share_url(self, 'user', share_url, user_input)

                if isinstance(result, dict):
                    user_id = result[CONF_USER_ID]
                    pool_id = result[CONF_POOL_ID]

                    await self.async_set_unique_id(f'{user_id}-{pool_id}')
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=INTEGRATION_NAME, data=result)

                return result

            except Exception:
                LOG.exception('Error processing Pool Math share URL')
                return self.async_show_form(
                    step_id='user',
                    data_schema=_build_share_url_schema(),
                    data_description={
                        'suggested_values': _build_suggested_values(
                            share_url=share_url,
                            name=user_input.get(CONF_NAME, DEFAULT_NAME),
                            target=user_input.get(CONF_TARGET, DEFAULT_TARGET),
                            scan_interval=user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_UPDATE_INTERVAL
                            ),
                        )
                    },
                    errors={'base': 'unknown_error'},
                )

        return _initial_form(self)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PoolMathOptionsFlow:
        """Get the options flow for this handler."""
        return PoolMathOptionsFlow()
