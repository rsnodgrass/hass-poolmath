"""Pool Math binary sensor platform for out-of-range detection."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import parse_pool
from .const import (
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
from .coordinator import PoolMathUpdateCoordinator
from .models import PoolMathConfig
from .sensor import get_device_info
from .targets import CHEMISTRY_SENSORS_WITH_TARGETS, get_target_range

LOG = logging.getLogger(__name__)

# binary sensor descriptions for chemistry problem sensors
BINARY_SENSOR_DESCRIPTIONS: dict[str, BinarySensorEntityDescription] = {
    'fc': BinarySensorEntityDescription(
        key='fc',
        translation_key='fc_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'cc': BinarySensorEntityDescription(
        key='cc',
        translation_key='cc_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'ph': BinarySensorEntityDescription(
        key='ph',
        translation_key='ph_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'ta': BinarySensorEntityDescription(
        key='ta',
        translation_key='ta_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'ch': BinarySensorEntityDescription(
        key='ch',
        translation_key='ch_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'cya': BinarySensorEntityDescription(
        key='cya',
        translation_key='cya_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'salt': BinarySensorEntityDescription(
        key='salt',
        translation_key='salt_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'bor': BinarySensorEntityDescription(
        key='bor',
        translation_key='bor_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'borate': BinarySensorEntityDescription(
        key='borate',
        translation_key='borate_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    'csi': BinarySensorEntityDescription(
        key='csi',
        translation_key='csi_problem',
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
}

# sensors that are conditional (only created if tracked in Pool Math)
CONDITIONAL_SENSORS = {
    'salt': 'trackSalt',
    'bor': 'trackBor',
    'borate': 'trackBor',
    'csi': 'trackCSI',
}


async def _migrate_entity_unique_ids(
    hass: HomeAssistant,
    config: PoolMathConfig,
) -> None:
    """Migrate binary sensor unique IDs from old format to new format.

    Old format: poolmath_{pool_id}_{sensor_key}_problem
    New format: poolmath_{user_id}_{pool_id}_{sensor_key}_problem
    """
    ent_reg = er.async_get(hass)

    for sensor_key in BINARY_SENSOR_DESCRIPTIONS:
        old_unique_id = f'poolmath_{config.pool_id}_{sensor_key}_problem'
        new_unique_id = (
            f'poolmath_{config.user_id}_{config.pool_id}_{sensor_key}_problem'
        )

        entity_id = ent_reg.async_get_entity_id('binary_sensor', DOMAIN, old_unique_id)
        if entity_id:
            LOG.info(f'Migrating binary sensor {entity_id} to new unique ID format')
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Pool Math binary sensors based on a config entry."""
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

    # migrate old unique IDs for backwards compatibility
    await _migrate_entity_unique_ids(hass, config)

    entities: list[PoolMathProblemSensor] = []

    if coordinator.data and coordinator.data.json:
        pool = parse_pool(coordinator.data.json)
        if pool and pool.get('overview'):
            overview = pool['overview']

            # create binary sensors for chemistry measurements with targets
            for sensor_key in CHEMISTRY_SENSORS_WITH_TARGETS:
                # skip if measurement not available
                if sensor_key not in overview or overview.get(sensor_key) is None:
                    continue

                # skip conditional sensors if not tracked
                if sensor_key in CONDITIONAL_SENSORS:
                    track_key = CONDITIONAL_SENSORS[sensor_key]
                    if not pool.get(track_key):
                        LOG.debug(
                            f'Skipping {sensor_key} binary sensor - tracking disabled'
                        )
                        continue

                # check if we have a description for this sensor
                if sensor_key not in BINARY_SENSOR_DESCRIPTIONS:
                    continue

                # check if we have target ranges for this sensor
                target_range = get_target_range(sensor_key, config.target, pool)
                if not target_range:
                    LOG.debug(f'Skipping {sensor_key} binary sensor - no target range')
                    continue

                entities.append(
                    PoolMathProblemSensor(
                        coordinator,
                        config,
                        BINARY_SENSOR_DESCRIPTIONS[sensor_key],
                    )
                )

    if entities:
        async_add_entities(entities)
        LOG.info(f'Created {len(entities)} Pool Math binary sensors for {config.name}')


class PoolMathProblemSensor(
    CoordinatorEntity[PoolMathUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if a pool chemistry value is out of range."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PoolMathUpdateCoordinator,
        config: PoolMathConfig,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)

        self._config = config
        self._target_profile = config.target
        self.entity_description = description

        self._attr_unique_id = (
            f'poolmath_{config.user_id}_{config.pool_id}_{description.key}_problem'
        )
        self._attr_device_info = get_device_info(config)
        self._attr_is_on: bool | None = None
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

        value = overview.get(sensor_key)
        if value is None:
            self._attr_is_on = None
            self._attr_extra_state_attributes = {}
            self.async_write_ha_state()
            return

        # get target range
        target_range = get_target_range(sensor_key, self._target_profile, pool)
        if not target_range:
            self._attr_is_on = None
            self._attr_extra_state_attributes = {'current_value': value}
            self.async_write_ha_state()
            return

        target_min = target_range.get(ATTR_TARGET_MIN)
        target_max = target_range.get(ATTR_TARGET_MAX)

        if target_min is None or target_max is None:
            self._attr_is_on = None
            self._attr_extra_state_attributes = {'current_value': value}
            self.async_write_ha_state()
            return

        # is_on = True means there's a problem (out of range)
        in_range = target_min <= value <= target_max
        self._attr_is_on = not in_range

        # calculate deviation from range
        deviation = 0.0
        if value < target_min:
            deviation = target_min - value
        elif value > target_max:
            deviation = value - target_max

        self._attr_extra_state_attributes = {
            'current_value': value,
            ATTR_TARGET_MIN: target_min,
            ATTR_TARGET_MAX: target_max,
            'deviation': round(deviation, 2),
        }

        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.data.json is not None
        )
