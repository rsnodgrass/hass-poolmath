import logging

from homeassistant.const import (
    ATTR_ICON,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature
)

from .const import (
    ATTR_DESCRIPTION,
    ATTR_TARGET_MAX,
    ATTR_TARGET_MIN,
    ATTR_TARGET_SOURCE,
    CONF_TARGET,
    ICON_GAUGE,
)

LOG = logging.getLogger(__name__)

# FIXME: add strings translation support for names/descriptiongs/units?
# see https://www.troublefreepool.com/blog/2018/12/12/abcs-of-pool-water-chemistry/
POOL_MATH_SENSOR_SETTINGS = {
    'cc': {
        ATTR_NAME: 'CC',
        ATTR_UNIT_OF_MEASUREMENT: 'mg/L',
        ATTR_DESCRIPTION: 'Combined Chlorine',
        ATTR_ICON: ICON_GAUGE,
    },
    'fc': {
        ATTR_NAME: 'FC',
        ATTR_UNIT_OF_MEASUREMENT: 'mg/L',
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
        ATTR_ICON: 'mdi:coolant-temperature',
    },
    'tc': {
        ATTR_NAME: 'TC',
        ATTR_UNIT_OF_MEASUREMENT: 'mg/L',
        ATTR_DESCRIPTION: 'Total Chlorine (FC + CC)',
        ATTR_ICON: ICON_GAUGE,
    },
    'pressure': {
        ATTR_NAME: 'Pressure',
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        ATTR_DESCRIPTION: 'Filter Pressure',
        ATTR_ICON: 'mdi:coolant-temperature',
    },
    'flowRate': {
        ATTR_NAME: 'Flow Rate',
        ATTR_UNIT_OF_MEASUREMENT: 'gpm',  # FIXME: confirm units
        ATTR_DESCRIPTION: 'Flow Rate',
        ATTR_ICON: 'mdi:coolant-temperature',
    },
}

# FIXME: targets should be profiles that users can select from based on the needs
# for a specific body of water (pool, salt pool, spa, hot tub, pond, etc)

TFP_TARGET_NAME = 'tfp'

# FIXME: targets should probably all be in code, since some values are computed based on other values
TFP_RECOMMENDED_TARGET_LEVELS = {
    'cc': {ATTR_TARGET_MIN: 0, ATTR_TARGET_MAX: 0.1},
    'ph': {ATTR_TARGET_MIN: 7.2, ATTR_TARGET_MAX: 7.8, 'target': 7.4},
    'ta': {ATTR_TARGET_MIN: 50, ATTR_TARGET_MAX: 90},
    #    'ch':     { ATTR_TARGET_MIN: 250,  ATTR_TARGET_MAX: 650  }, # with salt: 350-450 ppm
    #    'cya':    { ATTR_TARGET_MIN: 30,   ATTR_TARGET_MAX: 50   }, # with salt: 70-80 ppm
    'salt': {ATTR_TARGET_MIN: 3000, ATTR_TARGET_MAX: 3200, 'target': 3100},
}

DEFAULT_TARGETS = TFP_TARGET_NAME


def get_pool_targets(target_name=DEFAULT_TARGETS):
    if target_name == TFP_TARGET_NAME:
        return TFP_RECOMMENDED_TARGET_LEVELS
    else:
        LOG.error(
            f"Only '{TFP_TARGET_NAME}' targets currently supported, ignoring '{target_name}'."
        )
        return None
