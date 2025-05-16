"""Integration with Pool Math by Trouble Free Pool"""

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_USER_ID, CONF_POOL_ID, CONF_TARGET, CONF_TIMEOUT, CONF_SHARE_ID, DEFAULT_TIMEOUT, DOMAIN

LOG = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pool Math from a config entry."""
    try:
        # If the config entry is using the old format with share_id, create a repair issue
        if CONF_SHARE_ID in entry.data and (CONF_USER_ID not in entry.data or CONF_POOL_ID not in entry.data):
            ir.async_create_issue(
                hass,
                DOMAIN,
                "config_migration_needed",
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="config_migration_needed",
                data={"config_entry": entry},
            )
            return False

        # prefer options over data (not sure why, will have to ask the
        # original contributor who made this change)
        opt = entry.options
        d = entry.data
        hass.config_entries.async_update_entry(entry, options={
            CONF_USER_ID: opt.get(CONF_USER_ID, d.get(CONF_USER_ID)),
            CONF_POOL_ID: opt.get(CONF_POOL_ID, d.get(CONF_POOL_ID)),
            CONF_NAME: opt.get(CONF_NAME, d.get(CONF_NAME)),
            CONF_TIMEOUT: opt.get(CONF_TIMEOUT, d.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
            CONF_TARGET: opt.get(CONF_TARGET, d.get(CONF_TARGET)),
        })

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}

        # listen for options updates
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
        return True
    except Exception as e:
        LOG.error(f"Error setting up Pool Math integration: {e}")
        raise ConfigEntryNotReady from e


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Pool Math config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
