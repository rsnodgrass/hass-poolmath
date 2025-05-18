import aiohttp
import logging
import re
from typing import Any
from collections.abc import Awaitable
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
        self._url = (
            f'https://api.poolmathapp.com/share/pool?userId={user_id}&poolId={pool_id}'
        )
        LOG.debug(f"PoolMathClient '{name}' connecting to {self._url}")

    @staticmethod
    async def async_fetch_data(url: str, timeout: float=DEFAULT_TIMEOUT) -> str:
        """Fetch JSON data from the Pool Math service"""
        try:
            async with aiohttp.ClientSession() as session:
                LOG.info(f'GET {url} (timeout={timeout})')
                async with session.get(url, timeout=timeout) as response:
                    LOG.debug(f'GET {url} returned {response.status}')
                    if response.status != 200:
                        raise UpdateFailed(f'Failed with status {response.status} from {url}')
 
                    return await response.json()
        except aiohttp.ClientError as e:
            LOG.error(f'Failed fetching data from {url}: {e}')
            raise

    @staticmethod
    async def extract_ids_from_share_url(
        share_url: str, timeout: float = DEFAULT_TIMEOUT
    ) -> tuple[str | None, str | None]:
        """Extract user_id and pool_id from a Pool Math share URL."""
        match = re.search(
            r'https://(?:api\.poolmathapp\.com|troublefreepool\.com)/(?:share/|mypool/)([a-zA-Z0-9]+)',
            share_url,
        )
        if not match:
            LOG.error(f'Invalid Pool Math share URL {share_url}')
            return None, None

        share_id = match.group(1)

        # call service to discover the user_id and pool_id
        url = f'https://api.poolmathapp.com/share/{share_id}.json'
        try:
            data = await PoolMathClient.async_fetch_data(url, timeout=timeout)

            # extract user_id and pool_id from the response
            user_id = data.get('userId')
            pool = next(iter(data.get('pools', [])), {}).get('pool', {})
            pool_id = pool.get('id')

            if user_id and pool_id:
                return user_id, pool_id
            else:
                LOG.error(f"Couldn't find user_id or pool_id: {data}")
        except Exception as exc:
            LOG.exception('Error fetching data from Pool Math', exc)
            
        return None, None

    async def process_log_entry_callbacks(
        self,
        poolmath_json: dict[str, Any],
        async_callback: Callable[
            [str, datetime, float, dict[str, Any], dict[str, Any]], Awaitable[None]
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
        return self._url

    @staticmethod
    def _entry_timestamp(entry):
        return entry.find('time', class_='timestamp timereal').text
