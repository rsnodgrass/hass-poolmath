import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from .const import CONF_TIMEOUT, DEFAULT_NAME, DEFAULT_TIMEOUT

LOG = logging.getLogger(__name__)


class PoolMathClient:
    def __init__(self, url, name=DEFAULT_NAME, timeout=DEFAULT_TIMEOUT):
        self._url = url
        self._name = name
        self._timeout = timeout

        # parse out the unique pool identifier from the url
        self._pool_id = "unknown"
        match = re.search(r"/(mypool|share)/(.+)", self._url)
        if match:
            self._pool_id = match[2]
        else:
            self._pool_id = None

    async def async_update(self):
        """Fetch latest data from the Pool Math service as parsed HTML soup"""

        async with httpx.AsyncClient() as client:
            LOG.info(
                f"GET {self._url} (timeout={self._timeout}; name={self.name}; id={self.pool_id})"
            )
            response = await client.request("GET", self._url, timeout=self._timeout, allow_redirects=True)
            LOG.debug(f"GET {self._url} response: {response.status_code}")

            if response.status_code == httpx.codes.OK:
                return BeautifulSoup(response.text, "html.parser")

            return None

    async def process_log_entry_callbacks(self, poolmath_soup, async_callback):
        """Call provided async callback once for each type of log entry"""
        """   async_callback(log_type, timestamp, state)"""

        latest_timestamp = None
        already_processed_log_types = {}

        # Read back through all log entries and update any changed sensor states (since a given
        # log entry may only have a subset of sensor states)
        log_entries = poolmath_soup.find_all("div", class_="logCard")
        # LOG.debug(f"{self.name} log entries: %s", log_entries)

        for log_entry in log_entries:
            log_fields = log_entry.select(".chiclet")

            # find timestamp for the most recent PoolMath log entry
            if not latest_timestamp:
                latest_timestamp = PoolMathClient._entry_timestamp(log_entry)

            # FIXME: improve parsing to be more robust to Pool Math changes
            for entry in log_fields:
                log_type = entry.contents[3].text.lower()

                # only update if we haven't already updated the same log_type yet
                if not log_type in already_processed_log_types:
                    timestamp = PoolMathClient._entry_timestamp(log_entry)
                    state = entry.contents[1].text

                    await async_callback(log_type, timestamp, state)
                    already_processed_log_types[log_type] = state

        return latest_timestamp

    @property
    def pool_id(self):
        return self._pool_id

    @property
    def name(self):
        return self._name

    @staticmethod
    def _entry_timestamp(entry):
        return entry.find("time", class_="timestamp timereal").text
