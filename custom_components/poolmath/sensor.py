"""Pool Math sensor platform."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import parse_pool
from .const import (
    ATTRIBUTION,
    ATTR_LAST_UPDATED,
    CONF_USER_ID,
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .coordinator import PoolMathUpdateCoordinator
from .models import PoolMathConfig
from .targets import POOL_MATH_SENSOR_SETTINGS

LOG = logging.getLogger(__name__)

# Sensors that should only be included if tracked in Pool Math
CONDITIONAL_SENSORS = {
    'salt': 'trackSalt',
    'bor': 'trackBor',
    'borate': 'trackBor',
    'cc': 'trackCC',
    'csi': 'trackCSI',
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Math sensor based on a config entry."""

    # Get coordinator from integration setup
    coordinator: PoolMathUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        'coordinator'
    ]

    config = PoolMathConfig(
        user_id=entry.options[CONF_USER_ID],
        pool_id=entry.options[CONF_POOL_ID],
        name=entry.options[CONF_NAME],
        timeout=entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        target=entry.options[CONF_TARGET],
    )

    # Fetch initial data to determine which sensors to create
    await coordinator.async_config_entry_first_refresh()

    entities = []

    if coordinator.data and coordinator.data.json:
        pool = parse_pool(coordinator.data.json)
        if pool and pool.get('overview'):
            overview = pool['overview']

            # Create sensors for available measurements
            for sensor_key in POOL_MATH_SENSOR_SETTINGS:
                # Skip if measurement not available
                if sensor_key not in overview or overview.get(sensor_key) is None:
                    continue

                # Skip conditional sensors if not tracked
                if sensor_key in CONDITIONAL_SENSORS:
                    track_key = CONDITIONAL_SENSORS[sensor_key]
                    if not pool.get(track_key):
                        LOG.debug(
                            f'Skipping {sensor_key} - tracking disabled in Pool Math'
                        )
                        continue

                # Create sensor entity
                entities.append(PoolMathSensor(coordinator, config, sensor_key))

            # Add calculated Total Chlorine if we have FC and CC
            if 'fc' in overview and 'cc' in overview:
                entities.append(PoolMathSensor(coordinator, config, 'tc'))

    if entities:
        async_add_entities(entities)
        LOG.info(f'Created {len(entities)} Pool Math sensors for {config.name}')
    else:
        LOG.warning(f'No sensor data available for {config.name}')


def get_device_info(
    config: PoolMathConfig, pool_data: dict[str, Any] | None = None
) -> DeviceInfo:
    """Get device info for Pool Math integration."""
    pool_name = config.name
    if pool_data:
        pool_name = pool_data.get('name', config.name)

    return DeviceInfo(
        identifiers={(DOMAIN, config.pool_id)},
        configuration_url=f'https://www.troublefreepool.com/mypool/{config.user_id}/{config.pool_id}',
        entry_type=DeviceEntryType.SERVICE,
        manufacturer='Trouble Free Pool',
        model='Pool Math',
        name=pool_name,
    )


class PoolMathSensor(CoordinatorEntity[PoolMathUpdateCoordinator], SensorEntity):
    """Individual Pool Math sensor."""

    def __init__(
        self,
        coordinator: PoolMathUpdateCoordinator,
        config: PoolMathConfig,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._config = config
        self._sensor_type = sensor_type
        self._attr_attribution = ATTRIBUTION

        # Get sensor settings
        settings = POOL_MATH_SENSOR_SETTINGS.get(sensor_type, {})

        # Set basic attributes
        sensor_name = settings.get('name', sensor_type.upper())
        self._attr_name = f'{config.name} {sensor_name}'
        self._attr_translation_key = sensor_type
        self._attr_unique_id = f'poolmath_{config.pool_id}_{sensor_type}'
        self._attr_icon = settings.get('icon')
        self._attr_native_unit_of_measurement = settings.get('unit_of_measurement')

        # Handle temperature unit conversion
        if sensor_type in ['temp', 'waterTemp']:
            if config.unit_of_measurement == UnitOfTemperature.CELSIUS:
                self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

        # Set device class for known types
        if sensor_type in ['temp', 'waterTemp']:
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
        elif sensor_type in ['pressure']:
            self._attr_device_class = SensorDeviceClass.PRESSURE
        elif sensor_type in ['flowRate']:
            self._attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE

        # Set device info
        self._attr_device_info = get_device_info(config)

        # Initialize state
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data or not self.coordinator.data.json:
            return

        pool = parse_pool(self.coordinator.data.json)
        if not pool:
            return

        overview = pool.get('overview', {})

        # Handle calculated total chlorine
        if self._sensor_type == 'tc':
            fc = overview.get('fc')
            cc = overview.get('cc')
            if fc is not None and cc is not None:
                self._attr_native_value = fc + cc
                self._attr_extra_state_attributes = {
                    'fc': fc,
                    'cc': cc,
                    'calculated': True,
                }
        else:
            # Regular sensor value
            value = overview.get(self._sensor_type)
            if value is not None:
                self._attr_native_value = value

                # Add timestamp if available
                timestamp = overview.get(f'{self._sensor_type}Ts')
                if timestamp:
                    self._attr_extra_state_attributes = {ATTR_LAST_UPDATED: timestamp}

                # Handle temperature conversion
                if (
                    self._sensor_type in ['temp', 'waterTemp']
                    and self._config.unit_of_measurement == UnitOfTemperature.CELSIUS
                ):
                    self._attr_native_value = (value - 32) * 5 / 9

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.json is not None
        )

