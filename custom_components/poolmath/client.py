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
    ATTR_LAST_UPDATED,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    SHARE_URL_PATTERN
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

def parse_pool(json: str) -> dict:
    """Convenience function to extract pool sub-data from JSON"""
    if json:
        if pools := json.get('pools'):
            if len(pools) > 0:
                return pools[0].get('pool')
    return None

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

    async def async_get_json(self, timeout: float=DEFAULT_TIMEOUT) -> str:
        """Fetch JSON data from the Pool Math service"""
        return await PoolMathClient.async_fetch_data(self._url, timeout=timeout)

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
            LOG.exception(f'Failed fetching data from {url}', e)
            raise

    @staticmethod
    async def fetch_ids_using_share_url(
        share_url: str, timeout: float = DEFAULT_TIMEOUT
    ) -> tuple[str | None, str | None]:
        """Extract user_id and pool_id from a Pool Math share URL."""
        match = re.search(SHARE_URL_PATTERN, share_url)
        if not match:
            LOG.error(f'Invalid Pool Math share URL {share_url}')
            return None, None
        share_id = match.group(1)

        # call JSON service to discover the user_id and pool_id
        url = f'https://api.poolmathapp.com/share/{share_id}.json'
        try:
            data = await PoolMathClient.async_fetch_data(url, timeout=timeout)

            # extract user_id and pool_id from the response
            # pool = next(iter(data.get('pools', [])), {}).get('pool', {})
            if user_id := data.get('userId'):
                if pool := parse_pool(data):
                    if pool_id := pool.get('id'):
                        return user_id, pool_id
            
            LOG.error(f"Couldn't fetch user_id or pool_id from {url}: {data}")
        except Exception as e:
            LOG.exception(e)
        return None, None
    
    @staticmethod
    def parse_attributes(json: dict[str, Any], measurement: str) -> dict[str, Any]:
        """
        Parse any extra attributes returned from Pool Math for this measurement
        """
        attributes = {}
        if pool := parse_pool(json):
            overview = pool.get('overview')
            if timestamp := overview.get(f'{measurement}Ts'):
                attributes[ATTR_LAST_UPDATED] = timestamp

            if target := pool.get(f'{measurement}Target'):
                attributes['target'] = target
                attributes[ATTR_TARGET_SOURCE] = 'tfp'

            if target_min := pool.get(f'{measurement}Min'):
                attributes[ATTR_TARGET_MIN] = target_min

            if target_max := pool.get(f'{measurement}Max'):
                attributes[ATTR_TARGET_MAX] = target_max

        return attributes 
    
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

        pool = parse_pool(poolmath_json)
        if not pool:
            return

        latest_timestamp = None
        overview = pool.get('overview')

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

            attr = PoolMathClient.parse_attributes(poolmath_json, measurement)

            # find the timestamp of the most recent measurement update
            timestamp = attr.get(ATTR_LAST_UPDATED)
            if not latest_timestamp or timestamp > latest_timestamp:
                latest_timestamp = timestamp

            # update the sensor
            await async_callback(
                measurement, timestamp, value, attr, poolmath_json
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
