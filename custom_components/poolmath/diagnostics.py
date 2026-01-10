"""Diagnostics support for Pool Math integration."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_POOL_ID, CONF_USER_ID, DOMAIN
from .coordinator import PoolMathUpdateCoordinator

TO_REDACT: Final[set[str]] = {
    CONF_USER_ID,
    CONF_POOL_ID,
    'userId',
    'id',
    'email',
    'name',
    'configuration_url',
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PoolMathUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        'coordinator'
    ]

    coordinator_data: dict[str, Any] | None = None
    if coordinator.data and coordinator.data.json:
        coordinator_data = async_redact_data(coordinator.data.json, TO_REDACT)

    return {
        'entry': {
            'entry_id': entry.entry_id,
            'version': entry.version,
            'domain': entry.domain,
            'title': entry.title,
            'data': async_redact_data(dict(entry.data), TO_REDACT),
            'options': async_redact_data(dict(entry.options), TO_REDACT),
        },
        'coordinator': {
            'last_update_success': coordinator.last_update_success,
            'last_exception': (
                str(coordinator.last_exception) if coordinator.last_exception else None
            ),
            'update_interval': str(coordinator.update_interval),
            'data': coordinator_data,
        },
    }
