"""Repair handler for Pool Math integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import PoolMathClient
from .const import CONF_POOL_ID, CONF_SHARE_URL, CONF_USER_ID

LOG = logging.getLogger(__name__)


class PoolMathRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_share_url()

    async def async_step_share_url(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for the share URL to extract user_id and pool_id."""
        data_schema = {
            CONF_SHARE_URL: TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.URL,
                )
            ),
        }

        if user_input is not None:
            share_url = user_input[CONF_SHARE_URL]

            try:
                user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(
                    share_url
                )

                if not user_id or not pool_id:
                    return self.async_show_form(
                        step_id='share_url',
                        data_schema=data_schema,
                        errors={'base': 'invalid_url'},
                    )

                # update config entry with the new data
                new_data = dict(self.config_entry.data)
                new_data[CONF_USER_ID] = user_id
                new_data[CONF_POOL_ID] = pool_id

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title='', data={})

            except Exception:
                LOG.exception('Error fetching data from Pool Math API')
                return self.async_show_form(
                    step_id='share_url',
                    data_schema=data_schema,
                    errors={'base': 'unknown'},
                )

        return self.async_show_form(
            step_id='share_url',
            data_schema=data_schema,
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, Any]
) -> RepairsFlow:
    """Create flow to fix an issue."""
    if issue_id == 'config_migration_needed':
        return PoolMathRepairFlow(data['config_entry'])
    raise ValueError(f'Unknown issue_id: {issue_id}')
