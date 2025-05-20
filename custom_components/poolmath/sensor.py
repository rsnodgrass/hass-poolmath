from __future__ import annotations
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, RestoreSensor
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    ATTR_ATTRIBUTION,
    UnitOfTemperature,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PoolMathUpdateCoordinator
from .client import PoolMathClient, parse_pool
from .const import (
    ATTRIBUTION,
    ATTR_NAME,
    ATTR_LAST_UPDATED,
    ATTR_TARGET_SOURCE,
    CONF_USER_ID,
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .models import PoolMathConfig
from .targets import POOL_MATH_SENSOR_SETTINGS, get_sensor_targets

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
        timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        target=entry.options[CONF_TARGET],
        update_interval=timedelta(minutes=entry.options.get(CONF_SCAN_INTERVAL, 8)),
    )
    LOG.info(f"Setting up Pool Math sensor for {config.name} / {config.pool_id}")

    client = PoolMathClient(
        user_id=config.user_id,
        pool_id=config.pool_id,
        name=config.name,
        timeout=config.timeout,
    )
    coordinator = PoolMathUpdateCoordinator(hass, client, config)

    # create the core PoolMathServiceSensor, which is responsible for updating all other sensors
    # FIXME: We should move all the UpdatableSensors to just be
    # updated by the PoolMathUpdateCoordinator directly. The DataUpdateCoordinator
    # pattern didn't exist within HA when hass-poolmath was created, but basically
    # the PoolMathServiceSensor entity that updates all the sensor entities is an
    # alternative implementation of the DataUpdateCoordinator pattern.
    sensor = PoolMathServiceSensor(hass, coordinator, entry, config, async_add_entities)
    async_add_entities([sensor])

    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    # If you do not want to retry setup on failure, use
    # coordinator.async_refresh() instead
    await coordinator.async_config_entry_first_refresh()


def get_device_info(config: PoolMathConfig) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, config.pool_id)},
        # configuration_url="https://troublefreepool.com/blog/poolmath/",
        configuration_url=f"https://api.poolmathapp.com/share/pool?userId={config.user_id}&poolId={config.pool_id}",
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="Pool Math",
        model="Pool",  # FIXME: Translate
        name=f"Pool {config.pool_id}",  # FIXME: this should probably come from JSON name for this pool
        # name_by_user=  ... the name set by the user in Home Assistant
    )


class PoolMathServiceSensor(
    CoordinatorEntity[PoolMathUpdateCoordinator], RestoreSensor, SensorEntity
):
    """
    Sensor monitoring the Pool Math cloud service.
    This is effectively a DataCoordinator pattern implementation
    that was implemented before Home Assistant added a standard
    DataUpdateCoordinator...with a bit more attribute handling and
    extraction of targets from JSON data.

    NOTE: Once the DataCoordinator also direcly updates the UpdatableSensors,
    we could get rid of the sensor that tracks the PoolMathServiceSensor
    entirely, just leaving the actual data sensors.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PoolMathUpdateCoordinator,
        entry: ConfigEntry,
        config: PoolMathConfig,
        add_entities_callback: AddEntitiesCallback,
    ) -> None:
        """Initialize the Pool Math service sensor."""
        super().__init__(coordinator)

        self.hass = hass
        self._coordinator = coordinator
        self._config = config
        self._entry = entry

        self._name = config.name
        self._attr_icon = "mdi:water"

        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_POOL_ID: config.pool_id,
            CONF_USER_ID: config.user_id,
            "url": f"https://api.poolmathapp.com/share/?userId={config.user_id}&poolId={config.pool_id}",
        }
        self._attr_name = f"Pool Math Service: {config.name}"
        self._attr_unique_id = f"poolmath_{config.user_id}_{config.pool_id}"

        self._managed_sensors = {}
        self._add_entities_callback = add_entities_callback

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return get_device_info(self._config)

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.last_updated
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attrs

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to Home Assistant."""
        # on restart, attempt to restore previous state using RestoreSensor
        if last_state := await self.async_get_last_sensor_data():
            self._state = last_state.native_value
            self._attr_native_value = last_state.native_value
            LOG.debug(f"Restored sensor {self._name} from prior state {self._state}")

        await super().async_added_to_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self._coordinator.data:
            return

        self._state = self._coordinator.data.last_updated

        json = self._coordinator.data.json
        if pool := parse_pool(json):
            self._attrs |= {
                "name": pool.get("name", "Unknown Pool"),  # FIXME: translate
                "volume": pool.get("volume", 0),
            }

        # schedule update for all sensors based on this pool's data
        # (remove once Updata)
        self.hass.async_create_task(self._update_sensors_from_coordinator_data(json))
        self.async_write_ha_state()

    async def _update_sensors_from_coordinator_data(self, json: dict):
        """
        Update all managed sensors from coordinator data.

        FIXME: Eventually this can go away once the UpdatableSensor class is
        updated to inherit from CoordinatorEntity[PoolMathUpdateCoordinator].
        """
        try:
            # Iterate through all log entries and update sensor states
            client = self._coordinator._client
            timestamp = await client.process_log_entry_callbacks(
                json, self._update_sensor_callback
            )
            if timestamp:
                self._attrs[ATTR_LAST_UPDATED] = str(timestamp)
        except Exception as e:
            LOG.exception(e)

    @property
    def should_poll(self) -> bool:
        """No need to poll. DataUpdateCoordinator notifies entity of updates."""
        return False

    async def async_update(self) -> None:
        """
        Called by Home Assistant when it needs to refresh the entity's state.
        We don't need to do anything here since we're using the coordinator pattern.
        """
        pass

    async def get_sensor_entity(
        self, sensor_type: str, poolmath_json: dict
    ) -> UpdatableSensor | None:
        """
        Caches all the UpdatableSensors so can be updated when the coordinator
        PoolMathServiceSensor has new JSON.
        """
        if sensor := self._managed_sensors.get(sensor_type, None):
            return sensor

        defaults = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, None)
        if defaults is None:
            LOG.warning(f"Unknown sensor '{sensor_type}' discovered for {self.name}")
            return None

        name = f"{self._name} {defaults[ATTR_NAME]}"
        sensor = UpdatableSensor(
            self.hass,
            self._coordinator,
            self._entry,
            self._config,
            defaults,
            name,
            sensor_type,
            poolmath_json,
        )
        self._managed_sensors[sensor_type] = sensor

        # register sensor with Home Assistant (async callback requires passing to loop)
        self._add_entities_callback([sensor], True)

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

            # if FC or CC is updated, update the calculated TC sensor as well
            if measurement_type in ["fc", "cc"]:
                await self._update_total_chlorine_sensor(
                    timestamp, attributes, poolmath_json
                )

    async def _update_total_chlorine_sensor(self, timestamp, attributes, poolmath_json):
        """
        Update Total Chlorine sensor calculated from FC and CC measurements
        since PoolMath JSON response does not include a tc value.
        """
        # NOTE: If a pypoolmath client is ever created, it may be better to
        # just inject a 'tc' key/value into the response JSON rather than here.
        fc_sensor = await self.get_sensor_entity("fc", poolmath_json)
        cc_sensor = await self.get_sensor_entity("cc", poolmath_json)
        if (
            fc_sensor
            and cc_sensor
            and fc_sensor.state is not None
            and cc_sensor.state is not None
        ):
            try:
                if tc_sensor := await self.get_sensor_entity("tc", poolmath_json):
                    fc = float(fc_sensor.state)
                    cc = float(cc_sensor.state)
                    tc = fc + cc

                    LOG.info(
                        f"{self._name} Total Chlorine: FC {fc} + CC {cc} = TC {tc} mg/L"
                    )
                    await tc_sensor.inject_state(tc, timestamp, attributes)
            except (ValueError, TypeError) as e:
                LOG.warning(f"Error calculating Total Chlorine: {e}")

    @property
    def sensor_names(self):
        return self._managed_sensors.keys()


class UpdatableSensor(RestoreSensor, SensorEntity):
    """
    Representation of a sensor whose state is kept up-to-date by an external
    data source (the PoolMathServiceSensor acting as a specialized coordinator)

    NOTE: This should move to a CoordinatorEntity[PoolMathUpdateCoordinator]
    eventually (this did not exist at the time hass-poolmath was created),
    if all the attribute and min/max/target handling is moved into this from
    the process_log_entry_callbacks() method.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: PoolMathUpdateCoordinator,
        entry,
        config: PoolMathConfig,
        defaults,
        name: str,
        sensor_type: str,
        poolmath_json: dict,
    ):
        """Initialize the sensor."""
        super().__init__()

        self.hass = hass
        self._coordinator = coordinator

        self._name = name
        self._sensor_type = sensor_type
        self._state = None

        self._entry = entry
        self._config = config
        self._defaults = defaults

        self._attr_unique_id = f"poolmath_{config.pool_id}_{sensor_type}"
        self._attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            CONF_POOL_ID: config.pool_id,
            CONF_USER_ID: config.user_id,
            ATTR_DESCRIPTION: defaults.get(ATTR_DESCRIPTION),  # FIXME: translate!
        }

        self._set_unit_of_measurement(poolmath_json)

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return get_device_info(self._config)


    def _set_unit_of_measurement(self, poolmath_json: dict) -> None:
        """
        If this is a temp sensor, update the unit of measurement to the
        units being used in the JSON response from Pool Math.
        """
        units = self._defaults[ATTR_UNIT_OF_MEASUREMENT]

        # set units for temperature sensors to the units returned by Pool Math
        if units in [
            UnitOfTemperature.FAHRENHEIT,
            UnitOfTemperature.CELSIUS,
        ]:
            if pool := parse_pool(poolmath_json):
                if pool.get("waterTempUnitDefault") == 1:
                    units = UnitOfTemperature.CELSIUS
                else:
                    units = UnitOfTemperature.FAHRENHEIT
            LOG.info(f"{self._name} temp units = {units}")

        self._unit_of_measurement = units

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self._coordinator:
            return

        # FIXME: update the appropriate key from poolmath_json
        # measurement_key = self._sensor_type
        # poolmath_json = self._coordinator.data.json
        # value = None
        # attr = get_attributes_for_measurement(poolmath_json, measurement_key)
        # timestamp = attr.get[ATTR_LAST_UPDATED]
        # self.inject_state(self, value, timestamp, attributes=attr)
        # self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No need to poll. Coordinator (PoolMathSensorService currently) notifies entity of updates."""
        return False

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
        return self._defaults["icon"]

    async def inject_state(self, state, timestamp, attributes=None) -> None:
        """
        Inject the current state externally (since an external coordinator is
        calling the service to retrieve multiple sensors at once).
        """
        # self._attrs[ATTR_LAST_UPDATED] = datetime.fromtimestamp(
        #    timestamp / 1000.0
        # ).strftime('%Y-%m-%d %H:%M:%S')

        if attributes:
            self._attrs |= attributes

        # if state actually changed, notify HA and update any
        # ancillary data (e.g. targets)
        if self._state != state:
            self._state = state

        await self.update_sensor_targets()

    async def update_sensor_targets(self) -> None:
        """
        Update attributes for the sensor to include targets if
        any are defined for this sensor value. (e.g. target, target_min,
        target_max, warning_above).

        This should be called on every state update since eventually the
        calculations on several other sensor values may be used to determine
        the correct target values for a given sensor.
        """
        if targets := get_sensor_targets():
            self._attrs[ATTR_TARGET_SOURCE] = "tfp"
            if target_val := targets.get(self._sensor_type):
                self._attrs.update(target_val)

    async def async_added_to_hass(self) -> None:
        # on restart, attempt to restore previous state using RestoreSensor
        if last_state := await self.async_get_last_sensor_data():
            self._state = last_state.native_value
            self._attr_native_value = last_state.native_value
            LOG.debug(f"Restored sensor {self._name} from prior state {self._state}")

        await super().async_added_to_hass()
