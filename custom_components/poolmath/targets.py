"""Target sensor definitions and chemistry target ranges."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

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


class SensorType(str, Enum):
    """Pool Math sensor types."""
    COMBINED_CHLORINE = 'cc'
    FREE_CHLORINE = 'fc'
    PH = 'ph'
    TOTAL_ALKALINITY = 'ta'
    CALCIUM_HARDNESS = 'ch'
    CYANURIC_ACID = 'cya'
    SALT = 'salt'
    BORATE = 'bor'
    BORATE_ALT = 'borate'  # Alternative name
    CSI = 'csi'
    TEMPERATURE = 'temp'
    WATER_TEMPERATURE = 'waterTemp'
    SWG_CELL_PERCENTAGE = 'swgCellPercentage'
    TOTAL_CHLORINE = 'tc'  # Calculated
    PRESSURE = 'pressure'
    FLOW_RATE = 'flowRate'


class TargetType(str, Enum):
    """Pool Math target types."""
    TFP = 'tfp'


class Units:
    """Measurement units."""
    MG_PER_L = 'mg/L'
    PPM = 'ppm'
    PH = 'pH'
    CSI = 'CSI'
    PERCENT = '%'
    GPM = 'gpm'
    PSI = 'psi'


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

TFP_TARGET_NAME = 'tfp'

TFP_RECOMMENDED_TARGET_LEVELS: dict[str, dict[str, float]] = {
    'cc': {ATTR_TARGET_MIN: 0, ATTR_TARGET_MAX: 0.1},
    'ph': {ATTR_TARGET_MIN: 7.2, ATTR_TARGET_MAX: 7.8, 'target': 7.4},
    'ta': {ATTR_TARGET_MIN: 50, ATTR_TARGET_MAX: 90},
    'salt': {ATTR_TARGET_MIN: 3000, ATTR_TARGET_MAX: 3200, 'target': 3100},
}

DEFAULT_TARGETS = TFP_TARGET_NAME


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
        f"Only '{TFP_TARGET_NAME}' targets currently supported, ignoring "
        f"'{target_name}'"
    )
    return None
