"""Tests for entity ID stability to prevent breaking changes.

=============================================================================
                         ENTITY ID STABILITY TESTS
=============================================================================

These tests verify that unique_id generation remains stable across updates.
Changing unique_id formats is a BREAKING CHANGE that will:

    1. Create duplicate entities in Home Assistant
    2. Break user automations, scripts, and dashboards
    3. Lose historical data and statistics
    4. Require manual cleanup by users

=============================================================================
                           GOLDEN FORMATS
=============================================================================

SENSORS:
    Format: poolmath_{user_id}_{pool_id}_{sensor_key}
    Example: poolmath_abc123_pool456_fc

BINARY SENSORS (problem indicators):
    Format: poolmath_{user_id}_{pool_id}_{sensor_key}_problem
    Example: poolmath_abc123_pool456_ph_problem

DEVICE IDENTIFIER:
    Format: (DOMAIN, '{user_id}_{pool_id}')
    Example: ('poolmath', 'abc123_pool456')

=============================================================================
                           MIGRATION NOTES
=============================================================================

Historical format changes:
    v1 (legacy): poolmath_{pool_id}_{sensor_key}
    v2 (current): poolmath_{user_id}_{pool_id}_{sensor_key}

Migration code in sensor.py and binary_sensor.py handles v1 -> v2 migration.
If you need to change the format again, you MUST add migration logic.

=============================================================================
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.poolmath.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    PoolMathProblemSensor,
)
from custom_components.poolmath.const import DOMAIN
from custom_components.poolmath.models import PoolMathConfig
from custom_components.poolmath.sensor import (
    SENSOR_DESCRIPTIONS,
    PoolMathSensor,
    get_device_info,
)


# =============================================================================
# Unique ID Generation Functions (must match actual entity code)
# =============================================================================


def generate_sensor_unique_id(user_id: str, pool_id: str, sensor_key: str) -> str:
    """Generate unique_id for a sensor entity.

    This function must produce the exact same format as PoolMathSensor.__init__
    in custom_components/poolmath/sensor.py (line ~309-311).

    Format: poolmath_{user_id}_{pool_id}_{sensor_key}
    """
    return f'poolmath_{user_id}_{pool_id}_{sensor_key}'


def generate_binary_sensor_unique_id(
    user_id: str, pool_id: str, sensor_key: str
) -> str:
    """Generate unique_id for a binary sensor (problem indicator) entity.

    This function must produce the exact same format as PoolMathProblemSensor.__init__
    in custom_components/poolmath/binary_sensor.py (line ~212-214).

    Format: poolmath_{user_id}_{pool_id}_{sensor_key}_problem
    """
    return f'poolmath_{user_id}_{pool_id}_{sensor_key}_problem'


def generate_device_identifier(user_id: str, pool_id: str) -> tuple[str, str]:
    """Generate device identifier tuple.

    This function must produce the exact same format as get_device_info()
    in custom_components/poolmath/sensor.py (line ~279).

    Format: (DOMAIN, '{user_id}_{pool_id}')
    """
    return (DOMAIN, f'{user_id}_{pool_id}')


def generate_legacy_sensor_unique_id(pool_id: str, sensor_key: str) -> str:
    """Generate legacy v1 unique_id format (for migration testing).

    Format: poolmath_{pool_id}_{sensor_key}
    """
    return f'poolmath_{pool_id}_{sensor_key}'


def generate_legacy_binary_sensor_unique_id(pool_id: str, sensor_key: str) -> str:
    """Generate legacy v1 binary sensor unique_id format (for migration testing).

    Format: poolmath_{pool_id}_{sensor_key}_problem
    """
    return f'poolmath_{pool_id}_{sensor_key}_problem'


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_config() -> PoolMathConfig:
    """Create a sample Pool Math config for testing."""
    return PoolMathConfig(
        user_id='user-abc123',
        pool_id='pool-xyz789',
        name='Test Pool',
        timeout=15.0,
        target='tfp',
    )


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.data = None
    return coordinator


# =============================================================================
# Parametrized Sensor Unique ID Tests
# =============================================================================


@pytest.mark.parametrize(
    'user_id,pool_id,sensor_key,expected_unique_id',
    [
        # standard alphanumeric IDs
        ('user123', 'pool456', 'fc', 'poolmath_user123_pool456_fc'),
        ('user123', 'pool456', 'ph', 'poolmath_user123_pool456_ph'),
        ('user123', 'pool456', 'ta', 'poolmath_user123_pool456_ta'),
        # IDs with hyphens (common format)
        (
            'abc-def-123',
            'xyz-789-pool',
            'cya',
            'poolmath_abc-def-123_xyz-789-pool_cya',
        ),
        # UUIDs as IDs
        (
            '550e8400-e29b-41d4-a716-446655440000',
            'f47ac10b-58cc-4372-a567-0e02b2c3d479',
            'salt',
            'poolmath_550e8400-e29b-41d4-a716-446655440000_f47ac10b-58cc-4372-a567-0e02b2c3d479_salt',
        ),
        # all sensor keys
        ('u', 'p', 'fc', 'poolmath_u_p_fc'),
        ('u', 'p', 'cc', 'poolmath_u_p_cc'),
        ('u', 'p', 'tc', 'poolmath_u_p_tc'),
        ('u', 'p', 'ph', 'poolmath_u_p_ph'),
        ('u', 'p', 'ta', 'poolmath_u_p_ta'),
        ('u', 'p', 'ch', 'poolmath_u_p_ch'),
        ('u', 'p', 'cya', 'poolmath_u_p_cya'),
        ('u', 'p', 'salt', 'poolmath_u_p_salt'),
        ('u', 'p', 'bor', 'poolmath_u_p_bor'),
        ('u', 'p', 'borate', 'poolmath_u_p_borate'),
        ('u', 'p', 'csi', 'poolmath_u_p_csi'),
        ('u', 'p', 'temp', 'poolmath_u_p_temp'),
        ('u', 'p', 'waterTemp', 'poolmath_u_p_waterTemp'),
        ('u', 'p', 'pressure', 'poolmath_u_p_pressure'),
        ('u', 'p', 'flowRate', 'poolmath_u_p_flowRate'),
        ('u', 'p', 'swgCellPercent', 'poolmath_u_p_swgCellPercent'),
    ],
    ids=[
        'standard-fc',
        'standard-ph',
        'standard-ta',
        'hyphenated-ids',
        'uuid-ids',
        'key-fc',
        'key-cc',
        'key-tc',
        'key-ph',
        'key-ta',
        'key-ch',
        'key-cya',
        'key-salt',
        'key-bor',
        'key-borate',
        'key-csi',
        'key-temp',
        'key-waterTemp',
        'key-pressure',
        'key-flowRate',
        'key-swgCellPercent',
    ],
)
def test_sensor_unique_id_format(
    user_id: str, pool_id: str, sensor_key: str, expected_unique_id: str
) -> None:
    """Test that sensor unique_id generation matches expected golden format.

    WARNING: If this test fails after code changes, you have introduced a
    BREAKING CHANGE. Do NOT update this test to match new code. Instead:
        1. Add migration logic to handle old -> new format
        2. Add new test cases for the new format
        3. Keep old test cases to verify migration works
    """
    actual = generate_sensor_unique_id(user_id, pool_id, sensor_key)
    assert actual == expected_unique_id, (
        f'Sensor unique_id format changed! '
        f'Expected: {expected_unique_id}, Got: {actual}. '
        f'This is a BREAKING CHANGE - add migration logic!'
    )


# =============================================================================
# Parametrized Binary Sensor Unique ID Tests
# =============================================================================


@pytest.mark.parametrize(
    'user_id,pool_id,sensor_key,expected_unique_id',
    [
        # standard format
        ('user123', 'pool456', 'fc', 'poolmath_user123_pool456_fc_problem'),
        ('user123', 'pool456', 'ph', 'poolmath_user123_pool456_ph_problem'),
        # hyphenated IDs
        (
            'abc-def',
            'xyz-789',
            'cya',
            'poolmath_abc-def_xyz-789_cya_problem',
        ),
        # all binary sensor keys
        ('u', 'p', 'fc', 'poolmath_u_p_fc_problem'),
        ('u', 'p', 'cc', 'poolmath_u_p_cc_problem'),
        ('u', 'p', 'ph', 'poolmath_u_p_ph_problem'),
        ('u', 'p', 'ta', 'poolmath_u_p_ta_problem'),
        ('u', 'p', 'ch', 'poolmath_u_p_ch_problem'),
        ('u', 'p', 'cya', 'poolmath_u_p_cya_problem'),
        ('u', 'p', 'salt', 'poolmath_u_p_salt_problem'),
        ('u', 'p', 'bor', 'poolmath_u_p_bor_problem'),
        ('u', 'p', 'borate', 'poolmath_u_p_borate_problem'),
        ('u', 'p', 'csi', 'poolmath_u_p_csi_problem'),
    ],
    ids=[
        'standard-fc',
        'standard-ph',
        'hyphenated-ids',
        'key-fc',
        'key-cc',
        'key-ph',
        'key-ta',
        'key-ch',
        'key-cya',
        'key-salt',
        'key-bor',
        'key-borate',
        'key-csi',
    ],
)
def test_binary_sensor_unique_id_format(
    user_id: str, pool_id: str, sensor_key: str, expected_unique_id: str
) -> None:
    """Test that binary sensor unique_id generation matches expected golden format.

    WARNING: If this test fails after code changes, you have introduced a
    BREAKING CHANGE. Do NOT update this test to match new code. Instead:
        1. Add migration logic to handle old -> new format
        2. Add new test cases for the new format
        3. Keep old test cases to verify migration works
    """
    actual = generate_binary_sensor_unique_id(user_id, pool_id, sensor_key)
    assert actual == expected_unique_id, (
        f'Binary sensor unique_id format changed! '
        f'Expected: {expected_unique_id}, Got: {actual}. '
        f'This is a BREAKING CHANGE - add migration logic!'
    )


# =============================================================================
# Device Identifier Tests
# =============================================================================


@pytest.mark.parametrize(
    'user_id,pool_id,expected_identifier',
    [
        ('user123', 'pool456', ('poolmath', 'user123_pool456')),
        ('abc-def', 'xyz-789', ('poolmath', 'abc-def_xyz-789')),
        (
            '550e8400-e29b-41d4-a716-446655440000',
            'f47ac10b-58cc-4372-a567-0e02b2c3d479',
            (
                'poolmath',
                '550e8400-e29b-41d4-a716-446655440000_f47ac10b-58cc-4372-a567-0e02b2c3d479',
            ),
        ),
    ],
    ids=['standard', 'hyphenated', 'uuid'],
)
def test_device_identifier_format(
    user_id: str, pool_id: str, expected_identifier: tuple[str, str]
) -> None:
    """Test that device identifier generation matches expected golden format."""
    actual = generate_device_identifier(user_id, pool_id)
    assert actual == expected_identifier, (
        f'Device identifier format changed! '
        f'Expected: {expected_identifier}, Got: {actual}. '
        f'This is a BREAKING CHANGE!'
    )


# =============================================================================
# Integration Tests (verify actual entity classes match generators)
# =============================================================================


def test_actual_sensor_unique_id_matches_generator(
    sample_config: PoolMathConfig, mock_coordinator: MagicMock
) -> None:
    """Verify PoolMathSensor generates unique_id matching our generator function.

    This test ensures the generator function stays in sync with actual code.
    """
    for sensor_key, description in SENSOR_DESCRIPTIONS.items():
        sensor = PoolMathSensor(
            coordinator=mock_coordinator,
            config=sample_config,
            description=description,
        )

        expected = generate_sensor_unique_id(
            sample_config.user_id, sample_config.pool_id, sensor_key
        )

        assert sensor.unique_id == expected, (
            f'Sensor unique_id mismatch for {sensor_key}! '
            f'Generator: {expected}, Actual: {sensor.unique_id}. '
            f'Update the generator function to match actual code.'
        )


def test_actual_binary_sensor_unique_id_matches_generator(
    sample_config: PoolMathConfig, mock_coordinator: MagicMock
) -> None:
    """Verify PoolMathProblemSensor generates unique_id matching our generator function.

    This test ensures the generator function stays in sync with actual code.
    """
    for sensor_key, description in BINARY_SENSOR_DESCRIPTIONS.items():
        sensor = PoolMathProblemSensor(
            coordinator=mock_coordinator,
            config=sample_config,
            description=description,
        )

        expected = generate_binary_sensor_unique_id(
            sample_config.user_id, sample_config.pool_id, sensor_key
        )

        assert sensor.unique_id == expected, (
            f'Binary sensor unique_id mismatch for {sensor_key}! '
            f'Generator: {expected}, Actual: {sensor.unique_id}. '
            f'Update the generator function to match actual code.'
        )


def test_actual_device_info_identifier_matches_generator(
    sample_config: PoolMathConfig,
) -> None:
    """Verify get_device_info generates identifier matching our generator function."""
    device_info = get_device_info(sample_config)
    expected_identifier = generate_device_identifier(
        sample_config.user_id, sample_config.pool_id
    )

    assert expected_identifier in device_info['identifiers'], (
        f'Device identifier mismatch! '
        f'Generator: {expected_identifier}, '
        f'Actual identifiers: {device_info["identifiers"]}. '
        f'Update the generator function to match actual code.'
    )


# =============================================================================
# Legacy Format Tests (for migration verification)
# =============================================================================


@pytest.mark.parametrize(
    'pool_id,sensor_key,expected_legacy_id',
    [
        ('pool456', 'fc', 'poolmath_pool456_fc'),
        ('pool456', 'ph', 'poolmath_pool456_ph'),
        ('xyz-789', 'cya', 'poolmath_xyz-789_cya'),
    ],
)
def test_legacy_sensor_format_documented(
    pool_id: str, sensor_key: str, expected_legacy_id: str
) -> None:
    """Document and verify the legacy v1 format for migration testing.

    These IDs were used before user_id was added to unique_ids.
    Migration code converts these to the new format.
    """
    actual = generate_legacy_sensor_unique_id(pool_id, sensor_key)
    assert actual == expected_legacy_id


@pytest.mark.parametrize(
    'pool_id,sensor_key,expected_legacy_id',
    [
        ('pool456', 'fc', 'poolmath_pool456_fc_problem'),
        ('pool456', 'ph', 'poolmath_pool456_ph_problem'),
    ],
)
def test_legacy_binary_sensor_format_documented(
    pool_id: str, sensor_key: str, expected_legacy_id: str
) -> None:
    """Document and verify the legacy v1 binary sensor format for migration testing."""
    actual = generate_legacy_binary_sensor_unique_id(pool_id, sensor_key)
    assert actual == expected_legacy_id


# =============================================================================
# Completeness Tests
# =============================================================================


def test_all_sensor_keys_have_stable_ids() -> None:
    """Ensure all defined sensors have stable unique_id generation."""
    expected_sensor_keys = {
        'fc',
        'cc',
        'tc',
        'ph',
        'ta',
        'ch',
        'cya',
        'salt',
        'bor',
        'borate',
        'csi',
        'temp',
        'waterTemp',
        'pressure',
        'flowRate',
        'swgCellPercent',
    }

    actual_keys = set(SENSOR_DESCRIPTIONS.keys())
    assert actual_keys == expected_sensor_keys, (
        f'Sensor keys changed! '
        f'Expected: {expected_sensor_keys}, Got: {actual_keys}. '
        f'New sensors need unique_id stability tests added.'
    )


def test_all_binary_sensor_keys_have_stable_ids() -> None:
    """Ensure all defined binary sensors have stable unique_id generation."""
    expected_binary_keys = {
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
    }

    actual_keys = set(BINARY_SENSOR_DESCRIPTIONS.keys())
    assert actual_keys == expected_binary_keys, (
        f'Binary sensor keys changed! '
        f'Expected: {expected_binary_keys}, Got: {actual_keys}. '
        f'New binary sensors need unique_id stability tests added.'
    )
