"""DataUpdateCoordinator for Pool Math."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import PoolMathClient, PoolMathTimeoutError, PoolMathConnectionError
from .const import DOMAIN
from .models import PoolMathConfig, PoolMathState

LOG = logging.getLogger(__name__)


class PoolMathUpdateCoordinator(DataUpdateCoordinator[PoolMathState]):
    """Coordinator that HA uses to periodically fetch Pool Math data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PoolMathClient,
        config: PoolMathConfig,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOG, name=DOMAIN, update_interval=config.update_interval)
        self._client = client
        self._config = config

    async def _async_update_data(self) -> PoolMathState:
        """Called periodically to fetch data from Pool Math service."""
        try:
            json_data = await self._client.async_get_json()
            return PoolMathState(
                json=json_data, last_updated=json_data.get('last_updated')
            )
        except PoolMathTimeoutError as e:
            LOG.warning('Timeout updating Pool Math data: %s', e)
            raise UpdateFailed(f'Timeout error: {e}') from e
        except PoolMathConnectionError as e:
            LOG.warning('Connection error updating Pool Math data: %s', e)
            raise UpdateFailed(f'Connection error: {e}') from e
        except Exception as e:
            LOG.exception('Unexpected error updating Pool Math data')
            raise UpdateFailed(f'Unexpected error fetching Pool Math data: {e}') from e
