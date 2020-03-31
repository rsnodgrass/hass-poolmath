import logging

import voluptuous as vol
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from bs4 import BeautifulSoup
from datetime import timedelta

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components.rest.sensor import RestData
from homeassistant.const import (
    CONF_NAME,
    CONF_URL
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
import homeassistant.helpers.config_validation as cv

LOG = logging.getLogger(__name__)

DEFAULT_NAME = 'Pool'

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string
    }
)

# see https://www.troublefreepool.com/blog/2018/12/12/abcs-of-pool-water-chemistry/
POOL_MATH_SENSOR_SETTINGS = {
    'cc':     { 'name': 'CC',     'units': 'mg/L', 'description': 'Combined Chlorine', 'icon': 'mdi:gauge' },
    'temp':   { 'name': 'Temp',   'units': 'F°',   'description': 'Temperature'      , 'icon': 'mdi:coolant-temperature' },
    'fc':     { 'name': 'FC',     'units': 'mg/L', 'description': 'Free Chlorine'    , 'icon': 'mdi:gauge' },
    'ph':     { 'name': 'pH',     'units': 'pH',   'description': 'Acidity/Basicity' , 'icon': 'mdi:gauge' },
    'ta':     { 'name': 'TA',     'units': 'ppm',  'description': 'Total Alkalinity' , 'icon': 'mdi:gauge' },
    'ch':     { 'name': 'CH',     'units': 'ppm',  'description': 'Calcium Hardness' , 'icon': 'mdi:gauge' },
    'cya':    { 'name': 'CYA',    'units': 'ppm',  'description': 'Cyanuric Acid'    , 'icon': 'mdi:gauge' },
    'salt':   { 'name': 'Salt',   'units': 'ppm',  'description': 'Salt'             , 'icon': 'mdi:gauge' },
    'borate': { 'name': 'Borate', 'units': 'ppm',  'description': 'Borate'           , 'icon': 'mdi:gauge' },
    'csi':    { 'name': 'CSI',    'units': 'CSI',  'description': 'Calcite Saturation Index', 'icon': 'mdi:gauge' }
}

TFP_RECOMMENDED_TARGET_LEVELS = {
    'temp':   { 'min': 32,   'max': 104  },
    'fc':     { 'min': 0,    'max': 0    }, # depends on CYA
    'cc':     { 'min': 0,    'max': 0    },
    'ph':     { 'min': 7.2,  'max': 7.8, 'target': 7.7 },
    'ta':     { 'min': 0,    'max': 0    },
    'ch':     { 'min': 250,  'max': 350  }, # with salt: 350-450 ppm
    'cya':    { 'min': 30,   'max': 50   }, # with salt: 70-80 ppm
    'salt':   { 'min': 2000, 'max': 3000 },
    'borate': { 'min': 30,   'max': 50   },
    'csi':    { 'min': 0,    'max': 0    }
}

def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the Pool Math sensor integration."""
    client = PoolMathClient(hass, config, add_entities_callback)

    # create the Pool Math service sensor, which is responsible for updating all other sensors
    sensor = PoolMathServiceSensor("Pool Math Service", config, client)
    add_entities_callback([sensor], True)

class PoolMathClient():
    def __init__(self, hass, config, add_sensors_callback):
        self._hass = hass
        self._sensors = {}
        self._add_sensors_callback = add_sensors_callback

        verify_ssl = True
        self._url = config.get(CONF_URL)
        self._rest = RestData('GET', self._url, '', '', '', verify_ssl)

        # query the latest data from Pool Math
        soup = self._fetch_latest_data()
        if soup is None:
            raise PlatformNotReady
        
        self._name = config.get(CONF_NAME)
        if self._name == None:
            self._name = DEFAULT_NAME

            # extract the pool name, if defined
            h1_span = soup.select('h1')
            if h1_span and h1_span[0]:
                pool_name = h1_span[0].string
                if pool_name != None:
                    self._name = f"{pool_name} {DEFAULT_NAME}"

        LOG.info(f"Creating Pool Math sensors for '{self._name}'")
        self._update_from_log_entries(soup)

    def _fetch_latest_data(self):
        """Fetch the latest log entries from the Pool Math service"""
        self._rest.update()
        result = self._rest.data
        if result is None:
            LOG.warn(f"Failed updating Pool Math data from {self._url}")
            return None
        soup = BeautifulSoup(result, 'html.parser')
        #LOG.debug("Raw data from %s: %s", self._url, soup)
        return soup

    def update(self):
        soup = self._fetch_latest_data()
        if not soup:
            return None
        return self._update_from_log_entries(soup)

    def get_sensor(self, sensor_type):
        sensor = self._sensors.get(sensor_type, None)
        if sensor:
            return sensor

        config = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, None)
        if config is None:
            LOG.warning(f"Unknown Pool Math sensor '{sensor_type}' discovered at {self._url}")
            return None

        name = self._name + ' ' + config['name']
        sensor = UpdatableSensor(self._hass, name, config)
        self._sensors[sensor_type] = sensor

        # register sensor with Home Assistant
        self._add_sensors_callback([sensor], True)
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


class PoolMathServiceSensor(Entity):
    """Sensor monitoring the Pool Math cloud service and updating any related sensors"""

    def __init__(self, name, config, poolmath_client):
        """Initialize the Pool Math service sensor."""
        self._name = name
        self._state = None
        self._poolmath_client = poolmath_client

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        return "mdi:pool"

    def update(self):
        """Get the latest data from the source and updates the state."""
        # trigger an update of this sensor (and all related sensors)
        result = self._poolmath_client.update()
        if result:
            self._state = result

 
# FIXME: add timestamp for when the sensor/sample was taken
class UpdatableSensor(Entity, RestoreEntity):
    """Representation of a sensor whose state is kept up-to-date by an external data source."""

    def __init__(self, hass, name, config):
        """Initialize the sensor."""
        super().__init__()

        self._hass = hass
        self._name = name
        self._config = config
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        return True # FIXME: get scheduled updates working below

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._config['units']

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
        self._attrs = {"Log Timestamp": timestamp}

        if state_changed:
            self._state = state

            # FIXME: see should_poll
            # notify Home Assistant that the sensor has been updated
            #if (self.hass and self.schedule_update_ha_state):
            #    self.schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        
        # on restart, attempt to restore previous state (see https://aarongodfrey.dev/programming/restoring-an-entity-in-home-assistant/)
        state = await self.async_get_last_state()
        if not state:
            return
        self._state = state.state
        LOG.debug(f"Restored sensor {self._name} previous state {self._state}")

        # restore any attributes
        if 'Log Timestamp' in state.attributes:
            self._attrs = {
                "Log Timestamp": state.attributes['Log Timestamp']
            }

        async_dispatcher_connect(
            self._hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)