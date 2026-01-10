"""DataUpdateCoordinator for Pool Math."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import PoolMathClient, PoolMathConnectionError, PoolMathTimeoutError
from .const import DOMAIN
from .models import PoolMathConfig, PoolMathState

LOG = logging.getLogger(__name__)


class PoolMathUpdateCoordinator(DataUpdateCoordinator[PoolMathState]):
    """Coordinator that Home Assistant uses to periodically fetch Pool Math data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PoolMathClient,
        config: PoolMathConfig,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            client: Pool Math API client
            config: Pool Math configuration
        """
        super().__init__(hass, LOG, name=DOMAIN, update_interval=config.update_interval)
        self._client = client
        self._config = config

    async def _async_update_data(self) -> PoolMathState:
        """Fetch data from Pool Math service.

        Returns:
            Pool Math state with JSON data

        Raises:
            UpdateFailed: If data fetch fails
        """
        try:
            json_data = await self._client.async_get_json()
            return PoolMathState(
                json=json_data, last_updated=json_data.get('last_updated')
            )
        except PoolMathTimeoutError as exc:
            LOG.warning('Timeout updating Pool Math data: %s', exc)
            raise UpdateFailed(f'Timeout error: {exc}') from exc
        except PoolMathConnectionError as exc:
            LOG.warning('Connection error updating Pool Math data: %s', exc)
            raise UpdateFailed(f'Connection error: {exc}') from exc
        except Exception as exc:
            LOG.exception('Unexpected error updating Pool Math data')
            raise UpdateFailed(f'Unexpected error: {exc}') from exc
