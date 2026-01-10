"""Tests for Pool Math diagnostics."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.poolmath.const import DOMAIN
from custom_components.poolmath.diagnostics import async_get_config_entry_diagnostics
from custom_components.poolmath.models import PoolMathState


@pytest.fixture
def mock_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = 'test_entry_id'
    entry.version = 1
    entry.domain = DOMAIN
    entry.title = 'Pool Math'
    entry.data = {
        'user_id': 'sensitive-user-id',
        'pool_id': 'sensitive-pool-id',
        'name': 'My Pool',
    }
    entry.options = {
        'user_id': 'sensitive-user-id',
        'pool_id': 'sensitive-pool-id',
        'scan_interval': 8,
    }
    return entry


@pytest.fixture
def mock_coordinator(mock_pool_data: dict[str, Any]) -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.last_exception = None
    coordinator.update_interval = '0:08:00'
    coordinator.data = PoolMathState(json=mock_pool_data)
    return coordinator


async def test_diagnostics_redacts_sensitive_data(
    hass: HomeAssistant,
    mock_entry: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Test that diagnostics redacts sensitive data."""
    hass.data[DOMAIN] = {
        mock_entry.entry_id: {
            'coordinator': mock_coordinator,
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    # check that sensitive data is redacted
    assert diagnostics['entry']['data']['user_id'] == '**REDACTED**'
    assert diagnostics['entry']['data']['pool_id'] == '**REDACTED**'
    assert diagnostics['entry']['options']['user_id'] == '**REDACTED**'
    assert diagnostics['entry']['options']['pool_id'] == '**REDACTED**'


async def test_diagnostics_includes_coordinator_state(
    hass: HomeAssistant,
    mock_entry: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Test that diagnostics includes coordinator state."""
    hass.data[DOMAIN] = {
        mock_entry.entry_id: {
            'coordinator': mock_coordinator,
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    assert diagnostics['coordinator']['last_update_success'] is True
    assert diagnostics['coordinator']['last_exception'] is None
    assert diagnostics['coordinator']['update_interval'] is not None


async def test_diagnostics_handles_no_coordinator_data(
    hass: HomeAssistant,
    mock_entry: MagicMock,
) -> None:
    """Test diagnostics when coordinator has no data."""
    coordinator = MagicMock()
    coordinator.last_update_success = False
    coordinator.last_exception = Exception('Connection failed')
    coordinator.update_interval = '0:08:00'
    coordinator.data = None

    hass.data[DOMAIN] = {
        mock_entry.entry_id: {
            'coordinator': coordinator,
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    assert diagnostics['coordinator']['data'] is None
    assert 'Connection failed' in diagnostics['coordinator']['last_exception']


async def test_diagnostics_redacts_pool_data(
    hass: HomeAssistant,
    mock_entry: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Test that pool data is redacted in diagnostics."""
    hass.data[DOMAIN] = {
        mock_entry.entry_id: {
            'coordinator': mock_coordinator,
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    # pool data should be redacted
    coordinator_data = diagnostics['coordinator']['data']
    assert coordinator_data is not None

    # navigate to pool and check redaction
    pool = coordinator_data['pools'][0]['pool']
    assert pool['userId'] == '**REDACTED**'
    assert pool['id'] == '**REDACTED**'
    assert pool['name'] == '**REDACTED**'
