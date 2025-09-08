"""Pool Math API client for fetching pool chemistry data."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import aiohttp
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ATTR_TARGET_SOURCE,
    ATTR_LAST_UPDATED,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    SHARE_URL_PATTERN,
)

LOG = logging.getLogger(__name__)


class PoolMathError(Exception):
    """Base exception for Pool Math client."""


class PoolMathConnectionError(PoolMathError):
    """Connection-related errors."""


class PoolMathTimeoutError(PoolMathError):
    """Timeout errors."""


class PoolMathValidationError(PoolMathError):
    """Data validation errors."""


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


def parse_pool(json_data: dict[str, Any]) -> dict[str, Any] | None:
    """Convenience function to extract pool sub-data from JSON.

    Args:
        json_data: Pool Math API response data

    Returns:
        Pool data dictionary or None if not found
    """
    if not json_data:
        return None

    pools = json_data.get('pools')
    if not pools or not isinstance(pools, list) or len(pools) == 0:
        return None

    first_pool = pools[0]
    if not isinstance(first_pool, dict):
        return None

    return first_pool.get('pool')


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
        self._session: aiohttp.ClientSession | None = None
        LOG.debug(f"PoolMathClient '{name}' connecting to {self._url}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def async_get_json(self, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Fetch JSON data from the Pool Math service.

        Args:
            timeout: Request timeout in seconds

        Returns:
            Pool Math API response data
        """
        session = await self._get_session()
        try:
            LOG.info(f'GET {self._url} (timeout={timeout})')
            async with session.get(self._url) as response:
                LOG.debug(f'GET {self._url} returned {response.status}')
                if response.status != 200:
                    raise UpdateFailed(f'Failed with status {response.status} from {self._url}')
                return await response.json()
        except aiohttp.ClientTimeout as e:
            LOG.error(f'Timeout fetching data from {self._url}')
            raise PoolMathTimeoutError(f'Timeout accessing {self._url}') from e
        except aiohttp.ClientError as e:
            LOG.exception(f'Failed fetching data from {self._url}')
            raise PoolMathConnectionError(f'Network error accessing {self._url}: {e}') from e

    @staticmethod
    async def async_fetch_data(
        url: str, timeout: float = DEFAULT_TIMEOUT
    ) -> dict[str, Any]:
        """Fetch JSON data from the Pool Math service.

        Args:
            url: API endpoint URL
            timeout: Request timeout in seconds

        Returns:
            API response data

        Raises:
            UpdateFailed: If the request fails
        """
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                LOG.info(f'GET {url} (timeout={timeout})')
                async with session.get(url) as response:
                    LOG.debug(f'GET {url} returned {response.status}')
                    if response.status != 200:
                        raise UpdateFailed(
                            f'Failed with status {response.status} from {url}'
                        )

                    return await response.json()
        except aiohttp.ClientTimeout as e:
            LOG.error(f'Timeout fetching data from {url}')
            raise PoolMathTimeoutError(f'Timeout accessing {url}') from e
        except aiohttp.ClientError as e:
            LOG.exception(f'Failed fetching data from {url}')
            raise PoolMathConnectionError(f'Network error accessing {url}: {e}') from e

    @staticmethod
    async def fetch_ids_using_share_url(
        share_url: str, timeout: float = DEFAULT_TIMEOUT
    ) -> tuple[str | None, str | None]:
        """Extract user_id and pool_id from a Pool Math share URL.

        Args:
            share_url: Pool Math share URL from troublefreepool.com
            timeout: Request timeout in seconds

        Returns:
            Tuple of (user_id, pool_id) or (None, None) if extraction fails
        """
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
            if pool := parse_pool(data):
                user_id = pool.get('userId')
                pool_id = pool.get('id')
                if user_id and pool_id:
                    return user_id, pool_id

            LOG.error(f"Couldn't parse user/pool id from {url}: {data}")
        except Exception:
            LOG.exception(f'Failed GET {url}')
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
            [str, int | None, float, dict[str, Any], dict[str, Any]], Awaitable[None]
        ],
    ) -> int | None:
        """Call provided async callback once for each type of log entry.

        Args:
            poolmath_json: JSON response from Pool Math API
            async_callback: Callback function to process each measurement

        Returns:
            Timestamp of the most recent measurement or None
        """
        if not poolmath_json:
            return None

        pool = parse_pool(poolmath_json)
        if not pool:
            return None

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
            await async_callback(measurement, timestamp, value, attr, poolmath_json)

        return latest_timestamp

    @property
    def pool_id(self) -> str:
        """Return the pool ID."""
        return self._pool_id

    @property
    def user_id(self) -> str:
        """Return the user ID."""
        return self._user_id

    @property
    def name(self) -> str:
        """Return the pool name."""
        return self._name

    @property
    def url(self) -> str:
        """Return the API URL."""
        return self._url
