"""Tests for Pool Math config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.poolmath.const import (
    CONF_POOL_ID,
    CONF_SHARE_URL,
    CONF_TARGET,
    CONF_USER_ID,
    DEFAULT_NAME,
    DEFAULT_TARGET,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)


async def test_form_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test we get the form on initial user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={'source': config_entries.SOURCE_USER}
    )

    assert result['type'] == FlowResultType.FORM
    assert result['step_id'] == 'user'
    assert result['errors'] == {}


async def test_form_user_step_with_valid_url(hass: HomeAssistant) -> None:
    """Test successful config flow with valid share URL."""
    with patch(
        'custom_components.poolmath.config_flow.PoolMathClient.fetch_ids_using_share_url',
        new_callable=AsyncMock,
        return_value=('test-user-id', 'test-pool-id'),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'],
            {
                CONF_SHARE_URL: 'https://www.troublefreepool.com/mypool/abc123/xyz789',
                CONF_NAME: 'My Pool',
                CONF_TARGET: DEFAULT_TARGET,
                CONF_SCAN_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            },
        )

        assert result['type'] == FlowResultType.CREATE_ENTRY
        assert result['title'] == 'Pool Math'
        assert result['data'][CONF_USER_ID] == 'test-user-id'
        assert result['data'][CONF_POOL_ID] == 'test-pool-id'
        assert result['data'][CONF_NAME] == 'My Pool'


async def test_form_user_step_with_invalid_url(hass: HomeAssistant) -> None:
    """Test config flow with invalid share URL shows error."""
    with patch(
        'custom_components.poolmath.config_flow.PoolMathClient.fetch_ids_using_share_url',
        new_callable=AsyncMock,
        return_value=(None, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'],
            {
                CONF_SHARE_URL: 'https://example.com/invalid',
                CONF_NAME: DEFAULT_NAME,
                CONF_TARGET: DEFAULT_TARGET,
                CONF_SCAN_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            },
        )

        assert result['type'] == FlowResultType.FORM
        assert result['errors'] == {'base': 'invalid_share_url'}


async def test_form_user_step_with_connection_error(hass: HomeAssistant) -> None:
    """Test config flow handles connection errors."""
    with patch(
        'custom_components.poolmath.config_flow.PoolMathClient.fetch_ids_using_share_url',
        new_callable=AsyncMock,
        side_effect=Exception('Connection failed'),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'],
            {
                CONF_SHARE_URL: 'https://www.troublefreepool.com/mypool/abc123/xyz789',
                CONF_NAME: DEFAULT_NAME,
                CONF_TARGET: DEFAULT_TARGET,
                CONF_SCAN_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            },
        )

        assert result['type'] == FlowResultType.FORM
        assert result['errors'] == {'base': 'unknown_error'}


async def test_form_user_step_duplicate_entry(hass: HomeAssistant) -> None:
    """Test config flow rejects duplicate entries."""
    # create existing entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id='test-user-id-test-pool-id',
        data={
            CONF_USER_ID: 'test-user-id',
            CONF_POOL_ID: 'test-pool-id',
        },
    )
    entry.add_to_hass(hass)

    with patch(
        'custom_components.poolmath.config_flow.PoolMathClient.fetch_ids_using_share_url',
        new_callable=AsyncMock,
        return_value=('test-user-id', 'test-pool-id'),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result['flow_id'],
            {
                CONF_SHARE_URL: 'https://www.troublefreepool.com/mypool/abc123/xyz789',
                CONF_NAME: DEFAULT_NAME,
                CONF_TARGET: DEFAULT_TARGET,
                CONF_SCAN_INTERVAL: DEFAULT_UPDATE_INTERVAL,
            },
        )

        assert result['type'] == FlowResultType.ABORT
        assert result['reason'] == 'already_configured'


class MockConfigEntry:
    """Mock ConfigEntry for testing."""

    def __init__(
        self,
        *,
        domain: str,
        unique_id: str | None = None,
        data: dict | None = None,
    ) -> None:
        """Initialize the mock config entry."""
        self.domain = domain
        self.unique_id = unique_id
        self.data = data or {}
        self.options = {}
        self.entry_id = 'test_entry_id'
        self.version = 1
        self.minor_version = 1
        self.source = 'user'
        self.title = 'Pool Math'

    def add_to_hass(self, hass: HomeAssistant) -> None:
        """Add entry to Home Assistant."""
        hass.config_entries._entries[self.entry_id] = self
        if self.unique_id:
            hass.config_entries._entries_index.setdefault(
                self.domain, {}
            )[self.unique_id] = self.entry_id
