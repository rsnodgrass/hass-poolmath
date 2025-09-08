"""Integration with Pool Math by Trouble Free Pool"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .client import PoolMathClient
from .const import (
    CONF_USER_ID,
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    CONF_SHARE_ID,
    DEFAULT_TIMEOUT,
    DEFAULT_TARGET,
    DOMAIN,
)
from .coordinator import PoolMathUpdateCoordinator
from .models import PoolMathConfig

LOG = logging.getLogger(__name__)


def get_config_options(
    entry: ConfigEntry,
    keys: list[str],
    keys_with_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return set of config options where ConfigEntry options take precedence.

    Args:
        entry: Config entry
        keys: Required keys to extract
        keys_with_defaults: Optional keys with default values

    Returns:
        Dictionary of configuration options
    """
    if keys_with_defaults is None:
        keys_with_defaults = {}

    options = {}
    for key in keys + list(keys_with_defaults.keys()):
        options[key] = entry.options.get(
            key, entry.data.get(key, keys_with_defaults.get(key))
        )
    return options


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pool Math from a config entry."""
    # if config is using the old format with share_id, create a repair issue
    if CONF_SHARE_ID in entry.data and (
        CONF_USER_ID not in entry.data or CONF_POOL_ID not in entry.data
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            'config_migration_needed',
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key='config_migration_needed',
            data={'config_entry': entry},
        )
        return False

    try:
        # Update entry with proper options
        hass.config_entries.async_update_entry(
            entry,
            options=get_config_options(
                entry,
                [CONF_USER_ID, CONF_POOL_ID, CONF_NAME],
                {
                    CONF_TIMEOUT: DEFAULT_TIMEOUT,
                    CONF_TARGET: DEFAULT_TARGET,
                    CONF_SCAN_INTERVAL: 8,
                },
            ),
        )

        # Create configuration object
        config = PoolMathConfig(
            user_id=entry.options[CONF_USER_ID],
            pool_id=entry.options[CONF_POOL_ID],
            name=entry.options[CONF_NAME],
            timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            target=entry.options[CONF_TARGET],
            update_interval=timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, 8)),
        )

        # Create client and coordinator
        client = PoolMathClient(
            user_id=config.user_id,
            pool_id=config.pool_id,
            name=config.name,
            timeout=config.timeout,
        )
        coordinator = PoolMathUpdateCoordinator(hass, client, config)

        # Store coordinator for platform setup
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            'coordinator': coordinator,
            'config': config,
        }

        # when config options are updated, dynamically reload the entry
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

        # initialize the platforms for this integration
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])

        LOG.info(
            f"Pool Math integration setup completed for '{config.name}' ({config.pool_id})"
        )
        return True

    except Exception as e:
        LOG.exception(f'Error setting up Pool Math integration: {e}')
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
        # Clean up client session
        coordinator = hass.data[DOMAIN][entry.entry_id]['coordinator']
        if hasattr(coordinator, '_client'):
            await coordinator._client.close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

