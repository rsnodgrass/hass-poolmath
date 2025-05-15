from __future__ import annotations
from datetime import timedelta
import logging

from homeassistant.components.sensor import SensorEntity, RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import PoolMathClient
from .const import (
    ATTRIBUTION,
    CONF_USER_ID,
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    DOMAIN,
)
from .models import PoolMathConfig, PoolMathState
from .targets import POOL_MATH_SENSOR_SETTINGS, get_pool_targets

LOG = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Math sensor based on a config entry."""

    config = PoolMathConfig(
        user_id=entry.options[CONF_USER_ID],
        pool_id=entry.options[CONF_POOL_ID],
        name=entry.options[CONF_NAME],
        timeout=entry.options[CONF_TIMEOUT],
        target=entry.options[CONF_TARGET],
        update_interval=timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, 8)),
    )

    client = PoolMathClient(
        user_id=config.user_id,
        pool_id=config.pool_id,
        name=config.name,
        timeout=config.timeout,
    )

    coordinator = PoolMathDataCoordinator(hass, client, config)
    
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    #
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        PoolMathServiceSensor(coordinator, config)
    ])


class PoolMathDataCoordinator(DataUpdateCoordinator[PoolMathState]):
    """Coordinator for Pool Math data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PoolMathClient,
        config: PoolMathConfig,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOG,
            name="Pool Math",
            update_interval=config.update_interval,
        )
        self._client = client
        self._config = config

    async def _async_update_data(self) -> PoolMathState:
        """Fetch data from Pool Math API."""
        try:
            data = await self._client.async_get_data()
            return PoolMathState(
                last_updated=data.get("last_updated"),
                attributes=data,
            )
        except Exception as err:
            LOG.error("Error updating Pool Math data: %s", err)
            raise UpdateFailed(err) from err


class PoolMathServiceSensor(SensorEntity):
    """Sensor monitoring the Pool Math cloud service."""

    def __init__(
        self,
        coordinator: PoolMathDataCoordinator,
        config: PoolMathConfig,
    ) -> None:
        """Initialize the Pool Math service sensor."""
        super().__init__(coordinator)
        self._config = config
        self._coordinator = coordinator
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_POOL_ID: config.pool_id,
            CONF_USER_ID: config.user_id
        }
        self._attr_name = f"Pool: {config.name}"
        self._attr_unique_id = f"poolmath_{config.user_id}_{config.pool_id}"
        self._attr_icon = "mdi:water"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.troublefreepool.com/blog/poolmath/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"pool_math_{config.user_id}_{config.pool_id}")},
            manufacturer="Pool Math (Trouble Free Pool)",
            name="Pool Math",
        )

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.last_updated
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes."""
        return self._attrs

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        await super().async_added_to_hass()
        
        # restore previous state if available on HA startup
        if (last_state := await self.async_get_last_state()) is not None:
            self._state = last_state.state
            self._attrs = last_state.attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
        return ICON_POOL

    @property
    def should_poll(self):
        return True

    async def async_update(self) -> None:
        """Update the sensor's state and attributes from Pool Math API.

        This method fetches the latest pool data and updates:
        - Pool name and volume
        - Last updated timestamp
        - All sensor states via callback
        """

        url = self._attrs.get(CONF_URL)
        try:
            # trigger an update of this sensor (and all related sensors)
            client = self._poolmath_client
            poolmath_json = await client.async_update()
        except Exception as e:
            LOG.warning(
                f"Failed to update Pool Math data for {self.name} at {url}: {str(e)}"
            )
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
        self._attrs |= {
            "name": pool.get("name", "Unknown Pool"),
            "volume": pool.get("volume", 0)
        }

        # iterate through all the log entries and update sensor states
        timestamp = await client.process_log_entry_callbacks(
            poolmath_json, self._update_sensor_callback
        )
        self._attrs[ATTR_LAST_UPDATED_TIME] = timestamp

    async def get_sensor_entity(
        self, sensor_type: str, poolmath_json: dict
    ) -> UpdatableSensor | None:
        if sensor := self._managed_sensors.get(sensor_type, None):
            return sensor

        config = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, None)
        if config is None:
            LOG.warning(f"Unknown sensor '{sensor_type}' discovered for {self.name}")
            return None

        name = self._name + " " + config[ATTR_NAME]
        pool_id = self._poolmath_client.pool_id

        sensor = UpdatableSensor(
            self.hass, self._entry, name, config, sensor_type, poolmath_json
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
            await sensor.inject_state(state, timestamp, attributes)

        # If FC or CC is updated, update the calculated TC sensor as well
        if measurement_type in ['fc', 'cc']:
            await self._update_total_chlorine_sensor(timestamp, attributes, poolmath_json)

    async def _update_total_chlorine_sensor(
        self, timestamp, attributes, poolmath_json
    ):
        """
        Update Total Chlorine sensor calculated from FC and CC measurements
        since PoolMath JSON API does not include a tc value.
        """
        # NOTE: If a pypoolmath client is ever created, it may be better to
        # just inject a 'tc' key/value into the response JSON rather than here.
        fc_sensor = await self.get_sensor_entity('fc', poolmath_json)
        cc_sensor = await self.get_sensor_entity('cc', poolmath_json)
        if fc_sensor and cc_sensor:
            try:
                fc_value = float(fc_sensor.state) if fc_sensor.state else 0
                cc_value = float(cc_sensor.state) if cc_sensor.state else 0
                tc_value = fc_value + cc_value
                    
                tc_sensor = await self.get_sensor_entity('tc', poolmath_json)
                if tc_sensor:
                    LOG.info(
                        f"Updating TC sensor: FC={fc_value} + CC={cc_value} = TC={tc_value} mg/L"
                    )
                    await tc_sensor.inject_state(tc_value, timestamp, attributes)
            except (ValueError, TypeError) as e:
                LOG.warning(f"Error calculating total chlorine: {e}")

    @property
    def sensor_names(self):
        return self._managed_sensors.keys()


class UpdatableSensor(RestoreEntity, SensorEntity):
    """Representation of a sensor whose state is kept up-to-date by an external data source."""

    def __init__(self, hass, entry, name, config, sensor_type, poolmath_json):
        """Initialize the sensor."""
        super().__init__()

        self.hass = hass
        self._name = name
        self._entry = entry
        self._config = config
        self._sensor_type = sensor_type
        self._state = None
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_POOL_ID: config.pool_id,
            CONF_USER_ID: config.user_id
        }
        self._attr_unique_id = f"poolmath_{pool_id}_{sensor_type}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.troublefreepool.com/blog/poolmath/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="Pool Math (Trouble Free Pool)",
            name="Pool Math",
        )

        self.determine_unit_of_measurement()

    def determine_unit_of_measurement(self) -> None:
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
            if pools := poolmath_json.get("pools"):
                pool = pools[0].get("pool")
                if pool.get("waterTempUnitDefault") == 1:
                    self._unit_of_measurement = UnitOfTemperature.CELSIUS
                else:
                    self._unit_of_measurement = UnitOfTemperature.FAHRENHEIT

            LOG.info(f"Unit of temperature measurement {self._unit_of_measurement}")


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

    async def inject_state(self, state, timestamp, attributes=None) -> None:
        self._attrs[ATTR_LAST_UPDATED_TIME] = timestamp
        self._attrs[ATTR_LAST_UPDATED] = datetime.fromtimestamp(
            timestamp / 1000.0
        ).strftime("%Y-%m-%d %H:%M:%S")

        if attributes:
            self._attrs |= attributes

        # if state actually changed, notify HA and update any
        # anciliary data (e.g. targets)
        if self._state != state:
            self._state = state
            await self.update_sensor_targets()

            # notify Home Assistant that the sensor has been updated
            await self.async_write_ha_state()

    async def update_sensor_targets(self) -> None:
        """
        Update attributes for the sensor to include targets if 
        any are defined for this sensor value. (e.g. target, target_min, 
        target_max, warning_above).
        
        This should be called on every state update since eventually the
        calculations on several other sensor values may be used to determine
        the correct target values for a given sensor.
        """
        if targets := get_pool_sensor_targets():
            self._attrs[ATTR_TARGET_SOURCE] = "tfp"
            if target_val := targets.get(self._sensor_type):
                self._attrs.update(target_val)

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
