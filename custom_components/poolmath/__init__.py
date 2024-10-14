"""Integration with Pool Math by Trouble Free Pool"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SHARE_ID, CONF_TARGET, CONF_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pool Math from a config entry."""

    # prefer options
    share_id = entry.options.get(CONF_SHARE_ID, entry.data[CONF_SHARE_ID])
    name = entry.options.get(CONF_NAME, entry.data[CONF_NAME])
    timeout = entry.options.get(CONF_TIMEOUT, entry.data[CONF_TIMEOUT])
    target = entry.options.get(CONF_TARGET, entry.data[CONF_TARGET])

    # store options
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_SHARE_ID: share_id,
            CONF_NAME: name,
            CONF_TIMEOUT: timeout,
            CONF_TARGET: target,
        },
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}

    # listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # forward entry setup to platform(s)
    await hass.config_entries.async_forward_entry_setup(entry, Platform.SENSOR)

    return True


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
