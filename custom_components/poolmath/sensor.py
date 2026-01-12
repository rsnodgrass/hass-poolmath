"""Pool Math sensor platform."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import parse_pool
from .const import (
    ATTR_IN_RANGE,
    ATTR_LAST_LOGGED,
    ATTR_LAST_UPDATED,
    ATTR_TARGET,
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ATTRIBUTION,
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_TIMEOUT,
    CONF_USER_ID,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .targets import get_target_range
from .coordinator import PoolMathUpdateCoordinator
from .models import PoolMathConfig

LOG = logging.getLogger(__name__)

# sensors that should only be included if tracked in Pool Math
CONDITIONAL_SENSORS = {
    'salt': 'trackSalt',
    'bor': 'trackBor',
    'borate': 'trackBor',
    'cc': 'trackCC',
    'csi': 'trackCSI',
}


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    'fc': SensorEntityDescription(
        key='fc',
        translation_key='fc',
        native_unit_of_measurement='mg/L',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'cc': SensorEntityDescription(
        key='cc',
        translation_key='cc',
        native_unit_of_measurement='mg/L',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'tc': SensorEntityDescription(
        key='tc',
        translation_key='tc',
        native_unit_of_measurement='mg/L',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'ph': SensorEntityDescription(
        key='ph',
        translation_key='ph',
        native_unit_of_measurement='pH',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'ta': SensorEntityDescription(
        key='ta',
        translation_key='ta',
        native_unit_of_measurement='ppm',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'ch': SensorEntityDescription(
        key='ch',
        translation_key='ch',
        native_unit_of_measurement='ppm',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'cya': SensorEntityDescription(
        key='cya',
        translation_key='cya',
        native_unit_of_measurement='ppm',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'salt': SensorEntityDescription(
        key='salt',
        translation_key='salt',
        native_unit_of_measurement='ppm',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'bor': SensorEntityDescription(
        key='bor',
        translation_key='bor',
        native_unit_of_measurement='ppm',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'borate': SensorEntityDescription(
        key='borate',
        translation_key='borate',
        native_unit_of_measurement='ppm',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'csi': SensorEntityDescription(
        key='csi',
        translation_key='csi',
        native_unit_of_measurement='CSI',
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'temp': SensorEntityDescription(
        key='temp',
        translation_key='temp',
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon='mdi:coolant-temperature',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'waterTemp': SensorEntityDescription(
        key='waterTemp',
        translation_key='water_temp',
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        icon='mdi:coolant-temperature',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'pressure': SensorEntityDescription(
        key='pressure',
        translation_key='pressure',
        native_unit_of_measurement=UnitOfPressure.PSI,
        device_class=SensorDeviceClass.PRESSURE,
        icon='mdi:gauge',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'flowRate': SensorEntityDescription(
        key='flowRate',
        translation_key='flow_rate',
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        icon='mdi:water-pump',
        state_class=SensorStateClass.MEASUREMENT,
    ),
    'swgCellPercent': SensorEntityDescription(
        key='swgCellPercent',
        translation_key='swg_cell_percent',
        native_unit_of_measurement='%',
        icon='mdi:battery-charging',
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def _migrate_entity_unique_ids(
    hass: HomeAssistant,
    config: PoolMathConfig,
) -> None:
    """Migrate entity unique IDs from old format to new format.

    Old format: poolmath_{pool_id}_{sensor_key}
    New format: poolmath_{user_id}_{pool_id}_{sensor_key}

    This ensures backwards compatibility when adding user_id to unique IDs.
    """
    ent_reg = er.async_get(hass)

    for sensor_key in SENSOR_DESCRIPTIONS:
        old_unique_id = f'poolmath_{config.pool_id}_{sensor_key}'
        new_unique_id = f'poolmath_{config.user_id}_{config.pool_id}_{sensor_key}'

        # check if entity with old unique ID exists
        entity_id = ent_reg.async_get_entity_id('sensor', DOMAIN, old_unique_id)
        if entity_id:
            LOG.info(f'Migrating entity {entity_id} to new unique ID format')
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Math sensor based on a config entry."""
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

    # migrate old unique IDs to new format for backwards compatibility
    await _migrate_entity_unique_ids(hass, config)

    # fetch initial data to determine which sensors to create
    await coordinator.async_config_entry_first_refresh()

    entities: list[PoolMathSensor] = []

    if coordinator.data and coordinator.data.json:
        pool = parse_pool(coordinator.data.json)
        if pool and pool.get('overview'):
            overview = pool['overview']

            # create sensors for available measurements
            for sensor_key, description in SENSOR_DESCRIPTIONS.items():
                # skip calculated TC for now, handle separately
                if sensor_key == 'tc':
                    continue

                # skip if measurement not available
                if sensor_key not in overview or overview.get(sensor_key) is None:
                    continue

                # skip conditional sensors if not tracked
                if sensor_key in CONDITIONAL_SENSORS:
                    track_key = CONDITIONAL_SENSORS[sensor_key]
                    if not pool.get(track_key):
                        LOG.debug(
                            f'Skipping {sensor_key} - tracking disabled in Pool Math'
                        )
                        continue

                entities.append(PoolMathSensor(coordinator, config, description))

            # add calculated Total Chlorine if we have FC and CC
            if 'fc' in overview and 'cc' in overview:
                entities.append(
                    PoolMathSensor(
                        coordinator, config, SENSOR_DESCRIPTIONS['tc'], calculated=True
                    )
                )

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
        identifiers={(DOMAIN, f'{config.user_id}_{config.pool_id}')},
        configuration_url=f'https://www.troublefreepool.com/mypool/{config.user_id}/{config.pool_id}',
        entry_type=DeviceEntryType.SERVICE,
        manufacturer='Trouble Free Pool',
        model='Pool Math',
        name=pool_name,
    )


class PoolMathSensor(CoordinatorEntity[PoolMathUpdateCoordinator], SensorEntity):
    """Individual Pool Math sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PoolMathUpdateCoordinator,
        config: PoolMathConfig,
        description: SensorEntityDescription,
        calculated: bool = False,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._config = config
        self._calculated = calculated
        self._target_profile = config.target
        self.entity_description = description

        self._attr_unique_id = (
            f'poolmath_{config.user_id}_{config.pool_id}_{description.key}'
        )
        self._attr_device_info = get_device_info(config)
        self._attr_native_value: float | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data or not self.coordinator.data.json:
            return

        pool = parse_pool(self.coordinator.data.json)
        if not pool:
            return

        overview = pool.get('overview', {})
        sensor_key = self.entity_description.key

        # handle calculated total chlorine
        if self._calculated and sensor_key == 'tc':
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
            # regular sensor value
            value = overview.get(sensor_key)
            if value is not None:
                self._attr_native_value = value

                # build attributes dict
                attrs: dict[str, Any] = {}

                # add timestamp as ISO format if available
                timestamp = overview.get(f'{sensor_key}Ts')
                if timestamp:
                    attrs[ATTR_LAST_UPDATED] = timestamp
                    # convert unix epoch to ISO datetime string
                    try:
                        dt = datetime.fromtimestamp(timestamp, tz=UTC)
                        attrs[ATTR_LAST_LOGGED] = dt.isoformat()
                    except (ValueError, OSError, TypeError):
                        pass  # skip if timestamp is invalid

                # add target range attributes if available
                target_range = get_target_range(sensor_key, self._target_profile, pool)
                if target_range:
                    if ATTR_TARGET_MIN in target_range:
                        attrs[ATTR_TARGET_MIN] = target_range[ATTR_TARGET_MIN]
                    if ATTR_TARGET_MAX in target_range:
                        attrs[ATTR_TARGET_MAX] = target_range[ATTR_TARGET_MAX]
                    if 'target' in target_range:
                        attrs[ATTR_TARGET] = target_range['target']

                    # calculate in_range status
                    target_min = target_range.get(ATTR_TARGET_MIN)
                    target_max = target_range.get(ATTR_TARGET_MAX)
                    if target_min is not None and target_max is not None:
                        attrs[ATTR_IN_RANGE] = target_min <= value <= target_max

                self._attr_extra_state_attributes = attrs

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.json is not None
        )
