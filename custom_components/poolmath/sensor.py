import asyncio
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_URL,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import RestoreEntity
#from homeassistant.components.sensor.SensorEntity import SensorEntity

from .client import PoolMathClient
from .const import (
    ATTR_ATTRIBUTION,
    ATTR_DESCRIPTION,
    ATTR_LAST_UPDATED_TIME,
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ATTR_TARGET_SOURCE,
    ATTRIBUTION,
    CONF_TARGET,
    CONF_TIMEOUT,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ICON_GAUGE,
    ICON_POOL,
)
from .targets import POOL_MATH_SENSOR_SETTINGS, get_pool_targets

LOG = logging.getLogger(__name__)

DATA_UPDATED = "poolmath_data_updated"

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        # NOTE: targets are not really implemented, other than tfp
        vol.Optional(
            CONF_TARGET, default="tfp"
        ): cv.string  # targets/*.yaml file with min/max targets
        # FIXME: allow specifying EXACTLY which log types to monitor, always create the sensors
        # vol.Optional(CONF_LOG_TYPES, default=None):
    }
)


async def async_setup_platform(
    hass, config, async_add_entities_callback, discovery_info=None
):
    """Set up the Pool Math sensor integration."""
    url = config.get(CONF_URL)
    name = config.get(CONF_NAME)
    timeout = config.get(CONF_TIMEOUT)

    client = PoolMathClient(url, name=name, timeout=timeout)

    # create the core Pool Math service sensor, which is responsible for updating all other sensors
    sensor = PoolMathServiceSensor(
        hass, config, name, client, async_add_entities_callback
    )
    async_add_entities_callback([sensor], True)


class PoolMathServiceSensor(Entity):
    """Sensor monitoring the Pool Math cloud service and updating any related sensors"""

    def __init__(
        self, hass, config, name, poolmath_client, async_add_entities_callback
    ):
        """Initialize the Pool Math service sensor."""
        self.hass = hass
        self._config = config
        self._name = name
        
        self._managed_sensors = {}
        self._poolmath_client = poolmath_client
        
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_URL: self._poolmath_client.url
        }
        
        self._async_add_entities_callback = async_add_entities_callback

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Pool Math Service: " + self._name

    @property
    def state(self):
        return self._attrs.get(ATTR_LAST_UPDATED_TIME)

    @property
    def icon(self):
        return ICON_POOL

    @property
    def should_poll(self):
        return True

    async def async_update(self):
        """Get the latest data from the source and updates the state."""

        url = self._attrs.get(CONF_URL)
        try:
            # trigger an update of this sensor (and all related sensors)
            client = self._poolmath_client
            poolmath_json = await client.async_update()
        except Exception as e:
            LOG.warning(f"PoolMath request failed! {url}: {e}")
            return

        if not poolmath_json:
            LOG.warning(f"PoolMath returned NO JSON data: {url}")
            return

        # update state attributes with relevant data
        pools = poolmath_json.get('pools')
        if not pools:
            LOG.warning(f"PoolMath returned EMPTY pool data: {url}")
            return

        pool = pools[0].get('pool')
        self._attrs |= {
            'name': pool.get('name'),
            'volume': pool.get('volume')
        }

        # iterate through all the log entries and update sensor states
        timestamp = await client.process_log_entry_callbacks(
            poolmath_json, self._update_sensor_callback
        )
        self._attrs[ATTR_LAST_UPDATED_TIME] = timestamp

        
    @property
    def extra_state_attributes(self):
        """Return the any state attributes."""
        return self._attrs

    async def get_sensor_entity(self, sensor_type):
        sensor = self._managed_sensors.get(sensor_type, None)
        if sensor:
            return sensor

        config = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, None)
        if config is None:
            LOG.warning(f"Unknown sensor '{sensor_type}' discovered for {self.name}")
            return None

        name = self._name + " " + config[ATTR_NAME]
        pool_id = self._poolmath_client.pool_id

        sensor = UpdatableSensor(self.hass, pool_id, name, config, sensor_type)
        self._managed_sensors[sensor_type] = sensor

        # register sensor with Home Assistant (async callback requires passing to loop)
        self._async_add_entities_callback([sensor], True)

        return sensor

    async def _update_sensor_callback(self, measurement_type, timestamp, state, attributes):
        """Update the sensor with the details from the measurement"""
        sensor = await self.get_sensor_entity(measurement_type)
        if sensor and sensor.state != state:
            LOG.info(f"{self._name} {measurement_type}={state} (timestamp={timestamp})")
            sensor.inject_state(state, timestamp, attributes)

    @property
    def sensor_names(self):
        return self._managed_sensors.keys()


class UpdatableSensor(RestoreEntity):
#class UpdatableSensor(RestoreEntity, SensorEntity):
    """Representation of a sensor whose state is kept up-to-date by an external data source."""

    def __init__(self, hass, pool_id, name, config, sensor_type):
        """Initialize the sensor."""
        super().__init__()

        self.hass = hass
        self._name = name
        self._config = config
        self._sensor_type = sensor_type
        self._state = None

        if pool_id:
            self._unique_id = f"poolmath_{pool_id}_{sensor_type}"
        else:
            self._unique_id = None

        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

        # FIXME: use 'targets' configuration value and load appropriate yaml
        targets_map = get_pool_targets()
        if targets_map:
            self._targets = targets_map.get(sensor_type)
            if self._targets:
                self._attrs[ATTR_TARGET_SOURCE] = "tfp"
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
        return True  # FIXME: get scheduled updates working below

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._config[ATTR_UNIT_OF_MEASUREMENT]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the any state attributes."""
        return self._attrs

    @property
    def icon(self):
        return self._config["icon"]

    def inject_state(self, state, timestamp, attributes):
        state_changed = self._state != state
        
        self._attrs[ATTR_LAST_UPDATED_TIME] = timestamp
        if attributes:
            self._attrs |= attributes

        if state_changed:
            self._state = state

            # FIXME: see should_poll
            # notify Home Assistant that the sensor has been updated
            # if (self.hass and self.schedule_update_ha_state):
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

        # restore attributes
        if ATTR_LAST_UPDATED_TIME in state.attributes:
            self._attrs[ATTR_LAST_UPDATED_TIME] = state.attributes[ATTR_LAST_UPDATED_TIME]

        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
