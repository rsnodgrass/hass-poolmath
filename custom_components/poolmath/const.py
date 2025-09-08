"""Constants for Pool Math."""

INTEGRATION_NAME = 'Pool Math'
DOMAIN = 'poolmath'

ATTRIBUTION = 'Data from Pool Math (Trouble Free Pool)'

SHARE_URL_PATTERN = r'https://(?:api\.poolmathapp\.com|troublefreepool\.com)/(?:share/|mypool/)([a-zA-Z0-9]+)'

ATTR_DESCRIPTION = 'description'
ATTR_LAST_UPDATED = 'last_updated'
ATTR_NAME = 'name'
ATTR_TARGET_MIN = 'target_min'
ATTR_TARGET_MAX = 'target_max'
ATTR_TARGET_SOURCE = 'target_source'

CONF_USER_ID = 'user_id'
CONF_POOL_ID = 'pool_id'
CONF_SHARE_ID = 'share_id'  # Old configuration key
CONF_SHARE_URL = 'share_url'  # Share URL for simple setup
CONF_TARGET = 'target'
CONF_TIMEOUT = 'timeout'

DEFAULT_NAME = 'Pool'
DEFAULT_TIMEOUT = 15.0
DEFAULT_TARGET = 'tfp'
DEFAULT_UPDATE_INTERVAL = 8
ICON_GAUGE = 'mdi:gauge'
ICON_POOL = 'mdi:pool'
