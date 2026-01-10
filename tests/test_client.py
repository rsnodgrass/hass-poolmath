"""Tests for Pool Math API client."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


from custom_components.poolmath.client import (
    PoolMathClient,
    parse_pool,
)


class TestParsePool:
    """Tests for parse_pool function."""

    def test_parse_pool_valid(self, mock_pool_data: dict[str, Any]) -> None:
        """Test parsing valid pool data."""
        pool = parse_pool(mock_pool_data)
        assert pool is not None
        assert pool['id'] == 'test-pool-id'

    def test_parse_pool_empty(self) -> None:
        """Test parsing empty data."""
        assert parse_pool({}) is None

    def test_parse_pool_no_pools_key(self) -> None:
        """Test parsing data without pools key."""
        assert parse_pool({'other': 'data'}) is None

    def test_parse_pool_empty_pools_list(self) -> None:
        """Test parsing with empty pools list."""
        assert parse_pool({'pools': []}) is None

    def test_parse_pool_invalid_pool_structure(self) -> None:
        """Test parsing with invalid pool structure."""
        assert parse_pool({'pools': [None]}) is None
        assert parse_pool({'pools': ['string']}) is None
        assert parse_pool({'pools': [{}]}) is None


class TestPoolMathClient:
    """Tests for PoolMathClient class."""

    def test_client_initialization(self) -> None:
        """Test client initialization."""
        client = PoolMathClient(
            user_id='test-user',
            pool_id='test-pool',
            name='Test Pool',
            timeout=10.0,
        )

        assert client.user_id == 'test-user'
        assert client.pool_id == 'test-pool'
        assert client.name == 'Test Pool'
        assert 'test-user' in client.url
        assert 'test-pool' in client.url

    async def test_client_close_without_session(self) -> None:
        """Test closing client without active session."""
        client = PoolMathClient(
            user_id='test-user',
            pool_id='test-pool',
        )
        # should not raise
        await client.close()

    async def test_client_context_manager(self) -> None:
        """Test client as async context manager."""
        async with PoolMathClient(
            user_id='test-user',
            pool_id='test-pool',
        ) as client:
            assert client is not None

    @patch('aiohttp.ClientSession')
    async def test_async_get_json_success(
        self, mock_session_class: MagicMock, mock_pool_data: dict[str, Any]
    ) -> None:
        """Test successful JSON fetch."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_pool_data)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_session.closed = False
        mock_session.close = AsyncMock()

        mock_session_class.return_value = mock_session

        client = PoolMathClient(
            user_id='test-user',
            pool_id='test-pool',
        )

        result = await client.async_get_json()

        assert result == mock_pool_data
        await client.close()


class TestFetchIdsUsingShareUrl:
    """Tests for fetch_ids_using_share_url method."""

    async def test_invalid_url_format(self) -> None:
        """Test with invalid URL format."""
        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(
            'https://example.com/invalid'
        )
        assert user_id is None
        assert pool_id is None

    @patch.object(PoolMathClient, 'async_fetch_data')
    async def test_valid_troublefreepool_url(
        self, mock_fetch: AsyncMock, mock_pool_data: dict[str, Any]
    ) -> None:
        """Test with valid troublefreepool.com URL."""
        mock_fetch.return_value = mock_pool_data

        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(
            'https://www.troublefreepool.com/mypool/abc123'
        )

        assert user_id == 'test-user-id'
        assert pool_id == 'test-pool-id'

    @patch.object(PoolMathClient, 'async_fetch_data')
    async def test_valid_api_url(
        self, mock_fetch: AsyncMock, mock_pool_data: dict[str, Any]
    ) -> None:
        """Test with valid api.poolmathapp.com URL."""
        mock_fetch.return_value = mock_pool_data

        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(
            'https://api.poolmathapp.com/share/abc123'
        )

        assert user_id == 'test-user-id'
        assert pool_id == 'test-pool-id'

    @patch.object(PoolMathClient, 'async_fetch_data')
    async def test_fetch_exception(self, mock_fetch: AsyncMock) -> None:
        """Test handling of fetch exception."""
        mock_fetch.side_effect = Exception('Network error')

        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(
            'https://www.troublefreepool.com/mypool/abc123'
        )

        assert user_id is None
        assert pool_id is None

    @patch.object(PoolMathClient, 'async_fetch_data')
    async def test_missing_pool_data(self, mock_fetch: AsyncMock) -> None:
        """Test handling when pool data is missing required fields."""
        mock_fetch.return_value = {'pools': [{'pool': {}}]}

        user_id, pool_id = await PoolMathClient.fetch_ids_using_share_url(
            'https://www.troublefreepool.com/mypool/abc123'
        )

        assert user_id is None
        assert pool_id is None


class TestParseAttributes:
    """Tests for parse_attributes method."""

    def test_parse_attributes_with_timestamp(
        self, mock_pool_data: dict[str, Any]
    ) -> None:
        """Test parsing attributes includes timestamp."""
        attrs = PoolMathClient.parse_attributes(mock_pool_data, 'fc')

        assert 'last_updated' in attrs
        assert attrs['last_updated'] == 1704067200

    def test_parse_attributes_empty_data(self) -> None:
        """Test parsing with empty data."""
        attrs = PoolMathClient.parse_attributes({}, 'fc')
        assert attrs == {}

    def test_parse_attributes_missing_measurement(
        self, mock_pool_data: dict[str, Any]
    ) -> None:
        """Test parsing with measurement that has no timestamp."""
        # create data without timestamp for fc
        data = {
            'pools': [
                {
                    'pool': {
                        'overview': {'fc': 5.0},  # no fcTs
                    }
                }
            ]
        }
        attrs = PoolMathClient.parse_attributes(data, 'fc')
        assert 'last_updated' not in attrs
