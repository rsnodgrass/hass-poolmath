"""Repair handler for Pool Math integration."""
import logging
import re
import aiohttp
import voluptuous as vol

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import async_delete_issue

from .const import (
    CONF_USER_ID,
    CONF_POOL_ID,
    DOMAIN,
    INTEGRATION_NAME,
)

_LOGGER = logging.getLogger(__name__)

CONF_SHARE_URL = "share_url"

URL_PATTERN = r"https://(?:api\.poolmathapp\.com|troublefreepool\.com)/(?:share/|mypool/)([a-zA-Z0-9]+)"

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
        if user_input is not None:
            share_url = user_input[CONF_SHARE_URL]
            
            # Extract the share_id from the URL
            match = re.search(URL_PATTERN, share_url)
            if not match:
                return self.async_show_form(
                    step_id="share_url",
                    data_schema=vol.Schema({
                        vol.Required(CONF_SHARE_URL): cv.string,
                    }),
                    errors={"base": "invalid_url"},
                )
            
            share_id = match.group(1)
            
            # Fetch the JSON data to extract user_id and pool_id
            json_url = f"https://api.poolmathapp.com/share/{share_id}.json"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(json_url, timeout=10) as response:
                        if response.status != 200:
                            _LOGGER.error(f"Error: Received status code {response.status} from API")
                            return self.async_show_form(
                                step_id="share_url",
                                data_schema=vol.Schema({
                                    vol.Required(CONF_SHARE_URL): cv.string,
                                }),
                                errors={"base": "api_error"},
                            )
                        data = await response.json()
                        
                        # Extract the pool data
                        pool = next(iter(data.get("pools", [])), {}).get("pool", {})
                        
                        # Get the user_id from the pool data
                        user_id = pool.get("userId")
                            
                        # Get the pool_id from the pool data
                        pool_id = pool.get("id")
                        
                        _LOGGER.debug(f"Extracted user_id: {user_id}, pool_id: {pool_id}")
                        
                        if not user_id or not pool_id:
                            _LOGGER.error(f"Missing data in API response: user_id={user_id}, pool_id={pool_id}")
                            _LOGGER.debug(f"API response data: {data}")
                            return self.async_show_form(
                                step_id="share_url",
                                data_schema=vol.Schema({
                                    vol.Required(CONF_SHARE_URL): cv.string,
                                }),
                                errors={"base": "missing_data"},
                            )
                        
                        # Update the config entry with the new data
                        new_data = dict(self.config_entry.data)
                        new_data[CONF_USER_ID] = user_id
                        new_data[CONF_POOL_ID] = pool_id
                        
                        self.hass.config_entries.async_update_entry(
                            self.config_entry, data=new_data
                        )
                        
                        return self.async_create_entry(title="", data={})
            except Exception as exc:
                _LOGGER.exception("Error fetching data from Pool Math API: %s", exc)
                return self.async_show_form(
                    step_id="share_url",
                    data_schema=vol.Schema({
                        vol.Required(CONF_SHARE_URL): cv.string,
                    }),
                    errors={"base": "unknown"},
                )
        
        return self.async_show_form(
            step_id="share_url",
            data_schema=vol.Schema({
                vol.Required(CONF_SHARE_URL): cv.string,
            }),
        )

async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict
) -> RepairsFlow:
    """Create flow to fix an issue."""
    if issue_id == "config_migration_needed":
        return PoolMathRepairFlow(data["config_entry"])
