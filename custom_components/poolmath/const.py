"""Constants for Pool Math."""

from typing import Final

INTEGRATION_NAME: Final = 'Pool Math'
DOMAIN: Final = 'poolmath'

ATTRIBUTION: Final = 'Data from Pool Math (Trouble Free Pool)'

SHARE_URL_PATTERN: Final = (
    r'https://(?:api\.poolmathapp\.com|troublefreepool\.com)/'
    r'(?:share/|mypool/)([a-zA-Z0-9-]+)'
)

ATTR_DESCRIPTION: Final = 'description'
ATTR_IN_RANGE: Final = 'in_range'
ATTR_LAST_LOGGED: Final = 'last_logged'
ATTR_LAST_UPDATED: Final = 'last_updated'
ATTR_NAME: Final = 'name'
ATTR_TARGET: Final = 'target'
ATTR_TARGET_MAX: Final = 'target_max'
ATTR_TARGET_MIN: Final = 'target_min'
ATTR_TARGET_SOURCE: Final = 'target_source'

# events fired when chemistry values go out of or back in range
EVENT_CHEMISTRY_OUT_OF_RANGE: Final = 'poolmath_chemistry_out_of_range'
EVENT_CHEMISTRY_IN_RANGE: Final = 'poolmath_chemistry_in_range'

CONF_USER_ID: Final = 'user_id'
CONF_POOL_ID: Final = 'pool_id'
CONF_SHARE_ID: Final = 'share_id'  # deprecated configuration key
CONF_SHARE_URL: Final = 'share_url'
CONF_TARGET: Final = 'target'
CONF_TIMEOUT: Final = 'timeout'

DEFAULT_NAME: Final = 'Pool'
DEFAULT_TIMEOUT: Final = 15.0
DEFAULT_TARGET: Final = 'tfp'
DEFAULT_UPDATE_INTERVAL: Final = 8
ICON_GAUGE: Final = 'mdi:gauge'
ICON_POOL: Final = 'mdi:pool'
