"""Repair handler for Pool Math integration."""

import logging
import re
import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from .client import PoolMathClient, parse_pool

from .const import CONF_USER_ID, CONF_POOL_ID, CONF_SHARE_URL, SHARE_URL_PATTERN

LOG = logging.getLogger(__name__)


class PoolMathRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_share_url()

    async def async_step_share_url(self, user_input=None) -> FlowResult:
        """Ask for the share URL to extract user_id and pool_id."""
        data_schema = vol.Schema({vol.Required(CONF_SHARE_URL): cv.string})

        if user_input is not None:
            share_url = user_input[CONF_SHARE_URL]

            # validate and extract share_id from the URL
            match = re.search(SHARE_URL_PATTERN, share_url)
            if not match:
                return self.async_show_form(
                    step_id='share_url',
                    data_schema=data_schema,
                    errors={'base': 'invalid_url'},
                )

            # FIXME: can't we replace a bunch of this code with the following?
            # user_id, pool_id = await PoolMathClient.extract_ids_from_share_url(share_url)

            share_id = match.group(1)

            # Fetch the JSON data to extract user_id and pool_id
            url = f'https://api.poolmathapp.com/share/{share_id}.json'
            try:
                data = await PoolMathClient.async_fetch_data(url, timeout=10)
                if not data:
                    return self.async_show_form(
                        step_id='share_url',
                        data_schema=data_schema,
                        errors={'base': 'api_error'},
                    )

                # extract the required user_id/pool_id from the JSON response
                if pool := parse_pool(data):
                    user_id = pool.get('userId')
                    pool_id = pool.get('id')

                if not pool or not user_id or not pool_id:
                    LOG.error(
                        f'Missing user_id={user_id}, pool_id={pool_id} from {url}'
                    )
                    LOG.debug(f'API response data: {data}')
                    return self.async_show_form(
                        step_id='share_url',
                        data_schema=data_schema,
                        errors={'base': 'missing_data'},
                    )

                # update config entry with the new data
                new_data = dict(self.config_entry.data)
                new_data[CONF_USER_ID] = user_id
                new_data[CONF_POOL_ID] = pool_id

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )
                return self.async_create_entry(title='', data={})

            except Exception as exc:
                LOG.exception('Error fetching data from Pool Math API: %s', exc)
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
    hass: HomeAssistant, issue_id: str, data: dict
) -> RepairsFlow:
    """Create flow to fix an issue."""
    if issue_id == 'config_migration_needed':
        return PoolMathRepairFlow(data['config_entry'])
