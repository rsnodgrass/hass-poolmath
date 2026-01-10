"""Tests for Pool Math coordinator."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.poolmath.client import (
    PoolMathClient,
    PoolMathConnectionError,
    PoolMathTimeoutError,
)
from custom_components.poolmath.coordinator import PoolMathUpdateCoordinator
from custom_components.poolmath.models import PoolMathConfig


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock Pool Math client."""
    client = MagicMock(spec=PoolMathClient)
    client.async_get_json = AsyncMock()
    return client


@pytest.fixture
def mock_config() -> PoolMathConfig:
    """Create a mock Pool Math config."""
    return PoolMathConfig(
        user_id='test-user-id',
        pool_id='test-pool-id',
        name='Test Pool',
        timeout=15.0,
        target='tfp',
        update_interval=timedelta(minutes=8),
    )


async def test_coordinator_update_success(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config: PoolMathConfig,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test successful data update."""
    mock_client.async_get_json.return_value = mock_pool_data

    coordinator = PoolMathUpdateCoordinator(hass, mock_client, mock_config)
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data is not None
    assert coordinator.data.json == mock_pool_data


async def test_coordinator_update_timeout(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config: PoolMathConfig,
) -> None:
    """Test coordinator handles timeout errors."""
    mock_client.async_get_json.side_effect = PoolMathTimeoutError('Timeout')

    coordinator = PoolMathUpdateCoordinator(hass, mock_client, mock_config)

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator.async_refresh()

    assert 'Timeout' in str(exc_info.value)


async def test_coordinator_update_connection_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config: PoolMathConfig,
) -> None:
    """Test coordinator handles connection errors."""
    mock_client.async_get_json.side_effect = PoolMathConnectionError('Connection failed')

    coordinator = PoolMathUpdateCoordinator(hass, mock_client, mock_config)

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator.async_refresh()

    assert 'Connection' in str(exc_info.value)


async def test_coordinator_update_unexpected_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config: PoolMathConfig,
) -> None:
    """Test coordinator handles unexpected errors."""
    mock_client.async_get_json.side_effect = ValueError('Unexpected error')

    coordinator = PoolMathUpdateCoordinator(hass, mock_client, mock_config)

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator.async_refresh()

    assert 'Unexpected' in str(exc_info.value)


async def test_coordinator_extracts_last_updated(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config: PoolMathConfig,
) -> None:
    """Test coordinator extracts last_updated from response."""
    pool_data = {
        'last_updated': '2024-01-01T12:00:00Z',
        'pools': [
            {
                'pool': {
                    'id': 'test-pool-id',
                    'userId': 'test-user-id',
                    'name': 'Test Pool',
                    'overview': {'fc': 5.0},
                }
            }
        ],
    }
    mock_client.async_get_json.return_value = pool_data

    coordinator = PoolMathUpdateCoordinator(hass, mock_client, mock_config)
    await coordinator.async_refresh()

    assert coordinator.data.last_updated == '2024-01-01T12:00:00Z'
