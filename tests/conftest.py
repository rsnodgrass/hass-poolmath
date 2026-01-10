"""Fixtures for Pool Math tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from custom_components.poolmath.const import (
    CONF_POOL_ID,
    CONF_TARGET,
    CONF_USER_ID,
    DEFAULT_NAME,
    DEFAULT_TARGET,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title='Pool Math',
        data={
            CONF_USER_ID: 'test-user-id',
            CONF_POOL_ID: 'test-pool-id',
            CONF_NAME: DEFAULT_NAME,
            CONF_TARGET: DEFAULT_TARGET,
            CONF_SCAN_INTERVAL: DEFAULT_UPDATE_INTERVAL,
        },
        source='user',
        entry_id='test_entry_id',
        unique_id='test-user-id-test-pool-id',
    )


@pytest.fixture
def mock_pool_data() -> dict[str, Any]:
    """Create mock pool data response."""
    return {
        'pools': [
            {
                'pool': {
                    'id': 'test-pool-id',
                    'userId': 'test-user-id',
                    'name': 'Test Pool',
                    'trackSalt': True,
                    'trackBor': False,
                    'trackCC': True,
                    'trackCSI': True,
                    'overview': {
                        'fc': 5.0,
                        'fcTs': 1704067200,
                        'cc': 0.5,
                        'ccTs': 1704067200,
                        'ph': 7.4,
                        'phTs': 1704067200,
                        'ta': 80,
                        'taTs': 1704067200,
                        'ch': 350,
                        'chTs': 1704067200,
                        'cya': 40,
                        'cyaTs': 1704067200,
                        'salt': 3200,
                        'saltTs': 1704067200,
                        'csi': -0.2,
                        'csiTs': 1704067200,
                        'waterTemp': 82,
                        'waterTempTs': 1704067200,
                    },
                }
            }
        ]
    }


@pytest.fixture
def mock_pool_data_minimal() -> dict[str, Any]:
    """Create minimal mock pool data response."""
    return {
        'pools': [
            {
                'pool': {
                    'id': 'test-pool-id',
                    'userId': 'test-user-id',
                    'name': 'Test Pool',
                    'trackSalt': False,
                    'trackBor': False,
                    'trackCC': False,
                    'trackCSI': False,
                    'overview': {
                        'fc': 5.0,
                        'fcTs': 1704067200,
                        'ph': 7.4,
                        'phTs': 1704067200,
                    },
                }
            }
        ]
    }


@pytest.fixture
def mock_aiohttp_session() -> Generator[MagicMock, None, None]:
    """Mock aiohttp ClientSession."""
    with patch('aiohttp.ClientSession') as mock_session:
        session_instance = MagicMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=session_instance)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock_session


@pytest.fixture
def hass(hass: HomeAssistant) -> HomeAssistant:
    """Return Home Assistant instance."""
    return hass
