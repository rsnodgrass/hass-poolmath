import aiohttp
import logging
from typing import Any
from collections.abc import Callable
from datetime import datetime

from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ATTR_TARGET_SOURCE,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
)

LOG = logging.getLogger(__name__)

# Constants for sensor keys and tracking
KNOWN_SENSOR_KEYS = [
    'fc',
    'cc',
    'cya',
    'ch',
    'ph',
    'ta',
    'salt',
    'bor',
    'tds',
    'csi',
    'waterTemp',
    'flowRate',
    'pressure',
    'swgCellPercent',
]

ONLY_INCLUDE_IF_TRACKED = {
    'salt': 'trackSalt',
    'bor': 'trackBor',
    'cc': 'trackCC',
    'csi': 'trackCSI',
}


class PoolMathClient:
    """Client for interacting with the Pool Math API."""

    def __init__(
        self,
        user_id: str,
        pool_id: str,
        name: str = DEFAULT_NAME,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._user_id = user_id
        self._pool_id = pool_id
        self._name = name
        self._timeout = timeout
        self._json_url = (
            f'https://api.poolmathapp.com/share/pool?userId={user_id}&poolId={pool_id}'
        )
        LOG.debug(f'Using PoolMathClient for {name} at {self._json_url}')

    @staticmethod
    async def extract_ids_from_share_url(
        share_url: str, timeout: float = DEFAULT_TIMEOUT
    ) -> tuple[str | None, str | None]:
        """Extract user_id and pool_id from a Pool Math share URL."""
        import re

        # Extract the share_id from the URL
        match = re.search(
            r'https://(?:api\.poolmathapp\.com|troublefreepool\.com)/(?:share/|mypool/)([a-zA-Z0-9]+)',
            share_url,
        )
        if not match:
            LOG.error('Invalid Pool Math share URL format')
            return None, None

        share_id = match.group(1)

        # Fetch the JSON data to extract user_id and pool_id
        json_url = f'https://api.poolmathapp.com/share/{share_id}.json'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(json_url, timeout=timeout) as response:
                    if response.status != 200:
                        LOG.error(
                            f'Error: Received status code {response.status} from API'
                        )
                        return None, None

                    data = await response.json()

                    # Extract user_id and pool_id from the response
                    user_id = data.get('userId')
                    pool = next(iter(data.get('pools', [])), {}).get('pool', {})
                    pool_id = pool.get('id')

                    if not user_id or not pool_id:
                        LOG.error(
                            'Could not extract user_id or pool_id from Pool Math API'
                        )
                        return None, None

                    return user_id, pool_id
        except Exception as exc:
            LOG.exception(f'Error fetching data from Pool Math API: {exc}')
            return None, None

    async def async_fetch_data(self):
        """Fetch latest json data from the Pool Math service"""

        async with aiohttp.ClientSession() as session:
            try:
                LOG.info(
                    f'GET {self._json_url} (timeout={self._timeout}; name={self._name}; user_id={self._user_id}; pool_id={self._pool_id})'
                )
                async with session.get(
                    self._json_url, timeout=self._timeout
                ) as response:
                    LOG.debug(f'GET {self._json_url} response: {response.status}')
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise UpdateFailed(
                            f'Failed with status code {response.status} from {self._json_url}'
                        )
            except aiohttp.ClientError as e:
                LOG.error(f'Failed fetching data from {self._json_url}: {e}')
                raise

    async def process_log_entry_callbacks(
        self,
        poolmath_json: dict[str, Any],
        async_callback: Callable[
            [str, datetime, float, dict[str, Any], dict[str, Any]], None
        ],
    ) -> None:
        """Call provided async callback once for each type of log entry

        Args:
            poolmath_json: JSON response from Pool Math API
            async_callback: Callback function to process each measurement
        """
        if not poolmath_json:
            return

        pools = poolmath_json.get('pools')
        if not pools:
            return

        pool = pools[0].get('pool')
        overview = pool.get('overview')

        latest_timestamp = None

        for measurement in KNOWN_SENSOR_KEYS:
            value = overview.get(measurement)
            if value is None:
                continue

            # if a measurement can be disabled for tracking in PoolMath, skip adding this
            # sensor if the user has marked it to not be tracked
            if measurement in ONLY_INCLUDE_IF_TRACKED:
                if not pool.get(ONLY_INCLUDE_IF_TRACKED.get(measurement)):
                    LOG.info(
                        f'Ignoring measurement {measurement} since tracking is disable in PoolMath'
                    )
                    continue

            timestamp = overview.get(f'{measurement}Ts')

            # find the timestamp of the most recent measurement update
            if not latest_timestamp or timestamp > latest_timestamp:
                latest_timestamp = timestamp

            # add any attributes relevent to this measurement
            attributes = {}
            value_min = pool.get(f'{measurement}Min')
            if value_min:
                attributes[ATTR_TARGET_MIN] = value_min

            value_max = pool.get(f'{measurement}Max')
            if value_max:
                attributes[ATTR_TARGET_MAX] = value_max

            target = pool.get(f'{measurement}Target')
            if target:
                attributes['target'] = target
                attributes[ATTR_TARGET_SOURCE] = 'PoolMath'

            # update the sensor
            await async_callback(
                measurement, timestamp, value, attributes, poolmath_json
            )

        return latest_timestamp

    @property
    def pool_id(self):
        return self._pool_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return self._json_url

    @staticmethod
    def _entry_timestamp(entry):
        return entry.find('time', class_='timestamp timereal').text
