import logging

import asyncio
import voluptuous as vol
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from bs4 import BeautifulSoup
from datetime import timedelta

import re
import httpx

from homeassistant.core import callback
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.rest.data import RestData
from homeassistant.const import (
    CONF_NAME, CONF_URL, TEMP_FAHRENHEIT, ATTR_ICON, ATTR_NAME, ATTR_UNIT_OF_MEASUREMENT
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.helpers.config_validation as cv

from .const import (DOMAIN, ATTRIBUTION, ATTR_ATTRIBUTION, ATTR_DESCRIPTION, ATTR_TARGET_SOURCE, ATTR_LOG_TIMESTAMP, ATTR_TARGET_MIN, ATTR_TARGET_MAX, ICON_POOL, ICON_GAUGE, CONF_TARGET)

LOG = logging.getLogger(__name__)

DEFAULT_NAME = 'Pool'
DATA_UPDATED = 'poolmath_data_updated'

DEFAULT_TIMEOUT=2.0

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        
        # NOTE: targets are not really implemented, other than tfp
        vol.Optional(CONF_TARGET, default='tfp'): cv.string # targets/*.yaml file with min/max targets
    }
)

# see https://www.troublefreepool.com/blog/2018/12/12/abcs-of-pool-water-chemistry/
POOL_MATH_SENSOR_SETTINGS = {
    'cc': { ATTR_NAME: 'CC',
            ATTR_UNIT_OF_MEASUREMENT: 'mg/L',
            ATTR_DESCRIPTION: 'Combined Chlorine',
            ATTR_ICON: ICON_GAUGE },
    'fc': { ATTR_NAME: 'FC',
            ATTR_UNIT_OF_MEASUREMENT: 'mg/L',
            ATTR_DESCRIPTION: 'Free Chlorine',
            ATTR_ICON: ICON_GAUGE },
    'ph': { ATTR_NAME: 'pH',
            ATTR_UNIT_OF_MEASUREMENT: 'pH',
            ATTR_DESCRIPTION: 'Acidity/Basicity',
            ATTR_ICON: ICON_GAUGE },
    'ta': { ATTR_NAME: 'TA',
            ATTR_UNIT_OF_MEASUREMENT: 'ppm',
            ATTR_DESCRIPTION: 'Total Alkalinity',
            ATTR_ICON: ICON_GAUGE },
    'ch': { ATTR_NAME: 'CH',
            ATTR_UNIT_OF_MEASUREMENT: 'ppm',
            ATTR_DESCRIPTION: 'Calcium Hardness',
            ATTR_ICON: ICON_GAUGE },
    'cya': { ATTR_NAME: 'CYA',
             ATTR_UNIT_OF_MEASUREMENT: 'ppm',
             ATTR_DESCRIPTION: 'Cyanuric Acid',
             ATTR_ICON: ICON_GAUGE },
    'salt': { ATTR_NAME: 'Salt',
              ATTR_UNIT_OF_MEASUREMENT: 'ppm',
              ATTR_DESCRIPTION: 'Salt',
              ATTR_ICON: ICON_GAUGE },
    'bor':  { ATTR_NAME: 'Borate',
              ATTR_UNIT_OF_MEASUREMENT: 'ppm',
              ATTR_DESCRIPTION: 'Borate',
              ATTR_ICON: ICON_GAUGE },
    'borate': { ATTR_NAME: 'Borate',
                ATTR_UNIT_OF_MEASUREMENT: 'ppm',
                ATTR_DESCRIPTION: 'Borate',
                ATTR_ICON: ICON_GAUGE },
    'csi':    { ATTR_NAME: 'CSI',
                ATTR_UNIT_OF_MEASUREMENT: 'CSI',
                ATTR_DESCRIPTION: 'Calcite Saturation Index',
                ATTR_ICON: ICON_GAUGE },
    'temp':   { ATTR_NAME: 'Temp',
                ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT,
                ATTR_DESCRIPTION: 'Temperature',
                ATTR_ICON: 'mdi:coolant-temperature' }
}

# FIXME: this should be a profile probably, and allow user to select from
# a set of different profiles based on their needs (and make these ranges
# attributes of the sensors).  Profiles should be in YAML, not hardcoded here.
#
# FIXME: Load from targets/ based on targets config key...
# FIXME: targets should probably all be in code, since some values are computed based on other values
TFP_TARGET = 'tfp'
TFP_RECOMMENDED_TARGET_LEVELS = {
    'cc':     { ATTR_TARGET_MIN: 0,    ATTR_TARGET_MAX: 0.1  },
    'ph':     { ATTR_TARGET_MIN: 7.2,  ATTR_TARGET_MAX: 7.8, 'target': 7.4 },
    'ta':     { ATTR_TARGET_MIN: 50,   ATTR_TARGET_MAX: 90   },
#    'ch':     { ATTR_TARGET_MIN: 250,  ATTR_TARGET_MAX: 650  }, # with salt: 350-450 ppm
#    'cya':    { ATTR_TARGET_MIN: 30,   ATTR_TARGET_MAX: 50   }, # with salt: 70-80 ppm
    'salt':   { ATTR_TARGET_MIN: 3000, ATTR_TARGET_MAX: 3200, 'target': 3100 },
}

async def async_setup_platform(hass, config, async_add_entities_callback, discovery_info=None):
    """Set up the Pool Math sensor integration."""
    client = PoolMathClient(hass, config, async_add_entities_callback)

    # create the Pool Math service sensor, which is responsible for updating all other sensors
    sensor = PoolMathServiceSensor("Pool Math Service", config, client)
    await async_add_entities_callback([sensor], True)

def get_pool_targets(targets_key):
    if targets_key == TFP_TARGET:
        return TFP_RECOMMENDED_TARGET_LEVELS
    else:
        LOG.error(f"Only '{TFP_TARGET}' target currently supported, ignoring {CONF_TARGET}.")
        return None

class PoolMathClient():
    def __init__(self, hass, config, async_add_sensors_callback):
        self._hass = hass
        self._sensors = {}
        self._async_add_sensors_callback = async_add_sensors_callback

        self._url = config.get(CONF_URL)
        self._timestamp = None

        # parse out the unique pool identifier from the url
        match = re.search(r'/mypool/(.+)', self._url)
        if match:
            self._pool_id = match[0]

        self._async_client = None
        self._timeout = DEFAULT_TIMEOUT

        default_name = DEFAULT_NAME
        self._name = config.get(CONF_NAME, default_name)

        LOG.info(f"Creating Pool Math sensors for '{self._name}'")

    # TODO: Eventually move this all to external async client, and convert this to a HASS async impl
    async def async_update(self):
        """Fetch latest log entries from the Pool Math service"""
        try:
            if not self._async_client:
                self._async_client = httpx.AsyncClient(verify=False)

            LOG.debug(f"GET {self._url} (timeout={self._timeout})")
            response = await self._async_client.request('GET', self._url, timeout=self._timeout)

            soup = BeautifulSoup(response.text, 'html.parser')
            LOG.debug(f"Updating from raw data: %s", soup)
            self._update_from_log_entries(soup)

        except httpx.RequestError as ex:
            LOG.error(f"Error fetching {self._name} data from {self._url}: {ex}")

    def get_sensor(self, sensor_type):
        sensor = self._sensors.get(sensor_type, None)
        if sensor:
            return sensor

        config = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, None)
        if config is None:
            LOG.warning(f"Unknown Pool Math sensor '{sensor_type}' discovered at {self._url}")
            return None

        name = self._name + ' ' + config[ATTR_NAME]
        sensor = UpdatableSensor(self._hass, self._pool_id, name, config, sensor_type)
        self._sensors[sensor_type] = sensor

        # register sensor with Home Assistant from a thread
        await self._async_add_sensors_callback([sensor], True)

        return sensor


    def _update_from_log_entries(self, poolmath_soup):
        updated_sensors = {}
        latest_timestamp = None

        # Read back through all log entries and update any changed sensor states (since a given
        # log entry may only have a subset of sensor states)
        log_entries = poolmath_soup.find_all('div', class_='testLogCard')
        for log_entry in log_entries:
            log_fields = log_entry.select('.chiclet')
            LOG.debug("Pool Math log fields=%s", log_fields)

            if not latest_timestamp:
                # capture the timestamp for the most recent Pool Math log entry
                latest_timestamp = log_entry.find('time', class_='timestamp timereal')

            # FIXME: improve parsing to be more robust to Pool Math changes
            for entry in log_fields:
                sensor_type = entry.contents[3].text.lower()
                if not sensor_type in updated_sensors:
                    state = entry.contents[1].text

                    sensor = self.get_sensor(sensor_type)
                    if sensor:
                        timestamp = log_entry.find('time', class_='timestamp timereal').text
                        if sensor.state != state:
                            LOG.info(f"Pool Math returned updated {sensor_type}={state} (timestamp={timestamp})")
                        sensor.inject_state(state, timestamp)
                        updated_sensors[sensor_type] = sensor

        # record the most recent log entry's timestamp as the service's last updated timestamp
        self._timestamp = latest_timestamp
        return latest_timestamp

    @property
    def sensor_names(self):
        return self._sensors.keys()

    @property
    def latest_log_timestamp(self):
        return self._timestamp

class PoolMathServiceSensor(Entity):
    """Sensor monitoring the Pool Math cloud service and updating any related sensors"""

    def __init__(self, name, config, poolmath_client):
        """Initialize the Pool Math service sensor."""
        self._name = name
        self._poolmath_client = poolmath_client
        self._update_state_from_client()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the sensors currently being monitored from Pool Math."""
        return self._state

    @property
    def icon(self):
        return ICON_POOL

    def _update_state_from_client(self):
        # re-updated the state with list of sensors that are being monitored (in case any new sensors were discovered)
        self._state = self._poolmath_client.sensor_names
        self._attr = {
            ATTR_LOG_TIMESTAMP: self._poolmath_client.latest_log_timestamp
        }

    async def async_update(self):
        """Get the latest data from the source and updates the state."""

        # trigger an update of this sensor (and all related sensors)
        await self._poolmath_client.async_update()
        self._update_state_from_client()

 
# FIXME: add timestamp for when the sensor/sample was taken
class UpdatableSensor(RestoreEntity):
    """Representation of a sensor whose state is kept up-to-date by an external data source."""

    def __init__(self, hass, pool_id, name, config, sensor_type):
        """Initialize the sensor."""
        super().__init__()

        self._hass = hass
        self._name = name
        self._config = config
        self._sensor_type = sensor_type
        self._state = None

        if pool_id:
            self._unique_id = f"poolmath_{pool_id}_{sensor_type}"
        else:
            self._unique_id = None
        
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION
        }

        # FIXME: use 'targets' configuration value and load appropriate yaml
        targets_source = TFP_TARGET
        targets_map = get_pool_targets(targets_source)
        if targets_map:
            self._targets = targets_map.get(sensor_type)
            if self._targets:
                self._attrs[ATTR_TARGET_SOURCE] = targets_source
                self._attrs.update(self._targets)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def should_poll(self):
        return True # FIXME: get scheduled updates working below

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._config[ATTR_UNIT_OF_MEASUREMENT]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the any state attributes."""
        return self._attrs

    @property
    def icon(self):
        return self._config['icon']

    def inject_state(self, state, timestamp):
        state_changed = self._state != state
        self._attrs[ATTR_LOG_TIMESTAMP] = timestamp

        if state_changed:
            self._state = state

            # FIXME: see should_poll
            # notify Home Assistant that the sensor has been updated
            #if (self.hass and self.schedule_update_ha_state):
            #    self.schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        
        # for this integration, restoring state really doesn't matter right now (but leaving code below in place)
        # Reason: all the sensors are dynamically created based on Pool Math service call, which always returns
        # the latest state as well!
        if self._state:
            return

        # on restart, attempt to restore previous state (SEE COMMENT ABOVE WHY THIS ISN'T USEFUL CURRENTLY)
        # (see https://aarongodfrey.dev/programming/restoring-an-entity-in-home-assistant/)
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state
        LOG.debug(f"Restored sensor {self._name} previous state {self._state}")

        # restore any attributes
        if ATTR_LOG_TIMESTAMP in state.attributes:
            self._attrs[ATTR_LOG_TIMESTAMP] = state.attributes[ATTR_LOG_TIMESTAMP]

        async_dispatcher_connect(
            self._hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
