from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_URL,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .client import PoolMathClient
from .const import (
    ATTR_LAST_UPDATED_TIME,
    ATTR_TARGET_SOURCE,
    ATTRIBUTION,
    CONF_SHARE_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    DOMAIN,
    ICON_POOL,
)
from .targets import POOL_MATH_SENSOR_SETTINGS, get_pool_targets

LOG = logging.getLogger(__name__)

DATA_UPDATED = "poolmath_data_updated"

SCAN_INTERVAL = timedelta(minutes=2)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Math sensor based on a config entry."""

    share_id = entry.options[CONF_SHARE_ID]
    name = entry.options[CONF_NAME]
    timeout = entry.options[CONF_TIMEOUT]
    target = entry.options[CONF_TARGET]
    # log_types = entry.options[CONF_LOG_TYPES]

    client = PoolMathClient(share_id, name=name, timeout=timeout)

    # create the core Pool Math service sensor, which is responsible for updating all other sensors
    sensor = PoolMathServiceSensor(hass, entry, name, client, async_add_entities)
    async_add_entities([sensor])


class PoolMathServiceSensor(SensorEntity):
    """Sensor monitoring the Pool Math cloud service and updating any related sensors"""

    def __init__(self, hass, entry, name, poolmath_client, async_add_entities_callback):
        """Initialize the Pool Math service sensor."""
        self.hass = hass
        self._entry = entry
        self._name = name

        self._managed_sensors = {}
        self._poolmath_client = poolmath_client

        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_URL: self._poolmath_client.url,
        }
        self._attr_unique_id = f"poolmath_{self._poolmath_client.pool_id}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.troublefreepool.com/blog/poolmath/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Pool Math (Trouble Free Pool)",
            name="Pool Math",
        )

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
        pools = poolmath_json.get("pools")
        if not pools:
            LOG.warning(f"PoolMath returned EMPTY pool data: {url}")
            return

        pool = pools[0].get("pool")
        self._attrs |= {"name": pool.get("name"), "volume": pool.get("volume")}

        # iterate through all the log entries and update sensor states
        timestamp = await client.process_log_entry_callbacks(
            poolmath_json, self._update_sensor_callback
        )
        self._attrs[ATTR_LAST_UPDATED_TIME] = timestamp

    @property
    def extra_state_attributes(self):
        """Return the any state attributes."""
        return self._attrs

    async def get_sensor_entity(self, sensor_type, poolmath_json):
        sensor = self._managed_sensors.get(sensor_type, None)
        if sensor:
            return sensor

        config = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, None)
        if config is None:
            LOG.warning(f"Unknown sensor '{sensor_type}' discovered for {self.name}")
            return None

        name = self._name + " " + config[ATTR_NAME]
        pool_id = self._poolmath_client.pool_id

        sensor = UpdatableSensor(
            self.hass, self._entry, pool_id, name, config, sensor_type, poolmath_json
        )
        self._managed_sensors[sensor_type] = sensor

        # register sensor with Home Assistant (async callback requires passing to loop)
        self._async_add_entities_callback([sensor], True)

        return sensor

    async def _update_sensor_callback(
        self, measurement_type, timestamp, state, attributes, poolmath_json
    ):
        """Update the sensor with the details from the measurement"""
        sensor = await self.get_sensor_entity(measurement_type, poolmath_json)
        if sensor and sensor.state != state:
            LOG.info(
                f"{sensor.name} {measurement_type}={state} {sensor.unit_of_measurement} (timestamp={timestamp})"
            )
            sensor.inject_state(state, timestamp, attributes)

    @property
    def sensor_names(self):
        return self._managed_sensors.keys()


class UpdatableSensor(RestoreEntity, SensorEntity):
    """Representation of a sensor whose state is kept up-to-date by an external data source."""

    def __init__(self, hass, entry, pool_id, name, config, sensor_type, poolmath_json):
        """Initialize the sensor."""
        super().__init__()

        self.hass = hass
        self._name = name
        self._entry = entry
        self._config = config
        self._sensor_type = sensor_type
        self._state = None

        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._attr_unique_id = f"poolmath_{pool_id}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.troublefreepool.com/blog/poolmath/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Pool Math (Trouble Free Pool)",
            name="Pool Math",
        )

        # TEMPORARY HACK to get correct unit of measurement for water temps (but this also
        # applies to other units). No time to fix now, but perhaps someone will submit a PR
        # to fix this in future.
        self._unit_of_measurement = self._config[ATTR_UNIT_OF_MEASUREMENT]
        if self._unit_of_measurement in [
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        ]:
            # inspect the first JSON response to determine things that are not specified
            # with sensor values (since units/update timestamps are in separate keys
            # within the JSON doc)
            pools = poolmath_json.get("pools")
            if pools:
                pool = pools[0].get("pool")
                if pool.get("waterTempUnitDefault") == 1:
                    self._unit_of_measurement = UnitOfTemperature.CELSIUS
                else:
                    self._unit_of_measurement = UnitOfTemperature.FAHRENHEIT

            LOG.info(f"Unit of temperature measurement {self._unit_of_measurement}")

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
    def should_poll(self):
        return True  # FIXME: get scheduled updates working below

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

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
            self._attrs[ATTR_LAST_UPDATED_TIME] = state.attributes[
                ATTR_LAST_UPDATED_TIME
            ]

        async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)
