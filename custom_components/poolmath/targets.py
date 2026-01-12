"""Target sensor definitions and chemistry target ranges."""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any, Final

from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)

from .const import (
    ATTR_DESCRIPTION,
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ICON_GAUGE,
)

LOG = logging.getLogger(__name__)


class SensorType(StrEnum):
    """Pool Math sensor types."""

    COMBINED_CHLORINE = 'cc'
    FREE_CHLORINE = 'fc'
    PH = 'ph'
    TOTAL_ALKALINITY = 'ta'
    CALCIUM_HARDNESS = 'ch'
    CYANURIC_ACID = 'cya'
    SALT = 'salt'
    BORATE = 'bor'
    BORATE_ALT = 'borate'
    CSI = 'csi'
    TEMPERATURE = 'temp'
    WATER_TEMPERATURE = 'waterTemp'
    SWG_CELL_PERCENTAGE = 'swgCellPercentage'
    TOTAL_CHLORINE = 'tc'
    PRESSURE = 'pressure'
    FLOW_RATE = 'flowRate'


class TargetType(StrEnum):
    """Pool Math target types."""

    TFP = 'tfp'


class Units:
    """Measurement units."""

    MG_PER_L: Final = 'mg/L'
    PPM: Final = 'ppm'
    PH: Final = 'pH'
    CSI: Final = 'CSI'
    PERCENT: Final = '%'
    GPM: Final = 'gpm'
    PSI: Final = 'psi'


POOL_MATH_SENSOR_SETTINGS: dict[str, dict[str, Any]] = {
    SensorType.COMBINED_CHLORINE: {
        ATTR_NAME: 'CC',
        ATTR_UNIT_OF_MEASUREMENT: Units.MG_PER_L,
        ATTR_DESCRIPTION: 'Combined Chlorine',
        ATTR_ICON: ICON_GAUGE,
    },
    SensorType.FREE_CHLORINE: {
        ATTR_NAME: 'FC',
        ATTR_UNIT_OF_MEASUREMENT: Units.MG_PER_L,
        ATTR_DESCRIPTION: 'Free Chlorine',
        ATTR_ICON: ICON_GAUGE,
    },
    'ph': {
        ATTR_NAME: 'pH',
        ATTR_UNIT_OF_MEASUREMENT: 'pH',
        ATTR_DESCRIPTION: 'Acidity/Basicity',
        ATTR_ICON: ICON_GAUGE,
    },
    'ta': {
        ATTR_NAME: 'TA',
        ATTR_UNIT_OF_MEASUREMENT: 'ppm',
        ATTR_DESCRIPTION: 'Total Alkalinity',
        ATTR_ICON: ICON_GAUGE,
    },
    'ch': {
        ATTR_NAME: 'CH',
        ATTR_UNIT_OF_MEASUREMENT: 'ppm',
        ATTR_DESCRIPTION: 'Calcium Hardness',
        ATTR_ICON: ICON_GAUGE,
    },
    'cya': {
        ATTR_NAME: 'CYA',
        ATTR_UNIT_OF_MEASUREMENT: 'ppm',
        ATTR_DESCRIPTION: 'Cyanuric Acid',
        ATTR_ICON: ICON_GAUGE,
    },
    'salt': {
        ATTR_NAME: 'Salt',
        ATTR_UNIT_OF_MEASUREMENT: 'ppm',
        ATTR_DESCRIPTION: 'Salt',
        ATTR_ICON: ICON_GAUGE,
    },
    'bor': {
        ATTR_NAME: 'Borate',
        ATTR_UNIT_OF_MEASUREMENT: 'ppm',
        ATTR_DESCRIPTION: 'Borate',
        ATTR_ICON: ICON_GAUGE,
    },
    'borate': {
        ATTR_NAME: 'Borate',
        ATTR_UNIT_OF_MEASUREMENT: 'ppm',
        ATTR_DESCRIPTION: 'Borate',
        ATTR_ICON: ICON_GAUGE,
    },
    'csi': {
        ATTR_NAME: 'CSI',
        ATTR_UNIT_OF_MEASUREMENT: 'CSI',
        ATTR_DESCRIPTION: 'Calcite Saturation Index',
        ATTR_ICON: ICON_GAUGE,
    },
    'temp': {
        ATTR_NAME: 'Temp',
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        ATTR_DESCRIPTION: 'Temperature',
        ATTR_ICON: 'mdi:coolant-temperature',
    },
    'waterTemp': {
        ATTR_NAME: 'Temp',
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        ATTR_DESCRIPTION: 'Temperature',
        ATTR_ICON: 'mdi:coolant-temperature',
    },
    'swgCellPercentage': {
        ATTR_NAME: 'SWG Cell',
        ATTR_UNIT_OF_MEASUREMENT: '%',
        ATTR_DESCRIPTION: 'SWG Cell Percentage',
        ATTR_ICON: 'mdi:battery-charging',
    },
    'tc': {
        ATTR_NAME: 'TC',
        ATTR_UNIT_OF_MEASUREMENT: 'mg/L',
        ATTR_DESCRIPTION: 'Total Chlorine (FC + CC)',
        ATTR_ICON: ICON_GAUGE,
    },
    'pressure': {
        ATTR_NAME: 'Pressure',
        ATTR_UNIT_OF_MEASUREMENT: 'psi',
        ATTR_DESCRIPTION: 'Filter Pressure',
        ATTR_ICON: 'mdi:gauge',
    },
    'flowRate': {
        ATTR_NAME: 'Flow Rate',
        ATTR_UNIT_OF_MEASUREMENT: 'gpm',
        ATTR_DESCRIPTION: 'Flow Rate',
        ATTR_ICON: 'mdi:water-pump',
    },
}

TFP_TARGET_NAME: Final = 'tfp'

# TFP recommended target levels for pool chemistry
# Source: https://www.troublefreepool.com/blog/pool-school/
TFP_RECOMMENDED_TARGET_LEVELS: dict[str, dict[str, float]] = {
    'fc': {ATTR_TARGET_MIN: 2.0, ATTR_TARGET_MAX: 6.0},  # varies with CYA
    'cc': {ATTR_TARGET_MIN: 0.0, ATTR_TARGET_MAX: 0.5},
    'ph': {ATTR_TARGET_MIN: 7.2, ATTR_TARGET_MAX: 7.8, 'target': 7.4},
    'ta': {ATTR_TARGET_MIN: 50.0, ATTR_TARGET_MAX: 90.0, 'target': 70.0},
    'ch': {ATTR_TARGET_MIN: 250.0, ATTR_TARGET_MAX: 450.0, 'target': 350.0},
    'cya': {ATTR_TARGET_MIN: 30.0, ATTR_TARGET_MAX: 50.0, 'target': 40.0},
    'salt': {ATTR_TARGET_MIN: 3000.0, ATTR_TARGET_MAX: 3500.0, 'target': 3200.0},
    'bor': {ATTR_TARGET_MIN: 30.0, ATTR_TARGET_MAX: 50.0, 'target': 50.0},
    'borate': {ATTR_TARGET_MIN: 30.0, ATTR_TARGET_MAX: 50.0, 'target': 50.0},
    'csi': {ATTR_TARGET_MIN: -0.3, ATTR_TARGET_MAX: 0.3, 'target': 0.0},
}

# sensors that have meaningful target ranges for binary problem sensors
CHEMISTRY_SENSORS_WITH_TARGETS: Final[list[str]] = [
    'fc',
    'cc',
    'ph',
    'ta',
    'ch',
    'cya',
    'salt',
    'bor',
    'borate',
    'csi',
]

DEFAULT_TARGETS: Final = TFP_TARGET_NAME


def get_sensor_targets(
    target_name: str = DEFAULT_TARGETS,
) -> dict[str, dict[str, float]] | None:
    """Get sensor targets for the specified target profile.

    Args:
        target_name: Target profile name (currently only 'tfp' is supported)

    Returns:
        Dictionary of sensor targets or None if unsupported
    """
    if target_name == TFP_TARGET_NAME:
        return TFP_RECOMMENDED_TARGET_LEVELS

    LOG.error(
        "Only '%s' targets currently supported, ignoring '%s'",
        TFP_TARGET_NAME,
        target_name,
    )
    return None


def get_target_range(
    sensor_key: str,
    target_profile: str = DEFAULT_TARGETS,
    api_data: dict[str, Any] | None = None,
) -> dict[str, float] | None:
    """Get target range for a specific sensor.

    Checks API data first for pool-specific targets, falls back to profile targets.

    Args:
        sensor_key: Sensor key (e.g., 'ph', 'fc')
        target_profile: Target profile name (default 'tfp')
        api_data: Optional API response data containing pool-specific targets

    Returns:
        Dictionary with 'target_min', 'target_max', and optionally 'target' keys,
        or None if no targets defined for this sensor
    """
    result: dict[str, float] = {}

    # check API data for pool-specific targets
    if api_data:
        api_min = api_data.get(f'{sensor_key}Min')
        api_max = api_data.get(f'{sensor_key}Max')
        api_target = api_data.get(f'{sensor_key}Target')

        if api_min is not None:
            result[ATTR_TARGET_MIN] = float(api_min)
        if api_max is not None:
            result[ATTR_TARGET_MAX] = float(api_max)
        if api_target is not None:
            result['target'] = float(api_target)

    # fall back to profile targets if API data missing
    profile_targets = get_sensor_targets(target_profile)
    if profile_targets and sensor_key in profile_targets:
        sensor_targets = profile_targets[sensor_key]
        if ATTR_TARGET_MIN not in result and ATTR_TARGET_MIN in sensor_targets:
            result[ATTR_TARGET_MIN] = sensor_targets[ATTR_TARGET_MIN]
        if ATTR_TARGET_MAX not in result and ATTR_TARGET_MAX in sensor_targets:
            result[ATTR_TARGET_MAX] = sensor_targets[ATTR_TARGET_MAX]
        if 'target' not in result and 'target' in sensor_targets:
            result['target'] = sensor_targets['target']

    return result if result else None
