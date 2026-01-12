"""DataUpdateCoordinator for Pool Math."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import (
    PoolMathClient,
    PoolMathConnectionError,
    PoolMathTimeoutError,
    parse_pool,
)
from .const import (
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    DOMAIN,
    EVENT_CHEMISTRY_IN_RANGE,
    EVENT_CHEMISTRY_OUT_OF_RANGE,
)
from .models import PoolMathConfig, PoolMathState
from .targets import CHEMISTRY_SENSORS_WITH_TARGETS, get_target_range

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
        self._previous_in_range: dict[str, bool] = {}

    def _check_and_fire_events(self, json_data: dict) -> None:
        """Check chemistry values and fire events if range status changed.

        Args:
            json_data: API response JSON data
        """
        pool = parse_pool(json_data)
        if not pool:
            return

        overview = pool.get('overview', {})

        for sensor_key in CHEMISTRY_SENSORS_WITH_TARGETS:
            value = overview.get(sensor_key)
            if value is None:
                continue

            target_range = get_target_range(sensor_key, self._config.target, pool)
            if not target_range:
                continue

            target_min = target_range.get(ATTR_TARGET_MIN)
            target_max = target_range.get(ATTR_TARGET_MAX)
            if target_min is None or target_max is None:
                continue

            # determine current in_range status
            current_in_range = target_min <= value <= target_max

            # check if status changed from previous
            previous_in_range = self._previous_in_range.get(sensor_key)

            if previous_in_range is not None and current_in_range != previous_in_range:
                event_data = {
                    'measurement': sensor_key,
                    'value': value,
                    'target_min': target_min,
                    'target_max': target_max,
                    'pool_id': self._config.pool_id,
                    'pool_name': self._config.name,
                }

                if previous_in_range and not current_in_range:
                    # went out of range
                    LOG.info(
                        f'Pool chemistry {sensor_key} went out of range: '
                        f'{value} (range: {target_min}-{target_max})'
                    )
                    self.hass.bus.async_fire(EVENT_CHEMISTRY_OUT_OF_RANGE, event_data)
                elif not previous_in_range and current_in_range:
                    # came back in range
                    LOG.info(
                        f'Pool chemistry {sensor_key} back in range: '
                        f'{value} (range: {target_min}-{target_max})'
                    )
                    self.hass.bus.async_fire(EVENT_CHEMISTRY_IN_RANGE, event_data)

            # update previous state
            self._previous_in_range[sensor_key] = current_in_range

    async def _async_update_data(self) -> PoolMathState:
        """Fetch data from Pool Math service.

        Returns:
            Pool Math state with JSON data

        Raises:
            UpdateFailed: If data fetch fails
        """
        try:
            json_data = await self._client.async_get_json()

            # check for range changes and fire events
            self._check_and_fire_events(json_data)

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
