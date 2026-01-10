"""Tests for Pool Math sensor platform."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.poolmath.client import parse_pool
from custom_components.poolmath.models import PoolMathConfig, PoolMathState
from custom_components.poolmath.sensor import (
    SENSOR_DESCRIPTIONS,
    PoolMathSensor,
    get_device_info,
)


@pytest.fixture
def mock_config() -> PoolMathConfig:
    """Create a mock Pool Math config."""
    return PoolMathConfig(
        user_id='test-user-id',
        pool_id='test-pool-id',
        name='Test Pool',
        timeout=15.0,
        target='tfp',
    )


def test_parse_pool_valid_data(mock_pool_data: dict[str, Any]) -> None:
    """Test parsing valid pool data."""
    pool = parse_pool(mock_pool_data)

    assert pool is not None
    assert pool['id'] == 'test-pool-id'
    assert pool['userId'] == 'test-user-id'
    assert pool['overview']['fc'] == 5.0
    assert pool['overview']['ph'] == 7.4


def test_parse_pool_empty_data() -> None:
    """Test parsing empty pool data."""
    assert parse_pool({}) is None
    assert parse_pool({'pools': []}) is None
    assert parse_pool({'pools': [{}]}) is None


def test_parse_pool_invalid_structure() -> None:
    """Test parsing invalid pool data structure."""
    assert parse_pool({'pools': 'invalid'}) is None
    assert parse_pool({'pools': [None]}) is None
    assert parse_pool({'other': 'data'}) is None


def test_get_device_info(mock_config: PoolMathConfig) -> None:
    """Test device info generation."""
    device_info = get_device_info(mock_config)

    assert device_info['identifiers'] == {('poolmath', 'test-pool-id')}
    assert device_info['manufacturer'] == 'Trouble Free Pool'
    assert device_info['model'] == 'Pool Math'
    assert device_info['name'] == 'Test Pool'
    assert 'test-user-id' in device_info['configuration_url']
    assert 'test-pool-id' in device_info['configuration_url']


def test_get_device_info_with_pool_data(mock_config: PoolMathConfig) -> None:
    """Test device info uses pool data name when available."""
    pool_data = {'name': 'Custom Pool Name'}
    device_info = get_device_info(mock_config, pool_data)

    assert device_info['name'] == 'Custom Pool Name'


def test_sensor_descriptions_exist() -> None:
    """Test that all expected sensor descriptions exist."""
    expected_sensors = [
        'fc', 'cc', 'tc', 'ph', 'ta', 'ch', 'cya',
        'salt', 'bor', 'borate', 'csi',
        'temp', 'waterTemp', 'pressure', 'flowRate', 'swgCellPercent',
    ]

    for sensor_key in expected_sensors:
        assert sensor_key in SENSOR_DESCRIPTIONS, f'Missing sensor: {sensor_key}'


def test_sensor_descriptions_have_required_fields() -> None:
    """Test that all sensor descriptions have required fields."""
    for key, description in SENSOR_DESCRIPTIONS.items():
        assert description.key == key
        assert description.translation_key is not None
        assert description.native_unit_of_measurement is not None


def test_sensor_unique_id(mock_config: PoolMathConfig) -> None:
    """Test sensor unique_id format."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None

    sensor = PoolMathSensor(
        coordinator=mock_coordinator,
        config=mock_config,
        description=SENSOR_DESCRIPTIONS['fc'],
    )

    assert sensor.unique_id == 'poolmath_test-pool-id_fc'


def test_sensor_has_entity_name(mock_config: PoolMathConfig) -> None:
    """Test sensor has_entity_name is True for modern entity naming."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None

    sensor = PoolMathSensor(
        coordinator=mock_coordinator,
        config=mock_config,
        description=SENSOR_DESCRIPTIONS['fc'],
    )

    assert sensor.has_entity_name is True


def test_sensor_attribution(mock_config: PoolMathConfig) -> None:
    """Test sensor attribution."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None

    sensor = PoolMathSensor(
        coordinator=mock_coordinator,
        config=mock_config,
        description=SENSOR_DESCRIPTIONS['fc'],
    )

    assert 'Pool Math' in sensor.attribution


def test_total_chlorine_calculation(
    mock_config: PoolMathConfig, mock_pool_data: dict[str, Any]
) -> None:
    """Test that total chlorine is calculated correctly."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = PoolMathState(json=mock_pool_data)
    mock_coordinator.last_update_success = True

    sensor = PoolMathSensor(
        coordinator=mock_coordinator,
        config=mock_config,
        description=SENSOR_DESCRIPTIONS['tc'],
        calculated=True,
    )

    # trigger update
    sensor._handle_coordinator_update()

    # FC=5.0, CC=0.5, TC should be 5.5
    assert sensor.native_value == 5.5
    assert sensor.extra_state_attributes.get('calculated') is True
    assert sensor.extra_state_attributes.get('fc') == 5.0
    assert sensor.extra_state_attributes.get('cc') == 0.5


def test_sensor_availability(
    mock_config: PoolMathConfig, mock_pool_data: dict[str, Any]
) -> None:
    """Test sensor availability."""
    mock_coordinator = MagicMock()
    mock_coordinator.last_update_success = True
    mock_coordinator.data = PoolMathState(json=mock_pool_data)

    sensor = PoolMathSensor(
        coordinator=mock_coordinator,
        config=mock_config,
        description=SENSOR_DESCRIPTIONS['fc'],
    )

    assert sensor.available is True

    # test unavailable when update fails
    mock_coordinator.last_update_success = False
    assert sensor.available is False

    # test unavailable when no data
    mock_coordinator.last_update_success = True
    mock_coordinator.data = None
    assert sensor.available is False
