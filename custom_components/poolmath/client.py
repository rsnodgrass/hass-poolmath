import json
import logging
import re

import httpx

from .const import (
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ATTR_TARGET_SOURCE,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
)

LOG = logging.getLogger(__name__)

KNOWN_SENSOR_KEYS = [
    "fc",
    "cc",
    "cya",
    "ch",
    "ph",
    "ta",
    "salt",
    "bor",
    "tds",
    "csi",
    "waterTemp",
    "flowRate",
    "pressure",
    "swgCellPercent",
]

ONLY_INCLUDE_IF_TRACKED = {
    "salt": "trackSalt",
    "bor": "trackBor",
    "cc": "trackCC",
    "csi": "trackCSI",
}


class PoolMathClient:
    def __init__(self, share_id: str, name=DEFAULT_NAME, timeout=DEFAULT_TIMEOUT):
        self._share_id = share_id
        self._name = name
        self._timeout = timeout
        self._json_url = f"https://api.poolmathapp.com/share/{self._share_id}.json"
        LOG.debug(f"Using JSON URL: {self._json_url}")

    async def async_update(self):
        """Fetch latest json formatted data from the Pool Math API"""

        async with httpx.AsyncClient() as client:
            LOG.info(
                f"GET {self._json_url} (timeout={self._timeout}; name={self._name}; id={self._share_id})"
            )
            response = await client.request(
                "GET", self._json_url, timeout=self._timeout, follow_redirects=True
            )
            LOG.debug(f"GET {self._json_url} response: {response.status_code}")

            if response.status_code == httpx.codes.OK:
                return json.loads(response.text)

            return None

    async def process_log_entry_callbacks(self, poolmath_json, async_callback):
        """Call provided async callback once for each type of log entry"""
        """   async_callback(measurement_type, timestamp, state, attributes)"""

        if not poolmath_json:
            return

        pools = poolmath_json.get("pools")
        if not pools:
            return

        pool = pools[0].get("pool")
        overview = pool.get("overview")

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
                        f"Ignoring measurement {measurement} since tracking is disable in PoolMath"
                    )
                    continue

            timestamp = overview.get(f"{measurement}Ts")

            # find the timestamp of the most recent measurement update
            if not latest_timestamp or timestamp > latest_timestamp:
                latest_timestamp = timestamp

            # add any attributes relevent to this measurement
            attributes = {}
            value_min = pool.get(f"{measurement}Min")
            if value_min:
                attributes[ATTR_TARGET_MIN] = value_min

            value_max = pool.get(f"{measurement}Max")
            if value_max:
                attributes[ATTR_TARGET_MAX] = value_max

            target = pool.get(f"{measurement}Target")
            if target:
                attributes["target"] = target
                attributes[ATTR_TARGET_SOURCE] = "PoolMath"

            # update the sensor
            await async_callback(
                measurement, timestamp, value, attributes, poolmath_json
            )

        return latest_timestamp

    @property
    def pool_id(self):
        return self._share_id

    @property
    def share_id(self):
        return self._share_id

    @property
    def name(self):
        return self._name

    @property
    def url(self):
        return self._json_url

    @staticmethod
    def _entry_timestamp(entry):
        return entry.find("time", class_="timestamp timereal").text
